#!/bin/bash
cd /home/pascal/.openclaw/workspace
git add -A
if git diff --cached --quiet; then
    echo "No changes to commit"
else
    git commit -m "Auto commit: $(date '+%Y-%m-%d %H:%M')"
    git push github main
    echo "Pushed to GitHub at $(date)"
fi
