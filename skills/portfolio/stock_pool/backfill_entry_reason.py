#!/usr/bin/env python3
"""Backfill entry_reason metrics for existing Argus stock pool records.

Usage:
    PYTHONPATH=/path/to/workspace python3 backfill_entry_reason.py [--dry-run] [--limit N]
"""

import argparse
import sys
from datetime import datetime

sys.path.insert(0, "/home/pascal/.openclaw/workspace-yquant")


def format_date(d):  # noqa: N802
    return d.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description="回填 entry_reason 指标数据")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--limit", type=int, default=0, help="限制更新条数（0=全部）")
    args = parser.parse_args()

    from skills.portfolio.stock_pool.repository import StockPoolRepository
    from pymongo import MongoClient
    from bson import ObjectId

    repo = StockPoolRepository()

    # Load all active argus records
    all_items = []
    cursor = None
    while True:
        batch = repo.list(source="argus", status="active", limit=200, cursor=cursor)
        all_items.extend(batch["items"])
        cursor = batch.get("next_cursor")
        if not cursor:
            break

    argus_items = [i for i in all_items if i.get("source") == "argus"]
    print(f"Found {len(argus_items)} active Argus stock pool records")

    if args.limit > 0:
        argus_items = argus_items[: args.limit]

    # Build metrics map from argus_signal_pool
    client = MongoClient("mongodb://myq:6812345@172.25.240.1:27017/")
    signal_col = client["tradingagents"]["08_research_argus_signal_pool"]

    metrics_map = {}
    for doc in signal_col.find(
        {},
        {
            "wind_code": 1,
            "confidence": 1,
            "consensus_confidence": 1,
            "contributing_products_count": 1,
            "crowding_score": 1,
            "crowding_level": 1,
            "contributing_products": 1,
        },
    ).sort("_id", -1):
        code = doc.get("wind_code")
        if code and code not in metrics_map:
            metrics_map[code] = doc

    print(f"Loaded metrics for {len(metrics_map)} unique wind_codes from argus_signal_pool")

    updated = 0
    skipped = 0
    errors = []

    for item in argus_items:
        wind_code = item.get("wind_code")
        signal_data = metrics_map.get(wind_code, {})

        metrics = {
            "reason": item.get("entry_reason", {}).get("reason", ""),
            "bayesian_score": signal_data.get("confidence") or signal_data.get("bayesian_score") or 0,
            "consensus_confidence": signal_data.get("consensus_confidence") or 0,
            "contributing_products": signal_data.get("contributing_products") or [],
            "contributing_products_count": signal_data.get("contributing_products_count") or 0,
            "crowding_score": signal_data.get("crowding_score") or 0,
            "crowding_level": signal_data.get("crowding_level") or "LOW",
        }

        if args.dry_run:
            print(
                f"  [dry-run] {wind_code}: bayes={metrics['bayesian_score']:.2f}  "
                f"consensus={metrics['consensus_confidence']:.2f}  "
                f"products={metrics['contributing_products_count']}  "
                f"crowding={metrics['crowding_level']}"
            )
        else:
            try:
                result = repo.collection.update_one(
                    {"_id": ObjectId(item["id"])},
                    {
                        "$set": {
                            "entry_reason": metrics,
                            "audit.updated_at": datetime.utcnow(),
                            "audit.updated_by": "system:backfill",
                        }
                    },
                )
                if result.modified_count > 0:
                    updated += 1
                    print(
                        f"  ✅ {wind_code}: bayes={metrics['bayesian_score']:.2f}  "
                        f"consensus={metrics['consensus_confidence']:.2f}  "
                        f"products={metrics['contributing_products_count']}  "
                        f"crowding={metrics['crowding_level']}"
                    )
                else:
                    skipped += 1
                    print(f"  ⚠️  {wind_code}: no document modified")
            except Exception as e:
                errors.append({"id": item["id"], "wind_code": wind_code, "error": str(e)})
                print(f"  ❌ {wind_code}: {e}")

    print(f"\n{'[dry-run] ' if args.dry_run else ''}Done: updated={updated}, skipped={skipped}, errors={len(errors)}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e['wind_code']}: {e['error']}")


if __name__ == "__main__":
    main()