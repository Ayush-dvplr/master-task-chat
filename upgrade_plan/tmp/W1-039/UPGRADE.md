UPGRADE PROCEDURE (P14, Q141, Q142, Q145). DRAFT W1-039, 4 Nov 2026. Nothing is applied before PROCEED.

Tool: upgrade.py (standard library only). After PROCEED it lives at ROOT/master_chat_tasks/tools/upgrade.py. ROOT is the new root folder (Q84, S6). Dry run of this draft: UPGRADE_DRY_RUN.txt.

WHAT THE TOOL DOES AND DOES NOT DO
1. It runs every check and every recheck itself, with no AI tokens.
2. It never runs git. It prints the exact git commands; Ayush pastes them (R34 strict, Q145).
3. It never stops a session, a container or a background script, and never touches the old system.
4. It writes only the backup folder and its work folder (ROOT/master_chat_work/_upgrade by default).

SYSTEM AND DATA (Q141)
1. SYSTEM files, versioned in git: master_chat_tasks/tools, auto/auto.py, auto/AUTO_POLICY.md, prompts/templates (with CURRENT.json and CHANGELOG.md), RULES_IN_FORCE.md, BUILD_RULES.md, settings.json, README.md, knowledge files that hold how to text (PATTERNS.md, FIX_MAP.md, QC_FIX_PLAYBOOK.md and the like), the root opencode config and the .opencode/dcp.jsonc files, SYSTEM_VERSION, .gitignore.
2. DATA, never in git (listed in .gitignore and in upgrade.py DATA_RECORDS and DATA_WORK): board.json, BOARD.md, pending.db, log.jsonl, decisions.jsonl, feedback.jsonl, lessons.jsonl, open_questions.json, state.json, GOALS.md, STATE_CARD.md and its prev file, registry/, knowledge/fingerprints/, knowledge/intake/, auto/runs/, auto/LATEST, auto/SCHEDULED.*, and all of master_chat_work/ (outputs, bundles, QC reports, logs).
3. Daily backup: upgrade.py backup copies every record file into BACKUP/YYYYMMDD/records/ with a MANIFEST.json of sha256 values, and keeps one mirror of master_chat_work (only new or changed files are copied, so the 2.2 GB folder is cheap after the first day). BACKUP defaults to ROOT/master_chat_work/_upgrade/backup; a folder outside ROOT is better (Ayush to choose; settings key upgrade.backup_dir after PROCEED).

VERSIONS
1. Branch stable: the version Ayush runs. Branch v2: where new versions are prepared. Tags v2.0, v2.1 and so on, one per release.
2. A version is a tag. Upgrading means checking out a newer tag; going back means checking out an older tag or stable. Ignored DATA files stay in place across a checkout.
3. ROOT/SYSTEM_VERSION holds "system_id = mc2" and "version = v2.x"; the release that changes it carries the new tag.

THE PROCEDURE (each upgrade)
1. Backup: python3 master_chat_tasks/tools/upgrade.py backup
2. Preflight: python3 master_chat_tasks/tools/upgrade.py preflight --to v2.1
   Checks, each PASS, WARN or FAIL:
   a. settings.json valid: gate numbers, design margin under the final gate, soft cap at most hard cap, card sizes, Docker manager and kinds, runners and steps, blinds on oc-opus-5, system.id present.
   b. RULES_IN_FORCE.md and BUILD_RULES.md present.
   c. template_check.py clean: every current template matches CURRENT.json, holds no retired rule and no typed setting.
   d. kit_watch.py status: the live kit against the snapshot. CHANGED is a warning: classify it (S7, Q86); a MAJOR change blocks.
   e. the state card builds (in a copy), within the hard size, rules wrapped in protect tags.
   f. tool self tests: every Python file compiles; state_card, template_check, kit_watch and dockslot answer --help; dockslot status on fake capacity.
   g. no session of this system running: no board row running or issued, no live auto run, no dockslot lease.
   h. today's backup exists and every record file still matches it.
   Any FAIL: BLOCKED, no git command printed. All PASS or WARN: READY, and the commands are printed.
3. Ayush pastes the printed commands, which are:
   cd "<ROOT>"
   git status --porcelain              (must print nothing)
   git fetch origin --tags             (only when the version comes from GitHub)
   git tag before-v2.1-<YYYYMMDDTHHMM> (local mark of the version he runs now)
   git checkout v2.1
   python3 master_chat_tasks/tools/upgrade.py recheck --from v2.0 --to v2.1
4. Recheck (after the switch): settings valid, state card builds, template_check clean, cold recovery test, one dry precheck on a known bundle (settings upgrade.known_bundle: a QC passed bundle whose precheck.sh was CLEAN), dockslot status.
   The cold recovery test needs Ayush: the tool prints the recovery prompt (drafts/P1/MASTER_RECOVERY.md part B) and the pass list; Ayush pastes it into a fresh master session and reruns recheck with --cold-result pass or fail.
5. Recheck FAIL: the tool prints the rollback commands (git checkout of the old tag, a recheck of the old version, and an rsync of the records from today's backup, first with --dry-run, used only when the failed version changed DATA).
6. Recheck PASS: the tool prints "git branch -f stable v2.1" for Ayush to mark the version stable.
7. Going back at any time: upgrade.py rollback --from v2.1 --to v2.0 prints the same rollback commands.

FIRST INSTALL (once, after PROCEED; details in PLAN_FINAL.md part F)
1. A new ROOT folder (name to confirm with Ayush), separate from the old "Terminal Bench" folder.
2. SYSTEM files go in from the delivered v2.0 version; DATA is copied once from the old system (the old one is never moved or renamed).
3. Ayush runs backup, then preflight; the first recheck runs after the copy.

OPEN POINTS
1. Where branch v2 and the tags live: only in the local git of ROOT, or also pushed to GitHub by Ayush (R_REPOS lets this planning session push only upgrade_plan/ to its own branch).
2. The ROOT name and the backup folder outside ROOT.
3. precheck.sh reads the kit at a fixed Mac path (precheck.sh line 9): after PROCEED it reads the kit path from settings.json, so the recheck also works in ROOT.
4. A check for a migrated DATA field (for example registry "design") is added per release in its release note, not in the tool.
