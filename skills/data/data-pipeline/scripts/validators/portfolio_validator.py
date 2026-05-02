"""Portfolio data validators.

Validates data quality before database insertion.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Validation result container."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str):
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str):
        self.warnings.append(message)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def merge(self, other: "ValidationResult"):
        """Merge another ValidationResult into this one."""
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def validate_basic_info(records: list[dict]) -> ValidationResult:
    """Validate basic info records.

    Args:
        records: List of basic info records.

    Returns:
        ValidationResult with errors if any validation fails.
    """
    result = ValidationResult()
    for i, rec in enumerate(records):
        if not rec.get("product_code"):
            result.add_error(f"[{i}] product_code is empty")
        if not rec.get("product_name"):
            result.add_warning(f"[{i}] product_name is empty for {rec.get('product_code')}")
    return result


def validate_nav(records: list[dict]) -> ValidationResult:
    """Validate NAV records.

    Args:
        records: List of NAV records.

    Returns:
        ValidationResult with errors if any validation fails.
    """
    result = ValidationResult()
    for i, rec in enumerate(records):
        if not rec.get("nav_date"):
            result.add_error(f"[{i}] nav_date is empty")
        if not rec.get("product_code"):
            result.add_error(f"[{i}] product_code is empty")
        nav = rec.get("nav")
        if nav is not None and nav <= 0:
            result.add_error(f"[{i}] nav must be positive, got {nav}")
    return result


def validate_position(records: list[dict]) -> ValidationResult:
    """Validate position records.

    Args:
        records: List of position records.

    Returns:
        ValidationResult with errors if any validation fails.
    """
    result = ValidationResult()
    for i, rec in enumerate(records):
        if not rec.get("position_date"):
            result.add_error(f"[{i}] position_date is empty")
        if not rec.get("product_code"):
            result.add_error(f"[{i}] product_code is empty")
        if not rec.get("asset_wind_code"):
            result.add_error(f"[{i}] asset_wind_code is empty")
        ratio = rec.get("holding_ratio")
        if ratio is not None and not (0 <= ratio <= 1):
            result.add_warning(f"[{i}] holding_ratio {ratio} outside [0,1] range")
    return result


def validate_all(normalized: dict) -> ValidationResult:
    """Validate all normalized record types.

    Args:
        normalized: Dict with 'basic_info', 'nav', 'position' keys.

    Returns:
        Combined ValidationResult for all record types.
    """
    result = ValidationResult()
    result.merge(validate_basic_info(normalized.get("basic_info", [])))
    result.merge(validate_nav(normalized.get("nav", [])))
    result.merge(validate_position(normalized.get("position", [])))
    return result


if __name__ == "__main__":
    import json

    with open("examples/mock_3days_decoded.json") as f:
        decoded = json.load(f)

    from transformers.image_portfolio_normalizer import normalize_all

    normalized = normalize_all(decoded)
    result = validate_all(normalized)

    print("=== Validation Result ===")
    print(f"Valid: {result.valid}")
    print(f"Errors: {len(result.errors)}")
    for e in result.errors:
        print(f"  ERROR: {e}")
    print(f"Warnings: {len(result.warnings)}")
    for w in result.warnings:
        print(f"  WARNING: {w}")