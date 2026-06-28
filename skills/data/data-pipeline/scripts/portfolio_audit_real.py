#!/usr/bin/env python3
"""
Portfolio completeness audit using exchange_calendars XSHG (real A-share calendar).

Companion to `check_data_completeness.py`. The original script uses
`date.weekday() < 5` (weekend-only) as its trading-day filter, which produces
100+ false "missing" days for any window that crosses a Chinese statutory
holiday. This script:
  1. Calls the same `check_data_completeness.py --json` for the product×date
     row counts (so it reuses the Mongo loader and date-string handling).
  2. Cross-filters against `skills.infra.date_utils.get_trading_dates`,
     which goes through `exchange_calendars` XSHG (or the hardcoded
     `TRADING_DAYS_2026` fallback if exchange_calendars is not installed).
  3. Emits a per-(product, collection) gap report, trade coverage stats, and a
     position↔nav consistency check. Writes nothing to MongoDB.

Usage:
    .venv/bin/python scripts/portfolio_audit_real.py --start 2025-06-30 --end 2026-06-25
    .venv/bin/python scripts/portfolio_audit_real.py --start 2025-06-30 --end 2026-06-25 --json
    .venv/bin/python scripts/portfolio_audit_real.py --start 2025-06-30 --end 2026-06-25 --products SM001,SM003

Requirements:
    - Project root `.venv` must have `exchange_calendars` installed
      (`pip install exchange_calendars`). The skill-root venv (this script's
      directory) inherits the project venv if you run it via
      `yquant-investment/.venv/bin/python`. Without exchange_calendars, the
      fallback only covers 2026 and silently drops all 2025 trading days.

Notes (learned 2026-06-28):
- For 2025-06-30 ~ 2026-06-25, real XSHG trading days = 240 (not 259 from the
  weekend-only filter; not 122 from the date_utils fallback pre-fix).
- `portfolio_trade` is sparse. SM003 / SM004 trade on 84-90% of trading days;
  SM012 only 48.8% (mostly idle since 2025-11). Do NOT flag trade sparsity as
  a data gap unless a product drops below its own baseline.
- position ↔ nav gap dates are expected to be 100% identical because they
  share the same source batch. Any mismatch = real anomaly worth investigating.
"""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Repo paths — resolve relative to script location
#   scripts/portfolio_audit_real.py
#     .parent  -> skills/data/data-pipeline/scripts/  (SCRIPT_DIR)
#     .parent  -> skills/data/data-pipeline/          (SKILL_ROOT)
#     .parent  -> skills/data/                         (intermediate)
#     .parent  -> skills/                              (SKILLS_DIR)
#     .parent  -> yquant-investment/                  (REPO_ROOT)
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SKILL_ROOT.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from skills.infra.date_utils import get_trading_dates  # noqa: E402

COLLECTIONS = ["portfolio_position", "portfolio_nav", "portfolio_trade"]
INNER_SCRIPT = SKILL_ROOT / "scripts" / "check_data_completeness.py"


