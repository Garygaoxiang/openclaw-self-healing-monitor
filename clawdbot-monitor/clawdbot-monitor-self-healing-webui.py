#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clawdbot Gateway Monitor WebUI - 自愈增强版
基于Flask + Mazer风格Bootstrap 5 UI
"""

import os
import sys
import json
import time
import socket
import subprocess
import requests
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request

# ============== 复用原有监控逻辑 ==============
def _is_wsl() -> bool:
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False

IN_WSL = _is_wsl()

def get_wsl_home() -> str:
    """获取WSL中clawuser的主目录"""
    rc, stdout, _ = run_wsl_command("echo ~clawuser", 5)
    if rc == 0 and stdout.strip():
        return stdout.strip()
    return "/home/clawuser"

CONFIG = {
    "gateway_port": 18789,
    "check_interval": 30,
    "max_retries": 5,
    "retry_delay": 3,
    "log_file": Path.home() / ".clawdbot/monitor.log",
    "pid_file": Path.home() / ".clawdbot/monitor.pid",
    "proxy_host": "127.0.0.1",
    "proxy_port": 10808,
    "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID"),
    "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "chrome_debug_port": 9315,
    "chrome_cron_port": 9316,
    "chrome_extension": r"F:\Scripts\openclaw-browser-relay-extension",
    "minimax_api_key": os.environ.get("MINIMAX_API_KEY", "YOUR_MINIMAX_API_KEY"),  # API Key稍后配置
    "claude_api_url": "https://api.minimaxi.com/anthropic",
    "claude_api_key": os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
}

# ============== Flask App ==============
app = Flask(__name__, template_folder='webui', static_folder='webui')
app.config['JSON_AS_ASCII'] = False

# Windows 控制台编码修复
if sys.platform == "win32":
    import io
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# ============== 原有工具函数 ==============
def run_wsl_command(cmd: str, timeout: int = 30) -> tuple:
    try:
        if IN_WSL:
            args = ["bash", "-c", cmd]
        else:
            args = ["wsl", "-u", "clawuser", "-e", "bash", "-c", cmd]
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)

def is_gateway_running() -> bool:
    """检查Gateway健康状态"""
    try:
        rc, stdout, _ = run_wsl_command(
            f"curl -s --max-time 15 http://127.0.0.1:{CONFIG['gateway_port']}/health",
            timeout=25
        )
        if rc == 0 and '"ok":true' in stdout:
            return True
        return False
    except Exception:
        return False

def is_chrome_debugging_running(port: int) -> bool:
    """检查Chrome调试端口是否可用"""
    try:
        response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=3)
        return response.status_code == 200
    except Exception:
        return False

def get_gateway_info() -> dict:
    """获取Gateway详细信息"""
    try:
        rc, stdout, _ = run_wsl_command(
            f"curl -s --max-time 15 http://127.0.0.1:{CONFIG['gateway_port']}/api/status",
            timeout=25
        )
        if rc == 0 and stdout:
            return json.loads(stdout)
    except Exception:
        pass
    return {}

# ============== API 端点 ==============

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/status/gateway')
def api_gateway_status():
    """Gateway状态"""
    running = is_gateway_running()
    info = get_gateway_info() if running else {}
    return jsonify({
        "status": "running" if running else "stopped",
        "running": running,
        "port": CONFIG['gateway_port'],
        "info": info,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/status/network')
def api_network_status():
    """网络状态"""
    result = {
        "proxy": {
            "host": CONFIG['proxy_host'],
            "port": CONFIG['proxy_port'],
            "available": False
        },
        "direct": {
            "available": False
        },
        "ip": {
            "internal": "",
            "external": ""
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # 检测代理
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((CONFIG['proxy_host'], CONFIG['proxy_port']))
        sock.close()
        result["proxy"]["available"] = True
    except Exception:
        pass
    
    # 检测直连（通过WSL检测外网连通性）
    rc, stdout, _ = run_wsl_command("curl -s --max-time 5 https://www.google.com -o /dev/null -w '%{http_code}'", 10)
    result["direct"]["available"] = (rc == 0 and stdout == "200")
    
    # 获取IP
    try:
        rc, stdout, _ = run_wsl_command("curl -s --max-time 5 https://api.ipify.org", 10)
        if rc == 0 and stdout:
            result["ip"]["external"] = stdout.strip()
    except Exception:
        pass
    
    try:
        rc, stdout, _ = run_wsl_command("hostname -I | awk '{print $1}'", 5)
        if rc == 0 and stdout:
            result["ip"]["internal"] = stdout.strip()
    except Exception:
        pass
    
    return jsonify(result)

@app.route('/api/status/channels')
def api_channels_status():
    """Channel状态 (Telegram, Feishu)"""
    result = {
        "telegram": {
            "status": "unknown",
            "chat_id": CONFIG['telegram_chat_id'],
            "token_set": bool(CONFIG['telegram_token'] and CONFIG['telegram_token'] not in ["", "YOUR_TELEGRAM_TOKEN", "XXX_TELEGRAM_TOKEN"]),
            "proxy": True  # TG走代理
        },
        "feishu": {
            "status": "unknown",
            "configured": False,
            "proxy": False  # Feishu走直连
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # 检测Telegram Bot状态 (走代理)
    if result["telegram"]["token_set"]:
        try:
            token = CONFIG['telegram_token']
            proxies = {
                "http": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}",
                "https": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
            }
            session = requests.Session()
            session.trust_env = False
            session.proxies = proxies
            response = session.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10, verify=False)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result["telegram"]["status"] = "running"
                    result["telegram"]["bot_name"] = data.get("result", {}).get("first_name", "")
                else:
                    result["telegram"]["status"] = "error"
            else:
                result["telegram"]["status"] = "error"
        except Exception as e:
            result["telegram"]["status"] = f"error: {str(e)}"
    else:
        result["telegram"]["status"] = "not_configured"
    
    # 检测Feishu状态 (走直连，不走代理)
    try:
        # 方式1: 通过Gateway API检测（Gateway本身是直连的）
        rc, stdout, _ = run_wsl_command(
            f"curl -s --max-time 10 http://127.0.0.1:{CONFIG['gateway_port']}/api/plugins/feishu/status",
            timeout=15
        )
        if rc == 0 and stdout and '"ok"' in stdout:
            result["feishu"]["status"] = "running"
            result["feishu"]["configured"] = True
        else:
            # 方式2: 直接通过Feishu开放API检测（直连，不走代理）
            # 检查Feishu配置是否存在
            wsl_home = get_wsl_home()
            rc2, _, _ = run_wsl_command(f"ls {wsl_home}/.openclaw/feishu 2>/dev/null && echo 'exists' || echo ''", 5)
            if rc2 == 0 and 'exists' in _:
                result["feishu"]["configured"] = True
                # 尝试直连检测Feishu API（禁用代理）
                try:
                    session = requests.Session()
                    session.trust_env = False  # 禁用环境变量中的代理
                    # 直连，不设置proxies
                    response = session.get(
                        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                        headers={"Content-Type": "application/json"},
                        json={"app_id": "", "app_secret": ""},
                        timeout=10,
                        proxies=None  # 明确不走代理
                    )
                    # 即使token请求失败，只要能连接就说明直连正常
                    result["feishu"]["status"] = "running"
                except requests.exceptions.ProxyError:
                    # 代理错误说明配置了代理但不应该用
                    result["feishu"]["status"] = "proxy_error"
                except Exception:
                    # 其他错误（如网络不通）也认为直连检测失败
                    result["feishu"]["status"] = "direct_failed"
    except Exception:
        pass
    
    return jsonify(result)

@app.route('/api/status/chrome')
def api_chrome_status():
    """Chrome状态"""
    ports = [CONFIG['chrome_debug_port'], CONFIG['chrome_cron_port']]
    result = {
        "instances": {},
        "timestamp": datetime.now().isoformat()
    }
    
    for port in ports:
        running = is_chrome_debugging_running(port)
        result["instances"][str(port)] = {
            "port": port,
            "status": "running" if running else "stopped",
            "running": running,
            "debug_url": f"http://127.0.0.1:{port}" if running else None
        }
    
    return jsonify(result)

@app.route('/api/status/quota')
def api_quota_status():
    """模型额度"""
    result = {
        "minimax": {
            "status": "unknown",
            "remaining": None,
            "total": None,
            "percent": None
        },
        "timestamp": datetime.now().isoformat()
    }
    
    api_key = CONFIG.get("minimax_api_key", "")
    if not api_key or api_key == "YOUR_API_KEY":
        result["minimax"]["status"] = "not_configured"
        return jsonify(result)
    
    try:
        proxies = {
            "http": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}",
            "https": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
        }
        session = requests.Session()
        session.trust_env = False  # 禁用环境变量proxy
        session.proxies = proxies
        response = session.get(
            'https://api.minimaxi.com/v1/api/openplatform/coding_plan/remains',
            headers={
                'Authorization': f'Bearer {api_key}'
            },
            timeout=10,
            verify=False
        )
        if response.status_code == 200:
            data = response.json()
            model_remains = data.get("model_remains", [])
            
            # 找M2.1或M2.7模型的额度
            coding_model = None
            for model in model_remains:
                name = model.get("model_name", "")
                if "MiniMax-M" in name or "M2" in name:
                    coding_model = model
                    break
            
            if coding_model:
                total = coding_model.get("current_interval_total_count", 0)
                used = coding_model.get("current_interval_usage_count", 0)
                remaining_time = coding_model.get("remains_time", 0)
                
                result["minimax"]["remaining"] = remaining_time
                result["minimax"]["total"] = total + used if total else None
                result["minimax"]["used"] = used
                
                if total and total > 0:
                    result["minimax"]["percent"] = round((used / total) * 100, 1)
                elif remaining_time:
                    result["minimax"]["percent"] = None  # 时间制额度
                
                result["minimax"]["model_name"] = coding_model.get("model_name", "")
            
            result["minimax"]["all_models"] = [{
                "name": m.get("model_name", ""),
                "remaining_time": m.get("remains_time", 0),
                "used": m.get("current_interval_usage_count", 0),
                "total": m.get("current_interval_total_count", 0)
            } for m in model_remains]
            
            result["minimax"]["status"] = "ok"
        else:
            result["minimax"]["status"] = f"error: {response.status_code}"
    except Exception as e:
        result["minimax"]["status"] = f"error: {str(e)}"
    
    return jsonify(result)

@app.route('/api/status/plugins')
def api_plugins_status():
    """Plugins状态"""
    result = {
        "plugins": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # 从Gateway获取plugin列表
    try:
        rc, stdout, _ = run_wsl_command(
            f"curl -s --max-time 15 http://127.0.0.1:{CONFIG['gateway_port']}/api/plugins",
            timeout=25
        )
        if rc == 0 and stdout:
            try:
                data = json.loads(stdout)
                result["plugins"] = data.get("plugins", [])
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    
    # 如果Gateway API不可用，使用WSL配置文件
    if not result["plugins"]:
        wsl_home = get_wsl_home()
        
        # 已知的重要插件检测
        # memory-lancedb-pro
        rc, stdout, _ = run_wsl_command(f"ls -d {wsl_home}/.openclaw/memory/lancedb-pro 2>/dev/null && echo 'exists' || echo ''", 5)
        if rc == 0 and 'exists' in stdout:
            result["plugins"].append({
                "name": "memory-lancedb-pro",
                "status": "installed",
                "type": "memory"
            })
        
        # feishu
        rc, stdout, _ = run_wsl_command(f"ls -d {wsl_home}/.openclaw/feishu 2>/dev/null && echo 'exists' || echo ''", 5)
        if rc == 0 and 'exists' in stdout:
            result["plugins"].append({
                "name": "feishu",
                "status": "installed",
                "type": "channel"
            })
        
        # browser-relay (如果存在)
        rc, stdout, _ = run_wsl_command(f"ls -d {wsl_home}/.openclaw/browser 2>/dev/null && echo 'exists' || echo ''", 5)
        if rc == 0 and 'exists' in stdout:
            result["plugins"].append({
                "name": "browser",
                "status": "installed",
                "type": "extension"
            })
    
    return jsonify(result)

@app.route('/api/status/skills')
def api_skills_status():
    """Skills列表及状态"""
    result = {
        "skills": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # 读取skills目录
    skill_paths = [
        (Path.home() / ".claude" / "skills", "system"),
        (Path("F:/Scripts/.claude/skills"), "custom")
    ]
    
    for skill_path, skill_type in skill_paths:
        if skill_path.exists():
            for item in skill_path.iterdir():
                if item.is_dir() or item.suffix == '.md':
                    skill_info = {
                        "name": item.stem if item.suffix == '.md' else item.name,
                        "type": skill_type,
                        "path": str(item),
                        "status": "active"
                    }
                    # 尝试读取SKILL.md获取描述
                    skill_md = item / "SKILL.md" if item.is_dir() else item
                    if skill_md.exists():
                        try:
                            content = skill_md.read_text(encoding='utf-8', errors='replace')
                            for line in content.split('\n')[:5]:
                                if line.startswith('description:'):
                                    skill_info["description"] = line.replace('description:', '').strip()
                                    break
                        except Exception:
                            pass
                    result["skills"].append(skill_info)
    
    return jsonify(result)

@app.route('/api/status/cron')
def api_cron_status():
    """Cron任务状态及倒计时"""
    result = {
        "tasks": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # 从WSL的OpenClaw cron系统获取
    wsl_home = get_wsl_home()
    rc, stdout, _ = run_wsl_command(f"cat {wsl_home}/.openclaw/cron/jobs.json 2>/dev/null", 10)
    
    if rc == 0 and stdout:
        try:
            jobs_data = json.loads(stdout)
            jobs = jobs_data.get("jobs", [])
            now = datetime.now()
            
            for job in jobs:
                next_run = None
                # 尝试从state获取nextRunAtMs
                state = job.get("state", {})
                if state.get("nextRunAtMs"):
                    try:
                        next_run = datetime.fromtimestamp(state["nextRunAtMs"] / 1000)
                    except Exception:
                        pass
                
                # 解析schedule
                schedule = job.get("schedule", {})
                schedule_expr = ""
                if isinstance(schedule, dict):
                    schedule_expr = schedule.get("expr", "")
                else:
                    schedule_expr = str(schedule)
                
                # 计算相对时间
                time_diff = (next_run - now).total_seconds() if next_run else None
                
                # 获取上一个状态
                last_status = state.get("lastRunStatus", "unknown")
                last_error = state.get("lastError", "")
                
                task = {
                    "name": job.get("name", "Unknown"),
                    "id": job.get("id", ""),
                    "enabled": job.get("enabled", True),
                    "schedule": schedule_expr,
                    "description": job.get("description", ""),
                    "next_run": next_run.isoformat() if next_run else None,
                    "next_run_relative": format_relative_time(time_diff) if time_diff else "N/A",
                    "next_run_timestamp": next_run.timestamp() if next_run else None,
                    "last_status": last_status,
                    "last_error": last_error[:100] if last_error else "",
                    "last_run": datetime.fromtimestamp(state["lastRunAtMs"] / 1000).isoformat() if state.get("lastRunAtMs") else None
                }
                result["tasks"].append(task)
        except json.JSONDecodeError:
            pass
    
    return jsonify(result)

def calculate_next_cron_run(cron_parts: list, now: datetime) -> datetime:
    """计算下次Cron执行时间（简化版）"""
    try:
        minute, hour, day, month, weekday = cron_parts
        
        # 简单的下次执行计算
        # 从当前时间的下一秒开始找
        next_time = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # 最多查找7天
        for _ in range(7 * 24 * 60):
            if matches_cron(next_time, cron_parts):
                return next_time
            next_time += timedelta(minutes=1)
        
        return None
    except Exception:
        return None

def matches_cron(dt: datetime, cron_parts: list) -> bool:
    """检查时间是否匹配cron表达式"""
    try:
        minute, hour, day, month, weekday = cron_parts
        now = datetime.now()
        
        def match_cron_field(value: str, current: int) -> bool:
            if value == '*':
                return True
            if ',' in value:
                return str(current) in value.split(',')
            if '/' in value:
                step = int(value.split('/')[1])
                return current % step == 0
            if '-' in value:
                start, end = map(int, value.split('-'))
                return start <= current <= end
            try:
                return int(value) == current
            except ValueError:
                return True
        
        return (match_cron_field(minute, dt.minute) and
                match_cron_field(hour, dt.hour) and
                match_cron_field(day, dt.day) and
                match_cron_field(month, dt.month) and
                match_cron_field(weekday, dt.weekday()))
    except Exception:
        return False

def format_relative_time(seconds: float) -> str:
    """格式化为相对时间字符串"""
    if seconds is None:
        return "N/A"
    
    seconds = int(seconds)
    if seconds < 0:
        return "overdue"
    
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分钟"
    elif seconds < 86400:
        return f"{seconds // 3600}小时{seconds % 3600 // 60}分钟"
    else:
        return f"{seconds // 86400}天{(seconds % 86400) // 3600}小时"

@app.route('/api/logs')
def api_logs():
    """获取监控日志"""
    result = {
        "logs": [],
        "total_lines": 0
    }
    
    try:
        if CONFIG["log_file"].exists():
            lines = CONFIG["log_file"].read_text(encoding='utf-8', errors='replace').splitlines()
            result["total_lines"] = len(lines)
            # 返回最后100行
            result["logs"] = lines[-100:]
    except Exception as e:
        result["error"] = str(e)
    
    return jsonify(result)

@app.route('/api/status/all')
def api_all_status():
    """获取所有状态（聚合接口）"""
    return jsonify({
        "gateway": api_gateway_status().get_json(),
        "network": api_network_status().get_json(),
        "channels": api_channels_status().get_json(),
        "chrome": api_chrome_status().get_json(),
        "quota": api_quota_status().get_json(),
        "plugins": api_plugins_status().get_json(),
        "skills": api_skills_status().get_json(),
        "cron": api_cron_status().get_json(),
        "timestamp": datetime.now().isoformat()
    })

# ============== 启动服务器 ==============
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Clawdbot Gateway Monitor WebUI")
    parser.add_argument("--port", "-p", type=int, default=18790, help="WebUI端口 (默认: 18790)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()
    
    print(f"""
+========================================================+
|        Clawdbot Gateway Monitor WebUI 启动中           |
+--------------------------------------------------------+
|  地址: http://{args.host}:{args.port}                        |
|  Gateway端口: {CONFIG['gateway_port']}                                  |
+--------------------------------------------------------+
|  功能:                                                  |
|  - Gateway状态监控                                     |
|  - 网络状态 (直连/Proxy/IP)                           |
|  - Channel状态 (Telegram/Feishu)                      |
|  - Chrome调试状态 (9315/9316)                         |
|  - 模型额度查询                                        |
|  - Plugins/Skills状态                                  |
|  - Cron任务及倒计时                                    |
+========================================================+
    """)
    
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
