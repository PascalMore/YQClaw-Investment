# -*- coding: utf-8 -*-
"""
===================================
全球市场日报 HTML 报告生成器
===================================

生成移动端友好的 HTML 市场报告。

章节结构：
1. 全球市场概览（表格，冻结列+横向滚动）
2. 热点资讯 Top3
3. 各市场复盘
4. 金融日历
5. 小Q的洞察

移动端优化：
- 表格支持横向滚动
- 市场和指数列冻结（sticky）
- 自适应列宽
"""

import os
import sys
from datetime import datetime, date
from typing import Dict, List, Optional

# 导入市场数据适配器
import os
import sys
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
_src_dir = os.path.join(_parent_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from new_services.market_data_adapter import MarketDataAdapter
import litellm


# ============================================
# HTML 模板
# ============================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{title}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            background: #f5f5f7;
            font-size: 14px;
            padding: 12px;
            max-width: 100%;
        }}
        
        .report-container {{
            background: #fff;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        
        .report-header {{
            text-align: center;
            margin-bottom: 20px;
            padding: 20px 16px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 12px 12px 0 0;
            margin: -16px -16px 20px -16px;
            padding: 24px 16px;
        }}
        
        .report-header h1 {{
            font-size: 22px;
            color: #fff;
            margin-bottom: 4px;
            text-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        
        .report-header .subtitle {{
            font-size: 12px;
            color: rgba(255,255,255,0.7);
        }}
        
        h2 {{
            font-size: 16px;
            color: #1a1a1a;
            margin-bottom: 12px;
            padding-left: 10px;
            border-left: 3px solid #007aff;
        }}
        
        /* 表格容器 - 支持横向滚动 */
        .table-wrapper {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin: 0 -4px;
            padding: 0 4px;
        }}
        
        /* 冻结列表格 */
        .freeze-table {{
            width: 100%;
            min-width: 800px;
            border-collapse: collapse;
            font-size: 12px;
            table-layout: fixed;
        }}
        
        .freeze-table th,
        .freeze-table td {{
            padding: 10px 8px;
            text-align: left;
            border-bottom: 1px solid #eee;
            white-space: normal;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        
        /* 冻结列样式 */
        .freeze-table th.sticky,
        .freeze-table td.sticky {{
            position: sticky;
            left: 0;
            background: #fff;
            z-index: 2;
        }}
        
        .freeze-table th.sticky {{
            background: #f8f8f8;
            z-index: 3;
        }}
        
        /* 市场列更宽 */
        .freeze-table td:nth-child(1),
        .freeze-table th:nth-child(1) {{
            width: 60px;
            font-weight: 600;
            background: #f0f7ff;
        }}
        
        .freeze-table td:nth-child(1).sticky,
        .freeze-table th:nth-child(1).sticky {{
            background: #f0f7ff;
        }}
        
        /* 指数列 */
        .freeze-table td:nth-child(2),
        .freeze-table th:nth-child(2) {{
            width: 90px;
            background: #fafafa;
        }}
        
        .freeze-table td:nth-child(2).sticky,
        .freeze-table th:nth-child(2).sticky {{
            background: #fafafa;
        }}
        
        /* 涨跌幅颜色 */
        .up {{ color: #e74c3c; }}
        .down {{ color: #27ae60; }}
        .flat {{ color: #888; }}
        
        /* 市场分析列 - 更宽以显示完整内容 */
        .analysis-col {{
            width: 200px;
            max-width: 200px;
            font-size: 11px;
            line-height: 1.4;
            color: #555;
        }}
        
        /* 卡片区块 */
        .card {{
            background: #f9f9fb;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
        }}
        
        .card:last-child {{
            margin-bottom: 0;
        }}
        
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 6px;
        }}
        
        .card-meta {{
            font-size: 11px;
            color: #888;
            margin-bottom: 4px;
        }}
        
        .card-content {{
            font-size: 13px;
            color: #333;
            line-height: 1.5;
        }}
        
        /* 仓位建议标签 */
        .position-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
        }}
        
        .position-high {{ background: #ffeaea; color: #e74c3c; }}
        .position-medium {{ background: #fff4e5; color: #f39c12; }}
        .position-low {{ background: #e8f5e9; color: #27ae60; }}
        
        /* 日历样式 */
        .calendar-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        
        .calendar-item:last-child {{
            border-bottom: none;
        }}
        
        .calendar-date {{
            font-size: 12px;
            color: #888;
            width: 70px;
        }}
        
        .calendar-event {{
            flex: 1;
            font-size: 13px;
            color: #1a1a1a;
        }}
        
        .calendar-impact {{
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        
        .impact-high {{ background: #ffeaea; color: #e74c3c; }}
        .impact-medium {{ background: #fff4e5; color: #f39c12; }}
        .impact-low {{ background: #e8f5e9; color: #27ae60; }}
        
        /* 小Q洞察 */
        .insight-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            border-radius: 10px;
            padding: 16px;
        }}
        
        .insight-box h3 {{
            font-size: 15px;
            margin-bottom: 10px;
            opacity: 0.9;
        }}
        
        .insight-box p {{
            font-size: 13px;
            line-height: 1.6;
            opacity: 0.95;
        }}
        
        /* 页脚 */
        .report-footer {{
            text-align: center;
            padding: 16px;
            color: #888;
            font-size: 11px;
        }}
        
        /* 新闻列表 */
        .news-item {{
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        
        .news-item:last-child {{
            border-bottom: none;
        }}
        
        .news-title {{
            font-size: 13px;
            font-weight: 500;
            color: #1a1a1a;
            margin-bottom: 4px;
            line-height: 1.4;
        }}
        
        .news-meta {{
            font-size: 11px;
            color: #888;
        }}
        
        /* 无数据提示 */
        .no-data {{
            text-align: center;
            color: #888;
            padding: 20px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1>📈 全球市场报告</h1>
            <div class="subtitle">{date_str} · 每日全球市场报告</div>
        </div>
        
        <!-- 第一章：全球市场概览 -->
        <section class="report-section">
            <h2>📊 全球市场概览</h2>
            <div class="table-wrapper">
                <table class="freeze-table">
                    <thead>
                        <tr>
                            <th class="sticky">市场</th>
                            <th class="sticky">指数</th>
                            <th>收盘价</th>
                            <th>涨跌幅</th>
                            <th>成交额</th>
                            <th class="analysis-col">市场分析</th>
                            <th>仓位建议</th>
                            <th>理由</th>
                        </tr>
                    </thead>
                    <tbody>
                        {market_rows}
                    </tbody>
                </table>
            </div>
        </section>
    </div>
    
    <div class="report-container">
        <!-- 第二章：热点资讯 Top3 -->
        <section class="report-section">
            <h2>🔥 热点资讯 Top3</h2>
            {hot_news}
        </section>
    </div>
    
    <div class="report-container">
        <!-- 第三章：各市场复盘 -->
        <section class="report-section">
            <h2>📈 各市场复盘</h2>
            {market_review}
        </section>
    </div>
    
    <div class="report-container">
        <!-- 第四章：金融日历 -->
        <section class="report-section">
            <h2>📅 金融日历</h2>
            {calendar}
        </section>
    </div>
    
    <div class="report-container">
        <!-- 第五章：小Q的洞察 -->
        <section class="report-section">
            <h2>💡 小Q的洞察</h2>
            <div class="insight-box">
                <h3>🤖 今日观点</h3>
                <p>{insight}</p>
            </div>
        </section>
    </div>
    
    <div class="report-footer">
        <div>报告生成时间：{generated_at}</div>
        <div style="margin-top: 4px;">Powered by 小Q · AI 投资助手</div>
    </div>
</body>
</html>
"""


# ============================================
# 新闻卡片 HTML
# ============================================

NEWS_CARD_TEMPLATE = """
<div class="card">
    <div class="card-meta">{source} · {time}</div>
    <div class="card-title">{title}</div>
</div>
"""


# ============================================
# 市场复盘区块 HTML
# ============================================

REVIEW_SECTION_TEMPLATE = """
<div class="card">
    <div class="card-title">{market_name}</div>
    <div class="card-content">{content}</div>
</div>
"""


# ============================================
# 报告生成器
# ============================================

class ReportGenerator:
    """
    全球市场日报 HTML 报告生成器
    
    使用 MarketDataAdapter 获取数据，生成移动端友好的 HTML 报告。
    """
    
    # 数据缓存（避免重复API调用导致rate limiting）
    _cache = {}
    _cache_time = None
    CACHE_DURATION = 300  # 缓存5分钟
    
    # 指数清单配置
    INDEX_CONFIG = {
        # A股
        "上证指数": {"market": "A股", "code": "000001", "source": "cn"},
        "沪深300": {"market": "A股", "code": "000300", "source": "cn"},
        # 港股
        "恒生指数": {"market": "H股", "code": "^HSI", "source": "hk"},
        "恒生科技": {"market": "H股", "code": "HSTECH", "source": "hk"},
        # Crypto
        "BTC": {"market": "Crypto", "symbol": "BTCUSDT", "source": "binance"},
        "ETH": {"market": "Crypto", "symbol": "ETHUSDT", "source": "binance"},
        "SOL": {"market": "Crypto", "symbol": "SOLUSDT", "source": "binance"},
        "PEPE": {"market": "Crypto", "symbol": "PEPEUSDT", "source": "binance"},
        # 美股
        "标普500": {"market": "美股", "code": "^GSPC", "source": "us"},
        "纳斯达克": {"market": "美股", "code": "^IXIC", "source": "us"},
        # 大宗商品
        "黄金 AU2606": {"market": "大宗", "source": "comm", "data_key": "黄金"},
        "原油 SC2605": {"market": "大宗", "source": "comm", "data_key": "原油"},
        # 债券
        "中国国债(10Y)": {"market": "债市", "source": "bond", "data_key": "中国国债(10Y)"},
        "美国国债(10Y)": {"market": "债市", "source": "bond", "data_key": "美国国债(10Y)"},
    }
    
    # 市场分析映射（从复盘报告提取的关键结论）
    MARKET_ANALYSIS = {
        "A股": "科创50和创业板指表现最强，分别上涨6.18%和5.91%。市场分化突出，上涨1240家下跌4194家。科技成长板块获资金青睐，半导体净流入25.27亿元。",
        "H股": "港股今日震荡反弹，恒生科技指数表现优于大盘。南向资金净流入，科技股估值修复中。",
        "美股": "三大指数大幅上涨，标普500涨2.51%，纳斯达克涨2.80%。VIX暴跌18.39%至21.04，风险偏好急剧回升。",
        "Crypto": "加密市场整体回调，BTC跌1.23%逼近71000美元。山寨币普跌，PEPE跌超5%。",
        "大宗": "黄金和原油走势分化。黄金受到避险需求支撑，原油因地缘风险缓解而承压下跌。",
        "债市": "中美债券市场平稳运行。美联储政策预期稳定，中国债券收益率小幅波动。",
    }
    
    # 仓位建议配置
    POSITION_ADVICE = {
        "A股": {"level": "medium", "text": "5-6成"},
        "H股": {"level": "medium", "text": "4-5成"},
        "美股": {"level": "high", "text": "6-7成"},
        "Crypto": {"level": "low", "text": "2-3成"},
        "大宗": {"level": "medium", "text": "3-4成"},
        "债市": {"level": "low", "text": "2-3成"},
    }
    
    def __init__(self):
        self.adapter = MarketDataAdapter()
        self._fetch_all_data()  # 一次性获取所有数据并缓存
    
    def _format_change_pct(self, pct: float) -> str:
        """格式化涨跌幅"""
        if pct > 0:
            return f"<span class='up'>+{pct:.2f}%</span>"
        elif pct < 0:
            return f"<span class='down'>{pct:.2f}%</span>"
        else:
            return f"<span class='flat'>{pct:.2f}%</span>"
    
    def _format_price(self, value: float, index_name: str, source: str = None) -> str:
        """格式化价格"""
        # Crypto 小数位
        if index_name in ["BTC", "ETH", "SOL"]:
            return f"${value:,.2f}"
        elif index_name == "PEPE":
            return f"${value:.6f}"
        # 大宗商品
        elif source == "comm":
            if index_name.startswith("黄金"):
                return f"{value:.2f} 元/克"
            elif index_name.startswith("原油"):
                return f"{value:.2f} 元/桶"
            return f"{value:.2f}"
        # 债券收益率
        elif source == "bond":
            return f"{value:.4f}%"
        # 指数
        elif value > 10000:
            return f"{value:,.2f}"
        else:
            return f"{value:,.2f}"
    
    def _get_position_badge(self, market: str) -> str:
        """获取仓位建议标签"""
        advice = self.POSITION_ADVICE.get(market, {"level": "medium", "text": "待定"})
        level_class = f"position-{advice['level']}"
        return f"<span class='position-badge {level_class}'>{advice['text']}</span>"
    
    def _get_analysis(self, market: str) -> str:
        """获取市场分析（从复盘报告动态提取）"""
        # 优先使用动态获取的复盘摘要
        cache_key = f'_analysis_cache_{market}'
        if hasattr(self, '_analysis_cache') and market in self._analysis_cache:
            return self._analysis_cache[market]
        
        review_map = {
            "A股": ('cn', self.adapter.get_cn_market_review),
            "H股": ('hk', self.adapter.get_hk_market_review),
        }
        
        result = self.MARKET_ANALYSIS.get(market, "暂无分析数据")
        
        if market in review_map:
            review = review_map[market][1]()
            if review:
                result = self._llm_summarize_review(review, max_chars=85)
        elif market == "美股":
            review = self.adapter.get_us_market_review()
            if review:
                result = self._llm_summarize_review(review, max_chars=85)
        elif market == "Crypto":
            review = self.adapter.get_crypto_market_review()
            if review:
                result = self._llm_summarize_review(review, max_chars=85)
        
        # 缓存结果
        if not hasattr(self, '_analysis_cache'):
            self._analysis_cache = {}
        self._analysis_cache[market] = result
        
        return result
    
    def _llm_summarize_review(self, review_text: str, max_chars: int = 85) -> str:
        """用LLM将复盘报告总结为≤85字的核心分析（用于表格展示）"""
        if not review_text:
            return "暂无分析数据"
        
        # 截断过长文本以节省token
        text_to_summarize = review_text[:3000]
        
        try:
            response = litellm.completion(
                model="minimax/MiniMax-M2.7",
                messages=[{
                    "role": "user",
                    "content": (
                        f"请将以下市场复盘内容总结为不超过{max_chars}个字的核心分析，"
                        f"要求：1）简洁精炼；2）包含涨跌关键数据；3）给出核心结论。"
                        f"用中文输出，直接输出总结内容，不要任何前缀。\n\n{text_to_summarize}"
                    )
                }],
                max_tokens=100,
                temperature=0.3,
            )
            summary = response.choices[0].message.content.strip()
            # 确保不超过限制
            if len(summary) > max_chars:
                summary = summary[:max_chars]
            return summary
        except Exception as e:
            print(f"[ReportGenerator] LLM总结失败: {e}")
            # 降级：取第一段有效内容
            lines = [l.strip() for l in review_text.split('\n') if l.strip() and len(l.strip()) > 15]
            for line in lines:
                if not any(kw in line for kw in ['#', '---', '**', '##', '```', '>>>', '- ', '1.', '2.', '3.']):
                    return line[:max_chars]
            return "暂无分析数据"
    
    def _get_reason(self, market: str, index_name: str) -> str:
        """获取理由"""
        reasons = {
            "A股": "科技股领涨，政策预期支撑",
            "H股": "南向资金流入，估值修复",
            "美股": "VIX暴跌，风险偏好回升",
            "Crypto": "市场回调，整固后看涨",
            "大宗": "避险需求，通胀支撑",
            "债市": "收益率平稳，防御配置",
        }
        return reasons.get(market, "关注趋势延续")
    
    def _fetch_all_data(self):
        """一次性获取所有市场数据并缓存（避免rate limiting）"""
        import time
        now = time.time()
        
        # 检查缓存是否有效
        if (self._cache and 
            self._cache_time and 
            now - self._cache_time < self.CACHE_DURATION):
            return  # 缓存有效，直接使用
        
        print("[ReportGenerator] 开始获取市场数据...")
        
        # 清空旧缓存
        self._cache = {}
        
        # 获取各市场数据（仅调用一次）
        self._cache['cn'] = {d['name']: d for d in self.adapter.get_cn_index_data()}
        time.sleep(0.5)  # 避免请求过快
        
        self._cache['hk'] = {d['name']: d for d in self.adapter.get_hk_index_data()}
        time.sleep(0.5)
        
        self._cache['us'] = {d['name']: d for d in self.adapter.get_us_index_data()}
        time.sleep(0.5)
        
        self._cache['crypto'] = {d['symbol'].replace('USDT', ''): d for d in self.adapter.get_crypto_data()}
        time.sleep(0.5)
        
        # 大宗商品（黄金、原油）
        comm_data = {d['name']: d for d in self.adapter.get_commodity_data()}
        self._cache['comm'] = comm_data
        time.sleep(0.5)
        
        # 债券（中债、美债）
        bond_data = {d['name']: d for d in self.adapter.get_bond_data()}
        self._cache['bond'] = bond_data
        
        self._cache_time = now
        print(f"[ReportGenerator] 数据获取完成，缓存已更新")
    
    def _generate_market_rows(self) -> str:
        """生成市场概览表格行"""
        rows = []
        
        # 使用缓存数据
        cn_data = self._cache.get('cn', {})
        hk_data = self._cache.get('hk', {})
        us_data = self._cache.get('us', {})
        crypto_data = self._cache.get('crypto', {})
        comm_data = self._cache.get('comm', {})
        bond_data = self._cache.get('bond', {})
        
        # 按配置顺序生成行
        for index_name, config in self.INDEX_CONFIG.items():
            market = config["market"]
            source = config["source"]
            
            # 获取数据
            if source == "cn":
                data = cn_data.get(index_name)
                if data:
                    current = data.get('current', 0)
                    change_pct = data.get('change_pct', 0)
                    # A股指数：volume是股数，amount才是成交额（元）
                    # amount除以1e8得到亿元
                    volume = data.get('amount', 0)
                else:
                    current, change_pct, volume = 0, 0, 0
            
            elif source == "hk":
                data = hk_data.get(index_name)
                if data:
                    current = data.get('current', 0)
                    change_pct = data.get('change_pct', 0)
                    # H股：volume是成交额（元），格式化时除以1e8转亿
                    volume = data.get('volume', 0)
                else:
                    current, change_pct, volume = 0, 0, 0
            
            elif source == "us":
                data = us_data.get(index_name)
                if data:
                    current = data.get('current', 0)
                    change_pct = data.get('change_pct', 0)
                    volume = 0
                else:
                    current, change_pct, volume = 0, 0, 0
            
            elif source == "binance":
                data = crypto_data.get(index_name)
                if data:
                    current = data.get('price', 0)
                    change_pct = data.get('change_pct', 0)
                    volume = data.get('volume', 0)  # get_crypto_data() 将 quoteVolume 映射为 volume
                else:
                    current, change_pct, volume = 0, 0, 0

            elif source == "comm":
                data = comm_data.get(config['data_key'])
                if data:
                    current = data.get('price', 0)
                    change_pct = data.get('change_pct', 0)
                    # Tushare 期货主连返回 amount（成交金额，元），直接复用
                    volume = data.get('amount', 0) or 0
                else:
                    current, change_pct, volume = 0, 0, 0

            elif source == "bond":
                data = bond_data.get(config['data_key'])
                if data:
                    current = data.get('rate_10y', 0)  # 10年期国债收益率
                    change_pct = 0  # 债券收益率变化不常用
                    volume = 0
                else:
                    current, change_pct, volume = 0, 0, 0

            else:
                current, change_pct, volume = 0, 0, 0
            
            # 格式化成交额
            # A股/港股：volume 单位是元（CNY），转换为亿
            # Crypto：volume 是 quoteVolume，单位是 USDT，转换为亿USDT（统一用亿为单位）
            if source == "binance":
                if volume >= 1e8:
                    volume_str = f"{volume/1e8:.2f}亿U"
                elif volume >= 1e6:  # >= 100万USD
                    volume_str = f"{volume/1e8:.2f}亿U"  # 统一显示为亿U
                elif volume >= 1e4:
                    volume_str = f"{volume/1e4:.2f}万U"
                else:
                    volume_str = "-"
            else:
                if volume >= 1e8:
                    volume_str = f"{volume/1e8:.2f}亿"
                elif volume >= 1e4:
                    volume_str = f"{volume/1e4:.2f}万"
                else:
                    volume_str = "-"
            
            row = f"""
                        <tr>
                            <td class="sticky">{market}</td>
                            <td class="sticky">{index_name}</td>
                            <td>{self._format_price(current, index_name, source)}</td>
                            <td>{self._format_change_pct(change_pct) if source != "bond" else "-"}</td>
                            <td>{volume_str}</td>
                            <td class="analysis-col">{self._get_analysis(market)}</td>
                            <td>{self._get_position_badge(market)}</td>
                            <td>{self._get_reason(market, index_name)}</td>
                        </tr>
            """
            rows.append(row)
        
        return "".join(rows)
    
    def _generate_global_news(self) -> str:
        """生成热点资讯"""
        news_list = self.adapter.get_global_news(limit=3)
        
        if not news_list:
            return '<div class="no-data">暂无热点资讯</div>'
        
        cards = []
        for news in news_list:
            card = NEWS_CARD_TEMPLATE.format(
                source=news.get('source', '未知来源'),
                time=news.get('time', ''),
                title=news.get('title', '暂无标题')
            )
            cards.append(card)
        
        return "".join(cards)
    
    def _generate_market_review(self) -> str:
        """生成各市场复盘"""
        sections = []
        
        # 获取复盘报告
        cn_review = self.adapter.get_cn_market_review()
        us_review = self.adapter.get_us_market_review()
        
        if cn_review:
            sections.append(REVIEW_SECTION_TEMPLATE.format(
                market_name="🇨🇳 A股复盘",
                content=cn_review[:500] + "..." if len(cn_review) > 500 else cn_review
            ))
        
        if us_review:
            sections.append(REVIEW_SECTION_TEMPLATE.format(
                market_name="🇺🇸 美股复盘",
                content=us_review[:500] + "..." if len(us_review) > 500 else us_review
            ))
        
        if not sections:
            return '<div class="no-data">暂无市场复盘数据</div>'
        
        return "".join(sections)
    
    def _generate_calendar(self) -> str:
        """生成金融日历"""
        events = self.adapter.get_financial_calendar()
        
        if not events:
            return '<div class="no-data">暂无重要财经事件</div>'
        
        items = []
        for event in events[:10]:
            impact_class = f"impact-{event.get('impact', 'low')}"
            item = f"""
                <div class="calendar-item">
                    <div class="calendar-date">{event.get('date', '')}</div>
                    <div class="calendar-event">{event.get('event', '')}</div>
                    <div class="calendar-impact {impact_class}">{event.get('impact_text', '')}</div>
                </div>
            """
            items.append(item)
        
        return "".join(items)
    
    def _generate_insight(self) -> str:
        """生成小Q洞察"""
        # 基于市场分析生成简要洞察
        insights = []
        
        cn_data = self.adapter.get_cn_index_data()
        if cn_data:
            avg_change = sum(d.get('change_pct', 0) for d in cn_data) / len(cn_data)
            if avg_change > 2:
                insights.append("A股今日表现强劲，科创创业板领涨，建议关注科技主线")
            elif avg_change > 0:
                insights.append("A股震荡分化，结构性机会仍存，建议均衡配置")
            else:
                insights.append("A股整体偏弱，控制仓位防御为主")
        
        crypto_data = self.adapter.get_crypto_data()
        if crypto_data:
            btc = next((d for d in crypto_data if d['symbol'] == 'BTCUSDT'), None)
            if btc and btc.get('change_pct', 0) < -3:
                insights.append("BTC大幅回调，关注71000支撑，若守住可分批布局")
            elif btc and btc.get('change_pct', 0) > 3:
                insights.append("BTC强势反弹，涨势强劲但注意追高风险")
        
        us_data = self.adapter.get_us_index_data()
        if us_data:
            insights.append("美股大幅反弹，VIX暴跌说明风险偏好快速回升，可适度加仓")
        
        if not insights:
            insights.append("市场整体震荡，建议控制仓位，等待趋势明朗")
        
        return " ".join(insights)
    
    def generate_html_report(self) -> str:
        """生成完整 HTML 报告"""
        today = date.today()
        
        # 获取报告数据
        market_rows = self._generate_market_rows()
        hot_news = self._generate_global_news()
        market_review = self._generate_market_review()
        calendar = self._generate_calendar()
        insight = self._generate_insight()
        
        # 渲染模板
        html = HTML_TEMPLATE.format(
            title="全球市场日报",
            date_str=today.strftime("%Y年%m月%d日"),
            market_rows=market_rows,
            hot_news=hot_news,
            market_review=market_review,
            calendar=calendar,
            insight=insight,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return html
    
    def save_report(self, output_dir: Optional[str] = None) -> str:
        """保存报告到文件"""
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'reports')
        
        os.makedirs(output_dir, exist_ok=True)
        
        today = date.today()
        filename = f"global_market_report_{today.strftime('%Y%m%d')}.html"
        filepath = os.path.join(output_dir, filename)
        
        html_content = self.generate_html_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"[ReportGenerator] 报告已生成: {filepath}")
        return filepath


# ============================================
# 入口函数
# ============================================

def generate_daily_report() -> str:
    """生成每日全球市场日报"""
    generator = ReportGenerator()
    return generator.generate_html_report()


def save_daily_report(output_path: Optional[str] = None) -> str:
    """生成并保存每日全球市场日报"""
    generator = ReportGenerator()
    
    if output_path:
        html_content = generator.generate_html_report()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[ReportGenerator] 报告已保存: {output_path}")
        return output_path
    else:
        return generator.save_report()


if __name__ == "__main__":
    # 测试报告生成
    print("[ReportGenerator] 开始生成报告...")
    generator = ReportGenerator()
    html = generator.generate_html_report()
    
    # 保存到 reports 目录
    output_file = generator.save_report()
    print(f"[ReportGenerator] 报告已生成: {output_file}")
    print(f"[ReportGenerator] HTML 长度: {len(html)} 字符")
