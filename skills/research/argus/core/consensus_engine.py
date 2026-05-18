# skills/research/argus/core/consensus_engine.py
"""Multi-product consensus engine."""

import logging
from typing import List, Dict

from .pool_manager import PoolManager

logger = logging.getLogger(__name__)


class ConsensusEngine:
    """Calculate consensus direction across multiple products.
    
    Consensus is reached when multiple products show the same
    directional bias on the same stock.
    """
    
    def __init__(self, pool_manager: PoolManager = None):
        self.pool_manager = pool_manager or PoolManager()
    
    def calculate_consensus(
        self,
        signals: List[Dict]
    ) -> Dict[str, Dict]:
        """Calculate consensus for target stocks across products.
        
        Args:
            signals: List of signals from multiple products
        
        Returns:
            Dict[str, Dict]: Consensus for each wind_code
                {wind_code: {direction: str, count: int, confidence: float}}
        """
        # Aggregate by wind_code
        wind_code_signals: Dict[str, List[Dict]] = {}
        
        for signal in signals:
            for target in signal.get('target_stocks', []):
                wind_code = target.get('wind_code')
                if wind_code not in wind_code_signals:
                    wind_code_signals[wind_code] = []
                wind_code_signals[wind_code].append(signal)
        
        # Calculate consensus
        consensus = {}
        for wind_code, sigs in wind_code_signals.items():
            direction_counts = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
            total_confidence = 0.0
            
            for sig in sigs:
                direction = sig.get('signal_type', 'HOLD')
                direction_counts[direction] = direction_counts.get(direction, 0) + 1
                total_confidence += sig.get('confidence', 0)
            
            # Determine consensus direction
            max_count = max(direction_counts.values())
            total_signals = len(sigs)
            
            if max_count / total_signals >= 0.6:  # 60% threshold
                consensus_direction = max(direction_counts, key=direction_counts.get)
            else:
                consensus_direction = 'NEUTRAL'
            
            consensus[wind_code] = {
                'direction': consensus_direction,
                'count': total_signals,
                'confidence': total_confidence / total_signals if sigs else 0,
                'direction_breakdown': direction_counts,
            }
        
        logger.info(f"[ConsensusEngine] Calculated consensus for {len(consensus)} stocks")
        return consensus
    
    def is_consensus_reached(
        self,
        wind_code: str,
        consensus_data: Dict[str, Dict],
        min_products: int = 3
    ) -> bool:
        """Check if consensus is reached for a stock.
        
        Args:
            wind_code: Stock wind code
            consensus_data: Consensus data from calculate_consensus
            min_products: Minimum products needed for consensus
        
        Returns:
            bool: True if consensus reached
        """
        if wind_code not in consensus_data:
            return False
        
        data = consensus_data[wind_code]
        return (
            data['direction'] != 'NEUTRAL' and
            data['count'] >= min_products
        )