#!/usr/bin/env python3
"""
每日市场分析报告 - 主入口

生成全球金融市场日报，包括：
- A/H 股、美股、数字货币、大宗商品行情
- 各市场 Top3 热点资讯
- 小 Q 洞察与机会提示

Usage:
    python main.py [--date YYYY-MM-DD] [--output markdown|email] [--debug]
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# 导入模块
from data_fetcher import MarketDataFetcher
from news_aggregator import NewsAggregator
from report_formatter import ReportGenerator


def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        print("⚠️ 配置文件不存在，使用默认配置")
        return get_default_config()
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_default_config():
    """默认配置"""
    return {
        "data_sources": {
            "akshare": {"enabled": True},
            "yfinance": {"enabled": True},
            "binance": {"enabled": True},
            "tavily": {"enabled": False, "api_key": ""}
        },
        "push": {
            "email": {
                "enabled": False,
                "smtp_server": "",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "recipients": []
            }
        },
        "schedule": {
            "timezone": "Asia/Shanghai",
            "time": "08:30",
            "trading_days_only": True
        },
        "watchlist": {
            "stocks": ["600519", "00700", "AAPL", "NVDA"],
            "crypto": ["BTC", "ETH", "BNB", "SOL"]
        }
    }


def send_email(report: str, config: dict):
    """发送邮件报告"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    email_config = config.get("push", {}).get("email", {})
    
    if not email_config.get("enabled"):
        print("⚠️ 邮件推送未启用")
        return False
    
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = email_config['username']
        msg['To'] = ", ".join(email_config['recipients'])
        msg['Subject'] = f"📈 每日市场研究报告 - {datetime.now().strftime('%Y-%m-%d')}"
        
        # 添加报告内容
        msg.attach(MIMEText(report, 'plain', 'utf-8'))
        
        # 发送邮件
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        server.starttls()
        server.login(email_config['username'], email_config['password'])
        server.send_message(msg)
        server.quit()
        
        print("✅ 邮件推送成功")
        return True
        
    except Exception as e:
        print(f"❌ 邮件推送失败：{e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="每日市场分析报告生成器")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="报告日期 (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, choices=["markdown", "email", "both"],
                        default="markdown", help="输出方式")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    
    args = parser.parse_args()
    
    print(f"🚀 开始生成 {args.date} 的市场报告...")
    print("=" * 60)
    
    # 加载配置
    config = load_config()
    
    # 1. 获取市场数据
    print("\n📊 步骤 1/3: 获取市场数据...")
    fetcher = MarketDataFetcher()
    market_data = fetcher.get_all_market_data()
    
    # 2. 获取新闻
    print("\n📰 步骤 2/3: 获取新闻资讯...")
    tavily_key = config.get("data_sources", {}).get("tavily", {}).get("api_key", "")
    aggregator = NewsAggregator(tavily_api_key=tavily_key)
    news = aggregator.get_all_news()
    
    # 3. 生成报告
    print("\n📝 步骤 3/3: 生成报告...")
    generator = ReportGenerator()
    report = generator.generate_full_report(market_data, news)
    
    # 保存报告
    output_dir = Path(__file__).parent.parent / "reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"daily_report_{args.date}.md"
    generator.save_report(report, output_path)
    
    # 邮件推送
    if args.output in ["email", "both"]:
        print("\n📧 发送邮件...")
        send_email(report, config)
    
    print("\n" + "=" * 60)
    print("✅ 报告生成完成！")
    print(f"📁 保存位置：{output_path}")
    print("=" * 60)
    
    # 打印预览
    if args.debug:
        print("\n📋 报告预览:")
        print(report[:1000])


if __name__ == "__main__":
    main()
