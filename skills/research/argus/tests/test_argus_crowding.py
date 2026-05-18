# skills/research/argus/tests/test_argus_crowding.py
"""Unit tests for Argus C8 crowding analyzer."""

import sys
import unittest

sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')

from skills.research.argus.core import CrowdingAnalyzer


class TestCrowdingAnalyzer(unittest.TestCase):
    def test_crowding_four_layers_present(self):
        analyzer = CrowdingAnalyzer()
        positions = [
            {'product_code': 'SM001', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.12, 'industry': '食品饮料'},
            {'product_code': 'SM002', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.10, 'industry': '食品饮料'},
            {'product_code': 'SM003', 'asset_wind_code': '000858.SZ', 'asset_name': '五粮液', 'holding_ratio': 0.05, 'industry': '食品饮料'},
        ]
        trades = [
            {'product_code': 'SM001', 'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'amount': 1000000},
        ]
        signals = [
            {'product_code': 'SM001', 'signal_type': 'BUY', 'confidence': 0.8, 'target_stocks': [{'wind_code': '600519.SH', 'stock_name': '贵州茅台'}]},
            {'product_code': 'SM002', 'signal_type': 'BUY', 'confidence': 0.7, 'target_stocks': [{'wind_code': '600519.SH', 'stock_name': '贵州茅台'}]},
        ]

        crowding = analyzer.analyze(positions, trades, signals, macro_data={'liquidity_score': 0.6})

        self.assertIn('600519.SH', crowding)
        self.assertEqual(set(crowding['600519.SH']['layer_scores']), {'L1', 'L2', 'L3', 'L4'})
        self.assertIn(crowding['600519.SH']['crowding_level'], {'LOW', 'MEDIUM', 'HIGH'})
        self.assertGreater(crowding['600519.SH']['crowding_score'], crowding['000858.SZ']['crowding_score'])

    def test_crowding_defaults_to_neutral_macro_and_low_without_activity(self):
        analyzer = CrowdingAnalyzer()
        crowding = analyzer.analyze([
            {'product_code': 'SM001', 'asset_wind_code': '300750.SZ', 'asset_name': '宁德时代', 'holding_ratio': 0.01}
        ])

        stock = crowding['300750.SZ']
        self.assertEqual(stock['layer_scores']['L1'], 0.5)
        self.assertGreaterEqual(stock['crowding_score'], 0)
        self.assertLessEqual(stock['crowding_score'], 1)
        self.assertEqual(analyzer.get_level(0.2), 'LOW')
        self.assertEqual(analyzer.get_level(0.5), 'MEDIUM')
        self.assertEqual(analyzer.get_level(0.8), 'HIGH')


if __name__ == '__main__':
    unittest.main()
