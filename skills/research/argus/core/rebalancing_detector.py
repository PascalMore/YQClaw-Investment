# skills/research/argus/core/rebalancing_detector.py
"""Rebalancing event detection."""

import logging
from typing import List, Dict

from ..config import ARGUS_CONFIG

logger = logging.getLogger(__name__)


class RebalancingDetector:
    """Detect portfolio rebalancing events based on holding ratio changes."""
    
    def __init__(self):
        self.config = ARGUS_CONFIG.get('rebalancing', {})
        self.change_threshold = self.config.get('holding_ratio_change_threshold', 0.05)
        self.lookback_days = self.config.get('lookback_days', 5)
    
    def detect_rebalancing(
        self,
        current_positions: List[Dict],
        previous_positions: List[Dict]
    ) -> List[Dict]:
        """Detect rebalancing events between two periods.
        
        Args:
            current_positions: Current period positions
            previous_positions: Previous period positions
        
        Returns:
            List[Dict]: List of detected rebalancing events
        """
        # Build lookup by wind_code
        prev_lookup = {
            pos.get('asset_wind_code') or pos.get('wind_code'): pos.get('holding_ratio', 0)
            for pos in previous_positions
        }
        
        events = []
        for curr_pos in current_positions:
            wind_code = curr_pos.get('asset_wind_code') or curr_pos.get('wind_code')
            curr_ratio = curr_pos.get('holding_ratio', 0)
            prev_ratio = prev_lookup.get(wind_code, 0)
            change = curr_ratio - prev_ratio
            
            # Check if change exceeds threshold
            if abs(change) >= self.change_threshold:
                events.append({
                    'wind_code': wind_code,
                    'asset_name': curr_pos.get('asset_name'),
                    'previous_ratio': prev_ratio,
                    'current_ratio': curr_ratio,
                    'change': change,
                    'direction': 'BUY' if change > 0 else 'SELL',
                    'is_rebalancing': True,
                })
        
        logger.info(f"[RebalancingDetector] Detected {len(events)} rebalancing events")
        return events
    
    def is_significant_rebalancing(self, events: List[Dict]) -> bool:
        """Check if events constitute significant rebalancing.
        
        Args:
            events: List of rebalancing events
        
        Returns:
            bool: True if significant rebalancing detected
        """
        # More than 20% of positions changed = significant
        if len(events) >= 3:
            return True
        return False