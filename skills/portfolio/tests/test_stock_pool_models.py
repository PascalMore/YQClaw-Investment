"""Unit tests for stock pool data models."""

import unittest
from datetime import datetime

from skills.portfolio.stock_pool.models import PoolZone, StockPoolEntry, StockPoolSource, validate_patch


class StockPoolModelTest(unittest.TestCase):
    """Validate model normalization and field checks."""

    def test_entry_to_dict_normalizes_enums(self) -> None:
        """StockPoolEntry should serialize enum values and audit metadata."""
        entry = StockPoolEntry(
            stock_code="600519",
            wind_code="600519.SH",
            stock_name="贵州茅台",
            pool_zone="SCAN",
            source="argus",
            entry_reason={"signal_type": "flow", "score": 0.81, "confidence": 0.7, "evidence": ["x"]},
            entry_date=datetime(2026, 5, 19),
            tags=["消费"],
            bayesian_score=0.81,
            crowding_level="MEDIUM",
            crowding_score=0.35,
            consensus_confidence=0.7,
            contributing_products=["SM001", "SM002"],
            contributing_products_count=2,
            darwin_moment=True,
        )

        data = entry.to_dict(actor="tester")

        self.assertEqual(data["pool_zone"], PoolZone.SCAN.value)
        self.assertEqual(data["source"], StockPoolSource.ARGUS.value)
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["audit"]["created_by"], "tester")
        self.assertEqual(data["bayesian_score"], 0.81)
        self.assertEqual(data["crowding_level"], "MEDIUM")
        self.assertEqual(data["crowding_score"], 0.35)
        self.assertEqual(data["consensus_confidence"], 0.7)
        self.assertEqual(data["contributing_products"], ["SM001", "SM002"])
        self.assertEqual(data["contributing_products_count"], 2)
        self.assertNotIn("weight_change_30d", data)
        self.assertTrue(data["darwin_moment"])
        self.assertNotIn("source_detail", data)
        self.assertNotIn("source_signal_id", data)

    def test_entry_reason_metrics_are_removed(self) -> None:
        """StockPoolEntry should not serialize deprecated entry_reason.metrics."""
        entry = StockPoolEntry(
            stock_code="600519",
            wind_code="600519.SH",
            stock_name="贵州茅台",
            pool_zone="SCAN",
            source="argus",
            entry_reason={
                "reason": "New entry: 600519.SH bayesian=0.81",
                "trigger": "new_entry",
                "from_zone": None,
                "to_zone": "SCAN",
                "metrics": {"bayesian_score": 0.81},
            },
        )

        data = entry.to_dict(actor="tester")

        self.assertEqual(
            data["entry_reason"],
            {
                "reason": "New entry: 600519.SH bayesian=0.81",
                "trigger": "new_entry",
                "from_zone": None,
                "to_zone": "SCAN",
            },
        )

    def test_entry_requires_non_empty_reason(self) -> None:
        """Empty entry_reason should be rejected."""
        with self.assertRaises(ValueError):
            StockPoolEntry(
                stock_code="600519",
                wind_code="600519.SH",
                stock_name="贵州茅台",
                pool_zone="SCAN",
                source="argus",
                entry_reason={},
            )

    def test_validate_patch_rejects_invalid_zone(self) -> None:
        """Patch validation should reject unsupported pool zones."""
        with self.assertRaises(ValueError):
            validate_patch({"pool_zone": "FOCUS"})

    def test_validate_patch_preserves_source_fields(self) -> None:
        """Patch validation should not drop source fields."""
        patch = validate_patch({"source_detail": "legacy", "source_signal_id": "sig-001", "memo": "ok"})

        self.assertEqual(
            patch,
            {"source_detail": "legacy", "source_signal_id": "sig-001", "memo": "ok"},
        )


if __name__ == "__main__":
    unittest.main()
