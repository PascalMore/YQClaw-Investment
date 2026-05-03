"""
OCR 后处理校正器
================
利用"同产品同日期，字段不变性"原理校正 OCR 误读。

不变性规则：
- 同一产品（如 80PF11234）、同一日期，产品名称固定
- 同一产品、同一日期，最新净值固定
- 同一产品、同一日期，最新份额固定

OCR 易误读字符映射：
- F ↔ E（80PF vs 80PE）
- 景 ↔ 暑（景顺 vs 暑顺）
- 寒 ↔ 赛（寒武纪 vs 赛武纪）
- 灵 ↔ 显（灵活 vs 显活）
"""
import re
from typing import Any


# ============================================================
# 1. OCR 字符形近替换
# ============================================================

# 常见 OCR 误读映射（形近字）
OCR_CHAR_REPLACEMENTS = {
    '暑': '景',  # 景/暑
    '赛': '寒',  # 寒/赛
    '显': '灵',  # 灵/显
    '话': '活',  # 活/话（部分）
}

# 产品代码 F/E 混淆
CODE_FE_REPLACEMENTS = {
    '80PE': '80PF',
    '8OPE': '80PF',
    '80PF': '80PF',  # 正确的不变
}

# Wind 代码 OCR 误读后缀映射
# .US 股票代码常被误读为 XXXXIS, XXXXUS 等
WIND_CODE_SUFFIX_FIX = {
    'IS': 'US',  # AMZNIS → AMZN.US, MSETIS → MSFT.US 等
    'US': 'US',
    'SZ': 'SZ',
    'SH': 'SH',
    'HK': 'HK',
}

# 知名美股代码 OCR 误读映射（常见 ticker 误读）
KNOWN_US_TICKER_FIXES = {
    'AMZNIS': 'AMZN.US',
    'MSETIS': 'MSFT.US',
    'AAPLUS': 'AAPL.US',
    'TSLAUS': 'TSLA.US',
    'GOOGUS': 'GOOG.US',
    'NVDAUS': 'NVDA.US',
    'NFLXUS': 'NFLX.US',
    'MSFTUS': 'MSFT.US',
}

# Wind代码 → 资产名称映射（用于填充 OCR 完全丢失的名称）
WIND_CODE_TO_ASSET_NAME = {
    'AMZN.US': '亚马逊',
    'MSFT.US': '微软',
    'AAPL.US': '苹果',
    'TSLA.US': '特斯拉',
    'GOOG.US': '谷歌',
    'NVDA.US': '英伟达',
    'NFLX.US': '奈飞',
    'META.US': 'Meta',
    'AMD.US': 'AMD',
    'INTC.US': '英特尔',
    'CRM.US': 'Salesforce',
    'ORCL.US': '甲骨文',
    'PYPL.US': 'PayPal',
    'ADBE.US': 'Adobe',
    'TXN.US': '德州仪器',
}

# 资产名称 OCR 误读映射
ASSET_NAME_FIXES = {
    '谷歌': '谷歌',
}


def apply_char_corrections(text: str) -> str:
    """对单个文本应用字符校正。"""
    if not text or not isinstance(text, str):
        return text
    
    result = text
    for wrong, correct in OCR_CHAR_REPLACEMENTS.items():
        result = result.replace(wrong, correct)
    
    # 产品代码 F/E 校正
    for wrong, correct in CODE_FE_REPLACEMENTS.items():
        if result == wrong:
            result = correct
            break
        # 处理中间出现的情况（如 "80PE11234" → "80PF11234"）
        if wrong in result:
            result = result.replace(wrong, correct)
    
    return result


def correct_asset_name(name: str) -> str:
    """校正资产名称中的 OCR 误读。"""
    return apply_char_corrections(name)


def correct_product_code(code: str) -> str:
    """校正产品代码中的 OCR 误读。"""
    return apply_char_corrections(code)


def correct_wind_code(code: str) -> str:
    """校正 Wind 代码中的 OCR 误读。"""
    if not code:
        return code
    
    code = str(code).strip()
    
    # 先检查已知的美股 ticker 误读
    if code in KNOWN_US_TICKER_FIXES:
        return KNOWN_US_TICKER_FIXES[code]
    
    # 检查是否像 .US 后缀被误读
    # 例如 AMZNIS → AMZN.US
    for wrong_suffix, correct_suffix in WIND_CODE_SUFFIX_FIX.items():
        if code.endswith(wrong_suffix) and len(code) >= 4:
            # 尝试修复：去掉错误后缀，添加正确后缀
            base = code[:-len(wrong_suffix)] if wrong_suffix else code
            if base.isalpha() or base.isalnum():
                # 检查是否像美股代码（2-5个字母）
                if len(base) >= 2 and len(base) <= 5 and base.isupper():
                    return f"{base}.{correct_suffix}"
    
    return code


