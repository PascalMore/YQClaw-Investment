---
name: hotel_price_scraper
description: 每周一抓取 Booking 和 Jalan 目标酒店未来 30 天大床房（ダブル）和双床房（ツイン）最低价，合并输出 Excel 并通过邮件发送；用于酒店价格监控、周报附件生成和价格抓取失败排查。
---

# Hotel Price Scraper

## 触发条件

使用本技能处理以下任务：

- 每周一自动抓取酒店价格走势。
- 查询 Booking、Jalan 指定酒店未来 30 天**大床房和双床房**最低价。
- 生成酒店价格 Excel 周报并邮件发送。
- 排查酒店价格抓取、cookie 过期、平台页面解析失败等问题。

## 目标酒店（10 家）

| # | hotel_key | 酒店名 | Booking | Jalan |
|---|-----------|--------|---------|-------|
| 1 | legasta_shirakawa | ホテルレガスタ京都白川三条 | ✅ | ✅ |
| 2 | ms_sanjo_wakoku | エムズホテル三条WAKOKU | ✅ | ✅ |
| 3 | stay_sakura_higashiyama | ステイサクラ京都東山三条 | ✅ | ✅ |
| 4 | rakuten_urban_shijo | 楽天ステイアーバン四条河原町 | ✅ | ❌ |
| 5 | carta_gion | カルタホテル京都祇園 | ✅ | ❌ |
| 6 | travertin_kiyamachi | ホテルトラベルティン京都木屋町 | ✅ | ❌ |
| 7 | waka_asakusa_wakokoro | 若・浅草和心ホテル | ✅ | ❌ |
| 8 | super_hotel_asakusa | スーパーホテル浅草 | ✅ | ❌ |
| 9 | other_space_asakusa | OTHER SPACE Asakusa | ✅ | ❌ |
| 10 | hop_inn_tokyo_asakusa | Hop Inn Tokyo Asakusa | ✅ | ❌ |

## 输入

核心输入是目标酒店配置文件：

`~/.openclaw/workspace-yquant/skills/common/hotel_price_scraper/config.yaml`

配置应包含：

- 查询参数：`days_ahead`、`nights`、`adults`、`children`、`rooms`、`currency`。
- 酒店列表：每个酒店的 `hotel_key`、展示名和各平台 ID。
- 平台 cookie：Jalan/Booking 使用 requests session cookie。

邮件配置从以下文件读取：

`~/.openclaw/workspace-yquant/skills/.env`

必需环境变量：

- `EMAIL_SENDER`
- `EMAIL_PASSWORD`
- `EMAIL_RECEIVERS`（多个收件人用逗号分隔）

## 房型规则

每次抓取同时收集两种房型：

| room_category | 匹配关键词（不区分大小写） |
|---------------|-------------------------|
| `double` | ダブル、double |
| `twin` | ツイン、twin |

- 匹配优先级：先检查 twin，再检查 double
- 每种房型在同一家酒店同一天取**最低价**
- 不匹配任何关键词的房型自动跳过

## 输出

每次运行输出一个 Excel 文件和一封邮件。

Excel 文件：

`output/hotel_price_report_YYYY-MM-DD.xlsx`

Sheet：

- `Summary`：交叉对比表（hotel_name × checkin_date → booking_double/twin, jalan_double/twin 最低价）。
- `Booking`：Booking 原始标准化记录（含 room_category 列）。
- `Jalan`：Jalan 原始标准化记录（含 room_category 列）。
- `Errors`：单平台、单酒店、单日期失败记录。
- `RunMeta`：运行元数据、配置摘要和统计。

邮件：

- 主题：`【YQuant】酒店价格周报 YYYY-MM-DD`
- 正文：酒店数、有效报价数、错误数、错误摘要。
- 附件：统一 Excel 文件。

## 依赖环境

Python 依赖：

```bash
pip install pandas openpyxl requests beautifulsoup4 python-dotenv pyyaml
```

> Trip.com 相关的 selenium 依赖已不再是必需（第一版不含 Trip 平台）。

## 使用方式

### 每周抓取并发送邮件

```bash
cd /home/pascal/.openclaw/workspace-yquant/skills/common/hotel_price_scraper
python3 run.py --config config.yaml --env /home/pascal/.openclaw/workspace-yquant/skills/.env --output-dir output --days 30 --send-email
```

### 只运行单个平台

```bash
python3 run.py --config config.yaml --platform booking --days 30
python3 run.py --config config.yaml --platform jalan --days 30
python3 run.py --config config.yaml --platform all --days 30
```

支持平台：`jalan`、`booking`、`all`

### crontab

每周一 06:10 CST 运行：

```cron
10 6 * * 1 cd /home/pascal/.openclaw/workspace-yquant/skills/common/hotel_price_scraper && /usr/bin/python3 run.py --config config.yaml --env /home/pascal/.openclaw/workspace-yquant/skills/.env --output-dir output --days 30 --send-email >> logs/cron.log 2>&1
```

