"""Generic portfolio normalizer: flat DataFrame → nested JSON for image_portfolio_normalizer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _normalize_date(val: Any) -> str:
    """Strip time portion from date values (e.g. '2026-04-23 00:00:00' → '2026-04-23')."""
    s = str(val).strip()
    if s.startswith("202"):
        return s[:10]
    return s


def flatten_to_nested(
    df: pd.DataFrame,
    date_field: str = "截止日期",
    product_fields: list[str] | None = None,
    position_fields: list[str] | None = None,
    group_key: str = "产品名称",
) -> dict:
    """
    Convert a flat portfolio DataFrame to a nested JSON structure.

    Args:
        df: Source DataFrame with one row per (product, position) pair.
        date_field: Column name for the date (e.g. "截止日期").
        product_fields: Fields that belong at the product level.
                        Defaults to ["产品名称", "产品代码", "最新净值", "最新份额", "最新规模"].
        position_fields: Fields that belong inside each position dict.
                         Defaults to ["Wind代码", "资产名称", "持仓比例", "数量", "市值(本币)"].
        group_key: Column used to uniquely identify a product (e.g. "产品名称").

    Returns:
        A dict with top-level keys "metadata" and "daily_data", suitable for passing
        to ``image_portfolio_normalizer.normalize_all()``.
        The "daily_data" list contains one entry per unique date, each with a "date"
        string and a "products" list where each product has product-level fields
        plus a "positions" list.
    """
    if product_fields is None:
        product_fields = ["产品名称", "产品代码", "最新净值", "最新份额", "最新规模"]
    if position_fields is None:
        position_fields = ["Wind代码", "资产名称", "持仓比例", "数量", "市值(本币)"]

    # Ensure all expected columns are present
    available_product = [f for f in product_fields if f in df.columns]
    available_position = [f for f in position_fields if f in df.columns]

    # Build flat records with normalised dates
    records = []
    for _, row in df.iterrows():
        rec = {col: _normalize_date(row[col]) if col == date_field else row[col] for col in df.columns}
        records.append(rec)

    if not records:
        return {"metadata": {}, "daily_data": []}

    # Group by (date, group_key)
    # Key: (date_str, product_key) → product dict
    date_product_map: dict[tuple[str, str], dict] = {}
    date_order: list[str] = []

    for rec in records:
        date_str = _normalize_date(rec.get(date_field, ""))
        product_key = rec.get(group_key, "")

        map_key = (date_str, product_key)
        if map_key not in date_product_map:
            date_product_map[map_key] = {
                **{f: rec.get(f) for f in available_product},
                "positions": [],
            }
            if date_str not in date_order:
                date_order.append(date_str)

        pos = {f: rec.get(f) for f in available_position}
        date_product_map[map_key]["positions"].append(pos)

    # Build daily_data list preserving date order
    daily_data = []
    for d in date_order:
        # date_product_map key = (date_str, product_key); sorted by date then product
        sorted_keys = sorted(date_product_map.keys())
        daily_data.append({"date": d, "products": [date_product_map[k] for k in sorted_keys if k[0] == d]})

    # Build metadata
    dates_sorted = sorted(date_order)
    date_range = f"{dates_sorted[0]} ~ {dates_sorted[-1]}" if len(dates_sorted) > 1 else dates_sorted[0]
    unique_products = sorted({rec.get(group_key, "") for rec in records})

    metadata = {
        "source": "excel",
        "total_days": len(date_order),
        "total_records": len(records),
        "total_products": len(unique_products),
        "columns": list(df.columns),
        "date_range": date_range,
    }

    return {"metadata": metadata, "daily_data": daily_data}


# ----------------------------------------------------------------------
# Convenience wrappers used by 示例_持仓数据_压缩.py
# ----------------------------------------------------------------------
PORTFOLIO_PRODUCT_FIELDS = ["产品名称", "产品代码", "最新净值", "最新份额", "最新规模"]
PORTFOLIO_POSITION_FIELDS = ["Wind代码", "资产名称", "持仓比例", "数量", "市值(本币)"]
PORTFOLIO_DATE_FIELD = "截止日期"
PORTFOLIO_GROUP_KEY = "产品名称"


def normalize_portfolio(df: pd.DataFrame) -> dict:
    """Convert a flat portfolio DataFrame to nested JSON.

    Product-level fields: 产品名称, 产品代码, 最新净值, 最新份额, 最新规模
    Position fields:       Wind代码, 资产名称, 持仓比例, 数量, 市值(本币)
    """
    return flatten_to_nested(
        df,
        date_field=PORTFOLIO_DATE_FIELD,
        product_fields=PORTFOLIO_PRODUCT_FIELDS,
        position_fields=PORTFOLIO_POSITION_FIELDS,
        group_key=PORTFOLIO_GROUP_KEY,
    )


# ----------------------------------------------------------------------
# CLI entry-point for quick testing
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Portfolio DataFrame → nested JSON")
    parser.add_argument("input", help="Input xlsx/csv file")
    parser.add_argument("-o", "--output", help="Output JSON path")
    args = parser.parse_args()

    path = Path(args.input)
    df = pd.read_excel(path) if path.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(path)
    print(f"Read {len(df)} rows × {len(df.columns)} cols", file=__import__("sys").stderr)

    data = normalize_portfolio(df)
    print(f"Normalized: {len(data['daily_data'])} days, {data['metadata']['total_products']} products", file=__import__("sys").stderr)

    out = args.output or path.with_suffix(".decoded.json")
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {out}", file=__import__("sys").stderr)
