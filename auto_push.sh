#!/bin/bash
cd /home/pascal/.openclaw/workspace

# Add all changes
git add -A

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "No changes to commit"
else
    # Commit with timestamp
    git commit -m "Auto commit: $(date '+%Y-%m-%d %H:%M')"
    
    # Push to github
    git push github main
    echo "Pushed to GitHub at $(date)"
fi
