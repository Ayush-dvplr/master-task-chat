Q="/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/qc-20261101T195641-61bb"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
cd /tmp
n=0; until python3 "$DF" --need-mb 8192 --cpus 4 | tee -a "$Q/logs/launcher2.log" | grep -q START=yes; do n=$((n+1)); sleep 10; done
echo "slot for lane1b after $n polls $(date)" >> "$Q/logs/launcher2.log"
for r in oracle-1r oracle-2 oracle-3; do echo "START $r $(date)"; harbor run -p "$Q/copies/run/slipway-overhaul-replan-repair" --agent oracle --env docker -y --no-delete -o "$Q/jobs" --job-name $r; echo "END $r rc=$? $(date)"; done
echo LANE_DONE