def clean_numeric(text: Any) -> Any:
    """清理数字中的 OCR 误读字符（如 79566L → 79566）。"""
    if text is None or text == '':
        return text
    text_str = str(text).strip()
    # 去除末尾的字母（如 L, O, S 等误读）
    if text_str and text_str[-1] in ('L', 'O', 'S', 'l', 'o', 's'):
        # 检查前面是否确实是数字
        core = text_str[:-1]
        if core.isdigit():
            return core
    # 去除中间的误读字符
    text_str = re.sub(r'(\d)[lLOOS](\D)', r'\1\2', text_str)
    text_str = re.sub(r'(\D)[lLOOS](\d)', r'\1\2', text_str)
    return text_str


def correct_quantity(value: Any) -> Any:
    """校正数量字段。"""
    return clean_numeric(value)


def correct_decimal_point(text: Any, field_name: str) -> Any:
    """
    校正小数点丢失问题。
    
    常见情况：
    - '11' → '1.1' (净值，正常范围 0.5~3.0)
    - '123' → '1.23' (净值)
    - '209090909.' → '209090909' (去掉尾随小数点)
    
    Args:
        text: 原始值
        field_name: 字段名 ('nav', 'share', 'holding_ratio')
    """
    if text is None or text == '' or text == 'nan':
        return text
    
    text_str = str(text).strip()
    
    if field_name in ('nav', 'latest_nav', 'holding_ratio'):
        # 净值/比例：应该在 0~5 范围
        # 如果是 2-4 位整数且不含点，可能是丢失了小数点
        if text_str.isdigit() and len(text_str) >= 2:
            # 尝试在合适位置加小数点
            # 规则：如果数值 >= 10，则认为小数点丢失
            # 常见情况：1.1 → 11, 0.95 → 095(不太可能)
            val = int(text_str)
            if field_name in ('nav', 'latest_nav'):
                # 净值通常在 0.5~5 范围
                if 10 <= val <= 50:  # 11-50 可能是 1.1-5.0
                    return str(val / 10)
                elif val > 50:
                    return str(val / 100)
            elif field_name == 'holding_ratio':
                # 比例应该在 0~1
                if val >= 100:  # 可能是 0.xx 被漏了点
                    return '0.' + text_str[-2:] if len(text_str) >= 2 else text_str
    
    elif field_name in ('share', 'latest_share'):
        # 份额：去掉尾随小数点
        if text_str.endswith('.'):
            return text_str[:-1]
        # 如果是纯数字字符串结尾有误读字符
        if text_str and text_str[-1] in ('L', 'l'):
            core = text_str[:-1]
            if core.isdigit():
                return core
    
    return text


# ============================================================
# 2. 产品代码白名单（已知有效的产品代码）
# ============================================================

KNOWN_PRODUCT_CODES = {
    '80PF11234',
    '80PF11236',
    '80PF11238',
    '80PF11240',
    '80PF11242',
    '8OPF11234',  # 注意：这是 OCR 可能读成 80PF 的原始码
}


def fuzzy_match_code(ocr_code: str, whitelist: set = None) -> str:
    """
    模糊匹配产品代码。
    
    如果 OCR 代码不在白名单，尝试 Levenshtein 距离匹配。
    """
    if whitelist is None:
        whitelist = KNOWN_PRODUCT_CODES
    
    if ocr_code in whitelist:
        return ocr_code
    
    # 计算编辑距离，找最接近的
    best_match = ocr_code
    best_dist = float('inf')
    
    for known in whitelist:
        dist = levenshtein_distance(ocr_code, known)
        if dist < best_dist and dist <= 2:  # 允许最多2个编辑距离
            best_dist = dist
            best_match = known
    
    return best_match


def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的编辑距离。"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]


# ============================================================
# 3. 利用不变性规则进行行间校正
# ============================================================

def correct_by_invariant(
    records: list[dict],
    date: str,
    product_code: str
) -> dict:
    """
    利用不变性规则校正记录。
    
    同一产品、同一日期的记录：
    - product_name 应该一致
    - latest_nav 应该一致
    - latest_share 应该一致
    
    取出现最多的值作为正确值。
    """
    # 筛选同日期同产品的记录
    same_records = [
        r for r in records
        if str(r.get('position_date', '')) == str(date)
        and str(r.get('product_code', '')) == str(product_code)
    ]
    
    if len(same_records) <= 1:
        return None  # 没有可参照的记录
    
    corrections = {}
    
    # 统计 product_name
    names = [r.get('product_name') for r in same_records if r.get('product_name')]
    if names:
        corrections['product_name'] = most_common(names)
    
    # 统计 latest_nav
    navs = [r.get('latest_nav') for r in same_records if r.get('latest_nav') is not None]
    if navs:
        corrections['latest_nav'] = most_common(navs)
    
    # 统计 latest_share
    shares = [r.get('latest_share') for r in same_records if r.get('latest_share') is not None]
    if shares:
        corrections['latest_share'] = most_common(shares)
    
    return corrections if corrections else None


