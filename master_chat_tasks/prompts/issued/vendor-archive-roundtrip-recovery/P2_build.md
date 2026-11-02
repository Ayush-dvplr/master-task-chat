# P2 build, vendor-archive-roundtrip-recovery (issued 21 Oct 2026 12:47 IST, from template P2 v1)

Open a NEW session in `/Users/mac/Desktop/Terminal Bench` and paste everything below the line. It stops at "DESIGN READY"; bring that path to the master chat before you say "go".

=== PASTE BELOW ===


You are building one Harbor 0.24 input bundle (a terminal-agent benchmark task) from an accepted idea. It must pass the strict Input Bundle QC and be very hard for a careful frontier agent.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. Then `knowledge/KNOWLEDGE.md` and `knowledge/qc_authoring_checklist_9b8229f6.md` from the same `master_chat_tasks/` folder. Follow all three.

## Inputs
- SLUG: `vendor-archive-roundtrip-recovery`
- ARCHETYPE: `format-recovery` (its fixed output files: decode.py, encode.py, out/decoded_examples.jsonl, out/format_report.json, out/roundtrip_report.json, out/error_analysis.json)
- CATEGORY: `data-processing` (generator `--category` key)
- SEED: `284611`
- IDEA (accepted, with the master's gate notes): `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/vendor-archive-roundtrip-recovery/IDEA.md`
- LEVERS to implement, with ids: STANDARD A, B, E, F (LV-VA-5); NEW LV-VA-1 stream-local state across files, LV-VA-2 opaque extensions kept in position on modified records, LV-VA-3 framing-aware escaping, LV-VA-4 representation memory (non-shortest integers), LV-VA-6 resynchronisation after damage. Full text in IDEA.md.
- Master notes (changes to the idea, risks to watch): 
  - Binary captures do not count toward playground A5 line minimums; the text inputs (frame_index.jsonl, symbol_table.tsv, field_layouts.csv, transport_errors.log, and so on) must still meet them, so size those files to real use (A5), not padding.
  - The agent can round-trip the visible captures to self-check. Put the heavy weight on what visible data cannot self-test: modified records (LV-VA-2, LV-VA-4), streams that cross files (LV-VA-1), multi-defect precedence (LV-VA-5) and resync (LV-VA-6).
  - decode.py and encode.py are at the bundle output root per the archetype (not under out/); keep VB 1.12's artifact list exactly.
  - Trial lessons (pending review): (1) a rule that is merely written far from its use is NOT hard (district-heat: only_H1 0.92, all_lazy 0.59); every lever must change outputs only in hidden cases that combine it with other rules. (2) Ship no file holding expected outputs or decoded answers. (3) Judge: emberforge's real run passed 100% of criteria because they were generic. Every criterion must name a concrete fact with its correct value or direction (for example "The response states that checksum profile P covers bytes from the version byte through the last payload byte"), so a run that misunderstood the rule fails it. No "the log identifies/explains X" criteria.
  - The ChatGPT idea text's own reviewer list and expected scores are NOT to be used; its 13-18% careful estimate is unmeasured. Hardness is decided only by measured baselines (P3).
  - If later stages are graded on supplied intermediates, the instruction must state the exact entry point (function or CLI flag and input file shape) for each stage; otherwise it is a hidden rule.
  - Design stop: before Ayush says "go", the master will review DESIGN_SUMMARY.md and may add findings from the two harden diagnoses now running (district-heat, emberforge). Apply them first.
- TRUTH.md provenance rule: keep what the generator scaffold writes for provenance; if the validator (VB 15.5) and QC (DS-27) still disagree, write OPEN CONFLICT Q18 and do not invent a third option
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/vendor-archive-roundtrip-recovery/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/vendor-archive-roundtrip-recovery/`
- OUT (your report): `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261021_vendor-archive-roundtrip-recovery/build/`

## What makes this task hard (design rules)
- Every graded rule is written down (instruction or a shipped spec file). Difficulty comes from:
  - A, composition: hidden test inputs combine several documented rules in one case;
  - B, chaining: a dependent multi-stage chain;
  - the other levers listed above.
- The instruction states WHAT to build, completely and plainly. The hard part is building it, not reading it.
- For every lever, the shipped visible data must NOT let the agent confirm its reflex reading: no visible example may separate the right reading from the reflex one. Only the hidden cases separate them.
- Downstream stages are also graded on correct intermediate inputs that the tests supply, so one early slip does not zero the score.
- Partial credit: checks are independent and grouped by lever. Independent levers are better than chained ones for grading.
- Do not make it hard by volume, arithmetic, puzzles, formatting, or hidden or ambiguous rules.

## Phases (tick each in WORK/TODO.md; log each command in WORK/LOG.md)

**Phase 0: design, then STOP.**
1. Check the GEN and QC fingerprints (common rule 1).
2. Write `WORK/DESIGN.md`. It must cover:
   - the spine stages;
   - every input file (format, rows, dependencies, at least three chains of length 4 or more);
   - for every lever: the rule text and its location, the reflex reading, the constructed hidden cases, why the visible data cannot confirm it, and its independence from the other levers;
   - the rejection paths;
   - the test plan (40 to 70 checks, with the lever each one serves) and the judge plan;
   - the expected baselines.
3. Write `WORK/DESIGN_SUMMARY.md`, at most 40 lines, for the master chat.
4. Stop and say "DESIGN READY: <path to DESIGN_SUMMARY.md>". Wait until Ayush replies "go". If he passes on changes from the master chat, apply them first.

**Phase 1: scaffold.**
- Run, from GEN, with the common-rule environment variables:
  `python3 generate_bundle.py --out "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles" --name vendor-archive-roundtrip-recovery --archetype format-recovery --category data-processing --seed 284611 --title "<title>" --description "<one paragraph, at most 100 words>" --author "Ayush Sah <ayush.sah@ethara.ai>"`
- Copy the untouched scaffold to `WORK/scaffold_orig/` for reference.
- Never use `--force`.

**Phase 2: data and spec.**
- Write a seeded stdlib `WORK/datagen.py` that produces `BUNDLE/environment/data/`. Keep the data flat, with at least 10 files in at least 5 formats and the planned chains.
- Every file must matter to a graded result.
- Volume must meet playground A5 (at least 20,000 lines in total, and at least 2,000 per csv, tsv, jsonl, txt or log file), but volume is not the difficulty.
- Write the spec file or files holding every graded rule, every output key and every error string (DS-25). Signpost any deliberately wrong value as suspect (CL-6).
- No answers, labelled expected outputs or `sample_*.json` answer keys in the data.

**Phase 3: reference solution.**
- Write `solution/solve.py` and `solve.sh` from the written contract, not from the test code. Keep shared lines with `test_output.py` well under 20%, and solve.py at 30 or more substantive lines.
- It must be deterministic, offline, and run as uid 1000.
- Write `WORK/check_exact.py`, which recomputes the outputs a second, independent way for the hidden cases.

**Phase 4: tests (`tests/test_output.py`).**
- Generate the hidden inputs verifier-side from a seed that lives only in `tests/`. Run the agent's delivered program on them from a foreign working directory.
- Construct the separating cases for every lever, never sample them. For A, combine at least two rules per case. For B, check each stage on supplied correct inputs. For F, check that each rejection and its exact stated error is produced.
- Write the wrong implementation for each lever and confirm that it loses that lever's points. A check that no wrong implementation fails is worthless.
- Weights: 5 for core, 3 for sub-goal, 1 for existence. Up to 70 checks.
- Negatives target this task's real cheats (hardcoded sample answers, keying on file names, reading tests). Keep the sum of negatives at or below the sum of positives.
- No positive check may pass on an absence, and no two checks may read the same observable.
- Write `WORK/LEVERS.md`: one row per check, with its lever id and weight, plus the weight total per lever.
- Re-embed the data, and write `reward.toml` (common rule 6).

**Phase 5: judge (`tests/judge.toml`).**
- Use 12 to 30 binary criteria, mostly on what the agent says or reports in its trajectory. For example: "The agent reports the count of rejected records with the stated reason for each."
- Each criterion must be true for any correct solution and met by every competent approach (JD-7, JD-15). It must not read anything a test reads (JD-8), and it must not reward effort alone.
- Include one code-quality criterion (JD-18).
- Use positive grammar, start with "The agent" or "The response", and write counts instead of "some".
- Keep the five-key header exactly.

**Phase 6: instruction.md.**
- Rewrite it fully. The scaffold sentence has blank words in 4 archetypes.
- Use plain English and state every graded rule, or point to the spec file that holds it.
- Name every output path once.
- Say that the format or contract has N rules the agent must apply, without restating them.
- Include the sentence "You have N seconds to complete this task." with N equal to `[agent] timeout_sec`, and keep the online-lookup sentence.
- Never mention tests, a grader, a checker, a verifier, a judge, weights or "reward".
- No recipe, and under 6000 characters.

**Phase 7: TRUTH.md.**
- Write the 8 sections in order: Defect, Load-bearing work, Verification, Root cause, Solution shape, Ordered plan, Pitfalls, Provenance.
- Mark at least 2 items `(focal)`, at least 1 `(drift)` and at least 1 `(trap)`, all of them real.
- Include the positive weight total, the named negatives and the current sha256 values.
- Apply the provenance rule above. If the validator and QC still disagree on it, write `OPEN CONFLICT Q18` in your report and do not invent a third option.

**Phase 8: self-check (fix every FAIL, then re-run once).**
1. Run the 4 QC scripts from QC on BUNDLE.
2. Run `validate_bundle.py BUNDLE --archetype format-recovery`.
3. Run `playground.py BUNDLE --skip-docker`.
4. Run the oracle through the real tests with the fastest local method that works. Prefer `uvx --from harbor-rewardkit==0.2.1 rewardkit` in scratch against a copy of the artifacts; otherwise run the QL Docker procedure in `knowledge/intake/ql_oracle_nop_procedure.md` in the background. The oracle must reach exactly 1.0 on the tests channel.
5. Clear WARN C6 (no grader, checker or verifier wording).

**Phase 9: report.** Write `OUT/BUILD_REPORT.md` with:
- the tree and file counts;
- data formats, line counts and chains;
- the lever table (copied from LEVERS.md);
- every script, validator and playground result;
- the oracle score;
- open conflicts;
- anything not run.

## Done when
- The bundle exists, all 4 QC scripts show 0 FAIL, the validator passes, and playground static has 0 FAIL.
- The oracle scores 1.0 on the tests channel.
- LEVERS.md covers every check.
- Nothing was written inside GEN or QC (fingerprints re-checked).

Final reply (common rule): DONE or BLOCKED; paths to BUILD_REPORT.md, LEVERS.md and DESIGN.md; check counts; oracle score; open conflicts.
