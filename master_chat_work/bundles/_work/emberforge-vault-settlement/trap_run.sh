#!/bin/bash
# usage: trap_run.sh <bundle_root_with_tests> <outdir>
export PYTHONDONTWRITEBYTECODE=1
BR="$1"; OD="$2"
run() { python3 -B "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/score_local.py" "$BR" "$2" "$1" > "$OD/$1.json" 2> "$OD/$1.err"; echo "$1 done $(date +%T)"; }
run oracle "$BR/solution/solve.py" &
run a7 "/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_emberforge-vault-settlement/traj_a7/job/trajectory/claude-opus-5/Run 1/artifacts/app/out/settle_vault.py" &
run L3_rebased "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/L3_rebased.py" &
run L6_rebased "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/L6_rebased.py" &
wait
run L7_rebased "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/L7_rebased.py" &
run no_reinstate "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/no_reinstate.py" &
run no_apprentice_relief "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/no_apprentice_relief.py" &
run salvage_day_window "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/salvage_day_window.py" &
wait
run neg_network "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/neg_network.py" &
run neg_third_party "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/neg_third_party.py" &
run al27_stock_floor_last "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/al27_stock_floor_last.py" &
run al27_a2_edges "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/al27_a2_edges.py" &
wait
run al27_q1_all "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/al27_q1_all.py" &
run al27_v2_strict "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/al27_v2_strict.py" &
run mi_generic "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/mi_generic.py" &
run mi_traceback "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/emberforge-vault-settlement/wrong/mi_traceback.py" &
wait
echo ALL_DONE
