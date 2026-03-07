# 🤖 OpenClaw 全自动监控脚本

> 让你的 OpenClaw 永远在线，永不宕机

![OpenClaw](https://img.shields.io/badge/OpenClaw-2026.3.2-blue)
![Platform-Windows | WSL](https://img.shields.io/badge/Platform-Windows%20%7C%20WSL-green)
![License-MIT](https://img.shields.io/badge/License-MIT-yellow)

## ⚠️ 前置要求

在部署之前，请确保满足以下条件：

### 1. OpenClaw 已安装
```bash
# 全局安装 OpenClaw
npm install -g openclaw

# 验证安装
openclaw --version
```

### 2. Python 环境
```bash
# 确保 Python 已安装（用于运行监控脚本）
python --version

# 建议使用 Python 3.8+
```

### 3. WSL 环境（推荐）
本脚本设计为在 WSL 中运行，Windows 和 WSL 需要互通。

### 4. Telegram Bot
- 联系 @BotFather 创建机器人
- 获取 Bot Token

---

## 🚀 快速开始（自动部署）

### 方式一：克隆仓库

```bash
# 克隆到本地
git clone https://github.com/Garygaoxiang/openclaw-self-healing-monitor.git
cd openclaw-self-healing-monitor

# 编辑配置文件
# 1. clawdbot-monitor/clawdbot-monitor-self-healing.py
# 2. chrome9222/chrome9222.bat

# 启动监控
python clawdbot-monitor/clawdbot-monitor-self-healing.py
```

### 方式二：手动复制

将脚本复制到你的 Scripts 文件夹，修改配置后运行。

---

## ⚙️ 配置说明

### 1. clawdbot-monitor/clawdbot-monitor-self-healing.py

```python
CONFIG = {
    "gateway_port": 18789,           # OpenClaw Gateway 端口
    "check_interval": 30,            # 检查间隔（秒）
    "max_retries": 5,               # 最大重试次数
    "proxy_host": "127.0.0.1",      # 代理主机
    "proxy_port": 10808,            # 代理端口
    "telegram_chat_id": "YOUR_CHAT_ID",      # 你的 Telegram ID
    "telegram_token": "YOUR_BOT_TOKEN",       # Bot Token
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

## 🎯 核心功能

### 1. 🏥 健康监测
- 每 30 秒检查 Gateway 状态
- 实时监控 Telegram 连接
- 检测 Chrome 9222 调试端口

### 2. 🔧 自动修复
- 检测到配置错误时自动运行 `openclaw doctor --fix`
- 修复失败？调用 Claude Code 进行智能诊断
- 智能修复也失败？弹出窗口通知你

### 3. 🌐 代理自适应
- 自动检测可用代理
- 代理变更？无缝切换

### 4. 🍪 Cookie 同步
- 首次启动自动复制 Chrome Cookie
- 免去重复登录

### 5. 📱 Telegram 通知
- 启动/故障/修复 都会通知

---

## 📁 文件结构

```
├── clawdbot-monitor/
│   ├── clawdbot-monitor-self-healing.py   # 核心监控脚本
│   └── clawdbot-monitor.sh                # 启动脚本
├── chrome9222/
│   └── chrome9222.bat                     # Chrome 9222 启动器
├── backup-openclaw.sh                     # 配置备份
├── restore-openclaw.sh                    # 配置恢复
└── claude-fast.sh                       # Claude 快速调用
```

---

## 🔍 故障排查

### Q: 脚本提示 "Chrome 9222 启动超时"

```cmd
# 检查端口
curl http://127.0.0.1:9222/json
```

### Q: Telegram 消息发不出去

- 检查 Token 和 Chat ID 是否正确
- 检查网络能否访问 Telegram API

---

## 📝 更新日志

### v1.0.1
- 新增 Claude Code 自动修复
- 优化代理检测

### v1.0.0
- 初始版本

---

**made with ❤️ for OpenClaw users**

---

## 🌐 代理配置（可选）

如果你的网络需要代理才能访问外网（如 Telegram、Jina API 等），需要配置代理。

### 方式一：系统代理

```python
CONFIG = {
    "proxy_host": "127.0.0.1",   # 代理地址
    "proxy_port": 10808,          # 代理端口（Clash 默认 7890/10808）
}
```

### 方式二：无需代理

如果不需要代理，注释掉或留空：

```python
CONFIG = {
    "proxy_host": "",
    "proxy_port": 0,
}
```

---

## 🖥️ Windows + WSL 部署说明

本脚本设计为 **Windows + WSL** 架构：

### 架构图

```
┌─────────────────┐
│   Windows       │
│  ┌───────────┐  │
│  │ Chrome 9222│  │  ← 调试端口
│  │ Telegram Bot │  │  ← 消息推送
│  │ 代理 (Clash) │  │  ← 网络代理
│  └───────────┘  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     WSL         │
│  ┌───────────┐  │
│  │ OpenClaw  │  │  ← Gateway
│  │ 监控脚本   │  │  ← 健康监测
│  └────────└───────────────────┘  │
─┘
```

### WSL 访问 Windows 资源

- Chrome 9222: `http://127.0.0.1:9222`
- 代理: `http://127.0.0.1:10808` (或你的代理端口)

### 常用代理端口参考

| 软件 | 默认端口 |
|------|----------|
| Clash | 7890 / 10808 |
| V2Ray | 10808 |
| Shadowrocket | 1080 |
| Surge | 8889 |

---

## 📱 Telegram Bot 设置

### 1. 创建 Bot

1. 打开 Telegram，搜索 @BotFather
2. 发送 `/newbot`
3. 按提示设置名称和用户名
4. 获取 Token

### 2. 获取 Chat ID

1. 搜索 @userinfobot
2. 发送任意消息
3. 获取 ID

### 3. 配置

```python
CONFIG = {
    "telegram_token": "123456:ABC-DEF1234ghIkl-zyx57W2vT1EXAMPLE",
    "telegram_chat_id": "123456789",
}
```

---

## 🔧 常见问题

### WSL 无法访问 Chrome 9222

```bash
# 在 Windows 上确认 Chrome 9222 正在运行
curl http://127.0.0.1:9222/json

# 在 WSL 中测试
curl http://$(hostname -I | awk '{print $1}' | cut -d. -f1-3).1:9222/json
```

### 代理无法连接

- 确认代理软件正在运行
- 确认端口号正确
- 测试代理连通性：`curl -x http://127.0.0.1:10808 https://api.telegram.org`
