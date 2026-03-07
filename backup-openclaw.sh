#!/bin/bash
# OpenClaw 打包脚本
# 用法: ./backup-openclaw.sh [输出路径]
# 默认输出到当前目录

OUTPUT_DIR="${1:-.}"

# 获取当前日期
DATE=$(date +%Y%m%d)

# 打包文件名
BACKUP_FILE="openclaw-backup-${DATE}.tar.gz"

# 要打包的目录
SOURCES=(
    "$HOME/.openclaw/"
    "$HOME/clawd/"
    "$HOME/.config/opencode/"
)

echo "📦 正在打包 OpenClaw..."
echo "输出文件: $OUTPUT_DIR/$BACKUP_FILE"

# 排除不需要的目录
EXCLUDE_ARGS=(
    --exclude=".git"
    --exclude="node_modules"
    --exclude="*.log"
    --exclude="logs"
    --exclude="media/inbound"
    --exclude="media/outbound"
    --exclude=".openclaw/logs"
    --exclude=".openclaw/browser"
    --exclude=".openclaw/media"
    --exclude=".openclaw/delivery-queue"
)

# 创建打包
tar czf "$OUTPUT_DIR/$BACKUP_FILE" "${EXCLUDE_ARGS[@]}" "${SOURCES[@]}"

# 获取文件大小
SIZE=$(du -h "$OUTPUT_DIR/$BACKUP_FILE" | cut -f1)

echo "✅ 打包完成！"
echo "📁 文件: $OUTPUT_DIR/$BACKUP_FILE"
echo "📊 大小: $SIZE"
