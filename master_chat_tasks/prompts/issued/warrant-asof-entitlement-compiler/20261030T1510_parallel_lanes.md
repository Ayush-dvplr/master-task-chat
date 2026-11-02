Master note (30 Oct 15:10, Ayush OK): speed up Step 10 with parallel lanes. Same jobs, same full gate, nothing skipped.

Now: oracle-1 and oracle-2 are done (rc 0); oracle-3 is running (harbor pid 24727, chain bash pid 19791). Only 1 container is up and the image is already warm, so the "two at once build the same image" reason for one serial chain no longer applies.

1. Stop the serial chain from starting more jobs: `kill 19791` (the bash chain ONLY). Do NOT kill harbor pid 24727; check with `ps -p 24727` that oracle-3 is still running. Append a line to runs.log: "<time> master: chain stopped after oracle-3, owner/nop/stub moved to lanes 2-3".
2. Start owner-1 now as lane 2, and nop-1 then stub-1 one after the other as lane 3, each with the same command, copy and jobs dir the chain would have used (same `harbor run` flags as in the chain script; `yes |`, `-o` under the same /tmp/harbor-jobs-qc/<run> dir, `nohup`, own log lines `rc <job> <code> <date>` in runs.log). That is at most 3 containers up at once.
3. Poll with rising counters (`sleep 120; echo poll <n>`), never 3 identical calls. When oracle-3, owner-1, nop-1 and stub-1 all have result.json, write `ALL_DONE` in runs.log and carry on with Step 10, the final report and the compare exactly as the prompt says.
4. In v2.md Step 10, write one line: "Step 10 run in 3 lanes from 15:10 (master note); all jobs full, none reused."
