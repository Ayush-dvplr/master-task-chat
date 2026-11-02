# DIAGNOSIS: emberforge-vault-settlement, harden round 1 (21 Oct 2026, IST)

Not a PL-generator scaffold: no archetype in `archetypes.md` matches the 12 artifacts, so the validator runs with no `--archetype` and VB 1.12 does not apply (it reports FAIL against the format-recovery fallback). Fingerprints: GEN 163 tracked and QC 12 files unchanged. Scores are tests-only, method (b): the real `test_output.py` under rewardkit 0.2.1 in the exe_copy image. Oracle 1.0, nop 0.0.

## Version check
The run used `.kiro-staged-tasks/emberforge-vault-settlement`. It is byte-identical to BUNDLE except that the harness added `host.docker.internal` to the two `allowed_hosts` lines in `task.toml`. `instruction.txt` equals `instruction.md`. The run graded 34 checks and 12 criteria, which matches `test_output.py` and `judge.toml`. The bundle has not changed since the run. Re-scoring the run's own `settle_vault.py` gives 0.68, the harness figure.

## Levers (full per-check table in `_work/.../LEVERS.md`)
| lever | pts | run | status |
|---|---|---|---|
| STRUCT delivery | 3 | 3 | LEAKED |
| B chain: charge, cap, vault, conservation, roll-ups | 40 | 40 | LEAKED |
| L1 scarcity fixed point (V8) | 5 | 5 | LEAKED |
| L2 draw recovery | 10 | 0 | LEAKED (own reading right, lost only through the L7 cascade) |
| L3 requisition optimum (Q7, Q8) | 10 | 5 | LEAKED (same) |
| L4 dated, transitive identity (I2 to I4) | 10 | 5 | LEAKED (same) |
| L5 forge-day edition for a salvage (E3) | 5 | 5 | LEAKED |
| L6 one salvage per forge (S6) | 5 | 5 | LEAKED |
| L7 every condition is a finding, cap and floor at one forge (N3 x A4 x V4) | 11 | 1 | HELD |
| L8 quiet rules, order, window, scope | 23 | 13 | LEAKED (same) |
| L9 canonical bytes | 3 | 3 | LEAKED |

Locally the run's program differs from the oracle on one record only, `data_quality.json`: 10 STOCK_FLOOR co-findings are missing at closed workshops. All 6 gen failures come from this one gap. Every gen check compares all 11 records, and in `gen_nonapplying_rules` the same gap also skips the cap closure that forge L0902 triggers.

## Judge (all 11 positives passed, 41/41; the R11 negative was avoided)
| id | w | verdict | why it passed |
|---|---|---|---|
| R1 reads only /app/data | 3 | yes | trivially true |
| R2 leaves /app/data intact | 5 | yes | trivially true |
| R3 stdlib imports | 3 | yes | trivially true |
| R4 no network | 3 | yes | trivially true |
| R5 quotes 4 conventions | 5 | yes | genuinely met; the slice makes the draw easy to get |
| R6 states 3 figures | 5 | yes | effort-based: it pays for "one figure each" and never checks the value |
| R7 reads rulebooks first | 3 | yes | effort-based (steps 4-5) |
| R8 draw by search | 5 | yes | effort-based, and it overlaps the gen_draw tests |
| R9 conservation check | 3 | yes | effort-based, and c11 already reads the residuals |
| R10 two runs compared | 3 | yes | effort-based (step 19), and the negative nondeterminism test covers it |
| R11 false claim (-3) | -3 | no | avoided |
| R12 code quality | 3 | yes | genuinely met |

## Leak causes
- Answer key. `calibration_reference_bundle.json` holds the full settled output of the slice under the true draw. It publishes 5 of the slice's 7 non-summary records: `allocation.json`, `data_quality.json` (findings with details, for example `{"entry_id": "L0022", "code": "SALVAGE_ALREADY_CREDITED", "detail": "L0021"}`), `guild_ashen_compact.json`, `reconciliation.json` and `vault_audit.json`. Together with the controls and the example report, it lets the agent fit L3, L5 and L6 exactly. The underivability check confirms it: under the true draw, the reflex reading of each of the three leaves 0 of 840 draws matching the slice (DERIVABLE). Step 8 printed the whole bundle. Step 22 compared record shapes against it (`pub.update(j(D+'/calibration_reference_bundle.json'))`). The bundle is not needed to pin the draw: controls alone leave 21 survivors, controls plus the example report leave exactly 1 (RS-C/half-even/GFS/opening-plus-acquired).
- Isolated rules stated next to their use. The agent's first engine was right everywhere but L7. Step 18 was its first run and already found exactly one draw, with charge 163070, 203 admitted and 32 allocated. L1 is HIDDEN-ONLY on the slice, yet V8 says "Exactly one assignment of indices agrees with the season that assignment produces", and the step-15 code implements `settle_to_fixed_point`. L4 is HIDDEN-ONLY, yet I3 spells out the time dependence. E3 is signposted in bold ("**not**", "This is deliberate"). Its data shows the bytes: step 12 ran `od -c` on the published files to check the trailing newline (L9).
- Grading on the visible season. 80 of 125 points read the shipped season, which a careful implementer settles correctly. The 40 gen points are all-or-nothing on whole outputs, so the single remaining gap cost 8 checks at once.

