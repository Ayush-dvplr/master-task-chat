# A: reminder-store-reconciliation — verdict GENUINE (tests) / judge losses = process-criteria only

Run: `trajectories/claude-opus-5/run_1/`. Recorded 62.25 / 83.33 / 41.18.

## 1. Run health
- `result.json`: `exception_info` None. Agent 16:20:09–16:37:34Z (~17.5 min, 72 steps, ended with a final message, no step limit; MAX_ITERATIONS 350). Verifier 16:37:43–17:18:24Z = **40 m 41 s** (task.toml verifier timeout 9000 s, so no verifier timeout).
- `verifier/test-stdout.txt` = 15 bytes, only `reward: 0.6225`. No traceback, no `Permission denied`, no `No such file`. `ctrf.json` carries name/status/weight only (no messages).

## 2. Did the verifier run the agent's program?
Yes. `tests/test_output.py` `_invoke` L2293-2306 runs a `_readable_copy()` of the agent's `transform.py` (mode 0644 copy; comment L2281-2284 "whatever mode the agent left") under `setpriv` as nobody/nogroup, `_RUN_SECONDS = 200` (L2161); nonzero exit → AssertionError, caught by `_pass` L2150 → False. 22 of 35 tests passed, including 13 hidden-corpus tests (fresh cycle, torn records, frozen merges, damaged companion, tie-a, tie-b, wide calibration…), so the program ran, read and wrote fine as the unprivileged user.

Failed tests (13, all weight 1, 13/78 points):
- `test_generalisation_shifted_grace_boundary` (L2591, corpus `mutant-shifted_grace_boundary`, field `governing`).
- 12 trap tests L2523-2580 (`trap-due_chain`, `lead_delta`, `priority_drift`, `block_shuffle`, `backref_window`, `count_bias`, `endian_island`, `span_shadow`, `note_rotate`, `tag_alias`, `sentinel_escape`, `crc_span`), each `_same_rows("trap-X", [field])`.

**Cause (one bug, agent's own code):** agent `out/transform.py` `recover()` L742-770 keeps every surviving parameter assignment across 9 search stages (`SEARCH_STAGES` L715-725, cartesian `product` of survivors × stage candidates) and ends with
`if len(survivors) != 1: raise SystemExit('parameters underdetermined: %d assignments' % len(survivors))` (L768-769). The same code is in its first `create` at trajectory step 12.
- Trap corpora are built with ONLY one transform flag on (test_output.py `build_specs` L1466-1467 `if only is not None and tier != "sample": flags = only`). With the other transforms off, their parameters cannot move any control, so every candidate survives; survivors multiply stage by stage. INFERRED: the run either exceeds 200 s (40 m 41 s verifier ≈ 12 × 200 s) or hits the SystemExit — both are failures of the agent's program on valid input.
- Shifted-grace corpus sets every group gap to 45 (L1479-1480) in all tiers including calibration, so grace candidates tie on every control → >1 survivor → SystemExit. The agent's settlement rule itself is right (`govern()` uses `>= grace`, transform.py L505, same as reference L1705); this is NOT a boundary bug.
- The spec states ties are legitimate: `calibration.md` L3-8 "A wrong value moves at least one of them unless that value reads and settles every calibration capture exactly as the right one does, and such a value settles the cycle captures of this directory the same way as the right one." The uniqueness promise is scoped to the shipped slice only: instruction L3 "in the calibration slice shipped here exactly one candidate of each reproduces every control figure". Instruction L9 warns of reruns "under other parameter values with a calibration slice of their own ... each run must finish within 200 seconds".
→ wrong behaviour on a fully stated rule = **GENUINE**. Caveat: test docstrings say each trap checks a transform inverse ("the chained due offset is undone"), but the agent failed all 12 for one recovery reason (INFERRED from code; no failure messages exist). One mistake is billed 12 times (see B §6).

## 3. Near-zero check
Not applicable (tests 83.33).

## 4. Judge
`judge.toml` mode `batched`, 29 criteria, positive weight 51; 30 lost → 21/51 = 41.18. The judge read the response: closing-message criteria R5, R13, R19 passed. All 10 failed criteria (R17, R20-R23, R25-R29, all weight 3) are trajectory **conduct** criteria that need a specific probe printed (e.g. R21 write an encoder and byte-compare a re-encoded capture; R26 print a group whose newest member came exactly supersession_grace after its predecessor; R22 time a full run on a larger calibration slice). The agent did none of these; it self-tested only on shipped data. They fail because of what the agent did, not because they can't be met (the oracle can do each one). But they are procedure-specific probes (JD-15 conduct, odds-raising/preference at w3). They grade the agent's process, not a missed rule.

## 5. Permissions
`tests/test.sh`: `chown root:root /logs/verifier`, `chmod 755 /logs/verifier`, `chmod -R go-rwx /tests`, `exec rewardkit /tests --workspace /app ...`. The grader copies the agent program to 0644 before running it unprivileged (L2281-2306), and the output dir is 0777 (`_handout` L2260). Anti-cheat `_produced_with_altered_decodes` L2428-2443 corrupts and `chmod 0`s the `.decoded.json` answer files. Our /app/out read bug cannot happen here.

**Verdict: GENUINE.** 13/78 test points lost to one real recovery bug (assumed uniqueness, which the spec says only holds for the shipped slice). 30/51 judge points lost to unperformed process probes.
