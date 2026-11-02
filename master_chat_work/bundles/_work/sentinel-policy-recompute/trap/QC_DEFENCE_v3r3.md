# QC defence, sentinel-policy-recompute (Harden P9 v2 r1, QC v1 fixes P12 r1)

Each entry: rule id, live rule quoted (Input_Bundle_QC at harness HEAD 71a653b2), why the bundle
passes, fallback (QC_FIX_PLAYBOOK row and the DO fix that keeps the trap).

## IN-13 (tier sentence removed from instruction.md)
- Rule (01_Instruction_QC.md:43): "Internal consistency: the instruction must not contradict
  itself... constraints that jointly make the task impossible... circular dependencies... are
  all fails. Name both sentences..."
- History: QC v1 (v1.md:310) flagged "documented boundary operators" because no shipped file
  documented the tier key; the fix put "use the role level as the tier index without shifting
  it" into instruction.md.
- Why it passes now: the tier-key rule is written into the tier data before the sentence was
  deleted: `environment/data/threshold_tier_curve.parquet` schema metadata key `tier` = "the
  role_level of the resolved principal in principal_role_index.yaml", and
  `environment/data/convergence_spec.txt:6` "base_threshold = base_threshold of the
  threshold_tier_curve.parquet row whose tier equals the role_level of the resolved
  principal". The instruction no longer mentions a tier or boundary operator, so it has no
  sentence pointing at an undocumented rule and nothing to contradict.
- Fallback: playbook IN-15 row; DO state the rule once as a bare property in the governing
  file (already done in two places). NEVER put the sentence back into the instruction.

## IN-15 (every graded rule stated)
- Rule (01:45): "Every graded rule of engagement is stated somewhere the agent can read it...
  the instruction itself, or a specification or rules file the instruction points the agent
  to."
