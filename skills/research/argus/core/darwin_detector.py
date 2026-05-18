# skills/research/argus/core/darwin_detector.py
"""Darwin moment detection - crowding at extremes."""

import logging
from typing import List, Dict

from ..config import ARGUS_CONFIG

logger = logging.getLogger(__name__)


class DarwinDetector:
    """Detect Darwin moments - when crowded positioning reaches extreme levels.
    
    Darwin moments occur when:
    - Many products have overlapping high-conviction positions
    - Momentum indicators show accelerated movement
    - Crowding risk reaches critical levels
    """
    
    def __init__(self):
        self.config = ARGUS_CONFIG.get('darwin', {})
        self.crowding_threshold = self.config.get('crowding_threshold', 0.6)
        self.momentum_threshold = self.config.get('momentum_threshold', 0.03)
    
    def detect_darwin_moment(
        self,
        positions: List[Dict],
        all_products_positions: List[List[Dict]]
    ) -> bool:
        """Detect if current positions represent a Darwin moment.
        
        Args:
            positions: Current product positions
            all_products_positions: Positions of all tracked products
        
        Returns:
            bool: True if Darwin moment detected
        """
        # Check crowding level
        crowding = self._calculate_crowding(positions, all_products_positions)
        
        if crowding < self.crowding_threshold:
            return False
        
        # Check momentum (simplified - would use actual price data)
        momentum = self._calculate_momentum(positions)
        
        if momentum < self.momentum_threshold:
            return False
        
        logger.warning(f"[DarwinDetector] Darwin moment detected! crowding={crowding:.2f}, momentum={momentum:.3f}")
        return True
    
    def _calculate_crowding(
        self,
        positions: List[Dict],
        all_products_positions: List[List[Dict]]
    ) -> float:
        """Calculate crowding level (0-1).
        
        Args:
            positions: Current product positions
            all_products_positions: All products' positions
        
        Returns:
            float: Crowding level 0-1
        """
        if not positions or not all_products_positions:
            return 0.0
        
        # Get wind codes in current positions
        current_codes = {p['asset_wind_code'] for p in positions}
        
        # Count how many products have overlapping positions
        overlapping_count = 0
        total_products = len(all_products_positions)
        
        for product_pos in all_products_positions:
            product_codes = {p['asset_wind_code'] for p in product_pos}
            if current_codes & product_codes:  # Intersection
                overlapping_count += 1
        
        crowding = overlapping_count / total_products if total_products > 0 else 0.0
        return crowding
    
    def _calculate_momentum(self, positions: List[Dict]) -> float:
        """Calculate momentum indicator.
        
        Simplified version - would use actual price returns.
        
        Args:
            positions: Current positions
        
        Returns:
            float: Momentum indicator
        """
        if not positions:
            return 0.0
        
        # Simplified: use average holding ratio change as momentum proxy
        # In production, would use actual price returns
        avg_change = sum(
            abs(p.get('holding_ratio_change', 0)) 
            for p in positions
        ) / len(positions)
        
        return avg_change