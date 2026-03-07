# 🤖 OpenClaw 全自动监控脚本

> 让你的 OpenClaw 永远在线，永不宕机

![OpenClaw](https://img.shields.io/badge/OpenClaw-2026.3.2-blue)
![Platform-Windows | WSL](https://img.shields.io/badge/Platform-Windows%20%7C%20WSL-green)
![License-MIT](https://img.shields.io/badge/License-MIT-yellow)

## ⚠️ 前置要求

- OpenClaw 已安装
- Python 3.8+
- WSL 环境
- Telegram Bot（联系 @BotFather 创建）
- **网络魔法**（代理）：用于访问 Telegram、Jina 等外网

---

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/Garygaoxiang/openclaw-self-healing-monitor.git
cd openclaw-self-healing-monitor

# 修改配置文件
# 1. clawdbot-monitor/clawdbot-monitor-self-healing.py
# 2. chrome9222/chrome9222.bat

# 启动
python clawdbot-monitor/clawdbot-monitor-self-healing.py
```

---

## ⚙️ 配置说明

### 1. clawdbot-monitor/clawdbot-monitor-self-healing.py

```python
CONFIG = {
    "gateway_port": 18789,
    "check_interval": 30,
    "max_retries": 5,
    "proxy_host": "127.0.0.1",   # 你的代理地址
    "proxy_port": 10808,          # 你的代理端口
    "telegram_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID",
    "chrome_launcher": r"C:\\你的路径\\chrome9222\\chrome9222.bat",
}
```

### 2. chrome9222/chrome9222.bat

```bat
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
set CHROME_DEBUG_PROFILE=C:\ChromeDebugProfile
set CHROME_ORIGINAL_PROFILE=C:\Users\你的用户名\AppData\Local\Google\Chrome\User Data\Default
```

---

## 🌐 代理配置（重点！）

**Telegram 需要网络魔法才能使用！**

在 Windows 上开启代理软件（如 Clash、V2Ray 等），然后配置：

```python
CONFIG = {
    "proxy_host": "127.0.0.1",   # WSL 中访问 Windows 代理的地址
    "proxy_port": 10808,          # 代理端口（Clash 默认 10808，V2Ray 默认 1080）
}
```

### 常见代理端口

| 软件 | 端口 |
|------|------|
| Clash | 7890 / 10808 |
| V2Ray | 1080 |
| Surge | 8889 |

---

## 📱 Telegram Bot 设置

1. **创建 Bot**：@BotFather → /newbot
2. **获取 Chat ID**：@userinfobot 发消息获取
3. **填入配置**

---

## 🎯 核心功能

- 🏥 健康监测（30秒检查 Gateway）
- 🔧 自动修复（doctor --fix + Claude Code）
- 🌐 代理自适应
- 🍪 Cookie 同步
- 📱 Telegram 通知

---

## 📁 文件结构

```
├── clawdbot-monitor/
│   ├── clawdbot-monitor-self-healing.py
│   └── clawdbot-monitor.sh
├── chrome9222/
│   └── chrome9222.bat
├── backup-openclaw.sh
├── restore-openclaw.sh
└── claude-fast.sh
```

---

## ❓ 常见问题

### Q: Telegram 发不出去？

检查代理是否开启，端口是否正确。

### Q: Chrome 9222 超时？

```cmd
curl http://127.0.0.1:9222/json
```

---

**made with ❤️ for OpenClaw users**

---

## 🤝 交流 & 支持

- 🐛 问题反馈：https://github.com/Garygaoxiang/openclaw-self-healing-monitor/issues
- ⭐ 喜欢的话，点个 Star 吧！
- 🔄 欢迎 Fork 和 PR

---

**如果这个项目帮到了你，欢迎分享给更多 OpenClaw 用户！**

made with ❤️ for OpenClaw users
