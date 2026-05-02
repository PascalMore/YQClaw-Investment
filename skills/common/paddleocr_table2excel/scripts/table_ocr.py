#!/usr/bin/env python3
"""
PaddleOCR Table-to-Excel Pipeline
==================================
接收图片（Excel截图、手机照片、屏幕截图），
通过 PaddleOCR 行识别 + 产品代码锚点 + 列字段解析，
输出标准 .xlsx 文件。

关键发现（持仓表结构）：
  - 每行 OCR 文本带 (x, y, text)，产品代码（如 80PF11234）为锚点
  - 代码右侧依次出现：Wind代码、资产名称、持仓比例(0.xxxx)、
    数量(5-6位)、市值(6+位)、净值(0.xxxx)、份额(0.xxxx)、规模(7+位)
  - 行高约 45px，按 Y 聚类

依赖：PaddlePaddle 3.0.0 + PaddleOCR 2.7.3（全程离线）
"""
import sys as _sys
from pathlib import Path as _Path
_venv = _Path(__file__).parent / ".venv" / "lib" / "python3.10" / "site-packages"
if str(_venv) not in _sys.path:
    _sys.path.insert(0, str(_venv))

import cv2, numpy as np, re, warnings
from openpyxl import Workbook
warnings.filterwarnings("ignore")

from paddleocr import PaddleOCR


PRODUCT_CODES = {'80PF11234','80PF11236','80PF11238','80PF11240',
                '80PF11242','8OPF11234','80OPF11234','80PF11246','8OPF11236'}
DATE_RE = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
PCT_RE = re.compile(r'\b[01]\.\d{4,}\b')
NUM_RE = re.compile(r'\b(\d+)\b')
SZ_RE = re.compile(r'\b(\d{6}\.[A-Z]{2,4})\b')
HEADER = ['截止日期','产品名称','产品代码','Wind代码','资产名称',
          '持仓比例','数量','市值（本币）','最新净值','最新份额','最新规模']


def clean(s):
    s = str(s).strip()
    s = re.sub(r'\s+', ' ', s).strip()
    return s


class TablePreprocessor:
    """图片预处理：倾斜校正、去噪、对比度增强、去摩尔纹"""
    @staticmethod
    def deskew(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        coords = np.column_stack(np.where(gray > 0))
        if not len(coords):
            return img
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.5:
            return img
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def denoise(img):
        return cv2.fastNlMeansDenoisingColored(img, None, 8, 8, 7, 21)

    @staticmethod
    def enhance(img):
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(2.0, (8, 8)).apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    @staticmethod
    def remove_vertical_lines(img, thickness=8):
        """Remove thick vertical grid lines (from frozen columns) using morphological opening."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Detect vertical lines
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        detected = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel, iterations=3)
        # Threshold to get binary mask of vertical lines
        _, binary = cv2.threshold(detected, 30, 255, cv2.THRESH_BINARY)
        # Dilate to cover the full line thickness
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (thickness, 1))
        mask = cv2.dilate(binary, kernel, iterations=1)
        # Inpaint: fill vertical line pixels with local median
        result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
        return result

    @staticmethod
    def remove_moire(img):
        blur = cv2.GaussianBlur(img, (5, 5), 0)
        return cv2.addWeighted(img, 1.5, blur, -0.5, 0)

    def process(self, img):
        # Skip deskew: PaddleOCR is angle-tolerant and deskew can destroy image orientation
        # denoise → enhance → remove_moire (skip deskew)
        return self.remove_moire(self.enhance(self.denoise(img)))


class TableDetector:
    """基于网格线检测的表格区域定位"""
    def detect(self, img):
        """Detect table region using grid line detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 51, 5
        )
        vlines = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        )
        hlines = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        )
        grid = cv2.add(vlines, hlines)
        contours, _ = cv2.findContours(
            grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None
        return cv2.boundingRect(max(contours, key=lambda c: cv2.contourArea(c)))

    @staticmethod
    def _crop(img, rect, margin=5):
        x, y, tw, th = rect
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img.shape[1], x + tw + margin)
        y2 = min(img.shape[0], y + th + margin)
        return img[y1:y2, x1:x2]


