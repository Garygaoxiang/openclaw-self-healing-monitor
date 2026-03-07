# 🤖 OpenClaw 全自动监控脚本+全自动浏览器控制

> 让你的 OpenClaw 永远在线，永不宕机

## ⚙️ 首次配置

使用前请修改以下文件中的路径：

### 1. clawdbot-monitor/clawdbot-monitor-self-healing.py
```python
CONFIG = {
    "chrome_launcher": r"C:\\你的路径\\chrome9222\\chrome9222.bat",
}
```

### 2. chrome9222/chrome9222.bat
```bat
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
set CHROME_DEBUG_PROFILE=C:\ChromeDebugProfile
set CHROME_ORIGINAL_PROFILE=C:\Users\你的用户名\AppData\Local\Google\Chrome\User Data\Default
```

> 把所有 `PATH\TO\...` 替换为你实际的安装路径。

![OpenClaw](https://img.shields.io/badge/OpenClaw-2026.3.2-blue)
![Platform-Windows | WSL](https://img.shields.io/badge/Platform-Windows%20%7C%20WSL-green)
![License-MIT](https://img.shields.io/badge/License-MIT-yellow)

## 🌟 简介

你是否经历过这些崩溃时刻？

- 🚨 Gateway 突然宕机，重启后配置丢失
- 🔌 Chrome 9222 端口神秘断开，排查半天
- 📡 代理 IP 变更导致 Telegram 机器人失联
- 💔 辛辛苦苦配置的插件，因为一次错误操作全部归零

**这套监控脚本就是为了解决这些问题而生的！**

它就像一个 24 小时待命的运维工程师，默默守护着你的 OpenClaw 实例。

---

## 🎯 核心功能

### 1. 🏥 健康监测
- 每 30 秒检查 Gateway 状态
- 实时监控 Telegram 连接
- 检测 Chrome 9222 调试端口

### 2. 🔧 自动修复
- 检测到配置错误时自动运行 `openclaw doctor --fix`
- 修复失败？没关系，调用 Claude Code 进行智能诊断
- 智能修复也失败？弹出窗口通知你

### 3. 🌐 代理自适应
- 自动检测可用代理（127.0.0.1 或 Windows 主机 IP）
- 代理变更？无缝切换，无需人工干预

### 4. 🍪 Cookie 同步
- 首次启动自动从真实 Chrome 复制 Cookie
- 后续复用，**免去重复登录**的痛苦
- 保持登录态持久化

### 5. 📱 Telegram 通知
- 启动成功？通知你
- 出故障了？通知你
- 自动修复了？也通知你

---

## 📁 文件结构

```
Scripts(git)/
├── clawdbot-monitor/
│   ├── clawdbot-monitor-self-healing.py   # 🌟 核心监控脚本
│   └── clawdbot-monitor.sh                # 启动脚本（可选）
├── chrome9222/
│   └── chrome9222.bat                     # Chrome 9222 启动器
├── backup-openclaw.sh                     # OpenClaw 配置备份
├── restore-openclaw.sh                    # OpenClaw 配置恢复
└── claude-fast.sh                        # Claude Code 快速调用
```

---

## 🚀 快速开始

### 准备工作

1. **确保已安装 OpenClaw**
   ```bash
   npm install -g openclaw
   ```

2. **确保 WSL 已安装**（或使用 Windows 原生 Python）

3. **获取 Telegram Bot Token**
   - 联系 @BotFather 创建机器人
   - 获取 Token 备用

### 第一步：配置脚本

编辑 `clawdbot-monitor-self-healing.py`，修改以下配置：

```python
CONFIG = {
    "gateway_port": 18789,           # OpenClaw Gateway 端口
    "check_interval": 30,            # 检查间隔（秒）
    "max_retries": 5,                # 最大重试次数
    "retry_delay": 3,                # 重试间隔（秒）
    "proxy_host": "127.0.0.1",       # 代理主机
    "proxy_port": 10808,             # 代理端口
    "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",      # 你的 Telegram ID
    "telegram_token": "YOUR_TELEGRAM_TOKEN",       # Bot Token
}
```

### 第二步：设置 Chrome 9222

#### 方式一：使用脚本自动启动（推荐）

直接运行 `chrome9222.bat`，它会：
1. 关闭现有 Chrome 进程
2. 复制你的登录 Cookie（首次）
3. 启动带调试端口的 Chrome

```cmd
F:\Scripts\chrome9222\chrome9222.bat
```

#### 方式二：手动启动

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="C:\ChromeDebugProfile" ^
  --no-first-run ^
  --no-default-browser-check
```

### 第三步：启动监控

```bash
# 方式一：直接运行
python F:\Scripts\clawdbot-monitor\clawdbot-monitor-self-healing.py

# 方式二：使用启动脚本
bash F:\Scripts\clawdbot-monitor\clawdbot-monitor.sh
```

### 第四步：验证

打开 Telegram，你会收到：

```
✅ OpenClaw Gateway 已启动
🔧 调试 Chrome (9222) 已就绪
```

---

## ⚙️ 进阶配置

### Telegram 通知自定义

修改消息内容：

```python
# 自定义通知消息
def send_telegram(message):
    # 这里可以自定义消息格式、表情等
    pass
```

### 自动启动（Windows 计划任务）

1. 打开「任务计划程序」
2. 创建基本任务
3. 触发器：开机时
4. 操作：启动程序 → `python.exe`
5. 参数：`F:\Scripts\clawdbot-monitor\clawdbot-monitor-self-healing.py`

### 代理配置

如果使用代理：

```python
CONFIG = {
    "proxy_host": "your.proxy.com",  # 代理地址
    "proxy_port": 7890,              # 代理端口
}
```

---

## 🔍 故障排查

### Q: 脚本提示 "Chrome 9222 启动超时"

**A**: 确保 Chrome 9222 已正确启动，检查端口：

```cmd
curl http://127.0.0.1:9222/json
```

### Q: Telegram 消息发不出去

**A**: 检查 Token 和 Chat ID 是否正确，以及网络能否访问 Telegram API。

### Q: 监控脚本自己崩溃了

**A**: 查看日志文件 `monitor.log`，搜索错误信息。

---

## 🧠 工作原理

### 监控循环

```
┌─────────────────────────────────────┐
│         每 30 秒检查一次             │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│    Gateway /health 返回 200?         │
└─────────────────┬───────────────────┘
                  │
        ┌────────┴────────┐
        ▼                 ▼
       是                否
        │                 │
        ▼                 ▼
   "一切正常"        "开始自愈流程"
        │                 │
        │          ┌──────┴──────┐
        │          ▼              ▼
        │     doctor --fix    检查配置
        │          │              │
        │          ▼              ▼
        │       成功?           错误?
        │          │              │
        │    "已修复"        "调用 Claude"
        │          │              │
        │          └──────┬──────┘
        │                 ▼
        │          "通知人工处理"
        │                 │
        └─────────────────┘
```

### Cookie 同步机制

```
首次启动
    │
    ▼
检测 C:\ChromeDebugProfile 是否存在
    │
    ├─ 不存在 → 从真实 Chrome 复制全部 Cookie
    │
    └─ 已存在 → 直接复用（跳过复制，省时间）
```

---

## 📝 更新日志

### v1.0.1
- 新增 Claude Code 自动修复
- 优化代理检测逻辑
- 增加更多日志

### v1.0.0
- 初始版本
- 基础监控 + 自动修复
- Telegram 通知

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📜 许可证

MIT License - 自由使用，修改，分发

---

**made with ❤️ for OpenClaw users**

如果你觉得这套脚本对你有帮助，欢迎 Star ⭐
