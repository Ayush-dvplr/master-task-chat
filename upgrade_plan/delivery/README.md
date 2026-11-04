MC2 INSTALL GUIDE (STAGE A, up to mc2-v2.5.1). This is the only install text you need. Earlier reports in upgrade_plan/tmp/ (STEP0_REPORT.md and the others) are history; do not follow them.

What you get: a new folder ROOT = "/Users/mac/Desktop/mc2_root" that holds the new master chat system (mc2). It is a git clone of the file mc2.bundle in this folder, so it carries every version as a git tag: mc2-v2.0 (the old system files plus the upgrade tools) up to mc2-v2.5.1 (the newest). You install mc2-v2.0 first, copy your data in once, then move up one tag at a time with checks before and after each step. The old system in "/Users/mac/Desktop/Terminal Bench" keeps running and is only read, never written.

How to read this guide: every line indented by four spaces is one command to paste into Terminal. Lines that are not indented are explanations. Run the steps in order. Every path is in double quotes because "Terminal Bench" has a space.

1. Open Terminal (zsh) and set the names this guide uses. Do this again in every new Terminal window.
    setopt interactivecomments
    OLD="/Users/mac/Desktop/Terminal Bench"
    ROOT="/Users/mac/Desktop/mc2_root"
    PLAN="/Users/mac/Desktop/mc2_upgrade"
    BUNDLE="$PLAN/upgrade_plan/delivery/mc2.bundle"
    UP="$ROOT/master_chat_work/_upgrade/upgrade.py"
    python3 --version
   The first line makes zsh treat a line that starts with # as a comment, so the comment lines the upgrade tool prints above its commands can be pasted with them. (In bash it prints "command not found"; that is harmless.) python3 should be the Homebrew one, 3.11 or newer. A Python 3.9 from Xcode runs the upgrade, but tools/stacking_check.py then stops and says it needs 3.11.

2. The planning clone and the bundle. PLAN is the planning clone made by upgrade_plan/opencode_handoff/SETUP_STEPS.md step 1 (a separate folder, never the Terminal Bench folder). Bring it up to date and check the bundle:
    git -C "$PLAN" pull
    git -C "$PLAN" bundle verify "$BUNDLE"
   Expected: "The bundle records a complete history" and "okay". The list shows mc2-v2, mc2-stable and the tags mc2-v2.0 to mc2-v2.5.1.

3. Create ROOT from the bundle (it must not exist yet; if it does, stop and ask the master, never delete it):
    git clone -b mc2-stable "$BUNDLE" "$ROOT"
    git -C "$ROOT" tag -l "mc2-v*"
    cat "$ROOT/SYSTEM_VERSION"
   Expected: the six tags and "version = v2.0". ROOT's git remote "origin" is the bundle file, not GitHub; later fetches read the newest mc2.bundle from that same path.

4. Two local helpers, made once. The first line tells git to ignore your local settings file at every version (so "git status --porcelain" stays empty). The last two lines take the newest upgrade tool out of the bundle into ROOT/master_chat_work/_upgrade/ (DATA, ignored by git). You run that copy for every step, because the tool inside older versions prints comments after commands, which a plain zsh misreads, and has known bugs fixed in mc2-v2.5.1.
    printf '%s\n' "master_chat_tasks/settings.local.json" >> "$ROOT/.git/info/exclude"
    mkdir -p "$ROOT/master_chat_work/_upgrade"
    NEWEST="$(git -C "$ROOT" tag -l "mc2-v*" --sort=-v:refname | head -n 1)"
    git -C "$ROOT" show "$NEWEST:master_chat_tasks/tools/upgrade.py" > "$UP"
   Expected: echo "$NEWEST" prints mc2-v2.5.1. Running the printf line twice only adds a duplicate line, which is harmless.