- Why it passes: instruction.md:5 points to the reference files ("Each rule that binds a value
  is stated in the reference file that holds the data it governs"). Rule locations:
  allowance consumption `override_deltas.json` conventions line 9 (who consumes, order, cut);
  allowance values `quota_limits.cfg:6-8`; rev unit `override_deltas.json:6`; ranges line 7;
  selection `override_precedence.conf:2-5`; control meaning line 11; per-term risk rounding
  `risk_weight_rounding.txt:1-3`; clamp order `clamp_rules.txt:2-4`; effective version
  `policy_version_map.json` key `selection`; tier key as above; trace fields
  `output_field_spec.txt:16`; resolve output docs `output_field_spec.txt:4`.
- Fallback: playbook IN-15; DO add the missing sentence once, neutrally, in the governing file.

## IN-16 (no graded ambiguity), master condition 1
- Rule (01:46): "No significant ambiguity in anything that is graded... must show all three
  parts".
- Why it passes: the allowance sentence names all three parts: which rows consume (rows that
  pass selection), in what order (ascending seq across all rows of the tenant whichever
  principal they name), and the effect (a row passing after the allowance is used up is not
  applied). It is not left to the oracle. Version match (P12 r1, QC v1 G01-2):
  `override_precedence.conf:4` now says the override row and the window containing the
  effective instant both carry the effective version; solve.py rejects a row whose own
  version differs (`row-version-`), oracle bytes unchanged on shipped and hidden-a/b/c.
- Fallback: playbook IN-16 REBUT with the quoted sentence; if still flagged, DO tighten the
  same sentence in the ledger header (no example).

## AL-27 / TS-19 (hidden inputs inside stated bounds), master condition 2
- Rules (05:27) "a rule only counts as graded when the test's input actually constructs the
  situation where the rule matters"; (03:50) "Every graded behaviour must be learnable...
  every promise made to the agent must be graded by something".
- Why it passes: stated ranges (`override_deltas.json:7`) are timeout_ms_delta -5 to 5 on
  rev 1 and -900 to 900 on rev 2, max_records_delta -60 to 60, retry 0 to 3, risk 0 to 20;
  allowance 1 to 6 (`quota_limits.cfg:6`). Hidden rows: rev 1 values 5, -4, -3, 2, 1, 0, 3, -1;
  rev 2 values 40, 500, 75, 60, -60, 4, -90, 300, 90, 50, 30; mr -40..30; retry 0..3; risk
  0..11; allowance 2, 3, 4. Every row sits inside the ranges. Each graded rule has a hidden
  trigger: allowance cut by another principal (A, B, C, mutation-allowance), rev 2 below 100
  (A, B, C), rev 1 awkward values (A, B, C), per-term rounding separating (A, B, C,
  mutation-risk), control mismatch (B, corrupt t-f003), half-open boundary (WIN-PRE rows),
  window version (WIN-AUTH-V099 rows a7, c5), row version (P12 r2, QC v2 AL-27: hidden-a
  `OV-K042-a8` carries row version v099 inside the v100 window WIN-AUTH, after a1 and before the
  allowance is used up; a window-version-only reading applies it, cuts a5 and fails four
  hidden checks, 20/31). HIDDEN_HEADS rows carry an explicit row version.
  The shipped data never contradicts the rev rule: shipped rev 2 values are all >= 100 in
  magnitude and rev 1 rows are in seconds as stated (W5).
- Rerun check (P12 r2, QC v2 TS-26, Ayush approved): `hidden_resolve_rerun_is_canonical_and_byte_identical`
  builds one hidden-a corpus directory, runs the delivered resolve twice on it into two fresh
  out dirs, and asserts byte identity and canonical form of every document plus one assert
  that the hidden-a policy_resolved.json differs from the shipped corpus reference policy.
  It no longer compares to the hidden-a reference (that was paid by the hidden checks). A
  constant resolve that replays the shipped policy earns 0.
- Fallback: playbook AL-27 / TS-19; DO add or move hidden rows inside the stated bounds.

## AL-28 (penalty stacking)
- Rule (05:28): "Group the negatives by triggering action, ACROSS both layers... combined
  penalty above 5 is stacked".
- Why it passes: hardcoding (tests -5), forged transcript (tests -3), network or secret
  material in artifacts (tests -3), config.json produced from a resolve run on a copied and
  edited corpus (judge R3 -3, P12 v3 r3 QC v3 JD-11), undeclared /app/out file (judge R4 -3),
  a `set` config value that differs from every value a repaired resolve run printed (judge R8
  -5), false check claim (judge R9 -5). Seven distinct acts, each group at most 5. R3 and R8
  are disjoint: an edited-copy resolve value was printed by a repaired resolve run, so R8
  stands down for that act. R8 differs from the transcript negative (transcript `set` values vs config.json
  bytes) and from the hardcoding negative (literals in cli.py/schema.json). No negative grades a lever reading.
- Fallback: playbook AL-28; DO keep each act in one layer.

## TS-13 / TS-26 (one property, no double payment)
- Why it passes: each hidden test reads one document (policy_resolved.json,
  threshold_curve.json, dependency_trace.json) and asserts it whole; the two mutation tests
  read one document each on mutated shipped inputs; validate and canonical rerun read other
  observables. Shipped artifacts are one merged w1 check.
- QC v2 M1 TS-13 / M2 TS-20 (P12 r2): KEEP, same ruling as below (Ayush option a, 23 Oct
  19:45). QC v2 W7 TS-26 (rebuild check feeds the delivered policy into init/set): KEEP; the
  dependence is a natural cascade (LEVER_RULES G1); isolating it with the reference policy
  would hand 5 points to a wrong resolve.
- QC v1 G03-1/G03-3 (TS-20/TS-13 on the merged shipped check) are PAUSED in P12 r1: every
  legal split (weights 3,1,1,1,1,1 and all 1) failed trap survival (reflex 0.2895 / 0.2500
  > 0.20; controls lever ratio 0.816 / 0.861 < 0.90) and the shipped-only G3 cap (<= 5%).
  The config property is graded at 5 on hidden data by
  `hidden_config_document_rebuilt_by_cli_matches`. RULED (Ayush, 23 Oct 19:45, option a):
  keep the merged w1 shipped check and defend it. The core config outcome is graded at w5
  on three hidden corpora through the delivered init/set; the shipped check grades only the
  presentation of the one shipped instance. Splitting it hands the reflex agent shipped
  points (measured 0.25-0.29 > 0.20) and breaks the shipped-only cap, i.e. makes the task
  easier. If QC re-flags TS-20/TS-13, rebut with these numbers; do not split.
- Fallback: playbook TS-26 narrow wording; TS-13 split.
- P12 v3 r3 (QC v3 F1 TS-26, M1 TS-13; master directions, Ayush 24 Oct "split as directed"):
  the rebuild check is now `cli_init_and_set_rebuild_config_from_authoritative_values` (w3):
  init/set are fed the authoritative reference values, so it grades coercion, canonical
  writing and delivered-config provenance only; resolve values are paid once by the hidden
  policy check (m2 lost 23 of 31 before, 18 of 33 after: 10 to 5 inside the two checks).
  The merged shipped check is split into five w1 per-artifact checks (config + profiles,
  report, validation report, summary, tool archive). Measured cost: v0 agent program 5/31
  to 12/33 (trap v0 condition FAIL, accepted); every lever keeps 0.939 of its loss.

## TS-20 (weights)
- Weights use only the kit set {5, 3, 1, -3, -5}: three hidden whole-document checks 5; the init/set rebuild, mutations and validate 3; the canonical rerun and the five per-artifact shipped checks 1 (shipped presentation; core values are paid on hidden corpora). Judge R7 3 (reproduced wrong value, P12 v3 r3); judge R10 +3 code quality (P12 v3 r3 P1).

## TS-30 / H6 (file modes)
- Delivered tool.zip is extracted by the test into its own temp dir with dirs 0755 and files
  0644 (`_grant_read`), and runs as nobody via setpriv with `sys.executable -I`; out dirs 0o1777;
  leftovers killed by process group and by nobody uid; runs serialised under a lock. The
  owner-only oracle and chmod 600 runs are in the Phase 3 Docker block.
- Fallback: playbook TS-30; DO stage copies readable by the grader user.

## K8 / TS-S11
- `tests/Dockerfile:5` `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`.

## TS-S10
- `tests/reward.toml` test_output = 0.5/33 = 0.015151515151515152, judge = 0.5/37 =
  0.013513513513513514 (P12 v3 r3: two tests added by the split, R10 replaced by a +3
  code-quality criterion).

## JD-7 (oracle meets every criterion)
- solve.py runs the shipped tool once before repair (R6), then runs a scratch copy of the
  shipped computation and prints each wrong value next to the authoritative one before
  repair_cli (R7, solve.py:516-537), repairs cli.py computation, runs
  repaired resolve (R1) and init/set/validate for config and profiles (R2, R11), writes only
  the seven artifacts (R4), never writes under /app/data (R3: the self check copies the data
  to a temp dir), sets every config value from `json.loads` of the repaired resolve stdout
  (R8, solve.py `str(resolved[key])`), leaves a cli.py with named functions and no except
  clause (R10), solve.sh echoes the seven absolute artifact paths (R5), and
  `self_check_ledger()` builds an own ledger covering R12 to R15 and compares printed values
  with hand-computed ones, exiting on mismatch (R9 avoided).
- Fallback: playbook JD-7; DO fix oracle and TRUTH, never the criterion.

## JD-15 / JD-18 (conduct labelling, one code-quality criterion)
- R12 to R15 are conduct ("The agent constructs its own ... and checks ..."), type agent
  behavior; R10 is the single code-quality criterion, +3 since P12 v3 r3 (precheck J4,
  emberforge QC v9 wording); the old -1 except-clause criterion is deleted (same act as the
  error-handling part of R10). P12 r1 (QC v1 G04-1/G04-2/
  G04-4): R3, R7, R8 are type "agent behavior"; R7 names one observable (a printed wrong value
  of the shipped computation named before the code change, P12 v3 r3 QC v3 JD-9); R3 and R8 are reachable cheats
  of this task (no network, so the old package and outside-solution negatives were residue).
  R4 kept (Ayush approved).
- Fallback: playbook JD-15/JD-16 relabel; JD-18.

## W1 / leak retirement
- instruction.md no longer lists any trap; reconciliation_rules.conf trap keys, the clamp
  warning, the rounding worked example, and self-describing labels are removed (XREF retired strings,
  xref_check 0 findings). Each removed rule is still stated once in the governing file.

## DS-27 / DS-22 / DS-20 (P12 r1, QC v1 G02-1/G02-2/G02-3)
- TRUTH.md carries no production narrative (history-word grep: remaining hits are ordering
  words, a Python fact and data identifiers); solve.py line count recomputed with wc -l after
  the last solve.py edit; `client_version_ignored` is the constant true the field spec
  states, oracle bytes unchanged.

## IN-L2 (P12 r1, QC v1 G01-1)
- instruction.md:1 run-on sentence split in two; no other instruction change.
- P12 r2 (QC v2 M3): instruction.md:7 report sentence split in three; names
  `/app/out/validation_report.json` once; no fact added or removed.

## IN-2 (P12 r2, QC v2 W10)
- instruction.md:5 states the requirement (the repaired `resolve` works with the README options
  on any reference corpus of the same layout and stated ranges, every document matches that
  corpus's authoritative policy in full); it no longer describes grading. README documents
  `resolve --data-dir <dir> --out <out-dir>`.

## JD-5 (P12 r2, QC v2 M4)
- R5 names one observable: the response names the path of each of the seven delivered artifacts.

## Step 11 (P12 r2, QC v2 W11)
- `output_field_spec.txt:16` resolution_order is graded inside
  `hidden_dependency_trace_document_matches`: basenames boot_manifest.toml, bundle_ledger.jsonc,
  principal_role_index.yaml, override_deltas.json appear in that relative order (others allowed).

## DS-27 (P12 r2, QC v2 W12)
- TRUTH.md fault heading reads "the shipped corpus does not separate these faults; the fresh
  corpora do"; no production narrative.

## X1 (QC v2 W13)
- Binary-skip warning on tool.zip / parquet; KEEP, no text file carries a dash.

## P2 trap-file name (P12 v3 r3, precheck)
- environment/data/decoy_alias_table.jsonc renamed principal_alias_table.jsonc (content and the
  in-file notice line kept, CL-6); graded outputs byte-identical, input_count 56 unchanged.

## AL-27 (P12 v3 r3)
- WORK/RULE_COVERAGE.md: 14 contract rules, each with a mutant failing at least one test; the
  window-version rule (m14) was uncovered and is now constructed by hidden-c row OV-K042-c0.
