#!/usr/bin/env python3
"""
Data completeness check for Smart Money portfolio collections.

Usage:
    .venv/bin/python scripts/check_data_completeness.py --start 2025-07-07 --end 2025-07-09
    .venv/bin/python scripts/check_data_completeness.py --start 2025-07-07 --end 2025-07-09 --products SM001,SM002
    .venv/bin/python scripts/check_data_completeness.py --start 2025-07-07 --end 2025-07-09 --json

Output: matrix (product × date) for each collection (position / nav / trade).
Reports missing days per product (real gaps, excluding weekends).

Notes (learned 2026-06-27):
- position_date / nav_date / trade_date are stored as STRINGS, not datetime.
  Use $in with string dates or $gte/$lte with string range (works because
  ISO date format is lexicographically sortable).
- portfolio_position fields: holding_ratio / shares / market_value
  (NOT position_ratio / quantity / market_value_local).
- portfolio_trade is sparse — not every product trades every day.
  Don't treat missing trade rows as "data gap".
- portfolio_position/nav should have rows every trading day per product.
  Missing trading-day rows = real gap worth flagging.

Writes nothing to MongoDB. Read-only audit script.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# Repo paths — resolve relative to script location
SKILL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from loaders.mongodb_loader import PortfolioMongoLoader


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Sat=5, Sun=6


def trading_days(start: date, end: date) -> list[date]:
    return [d for d in (start + timedelta(days=i) for i in range((end - start).days + 1)) if not is_weekend(d)]


def matrix_report(db, start: date, end: date, products: list[str], collections: list[str]) -> dict:
    """Build product × date count matrix for each collection.

    NOTE: position_date / nav_date / trade_date are strings in MongoDB,
    so use $in with string list rather than $gte/$lte with date objects.
    """
    date_strs = [d.isoformat() for d in trading_days(start, end)]

    # Initialize all expected cells with 0
    expected = {(p, d): 0 for p in products for d in date_strs}

    result = {}
    for coll_name in collections:
        date_field = {
            "portfolio_position": "position_date",
            "portfolio_nav": "nav_date",
            "portfolio_trade": "trade_date",
        }[coll_name]
        grid = defaultdict(lambda: defaultdict(int))
        for r in db[coll_name].find(
            {date_field: {"$in": date_strs}, "product_code": {"$in": products}},
            {"_id": 0, "product_code": 1, date_field: 1},
        ):
            grid[r["product_code"]][r[date_field]] += 1
        result[coll_name] = {
            "date_field": date_field,
            "grid": {p: dict(grid[p]) for p in products},
            "totals": {p: sum(grid[p].values()) for p in products},
        }
    return {"date_range": [start.isoformat(), end.isoformat()], "trading_days": date_strs, "collections": result}


def print_report(rep: dict, products: list[str]) -> None:
    days = rep["trading_days"]
    start, end = rep["date_range"]
    print(f"=== Smart Money Data Completeness: {start} ~ {end} ===")
    print(f"(weekends excluded; total trading days: {len(days)})")
    print()

    for coll_name, info in rep["collections"].items():
        print(f"-- {coll_name} ({info['date_field']}) --")
        header = f"{'product':<8}" + "".join(f"{d[-2:]:>5}" for d in days) + " sum"
        print(header)
        for p in products:
            row = info["grid"].get(p, {})
            counts = [row.get(d, 0) for d in days]
            print(f"  {p:<6}" + "".join(f"{c:>5}" for c in counts) + f"  {info['totals'].get(p, 0)}")
        print()

    # Gap analysis: position/nav missing on trading days
    print("-- Gap analysis (missing on trading days) --")
    for coll_name in ("portfolio_position", "portfolio_nav"):
        info = rep["collections"][coll_name]
        for p in products:
            row = info["grid"].get(p, {})
            missing = [d for d in days if row.get(d, 0) == 0]
            if missing:
                print(f"  {coll_name} {p}: missing on {missing}")
            else:
                print(f"  {coll_name} {p}: ✅ all {len(days)} trading days present")


def main():
    ap = argparse.ArgumentParser(description="Smart Money portfolio data completeness check")
    ap.add_argument("--start", required=True, help="start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="end date YYYY-MM-DD")
    ap.add_argument("--products", default="SM001,SM002,SM003,SM004,SM012",
                    help="comma-separated product codes (default: all known)")
    ap.add_argument("--collections", default="portfolio_position,portfolio_nav,portfolio_trade",
                    help="comma-separated collection names")
    ap.add_argument("--json", action="store_true", help="output JSON instead of human-readable")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    products = args.products.split(",")
    collections = args.collections.split(",")

    db = PortfolioMongoLoader()._db()
    rep = matrix_report(db, start, end, products, collections)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(rep, products)


if __name__ == "__main__":
    main()