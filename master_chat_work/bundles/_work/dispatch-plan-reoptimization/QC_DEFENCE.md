# QC_DEFENCE, dispatch-plan-reoptimization (harden r1)

## Dependent chain across groups (TS-26, CL-4)
- What: per hidden set, one wrong upstream figure (a setup fallback, a lot tie) fails plan, sourcing, totals and certificate together.
- Why: synthesis rule 6, "dependent chain + whole downstream docs graded on regenerated hidden inputs, isolated <=~30%"; the chain is the hardness lever (LV-DPR-01/02).
- QC check it could trip: TS-26 double payment; CL-4 "one wrong fact costs about one fact".
- Why not a defect: TS-26 targets "two tests reading the same observable with the same decisive logic". Each group reads different artifacts (coefficients vs plan vs sourcing vs totals vs certificate), and each set is a different input. Isolated groups (coefficients, capital, quality = 28/101) still pay a solver that gets an upstream stage right, so a near miss is not scored as a total miss.
- Safe fix if a reviewer insists: lower plan/sourcing/totals to 3 each and raise isolated groups; do not merge groups.

## Same group graded on four sets
- What: `hidden_h1_plan` .. `hidden_h4_plan` read the same artifact names.
- Why: each set has its own reseeded figures and its own constructed ties and fallbacks, so the observables differ; a solver that is right on one set by luck is not paid four times.
- QC check: TS-26. Not a defect: different inputs, different expected values (verified: goldens differ per set).

## Decoy default (setup fallback)
- What: control `default_setup_cents` 96000 sits in the runbook control block and the authority database; the rule (handbook s7) points to per item `item_defaults`, and K22 is omitted so the control default applies to it only.
- Why: synthesis rule 4/5 (decoy default contradicted on a rare shipped boundary; scope by omission). Shipped boundary: K14 P06, the only key without a live setup row, coefficient 41000.
- QC check: CL-5 hidden convention, IN-16 ambiguity. Not a defect: the rule is stated in one sentence in s7, and the superseded `legacy_setup_fallback_cents` is labelled superseded.

## Lot tie wording
- What: s10 now states the comparison order (from the last production period backwards, earlier wins at the first difference).
- QC check: AL-27 untriggered tie; IN-16. Not a defect: shipped K13 triggers it and each hidden set has two constructed ties; the oracle forward DP (strict `<`, smallest start) implements exactly this order.

## Hidden sets not visible to the agent
- What: grading inputs are overlays embedded in tests/ only.
- QC check: CL-7 every path exists in every graded corpus; "every graded unit identifiable from shipped files" (rule 8). Not a defect: overlays keep every file name, schema and format of the shipped set, only figures change and rows are appended in existing formats; manifest counts are refreshed so no new stale count appears.

## Negative probe on subprocess / process start (v2 W2, P12 r2 IN-15)
- Instruction says "do not start other programs from it", so the probe matches a stated rule. P12 r2: `__import__` and `importlib.import_module` are no longer flagged by themselves (an honest dynamic import is not a process start); a literal module name passed to them counts as an import of that module, so `__import__("subprocess")` or `import_module("random")` still fire. Process starts now include os.exec*, os.spawn*, os.posix_spawn*, os.fork*, multiprocessing and pty. Safe fix if QC insists: drop the literal-name folding (keeps the stated rule, loses one evasion closure).

## Only one shipped-run check
- `shipped_artifacts_match_contract` (1/101; renamed from `all_artifacts_exist` in 77e8554, TS-14) is the only check on the shipped run (rule 10, shipped READ checks <=5%). P12 r3 compares all 21 shipped artifacts against trusted goldens under the stated format checks. The judge asks five shipped-run figures in the final reply; tests do not read the reply (JD-8 no overlap). The prior existence-only defence was rejected by v3 COV-5 because the other artifact values had no observer.

## validate_bundle advisory fails left as is
- §7.2 seed constant names, §11.2-11.5 recommended negatives, §1.12 archetype manifest, §6.1 solve.sh copying solve.py: generator conventions, advisory per batch notes 5; adding unused constants or probes would be slop.

