#!/bin/bash
# OpenClaw Gateway Monitor
# 自动监控 OpenClaw Gateway 连接状态，断连时自动重连

# 配置
GATEWAY_PORT=18789
CHECK_INTERVAL=30  # 检查间隔（秒）
MAX_RETRIES=5      # 最大重试次数
RETRY_DELAY=5      # 重试间隔（秒）
LOG_FILE="$HOME/.clawdbot/monitor.log"

# 确保日志目录存在
mkdir -p "$(dirname "$LOG_FILE")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    
    case $level in
        "INFO")
            echo -e "${GREEN}[$timestamp] $message${NC}"
            ;;
        "WARN")
            echo -e "${YELLOW}[$timestamp] $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}[$timestamp] $message${NC}"
            ;;
    esac
}

# 检查 Gateway 是否运行
check_gateway() {
    curl -s "http://localhost:$GATEWAY_PORT/health" > /dev/null 2>&1
    return $?
}

# 启动 Gateway
start_gateway() {
    log "INFO" "尝试启动 OpenClaw Gateway..."
    
    # 先停止可能存在的旧进程
    openclaw gateway stop > /dev/null 2>&1
    
    # 启动新进程
    openclaw gateway run --port $GATEWAY_PORT --force --verbose > /dev/null 2>&1 &
    
    # 等待启动
    sleep 3
    
    # 检查是否启动成功
    if check_gateway; then
        log "INFO" "Gateway 启动成功"
        return 0
    else
        log "ERROR" "Gateway 启动失败"
        return 1
    fi
}

# 重新连接
reconnect() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log "INFO" "尝试重新连接 (第 $attempt/$MAX_RETRIES 次)..."
        
        # 检查是否已有进程
        if check_gateway; then
            log "INFO" "Gateway 已经在运行"
            return 0
        fi
        
        # 尝试启动
        if start_gateway; then
            log "INFO" "重新连接成功"
            return 0
        fi
        
        # 等待后重试
        if [ $attempt -lt $MAX_RETRIES ]; then
            log "INFO" "等待 ${RETRY_DELAY}秒后重试..."
            sleep $RETRY_DELAY
        fi
        
        attempt=$((attempt + 1))
    done
    
    log "ERROR" "重新连接失败，已达到最大重试次数"
    return 1
}

# 主监控循环
monitor() {
    log "INFO" "========================================="
    log "INFO" "OpenClaw Gateway Monitor 启动"
    log "INFO" "端口: $GATEWAY_PORT"
    log "INFO" "检查间隔: ${CHECK_INTERVAL}秒"
    log "INFO" "========================================="
    
    # 初始检查
    if check_gateway; then
        log "INFO" "Gateway 正在运行"
    else
        log "WARN" "Gateway 未运行，尝试启动..."
        reconnect
    fi
    
    # 主循环
    while true; do
        if check_gateway; then
            # 连接正常
            sleep $CHECK_INTERVAL
        else
            # 连接断开
            log "WARN" "检测到 Gateway 断开连接"
            reconnect
            sleep $CHECK_INTERVAL
        fi
    done
}

# 显示状态
status() {
    if check_gateway; then
        echo -e "${GREEN}Gateway 运行正常 (端口: $GATEWAY_PORT)${NC}"
        curl -s "http://localhost:$GATEWAY_PORT/health" 2>/dev/null | head -c 200
    else
        echo -e "${RED}Gateway 未运行${NC}"
    fi
}

# 停止监控
stop() {
    log "INFO" "停止监控..."
    # 杀死监控进程
    pkill -f "clawdbot-monitor.sh" 2>/dev/null
    log "INFO" "监控已停止"
}

# 帮助信息
help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动监控（默认）"
    echo "  status    显示状态"
    echo "  stop      停止监控"
    echo "  restart   重启监控"
    echo "  help      显示帮助"
    echo ""
    echo "配置文件:"
    echo "  端口: $GATEWAY_PORT"
    echo "  检查间隔: ${CHECK_INTERVAL}秒"
    echo "  日志: $LOG_FILE"
}

# 主程序
case "${1:-start}" in
    start)
        monitor
        ;;
    status)
        status
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        monitor
        ;;
    help|--help|-h)
        help
        ;;
    *)
        echo "未知命令: $1"
        help
        exit 1
        ;;
esac
