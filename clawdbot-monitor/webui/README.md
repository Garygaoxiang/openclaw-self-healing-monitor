# Clawdbot Gateway Monitor WebUI

基于Mazer风格的Bootstrap 5监控仪表盘

## 功能特性

- ✅ **Gateway状态** - 实时监控Gateway运行状态
- 🌐 **网络状态** - Proxy/直连检测、IP地址显示
- 📱 **Channel状态** - Telegram/Feishu连接状态
- 🧩 **Chrome调试** - 9315/9316端口状态
- 💰 **API额度** - MiniMax模型额度查询
- 🔌 **Plugins/Skills** - 插件和技能列表
- ⏰ **Cron任务** - 定时任务及倒计时
- 📋 **实时日志** - 监控日志查看

## 启动方式

```bash
# 进入目录
cd F:\Scripts\clawdbot-monitor

# 启动WebUI (默认端口18790)
python clawdbot-monitor-self-healing-webui.py

# 指定端口
python clawdbot-monitor-self-healing-webui.py --port 18800

# 调试模式
python clawdbot-monitor-self-healing-webui.py --debug
```

## 访问地址

```
http://localhost:18790
```

## 配置API Key

### MiniMax API Key (模型额度查询)

方式1: 环境变量
```bash
set MINIMAX_API_KEY=your_api_key_here
```

方式2: 直接编辑脚本
编辑 `clawdbot-monitor-self-healing-webui.py`，找到:
```python
"minimax_api_key": os.environ.get("MINIMAX_API_KEY", ""),
```
改为:
```python
"minimax_api_key": "your_api_key_here",
```

### Telegram Bot Token

确保环境变量 `TELEGRAM_BOT_TOKEN` 已设置 (同原有监控脚本)

## API端点

| 端点 | 说明 |
|------|------|
| `GET /` | WebUI主页 |
| `GET /api/status/all` | 获取所有状态(聚合) |
| `GET /api/status/gateway` | Gateway状态 |
| `GET /api/status/network` | 网络状态 |
| `GET /api/status/channels` | Channel状态 |
| `GET /api/status/chrome` | Chrome状态 |
| `GET /api/status/quota` | API额度 |
| `GET /api/status/plugins` | Plugins列表 |
| `GET /api/status/skills` | Skills列表 |
| `GET /api/status/cron` | Cron任务 |
| `GET /api/logs` | 监控日志 |

## 与原有监控脚本的关系

此WebUI**独立运行**，不依赖原有的 `clawdbot-monitor-self-healing.py`：
- WebUI使用Flask提供Web服务 (端口18790)
- 原有监控脚本继续使用端口18789进行健康检查
- 两者可以同时运行，互不影响

## 文件结构

```
clawdbot-monitor/
├── clawdbot-monitor-self-healing.py      # 原监控脚本
├── clawdbot-monitor-self-healing-webui.py # WebUI服务器 (新建)
└── webui/
    └── index.html                         # 前端页面 (新建)
```

## 技术栈

- **后端**: Flask + Python 3
- **前端**: Bootstrap 5 + Vanilla JS
- **UI风格**: Mazer (GitHub: zuramai/mazer)
- **图标**: Bootstrap Icons
- **字体**: Geist

## 截图预览

界面包含:
- 顶部状态卡片 (Gateway/网络/Chrome/API额度)
- Channel状态面板
- Plugins/Skills表格
- Cron任务倒计时
- 实时日志查看器
- 底部统计信息
