# A restoration-cadence-settlement

**Verdict: GENUINE** (one wrong recovered convention, amplified by whole-report equality across the generalisation tier)

Recorded: overall 53.38 / tests 25.62 / rubric 81.13. QC re-grade on fixed verifier: 31 of 124 (0.2500) vs recorded 31 of 121 (QC report `Kunwar_Singh_restoration-cadence-settlement_QC_Report.md`:56, "that submission broke at `cadence_converted` and lost the whole generalisation tier - and no fresh rollout is needed"); H6 finding there was a false positive (:41/:57), owner-only run 1.000.

## Artefact checks
- exception_info null; no negative fired; ctrf messages empty.
- Program executed under the privilege drop: `_run_program` (tests/test_output.py:1560-1607) grants access first via `_grant_access` (:1515-1557). The agent's program was 0755 (trajectory step 47 `chmod 755`). No permission artefact; generalisation tests failed on value (INFERRED from the shipped-run value mismatch below, which already makes `_generalises` whole-report equality false).

## Root cause (wrong VALUE)
- The task withholds three conventions to be recovered from a calibration cycle (`environment/data/calibration_slice.md`: "Exactly one combination of the three reproduces every figure on this page").
- Test reference: `TRUE_ROUNDING = "half_even"`, `TRUE_ORDER = ("impair", "cadence", "credit")`, `TRUE_DECAY = (3, 5)` (tests/test_output.py:23-25); `compose` (:464-484) converts each later addend separately once the count has been converted.
- Agent (artifacts/app/out/cadence_settle.py:9-15 docstring; `quantise` :46-51; `settle_programme` :371-381): quantise "toward the count it was converted from", impair+credit first, conversion last; ceiling carry 3/5 (correct).
- Agent's model reproduced every published calibration figure: step 24 output "FULL MATCH f= 3/5 model DRC {'cq1': ('A', 11594), ... } total 30115"; step 29 "BYTE IDENTICAL" against `example_vault_report.json`. The calibration therefore does not separate the agent's model from the reference; the uniqueness claim holds only inside the test's candidate set (`ROUNDINGS`, `ORDERS`, `DECAYS` :27-36), which no shipped file lists (calibration_slice.md names the three conventions, not candidate values).
- Final claim (step 52): "no direction-blind rule reproduces both figures, and truncating the *change* is the only convention that reproduces all four per-programme figures".

## Per failed check (all wrong value, one root)
- `cadence_converted` 5 (:2203, compares source/cadence frames + governing element + cadence_total), `settled_frames_fixed` 5, `admission_settled` 5, `vaults_seated` 5, `cascade_and_ledger_closed` 5, `governing_element_excludes_print` 5 (:2404, compares `(governing_element, element_cadence_mhz)` then runs a mutated catalogue with whole `cadence_ledger.json` equality, so fails via the ledger), `admission_closes_as_a_prefix` 5 (draw order depends on settled frames).
- 11 `generalises_*` x5 = 55: `_generalises` (:1626-1655) requires every CORE_REPORTS file and every vault/lane partition to equal the reference; any convention error fails all 11.
- Passed (31): presence/parse/serialisation (w1), identity, spans, shots, defects, impairment, repairs, condition grades (grades coincide under both models).
- Not a separate gate test, but a natural cascade: one convention costs 90 of 121 recorded (93 of 124 re-graded).
