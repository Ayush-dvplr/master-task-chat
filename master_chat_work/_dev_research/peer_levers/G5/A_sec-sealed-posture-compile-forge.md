# A: sec-sealed-posture-compile-forge. Is the low score genuine?

Recorded: overall 69.70, tests 51.16, rubric 88.24 (judge mode `individual`).

**Verdict: ARTEFACT.** The agent lost 42 of 86 positive test points. That is the aggregate family 29 (field-strip contradiction, which also masks the file-extension key slip), manifest 5 (contradiction), and validation_report 5 + summary 3 (types never stated, plus cascade). The agent got the spine right: it replayed base only (step 16), and config_matches_policy and profiles_match passed. The task's "headline" lever, the per-corpus fixpoint `hi + (R mod 97) + (J mod 31) + (E_i mod 7)` (instruction L11, contract L56-75), is inert:
- expected aggregates are constant for every shift from 61 to 76;
- the agent's fixpoint converged in 1 iteration (step 18 "base shift 61 ... iters 1");
- the contract's warning that "A one-pass solver ... will ... corrupt every one of the fifty aggregates" is false for this data.

Evidence:
- Harness: `exception_info` None. ~13.3 min, 44 steps. test-stdout holds only `reward: 0.697`. ctrf has 32 tests, earned 44 of 86. Same test.sh as the other three tasks, so no permission artefact.
- Manifest: the oracle solve.py L406 builds the 19-name `MANIFEST_SET`. Instruction L22 says JSON artifacts only. The agent's manifest has 12 lines (step 42).
- Strip: the oracle strips (solve.py L117-229, several sites). The spec says byte-exact. The agent even saw the padded ini line `flag =  active` at step 14.
- The agent's self-check at step 33 ran an independent draft parser built on the same reading ("aggregates match: True"). This is the same self-consistency trap as in our DIAGNOSIS: a second parser with the same reading proves nothing.
- Judge (15 criteria, 45/51):
  - #1 (3) did not run the broken CLI before replacing it. HIDDEN rule.
  - #14 (3) "names at least one concrete journal operation whose misclassification would change the effective upper bound of every one of the fifty corpora". The agent offered an `unset` on handshake_timeout_ms and the judge rejected it. INFERRED: misclassifying *any* op shifts J by 1 and so changes every corpus bound, so the agent's example was arguably valid. The demand to name an op is stated nowhere either. HIDDEN / unreliable.

Phase B is reduced to design notes (B_sec-sealed-posture-compile-forge.md).
