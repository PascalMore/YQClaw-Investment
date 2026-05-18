# skills/research/argus/core/credibility.py
"""Bayesian credibility scoring engine."""

import logging
from typing import List, Dict

from ..config import ARGUS_CONFIG

logger = logging.getLogger(__name__)


class CredibilityScorer:
    """Calculate Bayesian credibility score for fund products.
    
    Scoring factors:
    - Consistency of positioning over time
    - Conviction level (holding ratio changes)
    - Crowding risk
    - Data quality
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or ARGUS_CONFIG.get('credibility', {})
        self.high_threshold = self.config.get('high_threshold', 0.8)
        self.medium_threshold = self.config.get('medium_threshold', 0.6)
        self.low_threshold = self.config.get('low_threshold', 0.4)
    
    def calculate_score(
        self,
        product_code: str,
        position_changes: List[Dict],
        trade_history: List[Dict] = None
    ) -> float:
        """Calculate credibility score for a product.
        
        Args:
            product_code: Product code
            position_changes: List of position changes with holding_ratio_change
            trade_history: Optional trade history
        
        Returns:
            float: Credibility score between 0.0 and 1.0
        """
        if not position_changes:
            logger.warning(f"[CredibilityScorer] No position data for {product_code}")
            return 0.5  # Neutral score for no data
        
        # Factor 1: Consistency (based on variance of changes)
        consistency_score = self._calculate_consistency(position_changes)
        
        # Factor 2: Conviction (based on magnitude of changes)
        conviction_score = self._calculate_conviction(position_changes)
        
        # Factor 3: Crowding risk (if available)
        crowding_score = self._calculate_crowding_score(position_changes)
        
        # Combine scores (weighted average)
        final_score = (
            consistency_score * 0.3 +
            conviction_score * 0.4 +
            crowding_score * 0.3
        )
        
        # Clamp to 0-1
        final_score = max(0.0, min(1.0, final_score))
        
        logger.info(f"[CredibilityScorer] {product_code} score: {final_score:.3f}")
        return final_score
    
    def _calculate_consistency(self, position_changes: List[Dict]) -> float:
        """Calculate consistency score based on variance of changes."""
        if len(position_changes) < 2:
            return 0.5  # Neutral for single observation
        
        changes = [pc.get('holding_ratio_change', 0) for pc in position_changes]
        
        # Calculate variance of changes
        mean = sum(changes) / len(changes)
        variance = sum((c - mean) ** 2 for c in changes) / len(changes)
        
        # Lower variance = higher consistency
        # Normalize variance to score (assume max variance of 0.1 is worst case)
        consistency = max(0, 1 - (variance / 0.01))
        return consistency
    
    def _calculate_conviction(self, position_changes: List[Dict]) -> float:
        """Calculate conviction score based on magnitude of changes."""
        if not position_changes:
            return 0.5
        
        # Average absolute change
        avg_change = sum(
            abs(pc.get('holding_ratio_change', 0)) 
            for pc in position_changes
        ) / len(position_changes)
        
        # Normalize: 5% change = high conviction
        conviction = min(1.0, avg_change / 0.05)
        return conviction
    
    def _calculate_crowding_score(self, position_changes: List[Dict]) -> float:
        """Calculate crowding score based on number of overlapping positions."""
        # This is a simplified version - in production would use actual crowding data
        return 0.7  # Default moderate crowding score
    
    def get_confidence_level(self, score: float) -> str:
        """Get confidence level label from score.
        
        Args:
            score: Credibility score
        
        Returns:
            str: 'HIGH', 'MEDIUM', 'LOW', or 'NONE'
        """
        if score >= self.high_threshold:
            return 'HIGH'
        elif score >= self.medium_threshold:
            return 'MEDIUM'
        elif score >= self.low_threshold:
            return 'LOW'
        else:
            return 'NONE'