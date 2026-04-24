#!/usr/bin/env python3
"""LLM summarization helper - runs in clean environment"""
import sys, os

# Load .env from daily_stock_analysis (3 levels up from src/new_services/)
# _llm_summarize.py is at: .../daily-market-analysis/src/new_services/
# 3 levels up = .../research  →  research/daily_stock_analysis/.env
env_path = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '..', '..', '..',
                 'daily_stock_analysis', '.env')
)
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k] = v

# Also load market_daily_analysis .env if exists (has proxy settings)
md_env = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '..', '..', '..', '..',
                 'daily-market-analysis', '.env')
)
if os.path.exists(md_env):
    for line in open(md_env):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v)

import litellm
litellm.suppress_debug_info = True

max_chars = int(sys.argv[1]) if len(sys.argv) > 1 else 85
prompt = sys.argv[2] if len(sys.argv) > 2 else ''

key = os.environ.get('LLM_MINIMAX_API_KEYS', '').split(',')[0]
base = os.environ.get('LLM_MINIMAX_BASE_URL', 'https://api.minimaxi.com/v1')

try:
    response = litellm.completion(
        model='minimax/MiniMax-M2.7',
        messages=[{'role': 'user', 'content': prompt}],
        api_key=key,
        api_base=base,
        max_tokens=300,  # 减小，避免浪费
        temperature=0.3,
    )
    msg = response.choices[0].message if response and response.choices else None
    raw = ''
    if msg:
        content_raw = msg.content.strip() if msg.content else ''
        # content 有实质内容则使用
        if content_raw and len(content_raw) > 3:
            raw = content_raw
        else:
            rc = getattr(msg, 'reasoning_content', None) or ''
            # MiniMax M2.7 将摘要放在 reasoning_content 末尾
            # 格式通常是 "Final answer: <摘要>" 或直接是纯中文摘要段
            import re
            # 优先找 Final answer 标记
            marker = 'Final answer:'
            if marker in rc:
                raw = rc.split(marker)[-1].strip()
            else:
                # 找最后一个独立的中文句子段（不以英文开头）
                # 将内容按换行分段，取最后一段包含中文的
                paragraphs = rc.split('\n')
                for para in reversed(paragraphs):
                    para = para.strip()
                    # 跳过英文推理过程
                    if not para:
                        continue
                    # 如果是纯中文内容段，很可能就是摘要
                    if re.search(r'[\u4e00-\u9fff]', para) and len(para) > 5:
                        # 进一步：取最后一个完整句
                        sentences = re.findall(r'[^。！？]+[。！？]', para + '|')
                        if sentences:
                            raw = sentences[-1].rstrip('|')
                        else:
                            raw = para
                        break
                # 兜底：取 reasoning_content 末尾 400 字
                if not raw:
                    raw = rc.strip()[-400:] if rc.strip() else ''
    sys.stdout.write(raw[:max_chars])
except Exception as e:
    sys.stderr.write(f'LLM error: {e}\n')
    sys.stdout.write('')
