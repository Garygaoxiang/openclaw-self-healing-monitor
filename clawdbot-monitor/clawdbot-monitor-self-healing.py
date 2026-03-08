#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clawdbot Gateway Monitor - 自愈增强版
支持双 Chrome (9222 + 9223)
"""

import os
import sys
import time
import signal
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

CONFIG = {
    "gateway_port": 18789,
    "check_interval": 30,
    "max_retries": 5,
    "retry_delay": 3,
    "log_file": Path.home() / ".clawdbot/monitor.log",
    "pid_file": Path.home() / ".clawdbot/monitor.pid",
    "proxy_host": "127.0.0.1",
    "proxy_port": 10808,
    "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "telegram_token": "YOUR_TELEGRAM_TOKEN",
    "chrome_launcher": r"F:\Scripts\startup_chrome.bat",
    "claude_api_url": "https://api.minimaxi.com/anthropic",
    "claude_api_key": "YOUR_CLAUDE_KEY"
}

def log(level: str, message: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {message}"
    CONFIG["log_file"].parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG["log_file"], 'a', encoding='utf-8') as f:
        f.write(log_line + "\n")
    print(log_line)

def send_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
        data = {
            "chat_id": CONFIG["telegram_chat_id"],
            "text": message
        }
        proxies = {
            "http": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}",
            "https": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}"
        }
        requests.post(url, json=data, proxies=proxies, timeout=10)
    except Exception as e:
        log("WARN", f"Telegram 通知失败: {e}")
    try:
        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
        data = {"chat_id": CONFIG["telegram_chat_id"], "text": message}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        log("WARN", f"Telegram 通知失败: {e}")

def is_chrome_running(port: int) -> bool:
    """检查指定端口的 Chrome 是否运行"""
    try:
        response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=3)
        return response.status_code == 200
    except Exception:
        return False

def is_chrome_debugging_running() -> bool:
    """检查 9222 和 9223 是否都运行"""
    port_9222 = is_chrome_running(9222)
    port_9223 = is_chrome_running(9223)
    log("INFO", f"Chrome 状态: 9222={port_9222}, 9223={port_9223}")
    return port_9222 and port_9223

def start_chrome_debugging():
    """启动双 Chrome (9222 + 9223)"""
    log("INFO", "启动双 Chrome (9222 + 9223)...")
    
    # 使用 startup_chrome.bat
    chrome_launcher = CONFIG.get("chrome_launcher", "")
    actual_launcher = chrome_launcher.replace(r"PATH\TO", r"F:\Scripts")
    
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", actual_launcher],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True
        )
        log("INFO", f"已执行启动器: {actual_launcher}")
    except Exception as e:
        log("ERROR", f"启动 Chrome 失败: {e}")

def check_and_restart_chrome():
    """检查 Chrome 状态并重启"""
    port_9222 = is_chrome_running(9222)
    port_9223 = is_chrome_running(9223)
    
    if not port_9222 or not port_9223:
        log("WARN", f"Chrome 端口异常: 9222={port_9222}, 9223={port_9223}")
        start_chrome_debugging()
        time.sleep(5)  # 等待启动
        send_telegram(f"🔄 Chrome 重启中... 9222={port_9222}, 9223={port_9223}")
    else:
        log("INFO", "Chrome 9222 和 9223 都正常运行")

def is_gateway_running() -> bool:
    """检查 Gateway 是否运行"""
    try:
        response = requests.get(f"http://127.0.0.1:{CONFIG['gateway_port']}/health", timeout=3)
        if response.status_code != 200:
            log("WARN", f"Gateway 状态异常: {response.status_code}")
            return False
        return True
    except Exception as e:
        log("WARN", f"Gateway 连接失败: {e}")
        return False

def restart_gateway():
    """重启 Gateway"""
    log("INFO", "重启 Gateway...")
    try:
        subprocess.Popen(
            ["npx", "openclaw", "gateway", "run", "--force", "--verbose"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True
        )
        log("INFO", "Gateway 重启命令已执行")
    except Exception as e:
        log("ERROR", f"Gateway 重启失败: {e}")

def call_claude_code_fix():
    """调用 Claude Code 进行智能修复"""
    log("INFO", "调用 Claude Code 自动修复...")
    
    # 使用 one-time 环境变量
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = CONFIG["claude_api_url"]
    env["ANTHROPIC_AUTH_TOKEN"] = CONFIG["claude_api_key"]
    
    try:
        result = subprocess.run(
            ["claude", "-p", "--dangerously-skip-permissions", "请检查 OpenClaw Gateway 状态，如果有问题请运行 openclaw doctor --fix 进行修复"],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
            shell=True
        )
        log("INFO", f"Claude Code 响应: {result.stdout[:500]}")
    except Exception as e:
        log("ERROR", f"Claude Code 调用失败: {e}")

def send_startup_notification():
    """发送启动通知"""
    send_telegram("🤖 监控脚本已启动\n- Chrome 9222 + 9223\n- Gateway 自愈监控")

def main():
    """主循环"""
    log("INFO", "=" * 50)
    log("INFO", "Clawdbot Monitor 启动")
    log("INFO", "=" * 50)
    
    send_startup_notification()
    
    consecutive_failures = 0
    
    while True:
        try:
            # 检查 Gateway
            gateway_ok = is_gateway_running()
            
            # 检查 Chrome (9222 + 9223)
            chrome_ok = is_chrome_debugging_running()
            
            if not gateway_ok:
                consecutive_failures += 1
                log("WARN", f"Gateway 检查失败 ({consecutive_failures}/{CONFIG['max_retries']})")
                
                if consecutive_failures >= CONFIG['max_retries']:
                    log("ERROR", "Gateway 连续失败，尝试重启...")
                    restart_gateway()
                    consecutive_failures = 0
            else:
                consecutive_failures = 0
            
            # 检查 Chrome 状态
            if not chrome_ok:
                log("WARN", "Chrome 端口异常，尝试重启...")
                start_chrome_debugging()
                time.sleep(5)
            
            time.sleep(CONFIG['check_interval'])
            
        except KeyboardInterrupt:
            log("INFO", "监控脚本已停止")
            break
        except Exception as e:
            log("ERROR", f"主循环异常: {e}")
            time.sleep(CONFIG['check_interval'])

if __name__ == "__main__":
    main()
