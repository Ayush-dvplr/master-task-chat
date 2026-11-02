#!/bin/zsh
cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/match-replay-desync-audit"
export PYTHONDONTWRITEBYTECODE=1
for v in mut_zero mut_carry mut_stepped mut_index var_perentry var_norenew var_opening var_cancelled_draw var_carry_eleven var_precedence var_renew_strict var_tiebreak var_lifo var_ctrl_all_old; do
  python3 -B local_score.py ../../match-replay-desync-audit/tests ../../match-replay-desync-audit/environment/data trap/variants_v3r3_after/$v.py trap/scores_after_v3r3/$v.txt
  echo "$v $(tail -1 trap/scores_after_v3r3/$v.txt)"
done
python3 -B local_score.py ../../match-replay-desync-audit/tests ../../match-replay-desync-audit/environment/data ../../match-replay-desync-audit/solution/solve.py trap/scores_after_v3r3/oracle.txt; echo "oracle $(tail -1 trap/scores_after_v3r3/oracle.txt)"
echo ALL_DONE
