#!/bin/bash
# 使用前请替换以下占位符为你的实际值
# ANTHROPIC_BASE_URL: Claude API 地址 (如 https://api.minimax.com/anthropic)
# ANTHROPIC_AUTH_TOKEN: 你的 Claude API Key
cmd.exe /c "set ANTHROPIC_BASE_URL=https://api.minimax.com/anthropic && set ANTHROPIC_AUTH_TOKEN=YOUR_CLAUDE_KEY && claude -p \"$1\""
