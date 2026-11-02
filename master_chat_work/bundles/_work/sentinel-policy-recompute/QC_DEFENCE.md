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
  (harden r2) region allowance values and key `quota_limits.cfg:6-9` (region of a tenant from
  `tenant_catalog.xml`); admit count and draw order `override_precedence.conf:5-6` (who draws,
  order, both counters, refusal draws neither); timeout_ms_delta unit by version cutover
  `units_reference.txt:6-7`; rev meaning and value ranges `override_deltas.json` conventions
  lines 5-7; selection `override_precedence.conf:2-4`; control meaning line 11; per-term risk rounding
  `risk_weight_rounding.txt:1-3`; clamp order `clamp_rules.txt:2-4`; effective version
  `policy_version_map.json` key `selection`; tier key as above; trace fields
  `output_field_spec.txt:16`; resolve output docs `output_field_spec.txt:4`.
- Fallback: playbook IN-15; DO add the missing sentence once, neutrally, in the governing file.

## IN-16 (no graded ambiguity), master condition 1
- Rule (01:46): "No significant ambiguity in anything that is graded... must show all three
  parts".
- Why it passes (harden r2): the draw_order sentence `override_precedence.conf:6` names all
  three parts: which rows draw (rows that pass selection), in what order (ascending seq across
  all rows of override_deltas.json), and the effect (applied only when both the region
  override_allowance and the window admit count have a unit left; an applied row uses one of
  each; a row refused by either draws neither). The unit rule `units_reference.txt:7` names
  the field, the comparison (version effective_from before the cutover) and both units. Version match (P12 r1, QC v1 G01-2):
  `override_precedence.conf:4` now says the override row and the window containing the
  effective instant both carry the effective version; solve.py rejects a row whose own
  version differs (`row-version-`), oracle bytes unchanged on shipped and hidden-a/b/c.
- Fallback: playbook IN-16 REBUT with the quoted sentence; if still flagged, DO tighten the
  same sentence in the ledger header (no example).

## AL-27 / TS-19 (hidden inputs inside stated bounds), master condition 2
- Rules (05:27) "a rule only counts as graded when the test's input actually constructs the
  situation where the rule matters"; (03:50) "Every graded behaviour must be learnable...
  every promise made to the agent must be graded by something".
- Harden r2: stated ranges (`override_deltas.json` conventions line 7) are max_records_delta
  -60 to 60, retry 0 to 3, risk 0 to 20, timeout_ms_delta -900 to 900; allowance 1 to 6
  (`quota_limits.cfg:6`). Every hidden row of n1-a..n3-b and hidden-a..d sits inside them;
  each new rule has its own hidden trigger (see section Harden round 2 below).
- Superseded P12 text: stated ranges were timeout_ms_delta -5 to 5 on
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
- Harden r2: 12 positive checks, P = 44: three `_hard` families 5 each, three coupling
  whole-document checks 5 each, init/set rebuild 3, two mutations 3, validate 3, rerun 1, one
  merged shipped check 1 (2.3%, master ruling 5). Negatives -5, -3, -3.
- Superseded P12 text: weights use only the kit set {5, 3, 1, -3, -5}: three hidden whole-document checks 5; the init/set rebuild, mutations and validate 3; the canonical rerun and the five per-artifact shipped checks 1 (shipped presentation; core values are paid on hidden corpora). Judge R7 3 (reproduced wrong value, P12 v3 r3); judge R10 +3 code quality (P12 v3 r3 P1).

## TS-30 / H6 (file modes)
- Delivered tool.zip is extracted by the test into its own temp dir with dirs 0755 and files
  0644 (`_grant_read`), and runs as nobody via setpriv with `sys.executable -I`; out dirs 0o1777;
  leftovers killed by process group and by nobody uid; runs serialised under a lock. The
  owner-only oracle and chmod 600 runs are in the Phase 3 Docker block.
- Fallback: playbook TS-30; DO stage copies readable by the grader user.

## K8 / TS-S11
- `tests/Dockerfile:5` `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`.

