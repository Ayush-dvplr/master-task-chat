Q="/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/qc-20261101T195641-61bb"
DF="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/dockfree.py"
waitslot() { n=0; until python3 "$DF" --need-mb 8192 --cpus 4 | tee -a "$Q/logs/launcher.log" | grep -q START=yes; do n=$((n+1)); sleep 10; done; echo "slot for $1 after $n polls $(date)" >> "$Q/logs/launcher.log"; }
cd /tmp
waitslot lane2
nohup bash -c 'Q="/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/qc-20261101T195641-61bb"; echo "START owner-1 $(date)"; harbor run -p "$Q/copies/owner/slipway-overhaul-replan-repair" --agent oracle --env docker -y -o "$Q/jobs" --job-name owner-1; echo "END owner-1 rc=$? $(date)"; echo LANE_DONE' > "$Q/logs/lane2.log" 2>&1 &
sleep 30
waitslot lane3
nohup bash -c 'Q="/Users/mac/Desktop/Terminal Bench/_runs/20261101/slipway-overhaul-replan-repair/qc-20261101T195641-61bb"; echo "START nop-1 $(date)"; harbor run -p "$Q/copies/run/slipway-overhaul-replan-repair" --agent nop --env docker -y -o "$Q/jobs" --job-name nop-1; echo "END nop-1 rc=$? $(date)"; echo "START stub-1 $(date)"; harbor run -p "$Q/copies/stub/slipway-overhaul-replan-repair" --agent oracle --env docker -y -o "$Q/jobs" --job-name stub-1; echo "END stub-1 rc=$? $(date)"; echo LANE_DONE' > "$Q/logs/lane3.log" 2>&1 &
echo LAUNCHER_DONE >> "$Q/logs/launcher.log"
