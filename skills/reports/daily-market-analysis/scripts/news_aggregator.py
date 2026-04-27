#!/usr/bin/env python3
"""
新闻聚合模块 - 全球财经新闻
支持：RSS 抓取、Tavily API 搜索、新闻排序
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List
import feedparser


class NewsAggregator:
    """新闻聚合器"""
    
    def __init__(self, tavily_api_key: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.tavily_api_key = tavily_api_key
        
        # RSS 源列表
        self.rss_feeds = {
            "us_stock": [
                "https://finance.yahoo.com/news/rssindex",
                "https://www.cnbc.com/id/100003114/device/rss/rss.html"
            ],
            "china_stock": [
                "http://app.stock.finance.sina.com.cn/rssfeed/stock_news.xml",
                "http://www.cs.com.cn/ssgs/companynews/rss.xml"
            ],
            "hk_stock": [
                "https://www.hkexnews.hk/rss/crrss.xml"
            ],
            "crypto": [
                "https://www.coindesk.com/arcade/rss",
                "https://cointelegraph.com/rss"
            ],
            "commodities": [
                "https://www.investing.com/rss/commodities_news.rss"
            ]
        }
    
    def fetch_rss_news(self, category: str, limit: int = 10) -> List[Dict]:
        """从 RSS 源获取新闻"""
        news_list = []
        
        feeds = self.rss_feeds.get(category, [])
        for feed_url in feeds:
            try:
                response = self.session.get(feed_url, timeout=10)
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries[:limit]:
                    news_list.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.published if hasattr(entry, 'published') else datetime.now().isoformat(),
                        "source": feed.feed.title if hasattr(feed.feed, 'title') else "Unknown",
                        "category": category,
                        "summary": entry.summary if hasattr(entry, 'summary') else ""
                    })
                
                print(f"✅ 获取 {category} RSS 新闻 {len(feed.entries)} 条")
                
            except Exception as e:
                print(f"❌ 获取 RSS {feed_url} 失败：{e}")
        
        return news_list
    
    def search_tavily(self, query: str, limit: int = 5) -> List[Dict]:
        """使用 Tavily API 搜索新闻"""
        if not self.tavily_api_key:
            print("⚠️ Tavily API Key 未配置，跳过搜索")
            return []
        
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "max_results": limit,
                "search_depth": "basic"
            }
            
            response = self.session.post(url, json=payload, timeout=10)
            data = response.json()
            
            news_list = []
            for result in data.get('results', []):
                news_list.append({
                    "title": result.get('title', ''),
                    "link": result.get('url', ''),
                    "published": datetime.now().isoformat(),
                    "source": result.get('title', 'Unknown'),
                    "category": "search",
                    "summary": result.get('content', '')
                })
            
            print(f"✅ Tavily 搜索获取 {len(news_list)} 条新闻")
            return news_list
            
        except Exception as e:
            print(f"❌ Tavily 搜索失败：{e}")
            return []
    
    def rank_news(self, news_list: List[Dict]) -> List[Dict]:
        """新闻排序（按时效性和重要性）"""
        # 简单排序：按时间倒序
        sorted_news = sorted(
            news_list,
            key=lambda x: x.get('published', ''),
            reverse=True
        )
        return sorted_news
    
    def get_top_news(self, category: str, top_n: int = 5) -> List[Dict]:
        """获取指定类别的 Top N 新闻"""
        news_list = self.fetch_rss_news(category, limit=top_n * 2)
        ranked = self.rank_news(news_list)
        return ranked[:top_n]
    
    def get_all_news(self) -> Dict:
        """获取全部类别新闻"""
        print("📰 开始获取新闻...")
        
        result = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "us_stock_top3": self.get_top_news("us_stock", 3),
            "china_stock_top3": self.get_top_news("china_stock", 3),
            "hk_stock_top3": self.get_top_news("hk_stock", 3),
            "crypto_top3": self.get_top_news("crypto", 3),
            "commodities_top3": self.get_top_news("commodities", 3)
        }
        
        print("✅ 新闻获取完成")
        return result


# 测试函数
if __name__ == "__main__":
    aggregator = NewsAggregator()
    news = aggregator.get_all_news()
    
    print("\n" + "="*60)
    print("📰 新闻预览")
    print("="*60)
    
    for category, items in news.items():
        if category == "timestamp":
            continue
        
        print(f"\n{category.replace('_', ' ').title()}:")
        for i, item in enumerate(items[:3], 1):
            print(f"  {i}. {item['title'][:60]}...")
    
    print("\n" + "="*60)
