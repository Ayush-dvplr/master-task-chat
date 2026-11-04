#!/bin/bash
# Refresh the simulated ROOT from the worktree: remove every file tracked at the previous tag, then
# copy every tracked and new (not ignored) worktree file. DATA files (ignored) are left alone.
set -e
W=/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2
R=/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/mc2_test/ROOT
PREV=${1:?previous tag}
cd "$W"
git ls-tree -r --name-only "$PREV" | while IFS= read -r f; do rm -f "$R/$f"; done
git ls-files -co --exclude-standard -z | tar --null -T - -cf - | tar -xf - -C "$R"
find "$R" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "refreshed $R from worktree (removed files of $PREV first); version: $(grep version "$R/SYSTEM_VERSION")"
