# 🤖 OpenClaw 全自动监控脚本 + GUI 面板

> 让你的 OpenClaw 永远在线，永不宕机

![OpenClaw](https://img.shields.io/badge/OpenClaw-2026.3-blue)
![Platform-Windows | WSL](https://img.shields.io/badge/Platform-Windows%20%7C%20WSL-green)
![License-MIT](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ 功能总览

| 功能 | 脚本 | 说明 |
|------|------|------|
| 自愈监控（命令行） | `clawdbot-monitor-self-healing.py` | 后台守护，自动重启 Gateway |
| GUI 监控面板 | `clawdbot-monitor-gui.py` | 桌面悬浮窗，实时日志 + 状态卡片 |
| WebUI 仪表盘 | `clawdbot-monitor-self-healing-webui.py` | 浏览器访问的监控面板 |
| 简易健康检查 | `clawdbot-monitor.sh` | Bash 脚本，轻量版 |

---

## ⚠️ 前置要求

- OpenClaw 已安装（WSL 环境）
- Python 3.8+（Windows）
- WSL 环境（用于执行 openclaw 命令）
- Telegram Bot（联系 @BotFather 创建）
- **网络魔法**（代理）：用于访问 Telegram 等外网

---

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/Garygaoxiang/openclaw-self-healing-monitor.git
cd openclaw-self-healing-monitor
```

---

## 🖥️ 方式一：GUI 桌面面板（推荐）

**功能特性：**
- 系统托盘悬浮窗（可拖拽，无标题栏）
- 实时日志显示（支持 ANSI 颜色，贴近终端效果）
- Gateway / Chrome 端口状态卡片
- 定时任务表格（按下次执行时间排序）
- 自动运行自愈监控子进程

**依赖安装：**
```bash
pip install customtkinter requests urllib3
```

**启动：**
```bash
python clawdbot-monitor/clawdbot-monitor-gui.py
```

**打包为 .exe：**
```bash
pip install pyinstaller
cd clawdbot-monitor
build-gui.bat
# 输出：dist\ClawdbotMonitor\ClawdbotMonitor.exe
```

**配置（编辑 `clawdbot-monitor-gui.py` 顶部 CONFIG）：**
```python
CONFIG = {
    "gateway_port": 18789,
    "chrome_debug_port": 9315,       # 你的 Chrome 调试端口
    "chrome_cron_port": 9316,        # 你的 Chrome Cron 端口
    "chrome_extension": r"YOUR_EXTENSION_PATH",
    "minimax_api_key": "YOUR_MINIMAX_API_KEY",
    "telegram_token": "YOUR_TELEGRAM_TOKEN",
    ...
}
```

---

## 🌐 方式二：WebUI 仪表盘

**功能特性：**
- 浏览器访问的监控面板（Bootstrap 5 / Mazer 风格）
- Gateway 状态、网络连通性、Chrome 端口、API 额度
- Telegram / Feishu Channel 状态
- Plugins / Skills 列表
- Cron 任务倒计时
- 实时日志查看

**依赖安装：**
```bash
pip install flask requests urllib3
```

**启动：**
```bash
python clawdbot-monitor/clawdbot-monitor-self-healing-webui.py
# 访问 http://localhost:18790
```

**配置（环境变量或直接编辑脚本）：**
```bash
set MINIMAX_API_KEY=YOUR_MINIMAX_API_KEY
set TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_TOKEN
set TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID
```

---

## ⚙️ 方式三：命令行自愈监控

**依赖安装：**
```bash
pip install requests
```

**启动：**
```bash
python clawdbot-monitor/clawdbot-monitor-self-healing.py
```

**配置（编辑 `clawdbot-monitor-self-healing.py` 顶部 CONFIG）：**
```python
CONFIG = {
    "gateway_port": 18789,
    "check_interval": 30,
    "proxy_host": "127.0.0.1",
    "proxy_port": 10808,              # 你的代理端口
    "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID"),
    "chrome_extension": r"YOUR_EXTENSION_PATH",
    "chrome_launcher": r"YOUR_CHROME_BAT_PATH",
    "claude_api_url": "https://api.minimaxi.com/anthropic",
    "claude_api_key": "YOUR_CLAUDE_KEY",
}
```

**自愈链：**
1. 检测 Gateway 断线
2. 自动重启 Gateway
3. 运行 `openclaw doctor --fix`
4. 调用 Claude Code 智能修复
5. 弹出交互修复窗口
6. 发送 Telegram 通知

---

## 🌐 代理配置

**Telegram 需要代理才能使用！**

```python
CONFIG = {
    "proxy_host": "127.0.0.1",   # Windows 代理地址
    "proxy_port": 10808,          # 代理端口
}
```

| 代理软件 | 常用端口 |
|----------|---------|
| Clash | 7890 / 10808 |
| V2Ray | 1080 |
| Surge | 8889 |

---

## 📱 Telegram Bot 设置

1. **创建 Bot**：@BotFather → /newbot → 获取 Token
2. **获取 Chat ID**：向 @userinfobot 发消息
3. **填入配置**（环境变量或直接写入脚本）

---

## 📁 文件结构

```
├── clawdbot-monitor/
│   ├── clawdbot-monitor-self-healing.py      # 自愈监控（命令行后台）
│   ├── clawdbot-monitor-self-healing-webui.py # WebUI 仪表盘服务器
│   ├── clawdbot-monitor-gui.py               # GUI 桌面面板
│   ├── clawdbot-monitor.sh                   # 简易 Bash 监控
│   ├── clawdbot-monitor.spec                 # PyInstaller 打包配置
│   ├── build-gui.bat                         # GUI 打包脚本
│   └── webui/
│       └── index.html                        # WebUI 前端页面
├── chrome9222/
│   └── chrome9222.bat
├── backup-openclaw.sh
├── restore-openclaw.sh
└── claude-fast.sh
```

---

## ❓ 常见问题

### Q: GUI 启动报错 `ModuleNotFoundError: customtkinter`？
```bash
pip install customtkinter
```

### Q: WebUI 报错 `ModuleNotFoundError: flask`？
```bash
pip install flask
```

### Q: Telegram 发不出去？
检查代理是否开启，端口是否正确。

### Q: Gateway 一直在重启？
Gateway 进程名是 `node`（非 `openclaw`），监控已改用 TCP socket 检测端口 18789，无需担心进程名问题。

### Q: Chrome 端口超时？
```cmd
curl http://127.0.0.1:9315/json
```

### Q: GUI 日志显示乱码？
确保系统已安装 Python 3.8+ 且 Windows 终端支持 UTF-8。

---

## 🤝 交流 & 支持

- 🐛 问题反馈：https://github.com/Garygaoxiang/openclaw-self-healing-monitor/issues
- ⭐ 喜欢的话，点个 Star 吧！
- 🔄 欢迎 Fork 和 PR

---

**made with ❤️ for OpenClaw users**
