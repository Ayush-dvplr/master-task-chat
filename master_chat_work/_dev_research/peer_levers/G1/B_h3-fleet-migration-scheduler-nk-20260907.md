# B: h3-fleet-migration-scheduler-nk-20260907

## 1. Inventory
- **Domain / archetype:** HTTP/3 fleet scheduler running over epochs (apportionment, placement, preemption, token buckets, fixed-point loop). The agent must deliver a reusable program `/app/out/reusable_scheduler.py <data> <out>` and 10 canonical JSON artifacts.
- **Files the agent sees:** 26 under /app/data. They are a 16.5 KB spec `README-input-schema.md` (204 lines), 11 small CSV/JSON inputs under 1 KB each, `worked_micro_example.json` (2.8 KB, a 3-node/2-epoch traced example), 6 sealed cases `case-*.json` (1.6-2.3 KB) and 6 witness files `seal-*.json` (170-234 B).
- **Instruction:** 568 words (`wc -w`).
- **Tests:** 35 checks per `solution/TRUTH.md:47-57`. There are 31 positives totalling 89: hygiene 4 x1, fresh tiny fixtures 13 (5,5,5,5,5,3,3,3,3,1,3,1,1), hidden scenarios 6 x3, sealed witnesses 6 x3, hard hygiene 2 x3. There are 4 negatives of -5.
- **Isolated vs whole output:** the fresh fixtures are isolated (each is a tiny corpus built in `_fixture_files`, L841-1053, with the agent program run on it). The hidden and sealed checks compare a whole artifact (schedule_matrix, objective_breakdown or final_state) to the reference.
- **Hidden inputs:** yes. `_seeded_scenario` (L1059) takes the shipped corpus and swaps one file (fleet nodes, QoS caps, arrivals set to 0, migration multiplier 5). The reference is computed at test time from the embedded copy of the data. Three of the "hidden" checks (baseline, challenge_final_state, and the damping and empty_epoch "fresh" checks) actually compare the agent's DELIVERED /app/out files on the shipped data.
- **Judge:** 17 criteria (14 positive totalling 44, 3 negatives of -3), batched mode, model gpt-5.6-sol, ATIF trajectory. The reward split is 0.5 / 0.5 (`reward.toml`: test 1/178, judge 1/88).

## 2. Rule map (the graded rules that matter)
| Rule | Where stated | Form | Trap explained? | Shipped data separates? |
|---|---|---|---|---|
| LR tie-break, floor vs cap, SLO compare, refill rounding (the 4 "withheld settlements") | instruction.md:5 names all four. README section 6 / 8.x lists each with "*The lost text settled ...* Candidates:" | Withheld value with a closed candidate list, recovered from seals | The candidates are listed. Which one is right is left to the seals | YES. Each seal separates exactly one. The agent replayed all 24 combinations against the 6 seals (steps 14-15) |
| Carry-over `consumed[n, e]` | README:93 uses it without defining it. README:16 says "units consumed per admitted stream" | Undefined symbol, and the only gloss contradicts the oracle | No | NO. In the micro example, units equal count on every node. The agent passed all 6 seals |
| Fixed-point loop is per epoch | README:31 "For each epoch e ... Phases 4-6 are wrapped in the fixed-point loop", README:102 "the epoch's admissions", README:106 "across all tenants and epochs" | Split across the section header and phase text, with one contrary clause | No | NO. Damping reduces to a no-op (README:105 "Practically, this reduces to ..."), so only the iteration count differs |
| Canonical JSON, integer only, manifest digests, final fold | README section 4 / section 10 | One plain sentence each | n/a | yes (all passed) |

## 3. Lever table (failed checks and criteria)
| id | w | rule | agent reading (evidence) | correct (reference) | mechanism | self-test catches? | fully stated? | family |
|---|---|---|---|---|---|---|---|---|
| hidden_baseline, tight_slo, burst, migration_dominant, challenge_final_state, empty_epoch, reusable_alternate | 3,3,3,3,3,3,1 = 19 | token carry-over | `reusable_scheduler.py:447` deducts the MTU units actually consumed | `test_output.py:707` deducts one token per placed stream | undefined symbol; the only gloss contradicts the reference | N: the seals and the micro example never put units ≠ count on a bucket that binds later | **NO, HIDDEN RULE** (contradicted by README:16) | C state carried across epochs, but not usable |
| fresh_fixed_point_damping | 3 | loop shape | one loop over the whole horizon (L485-517; 2 iterations) | one loop per epoch with a global counter (8 iterations) | the phase-order header plus one clause pointing the other way | N: no artifact checks the iteration count against a witness, and damping is a no-op | ambiguous, IN-16 risk | NEW: "structure-only trace" |
| judge R6, R9, R11, R12, R15 | 3 each | process narration | the agent brute-forced the combinations in one harness | wanted narrated falsification and a base run first | conduct criteria | n/a | yes | n/a |
| judge R14 | 3 | visible header print | the step-6 `cat` ran, but its observation is null | n/a | **trajectory-capture artefact** | n/a | n/a | artefact |