5. The harness clone in ROOT. The QC kit (Terminal_2.0_Harbor_Harness/Input_Bundle_QC) and the harness scripts belong in ROOT. Make a read only clone of the PL repo from your old folder's clone (git only reads the old folder), then point it at the same remote the old clone uses:
    git clone --no-hardlinks "$OLD/Terminal_2.0_Harbor_Harness" "$ROOT/Terminal_2.0_Harbor_Harness"
    git -C "$ROOT/Terminal_2.0_Harbor_Harness" remote set-url origin "$(git -C "$OLD/Terminal_2.0_Harbor_Harness" remote get-url origin)"
    git -C "$ROOT/Terminal_2.0_Harbor_Harness" rev-parse --short=8 HEAD
   Expected: the same commit as the old folder (git -C "$OLD/Terminal_2.0_Harbor_Harness" rev-parse --short=8 HEAD). This brings the tracked harness files and the kit. It does not bring the old jobs/, Tasks_INPUT/ and Output_RFP/ folders: old tasks finish in the old folder. Never pull, commit or push in this clone yourself; it is read only like the old one.
   If you skip this step: from mc2-v2.5.1 on, precheck.sh, kit_watch.py, the state card and issue.py use the old folder's kit and harness (read only) and print a one line NOTE saying so. Before mc2-v2.5.1 they do not (see step 11 for what fails then).

