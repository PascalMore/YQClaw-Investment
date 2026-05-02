---
name: paddleocr_table2excel
description: 基于 PaddleOCR 的离线表格图片识别技能。接收本地图片（Excel截图、手机拍摄表格照片、屏幕截图），自动进行图片预处理（去噪、增强对比度、去摩尔纹），然后用 PaddleOCR 行识别引擎 + 产品代码锚点解析还原表格结构，最终输出标准 .xlsx Excel 文件，保留原表格列顺序、数字格式、日期格式。用于：持仓数据图片 OCR、图片转 Excel、表格结构识别。触发时机：用户发送图片并要求识别为 Excel/CSV/表格。
---

# PaddleOCR Table-to-Excel Skill

## 环境路径

- **虚拟环境**：`skills/common/paddleocr_table2excel/.venv`
- **Python 解释器**：`.venv/bin/python`
- **系统 Python**：3.10.12（系统无 3.9，用 virtualenv 创建隔离环境）
- **所有依赖隔离在 .venv 内**，不污染全局环境

## 技术栈

- **PaddlePaddle**: 3.0.0（CPU 推理）
- **PaddleOCR**: 2.7.3
- **Paddlex**: 3.5.1
- **OpenCV**: 4.6.0（contrib-python）
- **openpyxl**: 3.1.5
- 全程离线运行，不调用任何云端 API

## 目录结构

```
skills/common/paddleocr_table2excel/
├── .venv/                     # Python 虚拟环境（完全隔离）
│   ├── bin/python             # 专用 Python 解释器
│   ├── bin/pip
│   └── lib/python3.10/site-packages/  # 所有依赖库
├── scripts/
│   └── table_ocr.py           # 主模块（Pipeline + 预处理 + OCR + 解析 + Excel）
└── SKILL.md                   # 本文件
```

## 使用方式

### 命令行调用

```bash
cd /home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel

# 处理图片生成 Excel
.venv/bin/python scripts/table_ocr.py \
  -i /path/to/portfolio_008.jpg \
  -o /tmp/result.xlsx

# 输出示例：
# ✅ 识别完成：16 行 → /tmp/result.xlsx
```

### Python API

```python
import sys
venv = "/home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel/.venv/lib/python3.10/site-packages"
if venv not in sys.path:
    sys.path.insert(0, venv)
sys.path.insert(0, "/home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel/scripts")

from table_ocr import Pipeline

pipe = Pipeline()
result = pipe.run("input.jpg", "output.xlsx")
# result: {"rows": 16, "columns": 11, "output": "output.xlsx",
#          "header": ["截止日期","产品名称","产品代码","Wind代码","资产名称",
#                     "持仓比例","数量","市值（本币）","最新净值","最新份额","最新规模"]}
print(result)
```

### Agent 内部调用

```python
import subprocess
venv_python = "/home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel/.venv/bin/python"
script = "/home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel/scripts/table_ocr.py"

result = subprocess.run(
    [venv_python, script, "-i", image_path, "-o", output_path],
    capture_output=True, text=True
)
print(result.stdout)
```

## 预处理流程

1. **去噪**：NL-Means 降噪（`cv2.fastNlMeansDenoisingColored`）
2. **对比度增强**：CLAHE 直方图均衡化（Lab 色彩空间）
3. **去摩尔纹**：高斯模糊 + 叠加混合
4. **跳过 deskew**：PaddleOCR 本身有角度容差，deskew 会破坏图像方向导致 OCR 失败
5. **表格区域检测**：自适应阈值 + 网格线检测 + 轮廓定位

## 解析策略

- **PaddleOCR 行识别**：每行文本识别为 (x, y, text) 三元组
- **行聚类**：Y 坐标每 45px 一个 band
- **产品代码锚点**：`80PF11234`、`80PF11236` 等为关键锚点
- **列分配**：按 X 坐标将 OCR 文本分配到对应列（日期/产品代码/Wind/资产/比例/数量/市值/净值/份额/规模）
- **字段提取规则**：
  - 持仓比例：`\b[01]\.\d{4,}\b`（如 0.0291，4位小数，避免误匹配 1.1）
  - 数量：第一个 4-6 位整数
  - 市值：第一个 6+ 位整数
  - 净值/份额：第二/第三个 `\b[01]\.\d{4,}\b`
  - 规模：第一个 7+ 位整数
- **Header 行过滤**：跳过含"持仓比例"/"市值（本币）"/"最新净值"等关键词的行

## 输出格式

- `.xlsx` 文件，openpyxl 生成
- 表头行：截止日期 / 产品名称 / 产品代码 / Wind代码 / 资产名称 / 持仓比例 / 数量 / 市值（本币） / 最新净值 / 最新份额 / 最新规模
- 数字字段自动识别：整数或浮点
- 日期字段保留 YYYY-MM-DD 格式

## 当前精度

- ✅ 产品代码（80PF11234 等）：正确识别
- ✅ 持仓比例（0.xxxx）：正确提取
- ✅ Wind 代码（如 002415.SZ）：正确提取
- ✅ 资产名称（英伟达、谷歌等）：正确提取
- ✅ 最新规模（230000000）：正确提取
- ⚠️ 数量字段：部分串位（如 0291 缺少前导，002594 被识别为市值）
- ⚠️ 市值字段：部分串位（如 600585 被误识别为数量）
- ⚠️ 日期：header band 无日期，依赖后续 data band 的日期

## 已知局限

- 持仓表因 freeze header，每两个 HTML 行对（header+data）交错排列
- 产品代码在 header band，数据在 data band，需要配对
- 部分数量字段（4位整数）与 Wind 代码（6位数字）可能混淆
- "英伟达"类资产名在 X2000-2600 范围可能被截断为"英伟"

## 部署状态

- ✅ 虚拟环境：`.venv` 已创建（Python 3.10.12 virtualenv）
- ✅ PaddlePaddle 3.0.0 + PaddleOCR 2.7.3 + Paddlex 3.5.1
- ✅ 预处理管道（去噪/增强/摩尔纹，skip deskew）
- ✅ 表格区域检测（自适应阈值 + 网格线）
- ✅ PaddleOCR 行识别（381-404 行/图）
- ✅ 列锚点解析（16 行有效数据/图）
- ✅ Excel 输出（.xlsx，11 列）
- ✅ 全程离线，不调用云端 API
- ✅ 依赖全部隔离在 skills/common/paddleocr_table2excel/.venv 内
- ⏳ 精度微调中（数量/市值偶有串位，header-data 配对待优化）