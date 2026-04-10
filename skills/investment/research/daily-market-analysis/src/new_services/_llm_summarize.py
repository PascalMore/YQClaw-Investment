#!/usr/bin/env python3
"""LLM summarization helper - runs in clean environment without market_data_adapter import pollution"""
import sys, os, json

# Load env (parent of parent is daily-market-analysis/, go up one more level to research/ then into daily_stock_analysis/)
env_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'daily_stock_analysis', '.env'))
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k] = v

import litellm

max_chars = int(sys.argv[1]) if len(sys.argv) > 1 else 85
prompt = sys.argv[2] if len(sys.argv) > 2 else ''

key = os.environ.get('LLM_MINIMAX_API_KEYS', os.environ.get('MINIMAX_API_KEY', '')).split(',')[0]
base = os.environ.get('LLM_MINIMAX_BASE_URL', 'https://api.minimaxi.com/v1')

try:
    response = litellm.completion(
        model='minimax/MiniMax-M2.7',
        messages=[{'role': 'user', 'content': prompt}],
        api_key=key,
        api_base=base,
        max_tokens=200,
        temperature=0.3,
    )
    summary = response.choices[0].message.content.strip() if response and response.choices else ''
    print(summary, end='')
except Exception as e:
    print('', end='')
