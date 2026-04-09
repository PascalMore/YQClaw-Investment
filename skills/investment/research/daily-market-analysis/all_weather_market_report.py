# -*- coding: utf-8 -*-
"""
全天候市场报告 - All Weather Market Report
"""

import os
import sys
from datetime import datetime, date
from typing import Dict, List, Optional

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_CURRENT_DIR, 'src'))
sys.path.insert(0, os.path.join(_CURRENT_DIR, 'src', 'new_services'))

INITIAL_ALLOCATION = {
    "A+H股": 0.53,
    "美股": 0.18,
    "中债": 0.18,
    "数字货币": 0.05,
    "大宗商品": 0.03,
    "美债": 0.03,
}


class AllWeatherMarketReport:
    def __init__(self, config=None):
        self.config = config
        self.report_date = date.today()
        self.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M CST")
        self.initial_allocation = INITIAL_ALLOCATION.copy()
        self._data_adapter = None
        self._cn_review = None
        self._us_review = None
        self._hk_review = None
        self._crypto_review = None
    
    @property
    def data_adapter(self):
        if self._data_adapter is None:
            from new_services import get_market_adapter
            self._data_adapter = get_market_adapter(self.config)
        return self._data_adapter
    
    def generate(self) -> str:
        self._fetch_reviews()
        
        sections = [
            self._generate_header(),
            self._generate_market_overview(),
            self._generate_hot_news(),
            self._generate_market_reviews(),
            self._generate_financial_calendar(),
            self._generate_insights(),
        ]
        return "\n\n".join(filter(None, sections))
    
    def _fetch_reviews(self):
        self._cn_review = self._get_cn_review()
        self._us_review = self._get_us_review()
        self._hk_review = self.data_adapter.get_hk_market_review()
        self._crypto_review = self.data_adapter.get_crypto_market_review()
    
    def _generate_header(self) -> str:
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][self.report_date.weekday()]
        return f"""# 📈 每日全球市场研究报告

**日期：** {self.report_date} {weekday}  
**生成时间：** {self.generated_at}"""
    
    def _summarize_review(self, review_text: str, max_sentences: int = 5) -> str:
        if not review_text:
            return "数据获取中..."
        
        lines = [l.strip() for l in review_text.split('\n') if l.strip()]
        key_points = []
        skip_keywords = ['#', '---', '**', '##', '```', '>>>']
        
        for line in lines:
            if any(kw in line for kw in skip_keywords):
                continue
            if len(line) < 15 or len(line) > 250:
                continue
            if line.startswith('- ') or line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                if len(line) > 50:
                    key_points.append(line)
            else:
                key_points.append(line)
            
            if len(key_points) >= max_sentences:
                break
        
        if len(key_points) < 3:
            for line in lines[len(lines)//3:len(lines)*2//3]:
                if line not in key_points and len(line) > 30:
                    key_points.append(line)
                    if len(key_points) >= max_sentences:
                        break
        
        if key_points:
            result = '；'.join(key_points[:max_sentences])
            result = result.replace('**', '').replace('- ', '').strip()
            return result if len(result) > 20 else "市场数据收集中..."
        return "市场数据获取中..."
    
    def _generate_market_overview(self) -> str:
        alloc_lines = " | ".join([f"{k} {int(v*100)}%" for k, v in self.initial_allocation.items()])
        
        cn_indices = self._get_cn_indices()
        hk_indices = self._get_hk_indices()
        us_indices = self._get_us_indices()
        crypto_data = self._get_crypto_data()
        
        cn_analysis = self._summarize_review(self._cn_review, 5) if self._cn_review else "数据获取中..."
        us_analysis = self._summarize_review(self._us_review, 5) if self._us_review else "数据获取中..."
        hk_analysis = self._summarize_review(self._hk_review, 3) if self._hk_review else "港股数据获取中..."
        crypto_analysis = self._get_crypto_analysis(crypto_data)
        
        shanghai = self._find_index(cn_indices, ["上证指数", "000001"])
        hs300 = self._find_index(cn_indices, ["沪深300", "000300", "HS300"])
        hsi = self._find_index(hk_indices, ["恒生指数", "HSI"])
        hstech = self._find_index(hk_indices, ["恒生科技", "HSTECH"])
        spx = self._find_index(us_indices, ["标普", "SPX", "S&P"])
        nasdaq = self._find_index(us_indices, ["纳斯达克", "NDX", "NASDAQ"])
        
        rows = []
        
        # A 股：上证指数
        if shanghai:
            emoji = self._emoji(shanghai.get('change_pct', 0))
            price = shanghai.get('current', shanghai.get('price', 0))
            change = shanghai.get('change_pct', 0)
            rows.append(f"| 上证指数 | {emoji} {price:.2f} | {change:+.2f}% | {cn_analysis} | 标配 40% | 核心资产 |")
        else:
            rows.append(f"| 上证指数 | ⚪ — | — | {cn_analysis} | 标配 40% | 核心资产 |")
        
        # A 股：沪深300（重复分析）
        if hs300:
            emoji = self._emoji(hs300.get('change_pct', 0))
            price = hs300.get('current', hs300.get('price', 0))
            change = hs300.get('change_pct', 0)
            rows.append(f"| 沪深300 | {emoji} {price:.2f} | {change:+.2f}% | {cn_analysis} | 标配 40% | 核心资产 |")
        else:
            rows.append(f"| 沪深300 | ⚪ — | — | {cn_analysis} | 标配 40% | 核心资产 |")
        
        # 港股：恒生指数
        if hsi:
            emoji = self._emoji(hsi.get('change_pct', 0))
            price = hsi.get('current', hsi.get('price', 0))
            change = hsi.get('change_pct', 0)
            rows.append(f"| 恒生指数 | {emoji} {price:.2f} | {change:+.2f}% | {hk_analysis} | 低配 15% | 南向待观察 |")
        else:
            rows.append(f"| 恒生指数 | ⚪ — | — | {hk_analysis} | 低配 15% | 南向待观察 |")
        
        # 港股：恒生科技（重复分析）
        if hstech:
            emoji = self._emoji(hstech.get('change_pct', 0))
            price = hstech.get('current', hstech.get('price', 0))
            change = hstech.get('change_pct', 0)
            rows.append(f"| 恒生科技 | {emoji} {price:.2f} | {change:+.2f}% | {hk_analysis} | 低配 15% | 南向待观察 |")
        else:
            rows.append(f"| 恒生科技 | ⚪ — | — | {hk_analysis} | 低配 15% | 南向待观察 |")
        
        # 美股：标普500
        if spx:
            emoji = self._emoji(spx.get('change_pct', 0))
            price = spx.get('current', spx.get('price', 0))
            change = spx.get('change_pct', 0)
            rows.append(f"| 标普500 | {emoji} {price:.2f} | {change:+.2f}% | {us_analysis} | 标配 20% | 估值偏高 |")
        else:
            rows.append(f"| 标普500 | ⚪ — | — | {us_analysis} | 标配 20% | 估值偏高 |")
        
        # 美股：纳斯达克（重复分析）
        if nasdaq:
            emoji = self._emoji(nasdaq.get('change_pct', 0))
            price = nasdaq.get('current', nasdaq.get('price', 0))
            change = nasdaq.get('change_pct', 0)
            rows.append(f"| 纳斯达克 | {emoji} {price:.2f} | {change:+.2f}% | {us_analysis} | 标配 20% | 估值偏高 |")
        else:
            rows.append(f"| 纳斯达克 | ⚪ — | — | {us_analysis} | 标配 20% | 估值偏高 |")
        
        # BTC
        btc = self._find_crypto(crypto_data, ["BTC", "比特币"])
        if btc:
            emoji = self._emoji(btc.get('change_pct', 0))
            price = btc.get('price', 0)
            change = btc.get('change_pct', 0)
            if price >= 1000:
                price_str = f"${price:,.0f}"
            else:
                price_str = f"${price:,.2f}"
            rows.append(f"| BTC | {emoji} {price_str} | {change:+.2f}% | {crypto_analysis} | 超配 10% | ETF净流入 |")
        else:
            rows.append(f"| BTC | ⚪ — | — | {crypto_analysis} | 超配 10% | ETF净流入 |")
        
        # 黄金/原油/债券占位
        rows.append(f"| 黄金 | ⚪ — | — | 待接入 | 标配 5% | — |")
        rows.append(f"| WTI原油 | ⚪ — | — | 待接入 | 低配 3% | — |")
        rows.append(f"| 美债10Y | ⚪ — | — | 待接入 | 标配 3% | — |")
        rows.append(f"| 中债10Y | ⚪ — | — | 待接入 | 超配 5% | — |")
        
        table = f"""## 一、全球市场概览

📊 **初始配置比例：** {alloc_lines}

| 市场 | 最新价 | 涨跌幅 | 市场分析 | 仓位建议 | 理由 |
|------|--------|--------|----------|----------|------|
"""
        table += '\n'.join(rows)
        
        return table
    
    def _emoji(self, value) -> str:
        if value > 0:
            return "🟢"
        elif value < 0:
            return "🔴"
        else:
            return "⚪"
    
    def _get_crypto_analysis(self, crypto_data: List[Dict]) -> str:
        if not crypto_data:
            return "数据获取中..."
        
        btc = self._find_crypto(crypto_data, ["BTC", "比特币"])
        if not btc:
            return "数据获取中..."
        
        change = btc.get('change_pct', 0)
        if change > 5:
            return "BTC 强势突破，市场 FOMO 情绪升温"
        elif change > 2:
            return "BTC 震荡偏强，市场情绪乐观"
        elif change > 0:
            return "BTC 小幅上涨，趋势偏多"
        elif change < -5:
            return "BTC 大幅回调，注意风险控制"
        elif change < -2:
            return "BTC 震荡偏弱，市场情绪谨慎"
        elif change < 0:
            return "BTC 小幅下跌，观望情绪浓厚"
        else:
            return "BTC 横盘整理，等待方向选择"
    
    def _find_index(self, indices: List[Dict], names: List[str]) -> Optional[Dict]:
        for idx in indices:
            name = idx.get('name', '')
            code = idx.get('code', '')
            for target in names:
                if target in name or target in code:
                    return idx
        return indices[0] if indices else None
    
    def _find_crypto(self, crypto_data: List[Dict], symbols: List[str]) -> Optional[Dict]:
        for c in crypto_data:
            sym = c.get('symbol', '')
            name = c.get('name', '')
            for target in symbols:
                if target in sym or target in name:
                    return c
        return crypto_data[0] if crypto_data else None
    
    def _get_cn_indices(self) -> List[Dict]:
        try:
            return self.data_adapter.get_cn_index_data()
        except:
            return []
    
    def _get_hk_indices(self) -> List[Dict]:
        try:
            return self.data_adapter.get_hk_index_data()
        except:
            return []
    
    def _get_us_indices(self) -> List[Dict]:
        try:
            return self.data_adapter.get_us_index_data()
        except:
            return []
    
    def _get_crypto_data(self) -> List[Dict]:
        try:
            return self.data_adapter.get_crypto_data()
        except:
            return []
    
    def _generate_hot_news(self) -> str:
        global_news = self.data_adapter.get_global_news(limit=3)
        cn_news = self.data_adapter.get_market_news("cn", limit=3)
        hk_news = self.data_adapter.get_market_news("hk", limit=3)
        us_news = self.data_adapter.get_market_news("us", limit=3)
        crypto_news = self.data_adapter.get_market_news("crypto", limit=3)
        commodity_news = self.data_adapter.get_market_news("commodity", limit=3)
        
        lines = ["## 二、热点资讯 Top 3 (过去24小时)", ""]
        
        lines.append("### 🌍 全球宏观影响力")
        if global_news:
            for i, news in enumerate(global_news[:3], 1):
                title = news.get('title', '无标题')
                source = news.get('source', '未知来源')
                lines.append(f"{i}. **{title}**")
                lines.append(f"   → 来源：{source}")
        else:
            lines.append("1. 【待接入】")
            lines.append("2. 【待接入】")
            lines.append("3. 【待接入】")
        
        lines.append("")
        lines.append("### 🇨🇳 A 股市场")
        if cn_news:
            for i, news in enumerate(cn_news[:3], 1):
                lines.append(f"{i}. {news.get('title', '—')}")
        else:
            lines.append("1. 【待接入】")
            lines.append("2. 【待接入】")
            lines.append("3. 【待接入】")
        
        lines.append("")
        lines.append("### 🇭🇰 港股市场")
        if hk_news:
            for i, news in enumerate(hk_news[:3], 1):
                lines.append(f"{i}. {news.get('title', '—')}")
        else:
            lines.append("1. 【待接入】")
            lines.append("2. 【待接入】")
            lines.append("3. 【待接入】")
        
        lines.append("")
        lines.append("### 🇺🇸 美股市场")
        if us_news:
            for i, news in enumerate(us_news[:3], 1):
                lines.append(f"{i}. {news.get('title', '—')}")
        else:
            lines.append("1. 【待接入】")
            lines.append("2. 【待接入】")
            lines.append("3. 【待接入】")
        
        lines.append("")
        lines.append("### ₿ 数字货币")
        if crypto_news:
            for i, news in enumerate(crypto_news[:3], 1):
                lines.append(f"{i}. {news.get('title', '—')}")
        else:
            lines.append("1. 【待接入】")
            lines.append("2. 【待接入】")
            lines.append("3. 【待接入】")
        
        lines.append("")
        lines.append("### 🥇 大宗商品")
        if commodity_news:
            for i, news in enumerate(commodity_news[:3], 1):
                lines.append(f"{i}. {news.get('title', '—')}")
        else:
            lines.append("1. 【待接入】")
            lines.append("2. 【待接入】")
            lines.append("3. 【待接入】")
        
        return "\n".join(lines)


    def _generate_market_reviews(self) -> str:
        sections = ["## 三、各市场复盘", ""]
        
        sections.append("### 3.1 A 股市场复盘")
        sections.append(self._cn_review if self._cn_review else "[获取失败]")
        sections.append("")
        
        sections.append("### 3.2 美股市场复盘")
        sections.append(self._us_review if self._us_review else "[获取失败]")
        sections.append("")
        
        sections.append("### 3.3 港股市场复盘")
        sections.append(self._hk_review if self._hk_review else "[获取失败]")
        sections.append("")
        
        sections.append("### 3.4 数字货币市场复盘")
        sections.append(self._crypto_review if self._crypto_review else "[获取失败]")
        sections.append("")
        
        sections.append("### 3.5 大宗商品市场复盘")
        sections.append(self.data_adapter.get_commodity_market_review())
        sections.append("")
        
        sections.append("### 3.6 债券市场复盘")
        sections.append(self.data_adapter.get_bond_market_review())
        
        return "\n".join(sections)
    
    def _get_cn_review(self) -> Optional[str]:
        try:
            review = self.data_adapter.get_cn_market_review()
            if review:
                lines = review.split('\n')
                result_lines = []
                skip_title = True
                for line in lines:
                    if skip_title and line.startswith('#'):
                        continue
                    skip_title = False
                    result_lines.append(line)
                return '\n'.join(result_lines).strip()
            return None
        except Exception as e:
            print(f"[Report] A 股复盘获取失败：{e}")
            return None
    
    def _get_us_review(self) -> Optional[str]:
        try:
            review = self.data_adapter.get_us_market_review()
            if review:
                lines = review.split('\n')
                result_lines = []
                skip_title = True
                for line in lines:
                    if skip_title and line.startswith('#'):
                        continue
                    skip_title = False
                    result_lines.append(line)
                return '\n'.join(result_lines).strip()
            return None
        except Exception as e:
            print(f"[Report] 美股复盘获取失败：{e}")
            return None
    
    def _generate_financial_calendar(self) -> str:
        calendar = self.data_adapter.get_financial_calendar(days=30)
        if calendar:
            lines = ["| 日期 | 事件 | 市场 | 预期影响 |", "|------|------|------|----------|"]
            for event in calendar:
                lines.append(f"| {event.get('date', '-')} | {event.get('event', '-')} | {event.get('market', '-')} | {event.get('impact', '-')} |")
            table = "\n".join(lines)
        else:
            table = "| 日期 | 事件 | 市场 | 预期影响 |\n|------|------|------|----------|\n| — | 金融日历数据待接入 | — | — |"
        
        return f"## 四、金融日历\n\n{table}"
    
    def _generate_insights(self) -> str:
        return """## 五、小Q洞察

🎯 **今日核心判断：**
- 风险偏好：—
- 重点关注：—

💡 **机会提示：**
1. —

⚠️ **风险提示：**
1. —

📋 **操作建议：**
| 操作 | 标的 | 理由 |
|------|------|------|
| — | — | — |

---
*本报告仅供参考，不构成投资建议。*"""


def generate_report() -> str:
    report = AllWeatherMarketReport()
    return report.generate()


def main():
    print("正在生成每日市场报告...")
    print("=" * 60)
    report = generate_report()
    print(report)
    print("=" * 60)
    print(f"报告生成完成，长度：{len(report)} 字符")


if __name__ == "__main__":
    main()



def generate_html_report(report: str, config: dict, report_date: str) -> str:
    """生成移动端友好的HTML格式报告"""
    
    # 完整的移动端优化样式
    html_head = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>每日全球市场报告 - """ + report_date + """</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', Helvetica, Arial, sans-serif; 
            background: #f5f7fa; 
            color: #333; 
            line-height: 1.6;
            padding: 0;
            margin: 0;
        }
        .report-card {
            background: #fff;
            border-radius: 16px;
            margin: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        .report-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2c5282 100%);
            color: #fff;
            padding: 16px 20px;
        }
        .report-header h1 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .report-header .subtitle {
            font-size: 12px;
            opacity: 0.85;
        }
        .table-wrapper {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .market-table {
            width: 100%;
            min-width: 600px;
            border-collapse: collapse;
            font-size: 13px;
        }
        .market-table th {
            background: #f8fafc;
            color: #666;
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #e2e8f0;
            white-space: nowrap;
        }
        .market-table td {
            padding: 14px;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: middle;
        }
        .market-table tr:last-child td {
            border-bottom: none;
        }
        .market-name {
            font-weight: 600;
            color: #1a202c;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .market-name .icon {
            font-size: 16px;
        }
        .price {
            font-weight: 700;
            font-size: 15px;
            color: #1e3c72;
            font-family: 'SF Mono', 'Menlo', Monaco, monospace;
            white-space: nowrap;
            text-align: right;
        }
        .change {
            text-align: center;
        }
        .change-up {
            background: linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%);
            color: #c53030;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            display: inline-block;
            white-space: nowrap;
        }
        .change-down {
            background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
            color: #276749;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            display: inline-block;
            white-space: nowrap;
        }
        .change-neutral {
            background: #f7f7f7;
            color: #999;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 13px;
            display: inline-block;
            white-space: nowrap;
        }
        .volume {
            color: #666;
            font-size: 12px;
            white-space: nowrap;
            text-align: right;
        }
        .analysis {
            color: #555;
            font-size: 12px;
            line-height: 1.5;
            max-width: 200px;
            word-break: break-word;
        }
        .section {
            padding: 16px 20px;
            border-bottom: 1px solid #f0f0f0;
        }
        .section:last-child {
            border-bottom: none;
        }
        .section-title {
            font-size: 15px;
            font-weight: 600;
            color: #1e3c72;
            margin-bottom: 12px;
        }
        .news-item {
            padding: 10px 0;
            border-bottom: 1px dashed #eee;
        }
        .news-item:last-child {
            border-bottom: none;
        }
        .news-title {
            font-size: 13px;
            color: #333;
            line-height: 1.5;
            margin-bottom: 4px;
        }
        .news-source {
            font-size: 11px;
            color: #999;
        }
        .footer {
            text-align: center;
            padding: 16px;
            color: #999;
            font-size: 11px;
        }
    </style>