def most_common(values: list, n: int = 3) -> Any:
    """
    返回出现最多的值。
    n: 考虑前 n 个出现最多的值。
    """
    if not values:
        return None
    
    from collections import Counter
    counter = Counter(values)
    return counter.most_common(n)[0][0]


# ============================================================
# 4. 主校正流程
# ============================================================

def post_correct_position_records(records: list[dict]) -> list[dict]:
    """
    对持仓记录进行后处理校正。
    
    流程：
    1. 字符校正（景→景，80PE→80PF）
    2. 产品代码白名单匹配
    3. 利用不变性规则校正（需要多行数据）
    
    Args:
        records: 原始 OCR 记录
        
    Returns:
        校正后的记录
    """
    if not records:
        return records
    
    # 按日期和产品代码分组
    grouped: dict[tuple, list[dict]] = {}
    for rec in records:
        key = (str(rec.get('position_date', '')), str(rec.get('product_code', '')))
        grouped.setdefault(key, []).append(rec)
    
    # 统计所有唯一的产品代码和日期
    all_dates = set()
    all_codes = set()
    for rec in records:
        all_dates.add(str(rec.get('position_date', '')))
        all_codes.add(str(rec.get('product_code', '')))
    
    # 第一步：字符级校正
    for rec in records:
        # 校正 product_name
        if rec.get('product_name'):
            rec['product_name'] = correct_asset_name(rec['product_name'])
        
        # 校正产品代码
        if rec.get('product_code'):
            rec['product_code'] = correct_product_code(rec['product_code'])
            rec['product_code'] = fuzzy_match_code(rec['product_code'])
        
        # 校正数量（清理数字末尾误读字符如 L）
        for field in ('quantity', 'market_value'):
            if rec.get(field):
                cleaned = clean_numeric(rec[field])
                if cleaned != rec[field]:
                    rec[field] = cleaned
        
        # 校正净值和份额的小数点
        for field in ('latest_nav', 'latest_share'):
            if rec.get(field):
                corrected = correct_decimal_point(rec[field], field)
                if corrected != rec[field]:
                    rec[field] = corrected
        
        # 校正 Wind 代码
        if rec.get('asset_wind_code'):
            corrected = correct_wind_code(rec['asset_wind_code'])
            if corrected != rec['asset_wind_code']:
                rec['asset_wind_code'] = corrected
        
        # 校正资产名称
        if rec.get('asset_name'):
            corrected = correct_asset_name(rec['asset_name'])
            if corrected != rec['asset_name']:
                rec['asset_name'] = corrected
        
        # 如果资产名称为空，尝试从 Wind 代码推断
        if not rec.get('asset_name') or rec['asset_name'] == '':
            wind_code = rec.get('asset_wind_code', '')
            if wind_code and wind_code in WIND_CODE_TO_ASSET_NAME:
                rec['asset_name'] = WIND_CODE_TO_ASSET_NAME[wind_code]
    
    # 第二步：利用不变性规则校正（同日期同产品）
    for (date, code), same_records in grouped.items():
        if len(same_records) <= 1:
            continue
        
        # 收集各字段出现最多的值
        counters = {
            'product_name': {},
            'latest_nav': {},
            'latest_share': {},
        }
        
        for rec in same_records:
            for field in counters:
                val = str(rec.get(field, '')) if rec.get(field) else ''
                if val:
                    counters[field][val] = counters[field].get(val, 0) + 1
        
        # 用众数替换每条记录
        for field, counter in counters.items():
            if counter:
                correct_val = max(counter, key=counter.get)
                for rec in same_records:
                    rec[field] = correct_val
    
    return records


def post_correct_basic_info(records: list[dict]) -> list[dict]:
    """
    校正 basic_info 记录。
    """
    for rec in records:
        if rec.get('product_name'):
            rec['product_name'] = correct_asset_name(rec['product_name'])
        if rec.get('product_code'):
            rec['product_code'] = correct_product_code(rec['product_code'])
            rec['product_code'] = fuzzy_match_code(rec['product_code'])
    return records


def post_correct_nav(records: list[dict]) -> list[dict]:
    """
    校正 NAV 记录。
    """
    for rec in records:
        if rec.get('product_code'):
            rec['product_code'] = correct_product_code(rec['product_code'])
            rec['product_code'] = fuzzy_match_code(rec['product_code'])
    return records


# ============================================================
# 5. 完整 Pipeline 入口
# ============================================================

def correct_all(normalized: dict) -> dict:
    """
    对所有 normalized 数据进行后处理校正。
    
    Args:
        normalized: {
            'basic_info': [...],
            'nav': [...],
            'position': [...]
        }
        
    Returns:
        校正后的 normalized
    """
    result = {
        'basic_info': post_correct_basic_info(normalized.get('basic_info', [])),
        'nav': post_correct_nav(normalized.get('nav', [])),
        'position': post_correct_position_records(normalized.get('position', [])),
    }
    return result
