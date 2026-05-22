#!/usr/bin/env python3
"""Verify ARGUS collections status and data quality.

Usage:
    python -m skills.research.argus.cli.verify_collections
"""

import sys
sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')

from collections import Counter
from skills.data.data_interface import MongoReader
from skills.research.argus.config import ARGUS_CONFIG


COLLECTIONS = {
    'industry_weight': '08_research_argus_industry_weight',
    'credential_score': '08_research_argus_credential_score',
    'signal': '08_research_argus_signal',
    'signal_pool': '08_research_argus_signal_pool',
    'darwin_event': '08_research_argus_darwin_event',
    'consensus_direction': '08_research_argus_consensus_direction',
}

DATABASE = ARGUS_CONFIG.get('mongo', {}).get('database', 'tradingagents')


def check_collection(reader: MongoReader, name: str, coll: str) -> dict:
    docs = list(reader.db[coll].find({}, {'_id': 0}))
    count = len(docs)
    dates = sorted(set(d.get('date') for d in docs if d.get('date')))
    date_range = f"{dates[0]} ~ {dates[-1]}" if dates else "N/A"
    
    return {
        'name': name,
        'count': count,
        'date_count': len(dates),
        'date_range': date_range,
        'docs': docs,
    }


def check_signal_pool(docs: list) -> dict:
    total = len(docs)
    date_count = len(set(d.get('date') for d in docs if d.get('date')))
    
    with_prosperity = sum(1 for d in docs if d.get('prosperity_signal'))
    with_darwin_moment = sum(1 for d in docs if d.get('darwin_moment') == True)
    with_darwin_conf = sum(1 for d in docs if d.get('darwin_confidence') is not None)
    with_darwin_event_id = sum(1 for d in docs if d.get('darwin_event_id'))
    
    pool_zones = Counter(d.get('pool_zone') for d in docs if d.get('pool_zone'))
    
    return {
        'total': total,
        'date_count': date_count,
        'prosperity_coverage': f"{with_prosperity}/{total} ({100*with_prosperity/total:.1f}%)",
        'darwin_moment_true': f"{with_darwin_moment}/{total}",
        'darwin_confidence': f"{with_darwin_conf}/{total}",
        'darwin_event_id': f"{with_darwin_event_id}/{total}",
        'pool_zones': dict(pool_zones),
    }


def check_credential_score(docs: list) -> dict:
    by_product = {}
    for d in docs:
        pc = d.get('product_code')
        if pc not in by_product:
            by_product[pc] = []
        by_product[pc].append(d.get('credibility_score', 0))
    
    level_counts = Counter()
    product_stats = {}
    for pc, scores in sorted(by_product.items()):
        latest = scores[-1]
        if latest < 0.5:
            level = 'WEAK'
        elif latest > 0.7:
            level = 'STRONG'
        else:
            level = 'MEDIUM'
        level_counts[level] += 1
        product_stats[pc] = {
            'latest': round(latest, 4),
            'level': level,
            'range': [round(min(scores), 4), round(max(scores), 4)],
            'dates': len(scores),
        }
    
    return {
        'total_records': len(docs),
        'product_count': len(by_product),
        'level_distribution': dict(level_counts),
        'product_stats': product_stats,
    }


def check_darwin_events(docs: list) -> dict:
    if not docs:
        return {'total': 0, 'status': 'No events (expected - products in MEDIUM range)'}
    
    by_status = Counter(d.get('status') for d in docs)
    by_sector = Counter(d.get('sw1_code') for d in docs)
    return {
        'total': len(docs),
        'by_status': dict(by_status),
        'by_sector': dict(by_sector.most_common(5)),
    }


def check_consensus_direction(docs: list) -> dict:
    signals = Counter(d.get('prosperity_signal') for d in docs if d.get('prosperity_signal'))
    deltas = [d.get('prosperity_delta', 0) for d in docs if d.get('prosperity_delta') is not None]
    
    return {
        'total': len(docs),
        'signal_distribution': dict(signals),
        'delta_stats': {
            'min': round(min(deltas), 2) if deltas else None,
            'max': round(max(deltas), 2) if deltas else None,
            'avg': round(sum(deltas)/len(deltas), 2) if deltas else None,
        },
    }


def main():
    reader = MongoReader(database=DATABASE)
    
    print("=" * 60)
    print("ARGUS Collections Verification Report")
    print("=" * 60)
    
    # Check each collection
    results = {}
    for name, coll in COLLECTIONS.items():
        r = check_collection(reader, name, coll)
        results[name] = r
        print(f"\n### {name} ({coll})")
        print(f"  Records: {r['count']}")
        print(f"  Dates: {r['date_count']} ({r['date_range']})")
    
    # Deep checks for key collections
    print("\n" + "=" * 60)
    print("Signal Pool Field Coverage")
    print("=" * 60)
    sp = check_signal_pool(results['signal_pool']['docs'])
    print(f"  Total: {sp['total']} records across {sp['date_count']} dates")
    print(f"  prosperity_signal: {sp['prosperity_coverage']}")
    print(f"  darwin_moment=True: {sp['darwin_moment_true']}")
    print(f"  darwin_confidence!=None: {sp['darwin_confidence']}")
    print(f"  darwin_event_id: {sp['darwin_event_id']}")
    print(f"  Pool zones: {sp['pool_zones']}")
    
    print("\n" + "=" * 60)
    print("Product Credibility Distribution")
    print("=" * 60)
    cs = check_credential_score(results['credential_score']['docs'])
    print(f"  Records: {cs['total_records']} across {cs['product_count']} products")
    print(f"  Level distribution: {cs['level_distribution']}")
    print(f"  Product details:")
    for pc, stats in cs['product_stats'].items():
        print(f"    {pc}: {stats['latest']} ({stats['level']}) range={stats['range']}")
    
    print("\n" + "=" * 60)
    print("Darwin Events")
    print("=" * 60)
    de = check_darwin_events(results['darwin_event']['docs'])
    for k, v in de.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 60)
    print("Consensus Direction")
    print("=" * 60)
    cd = check_consensus_direction(results['consensus_direction']['docs'])
    print(f"  Total: {cd['total']} records")
    print(f"  Signal distribution: {cd['signal_distribution']}")
    print(f"  Delta stats: {cd['delta_stats']}")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  All collections have data: {'YES' if all(r['count'] > 0 for r in results.values()) else 'NO'}")
    print(f"  signal_pool prosperity 100%: {'YES' if sp['prosperity_coverage'].endswith('100.0%)') else 'NO'}")
    print(f"  Darwin events detected: {de['total']}")
    print(f"  Consensus signals: {cd['signal_distribution']}")


if __name__ == '__main__':
    main()