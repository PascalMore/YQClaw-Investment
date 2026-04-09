# -*- coding: utf-8 -*-
"""
===================================
市场数据适配层 - Market Data Adapter
===================================

Phase 3 更新：
1. 从 reports 目录读取复盘报告（A 股/美股）
2. 复用 daily_stock_analysis 的 DataFetcherManager 获取实时指数
3. 复用 search_service 进行新闻搜索
4. Crypto 数据（CoinGecko API）

复用 daily_stock_analysis：
- DataFetcherManager: get_main_indices(region="cn/us/hk")
- reports 目录: 读取已生成的复盘报告
"""

import os
import sys
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

# ============================================
# 路径设置
# ============================================

def _get_project_root() -> str:
    """获取 daily-market-analysis 项目根目录"""
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current))

def _get_dsa_root() -> str:
    """获取 daily_stock_analysis 项目根目录"""
    root = _get_project_root()
    return os.path.join(os.path.dirname(root), 'daily_stock_analysis')

def _setup_import_paths():
    """
    设置导入路径，确保 daily_stock_analysis 的包优先被导入
    
    重要：dsa_path 必须放在 market_analysis 路径之前，
    否则会错误导入 market_analysis venv 中的旧版本包（如 chardet）
    """
    dsa_path = _get_dsa_root()
    dsa_src_path = os.path.join(dsa_path, 'src')
    
    # 先添加 daily_stock_analysis（优先级高）
    if dsa_src_path not in sys.path:
        sys.path.insert(0, dsa_src_path)
    if dsa_path not in sys.path:
        sys.path.insert(0, dsa_path)

_setup_import_paths()


# ============================================
# 市场数据适配器
# ============================================

