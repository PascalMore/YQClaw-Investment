# skills/research/argus/config/config.py
"""Argus configuration loader."""

import yaml
from pathlib import Path

# Load argus_config.yaml
CONFIG_PATH = Path(__file__).parent / 'argus_config.yaml'

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    ARGUS_CONFIG = yaml.safe_load(f)


# Product alias mapping
PRODUCT_ALIAS = {
    'JS': '景顺',
    'ZO': '中欧',
    'CCT': '常春藤',
    'FD': '富达',
    'RD': '日斗',
    'QG': '泉果',
    'XQ': '兴全',
    'HTF': '汇添富',
    'YFD': '易方达',
}


ARGUS_COLLECTIONS = ARGUS_CONFIG.get('mongo', {}).get('collections', {})
INDUSTRY_GROUPS = ARGUS_CONFIG.get('industry_groups', {})

ARGUS_UNIQUE_KEYS = {
    'credential_score': ['date', 'product_code'],
    'signal': ['date', 'signal_id'],
    'stock_pool': ['date', 'wind_code'],
    'industry_weight': ['date', 'product_code', 'sw1_code'],
}