## 操作原则

- 邮件凭据不得写入脚本或配置，只能读取 `skills/.env`。
- 单平台失败不应中断全局任务；记录错误后继续其他平台。
- **每次请求间隔 3 秒**（baseline；不要改大）。Booking WAF 抽中由 WAFChallengeError fail-fast 处理（见下方 P1），sleep 调大反而拖慢 baseline。调度器并发上限为 2。
- Jalan 和 Booking 使用 `requests.Session` 维持 cookie。
- 不自动绕过验证码，不使用高并发代理池。
- 输出 Excel 必须所有平台合并到一个文件。

## ⚠️ Pitfalls — Booking 抓取常见错误

### P1. "Booking page title not found" 几乎都是 WAF 频次控制，不是 cookie 失效

**症状**：周报里 Booking 平台出现 N 条 `RuntimeError('Booking page title not found or cookie expired')` 错误（典型 N=20-300），跨 10 家酒店随机散落，可能有局部连续（如某酒店连续 5 天都失败）。

**❌ 误诊**：第一反应是"Booking cookie 过期了，要刷新 cookie"。

**✅ 正确诊断**：
1. 写个单页诊断脚本，用同一份 cookie 单独访问任一失败 URL（不需要 cron 自动化，临时 `playwright sync_api` 起一个浏览器 + `page.goto` + `page.title()` + `page.locator("h2.pp-header__title").count()` 即可）。
2. **如果单页能拿到 title + h2 + 房型 + 价格 → cookie 没问题**。真实根因是 Booking WAF/反爬在批量请求中随机抽中请求，替换成 challenge 页。
3. 真正的 cookie 失效特征是：**所有酒店都失败**（包括单页测试），且错误一致。**跨酒店随机散落失败** = WAF 频次控制。

**根因**：Booking Playwright 抓取 300 次连续请求（10 家 × 30 天），sleep 太短（3s）触发 AWS WAF 频次阈值，WAF 替换返回 challenge 页（含 `captcha` / `verify you are a human` / `checking your browser` 关键词），`h2.pp-header__title` 拿不到 → 抛 "page title not found"。

**错误分类（统计样本：73 个错误）**：

| 错误类别 | 占比 | 根因 |
|---------|------|------|
| `page title not found` | ~89% | WAF challenge 页替换，h2 selector 拿不到 |
| `net::ERR_CONNECTION_CLOSED` | ~11% | WAF 主动断连 |

**修复（最终采用方案 A — 2026-06-29 落地状态）**：

**❌ 反例：不要把 sleep 调到 7s + WAF 重试 5 次**。听起来更"稳"，但实测（2026-06-29）导致全量 600 请求 91 分钟 0 产物（被 kill）。原因：sleep baseline 翻倍 + 5×30s backoff 累积 = 单 WAF 抽中请求等 2.5 分钟，30%-50% 抽中率下 600 请求花 60+ 分钟在 sleep。

**✅ 正确做法（方案 A）**：

1. `config.yaml`: `request_interval_seconds: 3`（保持原状）
2. `BookingScraper`: 加 WAF 检测 + 30s backoff + **重试 2 次**（不是 5 次）= 1 WAF-aware retry + 1 fast retry
3. WAF challenge 检测后 fail-fast，**不要等 5 次救不回来的请求**

**核心 trade-off**：

- WAFChallengeError 重试 5 次 = 救不回大多数 challenge（实测 5/5 仍失败）
- 重试 2 次 = 救回一部分，剩下的标 WAFChallengeError 直接记入 Errors 表
- sleep 7s = 即使 0% 抽中率 baseline 也从 30 分钟涨到 70 分钟
- sleep 3s + fail-fast = 30 分钟 baseline，errors 30-100（和原状持平），可观测性提升

**实现要点**（已落地 2026-06-29）：

1. 新增 `WAFChallengeError` 异常类（区别于通用 `RuntimeError`）
2. `_fetch_page_once` 返回后检测 challenge 信号（HTML 里无 `hprt-roomtype-icon-link` + 长度 < 50KB + 含 challenge 关键词）→ raise `WAFChallengeError`
3. `_fetch_page` 重试循环：`for attempt in range(2)`，`except WAFChallengeError` 走 30s backoff 1 次（`except Exception` 走原 2+attempt 秒短退避）
4. `run.py` 入口加 `sys.stdout.reconfigure(line_buffering=True)`（P2 修复）

**关键预测 / 验证**：

| 测试规模 | Phase 1 (sleep 7s) | Phase 2 (5 retries) | 方案 A (3s + 2 retries) |
|---------|-------------------|--------------------|-----------------------|
| 1 天 10 请求 | errors 2 (80% 成功率) | errors 2 (明确 WAFChallengeError) | errors 9 (90% WAF, IP 累积) |
| 全量 30 天 600 请求 | ~60 errors, 70 分钟 | **91 分钟 0 产物（kill）** | ~50-100 errors, 30-40 分钟 |

