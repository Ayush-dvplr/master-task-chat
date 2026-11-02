# A: session-watermark-settlement: verdict PARTLY (tests loss = ARTEFACT; judge loss = genuine but process-only)

Run `trajectories/claude-opus-5/run_1/`. Recorded score 60.57 / 96.70 / 24.44.

## 1. Run health
- `result.json`: `exception_info` None. Agent 12:33:07–12:40:39Z (~7.5 min, 33 steps, ends with a `finish` step at 33). Verifier 12:40:48–12:41:54Z (66 s).
- `verifier/test-stdout.txt` is only `reward: 0.967`. No tracebacks, no permission or missing-file errors.

## 2. Did the verifier run the agent's program? Yes. Every positive check passed
- test_output.py header L1-8: "The verifier never reads the agent data directory. It builds its own input corpora in temporary directories, computes the expected settlement ... and only then runs the delivered program on that corpus as an unprivileged subprocess." Corpora: `CORPORA` L706-730 (alpha/beta/gamma plus format variants v_bom/v_xmlns/v_cells; `sample` = shipped).
- report.json: all **31 positive tests passed** (positive weight 91). The whole test loss is one negative that fired: `negative_weight_non_stdlib_or_network_import` (-3, status `passed` = penalty applied). The score is 88/91 = 96.70.
- **This penalty is a false positive.** Check L2123-2130 flags any import named in `NETWORK_MODULES` (L2103, includes `"urllib.request"`). The agent's `out/settle_sessions.py` L19 `import urllib.request` is used once, at L187: `uri = "file:" + urllib.request.pathname2url(os.path.abspath(path)) + "?mode=ro"`. That builds a read-only SQLite file URI, with no network access. The instruction (L5) requires "only the Python standard library", and urllib.request is standard library. Neither the instruction nor spec.md forbids importing urllib (grep for `urllib|network|socket` in instruction.md and data/*.md finds no rule). Instruction L11 asks the *agent* to avoid online sources, not the program to avoid a module.
→ **Test loss is an ARTEFACT** (anti-cheat fires on an innocent act, which breaks TS-16). Genuine test points lost = **0**.

## 3. Near-zero
Not applicable.

## 4. Judge
`judge.toml` mode `batched`, 25 criteria, positive weight 45; 34 lost → 11/45 = 24.44. Failed: R8 (3), R9 (1), R13 (3), R14 (3), R15 (3), R16 (1), R17 (1), R18 (3), R19 (1), R20 (3), R21 (3), R22 (3), R24 (3), R25 (3). Every failed criterion is a trajectory **conduct** criterion of the form "locates or constructs <edge case> ... and reports what its program did". Examples: R8 events exactly `session_gap_ms` apart; R13 device time equal to an offset row's `effective_from_ms`; R18 event time + lateness == watermark; R25 build a second calibration control with chosen values and check recovery. The agent did no such probes. Its self-tests were a control-digest check, a determinism rerun and a digest-chain check (steps 19, 22, 25, 31). The agent's work is what failed these, and none is unmeetable. But the *program* handled every one of these edges correctly: the matching tests `test_gap_exact_event_opens_new_window`, `test_effective_dated_offset_applies` and `test_late_drop_ids` all passed. So the judge marks down undemonstrated diligence, not a wrong answer. R9 rewards looking for repeated ids in `raw_events.csv`, which spec.md's precedence table names a decoy ("`raw_events.csv` (a stale preview export)"). That makes R9 an odd preference criterion.
- The judge read the response. R12 (closing count matches final_state) was not triggered, and R23 (the agent reports the recovered bound and shows the digest reproduces) passed.

## 5. Permissions
`tests/test.sh` is identical to T1/T2: `chown root:root /logs/verifier`, `chmod 755`, `chmod -R go-rwx /tests`, then `exec rewardkit`. The program runs as an unprivileged subprocess on verifier-built corpora (header L6). The agent itself set `chmod 644` on the program (step 22). No read issue.

**Verdict: PARTLY.** No genuine test lever: the program was correct on all hidden corpora and format variants. The 3-point test loss is a false-positive anti-cheat. The low overall score comes entirely from 14 judge conduct criteria that each demand a specific edge-case demonstration.