def parse_row(cells):
    """
    以产品代码为锚点，从行的 OCR 单元格中提取字段
    cells: sorted list of (x_center, text)
    """
    combined = ' '.join(t for _, t in cells)

    # 找产品代码及其 X 位置
    code_x = None
    for x, t in cells:
        if t in PRODUCT_CODES:
            code_x = x
            break

    if code_x is None:
        return None

    # 代码右侧的所有 token
    right_tokens = []
    for x, t in cells:
        if x > code_x:
            right_tokens.extend(t.split())

    right_combined = ' '.join(right_tokens)

    # 过滤 header 关键词（冻结窗格导致 header 文本混入同行）
    HEADER_KEYWORDS = {
        '持仓比例', '数量', '市值（本币）', '最新净值', '最新份额', '最新规模',
        'Wind代码', '资产名称', '产品代码', '产品名称', '截止日期',
    }
    data_tokens = [t for t in right_tokens if t not in HEADER_KEYWORDS]
    data_combined = ' '.join(data_tokens)

    # Wind 代码
    wind = next((t for t in data_tokens if SZ_RE.match(t)), '')
    # 提取 wind 代码的数字部分用于过滤（如 '002415.SZ' -> '002415'）
    wind_digits = ''
    if wind:
        m = re.search(r'(\d{6})', wind)
        if m:
            wind_digits = m.group(1)
    # 资产名称（第一个中文词，排除产品代码）
    asset = next((t for t in data_tokens
                  if re.search(r'[一-鿿]', t)
                  and t not in PRODUCT_CODES), '')

    # 产品名称：第一个在代码左侧的中文词（出现在代码之前的"景顺灵活1号"）
    # 跳过日期格式的数字（如 "820260423" 是 "2026-04-23" 的 OCR 误读）
    product_name = ''
    for x, t in cells:
        if t in PRODUCT_CODES:
            break  # stop at code
        if re.search(r'[一-鿿]', t) and t not in HEADER_KEYWORDS:
            # Skip pure-digit tokens (likely corrupted dates like '820260423')
            if re.match(r'^\d{6,10}$', t):
                continue
            # Skip tokens starting with digits (row numbers mixed into product name)
            if re.match(r'^\d', t):
                continue
            product_name = t
    # 比例（0.xxxx，4位小数）、净值/份额（任意小数）
    RATIO_RE = re.compile(r'\b[01]\.\d{4,}\b')
    DECIMAL_RE = re.compile(r'\b\d+\.\d+\b')
    pcts_all = DECIMAL_RE.findall(data_combined)
    ratios = RATIO_RE.findall(data_combined)
    ratio = ratios[0] if ratios else ''
    # net/share: non-ratio decimals (don't start with 0 or 1 at integer part)
    others = [p for p in pcts_all if not re.match(r'^[01]\.', p)]
    net = others[0] if len(others) > 0 else ''
    share = others[1] if len(others) > 1 else ''
    # 数量（5-6 位整数）：跳过 wind 代码和纯小数 token
    qty = ''
    for tok in data_tokens:
        # Skip wind code itself
        if tok == wind_digits:
            continue
        # Skip pure decimal tokens (like '0.1169') - check isdigit BEFORE '.'
        if re.match(r'^\d+$', tok) and 4 <= len(tok) <= 6:
            qty = tok
            break
    # 市值（7+ 位整数）：跳过 wind 代码和 qty
    mkt = ''
    for tok in data_tokens:
        if tok == wind_digits or tok == qty:
            continue
        if re.match(r'^\d+$', tok) and len(tok) >= 7:
            mkt = tok
            break
    # 规模（8+ 位整数）
    scale = ''
    for tok in data_tokens:
        if tok == wind_digits or tok == qty or tok == mkt:
            continue
        if re.match(r'^\d+$', tok) and len(tok) >= 8:
            scale = tok
            break

    return {
        'wind': wind, 'asset': asset, 'product_name': product_name,
        'ratio': ratio, 'qty': qty, 'mkt': mkt,
        'net': net, 'share': share, 'scale': scale
    }