</head>
<body>"""
    
    # 解析Markdown内容并转换为HTML
    lines = report.split('\n')
    html_body = []
    in_section = False
    current_section = ""
    
    for line in lines:
        if line.startswith('## 一、'):
            if html_body:
                html_body.append("</div>")
            current_section = "overview"
            html_body.append(f'<div class="report-card">')
            html_body.append(f'<div class="report-header">')
            html_body.append(f'<h1>📈 每日全球市场报告</h1>')
            html_body.append(f'<div class="subtitle">{report_date} | YQClaw智能投资助手</div>')
            html_body.append(f'</div>')
            html_body.append('<div class="table-wrapper"><table class="market-table">')
            html_body.append('<thead><tr>')
            html_body.append('<th>市场</th><th>最新价</th><th>涨跌幅</th><th>成交额</th><th>市场分析</th>')
            html_body.append('</tr></thead><tbody>')
        elif line.startswith('## 二、') or line.startswith('## 三、') or line.startswith('## 四、') or line.startswith('## 五、'):
            # 结束表格
            if current_section == "overview":
                html_body.append('</tbody></table></div>')
                html_body.append('</div>')
                current_section = ""
            
            # 开始新章节
            section_name = line.replace('## ', '').replace('### ', '')
            html_body.append(f'<div class="report-card">')
            html_body.append(f'<div class="section">')
            html_body.append(f'<div class="section-title">{section_name}</div>')
        elif line.startswith('|') and not line.startswith('|---'):
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 2 and current_section == "overview":
                # 解析市场数据行
                market = cols[0] if cols else ""
                price = cols[1] if len(cols) > 1 else "—"
                change = cols[2] if len(cols) > 2 else "—"
                volume = cols[3] if len(cols) > 3 else "—"
                analysis = cols[4] if len(cols) > 4 else ""
                
                # 清理emoji
                market_clean = market
                
                # 解析涨跌
                change_class = "change-neutral"
                if '+' in change and change != '—':
                    change_class = "change-up"
                elif '-' in change and change != '—':
                    change_class = "change-down"
                
                # 清理涨跌幅文字
                change_clean = change.replace('🟢', '▲').replace('🔴', '▼').replace('⚪', '●')
                
                html_body.append('<tr>')
                html_body.append(f'<td class="market-name"><span class="icon">📊</span> {market_clean}</td>')
                html_body.append(f'<td class="price">{price}</td>')
                html_body.append(f'<td class="change"><span class="{change_class}">{change_clean}</span></td>')
                html_body.append(f'<td class="volume">{volume}</td>')
                html_body.append(f'<td class="analysis">{analysis}</td>')
                html_body.append('</tr>')
        elif line.startswith('|') and '---' in line:
            pass  # 跳过分隔行
        elif line.startswith('### '):
            section_title = line.replace('### ', '')
            html_body.append(f'<div style="padding: 8px 0 4px; font-weight: 600; color: #1e3c72;">{section_title}</div>')
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            text = line.strip()[2:]
            if text:
                html_body.append(f'<div class="news-item">• {text}</div>')
        elif line.strip() and not line.startswith('#'):
            if current_section:
                html_body.append(f'<p style="font-size: 13px; color: #555; line-height: 1.7; padding: 4px 0;">{line}</p>')
    
    # 结束最后一个section
    if current_section == "overview":
        html_body.append('</tbody></table></div>')
        html_body.append('</div>')
    
    html_body.append('<div class="footer">由 YQClaw智能投资助手 生成</div>')
    html_body.append('</body></html>')
    
    return html_head + '\n'.join(html_body)