## TS-S10
- `tests/reward.toml` test_output = 0.5/44 = 0.011363636363636364, judge = 0.5/37 =
  0.013513513513513514 (harden r2: P = 44).

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

## Harden round 2 (24 Oct 2026, master rulings 1-9 on DIAGNOSIS.md)
- Levers: N1 region override allowance (`quota_limits.cfg:7-9`, keyed by region;
  `tenant_catalog.xml` gives each tenant its region; `tenant_multiplier_table.xlsx` region equals
  the catalog in every corpus, ruling 4), N2 timeout unit by version cutover
  (`units_reference.txt:6-7`; L1 control is its amplifier), N3 window admit count
  (`effective_windows.xml` attribute `admit`; `override_precedence.conf:5-6`). L7 and L1 stay as
  graded noise / amplifier. See LEVERS.md and COST_TABLE.md.
- W1 (ruling 2): `rev` has one neutral meaning (`override_deltas.json` conventions line 5,
  "rev: the revision of the override row record, 1 or 2."); no sentence ties rev to a unit or
  says the unit is not taken from rev; shipped rev regenerated by gen_data.py so rev 1 iff the
  row's version is before the cutover (shipped data agrees with the rule, Never 11).
- Ruling 3: draw_order keeps "a row refused by either draws neither"; hidden-d grades both
  directions (OV-F003-d2 refused by the r-03 allowance while WIN-AUTH has admits; OV-K042-d5
  refused by WIN-AUTH admits while r-north has a unit); each misreading drops to 29/44.
- Ruling 5 / G3: one merged shipped check w1 (1/44 = 2.3%, under 5%); the five per-artifact
  checks of P12 v3 r3 are folded back into `shipped_artifacts_carry_policy_runs_and_archive` by
  master ruling, which supersedes the P12 v3 r3 split. Each `_hard` family separates only its
  own lever (single_lever.py: N1 readings fail only region_hard among the families, N2 only
  cutover_hard, N3 only admit_hard).
- Ruling 6 / JD: R11 is the observable outcome "produced by running its repaired
  sentinel-ctl" (no init/set demand beyond the README); R12 N2, R13 N1, R14 N3 are conduct w3,
  shown by solve.sh output `check R12 ok`..`check R14 ok` (solve.py self_check_ledger).
- Ruling 7 / G10: alone cost N1 52.3%, N2 34.1%, N3 52.3% of test points; all-but-one overall
  at the measured judge 51.35% is 49.5 / 58.6 / 49.5 (< 70). Ruling 8: reflex (probe-1 agent
  program, region lookup adapted) 0.1591 delivered, 0.1818 rebuilt (<= 0.20).
- AL-27: RULE_COVERAGE.md 16 rules, 21 mutants, each fails >= 1 test.


## Harden round 3 (25 Oct 2026, master GO on DIAGNOSIS.md): N4 timeout pool

