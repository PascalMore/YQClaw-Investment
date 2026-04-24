#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1 测试脚本：验证 daily-market-analysis 对 daily_stock_analysis 的集成
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, '/home/pascal/.openclaw/workspace/skills/investment/research/daily-market-analysis/src')
sys.path.insert(0, '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis')

print("=" * 60)
print("Phase 1: 验证 daily_stock_analysis 集成")
print("=" * 60)

# Test 1: 导入 analyzer_service
print("\n[Test 1] 导入 analyzer_service...")
try:
    from analyzer_service import analyze_stock, analyze_stocks, perform_market_review
    print("✅ analyzer_service 导入成功")
    print(f"   - analyze_stock: {analyze_stock}")
    print(f"   - analyze_stocks: {analyze_stocks}")
    print(f"   - perform_market_review: {perform_market_review}")
except Exception as e:
    print(f"❌ analyzer_service 导入失败: {e}")
    import traceback
    traceback.print_exc()

# Test 2: 导入 MarketDataAdapter
print("\n[Test 2] 导入 MarketDataAdapter...")
try:
    from new_services import get_market_adapter
    print("✅ MarketDataAdapter 导入成功")
except Exception as e:
    print(f"❌ MarketDataAdapter 导入失败: {e}")
    import traceback
    traceback.print_exc()

# Test 3: 获取 A股复盘
print("\n[Test 3] 获取 A股大盘复盘 (get_cn_market_review)...")
try:
    adapter = get_market_adapter()
    result = adapter.get_cn_market_review()
    if result:
        print(f"✅ A股复盘获取成功，长度: {len(result)} 字符")
        print("\n--- 预览前 500 字符 ---")
        print(result[:500])
    else:
        print("⚠️ A股复盘返回 None（可能无数据或出错）")
except Exception as e:
    print(f"❌ A股复盘获取失败: {e}")
    import traceback
    traceback.print_exc()

# Test 4: 获取美股复盘
print("\n[Test 4] 获取美股大盘复盘 (get_us_market_review)...")
try:
    adapter = get_market_adapter()
    result = adapter.get_us_market_review()
    if result:
        print(f"✅ 美股复盘获取成功，长度: {len(result)} 字符")
        print("\n--- 预览前 500 字符 ---")
        print(result[:500])
    else:
        print("⚠️ 美股复盘返回 None（可能无数据或出错）")
except Exception as e:
    print(f"❌ 美股复盘获取失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