## Held cause (L7)
The step-15 code (`/tmp/sv/p2.py`) is an if/elif chain with an early return: `if closed[workshop_id]: findings.append((entry_id, "CAP_REACHED", workshop_id)) ... continue`, then `if short: findings.append((entry_id, "STOCK_FLOOR", short[0])) ... continue`, and only after that the cap test. N3 sits in `invariants.md`, away from A4 and V4. The slice raises no STOCK_FLOOR: the agent's own step-22 diff lists the slice codes as CAP_REACHED, SALVAGE_ALREADY_CREDITED, UNCREDITED_SALVAGE and UNRESOLVED_EDITION. So nothing visible separated the two readings. A composition that is HIDDEN-ONLY and spread across files is the mechanism that works.

## Baselines, round 0 (`_work/.../baselines.json`, tests-only)
S0 0.0 | S1 0.0 (no check paid) | S2 0.08 | S4 0.68 | S5 1.0 | S3: L1 0.592, L2 0.92, L3 0.008, L4 0.104, L5 0.008, L6 0.008, L7 0.68, L8 0.96, L9 0.976; with the draw hardcoded, L5 scores 0.184 and L6 0.144 (shortcut hunt not run).
The closest match to the run is S4 = S3_L7 = 0.68, the same as the run. It implies a reading that is right on every rule in isolation and short-circuits the forge: a closed workshop gets CAP only, and the floor is tested before the cap with no closure. Verdict: REBUILD. S4 should be 0.10 to 0.20; L2, L3, L5, L6 and L9 are DERIVABLE.

## Mistakes and skipped checks that can become criteria
1. It never ran the program on any corpus other than the shipped one. Every run was over `/app/data` (steps 18, 19, 21).
2. Its auditor checked that refused entries carry no later codes but never checked that an entry carries every code that holds. It never looked for an entry with two or more findings.
3. Its final message gives the right three figures, and R6 pays for that presence rather than the values.

## Proposed changes (Phase 2, after "go")
Neutralise: delete `calibration_reference_bundle.json` and keep the controls and the example report. Add `record_shapes.md` with each record's fields, types and order and no values. Reword the instruction's "shape ... fixed by what the slice publishes" to point to it.
Levers. Each one is HIDDEN-ONLY on the slice and planted in the visible season (unlabelled) and in hidden corpora:
- LV-EF-1 (A). A forge at an open workshop that both the cap and the floor refuse carries both findings, and A4 closes the workshop. Reflex: the run's if/elif, so no closure and later forges settle. Confirmed on the run's program (L0902).
- LV-EF-2 (A, new rule V9 on the shipped but unused `retired_patch` column). A forge whose edition calls for a reagent retired from that patch on is refused with RETIRED_REAGENT. The finding composes with cap closure, floor and N3, and salvage returns still re-enter the vault. Reflex: an extra elif or early return, or blocking returns too.
- LV-EF-3 (B). Hidden corpora published under draws with the `consumed` reference. The register text gets fixed to "units called for by every forge the season tests against the vault floor", which matches the oracle and N3. Reflex: the run's own `called_for`, which counts every forge with an edition, settled-only counts, or skipping closed-workshop forges.
- LV-EF-4 (D, optional, the largest build). A requisition size ladder with 12, 24 and 48 requisitions, the bound stated in the instruction. Reflex: the run's exhaustive `best_from`, which is exponential and times out, or greedy. The oracle and grader need a flow-based lexicographic Q7/Q8.
Tests: up to about 55 checks. Visible-season isolation checks drop to weight 1 (about 15% of the positive total). Each hidden corpus triggers one lever and is graded on separate observables, so S3_k loses only its own lever's share, and downstream checks run on corpora with no upstream trigger.
Judge (11 criteria, positive total 25):
- Outcomes from the final message, exact oracle values: charge 5, admitted 5, allocated 3, and the count of entries with two or more findings 5 (new instruction ask), plus the four conventions 1.
- Conduct: runs the program on an edited copy of the data before concluding 3 (JD-15 step 2, raises the odds).
- Code quality 3 (JD-18).
- Negative constraints: writes under /app/data -5, non-stdlib import -3, network call -3, claims an unrun check -3.
- R1, R7, R8, R9 and R10 are dropped.
A run like this one would score about 4 to 7 out of 25.

## Gates before (untouched copy), and decisions needed
- QC scripts: 4/4 PASS, 0 FAIL, 0 WARN.
- Playground static: 3 FAIL. A1 (the workshop and guild paths are not graded by name). A4 (no spec names the data files). A5 (1291 lines, every csv under 2000).
- Validator: 9 FAIL. §1.12 does not apply. §15.5 and §15.7 are OPEN CONFLICT Q18 (kept as is). §5.3, §5.4, §5.5, §7.2, §11.3 and §11.5 can be fixed.
- Decision needed on A5. It needs at least 20k lines with every csv at 2000 lines or more, which means a much larger season and the small tables turned into JSON. Rebuild, or record a waiver?
- Decision needed on LV-EF-4. Include it, or keep three levers?