- Rule ids at risk: IN-15 (rule stated?), IN-16 (two readings of the second share), AL-27 (every branch triggered), CL-4 (one wrong fact), TS-13/TS-26 (new checks), JD-7/JD-8 (R16), DS-22 (TRUTH), Never 11 (shipped answer).
- Live rule, quoted (`override_precedence.conf:7`): "timeout_pool = the applied rows of one window whose timeout delta in milliseconds is above zero share the timeout_pool of that window in effective_windows.xml, a whole number of milliseconds from 600 to 1500: when their summed delta is at or below the pool, each adds its own delta; otherwise each adds floor(pool * its delta / summed delta). A row whose added delta is then below 100 adds none, and every millisecond of the pool is shared again, floor(pool * its delta / summed delta of the rows whose added delta was 100 or more), across only those rows. An applied row whose delta is zero or below adds its own delta". Pointer `override_deltas.json:10`; values: `timeout_pool` attribute of every window in `effective_windows.xml`.
- Why it passes: IN-15 - stated once as a bare property in the file that holds precedence rules, in that file's key = value vocabulary; the pool value sits on the window record it governs. IN-16 - the second share names its amount ("every millisecond of the pool"), its formula and its population ("across only those rows"); it does not tell the agent to test the fits branch again, so the one reading is the one written (caldermoor F2 wording; no "by the same rule"). AL-27 - RULE_COVERAGE m19-m24 each fail 4 checks (0.692). CL-4 - every N4 reading costs 16/52 (30.8%), not more: the pool moves only timeout_ms (max_records, retry, contribution unaffected), and only the four checks whose corpora bind the pool see it. TS-13/TS-26 - hidden_timeout_pool_hard grades the policy and trace documents on pool-a/pool-b (one property: the pooled timeout), mutation_pool_cut_reshares_timeout grades one changed value (pool 960 -> 900) on its own corpus. JD-7 - solve.py:695 `check R16 ok`. JD-8 - R16 grades the agent's own ledger check in the trajectory; no test reads the trajectory. Never 11 - shipped WIN-AUTH pool 1200 holds 250 ms + K118 delta, so shipped 285/3/2250/51 is unchanged under every reading.
- Safe fallback if QC still finds IN-16: playbook row IN-16, DO for this lever = one settling clause in `override_precedence.conf:7`, written for the general case, e.g. append "; the second share is not checked against the pool again" - never a worked figure, never in instruction.md. If QC finds CL-4: row CL-4, DO = keep the pool non-binding in every corpus that is not one of pool-a, pool-b, hidden-c, hidden-d, mutation-pool, mutation-risk (generator assert), and report one-fact-wrong per reading (all 30.8%).


## Test-hardening round t1 (26 Oct 2026, board b7e15f9): five quiet rules Q1-Q5

Common to all five. Rule ids at risk: IN-15 (rule stated?), IN-16 (one reading?), IN-17 (announcement of a discovery?), AL-1 (shipped data agrees with the rule), AL-27 (every stated rule triggered by hidden rows), CL-4 (one wrong fact costs too much), Never 6/8/11. Each rule is one sentence plus one toy example on invented values (K900/K905, OV-Q7, R1-R3, base 3000) that appear in no shipped or hidden file. The five sentences sit apart, each in the file that owns its family; none is in instruction.md, none uses "note that", "unlike", "even when", or says the shipped files lack the case. Shipped data shows none of the new keys or fields, so shipped answers are 285 / 3 / 2250 / 51 under every reading (AL-1, Never 11). Each hidden corpus built for a rule fires it at least twice (BRANCH_FIRE.md; AL-27); each rule wrong alone costs 7/75 = 9.3% (CL-4: under 12%, one owned test plus the rare-pair test); the old corpora fire none, so no old check moves.

### Q1 running timeout floor
- Live rule, quoted (`units_reference.txt:8-9`): "timeout floor: the timeout starts at the base in milliseconds and takes the amount each applied override adds, one at a time in ascending seq; whenever the running value falls below 1000 it is raised to 1000 before the next amount" / "timeout floor example: a base of 3000 with added amounts -900, -900, -800 and +500 runs 2100, 1200, 1000, 1500".
- Why it passes: IN-15 stated in the file that owns the timeout unit chain, in its `key: value` vocabulary, right after the conversion lines. IN-16 the order (ascending seq), the moment (before the next amount) and the value (1000) are all written; the example separates the running reading from both the sum and one final clamp (sum 900, final clamp 1000, running 1500). IN-17 it states a property of the computation, not a discovery about shipped rows. AL-27 q1-a/q1-b clip 3 and 2 times; combo pairs P3, P6.
- Safe fallback: if QC calls the example a near-answer (Never 11), keep the sentence and drop line 9; if IN-16, append "; the amount added is the timeout_pool amount" to line 8.