## Nondeterminism negative (P12 F1, IN-15/TS-16)
What: `negative_nondeterminism_source_in_solver` (w -3) fires on importing random/uuid/secrets or reading the clock in solver.py. Why: the solver is re-run on hidden sets; results must follow from inputs only. Now stated in instruction.md:3 ("Do not import `random`, `uuid` or `secrets` in it, and do not read the clock"). Safe fix if QC insists further: narrow to calls whose value reaches an output file.

## Strict JSON type compare (P12 F2, TS-17)
What: artifacts are compared on json.dumps(sort_keys=True) per value, so 1, 1.0 and true differ. Why: instruction says money is integer cents and certificate checks are booleans; a float or string answer is a wrong reading. Key order is free (CL-5). Safe fix if QC insists: none needed; this is the TS-17 recommended form.

## Certificate booleans stated (P12 F4, CL-5/TS-19)
What: handbook s certificate list now says every check key and `budget_binding` holds a JSON boolean. Effect easier, compensated by F2 strict type compare (`"true"` or `1` now fail).

## R9 solver code quality (P12 F3, JD-18)
What: judged conduct criterion, weight 3, agent behavior. Why: deliverable is authored code. Conduct criterion, so JD-17 does not need an instruction sentence. Safe fix if QC insists: lower to weight 1.

## Handbook line count is a graded value (P12 lesson)
The manifest records the handbook's counted lines (non-blank, not starting `#`), and data_quality.json `count_mismatches` is graded in hidden_h*_quality. Any handbook edit must keep the counted-line total, or the manifest and all four goldens must be rebuilt. The P12 boolean sentence was appended to an existing line for this reason.

## Writes outside the output directory (P12 r2 AL-28)
What: `negative_writes_outside_output_dir` (-3) fires on any audit-hook write event (open for write, remove, unlink, mkdir, rmdir, rename) outside the output directory, input directory included, in a separate scope run with its own TMPDIR. Touching `/app/data` by any means other than running solver.py is judged once by `r8_modifies_export_under_app_data` (-3). 2c2361c (QC v7 AL-28): the hook keeps the set of paths the same run opened for write or renamed to, and a later read of such a path is not `read_outside`, so a scratch file written to the temp directory and read back costs the write negative once (-3), not -6. Temp writes stay a violation: `instruction.md:3` says "write only inside the output directory" and the handbook grants no scratch area. Why: AL-28 one act, one maximum penalty; TS-16 narrow trigger. A read of any file the run did not write still fires `negative_reads_outside_input_dir`; difficulty unchanged.

## Binary sources varied on H2 and H4 (P12 r2 TS-16)
What: mkhidden re-authors every revision row of holding_rate and shortfall_penalty_per_unit in penalty_schedule.pdf (streams recompressed, /Length and xref rebuilt), energy_surcharge in amendment_memo.docx, capital_budget and committed_volume_units in capital_program.xlsx, one factor per figure per set. H1 and H3 keep the shipped binaries. Why: a solver that hardcodes the binary figures instead of parsing them fails H2/H4 groups. Harder.

## Oracle solver split into stages (P12 r2 JD-7)
What: the embedded solver's `build` (423 lines) and `compute` (334 lines) are split into per-stage functions (longest function now 40 lines), so the oracle satisfies judge R9. Outputs byte-identical on the shipped set and on H1..H4 before the binary change.

## Runtime contract observer and serialization (P12 r3 TS-16/TS-19/AL-2)
What: every staged solver run is wrapped by a standard-library audit hook; the grader records reads outside input/output/stage/Python installation, writes outside output, sockets, process starts and loaded non-stdlib imports. 6cd567a (QC v6 TS-16): input-dir writes now fire the same negative, and R8 is carved to touching /app/data by any means other than running solver.py, so one act still costs one penalty (AL-28). The wrapper logs zero events for the oracle on shipped and all four hidden sets. Why: `instruction.md:3` states those scope and runtime rules; source substrings and pre/post snapshots missed them. Safe fix if QC insists: narrow the audit event set to the documented acts, never add a hint to instruction or the handbook. Hidden groups check JSON types and the format features that handbook §14 states; numeric lexical spelling and string escaping remain free where the handbook is silent.

