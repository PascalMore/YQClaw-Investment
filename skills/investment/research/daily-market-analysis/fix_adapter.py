"""修复 market_data_adapter.py 中的 env 路径问题"""
import os

filepath = '/home/pascal/.openclaw/workspace/skills/investment/research/daily-market-analysis/src/new_services/market_data_adapter.py'
with open(filepath, 'r') as f:
    content = f.read()

# 修复1: _load_env 重复定义 + 国际新闻重复定义 → 合并为一个
old_block = """    def _load_env(self):
        \"\"\"加载环境变量\"\"\"
        env_file = '/home/pascal/.openclaw/workspace/skills/investment/research/daily-stock-analysis/.env'
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k] = v

    def _load_env(self):
        \"\"\"加载环境变量\"\"\"
        env_file = '/home/pascal/.openclaw/workspace/skills/investment/research/daily-stock-analysis/.env'
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k] = v

    def get_global_news(self, limit: int = 3) -> List[Dict[str, str]]:
        \"\"\"获取全球宏观热点新闻 - 使用 MiniMax Search\"\"\"
        return self.get_international_news(\"global\", limit)
    

    def get_international_news(self, category: str = \"global\", limit: int = 3) -> List[Dict[str, str]]:
        \"\"\"获取国际热点新闻 - 使用 MiniMax Search
        
        Args:
            category: \"global\" | \"crypto\" | \"us\"
            limit: 返回条数
        \"\"\"
        # 清除代理环境变量
        for k in list(os.environ.keys()):
            if \"proxy\" in k.lower():
                del os.environ[k]
        
        # 加载 .env 配置
        try:
            from dotenv import load_dotenv
            env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'
            if os.path.exists(env_path):
                load_dotenv(env_path)
        except Exception as e:
            print(f\"[Adapter] dotenv 加载失败: {e}\")
        
        category_keywords = {
            \"global\": \"Federal Reserve interest rate cut inflation economy news April 2026\",
            \"crypto\": \"Bitcoin price Ethereum ETF crypto market news today April 2026\",
            \"us\": \"S&P 500 Nasdaq Dow Jones stock market news today April 2026\"
        }
        
        keyword = category_keywords.get(category, category_keywords[\"global\"])
        
        # 直接调用 MiniMax API
        minimax_key = os.environ.get(\"LLM_MINIMAX_API_KEYS\", \"\").split(\",\")[0] if os.environ.get(\"LLM_MINIMAX_API_KEYS\") else \"\"
        if not minimax_key:
            minimax_key = os.environ.get(\"MINIMAX_API_KEY\", \"\")
        
        if minimax_key:
            try:
                import requests
                headers = {
                    'Authorization': f'Bearer {minimax_key}',
                    'Content-Type': 'application/json',
                    'MM-API-Source': 'Minimax-MCP',
                }
                payload = {\"q\": keyword}
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
                                \"title\": title,
                                \"content\": item.get('snippet', title),
                                \"source\": \"MiniMax\",
                                \"datetime\": \"\",
                                \"url\": item.get('url', '')
                            })
                    if results:
                        print(f\"[Adapter] {category} 国际新闻 (MiniMax): {len(results)} 条\")
                        return results
            except Exception as e:
                print(f\"[Adapter] MiniMax 失败: {e}\")
        
        print(f\"[Adapter] {category} 国际新闻: 获取失败\")
        return []
    

    def get_international_news(self, category: str = \"global\", limit: int = 3) -> List[Dict[str, str]]:
        \"\"\"获取国际热点新闻 - 使用 MiniMax Search\"\"\"
        # 清除代理
        for k in list(os.environ.keys()):
            if \"proxy\" in k.lower():
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
            \"global\": \"Federal Reserve interest rate economy news April 2026\",
            \"crypto\": \"Bitcoin Ethereum crypto market news April 2026\",
            \"us\": \"S&P 500 Nasdaq Dow stock market news April 2026\"
        }
        
        keyword = keywords.get(category, keywords[\"global\"])
        minimax_key = os.environ.get(\"LLM_MINIMAX_API_KEYS\", \"\").split(\",\")[0] if os.environ.get(\"LLM_MINIMAX_API_KEYS\") else \"\"
        
        if minimax_key:
            try:
                import requests
                headers = {'Authorization': f'Bearer {minimax_key}', 'Content-Type': 'application/json', 'MM-API-Source': 'Minimax-MCP'}
                resp = requests.post('https://api.minimaxi.com/v1/coding_plan/search', headers=headers, json={\"q\": keyword}, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    seen = set()
                    for item in data.get('organic', [])[:limit]:
                        title = item.get('title', '').strip()
                        if title and title not in seen:
                            seen.add(title)
                            results.append({\"title\": title, \"content\": item.get('snippet', title), \"source\": \"MiniMax\", \"datetime\": \"\", \"url\": item.get('url', '')})
                    if results:
                        print(f\"[Adapter] {category} 国际新闻 (MiniMax): {len(results)} 条\")
                        return results
            except Exception as e:
                print(f\"[Adapter] MiniMax 失败: {e}\")
        
        print(f\"[Adapter] {category} 国际新闻: 获取失败\")
        return []"""

