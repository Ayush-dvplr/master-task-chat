# P9 harden lp1 r1 diagnosis: vendor-archive-roundtrip-recovery (board 52dbb3c)

Written 23 Oct 2026 IST. Phase 1 only. No BUNDLE edits were made in Phase 1. Live QC kit: harness HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e.
RESULT: `traj_a2/trajectory_job_vendor-archive-roundtrip-recovery_0204d5/`, claude-opus-5 Run 1: tests 100.0, rubric 100.0, combined 100.0 (`logs/pass-summary.json`).

## 1. Phase A: is the 100 genuine? YES
- **Run copy.** `logs/job-config.json` points at `.kiro-staged-tasks/vendor-archive-roundtrip-recovery`. `diff -rq` of that folder against BUNDLE shows two differences, both made by the harness: `.kiro-staged-from` exists only in the staged copy, and `task.toml` lines 25 and 32 add `host.docker.internal` to allowed_hosts (the judge proxy injection). Nothing else differs. `agent/instruction.txt` is byte-identical to BUNDLE `instruction.md`. The BUNDLE tree sha before harden is f0cfd07a5746 (25 files).
- **No errors.** Run 1 `result.json` has exception_info None and reward 1.0. ctrf records 24 positive checks passed and 5 negatives that did not fire (they show as "failed" because they are inverted). `finalize.log` ends with "done", and `judge_trajectory` reports 1 ok, 0 failed.
- **The judge read the response.** reward-details quotes it per criterion, for example R1 "gives -786 for the last record of capture_gamma.varc" and R7 "validation claims are backed by recorded commands ... 6000 fuzz cases". All four figures in the agent's final message (step 40) equal TRUTH.
- **Earlier scores were artefacts.** The 52.41 came from the 0600 permission bug. The corrected replay on 21 Oct gave tests 88.97, before the r1 rebuild.

## 2. How the agent worked (trajectory, 41 steps, 19:14:54 to 19:25:52, 11 minutes)
- Steps 2 to 7 (first 30 s): it read every spec in full: `cat format_contract.md`, then `decoder_appendix.md` plus `escape_rules.md`, then `crc_profiles`, `schema_registry`, `revision_notes` and `loader_notes`, and an xxd dump of alpha, beta and gamma.
- Steps 8 to 11: it profiled the tables. It found that the names follow `<prefix>_%04d`, that the aliases follow `name@s<id%40+1>`, and that every id has exactly one alias row. It then baked the tables as a 2100-byte packed blob instead of the CSV.
- Step 12 (3 min 17 s in): it wrote `/app/decode.py` in full: decode, `--stream`, `--salvage` and the rejection order. Step 15 wrote `encode.py`.
- Step 24 made the only logic edit: it wraps the single-file frame loop in `try/except Damaged: break`. That path is not graded.
- Steps 25 to 32: self-tests. These were a full catalog round trip, header-error ordering, salvage on injected damage (fchk, damage up to the trailer, bad header), a hand-built continue/reset stream, overlong re-encode, a standalone CLI run from a temp dir, and a fuzz of 6000 cases.
- After the first write it never changed the logic that the grader checks.

## 3. Lever table (current bundle, before harden)
Verdict LEAKED means full credit on every check and criterion that the lever drives.

