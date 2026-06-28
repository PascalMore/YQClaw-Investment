# Trading-Day Discipline for Portfolio Data Audits

Triggered 2026-06-28 when auditing `portfolio_position / portfolio_nav / portfolio_trade` for
2025-06-30 ~ 2026-06-25. The first pass produced 137 false "missing" days that were actually
real A-share trading days, because the existing naive `date.weekday() < 5` filter only excludes
weekends — not Chinese statutory holidays (国庆、春节、劳动节、端午、etc.).

## The two real defects to know about

### 1. `check_data_completeness.py` uses weekend-only filter

File: `scripts/check_data_completeness.py:46`

```python
def trading_days(start: date, end: date) -> list[date]:
    return [d for d in (start + timedelta(days=i) for i in range((end - start).days + 1)) if not is_weekend(d)]
```

This produces 259 "trading days" for 2025-06-30 ~ 2026-06-25, of which **137 are statutory
holidays in 2025 that fall on weekdays**. Every one of those gets reported as a "missing" day
in the gap report, drowning the real signal.

**Correct count for the same window: 240 trading days** (from `exchange_calendars` XSHG).

### 2. `skills/infra/date_utils.py:15-47` has a 2025-silently-dropped fallback

```python
TRADING_DAYS_2026 = set([
    # 2026 only
    '2026-01-02', '2026-01-05', ...
])
```

`is_trading_day()` and `get_trading_dates()` try `exchange_calendars` first, but if it's not
installed in the active venv (the project root `.venv` does NOT have it by default — only
`skills/research/argus/.venv` does), the fallback returns:

- All 2025 dates: **wrongly classified as non-trading** (e.g. `is_trading_day("2025-09-03")`
  returns `False`, but 2025-09-03 was a normal A-share trading day)
- All 2026 dates: correct (via the hardcoded set)

Impact: any module that uses `get_trading_dates()` for **2025 dates** (argus backfill,
`refresh_all`, `backfill_stock_pool_audit`, etc.) will silently skip every 2025 day, regardless
of whether real data exists.

## How to do an A-share trading-day-correct audit

### Preferred path — engineering-grade one-liner (2026-06-28)

Use `scripts/portfolio_audit_real.py` which already wraps the XSHG calendar + JSON matrix
+ position/nav consistency check. It calls `check_data_completeness.py --json` internally
and cross-filters against `skills.infra.date_utils.get_trading_dates` (which auto-routes to
`exchange_calendars` XSHG when available).

```bash
# ✅ 一行命令搞定 (5 个产品 × position/nav/trade，跨年窗口默认走真日历)
.venv/bin/python skills/data/data-pipeline/scripts/portfolio_audit_real.py \
  --start 2025-06-30 --end 2026-06-25

# JSON 输出给下游
.venv/bin/python skills/data/data-pipeline/scripts/portfolio_audit_real.py \
  --start 2025-06-30 --end 2026-06-25 --json > /tmp/portfolio_audit.json

# 指定产品 / 单日
.venv/bin/python skills/data/data-pipeline/scripts/portfolio_audit_real.py \
  --start 2025-09-01 --end 2025-09-12 --products SM012
```

The script is **read-only** (never writes to MongoDB). It reuses the matrix from
`check_data_completeness.py --json` so the two scripts never disagree on row counts.

### Underlying primitive (when you need to embed the calendar in other code)

```python
import exchange_calendars as xcals
cal = xcals.get_calendar("XSHG")
real_td = [d.strftime("%Y-%m-%d") for d in cal.sessions_in_range("2025-06-30", "2026-06-25")]
# → 240 days for that window
```

### Venv state as of 2026-06-28 (replaces earlier "needs pip install" advice)

- ✅ **Project root `.venv` (Python 3.12.13)**: `exchange_calendars==4.13.2` installed
  (2026-06-28). `date_utils.get_trading_dates()` now auto-uses XSHG for any date range.
  Verified: 240 trading days for 2025-06-30 ~ 2026-06-25; `is_trading_day` 7/7 probe passes
  (国庆/元旦/春节/清明/劳动节/端午 all correct).
- ✅ **`skills/research/argus/.venv`**: also has `exchange_calendars`, but Python version
  differs from main `.venv` (3.12 vs 3.12, both OK now). Use main `.venv` for consistency.
- ❌ **Do NOT** keep widening the hardcoded `TRADING_DAYS_2026` set in `date_utils.py` —
  the hardcoded set will keep drifting from reality every year. The XSHG calendar is
  authoritative.

### DEPRECATED — "if you can't add a venv dependency" workaround (2026-06-28)