new_block = """    def _get_project_env_path(self) -> str:
        \"\"\"获取本项目 .env 文件路径\"\"\"
        current = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current))
        return os.path.join(project_root, '.env')
    
    def _load_env(self):
        \"\"\"加载本项目 .env（代理 + API Keys）\"\"\"
        env_file = self._get_project_env_path()
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k] = v

    def get_global_news(self, limit: int = 3) -> List[Dict[str, str]]:
        \"\"\"获取全球宏观热点新闻 - 使用 MiniMax Search\"\"\"
        return self.get_international_news(\"global\", limit)
    
    def get_international_news(self, category: str = \"global\", limit: int = 3) -> List[Dict[str, str]]:
        \"\"\"获取国际热点新闻 - 使用 MiniMax Search\"\"\"
        for k in list(os.environ.keys()):
            if \"proxy\" in k.lower():
                del os.environ[k]
        self._load_env()
        
        keywords = {
            \"global\": \"Federal Reserve interest rate economy news April 2026\",
            \"crypto\": \"Bitcoin Ethereum crypto market news April 2026\",
            \"us\": \"S&P 500 Nasdaq Dow stock market news April 2026\"
        }
        keyword = keywords.get(category, keywords[\"global\"])
        minimax_key = os.environ.get(\"LLM_MINIMAX_API_KEYS\", \"\").split(\",\")[0] if os.environ.get(\"LLM_MINIMAX_API_KEYS\") else \"\"
        if not minimax_key:
            minimax_key = os.environ.get(\"MINIMAX_API_KEY\", \"\")
        
        if minimax_key:
            try:
                import requests
                headers = {'Authorization': f'Bearer {minimax_key}', 'Content-Type': 'application/json', 'MM-API-Source': 'Minimax-MCP'}
                resp = requests.post('https://api.minimaxi.com/v1/coding_plan/search', headers=headers, json={\"q\": keyword}, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    seen = set()
                    for item in data.get('organic', [])[:limit]:
                        title = item.get('title', '').strip()
                        if title and title not in seen:
                            seen.add(title)
                            results.append({\"title\": title, \"content\": item.get('snippet', title), \"source\": \"MiniMax\", \"datetime\": \"\", \"url\": item.get('url', '')})
                    if results:
                        print(f\"[Adapter] {category} 国际新闻 (MiniMax): {len(results)} 条\")
                        return results
            except Exception as e:
                print(f\"[Adapter] MiniMax 失败: {e}\")
        print(f\"[Adapter] {category} 国际新闻: 获取失败\")
        return []"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("✅ 替换成功：_load_env + 国际新闻重复定义块")
else:
    print("❌ 未找到目标块")

# 修复2: get_crypto_data 中的 _load_env 调用也改成 self._load_env()
# 先检查有多少处残留的 daily_stock_analysis .env 路径
for old, new in [
    ("env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'", "env_path = self._get_project_env_path()"),
    ("from dotenv import load_dotenv\n            env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'\n            if os.path.exists(env_path):\n                load_dotenv(env_path)", "self._load_env()"),
]:
    if old in content:
        content = content.replace(old, new)
        print(f"✅ 替换残留路径: {old[:60]}...")

with open(filepath, 'w') as f:
    f.write(content)

print("文件已保存")
