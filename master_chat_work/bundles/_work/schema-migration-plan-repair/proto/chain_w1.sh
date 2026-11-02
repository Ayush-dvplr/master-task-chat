#!/bin/sh
# Scratch: one nohup chain for kill2 then B7 (host side).
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/schema-migration-plan-repair"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair"
A="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Output_RFP/schema-migration-plan-repair/trajectories/claude-opus-5/run_1/artifacts/app"
L=/tmp/opencode-logs/locks/schema-migration-plan-repair.lock
echo "e3e74e6 $(date)" > "$L"
rm -rf /tmp/smpr_tcopy; cp -Rp "$B/tests" /tmp/smpr_tcopy
echo "== kill2 $(date)"
docker run --rm --name smpr_w1_kill2 --cpus 2 --memory 9g -v "$W":/w python:3.12-slim sh /w/proto/kill2.sh
echo "== b7 $(date)"
docker run --rm --name smpr_w1_b7 --cpus 2 --memory 6g -v "$W":/w -v /tmp/smpr_tcopy:/t:ro -v "$A":/src_app:ro --entrypoint sh qcwarm-smpr-verifier-2b0f:latest /w/proto/b7.sh
rm -f "$L"
echo "== chain end $(date)"
echo CHAIN_ALL_DONE
