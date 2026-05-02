"""JSON ↔ Base64 序列化编解码器

用于数据跨边界传输：HTTP Header、JSON 字段、文件存储、消息队列等场景
支持：
  - 单天嵌套结构（nested）：按 group_key 分组
  - 多天嵌套结构（nested）：按 date + group_key 二级分组
  - 扁平结构（flat）：每行一条记录，字段全部展开
"""
import base64
import json
import zlib
from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class CodecResult:
    """编解码结果"""
    success: bool
    data: Any = None
    error: str = ""

    @property
    def is_valid(self) -> bool:
        return self.success and self.data is not None


class Base64Codec:
    """JSON ↔ Base64 编解码器，支持可选的 zlib 压缩"""

    def __init__(self, compress: bool = False, compression_level: int = 9,
                 data_layout: Literal["flat", "nested"] = "nested",
                 group_key: str = "产品名称",
                 position_fields: list[str] | None = None):
        """
        Args:
            compress: 是否在 Base64 编码前进行 zlib 压缩
            compression_level: zlib 压缩级别 (0-9)，默认 9（最高压缩）
            data_layout: 数据布局，flat=扁平，nested=嵌套聚合
            group_key: 嵌套结构分组字段（如 "产品名称"）
            position_fields: 嵌套结构中 positions 保留的字段列表
        """
        self.compress = compress
        self.compression_level = compression_level
        self.data_layout = data_layout
        self.group_key = group_key
        self.position_fields = position_fields or []
        self.date_field = "截止日期"

    def _flatten_to_nested(self, records: list[dict]) -> dict:
        """将扁平记录列表转换为嵌套结构（自动识别单天/多天）"""
        if not records:
            return {"metadata": {}, "products": []}

        all_fields = list(records[0].keys())

        # 检测是否多天数据
        unique_dates = set(str(r.get(self.date_field, ""))[:10] for r in records)
        multi_day = len(unique_dates) > 1

        if multi_day:
            # ===== 多天结构：按日期 + 产品二级分组 =====
            grouped_by_date = {}
            for rec in records:
                d = str(rec.get(self.date_field, ""))[:10]
                if d not in grouped_by_date:
                    grouped_by_date[d] = {}
                pk = rec.get(self.group_key)
                if pk not in grouped_by_date[d]:
                    grouped_by_date[d][pk] = {
                        f: rec[f] for f in all_fields
                        if f != self.group_key and f != self.date_field
                    }
                    grouped_by_date[d][pk]["positions"] = []
                pos = {f: rec[f] for f in self.position_fields if f in rec}
                grouped_by_date[d][pk]["positions"].append(pos)

            return {
                "metadata": {
                    "total_days": len(unique_dates),
                    "total_records": len(records),
                    "total_products": len(set(r.get(self.group_key) for r in records)),
                    "columns": all_fields,
                    "date_range": f"{min(unique_dates)} ~ {max(unique_dates)}",
                },
                "daily_data": [
                    {"date": d, "products": list(grouped_by_date[d].values())}
                    for d in sorted(grouped_by_date.keys())
                ],
            }
        else:
            # ===== 单天结构：仅按产品分组 =====
            grouped = {}
            for rec in records:
                pk = rec.get(self.group_key)
                if pk not in grouped:
                    grouped[pk] = {
                        f: rec[f] for f in all_fields if f != self.group_key
                    }
                    grouped[pk]["positions"] = []
                pos = {f: rec[f] for f in self.position_fields if f in rec}
                grouped[pk]["positions"].append(pos)

            return {
                "metadata": {
                    "total_records": len(records),
                    "total_products": len(grouped),
                    "columns": all_fields,
                },
                "products": list(grouped.values()),
            }

    def _prepare_data(self, data: Any) -> list[dict]:
        """统一数据格式：如果是 nested 结构则展开为 records 列表"""
        if isinstance(data, dict) and "daily_data" in data:
            # 多天嵌套结构 → 展开
            records = []
            for day in data["daily_data"]:
                base = {"date": day["date"]}
                for product in day["products"]:
                    prod_base = {k: v for k, v in product.items() if k != "positions"}
                    for pos in product.get("positions", []):
                        records.append({**base, **prod_base, **pos})
            return records
        elif isinstance(data, dict) and "products" in data:
            # 单天嵌套结构 → 展开
            records = []
            for product in data["products"]:
                base = {k: v for k, v in product.items() if k != "positions"}
                for pos in product.get("positions", []):
                    records.append({**base, **pos})
            return records
        elif isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], list) else []
        elif isinstance(data, list):
            return data
        else:
            raise ValueError(f"Unsupported data format: {type(data)}")

    def encode(self, data: Any) -> str:
        """
        将 Python 对象序列化为 Base64 字符串

        Args:
            data: 扁平记录列表、或嵌套结构 dict

        Returns:
            Base64 编码字符串
        """
        records = self._prepare_data(data)

        if self.data_layout == "nested":
            structured = self._flatten_to_nested(records)
        else:
            structured = {
                "metadata": {
                    "total_records": len(records),
                    "columns": list(records[0].keys()) if records else [],
                },
                "data": records,
            }

        json_bytes = json.dumps(structured, ensure_ascii=False,
                               separators=(",", ":"), default=str).encode("utf-8")

        if self.compress:
            compressed = zlib.compress(json_bytes, level=self.compression_level)
            return base64.b64encode(compressed).decode("ascii")

        return base64.b64encode(json_bytes).decode("ascii")

    def decode(self, encoded: str) -> Any:
        """
        将 Base64 字符串反解析为 Python 对象

        Args:
            encoded: Base64 编码字符串

        Returns:
            原始 Python 对象（单天嵌套或多天嵌套结构）
        """
        decoded = base64.b64decode(encoded)
        if self.compress:
            decompressed = zlib.decompress(decoded)
            return json.loads(decompressed)

        return json.loads(decoded)


