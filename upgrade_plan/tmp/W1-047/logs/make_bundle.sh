#!/bin/bash
# make_bundle.sh MODE: build mc2.bundle from W into the simulated planning repo and push it.
# MODE provisional: clone W to src, add a lightweight tag mc2-v2.5.1 there (W untouched). MODE final: bundle straight from W.
set -eu
S=/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad; E2="$S/e2e2"; W="$S/mc2"
MODE=${1:-provisional}
if [ "$MODE" = provisional ]; then
  rm -rf "$E2/src"; git clone -q "$W" "$E2/src"
  git -C "$E2/src" branch -q mc2-stable origin/mc2-stable 2>/dev/null || true
  git -C "$E2/src" branch -q -f mc2-v2 origin/mc2-v2 2>/dev/null || true
  git -C "$E2/src" tag -f mc2-v2.5.1 mc2-v2 >/dev/null
  REPO="$E2/src"
else
  REPO="$W"
fi
TAGS=$(git -C "$REPO" tag -l "mc2-v2.*")
rm -f "$E2/mc2.bundle"
git -C "$REPO" bundle create "$E2/mc2.bundle" mc2-v2 mc2-stable $TAGS
git bundle verify "$E2/mc2.bundle" >/dev/null && echo "bundle ok: $(git bundle list-heads "$E2/mc2.bundle" | wc -l) refs"
# simulated planning repo (GitHub stand in) with upgrade_plan/delivery
if [ ! -d "$E2/plan_origin.git" ]; then git init -q --bare "$E2/plan_origin.git"; fi
rm -rf "$E2/plan_work"; git clone -q "$E2/plan_origin.git" "$E2/plan_work" 2>/dev/null
mkdir -p "$E2/plan_work/upgrade_plan/delivery" "$E2/plan_work/upgrade_plan/opencode_handoff"
cp /home/user/master-task-chat/upgrade_plan/delivery/README.md /home/user/master-task-chat/upgrade_plan/delivery/s3_sample_*.md "$E2/plan_work/upgrade_plan/delivery/"
cp -R /home/user/master-task-chat/upgrade_plan/opencode_handoff/. "$E2/plan_work/upgrade_plan/opencode_handoff/"
cp "$E2/mc2.bundle" "$E2/plan_work/upgrade_plan/delivery/mc2.bundle"
cd "$E2/plan_work"; git add -A; git -c user.name=sim -c user.email=sim@example.invalid commit -qm "delivery $MODE $(date +%H%M%S)" || true
git branch -M claude/youthful-feynman-zug0uq; git push -q origin HEAD:claude/youthful-feynman-zug0uq 2>&1 | tail -1
git -C "$E2/plan_origin.git" symbolic-ref HEAD refs/heads/claude/youthful-feynman-zug0uq
