# skills/data/portfolio/transformer.py
"""Portfolio data transformer - converts raw data to processed format."""

import logging
from typing import List, Dict

from .config import PRODUCT_ALIAS

logger = logging.getLogger(__name__)


class PortfolioTransformer:
    """Transforms portfolio raw data to processed format."""
    
    @staticmethod
    def get_product_alias(product_code: str) -> str:
        """Get full company name from product code alias.
        
        Args:
            product_code: Product code (e.g., 'SM001', 'JS-001')
        
        Returns:
            str: Full company name (e.g., '景顺')
        """
        # Extract alias prefix (e.g., 'JS' from 'JS-001' or 'SM001')
        if '-' in product_code:
            alias = product_code.split('-')[0]
        else:
            # SM001 -> SM (first two chars for SM series)
            alias = product_code[:2] if product_code.startswith('SM') else product_code[:2]
        
        return PRODUCT_ALIAS.get(alias, alias)
    
    @staticmethod
    def transform_position(raw_positions: List[Dict]) -> List[Dict]:
        """Transform raw position data to processed format.
        
        Args:
            raw_positions: List of raw position records from MongoDB
        
        Returns:
            List[Dict]: Transformed position records
        """
        transformed = []
        for pos in raw_positions:
            # Add alias name
            alias = PortfolioTransformer.get_product_alias(pos.get('product_code', ''))
            transformed_pos = {
                **pos,
                'alias': alias,
                'holding_ratio_pct': round(pos.get('holding_ratio', 0) * 100, 4),
            }
            transformed.append(transformed_pos)
        
        logger.info(f"[PortfolioTransformer] transformed {len(transformed)} position records")
        return transformed
    
    @staticmethod
    def transform_trade(raw_trades: List[Dict]) -> List[Dict]:
        """Transform raw trade data to processed format.
        
        Args:
            raw_trades: List of raw trade records from MongoDB
        
        Returns:
            List[Dict]: Transformed trade records
        """
        transformed = []
        for trade in raw_trades:
            # Normalize direction
            direction = trade.get('direction', '')
            if '买' in direction:
                normalized_direction = 'BUY'
            elif '卖' in direction:
                normalized_direction = 'SELL'
            else:
                normalized_direction = 'HOLD'
            
            transformed_trade = {
                **trade,
                'direction_normalized': normalized_direction,
            }
            transformed.append(transformed_trade)
        
        logger.info(f"[PortfolioTransformer] transformed {len(transformed)} trade records")
        return transformed
    
    @staticmethod
    def calculate_holding_ratio_change(
        current_positions: List[Dict],
        previous_positions: List[Dict]
    ) -> List[Dict]:
        """Calculate holding ratio changes between two dates.
        
        Args:
            current_positions: Current period positions
            previous_positions: Previous period positions
        
        Returns:
            List[Dict]: Position changes with ratio_change field
        """
        # Build previous position lookup by wind_code
        prev_lookup = {
            pos['asset_wind_code']: pos.get('holding_ratio', 0)
            for pos in previous_positions
        }
        
        changes = []
        for curr_pos in current_positions:
            wind_code = curr_pos['asset_wind_code']
            prev_ratio = prev_lookup.get(wind_code, 0)
            curr_ratio = curr_pos.get('holding_ratio', 0)
            
            changes.append({
                **curr_pos,
                'holding_ratio_change': curr_ratio - prev_ratio,
                'previous_holding_ratio': prev_ratio,
            })
        
        return changes