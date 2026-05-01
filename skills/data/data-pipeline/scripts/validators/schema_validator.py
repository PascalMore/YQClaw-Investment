"""
SchemaValidator — 基于 Schema 的数据校验

从 YAML 定义加载数据结构，对每条记录进行：
- 必填字段检查
- 类型检查
- 数值范围检查
- 正则模式匹配
"""
import re
from typing import Any

from .base import BaseValidator, ValidationResult


class SchemaValidator(BaseValidator):
    """
    Schema 校验器

    Args:
        schema_dict: Schema 定义字典，格式如下:
        {
            "symbol": {"type": str, "required": True, "pattern": r"^\d{6}$"},
            "close":  {"type": float, "required": True, "min": 0, "max": 1e6},
            "note":   {"type": str, "required": False},
        }
    """

    def __init__(self, schema_dict: dict[str, dict] = None):
        self.schema = schema_dict or {}

    async def validate(self, records: list[dict]) -> ValidationResult:
        result = ValidationResult()

        for i, record in enumerate(records):
            errors = self._validate_record(record, index=i)
            for error in errors:
                result.add_error(f"[记录{i}] {error}")

        return result

    def _validate_record(self, record: dict, index: int = 0) -> list[str]:
        errors = []
        for field_name, rules in self.schema.items():
            value = record.get(field_name)

            # 必填检查
            if rules.get("required", False) and value is None:
                errors.append(f"字段 '{field_name}' 为必填但值是 None")
                continue

            if value is None:
                continue

            # 类型检查
            expected_type = rules.get("type")
            if expected_type and not isinstance(value, expected_type):
                errors.append(
                    f"字段 '{field_name}' 类型错误: 期望 {expected_type.__name__}, "
                    f"实际 {type(value).__name__}"
                )
                continue

            # 数值范围检查
            if expected_type in (int, float):
                min_val = rules.get("min")
                max_val = rules.get("max")
                if min_val is not None and value < min_val:
                    errors.append(f"字段 '{field_name}' 值 {value} 低于最小值 {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"字段 '{field_name}' 值 {value} 超过最大值 {max_val}")

            # 正则匹配
            pattern = rules.get("pattern")
            if pattern and isinstance(value, str):
                if not re.match(pattern, value):
                    errors.append(
                        f"字段 '{field_name}' 值 '{value}' 不匹配正则 {pattern}"
                    )

        return errors
