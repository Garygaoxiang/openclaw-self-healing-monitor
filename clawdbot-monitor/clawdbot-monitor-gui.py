#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clawdbot Gateway Monitor - CustomTkinter GUI
集成监控、自愈、自动重启功能 + 系统托盘悬浮窗
"""

import os
import re
import sys
import json
import time
import socket
import subprocess
import threading
import queue
import requests
import winreg
import tkinter as tk
import tkinter.ttk as ttk
from pathlib import Path
from datetime import datetime
import ctypes

# Windows 控制台编码修复
if sys.platform == "win32":
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import customtkinter as ctk
    from customtkinter import CTk, CTkFrame, CTkLabel, CTkButton, CTkSwitch, CTkTextbox
except ImportError:
    print("请安装 customtkinter: pip install customtkinter")
    sys.exit(1)

# 屏蔽对 127.0.0.1 的自签名证书警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
#  配置
# ============================================================
CONFIG = {
    "gateway_port": 18789,
    "check_interval": 30,
    "max_retries": 5,
    "retry_delay": 3,
    "proxy_host": "127.0.0.1",
    "proxy_port": 10808,
    "chrome_debug_port": 9315,
    "chrome_cron_port": 9316,
    "chrome_extension": r"F:\Scripts\openclaw-browser-relay-extension",
    "minimax_api_key": "YOUR_MINIMAX_API_KEY",
    "telegram_token": "YOUR_TELEGRAM_TOKEN",
    "log_file": Path.home() / ".clawdbot/monitor.log",
}

# 日志颜色 — 尽量贴近 Windows Terminal 命令行配色
LOG_COLORS = {
    "ERROR":   "#ff5555",   # 亮红       → 终端 stderr/error
    "WARN":    "#f1fa8c",   # 亮黄       → 终端 warning
    "INFO":    "#f8f8f2",   # 近白       → 终端默认前景（最常见）
    "SUCCESS": "#50fa7b",   # 亮绿       → 终端 success
    "GATEWAY": "#8be9fd",   # 亮青       → gateway 原始输出（与 INFO 区分）
    "DEBUG":   "#6272a4",   # 暗灰蓝     → debug/trace
    "SYS":     "#ff79c6",   # 粉         → GUI 系统消息
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ============================================================
#  全局状态
# ============================================================
log_queue: queue.Queue = queue.Queue(maxsize=2000)
_gui_print_queue: queue.Queue = queue.Queue(maxsize=5000)
gateway_proc = None  # 当前 gateway 子进程引用


class _TeeStdout:
    """将 print() 同时写入原始 stdout 和 GUI 队列"""
    def __init__(self, original):
        self._orig = original

    def write(self, text):
        if self._orig:
            try:
                self._orig.write(text)
                self._orig.flush()
            except Exception:
                pass
        if text and text.strip("\r\n"):
            try:
                _gui_print_queue.put_nowait(text)
            except queue.Full:
                pass
        return len(text) if text else 0

    def flush(self):
        if self._orig:
            try:
                self._orig.flush()
            except Exception:
                pass

    # 让 logging 等模块不报错
    def isatty(self):
        return False


sys.stdout = _TeeStdout(sys.stdout)


# ============================================================
#  工具函数
# ============================================================
def _is_wsl() -> bool:
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


IN_WSL = _is_wsl()


def get_wsl_home() -> str:
    try:
        if IN_WSL:
            r = subprocess.run(["bash", "-c", "echo ~clawuser"],
                               capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(["wsl", "-u", "clawuser", "-e", "bash", "-c", "echo ~clawuser"],
                               capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "/home/clawuser"


def run_wsl_command(cmd: str, timeout: int = 30) -> tuple:
    try:
        args = ["bash", "-c", cmd] if IN_WSL else ["wsl", "-u", "clawuser", "-e", "bash", "-c", cmd]
        r = subprocess.run(args, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)


def log(level: str, message: str):
    """统一日志：print 输出到控制台（已嵌入 GUI）+ 写文件备份"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}"
    print(line)
    try:
        CONFIG["log_file"].parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG["log_file"], "a", encoding="utf-8") as f:
            f.write(line + "\n")
        # 日志轮转：>1 MB 时保留最近 3000 行
        if CONFIG["log_file"].stat().st_size > 1_000_000:
            lines = CONFIG["log_file"].read_text(encoding="utf-8", errors="replace").splitlines()
            if len(lines) > 5000:
                CONFIG["log_file"].write_text("\n".join(lines[-3000:]) + "\n", encoding="utf-8")
    except Exception:
        pass
    try:
        log_queue.put_nowait((level, line))
    except queue.Full:
        pass


def gateway_output_reader(stream):
    """读取 gateway 子进程 stdout，写入日志文件（嵌入终端 tail -f 该文件）"""
    try:
        for raw in iter(stream.readline, ""):
            raw = raw.rstrip("\n\r")
            if raw:
                log("GATEWAY", raw)   # 同时写文件 + 发队列
    except Exception:
        pass


# ============================================================
#  检测函数
# ============================================================
def is_gateway_running() -> bool:
    """
    TCP 连接检测：直接从 Windows 连 127.0.0.1:{port}。
    WSL2 对 Windows localhost 透明，能建立 TCP 连接即为在线。
    比 WSL curl / ss 命令更快更可靠，不受进程名或响应格式影响。
    """
    port = CONFIG["gateway_port"]
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            return True
    except OSError:
        return False


