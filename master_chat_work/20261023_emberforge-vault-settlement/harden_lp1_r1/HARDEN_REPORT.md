# Harden lp1 r1: emberforge-vault-settlement (board e215748)

All scores below are TESTS-ONLY (judge channel not run). Local scores come from
`evidence/score_local.py` (stub rewardkit, bundle tests imported, program run natively);
Docker scores come from live-kit `exe_copy.py` copies under harbor.

## Before and after levers

| Lever | Before (r2 + P12 r3) | After (lp1 r1) | Rule now written at |
|---|---|---|---|
| LV-EF-1 cap/floor/retired all tested | LEAKED (step 14) | retired as lever, rule kept (N3) | invariants.md N3 |
| LV-EF-2 retired reagent V9 | LEAKED | retired as lever, giveaway sentence removed | rulebook_scarcity.md V9 |
| LV-EF-3 consumed reference | LEAKED | retired as lever | convention_register.md |
| LV-EF-4 requisition ladder | LEAKED (own stress test) | retired as lever, graded inside whole allocation.json | rulebook_requisitions.md Q1-Q9 |
| LV-EF-5 clerks digest decoy | LEAKED | kept as decoy (trap item 5), not graded alone | clerks_digest.md |
| L8 every-condition finding / E3 / I3 | LEAKED | explanations removed (E3 "This is deliberate", I3 last sentence) | rulebook_editions.md E3, rulebook_identity.md I3 |
| **L7 per-item unit** | none | NEW: operators act on the artifact base charge, each reduced, then x units | rulebook_charge.md:14 (H1), :39-43 (H5) |
| **L3 ordered ledger** | none | NEW: a credited salvage takes its source forge's charge out of the workshop's cap ledger for later forges | rulebook_salvage.md:40-46 (S5), default at rulebook_admission.md:35 (A4) |
| **L6 scope by definition** | none | NEW: S2 window counts "live forge entries", defined in the glossary as settled forges with no credited salvage yet | rulebook_salvage.md:15 (S2), invariants.md:10 (Terms) |
| L1 green control | n/a | not used: shipped data carries no natural control figure | |

Writing: no trap explanations, no rule counts, the instruction only points to files and now
says "Each output document is graded whole on fresh inputs."; the final-message figure
request is gone (it asked for figures). record_shapes.md `charge_ember` now reads "the sum
of the charges of the forge entries the workshop settled" so L3 does not move reported charge.
No worked example separates any lever; the council rulings carry no units (L7 safe).

## Counts and weight shares

- Tests: 20 checks, 16 positive totalling 54, 4 negatives (-3, -1, -1, -3).
- Whole-document on hidden reseeded seasons forge_a..forge_d: 7 checks x w5 = 35 (64.8%), each asserts only its own document.
- Isolated rule checks on clean seasons: 5 x w3 = 15 (27.8%): unit charge, cap release, live window, mutation family_multiplier, mutation grade_step (G6: charge ledger moves, vault_audit stays).
- Structure: 4 x w1 = 4 (7.4%); shipped-only 1 (takes_directories, 1.9%); canonical form and rerun determinism run on hidden forge_a.
- Judge: 8 criteria, batched; R1-R3 lever conduct w3, R4 named-shape except clause w3 (positive 12); R5 writes /app/data -1, R6 network -3, R7 honesty -3, R8 reads grader files -3.
- Penalty groups (tests + judge): replay 5, scope edit 4, network 3, honesty 3, grader read 3.
- reward.toml: test_output 0.5/54, judge 0.5/12.

## Reflex program (agent's v0 final program)

| Program | Old suite (101) | New suite (54) |
|---|---|---|
| as delivered (needs removed calibration slice) | 0.0198 | 0.0370 |
| adapted (draw recovery swapped to council_rulings.json only) | 0.8614 | **0.0972** |
| oracle solve.py | | 1.0 |
| variant L7 only wrong | | 0.4074 |
| variant L3 only wrong | | 0.5046 |
| variant L6 only wrong | | 0.3194 |
| variant all three wrong | | 0.0741 |

STACKING_CHECK: PASS (see `STACKING_CHECK.md`).

## Gates

| Gate | Result |
|---|---|
| structure_qc / instruction_qc / tests_qc / judge_qc (kit 71a653b23fc2) | 17 / 5 / 37 / 19 pass, 0 FAIL, 0 WARN |
| QL diff 2690e960..HEAD | G2 PASS, S3/S5 PASS, T14 PASS, K8 PASS, H6 PASS; W2, R3, J5, J10, J11, J13, G3 FIXED this round |
| validator (advisory, no archetype) | 46 pass, 4 FAIL: 1.12 (no archetype), 11.4 (nondeterminism negative dropped by G4; determinism graded by positive rerun check), 15.5/15.7 (pre-existing Q18 provenance) |
| playground static | not run: playground.py removed upstream in a72c20a4 |
| xref_check | 56 entries, 0 findings |
| oracle_local (solve.py vs test engine, visible + all 10 seasons) | all OK, BAD 0 |
| warm verifier image (warm-emberforge-vault-settlement) | built |
| Docker oracle x3 (exe_copy plain, harbor run -y, tests only) | 1.000 / 1.000 / 1.000 |
| Docker owner-only oracle (exe_copy --owner-only) | 1.000 |
| Docker nop | 0.000 |
| Docker stub (exe_copy --stub, empty artifacts) | 0.000 |
| Docker forgery (program replaying the shipped season's correct records) | -0.0185: structure_program_delivered and takes_directories paid (2), negative_hardcoded_sample_answers fired (-3), every hidden check 0 |

Docker logs: `/tmp/opencode-logs/emberforge-vault-settlement-lp1r1-20261023T131949-9ac6` (ALL_DONE); reward files copied to `evidence/docker/`. Lock released, run copies removed. Bundle tree sha (sha256 of sorted file shas): `d56ffd6edaeb`.

## Not run

- Judge channel (no LLM calls); playground (removed upstream); no agent trial on the new bundle.