class Pipeline:
    """主流程：预处理 → 表格检测 → PaddleOCR 行识别 → 锚点解析 → Excel输出"""

    def __init__(self):
        self.preprocessor = TablePreprocessor()
        self.ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)

    def run(self, image_path, output_path=None):
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        # 先检测表格区域（用原始图像更准确）
        detector = TableDetector()
        rect = detector.detect(img)
        if rect:
            img = detector._crop(img, rect)

        # 预处理（跳过 deskew，因为 PaddleOCR 本身有角度容差，deskew 会破坏图像方向）
        img = self.preprocessor.process(img)

        tmp_crop = str(image_path) + '.crop.jpg'
        cv2.imwrite(tmp_crop, img)

        # PaddleOCR 行识别
        result = self.ocr.ocr(img, cls=True)
        lines = result[0]

        # 按 Y 坐标聚类（行高约 45px）
        rh = 72.0  # ~2591px / 36 rows ≈ 72px/row
        row_bands = {}
        for line in lines:
            pts = line[0]
            y_center = (pts[0][1] + pts[1][1] + pts[2][1] + pts[3][1]) / 4
            x_center = (pts[0][0] + pts[1][0] + pts[2][0] + pts[3][0]) / 4
            text = clean(line[1][0])
            if not text:
                continue
            bi = int(y_center / rh)
            if bi not in row_bands:
                row_bands[bi] = []
            row_bands[bi].append((x_center, text))

        # 解析
        results = []
        last_date = ''

        for bi in sorted(row_bands.keys()):
            if bi < 2:
                continue

            cells = sorted(row_bands[bi], key=lambda x: x[0])
            combined = ' '.join(t for _, t in cells)

            # 日期
            date_m = DATE_RE.search(combined)
            date_str = date_m.group(1) if date_m else last_date
            if date_m:
                last_date = date_str

            # 找产品代码
            codes = [t for x, t in cells if t in PRODUCT_CODES]
            if not codes:
                continue

            parsed = parse_row(cells)
            if parsed is None:
                continue

            for code in codes:
                results.append([
                    date_str, parsed.get('product_name', ''), code,
                    parsed['wind'], parsed['asset'],
                    parsed['ratio'], parsed['qty'], parsed['mkt'],
                    parsed['net'], parsed['share'], parsed['scale']
                ])

        # 输出 Excel
        if output_path is None:
            output_path = str(_Path(image_path).with_suffix('.xlsx'))

        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        for c_idx, col in enumerate(HEADER, 1):
            ws.cell(row=1, column=c_idx, value=col)
        for r_idx, row in enumerate(results, 2):
            for c_idx, val in enumerate(row, 1):
                if val == '' or val is None:
                    continue
                try:
                    if '.' in str(val):
                        ws.cell(row=r_idx, column=c_idx, value=float(val))
                    elif str(val).isdigit():
                        ws.cell(row=r_idx, column=c_idx, value=int(float(val)))
                    else:
                        ws.cell(row=r_idx, column=c_idx, value=str(val))
                except (ValueError, AttributeError):
                    ws.cell(row=r_idx, column=c_idx, value=str(val))
        wb.save(str(output_path))

        if _Path(tmp_crop).exists():
            _Path(tmp_crop).unlink()

        return {
            "rows": len(results),
            "columns": len(HEADER),
            "output": output_path,
            "header": HEADER
        }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="PaddleOCR 表格图片转 Excel")
    p.add_argument("--input", "-i", required=True, help="输入图片路径")
    p.add_argument("--output", "-o", help="输出 Excel 路径（默认同名的 .xlsx）")
    args = p.parse_args()
    result = Pipeline().run(args.input, args.output)
    print(f"✅ 识别完成：{result['rows']} 行 → {result['output']}")