### Q2 reissued override_id
- Live rule, quoted (`override_deltas.json:6`, conventions item 3): "An override_id is stored on more than one row when the override was reissued; only the row with the highest seq is that override, and its earlier rows pass no selection and draw no unit. For example, OV-Q7 stored at seq 40 as active and at seq 52 as superseded is neither applied nor drawn."
- Why it passes: IN-15 stated next to "seq values are unique" in the file whose rows it governs. IN-16 controls: the existing control sentence (item 11, "over every stored row of that tenant, whatever its status, window, version or allowance") keeps counting earlier rows; EVIDENCE_MAP.md shows the stored controls of q2-a, q2-b, combo-a and combo-b reconcile only under the every-stored-row reading, so ledger_controls stays `ok` and the dedupe affects the draw only. AL-27 q2-a 2, q2-b 3 fires (earlier active row in an open window); combo P2, P5, P6, P7.
- Safe fallback: if QC reads the controls as deduped (IN-16), append "; controls still count every stored row" to item 3.

### Q3 principal alias for part of a window
- Live rule, quoted (`override_deltas.json:4`, conventions item 1): "param_key_aliases, when present at the top level, lists entries with alias, principal, start and end; while effective_instant lies in the half-open span from start to end, a row whose param_key is the alias is an override of that principal, and at any other instant it is an override of no principal; either way the row draws like any other row. For example, with alias K900, principal K905, start 100 and end 200, ..."
- Why it passes: IN-15 the key name, its four fields and their meaning are named in the file that holds the key (QL 26 Oct Q3). IN-16 half-open span stated with both edges in the example; "draws like any other row" settles units for out-of-span rows. Alias names in hidden corpora avoid every shipped param_key and principal_alias_table.jsonc (K042, K118), so the retired-alias trap and Q3 never touch. AL-27 q3-a 4, q3-b 3; combo P1-P4.
- Safe fallback: if IN-17 flags "when present", rewrite as "param_key_aliases is an optional top-level list of entries ...".

### Q4 requires order (chosen over the retry cap, master go note 2)
- Live rule, quoted (`override_precedence.conf:7`): "requires = a row with a requires field is applied only when the override it names was applied earlier in the same draw, at a lower seq; otherwise the row is refused and draws neither unit; for example, with R1 at seq 10 requiring R2, R2 at seq 12 and R3 at seq 14 requiring R2, R2 and R3 are applied and R1 is refused". Field named in `override_deltas.json:11` ("requires is an optional row field naming an override_id").
- Why it passes: IN-15 stated among the draw rules it extends, field named in the row file. IN-16 the example separates the order-free reading (R1 refused although R2 is applied). Refusal draws neither unit, matching draw_order. AL-27 q4-a, q4-b 2 refusals each incl. a named row applied later; combo P1, P5.
- Safe fallback: if QC flags a dependency on a row of another tenant as unclear, append "; the named override may belong to any tenant" to line 7.

### Q5 carried clause of a superseded row
- Live rule, quoted (`override_deltas.json:13`, conventions item 10): "A superseded row may have a carry field naming max_records_delta or risk_delta. When the window of such a row contains effective_instant and the row and the window both carry the effective version, that one delta is added for the row's principal in clamp_rules.txt or risk_weight_rounding.txt the way the delta of an applied override is added, while the row itself is not applied, draws no unit and is not listed among the applied overrides. ..."
- Why it passes: IN-15 stated right after the applied-row sentence it qualifies, naming both target files. IN-16 EVIDENCE_MAP.md Q5 table: carried rows are absent from applied_overrides, draw no unit (the r-north and admit counts reconcile only that way) and enter only the named sum; the half-open window and version conditions reuse the match wording. Carry appears only on the highest-seq row of an id and never with requires (generator check_bounds). AL-27 q5-a, q5-b 2 carried rows each plus one carry row outside its window; combo P4, P7.
- Safe fallback: if QC calls clamp interplay unclear, append "; a carried max_records_delta joins after_delta before scaling" to item 10.

