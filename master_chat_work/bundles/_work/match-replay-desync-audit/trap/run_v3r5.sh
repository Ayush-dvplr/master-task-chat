#!/bin/zsh
# usage: run_v3r5.sh <tests_dir> <scores_dir>
cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/match-replay-desync-audit"
export PYTHONDONTWRITEBYTECODE=1
D=../../match-replay-desync-audit/environment/data
for v in mut_zero mut_carry mut_stepped mut_index var_perentry var_norenew var_opening var_cancelled_draw var_carry_eleven var_precedence var_renew_strict var_tiebreak var_lifo var_ctrl_all_old; do
  python3 -B local_score.py "$1" $D trap/variants_v3r5/$v.py "$2/$v.txt" >/dev/null
  echo "$v $(tail -1 $2/$v.txt)"
done
python3 -B local_score.py "$1" $D ../../match-replay-desync-audit/solution/solve.py "$2/oracle.txt" >/dev/null; echo "oracle $(tail -1 $2/oracle.txt)"
echo ALL_DONE
