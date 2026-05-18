# skills/data/portfolio/config.py
"""Portfolio and Argus collection configuration."""

# MongoDB portfolio collection configuration
PORTFOLIO_COLLECTIONS = {
    'basic_info': 'portfolio_basic_info',
    'nav': 'portfolio_nav',
    'position': 'portfolio_position',
    'trade': 'portfolio_trade',
}

# Argus output collections (08_research)
ARGUS_COLLECTIONS = {
    'signal': '08_research_argus_signal',
    'stock_pool': '08_research_argus_stock_pool',
    'credential_score': '08_research_argus_credential_score',
    'credibility': '08_research_argus_credential_score',
}

# Product alias configuration
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
