#!/bin/bash
# run_selftests.sh: in the installed ROOT at mc2-v2.5.1: py_compile, template_check, every self test with the
# simulated harness in ROOT (kit + scripts/master_queue.py) and without it (folder moved aside), kit fallback
# checks, KIT_CLASSIFY step 1 literally, one real issue (problems 18, 19), ended again with board.py.
S=/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad; E2="$S/e2e2"
ROOT="$E2/Desktop/mc2_root"; OLD="$E2/Desktop/Terminal Bench"; MT="$ROOT/master_chat_tasks"; H="$ROOT/Terminal_2.0_Harbor_Harness"
export PATH="$E2/bin:$PATH"
cd "$MT"
echo "== version: $(sed -n 's/^version = //p' "$ROOT/SYSTEM_VERSION")"
echo "== py_compile (python3 $(python3 -V 2>&1), then python3.11)"
for py in python3 python3.11; do n=0; bad=0; for f in $(git -C "$ROOT" ls-files '*.py'); do n=$((n+1)); $py -c "import sys; compile(open(sys.argv[1]).read(), sys.argv[1], 'exec')" "$ROOT/$f" || bad=$((bad+1)); done; echo "$py: $n files, $bad failures"; done
echo "== template_check"; python3 -B tools/template_check.py | grep ^TOTAL; echo "[exit ${PIPESTATUS[0]}]"
alltests() {
  for t in tools/tests/test_*.py auto/tests/test_auto.py; do printf '%-40s ' "$t"; (cd "$(dirname "$t")" && python3 -B "$(basename "$t")" 2>&1 | tail -1); done
}
echo "== A. self tests WITH the simulated harness in ROOT (kit clone + scripts/master_queue.py)"
mkdir -p "$H/scripts"; cp "$E2/master_queue.py" "$H/scripts/master_queue.py"
alltests
python3 -B tools/tests/test_e3_e6_tools.py -v 2>&1 | grep -E "skipped|ok$" | cut -c1-200
echo "== B. self tests WITHOUT the harness in ROOT (moved aside)"
mv "$H" "$ROOT/_harness_aside"
alltests
python3 -B tools/tests/test_upgrade_tools.py -v 2>&1 | grep -m3 skipped | cut -c1-220
echo "== kit fallback without the harness in ROOT"
python3 tools/mc2_settings.py kit; echo "[exit $?]"
bash tools/precheck.sh --print-kit; echo "[exit $?]"
python3 -B tools/kit_watch.py card; echo "[exit $?]"
python3 -B tools/state_card.py --out "$ROOT/master_chat_work/_upgrade/card_nokit.md" >/dev/null; grep "^QC KIT" "$ROOT/master_chat_work/_upgrade/card_nokit.md"
python3 -B tools/issue.py --render prompts/templates/P11_full_qc_v3.md 2>&1 >/dev/null | head -2
python3 -B tools/issue.py --render prompts/templates/P11_full_qc_v3.md 2>/dev/null | grep -m1 "QC kit (live"
bash tools/precheck.sh "$OLD/Terminal_2.0_Harbor_Harness/Tasks_INPUT/cold-chain-backbone-quote" 2>&1 | tail -1
echo "== no kit anywhere (old_root emptied in settings.local.json for one run)"
cp settings.local.json "$E2/local.bak"; python3 -c "import json;p='settings.local.json';d=json.load(open(p));d['upgrade']['old_root']='';json.dump(d,open(p,'w'))"
bash tools/precheck.sh "$OLD/Terminal_2.0_Harbor_Harness/Tasks_INPUT/cold-chain-backbone-quote"; echo "[exit $?]"
cp "$E2/local.bak" settings.local.json
mv "$ROOT/_harness_aside" "$H"; rm -f "$H/scripts/master_queue.py"; rmdir "$H/scripts" 2>/dev/null
echo "== KIT_CLASSIFY step 1, literally from master_chat_tasks/ ([[DATE]] filled)"
D=$(TZ=Asia/Kolkata date +%Y%m%d)
cmd=$(grep -o '`mkdir -p ../master_chat_work/\[\[DATE\]\]_kit && [^`]*`' knowledge/KIT_CLASSIFY_PROMPT.md | tr -d '`' | sed "s/\[\[DATE\]\]/$D/g")
echo "\$ $cmd"; eval "$cmd"; echo "[exit $?]"; head -3 "../master_chat_work/${D}_kit/kit_watch.txt"
echo "== one real issue from the sample draft (mapped old path), then the row is ended"
sed "s|/Users/mac/Desktop|$E2/Desktop|g" "$E2/Desktop/mc2_upgrade/upgrade_plan/delivery/s3_sample_draft_P11.md" > "$E2/draft_mapped.md"
out=$(python3 -B tools/issue.py cold-chain-backbone-quote qc "$E2/draft_mapped.md" "[[ROOT]]/QC/reports/cold-chain-backbone-quote" 2>&1); echo "$out" | tail -3
sha=$(echo "$out" | sed -n 's/^Board `\([0-9a-f]*\)`.*/\1/p')
echo "rendered folder for $sha: $(ls prompts/rendered/$sha 2>/dev/null | tr '\n' ' ')(empty = no copy of the Template: line file)"
pf=$(python3 -c "import json,sys;print(next(r['prompt'] for r in json.load(open('board.json'))['rows'] if r['sha']=='$sha'))")
echo "YYYYMMDD sentence in the issued prompt: $(grep -c "is today's IST date" "$ROOT/$pf")"; echo "left [[...]]: $(grep -c '\[\[[A-Z_]*\]\]' "$ROOT/$pf")"
python3 -B tools/board.py set "$sha" status=done >/dev/null; echo "row $sha ended: [exit $?]"
echo "== git status in ROOT"; git -C "$ROOT" status --porcelain; echo "[end]"
