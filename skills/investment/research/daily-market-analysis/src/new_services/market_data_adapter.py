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
import json
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import litellm

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

    核心问题：CWD 为 market_analysis 目录时，Python 会将 CWD/src/ 识别为命名空间包
    并缓存到 sys.modules，导致 data_provider.base 中的 from src.data.stock_mapping 失败。
    解决：直接在 sys.modules['src'].__path__ 中 prepend dsa_src_path，使命名空间包
    在查找子包时优先搜索 daily_stock_analysis/src/。
    """
    dsa_path = _get_dsa_root()
    dsa_src_path = os.path.join(dsa_path, 'src')

    if dsa_path not in sys.path:
        sys.path.insert(0, dsa_path)

    # 将 dsa_src_path prepend 到 src.__path__（命名空间包的搜索路径）
    # 这样 'from src.data.stock_mapping' 会依次查找:
    #   1. dsa_src_path/src/data/  (正确位置)
    #   2. CWD_src_path/src/data/  (不存在，跳过)
    if 'src' in sys.modules:
        src_pkg = sys.modules['src']
        if hasattr(src_pkg, '__path__') and not isinstance(src_pkg.__path__, list):
            # _NamespacePath -> list
            src_pkg.__path__ = [dsa_src_path] + list(src_pkg.__path__)
        elif hasattr(src_pkg, '__path__'):
            src_pkg.__path__ = [dsa_src_path] + list(src_pkg.__path__)

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
        """获取美股主要指数（标普500、纳斯达克）
        
        优先使用 DSA DataFetcherManager.get_main_indices(region="us")，
        有更好的多数据源 fallback（Yfinance → Longbridge → Stooq）。
        失败时降级到 yfinance 直连。
        """
        # 优先走 DSA fetcher（多数据源 fallback）
        try:
            indices = self.fetcher.get_main_indices(region="us")
            if indices:
                # 过滤只保留 SPX 和 IXIC（避免多返回 DJI/VIX）
                filtered = [d for d in indices if d.get('code') in ('SPX', 'IXIC')]
                if filtered:
                    print(f"[Adapter] 美股指数 (DSA fetcher): {len(filtered)} 个")
                    return filtered
        except Exception as e:
            print(f"[Adapter] DSA fetcher 美股获取失败，降级: {e}")

        # Fallback: yfinance 直连
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
        """直接使用 yfinance 获取美股指数（带重试，rate limit 时快速失败）"""
        import time
        import yfinance as yf

        def fetch_with_retry(ticker_symbol, name, code, max_retries=2):
            """带重试的获取函数，rate limit 时最多重试1次"""
            for attempt in range(max_retries):
                try:
                    ticker = yf.Ticker(ticker_symbol)
                    # 带超时：避免挂住（通过 socket 超时实现）
                    import socket
                    socket.setdefaulttimeout(10)
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
                    err_str = str(e).lower()
                    if 'rate' in err_str or '429' in err_str or 'timeout' in err_str:
                        if attempt < max_retries - 1:
                            wait = 2 * (attempt + 1)
                            print(f"[Adapter] {name} rate limit/timeout，重试 ({attempt+1}/{max_retries})...")
                            time.sleep(wait)
                        else:
                            print(f"[Adapter] {name} 获取失败(已达最大重试)，跳过")
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
        data = fetch_with_retry("^IXIC", "纳斯达克", "NDX")
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
    
    def _get_project_env_path(self) -> str:
        """获取本项目 .env 文件路径"""
        current = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current))
        return os.path.join(project_root, '.env')

    def _load_env(self):
        """加载本项目 .env（代理 + API Keys）"""
        env_file = self._get_project_env_path()
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k] = v

    def _llm_news_search(self, prompt: str, max_results: int = 5) -> List[Dict[str, str]]:
        """使用 litellm 调用 MiniMax LLM 搜索新闻
        
        Args:
            prompt: 新闻搜索提示词
            max_results: 最多返回条数
        
        Returns:
            list of dicts with keys: title, source, datetime, url, content
        """
        # 重要：MiniMax API 不走代理，避免代理导致的 529 问题
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        
        self._load_env()
        api_key = os.environ.get("LLM_MINIMAX_API_KEYS", "").split(",")[0].strip()
        if not api_key:
            api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
        if not api_key:
            print("[Adapter] LLM news search: no API key found")
            return []
        
        api_base = os.environ.get("LLM_MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
        
        system_msg = (
            "You are a financial news assistant. "
            "When asked for news, respond ONLY with a valid JSON array (no markdown, no extra text). "
            f"Each element must have these fields: title, source, datetime, url, content. "
            f"Return at most {max_results} items. "
            "If you cannot retrieve real-time news, return an empty JSON array []. "
            "Do NOT include any explanation outside the JSON."
        )
        
        try:
            response = litellm.completion(
                model="minimax/MiniMax-M2.7",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                api_key=api_key,
                api_base=api_base,
                timeout=30,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
            items = json.loads(raw)
            if not isinstance(items, list):
                return []
            results = []
            seen = set()
            for item in items[:max_results]:
                title = str(item.get("title", "")).strip()
                if title and title not in seen:
                    seen.add(title)
                    results.append({
                        "title": title,
                        "content": str(item.get("content", item.get("snippet", title))),
                        "source": str(item.get("source", "MiniMax-LLM")),
                        "datetime": str(item.get("datetime", item.get("time", ""))),
                        "url": str(item.get("url", ""))
                    })
            return results
        except json.JSONDecodeError as e:
            print(f"[Adapter] LLM news search JSON parse error: {e}")
            return []
        except Exception as e:
            print(f"[Adapter] LLM news search error: {e}")
            return []

    def get_global_news(self, limit: int = 3) -> List[Dict[str, str]]:
        """获取全球宏观热点新闻 - 使用 MiniMax LLM"""
        return self.get_international_news("global", limit)

    def get_international_news(self, category: str = "global", limit: int = 3) -> List[Dict[str, str]]:
        """获取国际热点新闻 - 使用 litellm (MiniMax) + DuckDuckGo 备用"""
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        self._load_env()
        
        prompts = {
            "global": (
                f"Please provide the {limit} most important international financial and macroeconomic news "
                "from the past 24 hours (April 2026). Focus on: Federal Reserve, interest rates, "
                "global economy, major central banks, geopolitics affecting markets. "
                f"Return a JSON array of {limit} news items."
            ),
            "crypto": (
                f"Please provide the {limit} most important cryptocurrency market news "
                "from the past 24 hours (April 2026). Focus on: Bitcoin, Ethereum, "
                "major altcoins, DeFi, regulatory developments. "
                f"Return a JSON array of {limit} news items."
            ),
            "us": (
                f"Please provide the {limit} most important US stock market news "
                "from the past 24 hours (April 2026). Focus on: S&P 500, Nasdaq, Dow Jones, "
                "earnings reports, Fed policy, major tech stocks. "
                f"Return a JSON array of {limit} news items."
            )
        }
        prompt = prompts.get(category, prompts["global"])
        
        results = self._llm_news_search(prompt, max_results=limit)
        if results:
            print(f"[Adapter] {category} 国际新闻 (litellm/MiniMax): {len(results)} 条")
            return results
        
        # 备用：使用 DuckDuckGo 搜索新闻
        print(f"[Adapter] {category} 国际新闻 MiniMax 失败，尝试 DuckDuckGo...")
        ddg_results = self._duckduckgo_news_search(category, limit)
        if ddg_results:
            print(f"[Adapter] {category} 国际新闻 (DuckDuckGo): {len(ddg_results)} 条")
            return ddg_results
        
        print(f"[Adapter] {category} 国际新闻: 获取失败")
        return []
    
    def _duckduckgo_news_search(self, category: str = "global", limit: int = 3) -> List[Dict[str, str]]:
        """使用 DuckDuckGo 搜索新闻作为备用源"""
        query_map = {
            "global": "finance economy Federal Reserve interest rates",
            "crypto": "Bitcoin Ethereum cryptocurrency news",
            "us": "S&P 500 Nasdaq stock market news",
        }
        query = query_map.get(category, query_map["global"])
        
        try:
            from duckduckgosearch import DDGS
            results = []
            seen = set()
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=limit * 2):
                    title = r.get("title", "").strip()
                    if title and title not in seen and len(results) < limit:
                        seen.add(title)
                        results.append({
                            "title": title,
                            "content": r.get("body", title)[:200],
                            "source": r.get("source", "DuckDuckGo"),
                            "datetime": r.get("date", ""),
                            "url": r.get("url", "")
                        })
            return results
        except ImportError:
            print("[Adapter] duckduckgosearch 库未安装: pip install duckduckgosearch")
            return []
        except Exception as e:
            print(f"[Adapter] DuckDuckGo 新闻搜索失败: {e}")
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
        """获取国内热点新闻 - 降级链: litellm/MiniMax > 华尔街见闻 > CCTV
        """
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        self._load_env()
        
        # 市场热点提示词
        prompts = {
            "cn": (
                f"请提供今天（2026年4月）A股市场最重要的{limit}条热点新闻。"
                "重点关注：热点板块、概念股、涨停板龙头、主力资金流向、重要政策利好/利空、"
                "重大公司公告。每条新闻包含 title、source、datetime、url、content 字段，"
                f"以JSON数组格式返回，最多{limit}条。"
            ),
            "hk": (
                f"请提供今天（2026年4月）港股市场最重要的{limit}条热点新闻。"
                "重点关注：恒生指数、恒生科技、南向资金动向、腾讯阿里美团等科技龙头、"
                "港股通标的异动、重要宏观数据影响。"
                f"以JSON数组格式返回，最多{limit}条。"
            ),
            "commodity": (
                f"请提供今天（2026年4月）大宗商品市场最重要的{limit}条新闻。"
                "重点关注：黄金价格走势、原油供需、铜铝等工业金属、农产品期货、"
                "OPEC政策、美元走势影响。"
                f"以JSON数组格式返回，最多{limit}条。"
            )
        }
        
        prompt = prompts.get(market, prompts["cn"])
        results = []
        seen_titles = set()
        
        # 源1: litellm/MiniMax LLM (市场热点)
        llm_results = self._llm_news_search(prompt, max_results=limit)
        for item in llm_results:
            title = item.get("title", "").strip()
            if title and len(title) > 5 and title not in seen_titles:
                seen_titles.add(title)
                results.append(item)
        
        if len(results) >= limit:
            results.sort(key=lambda x: x.get('datetime', ''), reverse=True)
            print(f"[Adapter] {market} 国内新闻 (litellm/MiniMax): {len(results)} 条")
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
            env_path = self._get_project_env_path()
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
        """生成大宗商品市场复盘（黄金、原油）"""
        data = self.get_commodity_data()

        if not data:
            return "### 大宗商品市场概况\n\n黄金、原油数据获取失败。"

        lines = ["### 大宗商品市场概况", ""]

        for item in data:
            change_emoji = "🟢" if item['change_pct'] > 0 else "🔴" if item['change_pct'] < 0 else "⚪"
            price = item['price']
            unit = item.get('unit', '')
            amount = item.get('amount', 0)
            amount_str = f"{amount / 1e8:.2f}亿" if amount >= 1e8 else f"{amount / 1e4:.2f}万" if amount >= 1e4 else "-"

            lines.append(
                f"- **{item['name']}**：{change_emoji} {price:.2f}{unit} "
                f"({item['change_pct']:+.2f}%) | 成交金额: {amount_str}"
            )

        lines.append("")
        lines.append("### 一句话判断")

        gold = next((x for x in data if x['code'] == 'GOLD'), None)
        oil = next((x for x in data if x['code'] == 'OIL'), None)

        if gold and oil:
            if gold['change_pct'] > 0 and oil['change_pct'] > 0:
                verdict = "黄金、原油同步上涨，避险与需求双重支撑"
            elif gold['change_pct'] > 0 and oil['change_pct'] < 0:
                verdict = "黄金上涨、原油下跌，避险情绪升温但需求预期降温"
            elif gold['change_pct'] < 0 and oil['change_pct'] > 0:
                verdict = "黄金下跌、原油上涨，避险降温但需求预期回升"
            elif gold['change_pct'] < 0 and oil['change_pct'] < 0:
                verdict = "黄金、原油同步下跌，避险需求减弱"
            else:
                verdict = "黄金、原油窄幅震荡，等待方向"
            lines.append(f"- {verdict}")
        elif gold:
            lines.append(f"- 黄金 {gold['change_pct']:+.2f}%，{'强势' if gold['change_pct'] > 1 else '小幅' if gold['change_pct'] > 0 else '小幅下跌' if gold['change_pct'] < 0 else '横盘'}运行")
        elif oil:
            lines.append(f"- 原油 {oil['change_pct']:+.2f}%，{'强势' if oil['change_pct'] > 1 else '小幅' if oil['change_pct'] > 0 else '小幅下跌' if oil['change_pct'] < 0 else '横盘'}运行")

        return "\n".join(lines)

    def get_commodity_data(self) -> List[Dict[str, Any]]:
        """获取大宗商品数据（黄金、原油）
        
        数据优先级：
        1. Tushare 期货主连数据（黄金=AU.SHF, 原油=SC.INE）
        2. akshare 现货/期货数据（备用）
        """
        self._load_env()
        result = []
        tushare_token = os.environ.get('TUSHARE_TOKEN', '')

        # ── 1. Tushare 期货主连 ───────────────────────────────
        if tushare_token:
            try:
                import tushare as ts
                ts.set_token(tushare_token)
                pro = ts.pro_api()

                # 获取最近有数据的交易日（today可能是假日）
                today_str = datetime.now().strftime('%Y%m%d')
                mapping = None
                for days_back in range(10):
                    check_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
                    mapping = pro.fut_mapping(trade_date=check_date)
                    if not mapping.empty:
                        print(f"[Adapter] Tushare fut_mapping 使用日期: {check_date}")
                        break
                
                if mapping is None or mapping.empty:
                    print(f"[Adapter] Tushare fut_mapping 近10个交易日均为空")

                # 黄金主力: AU.SHF → mapping_ts_code
                gold_rows = mapping[mapping['ts_code'].str.startswith('AU') & ~mapping['ts_code'].str.contains('L')]
                oil_rows  = mapping[mapping['ts_code'].str.startswith('SC') & ~mapping['ts_code'].str.contains('L|TAS')]

                gold_code = gold_rows.iloc[0]['mapping_ts_code'] if not gold_rows.empty else None
                oil_code  = oil_rows.iloc[0]['mapping_ts_code']  if not oil_rows.empty else None

                # 黄金期货日线（查近两年数据，取最后2条）
                if gold_code:
                    df_g = pro.fut_daily(ts_code=gold_code, start_date='20240101', end_date='20500101')
                    if df_g is not None and not df_g.empty and len(df_g) >= 2:
                        df_g = df_g.sort_values('trade_date').tail(2)
                        curr = df_g.iloc[-1]
                        prev = df_g.iloc[-2]
                        curr_price = float(curr['close'])
                        prev_price = float(prev['close'])
                        pct = (curr_price - prev_price) / prev_price * 100 if prev_price else 0
                        # Tushare fut_daily 的 amount 是 万元，×10000 转为元
                        result.append({
                            'name': '黄金',
                            'code': gold_code,
                            'market': '大宗',
                            'price': curr_price,
                            'change_pct': pct,
                            'unit': '元/克',
                            'amount': float(curr.get('amount', 0)) * 10000 if curr.get('amount') else 0,
                            'source': 'Tushare'
                        })

                # 原油期货日线（查近两年数据，取最后2条）
                if oil_code:
                    df_o = pro.fut_daily(ts_code=oil_code, start_date='20240101', end_date='20500101')
                    if df_o is not None and not df_o.empty and len(df_o) >= 2:
                        df_o = df_o.sort_values('trade_date').tail(2)
                        curr = df_o.iloc[-1]
                        prev = df_o.iloc[-2]
                        curr_price = float(curr['close'])
                        prev_price = float(prev['close'])
                        pct = (curr_price - prev_price) / prev_price * 100 if prev_price else 0
                        # Tushare fut_daily 的 amount 是 万元，×10000 转为元
                        result.append({
                            'name': 'WTI原油',
                            'code': oil_code,
                            'market': '大宗',
                            'price': curr_price,
                            'change_pct': pct,
                            'unit': '元/桶',
                            'amount': float(curr.get('amount', 0)) * 10000 if curr.get('amount') else 0,
                            'source': 'Tushare'
                        })

                if result:
                    gold_count = sum(1 for x in result if 'AU' in x.get('code', ''))
                    oil_count = sum(1 for x in result if 'SC' in x.get('code', ''))
                    print(f"[Adapter] 大宗商品 (Tushare): 黄金={gold_count} 原油={oil_count}")

            except Exception as e:
                print(f"[Adapter] Tushare 大宗数据失败: {e}")

        # ── 2. akshare 备用（黄金现货）─────────────────────────
        if not any(r['name'] == '黄金' for r in result):
            try:
                import akshare as ak
                df = ak.spot_golden_benchmark_sge()
                if not df.empty and len(df) >= 2:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    curr_price = float(latest.get('晚盘价', latest.get('早盘价', 0)))
                    prev_price = float(prev.get('晚盘价', prev.get('早盘价', curr_price)))
                    pct = ((curr_price - prev_price) / prev_price * 100) if prev_price > 0 else 0
                    result.append({
                        'name': '黄金', 'code': 'GOLD', 'market': '大宗',
                        'price': curr_price, 'change_pct': pct,
                        'unit': '元/克', 'source': 'SGE'
                    })
            except Exception as e:
                print(f"[Adapter] 黄金(SGE)失败: {e}")

        # ── 3. yfinance WTI 备用（带重试）────────────────────────────────────
        # 重要：先清除代理环境变量，避免 yfinance 请求被代理干扰
        for k in list(os.environ.keys()):
            if "proxy" in k.lower():
                del os.environ[k]
        
        if not any(r['name'] == 'WTI原油' for r in result):
            import yfinance as yf
            for attempt in range(3):
                try:
                    t = yf.Ticker('CL=F')
                    hist = t.history(period='3d', timeout=15)
                    if not hist.empty and len(hist) >= 2:
                        curr = float(hist['Close'].iloc[-1])
                        prev = float(hist['Close'].iloc[-2])
                        pct = ((curr - prev) / prev * 100) if prev > 0 else 0
                        result.append({
                            'name': 'WTI原油', 'code': 'WTI', 'market': '大宗',
                            'price': curr, 'change_pct': pct,
                            'unit': '美元/桶', 'source': 'NYMEX'
                        })
                        print(f"[Adapter] WTI原油 (yfinance): ${curr:.2f} ({pct:+.2f}%)")
                        break
                    else:
                        print(f"[Adapter] WTI原油 yfinance 数据为空，重试 ({attempt+1}/3)")
                except Exception as e:
                    err_str = str(e).lower()
                    if 'rate' in err_str or '429' in err_str or 'too many' in err_str:
                        print(f"[Adapter] WTI原油 yfinance rate limit，重试 ({attempt+1}/3)...")
                        import time
                        time.sleep(3 * (attempt + 1))
                    else:
                        print(f"[Adapter] WTI原油 (yfinance) 失败: {e}")
                        break
            else:
                print(f"[Adapter] WTI原油 获取失败，已达最大重试次数")

        return result

    def get_bond_data(self) -> List[Dict[str, Any]]:
        """获取债券收益率数据（中债、美债），自动回溯最新有效值并计算日变化(bp)"""
        result = []
        try:
            import akshare as ak
            df = ak.bond_zh_us_rate()
            if not df.empty:
                # df 升序排列，取最后两行（含有效数据）
                valid = df.dropna(subset=['中国国债收益率10年', '美国国债收益率10年'])
                if len(valid) >= 2:
                    prev_row = valid.iloc[-2]
                    curr_row = valid.iloc[-1]

                    cn_10y_curr = float(curr_row['中国国债收益率10年'])
                    cn_10y_prev = float(prev_row['中国国债收益率10年'])
                    cn_2y_curr = float(curr_row['中国国债收益率2年']) if pd.notna(curr_row['中国国债收益率2年']) else None
                    cn_change_bp = (cn_10y_curr - cn_10y_prev) * 100  # 收益率差转 bp

                    us_10y_curr = float(curr_row['美国国债收益率10年'])
                    us_10y_prev = float(prev_row['美国国债收益率10年'])
                    us_2y_curr = float(curr_row['美国国债收益率2年']) if pd.notna(curr_row['美国国债收益率2年']) else None
                    us_change_bp = (us_10y_curr - us_10y_prev) * 100

                    result.append({
                        'name': '中国国债(10Y)',
                        'code': 'CNBOND',
                        'market': '债市',
                        'rate_10y': cn_10y_curr,
                        'rate_2y': cn_2y_curr,
                        'change_bp': cn_change_bp,
                        'unit': '%',
                        'source': 'akshare'
                    })
                    result.append({
                        'name': '美国国债(10Y)',
                        'code': 'USBOND',
                        'market': '债市',
                        'rate_10y': us_10y_curr,
                        'rate_2y': us_2y_curr,
                        'change_bp': us_change_bp,
                        'unit': '%',
                        'source': 'akshare'
                    })
        except Exception as e:
            print(f"[Adapter] 债券数据获取失败: {e}")

        return result

    def get_bond_market_review(self) -> str:
        """生成债券市场复盘（中债、美债）"""
        data = self.get_bond_data()

        if not data:
            return "### 债券市场概况\n\n债券数据获取失败。"

        lines = ["### 债券市场概况", ""]

        for item in data:
            rate_10y = item.get('rate_10y', 0)
            rate_2y = item.get('rate_2y')
            name = item['name']
            spread = (rate_10y - rate_2y) if rate_2y is not None else None
            spread_str = f"利差 {spread:.2f}%" if spread is not None else ""
            lines.append(f"- **{name}**：10Y {rate_10y:.4f}% {spread_str}")

        lines.append("")
        lines.append("### 一句话判断")

        cn = next((x for x in data if x['code'] == 'CNBOND'), None)
        us = next((x for x in data if x['code'] == 'USBOND'), None)

        if cn and us:
            spread_cn = (cn['rate_10y'] - cn['rate_2y']) if cn.get('rate_2y') else None
            spread_us = (us['rate_10y'] - us['rate_2y']) if us.get('rate_2y') else None

            if cn['rate_10y'] > us['rate_10y']:
                verdict = f"中债10Y({cn['rate_10y']:.2f}%) > 美债10Y({us['rate_10y']:.2f}%)，中美利差倒挂，人民币汇率承压"
            else:
                verdict = f"美债10Y({us['rate_10y']:.2f}%) > 中债10Y({cn['rate_10y']:.2f}%)，利差趋于正常，汇率压力缓解"
            lines.append(f"- {verdict}")

            if spread_us and spread_cn:
                if spread_us > spread_cn:
                    lines.append(f"- 美债曲线陡峭化程度更大（利差 {spread_us:.2f}% vs {spread_cn:.2f}%）")
                else:
                    lines.append(f"- 中债曲线陡峭化程度更大（利差 {spread_cn:.2f}% vs {spread_us:.2f}%）")
        elif cn:
            lines.append(f"- 中债10Y {cn['rate_10y']:.2f}% 运行")
        elif us:
            lines.append(f"- 美债10Y {us['rate_10y']:.2f}% 运行")

        return "\n".join(lines)

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
