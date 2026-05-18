# skills/research/argus/tests/test_argus_phase2_acceptance.py
"""Phase 2 acceptance tests for the Argus daily pipeline."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')

from skills.research.argus.cli.daily_processor import process_date


class FakeReader:
    def __init__(self, positions, trades):
        self.positions = positions
        self.trades = trades

    def read(self, date, **kwargs):
        collection_name = kwargs.get('collection_name')
        if collection_name == 'portfolio_position':
            return [p for p in self.positions if p['position_date'] == date]
        if collection_name == 'portfolio_trade':
            return [t for t in self.trades if t['trade_date'] == date]
        return []


class FakeWriter:
    def __init__(self):
        self.credential_scores = []
        self.signals = []
        self.stock_pool = []
        self.indexes_ensured = False

    def ensure_argus_indexes(self):
        self.indexes_ensured = True

    def write_argus_credential_scores(self, data):
        self.credential_scores.extend(data)
        return len(data)

    def write_argus_signals(self, data):
        self.signals.extend(data)
        return len(data)

    def write_argus_stock_pool(self, data):
        self.stock_pool.extend(data)
        return len(data)


class TestArgusPhase2Acceptance(unittest.TestCase):
    def test_phase2_end_to_end_pipeline_writes_three_raw_tables(self):
        positions = [
            {'position_date': '2026-03-10', 'product_code': 'SM001', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.02, 'market_value': 200000},
            {'position_date': '2026-03-10', 'product_code': 'SM002', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.03, 'market_value': 300000},
            {'position_date': '2026-03-11', 'product_code': 'SM001', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.08, 'market_value': 800000},
            {'position_date': '2026-03-11', 'product_code': 'SM002', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.07, 'market_value': 700000},
            {'position_date': '2026-03-11', 'product_code': 'SM003', 'asset_wind_code': '000858.SZ', 'asset_name': '五粮液', 'holding_ratio': 0.04, 'market_value': 400000},
        ]
        trades = [
            {'trade_date': '2026-03-11', 'product_code': 'SM001', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'direction': 'BUY', 'amount': 600000},
        ]
        writer = FakeWriter()

        with tempfile.TemporaryDirectory() as output_dir:
            results = process_date(
                '2026-03-11',
                reader=FakeReader(positions, trades),
                writer=writer,
                output_dir=Path(output_dir),
                write_mongo=True,
            )
            payload = json.loads(Path(results['output_file']).read_text(encoding='utf-8'))

        self.assertTrue(writer.indexes_ensured)
        self.assertEqual(results['products_processed'], 3)
        self.assertEqual(results['signals_generated'], 3)
        self.assertEqual(results['credential_scores_written'], 3)
        self.assertEqual(results['signals_written'], 3)
        self.assertEqual(results['stock_pool_written'], 2)
        self.assertTrue(all(record['date'] == '2026-03-11' for record in writer.credential_scores))
        self.assertTrue(all(record['date'] == '2026-03-11' for record in writer.signals))
        self.assertTrue(all(record['date'] == '2026-03-11' for record in writer.stock_pool))
        self.assertTrue(all('crowding_level' in signal['metadata'] for signal in writer.signals))
        self.assertEqual(payload['date'], '2026-03-11')
        self.assertIn('crowding', payload)
        self.assertIn('stock_pool', payload)

    def test_phase2_pipeline_handles_1000_products_in_memory(self):
        positions = [
            {
                'position_date': '2026-03-11',
                'product_code': f'SM{i:04d}',
                'asset_wind_code': f'{600000 + (i % 50):06d}.SH',
                'asset_name': f'Stock{i % 50}',
                'holding_ratio': 0.02 + (i % 5) * 0.005,
                'market_value': 100000 + i,
            }
            for i in range(1000)
        ]
        writer = FakeWriter()

        with tempfile.TemporaryDirectory() as output_dir:
            results = process_date(
                '2026-03-11',
                reader=FakeReader(positions, []),
                writer=writer,
                output_dir=Path(output_dir),
                write_mongo=True,
            )

        self.assertEqual(results['products_processed'], 1000)
        self.assertEqual(results['signals_generated'], 1000)
        self.assertEqual(results['credential_scores_written'], 1000)
        self.assertEqual(results['signals_written'], 1000)
        self.assertEqual(results['stock_pool_written'], 50)


if __name__ == '__main__':
    unittest.main()