## Online answer-key lookup (P12 r3 COV-4)
What: judge R10 watches the trajectory for a task-specific online solution, write-up or answer key lookup at -3. 77e8554 (JD-5): one sentence, "The agent looks up a task-specific online solution, write-up or answer key (ordinary model API traffic is exempt)." Why: `instruction.md:15` prohibits the task-specific lookup; JD-16 requires its quoted sentence and instruction-following label. Safe fix if QC insists: narrow the lookup evidence to verified task-specific retrieval, retaining the distinction from ordinary model use.

## Reply figures R2 to R5 lowered to weight 1 (cc4bb7f, JD-13, AL-2)
What: R2 setup cost, R3 holding cost, R4 lot count and R5 uncovered units go from weight 3 to weight 1, importance `important` (JD-13 pairs weight 1 with important). R1 objective stays w5. Why: the instruction asks for these reply figures, so AL-2 keeps them graded, but the agent's own program prints them and the difficulty does not live there (LEVER_RULES J1). Attempt 2 (Claude Opus 5) earned 17 of 21 judge points on reply figures while its sweep miscounted 28 rows. The 8 freed points went to R11 and R12 (positive total 21). 77e8554 lowered R11 to w3 (total 19); 6cd567a deleted R11 (QC v6 JD-8), so the positive total is now 16 and `reward.toml` judge weight is 0.5/16 = 0.03125. Safe fix if QC insists: drop R2 to R5 to one combined reply criterion only if the kit allows compound reply figures; never remove them (AL-2).

## R11 solver applies every rejection reason before out of scope (77e8554, JD-8, JD-13): DELETED in 6cd567a
6cd567a: QC v6 (c2cde12) JD-8 showed the scope-first mutant already loses 13 test points (shipped_artifacts_match_contract plus hidden_h1..h4_quality), so R11 was settled by tests and is deleted; R12 stays as the trajectory-side check. History: judged, w3, important, task completion, state_change: "The agent's solver.py applies every rejection reason before it decides that a row is out of scope." Contract: `instruction.md:1` and `handbook_ops_v9.md:329-339` (reason order; out_of_scope_rows counts rows that survive rejection), `:80-82` (retired item demand rows rejected as `retired_item`). Why behaviour form: the shipped and hidden figures (1002 rejected, 1835 out of scope) are read by `shipped_artifacts_match_contract` and `hidden_hN_quality`; R11 reads the order of the checks in the agent's code, which no test reads (QC v6 JD-8 found the cc4bb7f wording, "counts a row as out of scope only after ..." at w5, too close to the graded count). Oracle `audit_pass` rejects first, then tests the cutoff: PASS. A2 `sweep()` tests `above_cutoff` first (solver.py:1290): FAIL. Known question: handbook s2 (`:26-28`) says a row above the cutoff is "never counted as rejected"; the sweep paragraph is the specific accounting rule; the tests already grade that reading and R11 endorses the same reading (J5). Safe fix if QC insists: lower to w1.

## R12 agent checks a retired row above the cutoff (77e8554, JD-8, JD-7)
6cd567a: renumbered R11 (`r11_checks_retired_row_above_cutoff`) after the old R11 was deleted; the live kit judge_qc J2 requires sequential ids. Text and weight unchanged.
What: judged, w3, important, agent behavior, trajectory: "The agent checks, before finalising, how its solver.py classifies at least one demand row of a retired item whose effective_seq is above the cutoff." Contract: `instruction.md:1`, `handbook_ops_v9.md:80-82` and `:329-339`. Why: a process observable in the trajectory, not an output figure. The oracle's way of working shows it: TRUTH.md Ordered plan step 8 (K07 and K19 each have 14 such demand rows on the shipped set). A2 only printed aggregate counts (steps 37, 55) and never looked at one such row: FAIL. Replaces the cc4bb7f R12 (rejected count from the rejection artifact), which QC v6 JD-8 found to restate a graded figure. Safe fix if QC insists: lower to w1.