def is_chrome_debugging_running(port: int) -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def is_chrome_process_running(port: int) -> bool:
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["powershell", "-Command",
                 f"Get-WmiObject Win32_Process -Filter \"name='chrome.exe'\" | "
                 f"Where-Object {{ $_.CommandLine -like '*--remote-debugging-port={port}*' }}"],
                capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace",
            )
            return f"--remote-debugging-port={port}" in r.stdout
        else:
            r = subprocess.run(
                ["pgrep", "-f", f"chrome.*--remote-debugging-port={port}"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
    except Exception:
        return False


def kill_chrome_process(port: int):
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-Command",
                 f"Get-WmiObject Win32_Process -Filter \"name='chrome.exe'\" | "
                 f"Where-Object {{ $_.CommandLine -like '*--remote-debugging-port={port}*' }} | "
                 f"ForEach-Object {{ $_.Terminate() }}"],
                capture_output=True, timeout=10,
            )
            time.sleep(2)
    except Exception as e:
        log("WARN", f"终止 Chrome 进程失败: {e}")


def start_chrome_debugging(port: int) -> bool:
    if is_chrome_debugging_running(port):
        log("INFO", f"Chrome 调试 ({port}) 已在运行")
        return True
    if is_chrome_process_running(port):
        log("WARN", f"Chrome ({port}) 进程存在但 HTTP 未响应，先终止旧进程")
        kill_chrome_process(port)
    try:
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        profile_dir = r"C:\ChromeDebugProfile" if port == 9315 else rf"C:\ChromeDebugProfile{port}"
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        # 重置 exit_type 避免恢复对话框
        prefs_path = Path(profile_dir) / "Default" / "Preferences"
        if prefs_path.exists():
            try:
                prefs = json.loads(prefs_path.read_text(encoding="utf-8", errors="replace"))
                if prefs.get("profile", {}).get("exit_type") == "Crashed":
                    prefs.setdefault("profile", {})["exit_type"] = "Normal"
                    prefs_path.write_text(json.dumps(prefs), encoding="utf-8")
            except Exception:
                pass

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run", "--no-default-browser-check",
            "--force-device-scale-factor=1",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
        ]
        ext = CONFIG.get("chrome_extension", "")
        if ext and Path(ext).exists():
            cmd.append(f"--load-extension={ext}")

        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("INFO", f"Chrome ({port}) 启动命令已发出")

        for i in range(15):
            time.sleep(2)
            if is_chrome_debugging_running(port):
                log("INFO", f"Chrome ({port}) 启动成功（等待 {(i+1)*2}s）")
                return True
        log("ERROR", f"Chrome ({port}) 启动超时")
        return False
    except Exception as e:
        log("ERROR", f"Chrome ({port}) 启动失败: {e}")
        return False


def start_gateway() -> bool:
    global gateway_proc
    log("INFO", "正在启动 Gateway...")
    try:
        if is_gateway_running():
            log("INFO", "Gateway 已在运行")
            return True
        wsl_cmd = (
            "mkdir -p /home/clawuser/.clawdbot && "
            "export PATH=/home/clawuser/.npm-global/bin:$PATH && "
            f"openclaw gateway run --port {CONFIG['gateway_port']} --force --verbose 2>&1"
        )
        popen_args = (["bash", "-c", wsl_cmd] if IN_WSL
                      else ["wsl", "-u", "clawuser", "-e", "bash", "-c", wsl_cmd])
        gateway_proc = subprocess.Popen(
            popen_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        threading.Thread(target=gateway_output_reader, args=(gateway_proc.stdout,), daemon=True).start()

        for i in range(30):
            time.sleep(2)
            if is_gateway_running():
                log("INFO", f"Gateway 启动成功（等待 {(i+1)*2}s）")
                return True
        log("ERROR", "Gateway 启动超时")
        return False
    except Exception as e:
        log("ERROR", f"Gateway 启动失败: {e}")
        return False


def stop_gateway():
    try:
        run_wsl_command("pkill -f openclaw-gateway", 10)
        log("INFO", "Gateway 已停止")
    except Exception:
        pass


# ============================================================
#  慢速查询（全部在后台线程执行，不阻塞 UI）
# ============================================================
def _proxy_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.proxies = {
        "http": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}",
        "https": f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}",
    }
    return s


def get_network_status() -> dict:
    res = {"proxy": False, "direct": False, "proxy_ip": "", "direct_ip": ""}
    # 检查 proxy 端口是否可达
    try:
        sock = socket.socket()
        sock.settimeout(3)
        sock.connect((CONFIG["proxy_host"], CONFIG["proxy_port"]))
        sock.close()
        res["proxy"] = True
    except Exception:
        pass
    # 通过 proxy 获取外网 IP
    if res["proxy"]:
        try:
            s = _proxy_session()
            r = s.get("https://api.ipify.org", timeout=8, verify=False)
            if r.status_code == 200:
                res["proxy_ip"] = r.text.strip()
        except Exception:
            pass
    # 直连检测 + 直连外网 IP（通过 WSL curl，无代理）
    try:
        rc, out, _ = run_wsl_command(
            "curl -s --max-time 6 --noproxy '*' https://api.ipify.org", 10
        )
        if rc == 0 and out.strip():
            res["direct_ip"] = out.strip()
            res["direct"] = True
    except Exception:
        pass
    return res


