# B (design notes only, verdict ARTEFACT): sec-sealed-posture-compile-forge

Inventory:
- Same template as cli-config-01.
- Instruction 652 words, with an L11 per-corpus fixpoint `hi + (R mod 97) + (J mod 31) + (E_i mod 7)`. Contract 1891 words, fixpoint procedure at L56-75.
- 32 tests (positive total 86); 15 judge criteria in `individual` mode; split 50/50 (1/172, 1/102).

Worth noting:
1. **The fixpoint (family B, dependent chain / self-reference) looked hard and cost nothing.**
   - The contract spells out the iteration ("start with E(i) = 0, derive hi_eff(i), recount ... repeat until E(i) is stable") and warns about the one-pass mistake. That is the procedure plus the trap, which leaks.
   - The shipped data has no rows in the band that would make iteration matter: expected values are constant for shifts 61-76, and the agent's loop converged in 1 iteration (step 18).
   - Lesson: a self-referential rule must be paired with data whose answer actually changes between one pass and the fixpoint. Verify that with a sensitivity probe before shipping.
2. **The agent got the spine scope right here.** It replayed base only at step 16, even though the journal has 1796 base ops vs ~1800 per zone. So the scope-by-omission lever is not reliable: it hit 2 of 3 agents that faced it (cli, firewall; sealed escaped).
3. **The cross-file identity slip (extension in the aggregate key) appeared in 3 of 4 tasks** (policy, firewall, sealed). The agents wrote `c01_cve_severity.csv` because the contract says "corpus name" and the instruction refers to files by full path. The stem form appears only as the keys of validation_rules.json `corpus_bounds`.
   - This is a genuine agent tendency, masked here by the strip artefact.
   - It is a pattern we could make SAFE by defining "corpus name" once (e.g. in a glossary or rules file) and using it bare everywhere else.
4. Self-check at step 33: an independent parser written with the same reading. It is the same failure mode as our cohort agent: the second implementation shares the first one's interpretation, so agreement proves nothing.
5. The judge's #14 "concrete op" demand was rejected for an arguably valid example (INFERRED: any misclassification moves J). A narration criterion with a judge-defined answer is unreliable.