| Lever (r1 name) | Rule text and location | Agent got it right at | What gave it away | Checks (pts) |
|---|---|---|---|---|
| RUN: state per stream run | decoder_appendix.md L17-21 "A segment continues the state ... when that previous segment has `stream_continues` set. Every other segment starts from fresh state." | step 12, decode.py L328-349 (`continues[stream_id]`) | Rule stated next to its use; the shipped stream 3 (alpha continues, beta closes, gamma restarts) is a separating example; the judge R1/R2 ask makes the agent compute it (step 22) | stream_interleaved, stream_new_run, stream_eval_mix, stream_challenge_mix (20) |
| REV: own revision per segment (loader_notes decoy) | format_contract.md L136-138 "Every segment uses its own revision byte. Revisions 0 to 3 are identity revisions on every segment, continuation segments included" | step 12, L247 `canonical_for_short_key(raw_key, revision)` | The decoy is refuted in plain words on the line that uses it; the final reply says "Per the contract (which overrides loader_notes.md)" | stream_revision_change (5) |
| REMAP: remap before alias; unlisted bytes are identity | revision_notes.md L12-15 "Every other key byte under that revision is its own canonical id ... Resolve the short key through the revision first" | step 11 (REV_BLOB), step 12 L63-64 `.get(key, key)` | The procedure is numbered in contract L131-142 | stream_remap_alias, single_remapped_modes (10) |
| STATE: dict does not move the cumulator; reset | format_contract.md L97-99 "No other frame moves the cumulator, except reset" | step 12, L259-265 | The exception is written as its own sentence | stream_reset_mid_run, reset_clears_state (8) |
| ESC/EXT: bounded unescape; opaque extensions | escape_rules.md L11-16 (the trap is explained: "must not swallow that sync byte") | step 12, L115-142 and L187 | W1 violation: the trap is explained | single_escapes_ext (5) |
| SALV: resync and state across damage | escape_rules.md L54-65 ("A `0xAA` that merely appears inside damaged bytes is not a resume point", "state exactly as it was") | step 12, L352-396 (probe state copy) | W1 violation: both reflexes are named | salvage_state, salvage_mix (10) |
| ENC: delta_raw_len memory, null means shortest | decoder_appendix.md L73-77, format_contract.md L110-117 | step 15, write_sleb(length) | Stated twice; checked by the agent's self-test (step 25) | encode_unmodified, encode_edited, encode_new_record (15) |
| REJ: precedence and offsets | format_contract.md L151-167, a numbered list with an explicit "first non zero reserved byte" | step 12, L269-297 | Numbered list in one file | 5 reject_* checks (15) |
| Reports | decoder_appendix.md L95-162, key by key | step 19, make_reports.py | Key-by-key spec | 4 report_* checks (12) |
| Judge R1-R4 figures | instruction.md asks for them; they are computed from shipped files | steps 22-23 | The ask itself makes the agent run its own stream decode on the shipped files | R1-R4 (20 of 24 judge points) |

Common cause (this matches cohort DIAGNOSIS section 0, cause 4):
- Every rule sits in one plain sentence beside its use, and two of them explain the trap.
- The shipped stream 3 separates the RUN rule.
- No rule has a plausible second reading.
- The hidden fixtures only repeat rules the agent had already coded at step 12.
- The judge figures come from shipped files and need only the same code.
- The tests channel cannot separate a careful reader from the oracle: the a2 program is oracle-equivalent on all 24 checks.

**PRIMARY CAUSE: levers too weak by design (cause 4).** No artefact was found. The harness did not change the scoring, and our QC rounds put no new figure or rule in front of the agent.

## 4. Reflex program for Phase 3
- The agent's final `/app/decode.py` (17880 bytes) and `/app/encode.py` (3592 bytes) are saved as `OUT/agent_program/decode.py` and `encode.py`, with its `/app/out` reports in `OUT/agent_program/out/`. They come from `Run 1/artifacts/app/`.
- It bakes the shipped tables by pattern: names `<prefix>_%04d`, aliases `name@s<id%40+1>`. The new hidden inputs therefore keep the shipped tables, and only the segment files are reseeded.
- Its encoder packs `raw_value` with `signed=True` and passes `delta_raw_len` straight to the length padder.

## 5. Direction for Phase 2 (applied directly; no "go" needed)
Levers: L2 make-it-match repair, L3 stateful stream, L5 strict type beside a normalising rule, L6 scope carried by a definition. Each sits in the file that governs its data, has no trap explanation and no worked separating example (except L5, whose separating row ships). Each is graded by whole hidden documents. The details are in `WORK/LEVERS.md`.