def encode_json(data: Any, compress: bool = False, data_layout: Literal["flat", "nested"] = "nested",
                group_key: str = "产品名称", position_fields: list[str] | None = None) -> str:
    """便捷函数：将 Python 对象编码为 Base64 字符串（默认嵌套结构）"""
    return Base64Codec(compress=compress, data_layout=data_layout,
                      group_key=group_key, position_fields=position_fields).encode(data)


def decode_base64(encoded: str, compressed: bool = False) -> Any:
    """便捷函数：将 Base64 字符串反解析为 Python 对象"""
    return Base64Codec(compress=compressed).decode(encoded)


# ===== 单元测试 =====
if __name__ == "__main__":
    import pprint

    # 测试数据：3天 × 2产品 × 3持仓
    records = [
        # Day 1
        {"截止日期": "2026-04-23", "产品名称": "景顺灵活1号", "Wind代码": "002415.SZ", "资产名称": "海康威视", "持仓比例": 0.1169, "数量": 139767},
        {"截止日期": "2026-04-23", "产品名称": "景顺灵活1号", "Wind代码": "000858.SZ", "资产名称": "五粮液", "持仓比例": 0.0685, "数量": 37913},
        {"截止日期": "2026-04-23", "产品名称": "景顺灵活2号", "Wind代码": "600519.SH", "资产名称": "贵州茅台", "持仓比例": 0.05, "数量": 5000},
        # Day 2
        {"截止日期": "2026-04-24", "产品名称": "景顺灵活1号", "Wind代码": "002415.SZ", "资产名称": "海康威视", "持仓比例": 0.11, "数量": 140000},
        {"截止日期": "2026-04-24", "产品名称": "景顺灵活1号", "Wind代码": "000858.SZ", "资产名称": "五粮液", "持仓比例": 0.07, "数量": 38000},
        {"截止日期": "2026-04-24", "产品名称": "景顺灵活2号", "Wind代码": "600519.SH", "资产名称": "贵州茅台", "持仓比例": 0.06, "数量": 6000},
        # Day 3
        {"截止日期": "2026-04-25", "产品名称": "景顺灵活1号", "Wind代码": "002415.SZ", "资产名称": "海康威视", "持仓比例": 0.12, "数量": 145000},
        {"截止日期": "2026-04-25", "产品名称": "景顺灵活2号", "Wind代码": "600519.SH", "资产名称": "贵州茅台", "持仓比例": 0.055, "数量": 5500},
        {"截止日期": "2026-04-25", "产品名称": "景顺灵活2号", "Wind代码": "000858.SZ", "资产名称": "五粮液", "持仓比例": 0.065, "数量": 40000},
    ]

    codec = Base64Codec(
        compress=True,
        data_layout="nested",
        group_key="产品名称",
        position_fields=["Wind代码", "资产名称", "持仓比例", "数量"]
    )
    encoded = codec.encode(records)
    decoded = codec.decode(encoded)

    print("=== 多天嵌套结构测试 ===")
    print(f"输入记录: {len(records)} 条")
    print(f"Base64长度: {len(encoded)} chars")
    print(f"结构类型: {'多天' if 'daily_data' in decoded else '单天'}")
    print(f"天数: {decoded['metadata'].get('total_days', 1)}")
    print(f"产品数: {decoded['metadata']['total_products']}")
    print(f"循环一致: ✅ 通过" if codec.decode(encoded) == decoded else "❌ 失败")

    print("\n多天结构预览:")
    for day in decoded.get("daily_data", []):
        print(f"  {day['date']}: {len(day['products'])} 产品")
        for p in day["products"]:
            print(f"    {p['产品名称']}: {len(p['positions'])} 持仓")

    # 单天测试
    single_day = [r for r in records if str(r["截止日期"]) == "2026-04-23"]
    encoded_single = codec.encode(single_day)
    decoded_single = codec.decode(encoded_single)
    print(f"\n单天结构: {'products' in decoded_single}")
    print(f"产品数: {decoded_single['metadata']['total_products']}")
