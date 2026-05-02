"""
Excel → Nested JSON Transformer for PaddleOCR output.

Receives a pandas DataFrame from paddleocr_table2excel skill
(e.g. portfolio_008.xlsx with columns: 截止日期/产品名称/产品代码/Wind代码/资产名称/
持仓比例/数量/市值（本币）/最新净值/最新份额/最新规模),
converts it into the nested JSON structure expected by image_portfolio_normalizer.

Output structure:
{
    "daily_data": [
        {
            "date": "2026-04-23",
            "products": [
                {
                    "产品代码": "80PF11234",
                    "产品名称": "",
                    "最新净值": 1.1,
                    "最新份额": 209090909.1,
                    "最新规模": 230000000,
                    "positions": [
                        {
                            "Wind代码": "002415.SZ",
                            "资产名称": "海康威视",
                            "持仓比例": 0.1169,
                            "数量": 2415,
                            "市值（本币）": 2415,
                        },
                        ...
                    ]
                },
                ...
            ]
        },
        ...
    ]
}
"""
import sys
from pathlib import Path

# Inject venv packages so this module can run standalone
_venv = Path(__file__).parent.parent.parent / "common" / "paddleocr_table2excel" / ".venv" / "lib" / "python3.10" / "site-packages"
if str(_venv) not in sys.path:
    sys.path.insert(0, str(_venv))

import pandas as pd
from .base import BaseTransformer


class PaddleOCRExcelTransformer(BaseTransformer):
    """
    Converts Excel DataFrame from paddleocr_table2excel skill into nested JSON.

    Input DataFrame columns (from PaddleOCR):
        截止日期, 产品名称, 产品代码, Wind代码, 资产名称,
        持仓比例, 数量, 市值（本币）, 最新净值, 最新份额, 最新规模

    Output: nested JSON dict with 'daily_data' key
    """

    def __init__(self):
        self.source_type = "excel_from_paddleocr"

    def transform(self, records: list[dict]) -> list[dict]:
        """
        Args:
            records: List containing a single dict with keys:
                - 'df': pandas DataFrame from PaddleOCR Excel
                - 'source_path': original image path (optional, for logging)

        Returns:
            List containing a single dict with 'daily_data' key
        """
        if not records:
            return []

        record = records[0]
        df = record.get("df")
        if df is None:
            raise ValueError("No DataFrame found in records[0]['df']")

        if isinstance(df, str):
            # It's a file path — load it
            df = pd.read_excel(df)

        return self._convert(df)

    def _convert(self, df: pd.DataFrame) -> list[dict]:
        """
        Convert normalized Excel DataFrame into nested JSON structure.

        Strategy:
        - Group by (date, product_code) to build product-level records
        - Aggregate positions per product
        - Pull latest_nav/share/aum from the last position row per product
        """
        # Skip header rows (frozen pane leak: "持仓比例" appears as asset name)
        HEADER_KEYWORDS = {
            "持仓比例", "市值（本币）", "最新净值", "最新份额", "最新规模",
            "Wind代码", "资产名称", "产品代码", "产品名称", "截止日期", "数量",
        }
        REQUIRED_COLS = ["截止日期", "产品代码", "资产名称", "持仓比例"]
        for col in REQUIRED_COLS:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Drop rows where 资产名称 is a header keyword (frozen pane artifact)
        if "资产名称" in df.columns:
            df = df[df["资产名称"].apply(lambda v: str(v or "") not in HEADER_KEYWORDS)]

        # Clean up: drop rows where 产品代码 is null/empty
        df = df[df["产品代码"].notna() & (df["产品代码"].astype(str).str.strip() != "")]

        # Ensure numeric types
        for col in ["持仓比例", "数量", "市值（本币）", "最新净值", "最新份额", "最新规模"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        daily_data = []
        for date, date_group in df.groupby("截止日期", sort=False):
            products_map = {}

            for _, row in date_group.iterrows():
                code = str(row.get("产品代码", "")).strip()
                if not code:
                    continue

                if code not in products_map:
                    name = str(row.get("产品名称") or "").strip()
                    if name in ("", "nan", "None"):
                        name = ""
                    products_map[code] = {
                        "产品代码": code,
                        "产品名称": name,
                        "最新净值": self._to_float(row.get("最新净值")),
                        "最新份额": self._to_float(row.get("最新份额")),
                        "最新规模": self._to_int(row.get("最新规模")),
                        "positions": [],
                    }

                # Append position
                pos = {
                    "Wind代码": str(row.get("Wind代码") or "").strip(),
                    "资产名称": str(row.get("资产名称") or "").strip(),
                    "持仓比例": self._to_float(row.get("持仓比例")),
                    "数量": self._to_int(row.get("数量")),
                    "市值（本币）": self._to_int(row.get("市值（本币）")),
                }
                products_map[code]["positions"].append(pos)

            daily_data.append({
                "date": str(date)[:10] if date else "",
                "products": list(products_map.values()),
            })

        return [{"daily_data": daily_data}]

    @staticmethod
    def _to_float(v):
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_int(v):
        try:
            if v is None:
                return None
            return int(float(v))
        except (ValueError, TypeError):
            return None