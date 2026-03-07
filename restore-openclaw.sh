#!/bin/bash
# OpenClaw 恢复脚本
# 用法: ./restore-openclaw.sh <备份文件路径>
# 会精确覆盖对应目录

if [ -z "$1" ]; then
    echo "用法: $0 <备份文件路径>"
    echo "示例: $0 ~/Downloads/openclaw-backup-20260227.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ 错误: 找不到备份文件 $BACKUP_FILE"
    exit 1
fi

echo "⚠️  即将覆盖以下目录:"
echo "  - ~/.openclaw/"
echo "  - ~/clawd/"
echo "  - ~/.config/opencode/"
echo ""
read -p "确认继续? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "已取消"
    exit 0
fi

# 备份目标目录（如果有）
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
if [ -d "$HOME/.openclaw" ]; then
    echo "📁 备份现有配置到 ~/.openclaw.backup.$TIMESTAMP"
    mv "$HOME/.openclaw" "$HOME/.openclaw.backup.$TIMESTAMP"
fi

echo "📦 正在解压..."
tar xzf "$BACKUP_FILE" -C "$HOME"

# 修复权限
chmod 700 "$HOME/.openclaw"
chmod 700 "$HOME/clawd"

echo "✅ 恢复完成！"
echo ""
echo "⚠️  请注意:"
echo "  1. 重新启动 Gateway: proxychains npx openclaw gateway run --port 18789"
echo "  2. 检查 Telegram/飞书 配置是否正确"
