# TOOLS.md - Local Notes

## 邮件配置

### SMTP 设置（QQ 邮箱）
- **服务器:** smtp.qq.com
- **端口:** 465 (SSL)
- **发件人:** 532484187@qq.com
- **授权码:** <请在 QQ 邮箱设置中获取>

### 收件人
- **主邮箱:** 532484187@qq.com

## 投资系统配置

### 数据源
- AKShare: A 股/港股数据（免费）
- YFinance: 美股数据（免费）
- Binance API: 币安行情（免费）

### 推送配置
- 邮件推送
- 时间：每个交易日 08:30

### 自选股列表
- A 股：600519, 000858, 300750
- 港股：00700, 09988
- 美股：AAPL, NVDA, TSLA
- Crypto: BTC, ETH, SOL

## 常用命令

```bash
# 测试邮件发送
python3 ~/.openclaw/workspace/skills/common/utils/email/send_email.py \
  "532484187@qq.com" \
  "测试邮件" \
  "这是一封测试邮件"
```

## Telegram 配置

### Bot
- **Token**: <YOUR_TELEGRAM_BOT_TOKEN>
- **Chat ID**: 6805320916（Pascal 个人）

### 发送文件函数
```python
def telegram_send_file(token: str, chat_id: str, file_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id, "caption": caption}
        r = requests.post(url, data=data, files=files)
    return r.json()
```