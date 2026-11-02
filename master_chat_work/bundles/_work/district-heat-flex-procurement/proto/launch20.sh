#!/bin/bash
P="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement/proto"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement"
while [ "$(docker ps -q | wc -l | tr -d ' ')" -ge 2 ]; do sleep 15; done
echo "launch $(date +%T)"
rm -f "$P/dout/KILL20.txt"
docker run --rm --name dh_w1_kill20 --cpus 2 --memory 4g -v "$P":/w -v "$B":/b:ro -e EXTS="g20_61 g20_62" -e KF=dout/KILL20.txt district-heat-flex-procurement__eh2yzcy__env-main:latest bash /w/kill_in_docker.sh
echo "exit $? $(date +%T)"
