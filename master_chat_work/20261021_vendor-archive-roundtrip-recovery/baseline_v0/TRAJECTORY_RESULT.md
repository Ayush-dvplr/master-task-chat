# vendor-archive v0 trajectory (1 run, claude-opus-5, job 2026-10-21__17-36-36)
Source (copied, read only): Harbor_Harness/Terminal_2.0_Harbor_Harness/jobs/vendor-archive-roundtrip-recovery -> ./trajectory_job/

| channel | reported | note |
|---|---|---|
| tests | 4.83% (7/145) | INVALID: verifier bug, see below |
| rubric (judge ran) | 100% (36/36) | real |
| combined | 52.41 | INVALID (tests channel) |

## Verifier bug (REAL, reproduced locally)
- test_output.py writes each input to a NamedTemporaryFile/mkdtemp (0600/0700, owned by root) and then runs the agent's decode.py as `nobody` via setpriv. nobody cannot read the file.
- The agent's decode.py catches OSError and prints {"error":"unreadable_input","detail":"...<temp path>..."} with rc 0. So every decode check fails, and the two negatives fire (filename_dependent -5, nondeterministic -3) because the temp path differs per call. 15 - 8 = 7.
- Reproduced: chmod 000 on an input gives exactly that output. vendor-archive's tests have 0 chmod calls; the other 3 bundles do chmod their temp files.
- Never caught before: the builder and P3 ran rewardkit as a normal user (no setpriv); Docker oracle (Step 10) was not run. The Docker oracle would also score near 0.

## Agent's real work (same test file, agent's /app files, run locally as normal user, Python 3.14 and 3.12 identical)
- 129/145 = 88.97% tests. Failed only: basic_delta, va1_cross_delta (raw-frame running-total contract bug from P3), va4_overlong_bytes, report_decoded_examples. No negative fired.
- Implied combined ~94 (88.97 tests + 100 rubric) -> far above the per-run gate (overall<30). File: agent_program_rescored_local.json
