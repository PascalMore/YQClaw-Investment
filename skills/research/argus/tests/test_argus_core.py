# skills/research/argus/tests/test_argus_core.py
"""Unit tests for Argus core modules."""

import sys
sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')

import unittest
from skills.research.argus.core import (
    CredibilityScorer,
    SignalGenerator,
    PoolManager,
    RebalancingDetector,
    DarwinDetector,
    ConsensusEngine,
)


class TestCredibilityScorer(unittest.TestCase):
    """Test credibility scoring."""
    
    def setUp(self):
        self.scorer = CredibilityScorer()
    
    def test_high_conviction(self):
        """Test high conviction positions."""
        position_changes = [
            {'asset_wind_code': '600519.SH', 'holding_ratio_change': 0.05},
            {'asset_wind_code': '000858.SZ', 'holding_ratio_change': 0.03},
        ]
        score = self.scorer.calculate_score('SM001', position_changes)
        self.assertGreater(score, 0.6)
    
    def test_no_data(self):
        """Test neutral score when no data."""
        score = self.scorer.calculate_score('SM001', [])
        self.assertEqual(score, 0.5)
    
    def test_confidence_levels(self):
        """Test confidence level labels."""
        self.assertEqual(self.scorer.get_confidence_level(0.9), 'HIGH')
        self.assertEqual(self.scorer.get_confidence_level(0.7), 'MEDIUM')
        self.assertEqual(self.scorer.get_confidence_level(0.5), 'LOW')
        self.assertEqual(self.scorer.get_confidence_level(0.2), 'NONE')


class TestPoolManager(unittest.TestCase):
    """Test pool management."""
    
    def setUp(self):
        self.manager = PoolManager()
    
    def test_conviction_zone(self):
        """Test conviction zone classification."""
        zone = self.manager.classify_stock(
            '600519.SH', '贵州茅台', 0.85, ['SM001', 'SM002', 'SM003'], False
        )
        self.assertEqual(zone, 'CONVICTION')
    
    def test_scan_zone(self):
        """Test scan zone classification."""
        zone = self.manager.classify_stock(
            '600519.SH', '贵州茅台', 0.2, ['SM001'], False
        )
        self.assertEqual(zone, 'SCAN')
    
    def test_pool_update(self):
        """Test pool update with signals."""
        current_pool = {zone: set() for zone in PoolManager.ZONES}
        # Use WATCH zone: single product, 0.55 confidence meets 0.45 threshold
        signals = [{
            'product_code': 'SM001',
            'confidence': 0.55,
            'target_stocks': [{'wind_code': '600519.SH', 'stock_name': '贵州茅台'}],
            'metadata': {'darwin_moment': False}
        }]
        updated = self.manager.update_pool(current_pool, signals)
        self.assertIn('600519.SH', updated['WATCH'])


class TestRebalancingDetector(unittest.TestCase):
    """Test rebalancing detection."""
    
    def setUp(self):
        self.detector = RebalancingDetector()
    
    def test_detect_rebalancing(self):
        """Test rebalancing event detection."""
        current = [
            {'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.10},
            {'asset_wind_code': '000858.SZ', 'asset_name': '五粮液', 'holding_ratio': 0.08},
        ]
        previous = [
            {'asset_wind_code': '600519.SH', 'asset_name': '贵州茅台', 'holding_ratio': 0.05},
            {'asset_wind_code': '000858.SZ', 'asset_name': '五粮液', 'holding_ratio': 0.08},
        ]
        events = self.detector.detect_rebalancing(current, previous)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['wind_code'], '600519.SH')
        self.assertEqual(events[0]['direction'], 'BUY')


class TestConsensusEngine(unittest.TestCase):
    """Test consensus calculation."""
    
    def setUp(self):
        self.engine = ConsensusEngine()
    
    def test_consensus_reached(self):
        """Test consensus calculation."""
        signals = [
            {'product_code': 'SM001', 'signal_type': 'BUY', 'confidence': 0.8,
             'target_stocks': [{'wind_code': '600519.SH'}]},
            {'product_code': 'SM002', 'signal_type': 'BUY', 'confidence': 0.75,
             'target_stocks': [{'wind_code': '600519.SH'}]},
            {'product_code': 'SM003', 'signal_type': 'BUY', 'confidence': 0.7,
             'target_stocks': [{'wind_code': '600519.SH'}]},
        ]
        consensus = self.engine.calculate_consensus(signals)
        self.assertIn('600519.SH', consensus)
        self.assertEqual(consensus['600519.SH']['direction'], 'BUY')
        self.assertEqual(consensus['600519.SH']['count'], 3)


if __name__ == '__main__':
    unittest.main()