## t1 weights and instruction wording (26 Oct 2026)
- Rule ids at risk: TS-20 / tests_qc W2 (weights in {5, 3, 1, -3, -5}), IN-17 (instruction phrases).
- The five owned quiet-rule checks weigh 5 (first draft 4 failed W2); the rare-pair check 3; P = 80, reward test_output 0.5/80. Each primary misreading alone costs 8/80 = 10% (measured), all-but-one 90.0, first write 65.0.
- instruction.md: dropped "Several of those files are superseded or retired." and "and never a superseded or retired value", and "across two runs" became "across runs" (precheck IN17-PHRASE). The binding rules sit in the data files; no judge criterion or test reads those phrases.
- Safe fallback: if a reviewer wants the superseded wording back, the bundle ledger and migration notice still state which bundle is active, so no rule is lost.
- instruction.md:7 "except the seven artifacts named here" became "except the artifacts named here" (precheck IN17-PHRASE; the artifacts are each named in the same paragraph).

## Test-hardening round t2 (27 Oct 2026, board 4a82a12): U unique divisor fit, D1 resets, D2 reinstated chains

Common to all three. Rule ids at risk: IN-15, IN-16, IN-17, AL-1, AL-27, CL-4, TS-13/TS-26, TS-19, Never 6/8/11. Shipped data carries no `reports` key, no reset, no withdrawn or reinstated row, so shipped answers stay 285 / 3 / 2250 / 51 under every reading (AL-1, Never 11; BRANCH_FIRE 0). Every key, field and value form a test reads is named in the contract (QL Q3): `reports`, `kind` curve/reset, `seq`, `role`, `converged`, statuses `withdrawn`/`reinstated`, null `converged`/`risk_threshold`. No sentence says "note", names a wrong reading or lists cases (IN-17, W1). Each owned check costs 8.2% alone (CL-4 under 12%; instruction.md states whole-document exactness, FC:491). Each corpus family fires its own rule >= 2 times and none of Q1-Q5 (G1a ownership, generator `accepted()`); combo2 fires all of them (T4).

### U divisor fixed by the reports
- Live rule, quoted (`convergence_spec.txt:7`): "iteration_divisor = fixed by the curve reports in override_deltas.json: it is the divisor under which every standing curve report, its curve computed for the role it names (that role's param_key, tenant and role_level in principal_role_index.yaml) by the rules that give the resolved principal its curve, converges to its reported converged value; with no standing curve report it is iteration_divisor in reconciliation_rules.conf. When the reports fix no single divisor, the threshold is unresolved: iterations holds only the seed value, and converged and risk_threshold are null". Range `reconciliation_rules.conf:3` "# the divisor of iteration_rule in convergence_spec.txt is a whole number from 6 to 14". Null forms `output_field_spec.txt:14-15`.
- Why it passes: IN-15 stated in the file that owns iteration_rule; the candidate space is closed (6..14) where the divisor is defined (master go 1). IN-16 one reading: "every standing curve report" and "fix no single divisor" give the verdict for 0 and 2+ fits word for word; UNIQUENESS.md lists the fit set per corpus; 0-fit corpora are never generated. IN-17 no discovery is announced; no "try each" or count words (S3 lesson). AL-27 utie (tie), udecoy (decoy, first report alone fits 13 and 14), combo2-a/b.
- Safe fallback: if QC calls the recompute "for the role" unclear, append to line 7 "(its risk terms are its risk_weight_base and the risk_delta of every row applied or carried for it in the same draw)"; never a worked figure.

### D1 reset withdraws earlier reports
- Live rule, quoted (`override_deltas.json` conventions, file line 15): "reports, when present at the top level, lists curve reports, each with kind curve, seq, role (a role key of principal_role_index.yaml) and converged (a whole number), and resets, each with kind reset and seq. A reset withdraws every curve report at a lower seq; a curve report that no reset withdraws stands. For example, with curve reports at seq 4 and 9 and a reset at seq 6, only the curve report at seq 9 stands." Order: line 5 "seq values are unique across the rows and the reports".
- Why it passes: IN-15/16 the order is the existing seq order (no new process directive, master go 3); the toy example uses invented seqs. AL-27 d1-a/b two resets each, each withdrawn report alone changes the fit (all-curves fit = none). W6 one toy example.
- Safe fallback: if QC asks whether a reset withdraws reports reported later, the sentence already says "at a lower seq"; KEEP quoting 01:46.