def get_minimax_quota() -> dict:
    res = {"status": "unknown", "percent": 0, "remaining": 0, "used": 0}
    try:
        s = _proxy_session()
        r = s.get(
            "https://api.minimaxi.com/v1/api/openplatform/coding_plan/remains",
            headers={"Authorization": f"Bearer {CONFIG['minimax_api_key']}"},
            timeout=10, verify=False,
        )
        if r.status_code == 200:
            for m in r.json().get("model_remains", []):
                if "MiniMax-M" in m.get("model_name", ""):
                    total = m.get("current_interval_total_count", 0)
                    used = m.get("current_interval_usage_count", 0)
                    res.update({
                        "status": "ok",
                        "remaining": m.get("remains_time", 0),
                        "used": used,
                        "percent": round(used / total * 100, 1) if total else 0,
                    })
                    break
    except Exception:
        pass
    return res


def get_telegram_status() -> dict:
    res = {"status": "unknown", "bot_name": "", "connect": "Proxy"}
    try:
        s = _proxy_session()
        r = s.get(
            f"https://api.telegram.org/bot{CONFIG['telegram_token']}/getMe",
            timeout=10, verify=False,
        )
        if r.status_code == 200 and r.json().get("ok"):
            res["status"] = "running"
            res["bot_name"] = r.json().get("result", {}).get("first_name", "")
    except Exception:
        res["status"] = "error"
    return res


def get_feishu_status() -> dict:
    """
    飞书状态检测（直连，不走代理）。
    优先用 Feishu Open API 验证 app_id/app_secret，
    fallback 到进程检测。
    """
    res = {"status": "unknown", "bot_name": "", "connect": "直连"}
    try:
        wsl_home = get_wsl_home()
        # 尝试多个可能的配置文件路径
        cfg_paths = [
            f"{wsl_home}/.openclaw/plugins/feishu/config.json",
            f"{wsl_home}/.openclaw/feishu.json",
            f"{wsl_home}/.openclaw/config/feishu.json",
        ]
        cfg_out = ""
        for path in cfg_paths:
            rc, out, _ = run_wsl_command(f"cat {path} 2>/dev/null", 8)
            if rc == 0 and out.strip():
                cfg_out = out.strip()
                break

        if cfg_out:
            try:
                cfg = json.loads(cfg_out)
                app_id     = cfg.get("app_id") or cfg.get("appId", "")
                app_secret = cfg.get("app_secret") or cfg.get("appSecret", "")
                bot_name   = cfg.get("bot_name") or cfg.get("botName", "Feishu Bot")
                res["bot_name"] = bot_name

                if app_id and app_secret:
                    # 直连调用 Feishu Open API 获取 tenant_access_token（验活）
                    r = requests.post(
                        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                        json={"app_id": app_id, "app_secret": app_secret},
                        timeout=8,
                    )
                    if r.status_code == 200 and r.json().get("code") == 0:
                        res["status"] = "running"
                        return res
                    else:
                        res["status"] = "error"
                        return res
            except Exception:
                pass

        # fallback：进程名检测（更宽泛的关键词）
        rc, ps_out, _ = run_wsl_command(
            "ps aux | grep -E 'feishu|lark|openclaw' | grep -v grep", 10
        )
        if rc == 0 and ps_out.strip():
            res["status"] = "running"
            if not res["bot_name"]:
                res["bot_name"] = "Feishu Bot"
        else:
            res["status"] = "stopped"
    except Exception:
        res["status"] = "error"
    return res


def get_cron_jobs() -> list:
    jobs = []
    try:
        wsl_home = get_wsl_home()
        rc, out, _ = run_wsl_command(f"cat {wsl_home}/.openclaw/cron/jobs.json 2>/dev/null", 10)
        if rc == 0 and out:
            for j in json.loads(out).get("jobs", []):
                state = j.get("state", {})
                nrms = state.get("nextRunAtMs")
                lrms = state.get("lastRunAtMs")
                sch = j.get("schedule", {})
                jobs.append({
                    "name":        j.get("name", "Unknown"),
                    "description": j.get("description", j.get("desc", "")),
                    "schedule":    sch.get("expr", "") if isinstance(sch, dict) else str(sch),
                    "next_run":    datetime.fromtimestamp(nrms / 1000) if nrms else None,
                    "last_run":    datetime.fromtimestamp(lrms / 1000) if lrms else None,
                    "last_status": state.get("lastRunStatus", "unknown"),
                    "enabled":     j.get("enabled", True),
                })
    except Exception:
        pass
    return jobs


