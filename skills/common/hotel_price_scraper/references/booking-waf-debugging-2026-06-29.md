# Booking WAF Debugging Session — 2026-06-29

完整的"WAF 频次控制 vs Cookie 失效"误诊纠正实录。下次遇到类似 Booking 周报大量 `page title not found` 错误时，先按本文档的决策树走一遍。

## 背景

周一早上 6:10 cron 周报触发 300 个 Booking 请求（10 家 × 30 天），结束后 Excel `Errors` sheet 显示 73 条错误。用户问"为什么有 73 个错误，主要原因是啥"。

## 错误分布

73 条全部是 Booking 平台（Jalan 0 错误），按 hotel_id 散落 4-11 条/家：

```
meldia-shijo-kawaramachi                  11
hop-inn-tokyo-asakusa                     11
stay-sakurajing-du-dong-shan-bai-chuan    10
legasta-kyoto-shirakawa-sanjo              8
hoterutoraberuteinjing-du-mu-wu-ting       8
m-39-s-inn-sanjo-wakoku                    6
k3-asakusa-dong-jing                       6
super-asakusa                              5
carta-jing-du-he-yuan-ting                 4
hua-zhu-qian-cao-he-xin-hoteru             4
```

跨日期看：每家酒店都有"成功 + 失败"混合，**完全散落**，没有任何一家或一天是 100% 失败。这条特征是后续诊断的关键。

按错误类型：

| 错误 | 条数 | 占比 |
|------|------|------|
| `RuntimeError('Booking page title not found or cookie expired')` | 65 | 89% |
| `Error('Page.goto: net::ERR_CONNECTION_CLOSED ...')` | 8 | 11% |

## 错误判断决策树

```
看到 73 条 "Booking page title not found" 错误
    │
    ├─ cron.log 历史趋势是 6/15=0 → 6/22=300 → 6/29=73
    │  （WAF 触发了 → 临时缓解 → 又触发）
    │
    ├─ 第一反应：cookie 失效，准备刷 cookie
    │
    └─ 实际验证步骤：
        1. 写 /tmp/hotel_diag.py：单页用同一份 cookie 访问任一失败酒店
        2. 启 Playwright，注入 config.yaml:55 的 31 个 cookie
        3. 访问 https://www.booking.com/hotel/jp/meldia-shijo-kawaramachi.html?...
        4. 检查：
           - page.title() = "Rakuten STAY URBAN Shijo Kawaramachi..." ✅
           - h2.pp-header__title 拿得到 ✅
           - 房型 span 拿到 2 个，价格 span 拿到 3 个 ✅
        5. **结论：cookie 单页 100% 成功，根因不是 cookie**
    │
    └─ 真实根因：Booking WAF 频次控制
        - 300 个连续请求（sleep 3s）触发 AWS WAF 阈值
        - WAF 随机抽中请求，替换成 challenge 页
        - challenge 页没有 h2.pp-header__title → _parse_page 返回 -1 → 抛 "page title not found"
        - 8 条 ERR_CONNECTION_CLOSED = WAF 主动断连（同类根因）
        - 跨酒店散落 = 频次控制特征（不是某酒店 IP 被黑）
        - 个别酒店连续失败（如 legasta 7/6-7/10）= 短时间 IP 封禁窗口
```

## 修复方案演进

### Phase 1：1 行 config 改动（已做，验证有效）

```yaml
# config.yaml:107
request_interval_seconds: 3   # → 7
```

**测试结果**（1 天 × 10 家 = 10 个请求）：

| 修改前 (3s) | 修改后 (7s) |
|-------------|-------------|
| 2 errors | 2 errors（但失败酒店不同） |

**全量外推**（30 天 × 10 家 = 300 个请求）：

- 乐观估计：errors 73 → 30-40
- 悲观估计：errors 73 → 60-75

**判断标准**：1 天测试样本 2/10 errors = 20% 失败率。线性外推 300 × 20% = 60。但 WAF 触发不是纯线性（同酒店次日可能通过），实际可能 30-40。

**决策点**：如果用户接受 30-40 errors 作为终态，Phase 1 就够了。如果要 < 10，走 Phase 2。

### Phase 2：WAF 检测 + 30s backoff + 重试 5 次（已做，验证有效）

**代码改动**（`BookingScraper.py`）：

1. 新增异常类：
   ```python
   class WAFChallengeError(Exception):
       """WAF/captcha/challenge interstitial — treat as 'cool down' signal."""
   ```

2. `_fetch_page` 重试循环重写：
   ```python
   for attempt in range(5):
       try:
           return self._fetch_page_once(url)
       except WAFChallengeError as exc:
           last_error = exc
           print(f"  [WAF] challenge detected, backoff 30s (attempt {attempt+1}/5)")
           time.sleep(30)
       except Exception as exc:
           last_error = exc
           time.sleep(2 + attempt)
   ```