The argus venv detour is **no longer needed** because the project root `.venv` now has
`exchange_calendars`. Kept here for one release in case someone finds the new install
broken and needs to fall back. Plan: remove this section in a later date cleanup.

```bash
# Last-resort fallback (only if main .venv install somehow breaks)
# 1. get real trading days from argus venv (offline, one-time)
/home/pascal/workspace/yquant-investment/skills/research/argus/.venv/bin/python -c "
import exchange_calendars as xcals
c = xcals.get_calendar('XSHG')
import json
print(json.dumps([d.strftime('%Y-%m-%d') for d in c.sessions_in_range('2025-06-30', '2026-06-25')]))
" > /tmp/real_td.json

# 2. feed as filter to a custom gap-check wrapper (don't pass to check_data_completeness.py;
#    it doesn't accept a precomputed list — you'd need a small wrapper)
```

**Don't** use this workaround by default. Use `portfolio_audit_real.py` instead.

## Engineering entry point (2026-06-28 新增)

`scripts/portfolio_audit_real.py` is the production audit script. It:

- Reuses `check_data_completeness.py --json` for the product×date row-count matrix
- Cross-filters against `skills.infra.date_utils.get_trading_dates` (XSHG real calendar)
- Emits position / nav gap list, trade coverage stats, and position↔nav consistency check
- Supports `--matrix-cache PATH` to skip mongo on repeat calls (writes cache on first run)
- Supports `--json` for downstream tooling (no jq dependency; use `python3 -c` to extract fields)

Standard usage:

```bash
# 默认文本输出
.venv/bin/python skills/data/data-pipeline/scripts/portfolio_audit_real.py \
  --start 2025-06-30 --end 2026-06-25

# JSON + matrix cache（多次跑用，第二次开始 <1s）
.venv/bin/python skills/data/data-pipeline/scripts/portfolio_audit_real.py \
  --start 2025-06-30 --end 2026-06-25 --matrix-cache /tmp/m.json --json
```

Cross-references:

- `scripts/portfolio_audit_real.py` — production audit script (CLI / argparse / --json / --matrix-cache)
- `skills/data/data-pipeline/SKILL.md` "数据完整性检查" 段 — user-facing recipe with python -c field extraction examples
- `skills/infra/date_utils.py:130-159` — `get_trading_dates()` source (XSHG path)
- `references/trading-day-discipline-2026-06-28.md` — this file (historical bug context)

For 5 products (SM001 / SM002 / SM003 / SM004 / SM012) over 240 real trading days:

| Collection | Pattern | Detail |
|---|---|---|
| `portfolio_position` | All 5 products missing **2025-09-03** | One systemic gap day — likely OCR/source failure on a single day |
| `portfolio_position` | Scattered misses 2025-09-04/05/08/16 | Per-product individual gaps (1-2 days each) |
| `portfolio_nav` | Identical to position | Confirms position + nav come from the same source batch |
| `portfolio_trade` | Sparse, expected | SM003: 89.6% coverage. SM012: 48.8% (mostly idle since 2025-11) |

`portfolio_trade` being sparse is **not a data quality issue** — the user already confirmed
this in 2026-06-27. The user expects trade to be "roughly every trading day", which is true
for SM003 (active) but not for SM012 (passive hold). Do not flag trade sparsity as a gap
unless a product is **more sparse than its baseline** (e.g. SM003 drops below 80%).

## When to use this recipe

- Audit asks: "对 portfolio_nav/position/trade 做完整性核验"
- Audit asks: "哪些交易日的 portfolio 数据缺了"
- Pre-flight before any backfill (`refresh_all --backfill`, argus backfill, etc.) to know
  which dates the backfill actually needs to target
- Diagnosing "argus/refresh claims no data to process for 2025" — almost certainly this bug

## Cross-references

- `scripts/portfolio_audit_real.py` — engineering-grade audit (2026-06-28); wraps
  `check_data_completeness.py --json` + `date_utils.get_trading_dates` + position/nav
  consistency + trade coverage. **Use this for any new audit**, not the inline recipes
  above.
- `scripts/check_data_completeness.py` — the underlying audit script; the `--json` output
  is the input to `portfolio_audit_real.py`. Weekday-only filter is preserved here (intentional,
  to keep this script as a simple low-level tool). Do NOT use its "missing" list directly
  for cross-year windows.
- `skills/infra/date_utils.py:15-47` — the `TRADING_DAYS_2026` fallback (now deprecated
  since root `.venv` has `exchange_calendars`); kept for graceful degradation if the
  pip install is somehow removed.
- `references/agent-overengineering-anti-patterns.md` — don't pre-validate the date field
  with naive weekday checks; the pipeline knows.
