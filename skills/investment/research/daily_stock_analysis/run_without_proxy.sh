#!/bin/bash
# Unset all proxy settings before running Python
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY SOCKS_PROXY
unset http_proxy https_proxy all_proxy socks_proxy
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY SOCKS_PROXY
unset http_proxy https_proxy all_proxy socks_proxy

# Run Python with clean environment
exec /home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/venv/bin/python "$@"
