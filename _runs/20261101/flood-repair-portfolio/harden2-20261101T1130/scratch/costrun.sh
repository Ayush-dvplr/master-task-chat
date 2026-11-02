#!/bin/bash
R="/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden2-20261101T1130"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio"
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/flood-repair-portfolio"
prog() {
  case "$1" in
    oracle) echo "$B/solution/solve.py";;
    a1) echo "$W/h1_a1/a1_program/derive_report.py";;
    fw) echo "$W/h2_a1/firstwrite_program.py";;
    abo) echo "$W/h2_a1/allbutone_program.py";;
    dae) echo "$W/h1_a1/dae9563_program.py";;
    elim) echo "$W/h1_a1/elim_program.py";;
    vebest) echo "$W/h1_a1/vebest_program.py";;
  esac
}
for p in $PROGS; do
  D="$R/scratch/ct_$p"; rm -rf "$D"; mkdir -p "$D/tests" "$D/app/out" "$D/logs"
  cp "$B/tests/test_output.py" "$B/tests/test.sh" "$D/tests/"; cp "$R/scratch/vt_a1/tests/reward.toml" "$D/tests/"
  cp -R "$B/environment/data" "$D/app/data"; cp "$(prog $p)" "$D/app/out/derive_report.py"
  L="$R/logs/ct_$p.log"
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py" --need-mb 4096 --cpus 2 > "$L" 2>&1
  perl -e 'alarm 2700; exec @ARGV' docker run --rm --name cb8dada_ct_$p --memory 4g --cpus 2 -v "$D/tests:/tests" -v "$D/app:/app" -v "$D/logs:/logs" -v "$R/scratch/vrun2.sh:/vrun.sh:ro" cb8dada_verif bash /vrun.sh >> "$L" 2>&1
  echo "container_rc $?" >> "$L"
done
echo COST_ALL_DONE >> "$R/logs/costrun.done"
