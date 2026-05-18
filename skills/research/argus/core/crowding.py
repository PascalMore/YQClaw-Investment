# skills/research/argus/core/crowding.py
"""Four-layer crowding analysis for Argus C8."""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from ..config import ARGUS_CONFIG

logger = logging.getLogger(__name__)


class CrowdingAnalyzer:
    """Analyze stock crowding through macro, sector, micro, and event layers.

    L1 macro liquidity is an exogenous regime input and defaults to neutral
    when no macro data is available. L2-L4 are computed from Argus daily
    positions, trades, and generated signals so the daily pipeline remains
    deterministic and testable.
    """

    LAYERS = ['L1', 'L2', 'L3', 'L4']

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or ARGUS_CONFIG.get('crowding', {})
        thresholds = self.config.get('level_thresholds', {})
        self.low_threshold = thresholds.get('low', 0.35)
        self.high_threshold = thresholds.get('high', 0.70)
        self.weights = self.config.get(
            'layer_weights',
            {'L1': 0.20, 'L2': 0.25, 'L3': 0.35, 'L4': 0.20},
        )

    def analyze(
        self,
        positions: List[Dict],
        trades: Optional[List[Dict]] = None,
        signals: Optional[List[Dict]] = None,
        macro_data: Optional[Dict] = None,
    ) -> Dict[str, Dict]:
        """Return per-stock crowding diagnostics keyed by wind code."""
        trades = trades or []
        signals = signals or []
        macro_data = macro_data or {}

        stock_names = self._stock_names(positions, trades, signals)
        sector_scores = self._sector_scores(positions)
        micro_scores = self._micro_scores(positions, trades)
        event_scores = self._event_scores(signals)
        macro_score = self._macro_score(macro_data)

        diagnostics = {}
        for wind_code, stock_name in stock_names.items():
            layer_scores = {
                'L1': macro_score,
                'L2': sector_scores.get(wind_code, 0.5),
                'L3': micro_scores.get(wind_code, 0.0),
                'L4': event_scores.get(wind_code, 0.0),
            }
            score = sum(layer_scores[layer] * self.weights.get(layer, 0) for layer in self.LAYERS)
            score = round(max(0.0, min(1.0, score)), 4)
            diagnostics[wind_code] = {
                'wind_code': wind_code,
                'stock_name': stock_name,
                'crowding_score': score,
                'crowding_level': self.get_level(score),
                'layer_scores': layer_scores,
                'layer_details': {
                    'L1': 'macro liquidity proxy',
                    'L2': 'sector overlap/rotation proxy',
                    'L3': 'position concentration and turnover proxy',
                    'L4': 'event/consensus alignment proxy',
                },
            }

        logger.info("[CrowdingAnalyzer] calculated crowding for %s stocks", len(diagnostics))
        return diagnostics

    def get_level(self, score: float) -> str:
        """Map a 0-1 crowding score to LOW/MEDIUM/HIGH."""
        if score >= self.high_threshold:
            return 'HIGH'
        if score >= self.low_threshold:
            return 'MEDIUM'
        return 'LOW'

    def _macro_score(self, macro_data: Dict) -> float:
        if not macro_data:
            return self.config.get('default_macro_score', 0.5)

        liquidity = macro_data.get('liquidity_score')
        if liquidity is not None:
            return self._clamp(liquidity)

        rate_pressure = self._clamp(macro_data.get('rate_pressure', 0.5))
        credit_pressure = self._clamp(macro_data.get('credit_pressure', 0.5))
        return self._clamp((rate_pressure + credit_pressure) / 2)

    def _sector_scores(self, positions: List[Dict]) -> Dict[str, float]:
        sector_to_codes = defaultdict(set)
        for pos in positions:
            wind_code = pos.get('asset_wind_code')
            if not wind_code:
                continue
            sector = pos.get('industry') or pos.get('sector') or self._infer_market(wind_code)
            sector_to_codes[sector].add(wind_code)

        max_count = max((len(codes) for codes in sector_to_codes.values()), default=1)
        sector_crowding = {
            sector: len(codes) / max_count for sector, codes in sector_to_codes.items()
        }

        scores = {}
        for pos in positions:
            wind_code = pos.get('asset_wind_code')
            if not wind_code:
                continue
            sector = pos.get('industry') or pos.get('sector') or self._infer_market(wind_code)
            scores[wind_code] = round(sector_crowding.get(sector, 0.5), 4)
        return scores

    def _micro_scores(self, positions: List[Dict], trades: List[Dict]) -> Dict[str, float]:
        stock_product_pairs = defaultdict(set)
        stock_weight = defaultdict(float)
        stock_turnover = defaultdict(float)
        product_codes = {pos.get('product_code') for pos in positions if pos.get('product_code')}

        for pos in positions:
            wind_code = pos.get('asset_wind_code')
            product_code = pos.get('product_code')
            if not wind_code:
                continue
            if product_code:
                stock_product_pairs[wind_code].add(product_code)
            stock_weight[wind_code] += abs(float(pos.get('holding_ratio', 0) or 0))

        for trade in trades:
            wind_code = trade.get('asset_wind_code')
            if not wind_code:
                continue
            stock_turnover[wind_code] += abs(float(trade.get('amount', 0) or 0))

        max_weight = max(stock_weight.values(), default=1.0) or 1.0
        max_turnover = max(stock_turnover.values(), default=1.0) or 1.0
        product_count = max(len(product_codes), 1)

        scores = {}
        for wind_code in set(stock_weight) | set(stock_turnover):
            overlap = len(stock_product_pairs.get(wind_code, set())) / product_count
            concentration = stock_weight.get(wind_code, 0.0) / max_weight
            turnover = stock_turnover.get(wind_code, 0.0) / max_turnover
            scores[wind_code] = round(self._clamp(0.45 * overlap + 0.40 * concentration + 0.15 * turnover), 4)
        return scores

    def _event_scores(self, signals: List[Dict]) -> Dict[str, float]:
        direction_counts = defaultdict(lambda: defaultdict(int))
        confidence_sum = defaultdict(float)
        signal_count = defaultdict(int)

        for signal in signals:
            signal_type = signal.get('signal_type', 'HOLD')
            confidence = float(signal.get('confidence', 0) or 0)
            for target in signal.get('target_stocks', []):
                wind_code = target.get('wind_code')
                if not wind_code:
                    continue
                direction_counts[wind_code][signal_type] += 1
                confidence_sum[wind_code] += confidence
                signal_count[wind_code] += 1

        scores = {}
        for wind_code, counts in direction_counts.items():
            total = signal_count[wind_code]
            alignment = max(counts.values()) / total if total else 0.0
            avg_confidence = confidence_sum[wind_code] / total if total else 0.0
            scores[wind_code] = round(self._clamp(0.6 * alignment + 0.4 * avg_confidence), 4)
        return scores

    @staticmethod
    def _stock_names(positions: List[Dict], trades: List[Dict], signals: List[Dict]) -> Dict[str, str]:
        names = {}
        for record in positions + trades:
            wind_code = record.get('asset_wind_code')
            if wind_code:
                names[wind_code] = record.get('asset_name') or names.get(wind_code, '')
        for signal in signals:
            for target in signal.get('target_stocks', []):
                wind_code = target.get('wind_code')
                if wind_code:
                    names[wind_code] = target.get('stock_name') or names.get(wind_code, '')
        return names

    @staticmethod
    def _infer_market(wind_code: str) -> str:
        return wind_code.split('.')[-1] if '.' in wind_code else 'UNKNOWN'

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
