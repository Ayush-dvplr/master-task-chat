#!/bin/sh
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote"
docker run --rm --cpus 2 --memory 4g -e PYTHONDONTWRITEBYTECODE=1 -v "$W":/w:ro -w /w/proto python:3.12-slim python -B kill.py only ref,ref2,hybrid books/wide_101 books/wide_102 books/wide_103 > "$W/runs/kill_w1_d2r.log" 2>&1
echo ALL_DONE >> "$W/runs/kill_w1_d2r.log"
