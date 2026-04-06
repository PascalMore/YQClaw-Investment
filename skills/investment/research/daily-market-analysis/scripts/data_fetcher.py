#!/usr/bin/env python3
"""
数据获取模块 - 全球市场数据
支持：A 股、港股、美股、数字货币、大宗商品
"""

import akshare as ak
import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time


class MarketDataFetcher:
    """全球市场数据获取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    # ==================== A 股数据 ====================
    
    def get_a_stock_index(self) -> Dict:
        """获取 A 股主要指数"""
        try:
            # 上证指数
            sh = ak.stock_zh_index_daily(symbol="sh000001")
            # 深证成指
            sz = ak.stock_zh_index_daily(symbol="sz399001")
            # 创业板指
            cyb = ak.stock_zh_index_daily(symbol="sz399006")
            
            return {
                "上证指数": {
                    "收盘": sh['close'].iloc[-1],
                    "涨跌": (sh['close'].iloc[-1] - sh['close'].iloc[-2]) / sh['close'].iloc[-2] * 100
                },
                "深证成指": {
                    "收盘": sz['close'].iloc[-1],
                    "涨跌": (sz['close'].iloc[-1] - sz['close'].iloc[-2]) / sz['close'].iloc[-2] * 100
                },
                "创业板指": {
                    "收盘": cyb['close'].iloc[-1],
                    "涨跌": (cyb['close'].iloc[-1] - cyb['close'].iloc[-2]) / cyb['close'].iloc[-2] * 100
                }
            }
        except Exception as e:
            print(f"获取 A 股指数失败：{e}")
            return {}
    
    def get_a_stock_realtime(self, symbol: str) -> Dict:
        """获取 A 股个股实时行情"""
        try:
            data = ak.stock_zh_a_spot_em()
            stock = data[data['代码'] == symbol]
            if not stock.empty:
                return {
                    "名称": stock['名称'].iloc[0],
                    "最新价": stock['最新价'].iloc[0],
                    "涨跌幅": stock['涨跌幅'].iloc[0],
                    "成交量": stock['成交量'].iloc[0]
                }
        except Exception as e:
            print(f"获取 A 股{symbol}失败：{e}")
        return {}
    
    # ==================== 港股数据 ====================
    
    def get_hk_stock_index(self) -> Dict:
        """获取港股主要指数"""
        try:
            # 恒生指数
            hsi = ak.stock_hk_index_daily(symbol="HSI")
            # 恒生科技
            hstech = ak.stock_hk_index_daily(symbol="HSTECH")
            
            return {
                "恒生指数": {
                    "收盘": hsi['close'].iloc[-1],
                    "涨跌": (hsi['close'].iloc[-1] - hsi['close'].iloc[-2]) / hsi['close'].iloc[-2] * 100
                },
                "恒生科技": {
                    "收盘": hstech['close'].iloc[-1],
                    "涨跌": (hstech['close'].iloc[-1] - hstech['close'].iloc[-2]) / hstech['close'].iloc[-2] * 100
                }
            }
        except Exception as e:
            print(f"获取港股指数失败：{e}")
            return {}
    
    # ==================== 美股数据 ====================
    
    def get_us_stock_index(self) -> Dict:
        """获取美股主要指数"""
        try:
            indices = {
                "道琼斯": "^DJI",
                "纳斯达克": "^IXIC",
                "标普 500": "^GSPC"
            }
            
            result = {}
            for name, symbol in indices.items():
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d")
                if len(hist) >= 2:
                    close = hist['Close'].iloc[-1]
                    prev_close = hist['Close'].iloc[-2]
                    change = (close - prev_close) / prev_close * 100
                    result[name] = {
                        "收盘": round(close, 2),
                        "涨跌": round(change, 2)
                    }
            
            return result
        except Exception as e:
            print(f"获取美股指数失败：{e}")
            return {}
    
    def get_us_stock_realtime(self, symbol: str) -> Dict:
        """获取美股个股实时行情"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if not hist.empty:
                info = ticker.info
                return {
                    "名称": info.get('shortName', symbol),
                    "最新价": round(hist['Close'].iloc[-1], 2),
                    "涨跌幅": round((hist['Close'].iloc[-1] - hist['Open'].iloc[0]) / hist['Open'].iloc[0] * 100, 2)
                }
        except Exception as e:
            print(f"获取美股{symbol}失败：{e}")
        return {}
    
    # ==================== 数字货币数据 ====================
    
    def get_crypto_prices(self) -> Dict:
        """获取主流加密货币价格"""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
            result = {}
            
            for item in data:
                if item['symbol'] in symbols:
                    name = item['symbol'].replace('USDT', '')
                    result[name] = {
                        "价格": round(float(item['lastPrice']), 2),
                        "24h 涨跌": round(float(item['priceChangePercent']), 2),
                        "24h 成交量": round(float(item['volume']), 2)
                    }
            
            return result
        except Exception as e:
            print(f"获取数字货币价格失败：{e}")
            return {}
    
    # ==================== 大宗商品数据 ====================
    
    def get_commodities_prices(self) -> Dict:
        """获取大宗商品价格"""
        try:
            # 黄金
            gold = yf.Ticker("GC=F")
            gold_hist = gold.history(period="2d")
            
            # 原油
            crude = yf.Ticker("CL=F")
            crude_hist = crude.history(period="2d")
            
            # 铜
            copper = yf.Ticker("HG=F")
            copper_hist = copper.history(period="2d")
            
            result = {}
            
            if len(gold_hist) >= 2:
                close = gold_hist['Close'].iloc[-1]
                prev = gold_hist['Close'].iloc[-2]
                result["黄金"] = {
                    "价格": round(close, 2),
                    "涨跌": round((close - prev) / prev * 100, 2)
                }
            
            if len(crude_hist) >= 2:
                close = crude_hist['Close'].iloc[-1]
                prev = crude_hist['Close'].iloc[-2]
                result["原油"] = {
                    "价格": round(close, 2),
                    "涨跌": round((close - prev) / prev * 100, 2)
                }
            
            if len(copper_hist) >= 2:
                close = copper_hist['Close'].iloc[-1]
                prev = copper_hist['Close'].iloc[-2]
                result["铜"] = {
                    "价格": round(close, 2),
                    "涨跌": round((close - prev) / prev * 100, 2)
                }
            
            return result
        except Exception as e:
            print(f"获取大宗商品价格失败：{e}")
            return {}
    
    # ==================== 综合数据获取 ====================
    
    def get_all_market_data(self) -> Dict:
        """获取全部市场数据"""
        print("📊 开始获取市场数据...")
        
        result = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "a_stock": self.get_a_stock_index(),
            "hk_stock": self.get_hk_stock_index(),
            "us_stock": self.get_us_stock_index(),
            "crypto": self.get_crypto_prices(),
            "commodities": self.get_commodities_prices()
        }
        
        print("✅ 市场数据获取完成")
        return result