6. Copy the DATA once from the old folder (the old folder is only read). Run this while no old session is writing, or accept that a record written during the copy shows up later through carry_over.py. Every command copies into the parent folder, so a second run overwrites in place and never nests a folder; but a second run later would also replace ROOT's newer records with the old ones, so run it only now.
    MO="$OLD/master_chat_tasks"
    MN="$ROOT/master_chat_tasks"
    cp -Rp "$MO/registry" "$MN/"
    for f in board.json BOARD.md state.json GOALS.md open_questions.json; do cp -p "$MO/$f" "$MN/"; done
    cp -p "$MO"/*.jsonl "$MN/"
    sqlite3 "$MO/pending.db" ".backup '$MN/pending.db'"
    mkdir -p "$MN/prompts" "$MN/auto" "$MN/knowledge"
    cp -Rp "$MO/prompts/issued" "$MN/prompts/"
    cp -Rp "$MO/auto/runs" "$MO/auto/plans" "$MN/auto/"
    cp -Rp "$MO/knowledge/fingerprints" "$MO/knowledge/archive_md" "$MN/knowledge/"
    git -C "$ROOT" status --porcelain
   sqlite3 .backup makes a consistent copy of pending.db even while the old system has it open. A "No such file or directory" for a folder the old system never made (for example auto/plans) is harmless. The last line must print nothing: every DATA file is ignored by git.

7. Where bundles, QC reports and work folders live after the switch.
   1. The old folder keeps everything that belongs to tasks started there: "$OLD/master_chat_work" (2.2 GB, not copied), "$OLD/QC/reports", "$OLD/QC/copies", and the harness jobs/, Tasks_INPUT/ and Output_RFP/ in "$OLD/Terminal_2.0_Harbor_Harness". The board and registry rows you copied keep those old paths, and that is correct.
   2. Everything issued from ROOT writes under ROOT: "$ROOT/master_chat_work/<YYYYMMDD>_<topic>/", "$ROOT/master_chat_work/bundles/<slug>/", "$ROOT/QC/reports/<slug>/", "$ROOT/QC/copies/", "$ROOT/_runs/". These folders are DATA (ignored by git) and are made on first use.
   3. A task that started in the old system and goes on in ROOT (for example a recheck QC): the master fills [[ORIGINAL]], [[PREV_REPORT]] and [[PREV_COPY]] with the old paths. Those are read only inputs; template_check only checks templates, and issue.py accepts old paths in the filled fields. The new report goes to "$ROOT/QC/reports/<slug>/". Before the first build or fix step of such a task from ROOT, copy its bundle (replace SLUG by the task slug):
    mkdir -p "$ROOT/master_chat_work/bundles"
    cp -Rp "$OLD/master_chat_work/bundles/SLUG" "$ROOT/master_chat_work/bundles/"
   4. The current templates read a few reference files under [[ROOT]]/master_chat_work. Copy them once (about 10 MB):
    mkdir -p "$ROOT/master_chat_work/20261020_analysis/reports" "$ROOT/master_chat_work/_dev_research" "$ROOT/master_chat_work/gen_memory"
    cp -Rp "$OLD/master_chat_work/20261024_process" "$ROOT/master_chat_work/"
    cp -Rp "$OLD/master_chat_work/20261020_analysis/reports/qc" "$ROOT/master_chat_work/20261020_analysis/reports/"
    cp -Rp "$OLD/master_chat_work/_dev_research/delivery_study2" "$OLD/master_chat_work/_dev_research/peer_levers" "$ROOT/master_chat_work/_dev_research/"
    cp -p "$OLD/master_chat_work/gen_memory/ideas.jsonl" "$ROOT/master_chat_work/gen_memory/"
   5. A read only shortcut to the old QC reports (safe to run again; it never writes into the old folder):
    mkdir -p "$ROOT/QC"
    ln -sfn "$OLD/QC/reports" "$ROOT/QC/old_reports"

8. First checks and the first backup, still at mc2-v2.0. The backup goes to "/Users/mac/Desktop/mc2_backup/<YYYYMMDDTHHMMSS>/", one new folder per run, never overwritten.
    cd "$ROOT"
    python3 "$UP" status
    python3 "$ROOT/master_chat_tasks/tools/registry_check.py"
    python3 "$UP" backup
    python3 "$UP" preflight --old "$OLD"
   At mc2-v2.0 there is no settings.json yet, so preflight needs --old to tell sessions that run in the old system apart from sessions of ROOT (a copied live row is then a WARN "old system session, finishes there", not a FAIL). From mc2-v2.1 on, settings.json holds upgrade.old_root = "/Users/mac/Desktop/Terminal Bench", and a plain "python3 "$UP" preflight" does the same; giving --old "$OLD" anyway is always fine.
   Expected: VERDICT: READY and a block of commands for mc2-v2.1. Do not paste them yet if you want to do step 9 first; preflight can be run again any time.

9. Optional, for the dry precheck in every recheck: name one QC passed bundle in your local settings file (git ignored, so git status stays empty). Replace SLUG by a task that passed QC:
    KB="$OLD/Terminal_2.0_Harbor_Harness/Tasks_INPUT/SLUG"
    printf '{\n  "upgrade": {\n    "known_bundle": "%s"\n  }\n}\n' "$KB" > "$ROOT/master_chat_tasks/settings.local.json"
    git -C "$ROOT" status --porcelain
   The last line must print nothing. Every mc2-v2.5.1 tool merges settings.local.json over settings.json; older versions do not read it, so until mc2-v2.5.1 the recheck shows the dry precheck as WAIT, which is fine. Never put known_bundle into settings.json itself.

10. The upgrade loop, one tag at a time. Repeat 10.1 to 10.4 until preflight says UP TO DATE.
   10.1 Backup and preflight:
    cd "$ROOT"
    python3 "$UP" backup
    python3 "$UP" preflight --old "$OLD"
   10.2 If it ends "VERDICT: READY", paste the indented block it printed, as it is (the comment lines start with # and stand on their own line above their command). The block checks that "git status --porcelain" prints nothing, fetches the tags from origin (the bundle), sets a local marker tag before-<tag>-<YYYYMMDDTHHMMSS>, checks out the next tag and runs the recheck. If it ends BLOCKED, fix the FAIL rows it names (for example a live ROOT session: let it finish or mark its row done, then backup again) and run 10.1 again. If it ends UP TO DATE, ROOT runs the newest tag: go to step 12.
   10.3 Read how the recheck ends:
   1. "VERDICT: WAITING" (exit 3): normal. Only manual items are left (the cold recovery test, and the dry precheck until step 9 is done). Go on with 10.1 for the next tag.
   2. "VERDICT: RECHECK FAILED": paste the rollback block it printed, stop, and tell the master which row failed.
   3. "VERDICT: UPGRADE GOOD": you may mark this version stable by pasting the two lines it prints (git branch -f mc2-stable <tag>).
   10.4 After mc2-v2.3 (from that tag on, issue.py fills templates from settings), look at one filled prompt without issuing it. Neither command writes a board row, a pending item or a record, so the next preflight is not blocked:
    python3 "$ROOT/master_chat_tasks/tools/issue.py" --render "$ROOT/master_chat_tasks/prompts/templates/P11_full_qc_v3.md" > "$ROOT/master_chat_work/_upgrade/P11_rendered.md"
    python3 "$ROOT/master_chat_tasks/tools/issue.py" cold-chain-backbone-quote qc "$PLAN/upgrade_plan/delivery/s3_sample_draft_P11.md" "[[ROOT]]/QC/reports/cold-chain-backbone-quote" --dry-run
   Open "$ROOT/master_chat_work/_upgrade/P11_rendered.md" in any editor: the numbers come from settings and every path starts with ROOT; the [[NAME]] fields left in it are the ones the master fills. The dry run prints "DRY RUN ok" with cap warnings only. delivery/s3_sample_issued_P11.md shows how a really issued prompt looks. If you do issue a real prompt, its board row is live and the next preflight is BLOCKED until that session finishes or you end the row, for example: python3 "$ROOT/master_chat_tasks/tools/board.py" set SHA status=done (SHA from the issue output); then run the backup again before preflight.

11. What is expected to fail or wait when the harness is not in ROOT (step 5 skipped), and why it does not block the loop:
   1. At mc2-v2.3 to mc2-v2.5, precheck.sh runs the four kit scripts against a missing folder (every script exit 2) and kit_watch.py stops with "kit folder not found"; issued prompts name [[ROOT]]/Terminal_2.0_Harbor_Harness. Do not issue real build or QC prompts from ROOT before mc2-v2.5.1 or before step 5.
   2. From mc2-v2.5.1: precheck.sh, kit_watch.py, the state card and issue.py use the old folder's kit and print a NOTE; precheck.sh stops with "PRECHECK: STOP. QC kit folder not found" only when neither folder has a kit.
   3. Self tests: preflight runs only the tests that need no harness. From mc2-v2.5.1, test_e3_e6_tools.py and test_upgrade_tools.py (intake and repackage parts) say "skipped: needs the harness clone in ROOT" instead of failing; before mc2-v2.5.1 they fail when run by hand.
   4. Recheck from mc2-v2.2 on: "cold recovery test" is WAIT until you run it (step 12); "dry precheck on a known bundle" is WAIT until step 9.
   5. Preflight at mc2-v2.5 and later: "kit_watch status" is WAIT when no kit is found in ROOT or the old folder, and then no command is printed; place the harness (step 5) or give --kit.

12. At mc2-v2.5.1 (the newest tag in this bundle):
   1. Cold recovery test: the recheck output shows the prompt in full (the same text is in master_chat_tasks/README.md, section "Compact and restore prompts", part B). Paste it into a fresh master session and compare the reply with the PASS line, then:
    python3 "$UP" recheck --from mc2-v2.5 --to mc2-v2.5.1 --cold-result pass
   With the cold test passed and a known bundle that precheck finds clean, it ends UPGRADE GOOD and prints the git branch -f mc2-stable mc2-v2.5.1 line to paste.
   2. The new kit snapshot is saved only on your word (the master runs kit_watch.py save --by "<your exact words>").
   3. A later bundle: the master puts a newer mc2.bundle into this folder. Then:
    git -C "$PLAN" pull
    git -C "$ROOT" fetch origin --tags
    NEWEST="$(git -C "$ROOT" tag -l "mc2-v*" --sort=-v:refname | head -n 1)"
    git -C "$ROOT" show "$NEWEST:master_chat_tasks/tools/upgrade.py" > "$UP"
   and run the loop of step 10 again.

13. Rollback, any time after a step (the tool only prints; you paste). Example from mc2-v2.5.1 back to mc2-v2.5:
    python3 "$UP" rollback --from mc2-v2.5.1 --to mc2-v2.5
   It prints: git checkout of the older tag, a recheck (which then says "ROLLBACK DONE"; it prints a git branch -f mc2-stable line only when mc2-stable still points at the version you left), and, only if the failed version changed DATA, an rsync line that restores the records from the backup taken while the older version ran (look with --dry-run first). Every backup run has its own folder, so a rollback over two steps finds the records from before the first.

14. Optional: keep the versions on GitHub too. Push only named refs; the local before-* marker tags are never pushed this way. If GitHub refuses the mc2 branches, keep them local; the bundle and ROOT hold everything.
    git -C "$ROOT" remote add github https://github.com/Ayush-dvplr/master-task-chat.git
    git -C "$ROOT" push github "refs/remotes/origin/mc2-v2:refs/heads/mc2-v2" "mc2-stable" "refs/tags/mc2-v2.*:refs/tags/mc2-v2.*"

Notes
1. Tags: every mc2 tag from mc2-v2.1 on is a lightweight tag, and so is every later tag. mc2-v2.0 alone is annotated, so git rev-parse mc2-v2.0 prints the tag object 719a09c8 and git rev-parse "mc2-v2.0^{commit}" prints the commit 8d1c963e. A fix release has three numbers (mc2-v2.5.1).
2. Status on 4 Nov 2026: tags mc2-v2.0 to mc2-v2.5.1 on branch mc2-v2; mc2-stable points at mc2-v2.0 until you mark a newer tag stable (step 10.3 or 12).
3. Files in this folder: README.md (this guide), mc2.bundle, s3_sample_issued_P11.md (an issued prompt), s3_sample_draft_P11.md (the master's draft used in step 10.4).
