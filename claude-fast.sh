#!/bin/bash
cmd.exe /c "set ANTHROPIC_BASE_URL=https://cc.zhihuiapi.top && set ANTHROPIC_AUTH_TOKEN=XXX_CLAUDE_KEY && claude -p \"$1\""
