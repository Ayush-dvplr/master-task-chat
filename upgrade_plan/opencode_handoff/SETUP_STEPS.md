SETUP: continue the upgrade in opencode (Opus 5.5) on the Mac. These steps make the PLANNING clone (the upgrade plan, the helper prompts and the delivery folder). Installing the NEW system itself is a different text: upgrade_plan/delivery/README.md (the INSTALL guide), step 8 below.

Every line indented by four spaces is one command for Terminal (zsh). Paths are in double quotes.

1. Get the planning branch into its own new folder. Never run these commands inside "/Users/mac/Desktop/Terminal Bench": that folder is the live old system, and a checkout there would switch the files the old system runs on. Never use the new root "/Users/mac/Desktop/mc2_root" either.
    setopt interactivecomments
    PLAN="/Users/mac/Desktop/mc2_upgrade"
    git clone -b claude/youthful-feynman-zug0uq https://github.com/Ayush-dvplr/master-task-chat.git "$PLAN"
   Size: the branch carries master_chat_work, so the clone is about 2.2 GB checked out (about 40000 files) plus about 840 MB in .git; keep 4 GB free and expect several minutes. If "$PLAN" already exists and is this planning clone (git -C "$PLAN" branch --show-current prints claude/youthful-feynman-zug0uq), update it instead:
    git -C "$PLAN" pull
   If git -C "$PLAN" rev-parse --show-toplevel prints any other folder, stop and ask.

2. Put the session rules where opencode loads them by itself, at the clone root, so they stay in the system prompt even after a compression. Both commands copy into the clone root, so running them again overwrites in place and never nests a folder:
    cp "$PLAN/upgrade_plan/opencode_handoff/AGENTS.md" "$PLAN/AGENTS.md"
    cp -R "$PLAN/upgrade_plan/opencode_handoff/.opencode" "$PLAN/"
   The .opencode/dcp.jsonc there sets DCP to manual for this folder only and protects AGENTS.md, RESUME.md and the plan README from pruning. Check: start opencode in that folder; the DCP notice should say manual mode.

3. Start opencode from the clone root with Opus 5.5 (anthropic, variant high):
    cd "$PLAN"
    opencode

4. Paste upgrade_plan/opencode_handoff/START_PROMPT.md. The session answers in 5 lines and waits for you.

5. The mc2 worktree: the session's working copy of the new system's git branch mc2-v2, used only to change the new system (new commits and tags). It is not ROOT and nothing runs from it. Run from the clone root; the worktree goes to a fixed folder next to the clone:
    cd "$PLAN"
    git fetch upgrade_plan/delivery/mc2.bundle "+refs/heads/mc2-v2:refs/remotes/bundle/mc2-v2" "+refs/heads/mc2-stable:refs/remotes/bundle/mc2-stable" --tags
    git worktree add -b mc2-v2 "/Users/mac/Desktop/mc2_worktree" bundle/mc2-v2
   If "/Users/mac/Desktop/mc2_worktree" already exists from an earlier setup, skip both lines: the worktree is already there.
   Only writer of mc2-v2 (Ayush, 4 Nov, ENTRY 94): from now on the opencode session on the Mac is the ONLY writer of the new system's branch mc2-v2 and its tags. The cloud planning session never changes it again, and mc2.bundle stays frozen at mc2-v2.5.2: it is only the starting point for this worktree and for ROOT, and no newer bundle will come. The opencode session commits in the worktree (its commits and tags land in this planning clone's git, since the worktree shares it). New commits get new tags (mc2-v2.6 and up after the STAGE B approval; a fix release gets three numbers such as mc2-v2.5.3), always lightweight tags. Never force a branch or move an existing tag.
   How ROOT gets a version made here: ROOT's git remote "origin" first points at the bundle file. Before the first new version, point it at this planning clone once, so the fetch line that upgrade.py prints brings the new tags from here:
    git -C "/Users/mac/Desktop/mc2_root" remote set-url origin "/Users/mac/Desktop/mc2_upgrade"
   Then upgrade ROOT as usual (INSTALL guide: backup, preflight, the printed commands, recheck).

6. Before every compression paste COMPACT_PROMPT.md, compress, then paste START_PROMPT.md again.

7. Pushing: the session commits upgrade_plan/ and the worktree; you push yourself, only named refs, for example:
    git -C "$PLAN" push origin claude/youthful-feynman-zug0uq
   The mc2 branches and tags are pushed from ROOT (INSTALL guide step 14); local before-* marker tags are never pushed.

8. The first job is item 1 of NEXT.md: install the new system following the INSTALL guide upgrade_plan/delivery/README.md.

Notes
1. AGENTS.md at the clone root and .opencode/ are local helper files; do not commit them (or commit them if you want them on the branch; they hold no secrets).
2. Your global opencode config, plugins and the old system are not changed by any of this.