Confirmation: a one-line patch of L447 (`_scratch/h3_fix_out`) flips 7 of the 8 failed tests.

## 4. Contrast: what the agent passed
- **All 4 withheld settlements, all 6 sealed witnesses, and the 11 fresh fixtures** (43 points of fixtures). The design is "closed candidate list plus witnesses that separate each candidate". That is exactly the leak our DIAGNOSIS describes: a rule whose decisive case ships in the data lets the agent check itself. Here the agent searched all 2^4 x 3/2 = 24 combinations mechanically (step 15 prints PASS and fail per combination). A withheld constant with a finite candidate set and shipped witnesses is not a lever.
- Hygiene (canonical JSON, integer only, manifest, eleven files) passed: each is one plain sentence.

## 5. Agent behaviour
- 30 steps, about 12 min (18:55:33 to 19:07:29Z). Step 4 viewed the full README. Steps 6-10 read every input, the micro example and every case and seal. Step 12 wrote a hand-derivation thought for the 4 settlements. Step 13 wrote the scheduler in one go. Steps 14-15 ran the harness over all 24 combinations. Steps 16-19 ran on /app/data and checked reruns, canonical form and floats. Steps 20-21 fuzzed 300 random corpora for invariants only (capacity, SLO, ceilings), with no oracle. Steps 22-24 were cascade micro corpora. Step 27 was AGENTS.md.
- Self-tests used shipped seals plus invariant fuzzing, and neither separates units from count. The final message (step 29) claims "exactly one combination matches every seal" and reports total_cost 1216 (the reference is 1431).
- It never noticed the undefined `consumed`. There is no hedge about it in the final message (step 29).

## 6. Test design
- Expected values come from a reference reimplemented inside `test_output.py` (`_reference_solve`, L674-771) and run at test time on embedded data, fixtures or swapped-file scenarios. Each check is pass/fail with no partial credit.
- Negatives (hardcoded output, filename dependent, reads training corpus, nondeterministic) did not fire.
- About 9 points grade the agent's delivered files on shipped data (baseline, challenge, damping, empty_epoch). The rest run the agent's program.

## 7. Judge design
- Pattern worth reusing: R8 and R11 ("identifies at least one candidate combination that fits at most five of six seals and explicitly discards it, naming which ...") make the agent show a falsification step. These are conduct criteria that raise the odds, at w3, which is JD-15 safe.
- R14 rests on tool output being visible, so it is fragile when the harness drops observations. Avoid criteria that only pass if a specific early read is echoed.
- R6 (base solver before seals) is a pure ordering preference at w3, which JD-15 counts as minor and allowed. No JD-7 issue: the oracle can meet all of them. JD-18 is met by R16 (readable code).

## 8. QC safety
- Lever "undefined carry-over symbol": **NOT ALLOWED**. It fails IN-15 ("A rule that is graded but appears in no file the agent can read costs the honest agent reward", 01_Instruction_QC.md:45), it is contradicted by README:16, and it fails TS-19.
- Lever "loop shape": **RISKY**. IN-16 ("two defensible readings and nothing in any agent-visible file to settle them", 01:89).
- Withheld settlements with seals: SAFE, but it leaked (no points lost).
- TS-16: the negatives are cheat-only, so SAFE. TS-20: weights 5/3/1, SAFE. AL-28: 4 negatives on distinct acts, SAFE.

## 9. Writing style
- instruction.md:5 "their prose was lost from the shipped ... Section 6 ... names the four missing rules and lists the candidate values". This frames the withheld rules as lost text, so the agent knows to look but must use evidence to pick. (It leaked because the evidence was too direct.)
- README:105 "Practically, this reduces to: ... the fixed-point trace still records the pre/post admissions so the *loop shape* is exercised". This is a decoy that defuses one part (damping) while the graded thing (the loop's granularity) sits in the same paragraph. A good technique in principle, but here the granularity was ambiguous.
- README:16 "units consumed per admitted stream". A table gloss carries a definition. The lesson is the reverse: a gloss that contradicts the oracle makes a rule hidden.
