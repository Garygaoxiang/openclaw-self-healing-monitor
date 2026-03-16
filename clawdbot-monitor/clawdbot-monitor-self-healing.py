#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clawdbot Gateway Monitor - 自愈增强版
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
    try:
        if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        if hasattr(sys.stderr, 'buffer') and sys.stderr.buffer is not None:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass  # 如果替换失败，保留原始 stdout/stderr

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
    "telegram_token": "XXX_TELEGRAM_TOKEN",
    "chrome_debug_port": 9222,
    "chrome_cron_port": 9223,
    "chrome_extension": r"F:\Scripts\openclaw-browser-relay-extension",
    "chrome_launcher": r"F:\Scripts\chrome9222\chrome9222.bat",
    "claude_api_url": "https://api.minimaxi.com/anthropic",
    "claude_api_key": "XXX_CLAUDE_KEY"
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

def is_chrome_debugging_running(port: int) -> bool:
    try:
        response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=3)
        return response.status_code == 200
    except Exception:
        return False

def start_chrome_debugging(port: int) -> bool:
    """启动 Chrome 调试端口"""
    if is_chrome_debugging_running(port):
        log("INFO", f"调试 Chrome ({port}) 已在运行")
        return True

    log("INFO", f"启动调试 Chrome ({port})...")
    
    try:
        # 直接启动 Chrome（更可靠，避免 bat 脚本潜在问题）
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        # 针对 9222 保留原来已经配置好书签和扩展的状态目录
        if port == 9222:
            profile_dir = r"C:\ChromeDebugProfile"
        else:
            profile_dir = rf"C:\ChromeDebugProfile{port}"
        
        # 针对新端口，如果还没有配置文件，从 9222 的主配置目录中完整拷贝（包含所有扩展和书签）
        source_profile = r"C:\ChromeDebugProfile"
        if port != 9222 and os.path.exists(source_profile) and not os.path.exists(profile_dir):
            log("INFO", f"首次启动 Chrome ({port})，正在从 {source_profile} 完整复制配置...")
            try:
                # 使用 xcopy 完整复制该目录
                subprocess.run(
                    ["xcopy", source_profile, profile_dir, "/E", "/I", "/Q", "/Y", "/C"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                log("WARN", f"复制 Profile 失败: {e}")

        # 确保配置文件目录存在
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--force-device-scale-factor=1"
        ]
        
        # 自动加载 Browser Relay 扩展
        ext_path = CONFIG.get("chrome_extension", "")
        if ext_path and os.path.exists(ext_path):
            # 将路径作为字符串传递在列表中，subprocess会自动处理包含空格等情况
            cmd.append(f"--load-extension={ext_path}")
        else:
            log("WARN", "未找到 relay 扩展路径，禁用扩展启动")
            cmd.append("--disable-extensions")
            
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log("INFO", f"Chrome ({port}) 启动命令已执行: {cmd}")
    except Exception as e:
        log("ERROR", f"启动调试 Chrome ({port}) 失败: {e}")
        send_telegram(f"❌ 调试 Chrome ({port}) 启动异常: {e}")
        return False

    # 等待 Chrome 就绪，最多等待 30 秒
    for i in range(30):
        time.sleep(1)
        if is_chrome_debugging_running(port):
            log("INFO", f"调试 Chrome {port} 端口已就绪 (等待了 {i+1} 秒)")
            send_telegram(f"✅ 调试 Chrome ({port}) 已启动，并已加载 Relay 扩展")
            return True

    log("ERROR", f"调试 Chrome 启动超时，{port} 端口未响应")
    send_telegram(f"❌ 调试 Chrome ({port}) 启动超时，请检查 Chrome 是否正常安装")
    return False


def is_gateway_running() -> bool:
    try:
        response = requests.get(f"http://localhost:{CONFIG['gateway_port']}/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def run_wsl_command(cmd: str, timeout: int = 30) -> tuple:
    try:
        result = subprocess.run(["wsl", "-e", "bash", "-c", cmd], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)

def check_config_errors() -> tuple:
    cmd = "export PATH=/home/clawuser/.npm-global/bin:$PATH && openclaw doctor 2>&1"
    returncode, stdout, stderr = run_wsl_command(cmd, 30)
    output = stdout + stderr
    # 覆盖 openclaw 各版本可能出现的错误关键词
    error_keywords = [
        "Config invalid", "Unrecognized key", "Problem:",
        "ValidationError", "invalid configuration", "parse error",
        "SyntaxError", "Unexpected token", "Cannot find", "config error",
        "failed to load", "invalid value"
    ]
    error_lines = [line for line in output.split('\n')
                   if any(kw.lower() in line.lower() for kw in error_keywords)]
    if error_lines or returncode != 0:
        error_msg = '\n'.join(error_lines[:5]) or f"doctor 退出码={returncode}"
        return True, error_msg, output[:5000]
    return False, "", output[:5000]

def run_doctor_fix() -> tuple:
    log("INFO", "运行 openclaw doctor --fix 修复配置...")
    cmd = "export PATH=/home/clawuser/.npm-global/bin:$PATH && openclaw doctor --fix 2>&1"
    returncode, stdout, stderr = run_wsl_command(cmd, 60)
    output = stdout + stderr
    # 修复后再跑一次 doctor 验证（而不是靠 --fix 的输出判断）
    time.sleep(2)
    has_error, _, _ = check_config_errors()
    if not has_error and returncode == 0:
        log("INFO", "配置修复成功")
        return True, output
    else:
        log("ERROR", f"配置修复失败: {output[:500]}")
        return False, output

def call_claude_api_fix(error_info: str) -> bool:
    """直接通过 HTTP API 调用 Claude 分析并修复配置（不依赖 WSL claude CLI）"""
    import re
    log("INFO", "开始 Claude API 自动修复分析...")

    # 1. 收集诊断信息
    _, error_context, doctor_output = check_config_errors()

    # 2. 读取实际配置文件内容，方便 Claude 直接分析
    config_content = ""
    for config_path in [
        "~/.config/openclaw/config.json",
        "~/.openclaw/config.json",
        "~/.config/openclaw/config.yaml",
    ]:
        _, stdout, _ = run_wsl_command(f"cat {config_path} 2>/dev/null", 10)
        if stdout.strip():
            config_content = f"# {config_path}\n{stdout[:4000]}"
            break

    prompt = f"""OpenClaw Gateway 无法启动，请分析错误并给出修复用的 bash 命令。

## 错误信息
{error_info}

## openclaw doctor 输出
{doctor_output[:3000]}

## 当前配置文件
{config_content or '（无法读取配置文件）'}

请只输出可在 WSL bash 中执行的修复命令，格式为：
COMMAND_1: <命令1>
COMMAND_2: <命令2>
...

注意：PATH 已包含 /home/clawuser/.npm-global/bin。只修复配置错误，不要修改正常配置项。"""

    try:
        response = requests.post(
            f"{CONFIG['claude_api_url']}/v1/messages",
            headers={
                "x-api-key": CONFIG["claude_api_key"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )

        if response.status_code != 200:
            log("ERROR", f"Claude API 错误: {response.status_code} {response.text[:500]}")
            return fallback_interactive_fix(error_info)

        fix_text = response.json()["content"][0]["text"]
        log("INFO", f"Claude API 建议:\n{fix_text[:2000]}")
        send_telegram(f"🤖 Claude API 建议修复:\n{fix_text[:500]}")

        # 3. 解析命令：优先结构化格式，降级到代码块
        commands = re.findall(r'COMMAND_\d+:\s*(.+)', fix_text)
        if not commands:
            code_blocks = re.findall(r'```(?:bash|sh)?\n(.*?)```', fix_text, re.DOTALL)
            commands = [
                line.strip()
                for block in code_blocks
                for line in block.split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]

        if not commands:
            log("WARN", "Claude API 未返回可执行命令，回退到交互式修复")
            return fallback_interactive_fix(error_info)

        # 4. 执行命令
        log("INFO", f"执行 {len(commands)} 条修复命令...")
        for i, cmd in enumerate(commands[:10]):
            log("INFO", f"[{i+1}/{len(commands)}] {cmd}")
            full_cmd = f"export PATH=/home/clawuser/.npm-global/bin:$PATH && {cmd}"
            rc, stdout, stderr = run_wsl_command(full_cmd, 60)
            if stdout.strip():
                log("INFO", f"  stdout: {stdout[:500]}")
            if stderr.strip():
                log("WARN", f"  stderr: {stderr[:500]}")

        # 5. 真实验证修复结果
        time.sleep(3)
        has_error, remaining_error, _ = check_config_errors()
        if not has_error:
            log("INFO", "Claude API 修复成功，配置验证通过!")
            send_telegram("✅ Claude API 自动修复成功!")
            return True
        else:
            log("ERROR", f"修复后仍有配置错误: {remaining_error}")
            return fallback_interactive_fix(error_info)

    except requests.exceptions.Timeout:
        log("ERROR", "Claude API 请求超时")
    except Exception as e:
        log("ERROR", f"Claude API 调用失败: {e}")

    return fallback_interactive_fix(error_info)


# 保留旧名称作为别名，兼容 reconnect() 和 main() 中的调用
def call_claude_code_fix(error_info: str) -> bool:
    return call_claude_api_fix(error_info)

def fallback_interactive_fix(error_info: str):
    """回退到交互式修复窗口"""
    log("WARN", "回退到交互式修复...")
    send_telegram("🔧 doctor --fix 失败，请查看弹出的 Claude Code 窗口进行修复")
    
    cmd_window = f'''
@echo off
title OpenClaw 修复助手
echo ========================================
echo   OpenClaw 配置修复助手
echo ========================================
echo.
echo 请复制以下错误信息，粘贴到 Claude Code 中:
echo.
echo {error_info[:1000].replace('"', '\\"').replace('\n', ' ')}
echo.
echo 粘贴完成后按任意键打开 Claude Code...
pause > nul
set ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
set ANTHROPIC_AUTH_TOKEN=sk-cp-DDOK7A0jmYjYRVY82liprA6ALZycHzuc_5_UWioNCPEelQ9buUtk4TOGkHWh9tSqoaJMCP9q1jXFTF7XWHy6fEBgfSjEvuDEnl6o6rluMrUUERKJ7MM9k_U
doskey claude=claude --dangerously-skip-permissions $*
cmd /k cd /d F:\\Scripts\\clawdbot-monitor
'''
    try:
        batch_file = Path("F:/Scripts/clawdbot-monitor/fix_assist.bat")
        with open(batch_file, 'w', encoding='utf-8') as f:
            f.write(cmd_window)
        subprocess.Popen(["cmd", "/c", str(batch_file)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        log("INFO", "已打开修复助手窗口")
        return True
    except Exception as e:
        log("ERROR", f"打开修复窗口失败: {e}")
        return False

def collect_logs() -> str:
    log("INFO", "收集日志...")
    logs = []
    cmd = "tail -200 /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log 2>/dev/null || tail -200 /tmp/openclaw/openclaw.log 2>/dev/null"
    returncode, stdout, stderr = run_wsl_command(cmd, 10)
    logs.append("=== OpenClaw 日志 ===\n" + stdout[-5000:])
    cmd = "export PATH=/home/clawuser/.npm-global/bin:$PATH && openclaw doctor 2>&1"
    returncode, stdout, stderr = run_wsl_command(cmd, 30)
    logs.append("=== Doctor 输出 ===\n" + stdout)
    return '\n\n'.join(logs)

def cleanup_old_processes():
    try:
        cmd = "export PATH=/home/clawuser/.npm-global/bin:$PATH && openclaw gateway stop"
        run_wsl_command(cmd, 10)
        subprocess.run(["wsl", "systemctl", "--user", "stop", "openclaw-gateway.service"], capture_output=True)
        time.sleep(2)
        subprocess.run(["wsl", "pkill", "-9", "-f", "openclaw-gateway"], capture_output=True)
        subprocess.run(["wsl", "pkill", "-9", "-f", "clawdbot"], capture_output=True)
        log("INFO", "已清理旧进程")
    except Exception as e:
        log("WARN", f"清理进程失败: {e}")

def start_gateway() -> bool:
    log("INFO", f"启动 Clawdbot Gateway (端口: {CONFIG['gateway_port']})...")
    cleanup_old_processes()
    time.sleep(2)
    import socket
    proxy_port = CONFIG["proxy_port"]
    returncode, stdout, stderr = run_wsl_command("ip route show default | awk '{print $3}'", 5)
    windows_ip = stdout.strip() if stdout.strip() else "127.0.0.1"
    windows_ip = windows_ip.split()[0] if windows_ip.split() else "127.0.0.1"
    
    def test_proxy(host, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((host, port))
            sock.close()
            return True
        except Exception:
            return False
    
    proxy_host = "127.0.0.1"
    for test_host in ["127.0.0.1", windows_ip]:
        if test_proxy(test_host, proxy_port):
            proxy_host = test_host
            log("INFO", f"检测到可用代理: {test_host}:{proxy_port}")
            break
    else:
        log("WARN", f"未检测到可用代理，使用 127.0.0.1")
    
    proxy_host = proxy_host.strip().replace('\n', ' ').replace('\r', '')
    telegram_token = CONFIG["telegram_token"]
    gateway_port = CONFIG["gateway_port"]
    
    cmd_str = (
        f"export PATH=/home/clawuser/.npm-global/bin:$PATH && "
        f"export no_proxy='127.0.0.1,localhost,::1,feishu.cn,feishu.com,open.feishu.cn,192.168.0.0/16' && "
        f"export http_proxy='http://{proxy_host}:{proxy_port}' && "
        f"export https_proxy='http://{proxy_host}:{proxy_port}' && "
        f"export TELEGRAM_BOT_TOKEN='{telegram_token}' && "
        f"npx openclaw gateway run --port {gateway_port} --force --verbose"
    )
    
    try:
        subprocess.Popen(["wsl", "-e", "bash", "-c", cmd_str])
        log("INFO", f"已启动 Gateway (代理: http://{proxy_host}:{proxy_port})")
    except Exception as e:
        log("ERROR", f"启动失败: {e}")
        return False
    
    log("INFO", "等待 Gateway 启动...")
    time.sleep(15)
    
    if is_gateway_running():
        log("INFO", "Gateway 启动成功")
        send_telegram("✅ Gateway 已成功启动")
        for port in [CONFIG["chrome_debug_port"], CONFIG["chrome_cron_port"]]:
            if not is_chrome_debugging_running(port):
                log("INFO", f"Gateway 启动成功，同步启动调试 Chrome ({port})...")
                start_chrome_debugging(port)
            else:
                log("INFO", f"调试 Chrome ({port}) 已在运行，跳过")
        return True
    else:
        log("ERROR", "Gateway 启动失败 - 健康检查未通过")
        return False

def reconnect() -> bool:
    # 启动前先检查 config，避免带错误配置反复重试
    has_error, error_msg, _ = check_config_errors()
    if has_error:
        log("ERROR", f"检测到配置错误，跳过重试直接自愈: {error_msg}")
        send_telegram(f"⚠️ 配置错误，直接进入自愈流程: {error_msg[:200]}")
        return _run_self_healing(f"配置错误:\n{error_msg}")

    for attempt in range(1, CONFIG["max_retries"] + 1):
        log("WARN", f"尝试重新连接 (第 {attempt}/{CONFIG['max_retries']} 次)...")
        if is_gateway_running():
            log("INFO", "Gateway 健康检查通过")
            return True
        if start_gateway():
            log("INFO", "重新连接成功")
            return True

        if attempt < CONFIG["max_retries"]:
            log("INFO", f"等待 {CONFIG['retry_delay']} 秒后重试...")
            time.sleep(CONFIG["retry_delay"])

    # 重试耗尽后，再次检查 config（启动期间可能触发升级）
    has_error, error_msg, _ = check_config_errors()
    error_info = f"Gateway 连续 {CONFIG['max_retries']} 次启动失败"
    if has_error:
        error_info += f"\n配置错误: {error_msg}"

    log("ERROR", "重新连接失败，进入自愈流程...")
    return _run_self_healing(error_info)


def _run_self_healing(error_info: str) -> bool:
    """统一的自愈入口：doctor --fix → Claude API → 交互式"""
    log("WARN", "尝试自愈修复...")
    send_telegram(f"🔧 开始自愈修复...\n{error_info[:300]}")

    success, doctor_output = run_doctor_fix()
    if success:
        log("INFO", "doctor --fix 修复成功")
        send_telegram("✅ doctor --fix 修复成功")
        cleanup_old_processes()
        time.sleep(3)
        return False  # 返回 False 让调用方触发重新启动

    log("ERROR", "doctor --fix 修复失败，调用 Claude API 智能修复...")
    send_telegram("🤖 doctor --fix 失败，正在调用 Claude API 智能修复...")
    full_error = f"{error_info}\n\ndoctor --fix 输出:\n{doctor_output[:1000]}"

    if call_claude_code_fix(full_error):
        send_telegram("✅ Claude API 修复成功!")
        cleanup_old_processes()
        time.sleep(3)
        return False  # 让调用方重新触发启动
    else:
        logs = collect_logs()
        send_telegram(f"❌ 所有修复尝试均失败，需要人工介入\n\n日志:\n{logs[:2000]}")
        return False

def monitor():
    consecutive_failures = 0
    log("INFO", "=" * 50)
    log("INFO", "Clawdbot Gateway Monitor 自愈增强版 启动")
    log("INFO", f"端口: {CONFIG['gateway_port']}")
    log("INFO", f"检查间隔: {CONFIG['check_interval']}秒")
    log("INFO", f"连续 {CONFIG['max_retries']} 次启动失败后触发自愈")
    log("INFO", "=" * 50)
    
    if is_gateway_running():
        log("INFO", "Gateway 正在运行")
    else:
        log("WARN", "Gateway 未运行，尝试启动...")
        if reconnect():
            consecutive_failures = 0
        else:
            consecutive_failures += 1
    
    while True:
        try:
            if is_gateway_running():
                if consecutive_failures > 0:
                    log("INFO", "Gateway 恢复健康，连续失败计数重置")
                    consecutive_failures = 0
                for port in [CONFIG["chrome_debug_port"], CONFIG["chrome_cron_port"]]:
                    if not is_chrome_debugging_running(port):
                        log("WARN", f"检测到调试 Chrome ({port}) 已断开，尝试重启...")
                        send_telegram(f"⚠️ Chrome 调试端口 {port} 已断开，正在自动重启...")
                        start_chrome_debugging(port)
                time.sleep(CONFIG["check_interval"])
            else:
                log("WARN", "检测到 Gateway 断开连接")
                if reconnect():
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    log("ERROR", f"重新连接失败，连续失败次数: {consecutive_failures}")
                time.sleep(CONFIG["check_interval"])
        except KeyboardInterrupt:
            log("INFO", "监控已停止")
            break
        except Exception as e:
            log("ERROR", f"监控错误: {e}")
            time.sleep(CONFIG["check_interval"])

def run_daemon():
    if sys.platform == "win32":
        # Windows 不支持 os.fork()，使用 subprocess 在新进程启动
        script_path = os.path.abspath(__file__)
        proc = subprocess.Popen(
            [sys.executable, script_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
            close_fds=True
        )
        print(f"监控已在后台启动 (PID: {proc.pid})")
        CONFIG["pid_file"].parent.mkdir(parents=True, exist_ok=True)
        CONFIG["pid_file"].write_text(str(proc.pid))
        sys.exit(0)
    else:
        pid = os.fork()
        if pid > 0:
            print(f"监控已启动 (PID: {pid})")
            CONFIG["pid_file"].write_text(str(pid))
            sys.exit(0)
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        monitor()

def stop_monitor():
    cleanup_old_processes()
    log("INFO", "监控已停止")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clawdbot Gateway Monitor 自愈增强版")
    parser.add_argument("--daemon", "-d", action="store_true", help="后台运行")
    parser.add_argument("--status", "-s", action="store_true", help="显示状态")
    parser.add_argument("--stop", action="store_true", help="停止监控")
    parser.add_argument("--fix", action="store_true", help="手动修复")
    args = parser.parse_args()
    
    if args.status:
        if is_gateway_running():
            print("Gateway 运行正常")
        else:
            print("Gateway 未运行")
    elif args.stop:
        stop_monitor()
    elif args.fix:
        log("INFO", "手动修复...")
        has_error, error_msg, output = check_config_errors()
        if has_error:
            log("INFO", f"检测到错误: {error_msg}")
            success, out = run_doctor_fix()
            if success:
                log("INFO", "修复成功")
                send_telegram("✅ 手动修复成功")
            else:
                log("ERROR", "doctor --fix 失败，调用 Claude Code...")
                if call_claude_code_fix(error_msg):
                    send_telegram("✅ Claude Code 修复成功")
                else:
                    send_telegram("❌ 修复失败")
        else:
            log("INFO", "未检测到错误")
            send_telegram("✅ 配置正常")
    elif args.daemon:
        run_daemon()
    else:
        monitor()

if __name__ == "__main__":
    main()
