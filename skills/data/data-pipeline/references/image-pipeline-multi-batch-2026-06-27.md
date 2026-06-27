# 图片入库多批推送实战（2026-06-27）

## 场景

用户分多批推送同一批持仓截图到飞书：

| 推送时间 | image_cache 文件数 | unique hash | pipeline 实际跑过 |
|---|---|---|---|
| 09:46~09:47 | 18 张 | 18 个 | 第一轮 10 个后台任务（跑 0949 序列前 10 张）|
| 10:02 | 9 张 | 9 个（第一轮 9:46-50 子集）| 第二轮"重跑"，9 个全部入库 |
| 10:10 | 9 张 | 9 个（第一轮 9:47-33 子集）| **第三轮，9 个全部入库** |

**关键认知：image_cache unique hash 总数（60）= 三批去重后的全集，但 pipeline 不是一次性跑完。** 仅凭"归档目录里有"不能说"全部入库"。

## 诊断方法

### Step 1: 看 image_cache 时间分布

```bash
for f in /home/pascal/.hermes/profiles/yquant/image_cache/img_*.jpg; do
  TS=$(stat -c '%y' "$f" | cut -c12-19)
  H=$(md5sum "$f" | awk '{print $1}')
  echo "$H $TS"
done | sort -k2,2
```

输出示例（看到 09:46 / 10:02 / 10:10 三个时间簇）：
```
1db53a40bf49bf8adc38742d00c3b257 09:46:48
30d6cdac9533586347f1fa54c65e66e7 09:47:33
a70a46b94a2a42c39af3ce206bffbf0f 10:02:24
27bf7c249ff5bbbbc7e47f4edcb3e93f 10:10:40
```

### Step 2: 看每批的 hash 子集

```bash
# 早 09:46~09:47（18 张）vs 10:02（9 张）vs 10:10（9 张）的 hash 差集
```

**常见模式**：
- 10:02 是 09:46 的 9 张子集（同一批的部分重推）
- 10:10 是 09:47 的 9 张子集（同一批的另一部分重推）

### Step 3: 看归档目录 + pipeline 痕迹

```bash
ARCHIVE_DIR=/home/pascal/workspace/yquant-investment/skills/data/source/smart-money/2026-06-27/image

# 归档图（已 cp 过去的）
md5sum "$ARCHIVE_DIR"/portfolio_*.jpg | awk '{print $1}' | sort -u | wc -l

# pipeline 跑过 = 留下了同名 xlsx / vision_raw
ls "$ARCHIVE_DIR"/*.xlsx | wc -l
ls "$ARCHIVE_DIR"/*vision_raw*.json | wc -l
ls "$ARCHIVE_DIR"/*vision_error*.json | wc -l
```

### Step 4: 辅助脚本

`scripts/check_pending_pipeline_runs.py` 输出决策矩阵（hash 匹配 × xlsx 痕迹）。

## 三件事必须分清

| 概念 | 含义 | 检测方法 |
|---|---|---|
| **image_cache** | 飞书推送的所有图（可能含重复推送的副本）| `ls /home/pascal/.hermes/profiles/yquant/image_cache/` |
| **归档目录** | agent 第一步 cp 过去的图（按 unique hash 去重）| `ls skills/data/source/smart-money/{date}/image/` |
| **pipeline 跑过** | 留下了同名 xlsx 和 vision_raw json | `ls skills/data/source/smart-money/{date}/image/*.xlsx` |

**反例**：
- 仅凭"归档目录里有"回复用户"全部入库"
- 看到归档 unique hash 数 == image_cache unique hash 数就说"已处理完"

## MongoDB 业务日期字段实际类型 = 字符串

`portfolio_position.position_date` / `portfolio_nav.nav_date` / `portfolio_trade.trade_date` 在 MongoDB 里**实际类型是 `str`**（如 `'2025-07-07'`），不是 BSON datetime。

**症状 1**：用 `datetime.date(2025,7,7)` 做 `\$gte` 报 `bson.errors.InvalidDocument`
**症状 2**：用 `datetime.datetime` 做范围查询 → 返回 0 行（datetime > str）
**症状 3**：从查询结果读 `.day` → AttributeError

**正确查询模板**：

```python
DATES = [f'2025-07-{d:02d}' for d in range(1,16)]
db['portfolio_position'].find({'position_date': {'$in': DATES}}, ...)

# 取日期部分用字符串切片
for r in cursor:
    day = int(r['position_date'][-2:])  # '2025-07-07' → 7
```

## OCR 噪声：全角括号 `市值（本币）`

`load_pending_confirmed.py` 按精确列名读 CSV，OCR 输出 `市值（本币）`（全角括号）时 loader KeyError，结果 `loaded=0` 静默失败。

**症状**：`Result: format=portfolio, loaded=0, nav_loaded=0, records=0  ERROR: Row 0: '市值(本币)'`

**临时修复（仅针对当天这一行）**：
```bash
sed -i 's/市值（全币）/市值(本币)/g' skills/data/source/smart-money/{date}/review_pending/<file>_pending.csv
PYTHONPATH=skills/data/data-pipeline/scripts .venv/bin/python \
  skills/data/data-pipeline/scripts/load_pending_confirmed.py \
  --csv skills/data/source/smart-money/{date}/review_pending/<file>_pending.csv \
  --confirm-all
```

**长期方案（待用户拍板）**：写 `stock_name_corrections.py` 永久映射，让 OCR 噪声自动归一化。