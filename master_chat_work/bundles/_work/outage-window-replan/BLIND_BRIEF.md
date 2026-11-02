# BLIND_BRIEF: scoring one blind program on the final tests

Scorer: `proto/score_blind.sh` (container entry) runs `proto/score_blind.py` against the
FINAL `BUNDLE/tests/test_output.py` (read-only mount), with a stub `rewardkit` that registers
every criterion and weight. It copies the blind program to `/app/out/derive_report.py` and the
blind's delivered documents (`BLIND_DIR/out/*.json`) into `/app/out`, copies the shipped data to
`/app/data`, then calls every check exactly as rewardkit would (as root; the tests drop to
`nobody` and run `python3 /app/out/derive_report.py --data <dir> --out <dir>` from a foreign cwd).

Covered: shipped checks (delivered documents), hidden corpora h2 and h3 (generated from the
seeds inside tests/), altered copy, relocated copy, missing input, both test negatives.

## Command (one blind)

```bash
SHA=<blind sha>; BLIND_DIR=<blind dir>
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/outage-window-replan"
B="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/outage-window-replan"
mkdir -p "$W/blinds"
docker run --rm --init --memory 4g --cpus 2 --name owr_score_$SHA \
  -v "$B/environment/data:/srcdata:ro" -v "$B/tests:/tests:ro" \
  -v "$BLIND_DIR:/blind:ro" -v "$W:/d" \
  python:3.12-slim perl -e 'alarm 1800; exec @ARGV' bash /d/proto/score_blind.sh \
  > "$W/blinds/score_$SHA.txt" 2>&1
```

Memory and cpus match `task.toml` (`memory = 4096` MB, `cpus = 2`). At most 2 such containers
at once (check `docker ps` first; machine-wide at most 3 Docker-heavy sessions).
Worst case per blind: 6 program runs x 90 s test-side timeout plus generation, under 15 min;
the 1800 s alarm is a backstop.

## Output (`WORK/blinds/score_<sha>.txt`)

- `CHECK <name> w=<w> PASS|WRONG|TIMEOUT|CRASH|FIRED|silent <first message>`: WRONG = valid run,
  document differs (first differing path shown); TIMEOUT = no finish within 90 s
  (stated limit 60 s); CRASH = non-zero exit.
- `RUN <input set> <seconds> rc=<rc>`: seconds per corpus (h2, h3, altered, relocated, missing).
- `LEVER points (..., 68): lost N = WRONG a, TIMEOUT b, CRASH c` (hidden region, policy_audit,
  segment and summary checks).
- `## SCORE got/92 = x (negatives n)`.
- `ALL_DONE` last.

Validated 07:22 IST on the oracle (solve.py + shipped outputs, `blinds/score_oracle.txt`): `## SCORE 92/92 = 1.0000`, negatives silent, h2 2.5 s, h3 2.6 s, 16 s total.
