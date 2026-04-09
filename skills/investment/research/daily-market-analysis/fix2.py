import os

filepath = '/home/pascal/.openclaw/workspace/skills/investment/research/daily-market-analysis/src/new_services/market_data_adapter.py'
with open(filepath, 'r') as f:
    content = f.read()

old = "env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'"
new = "env_path = self._get_project_env_path()"
c1 = content.count(old)
content = content.replace(old, new)
print(f"替换 {c1} 处 daily_stock_analysis env 路径")

old2 = "from dotenv import load_dotenv\n            env_path = '/home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/.env'\n            if os.path.exists(env_path):\n                load_dotenv(env_path)"
new2 = "self._load_env()"
c2 = content.count(old2)
content = content.replace(old2, new2)
print(f"替换 {c2} 处 dotenv load_dotenv 调用")

with open(filepath, 'w') as f:
    f.write(content)
print("完成")