# 测试函数
if __name__ == "__main__":
    fetcher = MarketDataFetcher()
    data = fetcher.get_all_market_data()
    
    print("\n" + "="*60)
    print("📈 市场数据预览")
    print("="*60)
    
    if data.get("a_stock"):
        print("\n🇨🇳 A 股:")
        for name, info in data["a_stock"].items():
            print(f"  {name}: {info['收盘']:.2f} ({info['涨跌']:+.2f}%)")
    
    if data.get("hk_stock"):
        print("\n🇭🇰 港股:")
        for name, info in data["hk_stock"].items():
            print(f"  {name}: {info['收盘']:.2f} ({info['涨跌']:+.2f}%)")
    
    if data.get("us_stock"):
        print("\n🇺🇸 美股:")
        for name, info in data["us_stock"].items():
            print(f"  {name}: {info['收盘']:.2f} ({info['涨跌']:+.2f}%)")
    
    if data.get("crypto"):
        print("\n₿ 数字货币:")
        for name, info in data["crypto"].items():
            print(f"  {name}: ${info['价格']:.2f} ({info['24h 涨跌']:+.2f}%)")
    
    if data.get("commodities"):
        print("\n🏭 大宗商品:")
        for name, info in data["commodities"].items():
            print(f"  {name}: ${info['价格']:.2f} ({info['涨跌']:+.2f}%)")
    
    print("\n" + "="*60)
