# DIAGNOSIS - district-heat-flex-procurement, harden lp1 r2 (board eb6f232)

Source: trajectory a5 (`traj_a5/job/trajectory/claude-opus-5/Run 1/`), claude-opus-5, combined 0.8125 = tests 1.0 x 0.5 + judge 10/16 x 0.5. Bundle as after harden lp1 r1 + P12 r2 + QC v5.

## 1. Genuine check: GENUINE
- The harness staged copy (`Terminal_2.0_Harbor_Harness/.kiro-staged-tasks/district-heat-flex-procurement`) against BUNDLE (`diff -rq`): identical except the harness marker `.kiro-staged-from` and `task.toml` `allowed_hosts` gaining `host.docker.internal` (judge proxy injection). No judge-only file differs.
- `agent/instruction.txt` is byte-identical to `instruction.md`.
- `result.json`: `exception_info` None, reward 0.8125. `verifier/test-stdout.txt`: every positive `[check]` line says `passed`; no crash or timeout.
- `judge_response.txt` scores each criterion with quotes from the run (R1 1, R2 1, R3 0, R4 0, R5 1, R6 1, R7 1, R8 0, R9 1 = 10/16), so the judge read the response.
- Local replay: the a5 final program graded by the current `tests/test_output.py` (WORK `grade.py`) earns 113 of 113 = 1.0, the same as Docker.

## 2. How each lever leaked
Timeline (trajectory.json): step 5 `cat /app/data/schema.md` (06:49:48); step 6 `cat program.ini; cat export_manifest.tsv; head -20 rate_cards.xml`; steps 7-11 heads and statistics of every file (step 11 prints `mult Counter({'1': 102626, '5': 2750, '2': 2660})`, `cards 10000 64854000 226`); step 12 and step 14 (06:55-06:57) write `/app/out/derive_report.py`. The step 14 program is the final logic: later edits are case-insensitive codes (19), cosmetics (20) and the manifest row count (37). Self-checks after writing: step 17 independent Fraction re-derivation (0 failures), step 21 synthetic dense/tight extract generator (step 24: 0 failures), step 28 exact-half count, steps 29-33 a hand-computable mini extract.

Line numbers in the quotes are of the step 14 `file_text`.