# ============================================================
#  GUI 日志显示：_TeeStdout 队列 + ANSI 颜色解析
# ============================================================
class LogDisplay(ctk.CTkFrame):
    """
    从 _gui_print_queue 消费 print() 输出，解析 ANSI 转义码后按颜色渲染。
    Win32 嵌入在 Windows Terminal 环境下不可行，此方案跨终端类型稳定运行。
    """

    # ANSI 前景色映射（30-37 标准 + 90-97 高亮，与 Windows Terminal 默认色板一致）
    ANSI_FG: dict = {
        30: "#4d4d4d", 31: "#e74856", 32: "#16c60c", 33: "#f9f1a5",
        34: "#3b78ff", 35: "#b4009e", 36: "#61d6d6", 37: "#cccccc",
        90: "#767676", 91: "#f14c4c", 92: "#23d18b", 93: "#f5f543",
        94: "#3b8eea", 95: "#d670d6", 96: "#29b8db", 97: "#e5e5e5",
    }
    LEVEL_COLORS: dict = {
        "INFO": "#cccccc", "WARN": "#f5f543", "WARNING": "#f5f543",
        "ERROR": "#f14c4c", "GATEWAY": "#61d6d6", "STATUS": "#23d18b",
        "DEBUG": "#767676",
    }
    _ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="#0c0c0c", corner_radius=0, **kwargs)
        self._tb = CTkTextbox(
            self, font=("Consolas", 12), wrap="none",
            fg_color="#0c0c0c", text_color="#cccccc",
            scrollbar_button_color="#30363d",
            border_width=0, corner_radius=0,
        )
        self._tb.pack(fill="both", expand=True)
        self._tb.configure(state="disabled")
        tw = self._tb._textbox
        for code, color in self.ANSI_FG.items():
            tw.tag_config(f"a{code}", foreground=color)
        for lvl, color in self.LEVEL_COLORS.items():
            tw.tag_config(f"l{lvl}", foreground=color)
        self._poll()

    def _poll(self):
        tw = self._tb._textbox
        tw.configure(state="normal")
        try:
            for _ in range(100):
                text = _gui_print_queue.get_nowait()
                for line in text.splitlines():
                    if line.strip():
                        self._insert(tw, line)
        except queue.Empty:
            pass
        try:
            if int(tw.index("end-1c").split(".")[0]) > 2000:
                tw.delete("1.0", "200.0")
        except Exception:
            pass
        tw.configure(state="disabled")
        tw.see("end")
        self.after(150, self._poll)

    def _insert(self, tw, line: str):
        if self._ANSI_RE.search(line):
            # 含 ANSI 码：逐段着色
            cur = None
            pos = 0
            for m in self._ANSI_RE.finditer(line):
                chunk = line[pos:m.start()]
                if chunk:
                    tw.insert("end", chunk, (cur,) if cur else ())
                for part in (m.group(1) or "0").split(";"):
                    try:
                        n = int(part)
                    except ValueError:
                        continue
                    if n == 0 or n == 39:
                        cur = None
                    elif n in self.ANSI_FG:
                        cur = f"a{n}"
                pos = m.end()
            tail = line[pos:]
            if tail:
                tw.insert("end", tail, (cur,) if cur else ())
            tw.insert("end", "\n")
        else:
            # 无 ANSI 码：按 [LEVEL] 整行着色
            tag = ()
            m = re.search(r'\[(\w+)\]', line)
            if m:
                k = f"l{m.group(1).upper()}"
                if k in [f"l{x}" for x in self.LEVEL_COLORS]:
                    tag = (k,)
            tw.insert("end", line + "\n", tag)

    def clear(self):
        tw = self._tb._textbox
        tw.configure(state="normal")
        tw.delete("1.0", "end")
        tw.configure(state="disabled")

    def stop(self):
        pass


