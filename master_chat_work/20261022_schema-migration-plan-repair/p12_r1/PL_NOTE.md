# schema-migration-plan-repair (e5411d0): P12 r1 note for PL

All five QC v2 findings were rechecked against the live kit (HEAD 3fb1650b; none of the rules involved changed). There are no false positives and no open questions.

## Fixed
- DS-27: deleted the cross-check sentence from TRUTH.md. It was validation history and pointed to a repository that is not in the bundle.
- TS-13: split the three-part signature check into three checks. `signature_keeps_explicit_null` (w3) now checks only null vs absent. Two new w1 guards: `signature_rejects_unknown_schema` and `entry_points_leave_arguments_unchanged`. Totals are now 45 checks, positive 137, and reward.toml was recomputed. Effect: the tests channel gets marginally easier (+2/137 for any build that ships a working archive). Which wrong reading loses which checks is unchanged.
- JD-5: R7 now judges one thing: no debug residue (debug prints, commented-out code, functions nothing calls). The catalogue-code facet is already graded by the tests.
- TS-14: renamed `negative_hardcoded_sample_answers` to `negative_embedded_hidden_eval_data`. It now says what the body detects (the hidden seed or hidden edge ids in the delivered source). Weight and body are unchanged.

## Kept (minor)
- TS-23 (45 checks, above the 35 warn cap): this is a warn, well under the 70 hard cap. 19 checks are composed worlds that give partial credit per lever. Folding them would make a build that fixes 3 levers look the same as one that fixes 8.

## Unsure
- None.