### D2 reinstated rows
- Live rule, quoted (file line 14): "status is active, superseded, withdrawn or reinstated. A withdrawn row passes no selection. A reinstated row passes selection the way an active row does, but adds, in place of its own deltas, the deltas of the last active row of its override_id at a lower seq; when there is no such row it passes no selection. For example, OV-Z1 stored at seq 3 as active with max_records_delta 7, at seq 5 as active with max_records_delta 9, at seq 8 as withdrawn and at seq 12 as reinstated with max_records_delta 2 adds 9." Selection `override_precedence.conf:2` "select = active or reinstated status only".
- Why it passes: IN-15 stated beside the row fields it governs; IN-16 "last ... at a lower seq" fixes the source row; the no-source case has a verdict and is never generated (check_bounds). Reissue (Q2) still applies: only the highest-seq row of an id is that override, so a chain ending in withdrawn or superseded is not drawn. Controls still count every stored row (line 17 unchanged). AL-27 d2-a/b 3 reinstated rows each, chains >= 3 rows.
- Safe fallback: if QC flags "deltas" as unclear, append "(max_records_delta, retry_limit_delta, risk_delta and timeout_ms_delta)" after "the deltas".

### Judge
- Kept exactly (d0f1870). No probe added: solve.sh self-check runs on shipped copies, where none of U/D1/D2 fires, so it could not print a witness (QL Q1).

## Test-hardening round t3 (27 Oct 2026, board 3022cae): R cheapest ledger repair

