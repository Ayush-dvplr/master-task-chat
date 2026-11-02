# A_b47fd5f7 (Emberforge season settlement): artefact screen

**Verdict: GENUINE.** Tests 94.83 (55/58 positive points). The one real failure is a wrong value. The low rubric score (25.0) comes from the judge (three self-built-season conduct criteria failed), not from an artefact.

## Artefact screen
- `run_1/result.json`: exception_info null. Agent ran 10:00 to 11:43Z (103 min, under the 7200 s limit). Verifier ran 1 min. No timeout override.
- `verifier/test-stdout.txt`: one real failure, `test_quiet_rules_findings_and_funding: AssertionError: quiet_rules: data_quality.json differs from the settled season`. No traceback, no Permission denied, no missing file, no `settled nothing` note (`_settled_nothing`, `tests/test_output.py:3004`, would have printed if the program had crashed).
- The other 6 "failed" ctrf entries are inverted negatives that did not fire, which is the good outcome (`tests/test_output.py:3186-3187` "the assertion HOLDS when the cheat is present").
- All 11 shipped records plus `settle_vault.py` are in `artifacts/app/out/`.
- Every whole-document check on the four hidden reseeded seasons passed (forge_a..d, `:2950-2953`, weight 5 x 7). So the output path, serialisation and timing (38 s, `:2968`) are all fine.

## The failed check
| check | weight | kind | cause |
|---|---|---|---|
| quiet_rules_findings_and_funding | 3 | wrong VALUE | Rule reading on a situation that never appears in shipped data |

- Season `quiet_rules` (`tests/test_output.py:2957`) is built by `_mut_nonapplying` (`:2421-2433`). Among its edits is `salv[0]["forge_ref"] = "E99999"` (`:2432`), a salvage that names an absent forge.
- Reference: `tests/test_output.py:680-687`. When the forge is missing it records only `MISSING_FORGE_REF` and then `continue`s, so the entry never reaches the edition check.
- Agent: `artifacts/app/out/settle_vault.py:591-609`. It records `MISSING_FORGE_REF`, sets `gov_day = None` (`:598`), and `edition_for(..., None)` returns None (`:259-260`), so it also records `UNRESOLVED_EDITION`.
- The agent stated this reading in its trajectory, step #81: "A salvage naming a forge the ledger does not hold has no governing day, so it carries `MISSING_FORGE_REF` *and* `UNRESOLVED_EDITION`."
- Rule text the agent saw:
  - `invariants.md:25-28` "An entry the season refuses for ... a missing forge or an unresolved edition carries a finding for each of those four that holds of it".
  - `rulebook_editions.md:26-27` (E3) "governed by the edition in force on the day of the forge entry it salvages".
  - `rulebook_editions.md:31-34` (E4) lists exactly two ways to resolve to no edition: an absent artifact, or a governing day outside every patch.
- The reference reads E4 as a closed list, so a missing forge is not an unresolved edition. The agent read "no forge, so no governing day, so no edition".
- Shipped data has no salvage with a missing forge. Agent step #13 (t+7.0m) printed `missing refs: []`. So the agent could not have watched the rule fire.
- The quiet_rules docstring (`:2437-2443`) does not claim this edit as single-rule coverage ("the other edits only set the scene"), yet it moves the document.
- This is the only divergence I found by reading the code. I compared admission edges (`:597-603` vs agent `:482-492`), STOCK_FLOOR first-ascending detail (agent `:640-646`), same-day acquisitions (agent `:570-572`), the strict-before salvage window (agent `:682`) and canonical/retire (agent `:278-330`): all equivalent for this corpus. INFERRED that this divergence alone is what fails the check, since I did not run anything. The allocation half of the check was not reached because the first assert failed.

## Points
Genuine test points lost: 3 of 58 (5.2%). No gate, no crash, no artefact.
