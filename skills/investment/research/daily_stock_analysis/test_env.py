#!/usr/bin/env python
# Very first thing - use ctypes to clear environment BEFORE Python starts
import ctypes, os

# Clear all proxy-related env vars at C level before Python initialization
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        ctypes.os.environ.pop(key, None)

# Now proceed with normal imports
print('Testing litellm...')
import sys
sys.path.insert(0, '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis')

os.environ['MINIMAX_API_KEY'] = 'sk-cp-6zYqByU7U26dpVHSh0Ys_cgJLZjrsyC4zLBet8QHThZRutXseCCKgx3MB9GTRP_eaUlLNCWwaQsjk0Z_8_UFkcv-uo0avsfR5JThPMCnzplyotV3x1-8MXY'

import litellm
try:
    response = litellm.completion(
        model="minimax/MiniMax-M2.7",
        messages=[{"role": "user", "content": "Reply OK"}],
        max_tokens=10
    )
    print('SUCCESS:', response.choices[0].message.content)
except Exception as e:
    print('Error:', type(e).__name__)
    print('Message:', str(e)[:500])
