#!/usr/bin/env python3
"""
报告生成模块 - 生成 Markdown 格式市场日报
"""

from datetime import datetime
from typing import Dict, List


class ReportGenerator:
    """市场日报生成器"""
    
    def __init__(self):
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.weekday = self._get_weekday()
    
    def _get_weekday(self) -> str:
        """获取星期几"""
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return weekdays[datetime.now().weekday()]
    
    def format_market_data(self, data: Dict) -> str:
        """格式化市场数据"""
        lines = []
        lines.append("## 🌍 一、全球市场概览\n")
        
        # A 股
        if data.get("a_stock"):
            lines.append("### A 股")
            lines.append("| 指数 | 收盘 | 涨跌 |")
            lines.append("|------|------|------|")
            for name, info in data["a_stock"].items():
                lines.append(f"| {name} | {info['收盘']:.2f} | {info['涨跌']:+.2f}% |")
            lines.append("")
        
        # 港股
        if data.get("hk_stock"):
            lines.append("### 港股")
            lines.append("| 指数 | 收盘 | 涨跌 |")
            lines.append("|------|------|------|")
            for name, info in data["hk_stock"].items():
                lines.append(f"| {name} | {info['收盘']:.2f} | {info['涨跌']:+.2f}% |")
            lines.append("")
        
        # 美股
        if data.get("us_stock"):
            lines.append("### 美股")
            lines.append("| 指数 | 收盘 | 涨跌 |")
            lines.append("|------|------|------|")
            for name, info in data["us_stock"].items():
                lines.append(f"| {name} | {info['收盘']:.2f} | {info['涨跌']:+.2f}% |")
            lines.append("")
        
        # 数字货币
        if data.get("crypto"):
            lines.append("### 数字货币")
            lines.append("| 币种 | 价格 | 24h 涨跌 |")
            lines.append("|------|------|----------|")
            for name, info in data["crypto"].items():
                lines.append(f"| {name} | ${info['价格']:.2f} | {info['24h 涨跌']:+.2f}% |")
            lines.append("")
        
        # 大宗商品
        if data.get("commodities"):
            lines.append("### 大宗商品")
            lines.append("| 商品 | 价格 | 涨跌 |")
            lines.append("|------|------|------|")
            for name, info in data["commodities"].items():
                lines.append(f"| {name} | ${info['价格']:.2f} | {info['涨跌']:+.2f}% |")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_news(self, news: Dict) -> str:
        """格式化新闻"""
        lines = []
        lines.append("## 📰 二、各市场 Top3 热点资讯\n")
        
        category_names = {
            "us_stock_top3": "### 美股 Top3",
            "china_stock_top3": "### A 股 Top3",
            "hk_stock_top3": "### 港股 Top3",
            "crypto_top3": "### 数字货币 Top3",
            "commodities_top3": "### 大宗商品 Top3"
        }
        
        for key, title in category_names.items():
            items = news.get(key, [])
            if items:
                lines.append(title)
                lines.append("")
                for i, item in enumerate(items, 1):
                    lines.append(f"{i}. **{item['title']}**")
                    if item.get('summary'):
                        summary = item['summary'][:100] + "..." if len(item['summary']) > 100 else item['summary']
                        lines.append(f"   - {summary}")
                    lines.append(f"   - [来源]({item['link']})")
                    lines.append("")
        
        return "\n".join(lines)
    
    def format_insights(self, market_data: Dict, news: Dict) -> str:
        """生成小 Q 洞察"""
        lines = []
        lines.append("## 💡 三、小 Q 洞察与机会提示\n")
        
        # 简单洞察逻辑（后续可用 AI 增强）
        lines.append("### 重点关注")
        
        if market_data.get("crypto"):
            btc = market_data["crypto"].get("BTC", {})
            if btc.get("24h 涨跌", 0) > 5:
                lines.append("- 💰 比特币大涨超过 5%，关注能否站稳关键阻力位")
            elif btc.get("24h 涨跌", 0) < -5:
                lines.append("- ⚠️ 比特币大跌超过 5%，注意风险控制")
        
        if market_data.get("us_stock"):
            nasdaq = market_data["us_stock"].get("纳斯达克", {})
            if nasdaq.get("涨跌", 0) > 2:
                lines.append("- 📈 纳斯达克大涨，科技股情绪高涨")
            elif nasdaq.get("涨跌", 0) < -2:
                lines.append("- 📉 纳斯达克大跌，注意科技股回调风险")
        
        lines.append("")
        lines.append("### 风险提示")
        lines.append("- ⚠️ 市场有风险，投资需谨慎")
        lines.append("- ⚠️ 以上分析仅供参考，不构成投资建议")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_full_report(self, market_data: Dict, news: Dict) -> str:
        """生成完整报告"""
        header = f"""# 📈 每日市场研究报告

**日期：** {self.date} {self.weekday}
**生成时间：** {datetime.now().strftime("%H:%M")} CST
**数据来源：** AKShare, YFinance, Binance, RSS Feeds

---

"""
        
        sections = [
            header,
            self.format_market_data(market_data),
            self.format_news(news),
            self.format_insights(market_data, news),
            "\n---\n",
            "_小 Q 备注：市场永远是对的，但我们可以更聪明。数据是基础，判断是价值，执行是关键。_\n"
        ]
        
        return "\n".join(sections)
    
    def save_report(self, report: str, output_path: str = None):
        """保存报告到文件"""
        if not output_path:
            output_path = f"reports/daily_report_{self.date}.md"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 报告已保存：{output_path}")
        return output_path


# 测试函数
if __name__ == "__main__":
    generator = ReportGenerator()
    
    # 测试数据
    test_market_data = {
        "a_stock": {"上证指数": {"收盘": 3250.0, "涨跌": 0.5}},
        "crypto": {"BTC": {"价格": 68500.0, "24h 涨跌": 2.3}}
    }
    test_news = {"us_stock_top3": []}
    
    report = generator.generate_full_report(test_market_data, test_news)
    print(report[:500])
