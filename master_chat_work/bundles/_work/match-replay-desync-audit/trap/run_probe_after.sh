#!/bin/zsh
cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/match-replay-desync-audit"
export PYTHONDONTWRITEBYTECODE=1
python3 -B local_score.py ../../match-replay-desync-audit/tests ../../match-replay-desync-audit/environment/data probe/optimize.py trap/scores_after_v3r3/probe_agent.txt
tail -1 trap/scores_after_v3r3/probe_agent.txt
echo ALL_DONE