class MarketDataAdapter:
    """
    市场数据适配器
    
    复用 daily_stock_analysis 的数据层：
    - DataFetcherManager.get_main_indices() 获取实时指数
    - reports 目录读取复盘报告
    """
    
    def __init__(self, config=None):
        self.config = config
        self._reports_root = os.path.join(_get_dsa_root(), 'reports')
        self._fetcher = None
    
    @property
    def fetcher(self):
        """获取 DataFetcherManager 实例"""
        if self._fetcher is None:
            from data_provider.base import DataFetcherManager
            self._fetcher = DataFetcherManager()
        return self._fetcher
    
    # SearchService removed - using direct Tavily API
    
    # ========================================
    # 核心：获取各市场实时指数数据
    # ========================================
    
    def get_cn_index_data(self) -> List[Dict]:
        """获取 A 股主要指数（上证/深证/创业板/科创50）"""
        try:
            indices = self.fetcher.get_main_indices(region="cn")
            return indices if indices else []
        except Exception as e:
            print(f"[Adapter] 获取 A 股指数失败：{e}")
            return []
    
    def get_hk_index_data(self) -> List[Dict]:
        """获取港股主要指数（恒生/恒生科技）
        
        注意: fetcher.get_main_indices(region='hk') 返回错误数据（A股），
        因此直接使用 yfinance 获取港股指数
        """
        return self._fetch_hk_indices_direct()
    
    def get_us_index_data(self) -> List[Dict]:
        """获取美股主要指数（SPX/NDX/DJI）
        
        注意：跳过 fetcher 直接使用 yfinance，避免双重调用导致 rate limiting
        """
        # 直接使用 yfinance（跳过 fetcher 避免重复调用）
        return self._fetch_us_indices_direct()
    
    def _fetch_hk_indices_direct(self):
        """直接获取港股指数（恒生/恒生科技）
        
        恒生指数: akshare stock_hk_index_daily_sina (akshare provides volume)
        恒生科技: akshare stock_hk_index_daily_sina (yfinance ^HSTECH 已下市)
        """
        result = []
        
        # 恒生指数 - akshare (for volume data)
        try:
            import akshare as ak
            df = ak.stock_hk_index_daily_sina(symbol='HSI')
            if not df.empty and len(df) >= 2:
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                close = float(latest['close'])
                prev_close = float(prev['close'])
                change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
                volume = float(latest.get('amount', 0))  # amount in HK$
                result.append({
                    'name': '恒生指数',
                    'code': 'HSI',
                    'current': close,
                    'change_pct': change_pct,
                    'volume': volume,
                })
            elif not df.empty:
                latest = df.iloc[-1]
                close = float(latest['close'])
                open_price = float(latest['open'])
                change_pct = ((close - open_price) / open_price * 100) if open_price > 0 else 0
                volume = float(latest.get('amount', 0))
                result.append({
                    'name': '恒生指数',
                    'code': 'HSI',
                    'current': close,
                    'change_pct': change_pct,
                    'volume': volume,
                })
        except Exception as e:
            print(f"[Adapter] 恒生指数获取失败：{e}")
        
        # 恒生科技指数 - akshare (yfinance ^HSTECH 已下市)
        try:
            import akshare as ak
            df = ak.stock_hk_index_daily_sina(symbol='HSTECH')
            if not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                close = float(latest['close'])
                prev_close = float(prev['close'])
                change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
                # volume from akshare is already in HK dollar amount
                volume = float(latest.get('amount', 0))
                result.append({
                    'name': '恒生科技',
                    'code': 'HSTECH',
                    'current': close,
                    'change_pct': change_pct,
                    'volume': volume,
                })
        except Exception as e:
            print(f"[Adapter] 恒生科技获取失败：{e}")
        
        return result
    
    def _fetch_us_indices_direct(self):
        """直接使用 yfinance 获取美股指数（带重试）"""
        import time
        import yfinance as yf
        
        def fetch_with_retry(ticker_symbol, name, code, max_retries=3, initial_delay=2):
            """带重试的获取函数"""
            for attempt in range(max_retries):
                try:
                    ticker = yf.Ticker(ticker_symbol)
                    hist = ticker.history(period="2d")
                    if not hist.empty:
                        close = float(hist['Close'].iloc[-1])
                        if len(hist) > 1:
                            prev_close = float(hist['Close'].iloc[-2])
                        else:
                            prev_close = close
                        change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
                        return {
                            'name': name,
                            'code': code,
                            'current': close,
                            'change_pct': change_pct,
                            'volume': 0,
                        }
                except Exception as e:
                    if 'rate' in str(e).lower() or '429' in str(e):
                        print(f"[Adapter] {name} 获取失败(尝试 {attempt+1}/{max_retries}): 速率限制，等待 {initial_delay*(attempt+1)}s...")
                        time.sleep(initial_delay * (attempt + 1))
                    else:
                        print(f"[Adapter] {name} 获取失败：{e}")
                        break
            return None
        
        result = []
        
        # 标普500
        data = fetch_with_retry("^GSPC", "标普500", "SPX")
        if data:
            result.append(data)
        
        # 纳斯达克
        data = fetch_with_retry("^IXIC", "纳斯达克综合", "NDX")
        if data:
            result.append(data)
        
        return result
    
    # ========================================
    # 核心：读取 reports 目录已有报告
    # ========================================
    
    def _get_latest_report_path(self) -> Optional[str]:
        """获取最新复盘报告路径"""
        if not os.path.exists(self._reports_root):
            return None
        
        today = date.today()
        for days_ago in range(3):
            check_date = today - timedelta(days=days_ago)
            report_name = f"market_review_{check_date.strftime('%Y%m%d')}.md"
            report_path = os.path.join(self._reports_root, report_name)
            if os.path.exists(report_path):
                return report_path
        return None
    
    def _parse_report_sections(self, content: str) -> Dict[str, str]:
        """解析复盘报告，提取 A 股和美股部分"""
        sections = {}
        
        if "以下为美股大盘复盘" in content:
            parts = content.split("以下为美股大盘复盘")
            cn_part = parts[0]
            us_part = parts[1] if len(parts) > 1 else ""
            
            if "# A股大盘复盘" in cn_part:
                cn_section = cn_part.split("# A股大盘复盘")[1]
            else:
                cn_section = cn_part
            
            if "# 美股大盘复盘" in us_part:
                us_section = us_part.split("# 美股大盘复盘")[1]
            else:
                us_section = us_part
            
            sections['cn'] = cn_section.strip()
            sections['us'] = us_section.strip()
        elif "# 美股大盘复盘" in content:
            sections['us'] = content.split("# 美股大盘复盘")[1].strip()
        elif "# A股大盘复盘" in content:
            sections['cn'] = content.split("# A股大盘复盘")[1].strip()
        else:
            sections['raw'] = content
        
        return sections
    
    # ========================================
    # 复盘报告获取
    # ========================================
    
    def get_cn_market_review(self) -> Optional[str]:
        """获取 A 股大盘复盘（从 reports 目录读取）"""
        report_path = self._get_latest_report_path()
        if not report_path:
            return None
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = self._parse_report_sections(content)
            return sections.get('cn') or sections.get('raw')
        except Exception as e:
            print(f"[Adapter] 读取 A 股复盘失败：{e}")
            return None
    
    def get_us_market_review(self) -> Optional[str]:
        """获取美股大盘复盘（从 reports 目录读取）"""
        report_path = self._get_latest_report_path()
        if not report_path:
            return None
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = self._parse_report_sections(content)
            return sections.get('us')
        except Exception as e:
            print(f"[Adapter] 读取美股复盘失败：{e}")
            return None
    
    # ========================================
    # 新闻搜索
    # ========================================
    
    # ========================================
    # 新闻搜索（simple_news）
    # ========================================
    
    def _load_env(self):
        """加载环境变量"""
        import os
        env_file = '/home/pascal/.openclaw/workspace/skills/investment/research/daily-stock-analysis/.env'
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k] = v
    
    def _load_env(self):
        """加载环境变量"""
        import os
        env_file = '/home/pascal/.openclaw/workspace/skills/investment/research/daily-stock-analysis/.env'
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k] = v
    
    def get_global_news(self, limit: int = 3) -> List[Dict[str, str]]:
        """获取全球宏观热点新闻 - 使用 MiniMax Search"""
        return self.get_international_news("global", limit)
    


    def get_international_news(self, category: str = "global", limit: int = 3) -> List[Dict[str, str]]:
        """获取国际热点新闻 - 使用 MiniMax Search
        
        Args:
            category: "global" | "crypto" | "us"
            limit: 返回条数
        """
        # 清除代理环境变量
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        
        # 加载 .env 配置
        try:
            from dotenv import load_dotenv
            env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'
            if os.path.exists(env_path):
                load_dotenv(env_path)
        except Exception as e:
            print(f"[Adapter] dotenv 加载失败: {e}")
        
        category_keywords = {
            "global": "Federal Reserve interest rate cut inflation economy news April 2026",
            "crypto": "Bitcoin price Ethereum ETF crypto market news today April 2026",
            "us": "S&P 500 Nasdaq Dow Jones stock market news today April 2026"
        }
        
        keyword = category_keywords.get(category, category_keywords["global"])
        
        # 直接调用 MiniMax API
        minimax_key = os.environ.get("LLM_MINIMAX_API_KEYS", "").split(",")[0] if os.environ.get("LLM_MINIMAX_API_KEYS") else ""
        if not minimax_key:
            minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        
        if minimax_key:
            try:
                import requests
                headers = {
                    'Authorization': f'Bearer {minimax_key}',
                    'Content-Type': 'application/json',
                    'MM-API-Source': 'Minimax-MCP',
                }
                payload = {"q": keyword}
                resp = requests.post(
                    'https://api.minimaxi.com/v1/coding_plan/search',
                    headers=headers, json=payload, timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    seen_titles = set()
                    for item in data.get('organic', [])[:limit]:
                        title = item.get('title', '').strip()
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            results.append({
                                "title": title,
                                "content": item.get('snippet', title),
                                "source": "MiniMax",
                                "datetime": "",
                                "url": item.get('url', '')
                            })
                    if results:
                        print(f"[Adapter] {category} 国际新闻 (MiniMax): {len(results)} 条")
                        return results
            except Exception as e:
                print(f"[Adapter] MiniMax 失败: {e}")
        
        print(f"[Adapter] {category} 国际新闻: 获取失败")
        return []



    def get_international_news(self, category: str = "global", limit: int = 3) -> List[Dict[str, str]]:
        """获取国际热点新闻 - 使用 MiniMax Search"""
        # 清除代理
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        
        # 加载 .env
        try:
            from dotenv import load_dotenv
            env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'
            if os.path.exists(env_path):
                load_dotenv(env_path)
        except:
            pass
        
        keywords = {
            "global": "Federal Reserve interest rate economy news April 2026",
            "crypto": "Bitcoin Ethereum crypto market news April 2026",
            "us": "S&P 500 Nasdaq Dow stock market news April 2026"
        }
        
        keyword = keywords.get(category, keywords["global"])
        minimax_key = os.environ.get("LLM_MINIMAX_API_KEYS", "").split(",")[0] if os.environ.get("LLM_MINIMAX_API_KEYS") else ""
        
        if minimax_key:
            try:
                import requests
                headers = {'Authorization': f'Bearer {minimax_key}', 'Content-Type': 'application/json', 'MM-API-Source': 'Minimax-MCP'}
                resp = requests.post('https://api.minimaxi.com/v1/coding_plan/search', headers=headers, json={"q": keyword}, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    seen = set()
                    for item in data.get('organic', [])[:limit]:
                        title = item.get('title', '').strip()
                        if title and title not in seen:
                            seen.add(title)
                            results.append({"title": title, "content": item.get('snippet', title), "source": "MiniMax", "datetime": "", "url": item.get('url', '')})
                    if results:
                        print(f"[Adapter] {category} 国际新闻 (MiniMax): {len(results)} 条")
                        return results
            except Exception as e:
                print(f"[Adapter] MiniMax 失败: {e}")
        
        print(f"[Adapter] {category} 国际新闻: 获取失败")
        return []

    def get_market_news(self, market: str, limit: int = 5) -> List[Dict[str, str]]:
        """获取特定市场新闻 - 根据市场类型选择新闻源
        
        国际市场 (us/crypto/global): MiniMax Search
        国内市场 (cn/hk/commodity): MiniMax > 华尔街见闻 > CCTV
        """
        international_markets = ["us", "crypto", "global"]
        domestic_markets = ["cn", "hk", "commodity"]
        
        if market in international_markets:
            return self.get_international_news(market, limit)
        elif market in domestic_markets:
            return self.get_domestic_news(market, limit)
        else:
            return self.get_domestic_news("cn", limit)

    def get_domestic_news(self, market: str = "cn", limit: int = 3) -> List[Dict[str, str]]:
        """获取国内热点新闻 - 降级链: MiniMax > 华尔街见闻 > CCTV
        """
        # 市场热点关键字
        keywords = {
            "cn": "A股 热点板块 概念股 涨停 龙头股 资金流入 今日行情 2026年4月",
            "hk": "港股 恒生指数 恒生科技 科技股 南向资金 腾讯 阿里 今日行情 2026年4月",
            "commodity": "黄金价格 原油走势 大宗商品 期货 铜 农产品 今日行情 2026年4月"
        }
        
        keyword = keywords.get(market, keywords["cn"])
        results = []
        seen_titles = set()
        
        # 源1: MiniMax Search (市场热点)
        minimax_key = os.environ.get("LLM_MINIMAX_API_KEYS", "").split(",")[0] if os.environ.get("LLM_MINIMAX_API_KEYS") else ""
        if not minimax_key:
            minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        
        if minimax_key:
            try:
                import requests
                headers = {
                    'Authorization': f'Bearer {minimax_key}',
                    'Content-Type': 'application/json',
                    'MM-API-Source': 'Minimax-MCP',
                }
                payload = {"q": keyword}
                resp = requests.post(
                    'https://api.minimaxi.com/v1/coding_plan/search',
                    headers=headers, json=payload, timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get('organic', [])[:limit]:
                        title = item.get('title', '').strip()
                        if title and len(title) > 5 and title not in seen_titles:
                            seen_titles.add(title)
                            results.append({
                                "title": title,
                                "content": item.get('snippet', title),
                                "source": "MiniMax",
                                "datetime": "",
                                "url": item.get('url', '')
                            })
            except Exception as e:
                print(f"[Adapter] MiniMax 失败: {e}")
        
        if len(results) >= limit:
            results.sort(key=lambda x: x.get('datetime', ''), reverse=True)
            print(f"[Adapter] {market} 国内新闻 (MiniMax): {len(results)} 条")
            return results[:limit]
        
        # 源2: 华尔街见闻
        try:
            import akshare as ak
            df = ak.stock_news_main_cx()
            if df is not None and not df.empty:
                for _, row in df.head(limit * 2).iterrows():
                    title = str(row.get('summary', row.get('title', ''))).strip()
                    if title and 'None' not in title and len(title) > 10 and title not in seen_titles:
                        seen_titles.add(title)
                        results.append({
                            "title": title,
                            "content": title,
                            "source": f"华尔街见闻-{row.get('tag', '市场')}",
                            "datetime": '',
                            "url": row.get('url', '')
                        })
        except Exception as e:
            print(f"[Adapter] 华尔街见闻失败: {e}")
        
        if len(results) >= limit:
            results.sort(key=lambda x: x.get('datetime', ''), reverse=True)
            return results[:limit]
        
        # 源3: CCTV新闻
        try:
            import akshare as ak
            df = ak.news_cctv()
            if df is not None and not df.empty:
                for _, row in df.head(limit).iterrows():
                    title = str(row.get('title', '')).strip()
                    if title and 'None' not in title and title not in seen_titles:
                        seen_titles.add(title)
                        results.append({
                            "title": title,
                            "content": str(row.get('content', title))[:200],
                            "source": "CCTV",
                            "datetime": str(row.get('date', '')),
                            "url": ''
                        })
        except Exception as e:
            print(f"[Adapter] CCTV新闻失败: {e}")
        
        results.sort(key=lambda x: x.get('datetime', ''), reverse=True)
        return results[:limit]
    
    # ========================================
    # Crypto 数据
    # ========================================
    
    def get_crypto_data(self) -> List[Dict[str, Any]]:
        """获取主流数字货币数据
        
        优先级：Binance API > Yahoo Finance
        Binance: BTC/ETH/SOL/BNB/PEPE
        Yahoo Finance: 备用
        """
        # 清除代理环境变量
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        
        # 加载 .env 获取代理配置（手动读取，不依赖 dotenv）
        proxies = None
        try:
            env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            os.environ[k] = v
            if os.environ.get('USE_PROXY', '').lower() == 'true':
                proxy_host = os.environ.get('PROXY_HOST', '127.0.0.1')
                proxy_port = os.environ.get('PROXY_PORT', '7890')
                proxies = {
                    'http': f'http://{proxy_host}:{proxy_port}',
                    'https': f'http://{proxy_host}:{proxy_port}',
                }
                print(f"[Adapter] 使用代理: {proxy_host}:{proxy_port}")
        except Exception as e:
            print(f"[Adapter] 代理配置加载失败: {e}")
        
        # Binance API
        try:
            import requests
            symbols_config = [
                ('BTCUSDT', '比特币 BTC', 'BTC'),
                ('ETHUSDT', '以太坊 ETH', 'ETH'),
                ('SOLUSDT', 'Solana SOL', 'SOL'),
                ('BNBUSDT', 'BNB', 'BNB'),
                ('PEPEUSDT', 'Pepe', 'PEPE'),
            ]
            crypto_data = []
            for sym, name, short_sym in symbols_config:
                try:
                    resp = requests.get(
                        f'https://api.binance.com/api/v3/ticker/24hr',
                        params={'symbol': sym},
                        proxies=proxies,
                        timeout=10
                    )
                    if resp.status_code == 200:
                        d = resp.json()
                        crypto_data.append({
                            'symbol': short_sym,
                            'name': name,
                            'price': float(d.get('lastPrice', 0)),
                            'change_pct': float(d.get('priceChangePercent', 0)),
                            'volume': float(d.get('quoteVolume', 0)),
                        })
                except Exception as e:
                    print(f"[Adapter] Binance {sym} failed: {e}")
            if crypto_data:
                print(f"[Adapter] Crypto 数据 (Binance): {len(crypto_data)} 个币种")
                return crypto_data
        except Exception as e:
            print(f"[Adapter] Binance 失败: {e}")
        
        # Fallback: Yahoo Finance
        try:
            import yfinance as yf
            tickers = {
                'BTC-USD': ('比特币 BTC', 'BTC'),
                'ETH-USD': ('以太坊 ETH', 'ETH'),
                'SOL-USD': ('Solana SOL', 'SOL'),
            }
            crypto_data = []
            for symbol, (name, short_sym) in tickers.items():
                try:
                    t = yf.Ticker(symbol)
                    hist = t.history(period='2d')
                    if not hist.empty and len(hist) >= 2:
                        curr = float(hist['Close'].iloc[-1])
                        prev = float(hist['Close'].iloc[-2])
                        change_pct = ((curr - prev) / prev * 100) if prev > 0 else 0
                        crypto_data.append({
                            'symbol': short_sym,
                            'name': name,
                            'price': curr,
                            'change_pct': change_pct,
                            'volume': 0,
                        })
                except Exception as e:
                    print(f"[Adapter] Yahoo {symbol} failed: {e}")
            if crypto_data:
                print(f"[Adapter] Crypto 数据 (Yahoo): {len(crypto_data)} 个币种")
                return crypto_data
        except Exception as e:
            print(f"[Adapter] Yahoo Finance 失败: {e}")
        
        return []
    
    def get_crypto_market_review(self) -> str:
        """生成数字货币市场复盘"""
        data = self.get_crypto_data()
        
        if not data:
            return "### 主流加密货币表现\n\n数字货币数据获取失败。"
        
        lines = ["### 主流加密货币表现", ""]
        
        for coin in data:
            change_emoji = "🟢" if coin['change_pct'] > 0 else "🔴" if coin['change_pct'] < 0 else "⚪"
            price = coin['price']
            if price >= 1000:
                price_str = f"${price:,.0f}"
            elif price >= 1:
                price_str = f"${price:,.2f}"
            else:
                price_str = f"${price:,.4f}"
            
            lines.append(f"- **{coin['name']}**：{change_emoji} {price_str} ({coin['change_pct']:+.2f}%)")
        
        lines.append("")
        lines.append("### 一句话判断")
        
        if data:
            btc = data[0]
            if btc['change_pct'] > 5:
                verdict = "BTC 强势突破，市场 FOMO 情绪升温"
            elif btc['change_pct'] > 2:
                verdict = "BTC 震荡偏强，市场情绪乐观"
            elif btc['change_pct'] > 0:
                verdict = "BTC 小幅上涨，观望情绪浓厚"
            elif btc['change_pct'] < -5:
                verdict = "BTC 大幅回调，注意风险控制"
            elif btc['change_pct'] < -2:
                verdict = "BTC 震荡偏弱，市场情绪谨慎"
            else:
                verdict = "BTC 横盘整理，等待方向选择"
            lines.append(f"- {verdict}")
        
        return "\n".join(lines)
    
    # ========================================
    # 预留接口
    # ========================================
    
    def get_hk_market_review(self) -> str:
        """港股复盘 - 待实现"""
        return "### 港股市场概况\n\n港股复盘待接入。"
    
    def get_commodity_market_review(self) -> str:
        """大宗商品复盘 - 待实现"""
        return "### 大宗商品市场\n\n数据待接入。"
    
    def get_bond_market_review(self) -> str:
        """债券复盘 - 待实现"""
        return "### 债券市场\n\n数据待接入。"
    
    def get_financial_calendar(self, days: int = 30) -> List[Dict[str, Any]]:
        """金融日历 - 待实现"""
        return []


# ============================================
# 单例访问器
# ============================================

_global_adapter: Optional[MarketDataAdapter] = None

def get_market_adapter(config=None) -> MarketDataAdapter:
    """获取全局市场数据适配器实例"""
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = MarketDataAdapter(config=config)
    return _global_adapter
