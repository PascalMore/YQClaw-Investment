"""
图片 → Excel Pipeline
使用 RapidOCR 识别图片中表格，输出扁平 DataFrame 并保存为 Excel

V11: 直接按行验证（Y坐标分组后验证每行）
- 分行后，每行按 X 排序
- 验证行是否有效：第一个元素是日期，且有 >= 5 个元素
- 清理日期中的行号前缀
"""
import re
from pathlib import Path
from collections import defaultdict

import pandas as pd
from rapidocr_onnxruntime import RapidOCR


class PortfolioTableOCR:
    """使用 RapidOCR 识别持仓表格图片，输出扁平 DataFrame"""

    COLUMNS = ["截止日期", "产品名称", "产品代码", "Wind代码", "资产名称",
               "持仓比例", "数量", "市值(本币)", "最新净值", "最新份额", "最新规模"]

    # 已知产品代码
    KNOWN_PRODUCT_CODES = {'80PF11234', '80PF11236', '80PF11238', '80PF11240',
                          '80PF11242', '8OPF11234'}

    # 表头关键词（过滤整行）
    HEADER_KEYWORDS = {'截止日期', '产品名称', '产品代码', 'Wind代码', '资产名称',
                      '持仓比例', '数量', '市值（本币）', '市值(本币)', '最新净值', '最新份额', '最新规模'}

    # UI 元素关键词
    SKIP_KEYWORDS = {'Excel', '文件', '开始', '插入', '页面布局', '公式', '数据',
                     '审间', '视图', '开发工具', 'PDF', '帮助', 'OfficePLUS',
                     '同花顺', 'Wind', '操作说明', 'PDF工具箱', '福昕PDF',
                     '共享', '司', '团', 'Yaqiang Mao', '®'}

    def __init__(self):
        self.ocr = RapidOCR()

    def ocr_image(self, image_path: str) -> list:
        """OCR 单张图片，返回 (text, x, y) 列表"""
        result, elapse = self.ocr(image_path)
        if not result:
            return []
        return [(line[1].strip(), line[0][0][0], line[0][0][1]) for line in result if line[1].strip()]

    def parse_portfolio_table(self, ocr_data: list) -> pd.DataFrame:
        """
        解析策略：
        1. 按 Y 坐标分行（容差35px）
        2. 每行按 X 坐标排序
        3. 过滤表头词和 UI 元素
        4. 验证：第一个元素是日期（干净格式），且产品代码在正确位置
        """
        if not ocr_data:
            raise ValueError("No text found")

        # Step 1: 按 Y 坐标分行
        rows_by_y = defaultdict(list)
        for text, x, y in ocr_data:
            y_key = round(y / 35) * 35
            rows_by_y[y_key].append((text, x))

        # Step 2: 排序并过滤
        valid_rows = []
        for y_key in sorted(rows_by_y.keys()):
            row = sorted(rows_by_y[y_key], key=lambda t: t[1])
            texts = [t[0] for t in row]

            # 过滤
            filtered = self._filter_row(texts)
            if len(filtered) < 5:
                continue

            # 验证：日期在第一个位置，产品代码在第三个位置（索引2）
            if self._is_valid_data_row(filtered):
                valid_rows.append(filtered)

        if not valid_rows:
            raise ValueError("No valid data rows extracted")

        print(f"  Found {len(valid_rows)} valid rows")

        df = pd.DataFrame(valid_rows, columns=self.COLUMNS)
        return df

    def _filter_row(self, texts: list) -> list:
        """过滤行中的表头词、UI元素、行号"""
        filtered = []
        for text in texts:
            # 跳过表头关键词
            if text in self.HEADER_KEYWORDS:
                continue
            # 跳过 UI 关键词
            if text in self.SKIP_KEYWORDS:
                continue
            # 跳过单个字母
            if re.match(r'^[A-Z]$', text):
                continue
            # 跳过短数字（行号，如 1, 2, 3）
            if re.match(r'^\d{1,3}$', text):
                continue
            # 跳过特殊行号标识（如 D7, L, F43 等）
            if re.match(r'^[A-Z]\d+$', text) or re.match(r'^[A-Z]\d+[A-Z]?$', text):
                continue
            filtered.append(text)
        return filtered

    def _is_valid_data_row(self, texts: list) -> bool:
        """
        验证是否是有效数据行
        条件：
        - 第一个元素是干净日期（格式：2026-04-23）
        - 产品代码在索引2的位置
        """
        if len(texts) < 5:
            return False

        # 检查第一个元素是否是干净日期
        if not re.match(r'^202[0-9]-\d{2}-\d{2}$', str(texts[0])):
            return False

        # 检查索引2是否是产品代码
        if texts[2] not in self.KNOWN_PRODUCT_CODES:
            return False

        return True

    def process_images(self, image_dir: str, output_path: str = None) -> pd.DataFrame:
        """处理目录下所有图片，合并结果并保存 Excel"""
        image_dir = Path(image_dir)
        image_files = sorted(image_dir.glob("*.jpg")) + sorted(image_dir.glob("*.png"))

        if not image_files:
            raise ValueError(f"No images found in {image_dir}")

        all_rows = []
        for img_path in image_files:
            try:
                print(f"Processing {img_path.name}...")
                ocr_data = self.ocr_image(str(img_path))
                df = self.parse_portfolio_table(ocr_data)
                if len(df) > 0:
                    all_rows.append(df)
                    print(f"  ✅ {len(df)} rows")
                else:
                    print(f"  ⚠️ 0 rows")
            except Exception as e:
                print(f"  ❌ {img_path.name}: {e}")

        if not all_rows:
            raise ValueError("No data extracted from any image")

        combined_df = pd.concat(all_rows, ignore_index=True)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            combined_df.to_excel(output_path, index=False)
            print(f"\n✅ Saved to {output_path}")

        return combined_df


def main():
    import argparse
    parser = argparse.ArgumentParser(description="图片 → Excel 持仓数据")
    parser.add_argument("image_dir", help="图片目录")
    parser.add_argument("-o", "--output", help="输出 Excel 路径")

    args = parser.parse_args()

    ocr = PortfolioTableOCR()
    df = ocr.process_images(args.image_dir, args.output)
    print(f"\n总计: {len(df)} 条持仓记录")


if __name__ == "__main__":
    main()