def fetch_matrix(
    start: str,
    end: str,
    products: list[str] | None,
    cache_path: str | Path | None = None,
) -> dict:
    """Load the product×date row-count matrix.

    If `cache_path` is given and exists, load JSON from that file (skips mongo).
    Otherwise run `check_data_completeness.py --json` and parse the matrix,
    optionally writing the result to `cache_path` for reuse.
    """
    if cache_path is not None and Path(cache_path).exists():
        with open(cache_path) as f:
            return json.load(f)

    cmd = [sys.executable, str(INNER_SCRIPT), "--start", start, "--end", end, "--json"]
    if products:
        cmd.extend(["--products", ",".join(products)])
    proc = subprocess.run(
        cmd,
        cwd=str(SKILL_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"check_data_completeness.py failed:\n{proc.stderr}\n")
        sys.exit(proc.returncode)
    matrix = json.loads(proc.stdout)

    if cache_path is not None:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(matrix, f, indent=2, ensure_ascii=False)

    return matrix


def build_gap_report(matrix: dict, real_trading_days: list[str]) -> dict:
    """For each (collection, product), list real trading days missing rows."""
    report = {}
    for coll in COLLECTIONS:
        report[coll] = {}
        for product, grid in matrix["collections"][coll]["grid"].items():
            missing = [d for d in real_trading_days if grid.get(d, 0) == 0]
            report[coll][product] = missing
    return report


def trade_coverage(matrix: dict, real_trading_days: list[str]) -> dict:
    """Per-product: how many trading days have at least one trade row."""
    out = {}
    for product, grid in matrix["collections"]["portfolio_trade"]["grid"].items():
        has = sum(1 for d in real_trading_days if grid.get(d, 0) > 0)
        total_rows = sum(grid.get(d, 0) for d in real_trading_days)
        out[product] = {
            "days_with_trades": has,
            "trading_days": len(real_trading_days),
            "coverage_pct": round(has / len(real_trading_days) * 100, 1) if real_trading_days else 0,
            "total_rows": total_rows,
        }
    return out


def position_nav_consistency(gap_report: dict) -> dict:
    """Check that position and nav have identical gap dates per product."""
    out = {}
    for product in gap_report["portfolio_position"]:
        pos = set(gap_report["portfolio_position"][product])
        nav = set(gap_report["portfolio_nav"][product])
        out[product] = {
            "match": pos == nav,
            "only_in_position": sorted(pos - nav),
            "only_in_nav": sorted(nav - pos),
            "intersection_size": len(pos & nav),
        }
    return out


def render_text(
    matrix: dict,
    real_trading_days: list[str],
    gap_report: dict,
    coverage: dict,
    consistency: dict,
) -> str:
    products = list(matrix["collections"]["portfolio_position"]["grid"].keys())
    lines = []
    lines.append(f"XSHG real trading days: {len(real_trading_days)}")
    lines.append(f"products: {products}")
    lines.append(f"date range: {matrix['date_range']}")
    lines.append("")
    lines.append("=" * 80)
    lines.append(f"GAP REPORT (XSHG real trading days = {len(real_trading_days)})")
    lines.append("=" * 80)

    for coll in COLLECTIONS:
        lines.append("")
        lines.append(f"--- {coll} ---")
        for product, missing in gap_report[coll].items():
            if missing:
                lines.append(f"  {product}: MISSING on {len(missing)}/{len(real_trading_days)} trading days")
                lines.append(f"     days: {missing}")
            else:
                lines.append(f"  {product}: ✅ COMPLETE ({len(real_trading_days)}/{len(real_trading_days)})")

    lines.append("")
    lines.append("=" * 80)
    lines.append("TRADE COVERAGE (sparse, by-product baseline)")
    lines.append("=" * 80)
    for product, stat in coverage.items():
        lines.append(
            f"  {product}: {stat['days_with_trades']}/{stat['trading_days']} = "
            f"{stat['coverage_pct']}% | total rows: {stat['total_rows']}"
        )

    lines.append("")
    lines.append("=" * 80)
    lines.append("POSITION vs NAV GAP CONSISTENCY")
    lines.append("=" * 80)
    for product, c in consistency.items():
        if c["match"]:
            lines.append(f"  {product}: ✅ position gaps == nav gaps ({c['intersection_size']} days)")
        else:
            lines.append(f"  {product}: ⚠️  MISMATCH")
            if c["only_in_position"]:
                lines.append(f"      only in position: {c['only_in_position']}")
            if c["only_in_nav"]:
                lines.append(f"      only in nav:      {c['only_in_nav']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Portfolio completeness audit using real XSHG trading calendar.",
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--products",
        default=None,
        help="Comma-separated product codes (default: all from matrix)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human text",
    )
    parser.add_argument(
        "--matrix-cache",
        default=None,
        metavar="PATH",
        help=(
            "Read product×date matrix from this JSON file if it exists (skips mongo); "
            "otherwise run check_data_completeness.py and write the matrix to this path "
            "for subsequent runs to reuse."
        ),
    )
    args = parser.parse_args()

    products = [p.strip() for p in args.products.split(",")] if args.products else None
    matrix = fetch_matrix(args.start, args.end, products, args.matrix_cache)
    real_td = get_trading_dates(args.start, args.end)
    gap_report = build_gap_report(matrix, real_td)
    coverage = trade_coverage(matrix, real_td)
    consistency = position_nav_consistency(gap_report)

    if args.json:
        out = {
            "date_range": [args.start, args.end],
            "trading_days_count": len(real_td),
            "products": list(matrix["collections"]["portfolio_position"]["grid"].keys()),
            "gap_by_collection": gap_report,
            "trade_coverage": coverage,
            "position_nav_consistency": consistency,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print(render_text(matrix, real_td, gap_report, coverage, consistency))


if __name__ == "__main__":
    main()