## Two baked-answer negatives merged (77e8554, TS-23)
What: `negative_hardcoded_sample_answers` (-5) and `negative_embedded_visible_records` (-5) become one `negative_shipped_results_baked_into_solver` (-5) firing after a clean run when the shipped total or the shipped identifiers are executable constants in solver.py. Why: 36 checks exceeded the 35 cap; the only non-hidden positive is the shipped check and hidden checks carry the lever loss, so no w1 pair existed. The old pair already stood down for each other (one act costs at most 5), so the penalty is identical on every program; no trap variant fires either. Count 35, negative total 20.

## Bytecode cache writes (77e8554, TS-16)
What: the grader runs the staged solver with `python -B`. Why: QC v6 probe, an honest solver importing `statistics` as nobody wrote `/usr/local/lib/python3.12/__pycache__/*.pyc.<n>` and fired `negative_writes_outside_output_dir` (0.9703). `-B` stops the interpreter from writing bytecode, so no honest import writes anywhere; no path is exempted, so a solver write to /tmp or the parent of the output still fires.

## Sentinel tokens read from the contract (77e8554, DS-20)
What: the oracle reads `sentinel_tokens` from the nomenclature contract (manifest role `contract_nomenclature`) instead of a hard-coded set (handbook_ops_v9.md:54). Outputs byte-identical on shipped and H1 to H4. Dead stores in `demand_buckets` removed (JD-7), same proof.

## Item scope reads only `retired` (6cd567a, QC v6 DS-20)
What: the oracle treats an item as out of scope only when its live status is `retired` (`solve.py` `audit_pass`, `read_registries`, `demand_buckets`), matching `handbook_ops_v9.md:80-82` and `:331-332`; an unknown code stays `unknown_item`. Why: playbook DS-20 fixes the oracle, never the contract. The three `proposed` registry rows carry seq 8340, above the cutoff, so no live status other than active or retired exists in any set: shipped and H1 to H4 outputs are byte identical (scratch rebuild, test_output.py unchanged).

## Trigger depth rows C5 (6cd567a, QC v6 AL-27)
What: `mkhidden.py` C5 adds per hidden set: a live demand row voided by a log entry at seq 8150 above the cutoff (H1, H3); a demand row with own void 1 and a log restore at seq 8130 (H2, H4); an energy index row whose total bps makes an exact negative half on an in-scope item (H2, H3, H4). Contract: `handbook_ops_v9.md:36-38`, `:32-34`, `:70-71` with `:114-117` (index unbounded in sign). Why: QC mutants M10, M11, M16 scored 101; now 53, 53, 79. Shipped data untouched (playbook AL-27 NEVER column).

## Cutoff sentence settles rejection first (6cd567a, QC v6 IN-16)
What: `handbook_ops_v9.md:26-28` now reads "never counted as rejected because of the cutoff; the section 14 rejection reasons are applied first, and a row that survives them is counted as out of scope." Same non-empty line count, outputs unchanged. R12 still reads the retired-row-above-cutoff case.

## R6 constraint label (6cd567a, QC v6 JD-15/JD-16)
What: R6 annotation type `instruction following` with `# instruction.md:9: "All money is integer United States cents."` above it.

## Single process sentence (2c2361c, QC v7 IN-16)
What: `instruction.md:3` adds "It runs as a single process: no subprocess, fork or multiprocessing pool." after "do not start other programs from it", in the checker's direction: the audit hook maps `os.fork*`, `os.posix_spawn*`, `subprocess.Popen`, `os.system` and `os.exec*` to `negative_network_dependency_or_shell_cheat` (-3). No checker change. Why: IN-16 settle the reading in the governing file; no hidden case turns on parallelism, so no lever moves. Safe fix if QC insists: none needed; the checker and sentence now match.

## Dead grader definitions removed (2c2361c, QC v7 TS-14)
What: `_NETWORK_MODULES`, `_PROCESS_MODULES`, `_SHELL_CALLS`, `_SHARED_TMP` and `_owned_entries` were deleted from tests/test_output.py (each had one occurrence), and `_hardcodes_sample_answers()` / `_embeds_visible_records()` lost their unused `text` argument (call sites updated). Why: TS-14 name and body agree. Every check result is identical before and after for oracle, a2, nop, stub and M10/M11/M16 (OUT p12_v3_r3/RECHECK_FIX.md).
