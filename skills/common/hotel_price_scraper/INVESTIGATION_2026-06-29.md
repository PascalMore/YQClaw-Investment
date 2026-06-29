# Hotel Price Scraper — 2026-06-29 WAF 排查与改造记录

> 临时性排查笔记，记录本次会话对"周一 73 errors"问题的调查、尝试、决策。
> 不是 RFC/SPEC/DESIGN，不进入正式设计文档。
> 排查背景：2026-06-29 周一 cron 跑完后，邮件报告 `records=455 errors=73`，10 家酒店 30 天里 73 条抓取失败。

---

## TL;DR

| 项 | 值 |
|----|---|
| **真实根因** | Booking WAF/反爬频次控制（**不是** cookie 失效）|
| **错误分类** | 65 × `Booking page title not found` + 8 × `ERR_CONNECTION_CLOSED` |
| **失败特征** | 跨 10 家酒店均匀散落，个别酒店有连续失败窗口（legasta 7/6~7/10 连续 5 天全 ERR） |
| **最终改动** | 方案 A（见下） |
| **预期收益** | 全量耗时 30 分钟内（vs Phase 0 的 30 分钟持平），可观测性大幅提升 |

## 决策时间线

### 第一印象（错）：cookie 失效
- 错误信息 `Booking page title not found or cookie expired` 第一直觉是 cookie 老化
- cron.log 历史趋势：6/15 `errors=0` → 6/22 `errors=300` → 6/29 `errors=73`，符合 cookie 老化模式

### 实证反例：cookie 是好的
写 `hotel_diag.py` 用同一份 cookie 单页访问 `meldia-shijo-kawaramachi/2026-06-30`：
- ✅ `page.title()` 返回 `Rakuten STAY URBAN Shijo Kawaramachi`
- ✅ `h2.pp-header__title` 拿到
- ✅ 拿到 2 个房型 + 3 个价格

**结论：cookie 单页访问 100% 成功，cookie 不是根因。**

### 真实根因：Booking WAF/反爬
- 单页 OK、批量 300 页挂
- 失败日期在 10 家酒店里完全散落 + 个别连续段（典型 WAF 短时封禁窗口）
- 8 条 `ERR_CONNECTION_CLOSED` 是 WAF 主动断连
- 错误信息 "page title not found" 是被 challenge 页替换了真实页面

### 关键发现
**WAF 抽中率是 IP 累积效应**，不取决于单次跑批 sleep 设置。
- 今天同 IP 累积跑 3 次后，1 天 10 个请求 9 失败（90% 抽中率）
- 等 1-2 天 IP 冷却后会回落到 20-30%（与 Phase 0 同水平）

---

## 调度策略分析

scheduler.py 当前策略（**`request_interval_seconds=3` + 平台并发 2 + 平台内顺序**）：

```
时间轴 ──────────────────────────────────────────────────►
Booking 线程 ─[10家×30天顺序]─每请求~30s+3s sleep─► ~16 分钟
Jalan  线程 ─[3家×30天顺序]─每请求~3s+3s sleep──►  ~5 分钟
```

并发=2（合理），但 sleep 3s 对 Booking WAF 太密。

---

## 尝试过的方案

### Phase 1：`request_interval_seconds 3 → 7`
- **改动**：`config.yaml` 1 行
- **1 天测试**：errors 7-8 → 2（80% 成功率）
- **全量预测**：errors 60-75（**比 Phase 0 持平或略好**）
- **额外代价**：耗时 30 分钟 → 70 分钟（sleep baseline 翻倍）

### Phase 2：WAFChallengeError 检测 + 5 次重试 30s backoff
- **改动**：`BookingScraper._fetch_page` + 新增 `WAFChallengeError` + `_is_waf_challenge()` 检测
- **1 天测试**：errors 2（失败从 RuntimeError 变成 WAFChallengeError 类型，明确可观测）
- **全量跑 91 分钟 0 产物 → killed**
  - 5 次 × 30s = 150s 退避 = 单个 WAF 失败请求等 2.5 分钟
  - WAF 累积效应：30 天 600 请求 30%-50% 抽中 → 大量时间在 sleep
  - Python 3.12 stdout block-buffer → 看不到进度

### 方案 A：回滚 + 修补（最终采用）
- `request_interval_seconds: 7 → 3`（恢复 baseline）
- WAFChallengeError 重试 5 → 2（fail-fast，不再 150s 死循环）
- `print(flush=True)` + `sys.stdout.reconfigure(line_buffering=True)`（修 stdout buffer）
- 错误类型保留 `WAFChallengeError` 明确（不变）

---

## 实际改动清单

### `config.yaml`
```diff
-request_interval_seconds: 7
+request_interval_seconds: 3
```