# ============================================================
#  主 GUI 应用
# ============================================================
class ClawdbotMonitorApp(CTk):
    def __init__(self):
        super().__init__()
        self.title("Clawdbot Gateway Monitor")
        self.geometry("1400x900")
        self.minsize(1100, 720)
        self._center_window()

        # 控制开关
        self.auto_restart = ctk.BooleanVar(value=True)
        self.auto_heal = ctk.BooleanVar(value=True)
        self.autostart_enabled = ctk.BooleanVar(value=self._read_autostart())

        # 监控状态
        self.monitoring = True
        self.consecutive_failures = 0

        # 慢速数据缓存（后台线程写 → 主线程读）
        self._cache_lock = threading.Lock()
        self._cache = {
            "network":  {"proxy": False, "direct": False, "external_ip": ""},
            "telegram": {"status": "unknown", "bot_name": ""},
            "feishu":   {"status": "unknown", "bot_name": ""},
            "quota":    {"status": "unknown", "percent": 0},
            "cron":     [],
        }
        self._slow_running = False
        self._slow_last_ts = 0.0

        # 队列：监控线程 → UI 线程
        self._mon_queue: queue.Queue = queue.Queue()
        self._heal_proc = None

        self._build_ui()

        # 启动状态检测线程（TCP 端口检测）
        threading.Thread(target=self._monitor_worker, daemon=True).start()
        # 启动自愈监控子进程线程
        threading.Thread(target=self._healing_worker, daemon=True).start()

        # 首次立刻触发一次慢速查询
        self._trigger_slow_update()

        # 启动 UI 刷新定时器
        self._tick_ui()

    # ----------------------------------------------------------
    def _center_window(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"1400x900+{(sw-1400)//2}+{(sh-900)//2}")

    def _read_autostart(self) -> bool:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run",
                               0, winreg.KEY_READ)
            winreg.QueryValueEx(k, "ClawdbotMonitor")
            winreg.CloseKey(k)
            return True
        except Exception:
            return False

    # ==================== UI 构建 ====================
    def _build_ui(self):
        # ---- 顶栏 ----
        hdr = CTkFrame(self, corner_radius=0, fg_color="#0d1117", height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        CTkLabel(hdr, text="🐾  Clawdbot Gateway Monitor",
                 font=("Segoe UI", 19, "bold"),
                 text_color="#e6edf3").pack(side="left", padx=16)

        self._hdr_status = CTkLabel(hdr, text="●  初始化中...",
                                    font=("Segoe UI", 12), text_color="#6e7681")
        self._hdr_status.pack(side="left", padx=8)

        btn_f = CTkFrame(hdr, fg_color="transparent")
        btn_f.pack(side="right", padx=12)
        _bc = dict(width=74, height=28, font=("Segoe UI", 12), corner_radius=6)
        CTkButton(btn_f, text="刷新",  command=self._manual_refresh,
                  fg_color="#1565c0", hover_color="#1976d2", **_bc).pack(side="left", padx=3)
        CTkButton(btn_f, text="启动",  command=self._start_gw,
                  fg_color="#1b5e20", hover_color="#2e7d32", **_bc).pack(side="left", padx=3)
        CTkButton(btn_f, text="停止",  command=self._stop_gw,
                  fg_color="#b71c1c", hover_color="#c62828", **_bc).pack(side="left", padx=3)
        CTkButton(btn_f, text="托盘",  command=self._to_tray,
                  fg_color="#37474f", hover_color="#455a64", **_bc).pack(side="left", padx=3)

        # ---- 主体 ----
        body = CTkFrame(self, corner_radius=0, fg_color="#161b22")
        body.pack(fill="both", expand=True, padx=8, pady=(6, 8))

        # 左栏
        left = CTkFrame(body, corner_radius=10, width=214, fg_color="#0d1117")
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self._build_left(left)

        # 右栏
        right = CTkFrame(body, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

    # ---- 左栏 ----
    def _build_left(self, p):
        _lp = dict(anchor="w", padx=14, pady=3)

        CTkLabel(p, text="控制选项",
                 font=("Segoe UI", 13, "bold"),
                 text_color="#e6edf3").pack(pady=(14, 6), padx=14, anchor="w")

        CTkSwitch(p, text="自动重启 Gateway",
                  variable=self.auto_restart,
                  onvalue=True, offvalue=False,
                  font=("Segoe UI", 12)).pack(**_lp)
        CTkSwitch(p, text="故障自动自愈",
                  variable=self.auto_heal,
                  onvalue=True, offvalue=False,
                  font=("Segoe UI", 12)).pack(**_lp)

        CTkButton(p, text="手动触发自愈", command=self._trigger_heal,
                  fg_color="#e65100", hover_color="#f4511e",
                  width=182, height=30,
                  font=("Segoe UI", 12)).pack(anchor="w", padx=14, pady=(10, 4))

        CTkFrame(p, height=1, fg_color="#30363d").pack(fill="x", padx=10, pady=12)

        CTkLabel(p, text="开机启动",
                 font=("Segoe UI", 13, "bold"),
                 text_color="#e6edf3").pack(pady=(0, 6), padx=14, anchor="w")
        CTkSwitch(p, text="开机自动启动",
                  variable=self.autostart_enabled,
                  onvalue=True, offvalue=False,
                  font=("Segoe UI", 12),
                  command=self._toggle_autostart).pack(**_lp)

        CTkFrame(p, height=1, fg_color="#30363d").pack(fill="x", padx=10, pady=12)

        CTkLabel(p, text="运行统计",
                 font=("Segoe UI", 13, "bold"),
                 text_color="#e6edf3").pack(pady=(0, 6), padx=14, anchor="w")
        self._stats_lbl = CTkLabel(
            p, text="连续失败: 0\n最后检查: --\n状态: 初始化",
            font=("Consolas", 12), anchor="w", justify="left",
            text_color="#8b949e",
        )
        self._stats_lbl.pack(**_lp)

    # ---- 右栏 ----
    def _build_right(self, p):
        # 状态卡片行
        card_row = CTkFrame(p, corner_radius=10, fg_color="#0d1117", height=148)
        card_row.pack(fill="x", pady=(0, 8))
        card_row.pack_propagate(False)

        for attr, title, icon in [
            ("_card_gw",   "Gateway",  "🖥️"),
            ("_card_chr",  "Chrome",   "🌐"),
            ("_card_net",  "网络",     "📶"),
            ("_card_tg",   "Telegram", "💬"),
            ("_card_fs",   "Feishu",   "📱"),
            ("_card_qt",   "API 额度", "💰"),
        ]:
            c = self._make_card(card_row, title, icon)
            c.pack(side="left", fill="both", expand=True, padx=5, pady=8)
            setattr(self, attr, c)

        # ---- Cron 任务表格（ttk.Treeview）----
        cron_f = CTkFrame(p, corner_radius=10, fg_color="#0d1117", height=220)
        cron_f.pack(fill="x", pady=(0, 8))
        cron_f.pack_propagate(False)

        CTkLabel(cron_f, text="定时任务 (Cron Jobs)",
                 font=("Segoe UI", 13, "bold"),
                 text_color="#e6edf3").pack(anchor="w", padx=12, pady=(8, 3))

        # 深色主题
        _ts = ttk.Style()
        _ts.theme_use("clam")
        _ts.configure("Cron.Treeview",
            background="#0d1117", foreground="#c9d1d9",
            rowheight=22, fieldbackground="#0d1117",
            borderwidth=0, font=("Consolas", 12),
        )
        _ts.configure("Cron.Treeview.Heading",
            background="#161b22", foreground="#8be9fd",
            font=("Segoe UI", 12, "bold"), relief="flat", borderwidth=0,
        )
        _ts.map("Cron.Treeview",
            background=[("selected", "#264f78")],
            foreground=[("selected", "#e6edf3")],
        )

        tv_wrap = tk.Frame(cron_f, bg="#0d1117")
        tv_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        cols = ("name", "schedule", "next_run", "last_run", "last_status", "description")
        self._cron_tv = ttk.Treeview(
            tv_wrap, columns=cols, show="tree headings",
            style="Cron.Treeview", height=5, selectmode="none",
        )
        # 列定义
        self._cron_tv.heading("#0",           text=" 状",    anchor="w")
        self._cron_tv.column("#0",            width=28, minwidth=28, stretch=False)
        self._cron_tv.heading("name",         text="名称",   anchor="w")
        self._cron_tv.column("name",          width=160, minwidth=80)
        self._cron_tv.heading("schedule",     text="计划",   anchor="w")
        self._cron_tv.column("schedule",      width=150, minwidth=80)
        self._cron_tv.heading("next_run",     text="下次执行", anchor="w")
        self._cron_tv.column("next_run",      width=105, minwidth=70)
        self._cron_tv.heading("last_run",     text="上次执行", anchor="w")
        self._cron_tv.column("last_run",      width=105, minwidth=70)
        self._cron_tv.heading("last_status",  text="状态",   anchor="center")
        self._cron_tv.column("last_status",   width=48,  minwidth=40, anchor="center")
        self._cron_tv.heading("description",  text="描述",   anchor="w")
        self._cron_tv.column("description",   width=400, minwidth=100)
        # 行颜色 tag
        self._cron_tv.tag_configure("ok",       foreground="#c9d1d9")
        self._cron_tv.tag_configure("error",    foreground="#ff5555")
        self._cron_tv.tag_configure("unknown",  foreground="#8b949e")
        self._cron_tv.tag_configure("disabled", foreground="#484f58")
        # 横向滚动条
        xsb = ttk.Scrollbar(tv_wrap, orient="horizontal", command=self._cron_tv.xview)
        self._cron_tv.configure(xscrollcommand=xsb.set)
        xsb.pack(side="bottom", fill="x")
        self._cron_tv.pack(fill="both", expand=True)

        # ---- 实时日志 ----
        log_f = CTkFrame(p, corner_radius=10, fg_color="#0d1117")
        log_f.pack(fill="both", expand=True)

        log_hdr = CTkFrame(log_f, fg_color="transparent", height=36)
        log_hdr.pack(fill="x", padx=12, pady=(8, 0))
        log_hdr.pack_propagate(False)
        CTkLabel(log_hdr, text="实时日志",
                 font=("Segoe UI", 13, "bold"),
                 text_color="#e6edf3").pack(side="left")
        CTkButton(log_hdr, text="清空", width=60, height=24,
                  font=("Segoe UI", 11), fg_color="#30363d", hover_color="#3d444d",
                  command=lambda: self._term.clear()).pack(side="right")

        self._term = LogDisplay(log_f)
        self._term.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def _make_card(self, parent, title: str, icon: str) -> CTkFrame:
        card = CTkFrame(parent, corner_radius=8, fg_color="#161b22")
        CTkLabel(card, text=icon, font=("Segoe UI Emoji", 22)).pack(pady=(10, 1))
        CTkLabel(card, text=title, font=("Segoe UI", 10),
                 text_color="#6e7681").pack()
        val = CTkLabel(card, text="检测中...", font=("Segoe UI", 12, "bold"),
                       text_color="#8b949e")
        val.pack(pady=(2, 8))
        card._val = val
        return card

    def _set_card(self, card, text: str, ok=None):
        """ok=True→绿  ok=False→红  ok=None→黄"""
        card._val.configure(text=text)
        if ok is True:
            card._val.configure(text_color="#50fa7b")
        elif ok is False:
            card._val.configure(text_color="#ff5555")
        else:
            card._val.configure(text_color="#f1fa8c")

    # ==================== 后台监控线程 ====================
    # ---- 状态检测线程（仅更新卡片，不负责重启）----
    def _monitor_worker(self):
        """每 30s 做一次 TCP 端口检测，更新状态卡片"""
        while self.monitoring:
            try:
                gw = self._port_open(CONFIG["gateway_port"])
                c1 = self._port_open(CONFIG["chrome_debug_port"])
                c2 = self._port_open(CONFIG["chrome_cron_port"])
                self._mon_queue.put({"gw": gw, "c1": c1, "c2": c2, "ts": datetime.now()})
            except Exception as e:
                log("ERROR", f"状态检测异常: {e}")
            time.sleep(CONFIG["check_interval"])

    @staticmethod
    def _port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            return False

    # ---- 自愈监控子进程线程 ----
    def _healing_worker(self):
        """运行 clawdbot-monitor-self-healing.py，输出实时显示在 GUI 日志区"""
        script = Path(__file__).parent / "clawdbot-monitor-self-healing.py"
        if not script.exists():
            log("ERROR", f"找不到自愈脚本: {script}")
            return

        while self.monitoring:
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                self._heal_proc = proc
                log("INFO", f"自愈监控已启动 (PID {proc.pid})")

                for line in iter(proc.stdout.readline, ""):
                    if not self.monitoring:
                        break
                    line = line.rstrip("\n\r")
                    if line:
                        print(line)   # → _TeeStdout → _gui_print_queue → LogDisplay

                proc.stdout.close()
                proc.wait()

                if not self.monitoring:
                    break
                log("WARN", "自愈监控进程意外退出，5 秒后重启...")
                time.sleep(5)
            except Exception as e:
                log("ERROR", f"自愈监控启动失败: {e}")
                time.sleep(10)

    # ---- 慢速查询后台线程 ----
    def _trigger_slow_update(self):
        if self._slow_running:
            return
        self._slow_running = True
        self._slow_last_ts = time.time()
        threading.Thread(target=self._slow_worker, daemon=True).start()

    def _slow_worker(self):
        try:
            results = {
                "network":  get_network_status(),
                "telegram": get_telegram_status(),
                "feishu":   get_feishu_status(),
                "quota":    get_minimax_quota(),
                "cron":     get_cron_jobs(),
            }
            with self._cache_lock:
                self._cache.update(results)
        except Exception as e:
            log("DEBUG", f"慢速查询异常: {e}")
        finally:
            self._slow_running = False

    # ==================== UI 定时刷新（每 3s）====================
    def _tick_ui(self):
        try:
            # 1. 消费监控队列（只取最新一条）
            latest = None
            while True:
                try:
                    latest = self._mon_queue.get_nowait()
                except queue.Empty:
                    break
            if latest:
                self._apply_mon(latest)

            # 2. 每 60s 触发一次慢速查询（后台线程）
            if time.time() - self._slow_last_ts > 60 and not self._slow_running:
                self._trigger_slow_update()

            # 3. 从缓存刷新慢速卡片
            self._refresh_slow_cards()

        except Exception:
            pass

        self.after(3000, self._tick_ui)

    def _apply_mon(self, d: dict):
        gw, c1, c2 = d["gw"], d["c1"], d["c2"]

        self._set_card(self._card_gw, "运行中" if gw else "已停止", gw)

        chr_txt = f"9315:{'✓' if c1 else '✗'}  9316:{'✓' if c2 else '✗'}"
        self._set_card(self._card_chr, chr_txt,
                       True if (c1 and c2) else (None if (c1 or c2) else False))

        dot_color = "#50fa7b" if gw else "#ff5555"
        self._hdr_status.configure(
            text=f"●  Gateway {'运行中' if gw else '已停止'}",
            text_color=dot_color,
        )
        self._stats_lbl.configure(
            text=f"连续失败: {self.consecutive_failures}\n"
                 f"最后检查: {d['ts'].strftime('%H:%M:%S')}\n"
                 f"状态: {'运行中' if gw else '已停止'}",
        )

        # 同步刷新 Cron（使用当前缓存）
        with self._cache_lock:
            jobs = list(self._cache["cron"])
        self._refresh_cron(jobs)

    def _refresh_slow_cards(self):
        with self._cache_lock:
            net    = dict(self._cache["network"])
            tg     = dict(self._cache["telegram"])
            feishu = dict(self._cache["feishu"])
            quota  = dict(self._cache["quota"])

        # 网络 — 分两行显示 proxy IP 和直连 IP
        net_lines = []
        if net["proxy"]:
            ip = net["proxy_ip"] or "---"
            net_lines.append(f"Proxy ✓  {ip}")
        else:
            net_lines.append("Proxy ✗")
        if net["direct"]:
            ip = net["direct_ip"] or "---"
            net_lines.append(f"直连  ✓  {ip}")
        else:
            net_lines.append("直连  ✗")
        net_ok = net["proxy"] or net["direct"]
        self._set_card(self._card_net, "\n".join(net_lines),
                       True if net_ok else False)

        # Telegram — 标注走 Proxy
        if tg["status"] == "running":
            self._set_card(self._card_tg,
                           f"✓ {tg['bot_name']}\nvia Proxy", True)
        elif tg["status"] == "error":
            self._set_card(self._card_tg, "连接错误\nvia Proxy", False)
        else:
            self._set_card(self._card_tg, "检测中...", None)

        # Feishu — 标注走直连
        if feishu["status"] == "running":
            self._set_card(self._card_fs,
                           f"✓ {feishu['bot_name']}\n直连", True)
        elif feishu["status"] == "stopped":
            self._set_card(self._card_fs, "已停止\n直连", None)
        elif feishu["status"] == "error":
            self._set_card(self._card_fs, "连接错误\n直连", False)
        else:
            self._set_card(self._card_fs, "检测中...", None)

        # API 额度（percent 字段 = 剩余百分比）
        if quota["status"] == "ok":
            pct = quota["percent"]
            # 剩余多 → 绿；剩余少 → 黄/红
            self._set_card(self._card_qt, f"剩余 {pct:.1f}%",
                           True if pct > 50 else (None if pct > 20 else False))
        elif quota["status"] == "unknown":
            self._set_card(self._card_qt, "检测中...", None)
        else:
            self._set_card(self._card_qt, "查询失败", False)

    def _refresh_cron(self, jobs: list):
        """用 ttk.Treeview 刷新定时任务表格，按下次执行时间升序排列"""
        for item in self._cron_tv.get_children():
            self._cron_tv.delete(item)

        # 按 next_run 升序：有时间的排前面，None 排最后
        jobs = sorted(jobs, key=lambda j: (j["next_run"] is None, j["next_run"] or 0))

        for j in jobs:
            dot = "●" if j["enabled"] else "○"
            ls  = j["last_status"]
            lr  = "✓" if ls == "ok" else ("✗" if ls == "error" else "?")
            nt  = j["next_run"].strftime("%m-%d %H:%M") if j["next_run"] else "---"
            lt  = j["last_run"].strftime("%m-%d %H:%M") if j.get("last_run") else "---"
            desc = j.get("description") or ""
            tag  = ("disabled" if not j["enabled"]
                    else ("ok" if ls == "ok"
                          else ("error" if ls == "error" else "unknown")))
            self._cron_tv.insert(
                "", "end",
                text=dot,
                values=(j["name"], j["schedule"], nt, lt, lr, desc),
                tags=(tag,),
            )

    # ==================== 操作回调 ====================
    def _manual_refresh(self):
        log("INFO", "手动刷新触发，强制重新查询所有状态")
        self._slow_last_ts = 0.0  # 下次 tick 立即触发慢速查询

    def _start_gw(self):
        log("INFO", "手动启动 Gateway...")
        threading.Thread(
            target=lambda: log("INFO", "Gateway 启动" + ("成功" if start_gateway() else "失败")),
            daemon=True,
        ).start()

    def _stop_gw(self):
        log("INFO", "手动停止 Gateway...")
        threading.Thread(target=stop_gateway, daemon=True).start()

    def _trigger_heal(self):
        """调用 self-healing --fix 执行手动修复"""
        log("INFO", "触发自愈流程...")
        script = Path(__file__).parent / "clawdbot-monitor-self-healing.py"
        def _run():
            proc = subprocess.Popen(
                [sys.executable, str(script), "--fix"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip("\n\r")
                if line:
                    print(line)
            proc.stdout.close()
            proc.wait()
        threading.Thread(target=_run, daemon=True).start()

    def _toggle_autostart(self):
        if self.autostart_enabled.get():
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                   r"Software\Microsoft\Windows\CurrentVersion\Run",
                                   0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(k, "ClawdbotMonitor", 0, winreg.REG_SZ,
                                  f'"{sys.executable}" "{os.path.abspath(__file__)}"')
                winreg.CloseKey(k)
                log("INFO", "已开启开机自启动")
            except Exception as e:
                log("ERROR", f"设置自启动失败: {e}")
        else:
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                   r"Software\Microsoft\Windows\CurrentVersion\Run",
                                   0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(k, "ClawdbotMonitor")
                winreg.CloseKey(k)
                log("INFO", "已关闭开机自启动")
            except Exception:
                pass

    # ==================== 托盘 ====================
    def _to_tray(self):
        self.withdraw()
        if not (hasattr(self, "_tray_win") and self._tray_win.winfo_exists()):
            self._make_tray_widget()

    def _make_tray_widget(self):
        """右下角悬浮小窗（pystray 不可用时的替代方案）"""
        tw = ctk.CTkToplevel(self)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.configure(fg_color="#0d1117")

        sw, sh = tw.winfo_screenwidth(), tw.winfo_screenheight()
        # 定位在右下角，留出足够空间避免被任务栏遮挡
        tw.geometry(f"140x120+{sw-150}+{sh-170}")

        # 拖拽状态
        _drag = {"x": 0, "y": 0}

        def _on_drag_start(e):
            _drag["x"] = e.x_root - tw.winfo_x()
            _drag["y"] = e.y_root - tw.winfo_y()

        def _on_drag_move(e):
            tw.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")

        # 顶部拖拽区域（标题栏替代）
        drag_lbl = CTkLabel(tw, text="🐾  Clawdbot  ✥",
                            font=("Segoe UI", 11, "bold"),
                            fg_color="#1565c0", corner_radius=5,
                            width=120, height=26,
                            text_color="white",
                            cursor="fleur")
        drag_lbl.pack(pady=(6, 4))
        drag_lbl.bind("<ButtonPress-1>", _on_drag_start)
        drag_lbl.bind("<B1-Motion>", _on_drag_move)
        # 也允许在整个窗口上拖拽（避免死角）
        tw.bind("<ButtonPress-1>", _on_drag_start)
        tw.bind("<B1-Motion>", _on_drag_move)

        self._tray_status = CTkLabel(tw, text="监控运行中",
                                      font=("Segoe UI", 10),
                                      text_color="#50fa7b")
        self._tray_status.pack()

        CTkButton(tw, text="打开主界面", width=120, height=28,
                  font=("Segoe UI", 10),
                  fg_color="#1b5e20", hover_color="#2e7d32",
                  command=lambda: self._restore(tw)).pack(pady=(4, 2))

        CTkButton(tw, text="退出", width=120, height=26,
                  font=("Segoe UI", 10),
                  fg_color="#b71c1c", hover_color="#c62828",
                  command=self._quit_app).pack(pady=(0, 4))

        self._tray_win = tw

    def _restore(self, tw=None):
        self.deiconify()
        self.lift()
        if tw and tw.winfo_exists():
            tw.destroy()

    def _quit_app(self):
        self.monitoring = False
        try:
            self._term.stop()
        except Exception:
            pass
        # 终止自愈监控子进程
        try:
            if self._heal_proc and self._heal_proc.poll() is None:
                self._heal_proc.terminate()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)


# ============================================================
#  入口
# ============================================================
if __name__ == "__main__":
    log("INFO", "Clawdbot Gateway Monitor GUI 启动")
    app = ClawdbotMonitorApp()
    app.protocol("WM_DELETE_WINDOW", app._to_tray)
    app.mainloop()
