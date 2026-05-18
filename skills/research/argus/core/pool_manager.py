# skills/research/argus/core/pool_manager.py
"""Four-zone stock pool management."""

import logging
from typing import List, Dict, Set

from ..config import ARGUS_CONFIG

logger = logging.getLogger(__name__)


class PoolManager:
    """Manage the four-zone stock pool: SCAN/WATCH/CANDIDATE/CONVICTION.
    
    Zone definitions:
    - CONVICTION: High confidence, multi-product consensus
    - CANDIDATE: Medium confidence, some consensus
    - WATCH: Low confidence, needs monitoring
    - SCAN: New signals, under evaluation
    """
    
    ZONES = ['SCAN', 'WATCH', 'CANDIDATE', 'CONVICTION']
    
    def __init__(self):
        self.config = ARGUS_CONFIG.get('pool_zones', {})
    
    def classify_stock(
        self,
        wind_code: str,
        stock_name: str,
        confidence: float,
        contributing_products: List[str],
        darwin_moment: bool = False
    ) -> str:
        """Classify a stock into a pool zone.
        
        Args:
            wind_code: Stock wind code
            stock_name: Stock name
            confidence: Signal confidence score
            contributing_products: List of product codes contributing to signal
            darwin_moment: Whether this is a Darwin moment
        
        Returns:
            str: Pool zone (SCAN/WATCH/CANDIDATE/CONVICTION)
        """
        # Darwin moment stocks go to CANDIDATE at minimum
        if darwin_moment:
            base_zone = 'CANDIDATE'
        else:
            base_zone = 'SCAN'
        
        # Apply thresholds
        conviction_config = self.config.get('conviction', {})
        candidate_config = self.config.get('candidate', {})
        watch_config = self.config.get('watch', {})
        scan_config = self.config.get('scan', {})
        
        # CONVICTION: High confidence + multiple products
        if (confidence >= conviction_config.get('min_confidence', 0.75) and
            len(contributing_products) >= conviction_config.get('min_contributing_products', 3)):
            return 'CONVICTION'
        
        # CANDIDATE: Medium confidence + some products
        if (confidence >= candidate_config.get('min_confidence', 0.60) and
            len(contributing_products) >= candidate_config.get('min_contributing_products', 2)):
            return 'CANDIDATE'
        
        # WATCH: Low confidence
        if confidence >= watch_config.get('min_confidence', 0.45):
            return 'WATCH'
        
        # SCAN: Everything else
        return 'SCAN'
    
    def update_pool(
        self,
        current_pool: Dict[str, Set[str]],
        new_signals: List[Dict]
    ) -> Dict[str, Set[str]]:
        """Update pool with new signals.
        
        Args:
            current_pool: Current pool state {zone: {wind_codes}}
            new_signals: List of new signals
        
        Returns:
            Dict[str, Set[str]]: Updated pool state
        """
        # Initialize if empty
        if not current_pool:
            current_pool = {zone: set() for zone in self.ZONES}
        
        for signal in new_signals:
            for target in signal.get('target_stocks', []):
                wind_code = target.get('wind_code')
                confidence = signal.get('confidence', 0)
                products = [signal.get('product_code')]
                darwin = signal.get('metadata', {}).get('darwin_moment', False)
                
                zone = self.classify_stock(
                    wind_code,
                    target.get('stock_name'),
                    confidence,
                    products,
                    darwin
                )
                
                # Add to new zone, remove from others
                for z in self.ZONES:
                    current_pool[z].discard(wind_code)
                current_pool[zone].add(wind_code)
        
        logger.info(f"[PoolManager] Pool updated: {', '.join(f'{z}={len(s)}' for z, s in current_pool.items())}")
        return current_pool
    
    def get_pool_summary(self, pool: Dict[str, Set[str]]) -> Dict[str, int]:
        """Get pool summary counts.
        
        Args:
            pool: Pool state
        
        Returns:
            Dict[str, int]: Zone counts
        """
        return {zone: len(stocks) for zone, stocks in pool.items()}