#!/usr/bin/env python3
"""Backfill Phase 4B (Darwin Events) and Phase 4C (Consensus Direction) for Argus.

Usage:
    python -m skills.research.argus.cli.backfill_phase4_bc [start_date] [end_date]
"""

import sys
sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')

from datetime import datetime, timedelta
from skills.data.data_interface import MongoReader, MongoWriter
from skills.research.argus.config import ARGUS_CONFIG
from skills.research.argus.core import DarwinDetector, ConsensusDirectionEngine
from skills.infra import format_date, get_latest_trading_day, get_logger

logger = get_logger('argus', 'research/argus/backfill_phase4_bc')


def get_trading_days(start_date: str, end_date: str) -> list:
    """Get list of trading days between start and end date."""
    from skills.infra import parse_date
    days = []
    current = parse_date(start_date)
    end = parse_date(end_date)
    while current <= end:
        trading_day = get_latest_trading_day(format_date(current))
        if trading_day >= start_date and trading_day not in days:
            days.append(trading_day)
        current += timedelta(days=1)
    return sorted(set(days))


def backfill_phase4_bc(start_date: str, end_date: str) -> dict:
    """Backfill Phase 4B and 4C for all trading days."""
    reader = MongoReader(database=ARGUS_CONFIG.get('mongo', {}).get('database', 'tradingagents'))
    writer = MongoWriter(database=ARGUS_CONFIG.get('mongo', {}).get('database', 'tradingagents'))
    writer.ensure_argus_indexes()
    
    darwin_detector = DarwinDetector()
    consensus_engine = ConsensusDirectionEngine()
    
    trading_days = get_trading_days(start_date, end_date)
    logger.info(f"[Backfill] Starting Phase 4B/4C backfill for {len(trading_days)} days: {start_date} ~ {end_date}")
    
    results = {
        'days_processed': 0,
        'darwin_events_total': 0,
        'consensus_direction_written': 0,
        'errors': [],
    }
    
    for date in trading_days:
        try:
            # Read required data
            from datetime import datetime, timedelta
            end_dt = datetime.strptime(date, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=35)
            start_date_35 = start_dt.strftime('%Y-%m-%d')
            
            # Read index quotes for Darwin detection (20d lookback from industry_weight data)
            index_quotes = reader.read_index_quotes('000300.SH', start_date_35, date)
            
            # Also need to read SW industry index quotes for Darwin detection
            sw_codes = [
                "801010.SI", "801030.SI", "801040.SI", "801050.SI", "801080.SI",
                "801110.SI", "801120.SI", "801130.SI", "801140.SI", "801150.SI",
                "801160.SI", "801170.SI", "801180.SI", "801200.SI", "801210.SI",
                "801230.SI", "801710.SI", "801720.SI", "801730.SI", "801740.SI",
                "801750.SI", "801760.SI", "801770.SI", "801780.SI", "801790.SI",
                "801880.SI", "801890.SI", "801950.SI", "801960.SI", "801970.SI",
                "801980.SI",
            ]
            for sw_code in sw_codes:
                sw_quotes = reader.read_index_quotes(sw_code, start_date_35, date)
                index_quotes.extend(sw_quotes)
            
            credential_scores = reader.read_credential_scores(date)
            industry_weights = reader.read_industry_weights(date)
            
            if not industry_weights:
                logger.warning(f"[Backfill] No industry weights for {date}, skipping")
                continue
            
            # Phase 4B: Darwin Detection
            darwin_events = darwin_detector.detect_for_date(
                date,
                index_quotes=index_quotes,
                credential_scores=credential_scores,
                industry_weights=industry_weights,
            )
            if darwin_events:
                writer.write_argus_darwin_events(darwin_events)
                results['darwin_events_total'] += len(darwin_events)
            
            # Phase 4C: Consensus Direction
            consensus_direction = consensus_engine.calculate_for_date(date, industry_weights)
            writer.write_argus_consensus_direction([consensus_direction])
            results['consensus_direction_written'] += 1
            
            results['days_processed'] += 1
            
            if results['days_processed'] % 10 == 0:
                logger.info(f"[Backfill] Progress: {results['days_processed']}/{len(trading_days)} days")
                
        except Exception as e:
            logger.error(f"[Backfill] Error processing {date}: {e}")
            results['errors'].append({'date': date, 'error': str(e)})
    
    logger.info(
        f"[Backfill] Complete: {results['days_processed']} days processed, "
        f"{results['darwin_events_total']} Darwin events, "
        f"{results['consensus_direction_written']} consensus direction records"
    )
    
    return results


def main():
    """CLI entry point."""
    start_date = sys.argv[1] if len(sys.argv) > 1 else '2025-12-31'
    end_date = sys.argv[2] if len(sys.argv) > 2 else '2026-05-20'
    
    logger.info(f"[Backfill Phase 4B/4C] Starting: {start_date} ~ {end_date}")
    
    try:
        results = backfill_phase4_bc(start_date, end_date)
        print("\n=== Phase 4B/4C Backfill Results ===")
        print(f"Days Processed: {results['days_processed']}")
        print(f"Darwin Events: {results['darwin_events_total']}")
        print(f"Consensus Directions: {results['consensus_direction_written']}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
            for e in results['errors'][:5]:
                print(f"  - {e['date']}: {e['error']}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()