### R spare rows, repair, cheapest total, tie, null
- Live rule, quoted (`override_deltas.json` conventions[14], file line 17): "A stored row is spare when its status is withdrawn, or it is superseded and has no carry field, or a row at a higher seq has the same override_id; the last active row at a lower seq of an override_id whose highest-seq row is reinstated is never spare. A repair of a tenant whose ledger_controls is mismatch is a set of that tenant's spare rows whose removal leaves the tenant's stored row count and both sums equal to its controls entry (an empty set counts). Of all repairs, the tenant takes the one whose rows have the smallest total of absolute timeout_ms_delta in milliseconds; equal totals go to the set whose seq values, in ascending order, come first compared one by one. A tenant with no repair has null." plus one toy example on invented seqs 2/4/6/7/9. Shape `output_field_spec.txt:4` (resolve writes ledger_repair.json) and `:17` "ledger_repair = object keyed by every tenant whose ledger_controls is \"mismatch\"; the value is the ascending list of the seq of every row in that tenant's repair as defined in override_deltas.json, or null". Limit `instruction.md:5` "Each `resolve` run must finish within 60 seconds." Milliseconds come from the existing cutover rule (`units_reference.txt:6-7`), the sums from conventions[13] (unchanged).
- Why it passes: IN-15 stated once, in the file whose rows and controls it governs, beside the controls definition; the output key set, value form (ascending seq list or null) and the time limit are all named (QL Q3). IN-16 one reading: objective (smallest total absolute ms), constraints (spare rows only, row count and both sums equal), tie-break (ascending seq lists compared one by one) and verdict (no repair -> null; empty set counts) are each one plain clause; EVIDENCE_MAP lists the no-repair, tie, zero-row and stored-above-recomputed cases. IN-17 no method words (no search, table, prune, order of visit) and no trap announcement; the toy example shows only the definition. AL-1 the shipped instance is small (t-atlas, two spare rows, repair [3, 6]) and printed by solve.sh. AL-27 each hidden family has two corpora with two repaired tenants and one null tenant; rtie carries equal-total optima, runit pre-cutover spare rows, rspare cheap carry/reissue/reinstated-source twins (BRANCH_FIRE t3). CL-4 the value ranges are the stated ones (conventions[6]); no stated bound on spare-row count or repair size. Hidden repairs use 59-71 spare rows per tenant; the reference resolves each corpus in <= 0.25 s in Docker (COST_TABLE t3), far under the stated 60 s.
- Safe fallback: if QC calls "both sums" unclear, replace with "its max_records_delta sum and its timeout_ms_delta sum in milliseconds"; if QC asks for the size of the hidden ledgers, answer that the stated value ranges are the only bound (instruction para 3) and add nothing. The shipped tool.zip README (the broken tool's own text, lines 11-13) still lists three resolve documents; output_field_spec.txt:4 fixes the shape of every artifact (instruction para 3). If QC asks, add `ledger_repair.json` to that README line and re-pin tool.zip (common rule 6); not done now so the shipped archive and its pinned sha stay unchanged.

### Fresh state corpora check
- Live rules: the existing Q1-Q5, U, D1, D2 sentences (t1/t2 sections above), unchanged.
- Why it passes: one more whole-document check on seed 3 corpora of the same generated families; no new rule, no new wording; existing checks byte-unchanged (WORK/test_body_before_t3.py diff: additions only).
- Safe fallback: none needed.

### Rare repair pairs check and weights
- Live rules: the R sentence (override_deltas.json:17), unchanged.
- Why it passes: `hidden_rare_repair_pairs_hard` (w3) compares the whole `ledger_repair.json` on rall-a/b, where ties, pre-cutover rows and the spare reading meet on the same tenants; no new rule. All new weights are 5 or 3 (tests_qc W2 set); P = 131, reward.toml test_output 0.5/131.
- Safe fallback: none needed.

### Judge
- Kept exactly. No probe added: solve.sh self-check prints only the shipped repair {"t-atlas": [3, 6]}, which every reading that reads the rule gets right (QL Q1).

## Gate v3.6 harden (217875e, 27 Oct 2026): QC v7 fixes merged and judge band rebuilt
| rule | item | quoted text / location | why it passes | safe fallback |
|---|---|---|---|---|
| CL-2 (v7 finding 1) | old R10 handler criterion | dropped (F1) | the shipped cli.py has 0 handlers, so "every exception handler acts" was vacuous; no replacement carries its 5 points | none needed |
| JD-18 / CL-2 | R12 `r12_cli_names_unreadable_reference_file` w1, state_change, important | "The agent leaves a maintainable /app/tool/cli.py in which a reference file that is unreadable or unparsable stops the run with an error message naming that file." | judges how the code handles errors (04:99 "errors handled rather than swallowed"); FALSE on the unedited shipped cli.py, measured in Docker on Python 3.12: malformed boot_manifest.toml ends `tomllib.TOMLDecodeError: Invalid statement (at line 1, column 1)`, malformed bundle_ledger.jsonc and request_corpus.json end `json.decoder.JSONDecodeError: ...`, none names the file (and the shipped file does not start on 3.12); oracle meets it: CORRECT_CLI `declared_input` solve.py:44-53 wraps every reader, self-check prints `check unreadable input ok` | narrow to "names the file" only |
| J7 label | R12 type | "agent behavior" | judge_qc.py:122-125 allowed set has no code-quality label; JD-18 calls it a conduct criterion under JD-15 and "agent behavior" is the conduct label (vendor v5:35: code quality under "task completion" was a minor). Deviation from the master note ("agent behavior is wrong") recorded in the report | relabel on QC request |
| JD-13 | R12 w1 important; R6-R8 w3 important (F2, v7 finding 5) | judge.toml | judge_qc J13: important needs 1 or 3 | none |
| JD-5 | R10, R11, R12 | one act each: one rerun on one altered copy with its shown value; one code property | "runs ... and shows" are two facets of one run (QC v7 JD-5 line on R1-R5) | split show into its own w1 |
| JD-6 | R12 | /app/tool/cli.py is in task.toml artifacts (task.toml:2); R10, R11 read the trajectory | decidable from declared artifacts and trajectory | none |
| JD-7 | R10, R11, R12 | solve.py self-check prints `check version map rerun ok` (v100 -> v099), `check unit cutover rerun ok` (2250 -> 2857), `check unreadable input ok` | the oracle performs each act; Docker run log /tmp/spr217/oracle1.log | none |
| JD-14 | R10 vs R4/R5; R11 vs R6 | R10 reads the effective version after a version-map edit, R11 the timeout after a cutover edit; R4/R5 read max_records and the threshold; R6 is a separate recomputation with no rerun | distinct observables | none |
| JD-15 | R10, R11 | serve instruction.md:7 "including the resolved param key, tenant, effective version" with policy_version_map.json:2 selection; units_reference.txt:6-7 cutover with instruction.md:5 "every document it writes must match that corpus's authoritative policy in full" | odds-raising conduct at w3 (QC_RULINGS vendor v5:323, QL Q2) | w1 |
| JD-8 | R10-R12 | no test reads the agent's own altered corpora or the cli.py source | trajectory and code-quality judgements, tests read /app/out and reruns | none |
| AL-28 | negatives | R14 -3, R15 -5, R16 -3 unchanged acts; tests negatives unchanged | largest group 5 | none |
| TS-13 (v7 finding 4) | F3 split | `shipped_config_carries_policy_values` w3, `shipped_profiles_carry_policy_deltas` w3; rebuild bytes assert deleted (graded by `cli_init_and_set_rebuild_config_from_authoritative_values` on hidden corpora) | one artifact per check | none |
| TS-20 | F3 halves | shipped checks 3, hidden whole-document checks 5 | core > sub-goal | none |
| TS-23 (v7 finding 6) | 40 checks | tests_qc A3 warn | option A (Ayush decision 3): recorded warn, no merges (F4 not applied); 03:62 | none |
| IN-17 / IN-L2 (v7 finding 2) | instruction.md:7 | "It must also record whether every delivered artifact is present and whether the configuration matches the resolved policy." | names output_field_spec.txt:8-9 fields; announces no discovery; no new rule | previous wording |
| DS-22 (v7 finding 3) | TRUTH.md:52 | `override_precedence.conf:8` | timeout_pool is line 8; all TRUTH counts rewritten (40 checks, 146/-14, 16 criteria 37/-11); sha by truth_sha.py last | none |
| DS-17 | solve.py prints | plain descriptions, no R or J numbers (grep empty) | oracle trajectory carries no criterion ids | none |
| DS-27 | TRUTH.md | no round or lever tags added | | none |
| AL-1, AL-2, AL-27, IN-15, IN-16 | none touched | no new rule, data or hidden corpus | unchanged since v7 PASS | none |

## P12 fix QC v8 (3157183, 28 Oct 2026)
- CL-1 / AL-2 tool-use (QC v8 G05-1, REAL, FIXED): instruction.md:3 "use the repaired tool itself to produce the main configuration `/app/out/config.json` rather than hand-writing it". Checker: test `shipped_config_produced_by_repaired_tool` (w1, tests/test_output.py:1683-1685): the delivered init and set, fed the shipped authoritative values, must write config.json byte for byte (Final_checklist.md:488 "a test where the effect can still be inspected at grade time"). Own check, never folded into `shipped_config_carries_policy_values` (TS-13, G2). Reads the delivered tool and the delivered config bytes, not report.json. The unshipped tool writes a wrong config, so the check is not vacuous. If QC insists on a trajectory criterion instead: keep the test and do not add judged points an a7-like run earns (gate v3.6).
- JD-5 / JD-3 R12 (QC v8 G04-1, REAL, FIXED): "a maintainable" dropped; R12 now "The agent leaves /app/tool/cli.py whose exception handlers stop the run with an error message naming the file when a reference file is unreadable or unparsable." One act, J4 template words (precheck J4 needs one code-quality criterion; dropping only the two words left none). Oracle meets it (solve.py:40-53 `declared_input`), shipped cli.py fails it (malformed JSON traceback names no file).
- DS-22 (QC v8 G02-1, G02-2, REAL, FIXED): TRUTH.md line count, probe list and the Ordered-plan sentence regenerated by script with counts 41 / 147 and sha256 values last.
- TS-23 / A3: 41 checks, KEPT (option A, Ayush 27 Oct; 03_Tests_QC TS-23 warn, no cap).