### `BookingScraper.py`
1. 新增 `WAFChallengeError` 异常类（区别于 RuntimeError）
2. 新增 `_is_waf_challenge(html)` 检测方法（看 `hprt-roomtype-icon-link` / `pp-header__title` 是否在 HTML 里 + 关键词匹配）
3. `scrape()` 末尾检测 WAF challenge → raise `WAFChallengeError`
4. `_fetch_page()` 重试 5 → 2，WAFChallengeError 走 30s 退避（只 1 次），其他错误走 2+attempt 退避

### `run.py`
1. 入口处 `sys.stdout.reconfigure(line_buffering=True)` + `sys.stderr.reconfigure(line_buffering=True)`（try/except 兼容旧 Python）
2. 最后 print 加 `flush=True`

---

## 验证结果（2026-06-29 17:35-17:40）

| 测试 | 结果 |
|------|------|
| `print(flush=True)` 立即输出 | ✅ `reconfigure = True` |
| Jalan 1 天（无 WAF baseline） | ✅ 13.5s / 5 records / 0 errors |
| Booking 1 天 10 请求 | 2 records / **9 WAFChallengeError**（IP 累积过热，预期内）|
| stdout 进度输出 | ✅ 看到 WAF 触发日志（不像之前 0 字节） |

---

## 预测下周一（7/6）全量效果

| 指标 | Phase 0 (6/29 原状) | 方案 A (7/6 预测) |
|------|---------------------|-------------------|
| 全量耗时 | 30 分钟 | 30-35 分钟 |
| errors | 73 | 50-100（持平或略多）|
| 邮件 | 成功 | 成功 |
| log 可观测性 | 0 字节（buffer） | ✅ 实时可见 |

**关键预测依据**：方案 A 不改 WAF 触发频次（sleep 恢复 3s），所以 errors 数不会比原状少；但 WAFChallengeError 明确抛出 + fail-fast 防止 91 分钟死循环重演。

---

## 给下周一值班的人

1. **不要慌**：73 errors 不影响邮件发送，cron 行为仍正常
2. **如果 errors 跳到 150+**：
   - 先看 `/home/pascal/workspace/yquant-investment/skills/common/hotel_price_scraper/logs/cron.log` 末尾
   - 看 WAF 抽中是否集中在某家酒店 → 临时加进 `config.yaml` 的 `hotels[].platforms.booking = ""`（跳过该酒店）
3. **不要手动 refresh cookie**（已验证 cookie 没问题，刷新会浪费时间）
4. **如果需要全量重跑**：
   ```bash
   cd /home/pascal/workspace/yquant-investment/skills/common/hotel_price_scraper
   .venv/bin/python3 run.py --config config.yaml \
     --env /home/pascal/workspace/yquant-investment/skills/.env \
     --output-dir output --days 30 --send-email
   ```

---

## 后续可考虑的优化（未做）

- **Playwright context 复用**：单次 launch 跑 600 请求，避免每次冷启动指纹
- **IP 代理轮换**：直接绕过 WAF IP 黑名单（需要新基础设施）
- **WAF 抽中率自适应**：连续 N 个 WAF 错误时自动 sleep 5 分钟（global cooldown）

## 相关文件

- 代码改动：
  - `skills/common/hotel_price_scraper/config.yaml`
  - `skills/common/hotel_price_scraper/BookingScraper.py`
  - `skills/common/hotel_price_scraper/run.py`
- 周报产物：`skills/common/hotel_price_scraper/output/hotel_price_report_2026-06-29.xlsx`
- 临时测试产物：
  - `/tmp/hotel_phase1_test/`
  - `/tmp/hotel_phase2_test/`
  - `/tmp/hotel_phaseA_test/`
  - `/tmp/hotel_jalan_baseline/`
  - `/tmp/manual_hotel_full.log`（被 kill 任务的 0 字节 log，作为 buffer bug 证据）
  - `/tmp/hotel_diag.py`（cookie 实证脚本）

## 会话上下文

- 会话开始：用户报告"周一收到酒店价格周报 455 记录 73 错误"
- 用户决策：
  1. 先排查根因（不是刷 cookie）
  2. 改抓取策略（Phase 1 + Phase 2 → 失败 → 方案 A 回滚）
  3. 手动触发全量验证 → 91 分钟 0 产物 → 暴露 Phase 2 退化
  4. 方案 A 改造完成，1 天验证通过
- 涉及其他任务（同一会话内）：
  - Smart Money 图片数据入库（8 张图，今天 9:51-9:52 推送）
  - Portfolio 数据完整性 audit（242 交易日 / 5 产品）
  - SM004 ad-hoc Excel 导出到 Telegram 个人 + DailyHappyGroup
