"""Image portfolio data normalizer.

Normalizes nested JSON from image OCR into flattened records ready for database insertion.
"""
from typing import Any


def normalize_basic_info(daily_data: list[dict]) -> list[dict]:
    """Extract product basic info records.

    Args:
        daily_data: List of daily data dicts from decoded image JSON.

    Returns:
        List of basic info records with product_code, product_name,
        and latest nav/share/aum from the most recent date.
    """
    seen: set = set()
    latest_by_product: dict = {}

    # First pass: collect latest nav/share/aum per product (from last date)
    for day in daily_data:
        for product in day.get("products", []):
            code = product.get("产品代码")
            if code:
                latest_by_product[code] = {
                    "product_code": code,
                    "product_name": product.get("产品名称", ""),
                    "latest_nav": product.get("最新净值"),
                    "latest_share": product.get("最新份额"),
                    "latest_aum": product.get("最新规模"),
                }

    # Return in insertion order (first seen)
    for day in daily_data:
        for product in day.get("products", []):
            code = product.get("产品代码")
            if code and code not in seen:
                seen.add(code)

    records = [latest_by_product[code] for code in seen if code in latest_by_product]
    return records


def normalize_nav(daily_data: list[dict]) -> list[dict]:
    """Extract NAV records.

    Args:
        daily_data: List of daily data dicts from decoded image JSON.

    Returns:
        List of NAV records with date, product_code, nav, aum, share.
    """
    records = []
    for day in daily_data:
        date = day.get("date")
        for product in day.get("products", []):
            records.append({
                "nav_date": date,
                "product_code": product.get("产品代码"),
                "nav": product.get("最新净值"),
                "aum": product.get("最新规模"),
                "share": product.get("最新份额"),
            })
    return records


def normalize_position(daily_data: list[dict]) -> list[dict]:
    """Extract position records.

    Args:
        daily_data: List of daily data dicts from decoded image JSON.

    Returns:
        List of position records with date, product_code, asset_wind_code,
        asset_name, holding_ratio, shares, market_value.
    """
    records = []
    for day in daily_data:
        date = day.get("date")
        for product in day.get("products", []):
            product_code = product.get("产品代码")
            for pos in product.get("positions", []):
                records.append({
                    "position_date": date,
                    "product_code": product_code,
                    "asset_wind_code": pos.get("Wind代码"),
                    "asset_name": pos.get("资产名称"),
                    "holding_ratio": pos.get("持仓比例"),
                    "shares": pos.get("数量"),
                    "market_value": pos.get("市值(本币)"),
                })
    return records


def normalize_all(decoded: dict) -> dict:
    """Normalize entire decoded image JSON.

    Args:
        decoded: Full decoded JSON from image OCR with 'daily_data' key.

    Returns:
        Dict with 'basic_info', 'nav', 'position' keys mapping to record lists.
    """
    daily_data = decoded.get("daily_data", [])
    return {
        "basic_info": normalize_basic_info(daily_data),
        "nav": normalize_nav(daily_data),
        "position": normalize_position(daily_data),
    }


if __name__ == "__main__":
    import json

    with open("examples/mock_3days_decoded.json") as f:
        decoded = json.load(f)

    normalized = normalize_all(decoded)
    print("=== Normalized Record Summary ===")
    print(f"basic_info : {len(normalized['basic_info'])} records")
    for r in normalized["basic_info"]:
        print(f"  {r['product_code']} | {r['product_name']}")

    print(f"\nnav         : {len(normalized['nav'])} records")
    print(f"  sample: {normalized['nav'][0]}")

    print(f"\nposition    : {len(normalized['position'])} records")
    print(f"  sample: {normalized['position'][0]}")