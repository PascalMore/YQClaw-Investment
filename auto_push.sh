#!/bin/bash
cd /home/pascal/.openclaw/workspace-yquant

# 初始化并更新所有子模块
git submodule update --init --recursive

# 子模块有变更时先提交子模块
git submodule foreach 'git add -A && git diff --cached --quiet || (git commit -m "Auto commit sub: $(date '+%Y-%m-%d %H:%M')" && git push origin HEAD)'

# 主仓库提交
git add -A
if git diff --cached --quiet; then
    echo "No changes to commit"
else
    git commit -m "Auto commit: $(date '+%Y-%m-%d %H:%M')"
    git push origin main
    echo "Pushed to GitHub at $(date)"
fi