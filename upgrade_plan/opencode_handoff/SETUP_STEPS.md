SETUP: continue the upgrade in opencode (Opus 5.5) on the Mac

1. Get the latest planning branch into a separate clone (not inside your old "Terminal Bench" folder and not inside the new mc2 root):
   git clone -b claude/youthful-feynman-zug0uq <repo url> ~/Desktop/mc2_upgrade
   (If you already have a clone: git fetch origin claude/youthful-feynman-zug0uq, then git checkout claude/youthful-feynman-zug0uq, then git pull.)
2. Put the session rules where opencode loads them by itself, at the clone root, so they stay in the system prompt even after a compression:
   cp ~/Desktop/mc2_upgrade/upgrade_plan/opencode_handoff/AGENTS.md ~/Desktop/mc2_upgrade/AGENTS.md
   cp -R ~/Desktop/mc2_upgrade/upgrade_plan/opencode_handoff/.opencode ~/Desktop/mc2_upgrade/.opencode
   The .opencode/dcp.jsonc there sets DCP to manual for this folder only. Check: start opencode in that folder; the DCP notice should say manual mode.
3. Start opencode from the clone root with Opus 5.5 (anthropic, variant high):
   cd ~/Desktop/mc2_upgrade, then opencode
4. Paste upgrade_plan/opencode_handoff/START_PROMPT.md. The session answers in 5 lines and waits for you.
5. Recreate the mc2 worktree from the bundle (the session can do this with you), inside the clone:
   git fetch upgrade_plan/delivery/mc2.bundle "refs/heads/mc2-v2:refs/heads/mc2-v2" "refs/heads/mc2-stable:refs/heads/mc2-stable" --tags
   git worktree add ../mc2_worktree mc2-v2
   Changes to the new system are made there and committed as new tags (mc2-v2.6 and up after STAGE B approval).
6. Before every compression paste COMPACT_PROMPT.md, compress, then paste START_PROMPT.md again.
7. Pushing: the session commits upgrade_plan/ and the worktree; you push yourself, for example:
   git push origin claude/youthful-feynman-zug0uq
   git push origin mc2-v2 mc2-stable --tags
8. The first job is item 1 of NEXT.md: install STAGE A in the new root following upgrade_plan/delivery/README.md.

Notes
1. AGENTS.md at the clone root and .opencode/ are local helper files; do not commit them (or commit them if you want them on the branch; they hold no secrets).
2. Your global opencode config, plugins and the old system are not changed by any of this.
