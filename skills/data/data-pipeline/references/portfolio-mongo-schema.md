# Portfolio MongoDB Schema — Quick Reference (2026-06-29 update)

> **Use this when:** writing ad-hoc queries, building export scripts, or auditing
> data integrity against `tradingagents` collection.
>
> **One-time update from 2026-06-29 audit:** this file consolidates the field-name
> and type pitfalls that bit us across multiple sessions. Read it before
> writing any new portfolio Mongo query.

## Collections Overview

| Collection | Unique key | Business date field | Date type |
|------------|------------|---------------------|-----------|
| `portfolio_basic_info` | `product_code` | (none) | — |
| `portfolio_nav` | `(product_code, nav_date)` | `nav_date` | **string** `YYYY-MM-DD` |
| `portfolio_position` | `(product_code, position_date, asset_wind_code)` | `position_date` | **string** `YYYY-MM-DD` |
| `portfolio_trade` | `(product_code, trade_date, asset_wind_code, direction)` | `trade_date` | **string** `YYYY-MM-DD` |

⚠️ **All date fields are `str`, not `datetime.datetime`.** See "Type Pitfall" below.

## Actual Field Names Per Collection

`portfolio_position` (实测，不是文档说的):

```
asset_name           str
asset_wind_code      str   (e.g. "600000.SH")
holding_ratio        float (0.0853 = 8.53%, NOT 8.53)
shares               int
market_value         int   (in 元, NOT local currency)
position_date        str
product_code         str   (SM001/SM002/SM003/SM004/SM012/CCT-001)
updated_at           datetime (BSON)
source_image         str (file path of original jpg, optional)
```

❌ **Wrong field names** (these do not exist; old SKILL drafts and "common sense" suggest them):

- `position_ratio` → use `holding_ratio`
- `quantity` → use `shares`
- `market_value_local` → use `market_value`
- `wind_code` → use `asset_wind_code`

`portfolio_nav`:

```
nav_date       str
product_code   str
nav            float   (单位净值, e.g. 0.9697)
aum            float   (资产规模, in 元; 1.46e8 = 1.46亿)
share          float   (份额; 早期记录可能没有这个字段)
updated_at     datetime (BSON)
```

❌ **Wrong field names**: `scale` (实际是 `aum`), `nav_value` (实际是 `nav`).

`portfolio_basic_info` (snapshot, 最新一次更新的元数据):

```
product_code   str   (PK)
product_name   str   (e.g. "ZO-002")
latest_nav     float (snapshot of most recent nav)
latest_aum     float (snapshot of most recent aum)
updated_at     datetime
```

**Note**: `latest_nav` / `latest_aum` are not "latest by date" — they are
"latest by `updated_at` of the basic_info doc itself". Don't use these for
historical backfilling; query `portfolio_nav` instead.

`portfolio_trade`:

```
trade_date        str
product_code      str
asset_wind_code   str
asset_name        str
direction         str  ("买入" / "卖出")
change_ratio      float (0.05 = 5% INCREASE for 买入, 5% DECREASE for 卖出 — sign is INVERTED in source)
change_amount     int   (in 元, signed)
updated_at        datetime
```

❌ **Wrong field names**: `quantity` (不在此集合), `wind_code`.

## Type Pitfall — String Date vs datetime

**Symptom**: `bson.errors.InvalidDocument: cannot encode object: datetime.date(...)` when using `datetime.date` in `$gte` / `$lte`.

```python
# ❌ WRONG — throws InvalidDocument
db['portfolio_position'].find({'position_date': {'$gte': datetime.date(2025, 7, 1)}})

# ❌ WRONG — returns 0 rows (datetime > str lexicographically)
db['portfolio_position'].find({'position_date': {'$gte': datetime.datetime(2025, 7, 1)}})

# ✅ CORRECT — $in with strings
db['portfolio_position'].find({'position_date': {'$in': ['2025-07-01', '2025-07-02']}})

# ✅ CORRECT — string range (lex order = date order for YYYY-MM-DD)
db['portfolio_position'].find({'position_date': {'$gte': '2025-07-01', '$lte': '2025-07-31'}})
```

**Diagnosis**: before writing a query, do
`db['portfolio_position'].find_one()` and check `type(r['position_date'])` to confirm string.

## First-time Use Recipe

Don't guess field names. Always start with `find_one()`:

```python
import sys
sys.path.insert(0, '/home/pascal/workspace/yquant-investment/skills/data/data-pipeline/scripts')
from loaders.mongodb_loader import PortfolioMongoLoader
db = PortfolioMongoLoader()._db()

# Print actual fields for each collection
for coll in ['portfolio_position', 'portfolio_nav', 'portfolio_trade', 'portfolio_basic_info']:
    r = db[coll].find_one({'product_code': 'SM004'})
    if r:
        print(f"{coll}: {sorted(r.keys())}")
        print(f"  sample: {r}")
```

Then write the query based on the printed keys.

## product_code ↔ product_name Mapping

| product_code | product_name |
|--------------|--------------|
| SM001 | ZO-001 |
| SM002 | ZO-002 |
| SM003 | ZO-003 |
| SM004 | ZO-002 ← note: SM004's name is ALSO ZO-002 (2026 rename history) |
| SM012 | ZO-012 |
| CCT-001 | CCT-001 |

**Source of truth**: `portfolio_basic_info` — don't hardcode the mapping, query it:

```python
db['portfolio_basic_info'].find_one({'product_name': 'ZO-002'})['product_code']  # → 'SM004'
```

## Trade Density Reality (don't over-report as "data missing")

`portfolio_trade` is **sparse** — not every product has a trade every day. Don't
report low coverage as a data quality issue:

- SM001/SM002: ~60% coverage (145/242 days)
- SM003: ~89% coverage
- SM004: ~84% coverage
- SM012: ~48% coverage (lowest, but still normal)

Use `portfolio_audit_real.py --json` to see actual coverage; don't infer from
gap counts.

## Ad-hoc Query Templates

**SM002 持仓 + 当日 nav（按日期 join）**:

```python
from datetime import date
import pandas as pd

DATES = [f'2026-06-{d:02d}' for d in range(1, 26)]
# Pre-fetch nav dict
nav_by_date = {r['nav_date']: (r['nav'], r['aum'])
               for r in db['portfolio_nav'].find({
                   'product_code': 'SM002',
                   'nav_date': {'$in': DATES}
               })}
# Position rows with nav join
rows = []
for r in db['portfolio_position'].find({
    'product_code': 'SM002',
    'position_date': {'$in': DATES}
}):
    nav, aum = nav_by_date.get(r['position_date'], (None, None))
    rows.append({
        'date': r['position_date'],
        'code': r['asset_wind_code'],
        'name': r['asset_name'],
        'ratio': r['holding_ratio'],
        'shares': r.get('shares', 0),
        'market_value': r.get('market_value', 0),
        'nav': nav,
        'aum': aum,
    })
df = pd.DataFrame(rows)
```

**Trade coverage for last 30 trading days**:

```python
# Use portfolio_audit_real.py instead of writing this from scratch
import subprocess
r = subprocess.run([
    '.venv/bin/python', 'skills/data/data-pipeline/scripts/portfolio_audit_real.py',
    '--start', '2026-05-15', '--end', '2026-06-25', '--json'
], capture_output=True, text=True, cwd='/home/pascal/workspace/yquant-investment')
import json
d = json.loads(r.stdout)
print(d['trade_coverage'])
```