**1 天测试 ≠ 全量表现**。WAF 抽中率是 **IP 累积效应**：同 IP 当天累积跑 2-3 次后抽中率从 20% 涨到 80-90%。1 天测试无法预测全量。**任何 sleep / retry 调整后必须做全量验证再上线**。

**验证方法**：跑 `--platform booking --days 1`（10 个请求），errors 期望 < 5。如果 > 5 说明还有别的因素。

**反例（不要做）**：
- 看到错误立刻去刷 cookie → 不解决根因
- 一次改 sleep + 重试 + context 复用 3 个东西 → 无法判断哪个生效
- 把 `WAFChallengeError` 和 `RuntimeError` 混在一起 → 失去"长 backoff 仅给 WAF"的能力

### P2. Python stdout 在非 TTY 是 block-buffered，cron/background 跑时 log 不实时

**症状**：用 `terminal(background=true, notify_on_complete=true)` 或 crontab 启 `run.py` 后，log 文件长期为空（0 字节），进程在跑但看不到任何 print 输出。本会话（2026-06-29）90+ 分钟跑批因这个原因完全不可观测。

**根因**：Python 3.12 默认 stdout 是 line-buffered，但当 stdout 不是 TTY（被 `>` / `tee` / pipe 重定向时）会变成 block-buffered，4KB 或进程退出才 flush。

**解决（2026-06-29 已落地）**：`run.py` 入口加 `sys.stdout.reconfigure(line_buffering=True)`，try/except 兼容旧版 Python：

```python
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass  # Python < 3.7 or already-closed
```

外加所有 `print(...)` 加 `flush=True`（特别是 WAFChallengeError 触发时的进度日志）。

**诊断方法**：跑命令后立刻 `wc -c < logfile` 看大小。如果长期 0 字节 → 100% 是 block-buffer 问题。如果有 1-2 字节但很慢 → 也可能是同问题（line-buffer 但 spawn 慢）。

### P3. Playwright 启动开销是隐性时间成本

每次 `_fetch_page_once` 都 `p.chromium.launch() + new_context + new_page + close`，单次 ~5-10s。300 个请求 × 5s 启动 = 25 分钟里 25% 是浏览器冷启动。

**当前选择**：不优化。Playwright context 跨请求复用（Phase 3）能省时间但引入 stale state 风险，性价比低。如果未来 cron 跑超时，再考虑。

## 参考文档
## 开发测试

```bash
cd /home/pascal/workspace/yquant-investment/skills/common/hotel_price_scraper
python3 -m pytest tests
python3 run.py --platform booking --days 1
python3 run.py --platform all --days 1
```

## ⚠️ 重要 Pitfall — 2026-06-29 WAF 排查实战教训

**完整记录**：`skills/common/hotel_price_scraper/INVESTIGATION_2026-06-29.md`（177 行 / 7.7KB）

### Pitfall A：Booking WAF 抽中率是 IP 累积效应，不是单次 sleep 决定

- 早晨冷启动：抽中率 20-30%（正常）
- 同 IP 当天累积跑 2-3 次后：抽中率可达 80-90%
- 24-48h IP 冷却后回落
- **含义**：errors 数不能简单"调 sleep 改"，要接受 50-100/300 是常态
- **不是 cookie 失效**（cookie 单页访问 100% 成功，cookie 不是根因）

### Pitfall B：Python 3.12 stdout block-buffer bug

- cron/tee 看不到实时输出（log 0 字节）
- 修复：`run.py` 入口加 `sys.stdout.reconfigure(line_buffering=True)`（try/except 兼容旧版）+ print 加 `flush=True`
- **已修复**：`run.py` 现状已包含 `sys.stdout.reconfigure` + 入口 try/except

### Pitfall C：WAFChallengeError retry 上限不能太高

- 5 次 × 30s = 150s 死循环救不回大多数 challenge（Phase 2 测试：super-asakusa / k3-asakusa 5 次都失败）
- 正确做法：fail-fast（1-2 次重试），不要为"可能救回来"等 2.5 分钟/请求
- **已实施**：方案 A 改造后，WAFChallengeError 重试上限 = 2（含 1 次 30s 退避）

### 排查流程（如果下次再遇到 errors 突增）

1. **不要刷 cookie**（cookie 单独访问 100% 成功）
2. **看 cron.log 末尾**，统计 WAFChallengeError vs RuntimeError vs ERR_CONNECTION_CLOSED
3. **看失败是否集中在某家酒店** → 临时加 `config.yaml` 的 `hotels[].platforms.booking = ""` 跳过
4. **写 hotel_diag.py 单页诊断**（用同一份 cookie + 同一 URL，看是否拿得到 h2.pp-header__title）
5. **等 24-48h IP 冷却**（不一定要立刻修）

## crontab

每周一 06:10 CST 运行：
- su-scraper 重构设计：`REFACTOR_DESIGN.md`
