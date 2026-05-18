#!/usr/bin/env python3
# skills/research/argus/cli/daily_processor.py
"""Daily Argus end-to-end processing CLI.

Usage:
    python -m skills.research.argus.cli.daily_processor 2026-03-11
    python -m skills.research.argus.cli.daily_processor
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add workspace to path for direct script execution.
sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')

from skills.data.data_interface import MongoReader, MongoWriter
from skills.data.portfolio import PortfolioTransformer
from skills.infra import format_date, get_latest_trading_day, get_logger, parse_date
from skills.research.argus.config import ARGUS_CONFIG
from skills.research.argus.core import (
    ConsensusEngine,
    CredibilityScorer,
    CrowdingAnalyzer,
    DarwinDetector,
    PoolManager,
    RebalancingDetector,
    SignalGenerator,
)

logger = get_logger('argus', 'research/argus')


def process_date(
    target_date: str,
    reader: Optional[MongoReader] = None,
    writer: Optional[MongoWriter] = None,
    output_dir: Optional[Path] = None,
    write_mongo: bool = True,
) -> dict:
    """Process Argus for a single date from Mongo input to Mongo/JSON output."""
    logger.info("[Argus] Starting daily processing for %s", target_date)

    date_to_process = get_latest_trading_day(target_date)
    previous_date = _previous_trading_day(date_to_process)
    reader = reader or MongoReader(database=ARGUS_CONFIG.get('mongo', {}).get('database', 'tradingagents'))

    transformer = PortfolioTransformer()
    credibility_scorer = CredibilityScorer()
    signal_generator = SignalGenerator(credibility_scorer)
    pool_manager = PoolManager()
    rebalancing_detector = RebalancingDetector()
    darwin_detector = DarwinDetector()
    consensus_engine = ConsensusEngine(pool_manager)
    crowding_analyzer = CrowdingAnalyzer()

    results = {
        'date': date_to_process,
        'previous_date': previous_date,
        'products_processed': 0,
        'signals_generated': 0,
        'credential_scores_written': 0,
        'signals_written': 0,
        'stock_pool_written': 0,
        'pool_summary': {},
        'output_file': None,
    }

    positions = reader.read(date_to_process, collection_name='portfolio_position')
    if not positions:
        logger.warning("[Argus] No position data for %s", date_to_process)
        return results

    trades = reader.read(date_to_process, collection_name='portfolio_trade')
    previous_positions = reader.read(previous_date, collection_name='portfolio_position')

    product_codes = sorted({p['product_code'] for p in positions if p.get('product_code')})
    positions_by_product = _group_by_product(positions)
    previous_by_product = _group_by_product(previous_positions)
    all_product_positions = [positions_by_product[code] for code in product_codes]

    all_signals: List[Dict] = []
    credential_records: List[Dict] = []

    for product_code in product_codes:
        current_pos = positions_by_product[product_code]
        previous_pos = previous_by_product.get(product_code, [])
        product_name = transformer.get_product_alias(product_code)
        position_changes = transformer.calculate_holding_ratio_change(current_pos, previous_pos)
        rebalancing_events = rebalancing_detector.detect_rebalancing(position_changes, previous_pos)
        darwin_moment = darwin_detector.detect_darwin_moment(position_changes, all_product_positions)
        credibility_score = credibility_scorer.calculate_score(product_code, position_changes)

        credential_records.append(_credential_record(date_to_process, product_code, product_name, credibility_score, position_changes))

        signals = signal_generator.generate_signals(
            product_code=product_code,
            product_name=product_name,
            position_changes=position_changes,
            pool_zone='SCAN',
            darwin_moment=darwin_moment,
            consensus_direction='NEUTRAL',
        )
        for signal in signals:
            signal['date'] = date_to_process
            signal['metadata']['rebalancing_events_count'] = len(rebalancing_events)
        all_signals.extend(signals)

    consensus = consensus_engine.calculate_consensus(all_signals)
    crowding = crowding_analyzer.analyze(positions, trades, all_signals)
    stock_pool_records = _build_stock_pool_records(
        date_to_process,
        all_signals,
        consensus,
        crowding,
        pool_manager,
    )
    _annotate_signals(all_signals, stock_pool_records, consensus, crowding)

    current_pool = {zone: set() for zone in PoolManager.ZONES}
    for record in stock_pool_records:
        current_pool[record['pool_zone']].add(record['wind_code'])

    results.update({
        'products_processed': len(product_codes),
        'signals_generated': len(all_signals),
        'pool_summary': pool_manager.get_pool_summary(current_pool),
    })

    if write_mongo:
        writer = writer or MongoWriter(database=ARGUS_CONFIG.get('mongo', {}).get('database', 'tradingagents'))
        writer.ensure_argus_indexes()
        results['credential_scores_written'] = writer.write_argus_credential_scores(credential_records)
        results['signals_written'] = writer.write_argus_signals(all_signals)
        results['stock_pool_written'] = writer.write_argus_stock_pool(stock_pool_records)

    output_file = _write_json_output(
        date_to_process,
        all_signals,
        consensus,
        crowding,
        stock_pool_records,
        results,
        output_dir,
    )
    results['output_file'] = str(output_file)

    logger.info("[Argus] Processing complete: %s signals generated", len(all_signals))
    return results


def _previous_trading_day(date_to_process: str) -> str:
    previous_calendar_day = parse_date(date_to_process) - timedelta(days=1)
    return get_latest_trading_day(format_date(previous_calendar_day))


def _group_by_product(records: List[Dict]) -> Dict[str, List[Dict]]:
    grouped = defaultdict(list)
    for record in records:
        product_code = record.get('product_code')
        if product_code:
            grouped[product_code].append(record)
    return grouped


def _credential_record(
    date_to_process: str,
    product_code: str,
    product_name: str,
    credibility_score: float,
    position_changes: List[Dict],
) -> Dict:
    return {
        'date': date_to_process,
        'product_code': product_code,
        'product_name': product_name,
        'credibility_score': round(credibility_score, 4),
        'confidence_level': CredibilityScorer().get_confidence_level(credibility_score),
        'positions_count': len(position_changes),
        'avg_abs_holding_ratio_change': round(
            sum(abs(p.get('holding_ratio_change', 0) or 0) for p in position_changes) / len(position_changes),
            6,
        ) if position_changes else 0.0,
    }


def _build_stock_pool_records(
    date_to_process: str,
    signals: List[Dict],
    consensus: Dict[str, Dict],
    crowding: Dict[str, Dict],
    pool_manager: PoolManager,
) -> List[Dict]:
    stock_signals = defaultdict(list)
    stock_names = {}
    for signal in signals:
        for target in signal.get('target_stocks', []):
            wind_code = target.get('wind_code')
            if not wind_code:
                continue
            stock_signals[wind_code].append(signal)
            stock_names[wind_code] = target.get('stock_name') or stock_names.get(wind_code, '')

    records = []
    for wind_code, related_signals in stock_signals.items():
        products = sorted({signal.get('product_code') for signal in related_signals if signal.get('product_code')})
        confidence = max(signal.get('confidence', 0) for signal in related_signals)
        darwin_moment = any(signal.get('metadata', {}).get('darwin_moment') for signal in related_signals)
        pool_zone = pool_manager.classify_stock(
            wind_code,
            stock_names.get(wind_code, ''),
            confidence,
            products,
            darwin_moment,
        )
        crowding_data = crowding.get(wind_code, {})
        consensus_data = consensus.get(wind_code, {})
        records.append({
            'date': date_to_process,
            'wind_code': wind_code,
            'stock_name': stock_names.get(wind_code, ''),
            'pool_zone': pool_zone,
            'confidence': round(confidence, 4),
            'contributing_products': products,
            'contributing_products_count': len(products),
            'consensus_direction': consensus_data.get('direction', 'NEUTRAL'),
            'consensus_confidence': round(consensus_data.get('confidence', 0), 4),
            'crowding_score': crowding_data.get('crowding_score', 0),
            'crowding_level': crowding_data.get('crowding_level', 'LOW'),
            'crowding_layers': crowding_data.get('layer_scores', {}),
            'darwin_moment': darwin_moment,
        })
    return records


def _annotate_signals(
    signals: List[Dict],
    stock_pool_records: List[Dict],
    consensus: Dict[str, Dict],
    crowding: Dict[str, Dict],
) -> None:
    pool_by_stock = {record['wind_code']: record for record in stock_pool_records}
    for signal in signals:
        target = (signal.get('target_stocks') or [{}])[0]
        wind_code = target.get('wind_code')
        if not wind_code:
            continue
        pool_record = pool_by_stock.get(wind_code, {})
        crowding_data = crowding.get(wind_code, {})
        signal['metadata'].update({
            'crowding_level': crowding_data.get('crowding_level', 'LOW'),
            'crowding_score': crowding_data.get('crowding_score', 0),
            'crowding_layers': crowding_data.get('layer_scores', {}),
            'pool_zone': pool_record.get('pool_zone', signal['metadata'].get('pool_zone', 'SCAN')),
            'contributing_products_count': pool_record.get('contributing_products_count', 1),
            'consensus_direction': _signal_consensus_label(consensus.get(wind_code, {}).get('direction', 'NEUTRAL')),
        })


def _signal_consensus_label(direction: str) -> str:
    return {'BUY': 'BULLISH', 'SELL': 'BEARISH', 'HOLD': 'NEUTRAL'}.get(direction, direction)


def _write_json_output(
    date_to_process: str,
    signals: List[Dict],
    consensus: Dict[str, Dict],
    crowding: Dict[str, Dict],
    stock_pool_records: List[Dict],
    results: Dict,
    output_dir: Optional[Path],
) -> Path:
    output_dir = output_dir or Path('/home/pascal/.openclaw/workspace-yquant/logs/research/argus')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f'argus_signal_{date_to_process.replace("-", "")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'date': date_to_process,
            'signals': signals,
            'consensus': consensus,
            'crowding': crowding,
            'stock_pool': stock_pool_records,
            'pool_summary': results['pool_summary'],
        }, f, ensure_ascii=False, indent=2)
    return output_file


def main():
    """CLI entry point."""
    target_date = sys.argv[1] if len(sys.argv) > 1 else format_date(datetime.now().date())
    logger.info("[Argus CLI] Processing date: %s", target_date)

    try:
        results = process_date(target_date)
        print("\n=== Argus Processing Results ===")
        print(f"Date: {results['date']}")
        print(f"Products: {results['products_processed']}")
        print(f"Signals: {results['signals_generated']}")
        print(f"Credential Scores Written: {results['credential_scores_written']}")
        print(f"Signals Written: {results['signals_written']}")
        print(f"Stock Pool Written: {results['stock_pool_written']}")
        print(f"Pool: {results['pool_summary']}")
        print(f"Output: {results['output_file']}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
