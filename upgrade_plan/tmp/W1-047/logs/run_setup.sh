#!/bin/bash
# run_setup.sh: SETUP_STEPS.md steps 1, 2 (twice) and 5 (first run with an OLDER bundle, then the update lines
# with the newer final bundle), literally, GitHub URL mapped to the simulated planning repo.
S=/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad; E2="$S/e2e2"; W="$S/mc2"
G=/home/user/master-task-chat/upgrade_plan/opencode_handoff/SETUP_STEPS.md
cmds() { python3 "$E2/guide_cmds.py" "$G" "$1" | sed "s|$E2/github.git|$E2/plan_origin.git|"; }
run() { while IFS= read -r c; do [ -z "$c" ] && continue; echo "\$ $c"; eval "$c"; echo "    [exit $?]"; done; }
echo "== older bundle (mc2-v2 at 6d746b28, tags mc2-v2.0 to mc2-v2.5) into the planning repo"
rm -rf "$E2/src_old"; git clone -q "$W" "$E2/src_old"; git -C "$E2/src_old" checkout -q --detach; git -C "$E2/src_old" branch -q -f mc2-v2 6d746b28; git -C "$E2/src_old" branch -q mc2-stable origin/mc2-stable
git -C "$E2/src_old" tag -d mc2-v2.5.1 >/dev/null
rm -f "$E2/mc2.bundle"; git -C "$E2/src_old" bundle create "$E2/mc2.bundle" mc2-v2 mc2-stable mc2-v2.0 mc2-v2.1 mc2-v2.2 mc2-v2.3 mc2-v2.4 mc2-v2.5 2>/dev/null
rm -rf "$E2/plan_origin.git" "$E2/plan_work"; git init -q --bare "$E2/plan_origin.git"; git clone -q "$E2/plan_origin.git" "$E2/plan_work" 2>/dev/null
mkdir -p "$E2/plan_work/upgrade_plan/delivery"; cp -R /home/user/master-task-chat/upgrade_plan/opencode_handoff "$E2/plan_work/upgrade_plan/"; cp "$E2/mc2.bundle" "$E2/plan_work/upgrade_plan/delivery/"
(cd "$E2/plan_work" && git add -A && git -c user.name=sim -c user.email=sim@example.invalid commit -qm old && git branch -M claude/youthful-feynman-zug0uq && git push -q origin HEAD:claude/youthful-feynman-zug0uq 2>/dev/null; git -C "$E2/plan_origin.git" symbolic-ref HEAD refs/heads/claude/youthful-feynman-zug0uq)
rm -rf "$E2/Desktop/mc2_upgrade" "$E2/Desktop/mc2_worktree"
echo "######## SETUP 1"; run < <(cmds 1)
echo "######## SETUP 2 (first run)"; run < <(cmds 2)
echo "######## SETUP 2 (second run: must not nest .opencode)"; run < <(cmds 2)
echo "nested? $(ls -a "$PLAN/.opencode")"
echo "######## SETUP 5 (first run)"; run < <(cmds 5 | head -3)
echo "worktree at: $(git -C "$E2/Desktop/mc2_worktree" log --oneline -1)"
echo "######## SETUP 5 rerun of the first three lines (expected: the add line refuses, as the text says)"; run < <(cmds 5 | head -3)
echo "== newer bundle (final, from W) is published; git pull in PLAN"
"$E2/make_bundle.sh" final >/dev/null 2>&1
git -C "$PLAN" pull -q; echo "    [pull exit $?]"
echo "######## SETUP 5 update lines"; cd "$PLAN"; run < <(cmds 5 | tail -2)
echo "worktree at: $(git -C "$E2/Desktop/mc2_worktree" log --oneline -1); git status: $(git -C "$E2/Desktop/mc2_worktree" status --porcelain | wc -l) lines"
echo "######## SETUP 5 update lines again (rerun safe)"; cd "$PLAN"; run < <(cmds 5 | tail -2)
