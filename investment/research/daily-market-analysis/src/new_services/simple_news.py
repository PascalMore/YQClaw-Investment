# Simple news adapter using Tavily API directly
import os
import requests
import json

def search_news(query: str, limit: int = 5) -> list:
    """Direct Tavily API call for news search"""
    tavily_keys = os.environ.get('TAVILY_API_KEYS', '')
    if not tavily_keys:
        return []
    
    api_key = tavily_keys.split(',')[0].strip()
    
    try:
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        data = json.dumps({
            'query': query,
            'search_depth': 'basic',
            'max_results': limit
        })
        
        resp = requests.post(
            'https://api.tavily.com/search',
            headers=headers,
            data=data,
            timeout=10
        )
        
        if resp.status_code == 200:
            result = resp.json()
            results = result.get('results', [])
            news = []
            for r in results[:limit]:
                news.append({
                    'title': r.get('title', ''),
                    'source': r.get('source', ''),
                    'url': r.get('url', ''),
                    'time': r.get('published_date', '')
                })
            return news
    except Exception as e:
        print(f"Tavily error: {e}")
    return []