| lever | first correct step | agent quote | class | evidence |
|---|---|---|---|---|
| L1 receipt (`export_manifest.tsv` control) | 14 (count), 37 (row count fix) | `count = -1` / `for line in self._fixed_lines("export_manifest.tsv"): count += 1` (299-303); the receipt's `field_sum` is never compared with anything | e: the control agrees with the correct reading by construction ("the sum of that field's values as they are written in the file", export_manifest.tsv:4) and `schema.md:98` says "No report figure is taken from it", so nothing pushes a reader to repair towards it. The lever punishes a reading nobody takes. | export_manifest.tsv:1-5, schema.md:95-98 |
| L2 register multiplier (make-it-match repair) | 11 (counts multipliers), 14 | `multiplier = int(row["register_multiplier"])` / `self.ticks(int(row["relief_wh"]) * multiplier)` (232-235) | a: one plain sentence names the field and the product. The repair is never tempting because the agent never compares Wh with the receipt (see L1). | schema.md:54-57 "the row's relief in Wh is its `relief_wh` times its `register_multiplier`" |
| L4 rate composition (override, uplift, adder, cap) | 6 (reads program.ini and the rate_cards comment), 14 | `start = card.find("base") if override is None else override` (178-179); `before = start + self.uplift[site_key[0]] + self.rate_adder[site["segment"]]` / `return before, min(before, cap), before > cap` (336-337) | a + d: every piece is one plain sentence, and section 6 is a pointer list naming all three source files ("formed from its card in `rate_cards.xml`, its event in `events.json` and the `[segment_rate_adders]` of `program.ini`, each as that file states"), which acts as a checklist. The judge saw `R3 = 0` only because the agent's own example did not combine override and adder. | rate_cards.xml:4-5, events.json uplift schema.md:36-37, program.ini:21-22, schema.md:134-135, schema.md:193-195 |
| L7 per-interval half-to-even credit | 14 | `return sum(div_half_even(ticks * self.wh_per_tick * effective, den) for ticks in relief_ticks)` (339-345) | a (then c): the comment states the unit and the mode, with its own gloss "(an exact half goes to the even neighbour)". Afterwards (step 28) the agent measured the separation itself: "intervals 25554 exact halves 933, offers whose credit differs under half-up: 449". | rate_cards.xml:6-9 |
| H1 waiver precedence and validity | 14 | `waived = (waiver.get("waiver_status") == "VALID" and waiver.get("waiver_signed") == "Y" and site["critical"] and site["segment"].lower() == "public")`, ladder `SAFETY_HOLD`, `COOLDOWN`, `pending and waived` (308-330) | a | schema.md:140-144 |
| H2 greatest tuple tie | 14 | `tag = sorted(chosen)` / `if tag > best_tag: best_tag = tag` (446-452) | a | schema.md:126-129 |
| H3 cap after every adjustment | 14 | `return before, min(before, cap), before > cap` (337) | a | schema.md:134-135 |
| H4 residual in descending id order | 14 | `order = sorted(shares, reverse=True)` / `order.sort(key=lambda b: -remainders[b])` (515-516) | a | schema.md:129-130, 221-223 |
| H5 / DH-2 ticks when first derived, ticks in the search | 14 | `self.ticks(int(row["relief_wh"]) * multiplier)` (234); search over packed tick vectors (420-436) | a | schema.md:118-122, 169-172 |
| DH-3 funded pool | 14 | `funded_cents = max(0, pool_cents - credit_cents)` (638) | a | schema.md:207-209 |
| DH-4 rejected profile rows in order | 14 | orphan, out-of-range, duplicate in that order (217-240) | a | schema.md:57-65 |
| DH-5 waiver doubles the weight via the label | 14 | `if extract.label[site_key] == "CONTINUITY_WAIVED": weight *= 2` (646-647) | a | schema.md:212-213 |
| DH-6 decoy `[export] waiver_signed = Y` | 14 | `if not (row.get("waiver_signed") or "").strip(): missing += 1` (161) and validity requires `== "Y"` (316) | a: schema.md:30-31 says `[export]` "carries no rule for this programme" | schema.md:30-31, 79-80 |
| DH-7 objective component order | 14 | `key = (cached[0], deficit, cost_weight * bid + recovery_weight * recovery_total, cached[1], len(chosen))` (437-443) | a | schema.md:174-187 |

Summary: every graded rule leaked as class (a) on the first write, about 8 minutes in. None leaked through a test name or error text (the agent never saw tests). L4 also leaked through the section 6 pointer list (d). L1 and L2 never had a pull: no step compares a computed figure with the receipt, because the receipt feeds no report figure and states the as-written reading itself.

## 3. Why the round-1 agent program lost 0.82 and the fresh agent lost 0
- The round-1 gate program (a4) was written against the bundle before lp1 r1 added `register_multiplier`, the `override` element, `[segment_rate_adders]`, `export_manifest.tsv` and the per-interval half-to-even credit. It scored 20/113 = 0.177 because those rules did not exist when it was written: it fails `register_multiplier_case`, `rate_composition_case`, `interval_credit_rounding_case`, both mutations, all 20 composed documents and the two format checks that need `export_manifest.tsv` in `rows`. The gate measured staleness, not whether a reader of the new text would take the wrong reading.
- A fresh agent reads each new rule once, in a plain sentence near or pointed to from its use, and codes it on the first write. Its self-checks (re-derivation, generated extracts, mini extract) all use its own reading, so nothing could fail it.
- L1 (receipt) and L2 (multiplier repair) punish a reading nobody takes: the receipt states the as-written reading and is never used for a figure, so no agent is pulled to drop the multiplier to make it match. They are replaced in Phase 2.
- L4 and L7 punish readings a careless reader takes, but the text made the careful reading the only one; both need the wrong reading to be the natural careful one.

## 4. Gate program for round 2
`OUT/agent_program/derive_report.py` is the a5 final program (32,111 bytes, from `artifacts/app/out/`). It scores 1.0 on the current tests. Because a gate on an old program only measures staleness, round 2 also builds `OUT/agent_program_reflex/`: the a5 program with every new rule added in its reflex reading (no other change), and reports both.
