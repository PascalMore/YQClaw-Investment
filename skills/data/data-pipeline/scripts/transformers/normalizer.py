"""
NaNNormalizer — NaN/None 值规范化

将 dict 中的 NaN（含 pandas/numpy/内置 float NaN）统一转换为 None，
便于 MongoDB 存储和 JSON 序列化。
"""
import math
from typing import Any

from .base import BaseTransformer


class NaNNormalizer(BaseTransformer):
    """NaN 值规范化转换器"""

    def __init__(self, drop_null_keys: bool = False):
        """
        Args:
            drop_null_keys: 若为 True，则删除值为 None 的 key；
                            若为 False，保留 None 值（MongoDB 支持 None）。
        """
        self.drop_null_keys = drop_null_keys

    async def transform(self, records: list[dict]) -> list[dict]:
        return [self._normalize_record(r) for r in records]

    def _normalize_record(self, record: dict) -> dict:
        result = {}
        for key, value in record.items():
            normalized = self._normalize_value(value)
            if normalized is not None or not self.drop_null_keys:
                result[key] = normalized
        return result

    def _normalize_value(self, value: Any) -> Any:
        """将 NaN 系列值转换为 None"""
        if isinstance(value, float) and math.isnan(value):
            return None
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._normalize_value(item) for item in value]
        return value