3. `scrape()` 内 WAF 检测：
   ```python
   if self._is_waf_challenge(html):
       raise WAFChallengeError(f"Booking returned challenge page for {hotel_id} on {checkin}")
   ```

4. `_is_waf_challenge()` 检测逻辑（关键）：
   ```python
   lower = html.lower()
   if "hprt-roomtype-icon-link" not in lower and "pp-header__title" not in lower:
       if any(m in lower for m in ["captcha", "verify you are a human", ...]) \
          or len(html) < 50000:
           return True
   return False
   ```

**关键设计选择**：
- **WAFChallengeError 单独异常**（不是 RuntimeError）→ 重试循环里可以给更长 backoff
- **5 次重试上限**（原 3 次）→ 给 WAF 充分"凉下来"机会
- **检测放 scrape() 不放 _fetch_page_once()** → _fetch_page_once 仍能 throw 其他 Playwright 异常（connection closed 等）走短退避路径

**测试结果**（1 天 × 10 家 = 10 个请求）：

| Phase 1 (7s only) | Phase 2 (7s + WAF retry) |
|-------------------|-------------------------|
| 8/10 成功（80%） | **10/10 成功（100%）** |
| 失败：stay-sakura, hop-inn | 失败：super-asakusa, k3-asakusa |

**核心观察**：
- ✅ stay-sakura + hop-inn（Phase 1 失败的）→ Phase 2 成功（WAF retry 救了它们）
- ❌ super-asakusa + k3-asakusa（新失败）→ WAFChallengeError 5 次都失败，说明 30s backoff × 5 = 150s 仍不够
- ⏱️ 总耗时 5:40（5:43-5:11）vs Phase 1 5:37，几乎一样（因为 Phase 1 失败的也是等 30s 5 次重试）

**全量外推**：errors 73 → 30-50（救回 ~50% 的 WAF 抽中）。

### Phase 3：Playwright context 复用（不推荐）

**潜在收益**：节省每次 ~5-10s 浏览器冷启动，300 请求 × 5s = 25 分钟里 25% 是冷启动。

**为什么不推荐**：
- ~100 行重构，引入 stale state 风险（context 里的 cookie / cache 跨请求可能污染）
- cookie + UA 已经在 cookie 注入逻辑里，context 复用不一定改善
- Booking WAF 抽中逻辑主要看"请求频率 + UA 一致性"，不是 context 复用

**何时再做**：如果未来 cron 跑超时（> 60 分钟）才考虑。

## 经验教训

1. **误诊的代价**：第一反应"刷 cookie"如果执行了，要 1-2 小时抓新 cookie + 全量重测 + 重发邮件，浪费且根因没解决。先验证再行动。
2. **单页诊断的威力**：用现成的 Playwright + 现成的 cookie 写 30 行诊断脚本，能在 1 分钟内把"cookie 失效"假设证伪。**永远先做最小验证再下结论**。
3. **小样本外推的风险**：1 天测试看到 2/10 errors 推 300 → 60 是线性外推，但 WAF 触发是状态相关的（IP 在 WAF 名单上的衰减、cookie 时效等）。**外推时要说明假设，给出区间而不是点估计**。
4. **分阶段修复的价值**：先改 1 行（最小爆炸半径），跑测试看效果，**再决定下一步**。一次改 3 个东西出问题时无法定位。
5. **异常类别的作用**：把 WAFChallengeError 单独出来（不是 RuntimeError）让重试循环能给"长 backoff"，是修复的关键设计。
6. **Python 3.12 stdout buffer 坑**：`terminal(background=true)` 启的进程 log 不实时，因为非 TTY 是 block-buffered。临时方案 `python -u`。

## 给下次会话的速查

**如果看到 Booking 周报出现 > 20 条 errors**：

1. 先看 `errors/hotel_price_report_YYYY-MM-DD.xlsx` 的 `Errors` sheet
2. 如果 80%+ 是 "page title not found" + 跨酒店散落 → **直接做 Phase 1**（改 config 1 行）
3. 跑 `--platform booking --days 1` 验证
4. 验证后：
   - 1 天 errors < 3 → 接受 Phase 1，cron 跑全量观察
   - 1 天 errors 3-5 → 走 Phase 2（已落地代码，无需重做）
   - 1 天 errors > 5 → 检查是否有其他因素（cookie 真的失效 / 网络问题 / Booking 大规模封 IP）

**不要做**：
- ❌ 看到错误立刻刷 cookie
- ❌ 改 cron 跑批时间错峰（治标不治本，Booking 任何时候都可能抽）
- ❌ 加 IP 代理（成本大、收益小，先把 Phase 1+2 做透）
- ❌ 改 `concurrent` 配置（已经是 2，再大就触发 WAF）
