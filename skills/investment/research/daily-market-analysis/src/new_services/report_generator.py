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
import subprocess
import sys
from datetime import datetime, date
from typing import Dict, List, Optional

# 导入市场数据适配器
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
_src_dir = os.path.join(_parent_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from new_services.market_data_adapter import MarketDataAdapter


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

        /* ========== 热点资讯 Grid ========== */
        .news-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}

        .news-card {{
            background: #fff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }}

        .news-card-header {{
            padding: 6px 10px;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .news-card-header .dot {{
            display: none;
        }}

        .news-card.global   .news-card-header {{ background: #EEF3FF; color: #3B49DD; }}
        .news-card.global   .news-card-header .dot {{ background: #3B49DD; }}
        .news-card.cn        .news-card-header {{ background: #FFF3E0; color: #E65100; }}
        .news-card.cn        .news-card-header .dot {{ background: #E65100; }}
        .news-card.hk        .news-card-header {{ background: #F3E5F5; color: #6A1B9A; }}
        .news-card.hk        .news-card-header .dot {{ background: #6A1B9A; }}
        .news-card.us        .news-card-header {{ background: #E3F2FD; color: #0D47A1; }}
        .news-card.us        .news-card-header .dot {{ background: #0D47A1; }}
        .news-card.crypto    .news-card-header {{ background: #E8F5E9; color: #2E7D32; }}
        .news-card.crypto    .news-card-header .dot {{ background: #2E7D32; }}
        .news-card.commodity .news-card-header {{ background: #FBE9E7; color: #BF360C; }}
        .news-card.commodity .news-card-header .dot {{ background: #BF360C; }}

        .news-card-body {{
            padding: 6px 10px;
            display: flex;
            flex-direction: column;
        }}

        .news-card-item {{
            padding: 5px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .news-card-item:last-child {{
            border-bottom: none;
            padding-bottom: 0;
        }}
        .news-card-item:first-child {{
            padding-top: 0;
        }}

        .news-card-item .title {{
            font-size: 13px;
            font-weight: 500;
            color: #1a1a1a;
            line-height: 1.5;
            margin-bottom: 3px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .news-card-item .title a {{
            color: inherit;
            text-decoration: none;
        }}

        .news-card-item .title a:hover {{
            color: #3B49DD;
            text-decoration: underline;
        }}

        .news-card-item .digest {{
            font-size: 12px;
            color: #666;
            line-height: 1.5;
            margin-bottom: 4px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .news-card-item .meta {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 11px;
            color: #aaa;
            white-space: nowrap;
        }}

        .news-card-item .meta .source {{
            color: #888;
            background: #f5f5f5;
            padding: 1px 6px;
            border-radius: 3px;
            max-width: 90px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex-shrink: 1;
        }}

        .news-card-item .meta .time {{
            flex-shrink: 0;
            color: #aaa;
        }}

        .news-card-item .meta .detail-link {{
            color: #3B49DD;
            text-decoration: none;
            margin-left: auto;
            font-size: 11px;
        }}

        .news-card-item .meta .detail-link:hover {{
            text-decoration: underline;
        }}

        .news-footer {{
            margin-top: 16px;
            text-align: center;
            color: #bbb;
            font-size: 11px;
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
        <div style="margin-top: 4px;">Powered by {sender_name}</div>
    </div>
</body>
</html>
"""


# ============================================
# 新闻卡片 HTML
# ============================================

# 单条新闻 HTML（用于 grid 中的每个 item）
NEWS_ITEM_TEMPLATE = """
<div class="news-card-item">
    <div class="title"><a href="{url}" target="_blank">{title}</a></div>
    <div class="digest">{digest}</div>
    <div class="meta">
        <span class="time">{time}</span>
        <span class="source">{source}</span>
    </div>
</div>
"""

NEWS_ITEM_TEMPLATE_NO_TIME = """
<div class="news-card-item">
    <div class="title"><a href="{url}" target="_blank">{title}</a></div>
    <div class="digest">{digest}</div>
    <div class="meta">
        <span class="source">{source}</span>
    </div>
</div>
"""

# 单板块卡片 HTML
NEWS_SECTION_TEMPLATE = """
<div class="news-card {cls}">
    <div class="news-card-header">
        <span class="dot"></span>
        {label}
    </div>
    <div class="news-card-body">
{items}
    </div>
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
    
    # 指数清单配置（name 字段必须与 MarketDataAdapter 返回的 name 一致）
    INDEX_CONFIG = {
        # A股
        "上证指数": {"market": "A股", "code": "000001", "source": "cn"},
        "沪深300": {"market": "A股", "code": "000300", "source": "cn"},
        # 港股
        "恒生指数": {"market": "H股", "code": "HSI", "source": "hk"},
        "恒生科技": {"market": "H股", "code": "HSTECH", "source": "hk"},
        # Crypto
        "BTC": {"market": "Crypto", "symbol": "BTCUSDT", "source": "binance"},
        "ETH": {"market": "Crypto", "symbol": "ETHUSDT", "source": "binance"},
        "SOL": {"market": "Crypto", "symbol": "SOLUSDT", "source": "binance"},
        "PEPE": {"market": "Crypto", "symbol": "PEPEUSDT", "source": "binance"},
        # 美股（name 与 DSA fetcher 返回的一致）
        "标普500指数": {"market": "美股", "code": "SPX", "source": "us"},
        "纳斯达克综合指数": {"market": "美股", "code": "IXIC", "source": "us"},
        # 大宗商品（data_key 与 get_commodity_data 返回的 name 一致）
        "黄金": {"market": "大宗", "source": "comm", "data_key": "黄金"},
        "WTI原油": {"market": "大宗", "source": "comm", "data_key": "WTI原油"},
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
    
    def __init__(self, config=None):
        self.adapter = MarketDataAdapter()
        # 加载配置（用于新闻数量等设置）
        if config is None:
            import json, os
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                except:
                    config = {}
        self.config = config or {}
        self.adapter = MarketDataAdapter(self.config)
        self._fetch_all_data()  # 一次性获取所有数据并缓存
    
    def _format_change_pct(self, pct: float) -> str:
        """格式化涨跌幅"""
        if pct > 0:
            return f"<span class='up'>+{pct:.2f}%</span>"
        elif pct < 0:
            return f"<span class='down'>{pct:.2f}%</span>"
        else:
            return f"<span class='flat'>{pct:.2f}%</span>"

    def _format_change_bp(self, bp: float) -> str:
        """格式化债券收益率变化（单位：bp）"""
        if bp > 0:
            return f"<span class='up'>+{bp:.1f}bp</span>"
        elif bp < 0:
            return f"<span class='down'>{bp:.1f}bp</span>"
        else:
            return f"<span class='flat'>{bp:.1f}bp</span>"
    
    def _format_price(self, value: float, index_name: str, source: str = None) -> str:
        """格式化价格"""
        # 数据不可用
        if value is None or value == 0:
            return "-"
        
        # Crypto 小数位
        if index_name in ["BTC", "ETH", "SOL"]:
            return f"${value:,.2f}"
        elif index_name == "PEPE":
            return f"${value:.8f}"
        # 大宗商品
        elif source == "comm":
            if index_name.startswith("黄金"):
                return f"{value:.2f} 元/克"
            elif index_name.startswith("WTI") or index_name.startswith("原油"):
                return f"${value:.2f}"
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
        
        # 默认用 MARKET_ANALYSIS 静态文本
        result = self.MARKET_ANALYSIS.get(market, "暂无分析数据")
        
        if market in review_map:
            review = review_map[market][1]()
            if review:
                summarized = self._llm_summarize_review(review, max_chars=100)
                # 只有 LLM 返回有效内容（非空、非复读文本）才用
                if summarized and len(summarized) > 5:
                    result = summarized
        elif market == "美股":
            review = self.adapter.get_us_market_review()
            if review:
                summarized = self._llm_summarize_review(review, max_chars=100)
                if summarized and len(summarized) > 5:
                    result = summarized
        elif market == "Crypto":
            review = self.adapter.get_crypto_market_review()
            if review:
                summarized = self._llm_summarize_review(review, max_chars=100)
                if summarized and len(summarized) > 5:
                    result = summarized
        
        # 缓存结果
        if not hasattr(self, '_analysis_cache'):
            self._analysis_cache = {}
        self._analysis_cache[market] = result
        
        return result
    
    def _llm_summarize_review(self, review_text: str, max_chars: int = 85) -> str:
        """用LLM将复盘报告总结为≤85字的核心分析（用于表格展示）"""
        if not review_text:
            return "暂无分析数据"

        import re
        text_to_summarize = review_text[:3000]
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text_to_summarize))
        input_text = text_to_summarize[:500] if not has_chinese else text_to_summarize[:1500]
        prompt = (
            f"请用中文一句话总结以下市场复盘内容，包含关键涨跌数据和方向，用85-100字输出：\n\n"
            f"{input_text}"
        )

        summary = ''
        for attempt in range(3):
            try:
                import litellm
                litellm.suppress_debug_info = True
                import os as _os
                _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.env')
                if os.path.exists(_env_path):
                    for line in open(_env_path):
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            _os.environ.setdefault(k, v)
                _minimax_key = _os.environ.get('LLM_MINIMAX_API_KEYS', '').split(',')[0]
                _minimax_base = _os.environ.get('LLM_MINIMAX_BASE_URL', 'https://api.minimaxi.com/v1')
                response = litellm.completion(
                    model='minimax/MiniMax-M2.7',
                    messages=[{'role': 'user', 'content': prompt}],
                    api_key=_minimax_key,
                    api_base=_minimax_base,
                    max_tokens=300,
                    temperature=0.3,
                )
                msg = response.choices[0].message if response and response.choices else None
                content_raw = msg.content.strip() if msg.content else ''
                rc = getattr(msg, 'reasoning_content', None) or ''

                # 优先从 content 提取（非MiniMax模型通常在content）
                if content_raw and len(content_raw) > 5 and '请用中文' not in content_raw:
                    summary = content_raw
                    break

                # MiniMax-M2.7: content为空，实际回复在reasoning_content中
                if rc:
                    # 找英文双引号包裹的内容（模型在思考过程中输出的中文摘要）
                    quoted = re.findall(r'"([^"]{20,300})"', rc)
                    for q in reversed(quoted):
                        # 跳过 prompt 本身（prompt 以特定中文指令开头）
                        if q.strip().startswith(('请用中文', '一句话总结', '用中文')):
                            continue
                        if re.search(r'[\u4e00-\u9fff]', q) and re.search(r'\d', q) and len(q) > 20:
                            summary = q.strip()
                            break
                    # 从后往前找第一个包含数字的完整中文句子
                    if not summary:
                        sentences = re.findall(r'[^。！？\n]{30,300}[。！？]', rc)
                        for s in reversed(sentences):
                            s = s.strip()
                            if s.startswith(('请用中文', '一句话总结', '用中文')):
                                continue
                            if re.search(r'[\u4e00-\u9fff]', s) and re.search(r'\d', s) and len(s) > 20:
                                summary = s
                                break
                    # 跳过 prompt 复读内容（包含 prompt 完整文本或开头关键词）
                    if summary and (
                        '请用中文' in summary
                        or summary == prompt
                        or summary.startswith(('请用中文', '一句话总结', '用中文'))
                    ):
                        summary = ''
                    if summary:
                        break
            except Exception as e:
                err_str = str(e)
                if '529' in err_str or 'overloaded' in err_str.lower():
                    print(f"[ReportGenerator] LLM 529过载，重试 ({attempt+1}/3)...")
                    import time
                    time.sleep(3 * (attempt + 1))
                else:
                    print(f"[ReportGenerator] LLM call error: {e}")
                    break
        else:
            summary = ''

        if not summary:
            # 优先尝试提取"市场总结"等第一段正文（结构化复盘格式）
            import re
            # 匹配一级或二级标题后的第一段正文（非列表、非代码块）
            section_header_pattern = re.compile(
                r'^#{1,3}\s*[一二三四五六七八九十\d]+\s*[、,.\-].*$',
                re.MULTILINE
            )
            lines = review_text.split('\n')
            in_first_section = False
            for line in lines:
                stripped = line.strip()
                # 遇到第一段正文标题
                if section_header_pattern.match(stripped):
                    in_first_section = True
                    continue
                # 跳过标题行、空行、列表、代码块、分隔线
                if not stripped or stripped.startswith('#') or stripped.startswith('- ') or \
                   stripped.startswith('```') or stripped.startswith('>>>') or \
                   re.match(r'^[\-\*]+ ', stripped) or re.match(r'^\d+\. ', stripped) or \
                   stripped.startswith('---') or len(stripped) < 15:
                    continue
                # 遇到下一个章节标题，停止
                if in_first_section and section_header_pattern.match(stripped):
                    break
                # 找到正文第一段
                if in_first_section:
                    # 去掉 ** 加粗标记
                    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
                    # 如果是纯英文内容且有中文版本，尝试跳过
                    import re
                    if not re.search(r'[\u4e00-\u9fff]', clean):
                        # 纯英文内容，标记但继续找中文
                        summary = clean[:max_chars]
                        # 不 break，继续找后续可能的中文内容
                    else:
                        summary = clean[:max_chars]
                        break

            # 如果结构化提取失败，使用原有启发式
            if not summary:
                for line in lines:
                    stripped = line.strip()
                    if (stripped and len(stripped) > 15 and
                        not any(kw in stripped for kw in ['#', '---', '**', '##', '```', '>>>', '- ', '1.', '2.', '3.'])):
                        summary = stripped[:max_chars]
                        break
            
            # 如果summary是纯英文（无中文），尝试从剩余行找中文内容
            import re
            if summary and not re.search(r'[\u4e00-\u9fff]', summary):
                # 纯英文summary，尝试在后面几行找到中文内容
                for line in lines:
                    stripped = line.strip()
                    if (stripped and len(stripped) > 10 and
                        not any(kw in stripped for kw in ['#', '---', '**', '##', '```', '>>>', '- ', '1.', '2.', '3.']) and
                        re.search(r'[\u4e00-\u9fff]', stripped)):
                        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
                        summary = clean[:max_chars]
                        break
                # 如果还是找不到中文，使用原始英文但不加句号后缀
                if not re.search(r'[\u4e00-\u9fff]', summary):
                    summary = summary.rstrip('.,;: ')
                    if summary and summary[-1] not in '!.?':
                        summary += '.'

        # 确保不超长，截断到最后一个完整句
        if len(summary) > max_chars:
            truncated = summary[:max_chars]
            # 支持中英文标点：句号、逗号（中文逗号也可能是句子分隔）
            for sep in ['。', '. ', '，']:
                idx = truncated.rfind(sep)
                if idx > max_chars * 0.4:  # 阈值降低，留更多内容
                    summary = truncated[:idx + 1].strip()
                    break
            else:
                summary = truncated.rstrip('-,;:， ').strip()

        # 确保有句号结尾（如果截断后已有句号/感叹号/问号则不加）
        if summary and summary[-1] not in '。.！？':
            # 找最后一个完整句（倒着找句号）
            last_句 = max(summary.rfind('。'), summary.rfind('！'), summary.rfind('？'))
            if last_句 > max_chars * 0.5:
                summary = summary[:last_句 + 1]
            elif summary.endswith('，') or summary.endswith(','):
                # 逗号结尾 → 改为句号
                summary = summary.rstrip('，,').strip() + '。'
            else:
                summary += '。'

        return summary
    
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
                    # 数据获取失败时用 None 标记，不要显示为 0
                    current, change_pct, volume = None, None, 0

            elif source == "bond":
                data = bond_data.get(config['data_key'])
                if data:
                    current = data.get('rate_10y', 0)
                    change_bp = data.get('change_bp', 0)
                    volume = 0
                else:
                    current, change_bp, volume = 0, 0, 0

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
            
            if source == "bond":
                change_cell = self._format_change_bp(change_bp)
            else:
                change_cell = self._format_change_pct(change_pct) if change_pct is not None else "-"

            row = f"""
                        <tr>
                            <td class="sticky">{market}</td>
                            <td class="sticky">{index_name}</td>
                            <td>{self._format_price(current, index_name, source)}</td>
                            <td>{change_cell}</td>
                            <td>{volume_str}</td>
                            <td class="analysis-col">{self._get_analysis(market)}</td>
                            <td>{self._get_position_badge(market)}</td>
                            <td>{self._get_reason(market, index_name)}</td>
                        </tr>
            """
            rows.append(row)
        
        return "".join(rows)
    
    # 六大新闻板块配置
    NEWS_CATEGORIES = [
        {"key": "global",    "cls": "global",    "label": "🌍 全球宏观影响力"},
        {"key": "us",        "cls": "us",        "label": "🇺🇸 美股市场"},
        {"key": "crypto",    "cls": "crypto",    "label": "₿ 数字货币"},
        {"key": "cn",        "cls": "cn",        "label": "🇨🇳 A 股市场"},
        {"key": "hk",        "cls": "hk",        "label": "🇭🇰 港股市场"},
        {"key": "commodity", "cls": "commodity", "label": "🥇 大宗商品"},
    ]

    def _generate_global_news(self) -> str:
        """生成热点资讯 - 6 板块 grid 布局

        每个板块从各市场新闻接口获取 3 条，6 列 grid 展示。
        """
        news_limit = 3
        sections = []

        for cat in self.NEWS_CATEGORIES:
            key = cat["key"]
            # 获取对应市场新闻
            if key == "global":
                news_list = self.adapter.get_global_news(limit=news_limit)
            else:
                news_list = self.adapter.get_market_news(key, limit=news_limit)

            items_html = []
            for news in news_list[:news_limit]:
                title = news.get('title', '暂无标题')
                digest = news.get('content', '') or news.get('snippet', '')
                if len(digest) > 100:
                    digest = digest[:100].rstrip('-,;:，') + '...'
                source = news.get('source', '未知')
                time_str = news.get('time') or news.get('datetime', '')
                # 简化时间显示为短格式
                if 'T' in time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        time_str = dt.strftime('%y/%m/%d %H:%M')
                    except:
                        pass
                else:
                    # 去掉秒和完整日期，只保留 MM-DD HH:MM 或 HH:MM
                    import re
                    m = re.search(r'(\d{2,4})\D(\d{2})\D(\d{2}).*?(\d{1,2}:\d{2})', time_str)
                    if m:
                        time_str = f"{m.group(1)[-2:]}/{m.group(2)}/{m.group(3)} {m.group(4)}"
                    elif re.search(r'\d{1,2}:\d{2}', time_str):
                        time_str = re.search(r'(\d{1,2}:\d{2})', time_str).group(1)
                url = news.get('url', '#')
                if not url or url == '#':
                    url = '#'

                if time_str:
                    items_html.append(NEWS_ITEM_TEMPLATE.format(
                        title=title,
                        digest=digest,
                        source=source,
                        time=time_str,
                        url=url,
                    ))
                else:
                    items_html.append(NEWS_ITEM_TEMPLATE_NO_TIME.format(
                        title=title,
                        digest=digest,
                        source=source,
                        url=url,
                    ))

            if not items_html:
                items_html = ['<div class="news-card-item"><div class="title">暂无资讯</div></div>']

            sections.append(NEWS_SECTION_TEMPLATE.format(
                cls=cat["cls"],
                label=cat["label"],
                items="\n".join(items_html),
            ))

        grid_html = '<div class="news-grid">\n' + '\n'.join(sections) + '\n</div>'
        sender_name = self.config.get('push', {}).get('email', {}).get('sender_name', 'YQClaw智能投资助手')
        footer = f'<div class="news-footer">数据来源：MiniMax · DuckDuckGo · GNews　｜　{sender_name}</div>'
        return grid_html + '\n' + footer
    
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
        sender_name = self.config.get('push', {}).get('email', {}).get('sender_name', 'YQClaw智能投资助手')
        html = HTML_TEMPLATE.format(
            title="全球市场日报",
            date_str=today.strftime("%Y年%m月%d日"),
            market_rows=market_rows,
            hot_news=hot_news,
            market_review=market_review,
            calendar=calendar,
            insight=insight,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sender_name=sender_name
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
