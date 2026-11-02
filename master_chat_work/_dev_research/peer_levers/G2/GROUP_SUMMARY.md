# G2 peer lever mining: group summary (board dfdc8b8)

- Anubis_Tasks_Samples HEAD: `19cdf6989906385943b9ca00acaadcae204b29e8`.
- Session renamed to `dfdc8b8` (ses_e9970f238ffeatSccdg0NKEhxs, shown in `opencode session list`).
- Each claim below points to evidence in the per-task files: `A_<slug>.md` for verdicts, `B_<slug>.md` for mechanisms.
- "pts" = raw test or criterion weight. "pct" = the effect on the 0-100 tests or rubric score.

## 1. Results
| task | verdict A | overall / tests / rubric | genuine test pts lost | genuine judge pts lost |
|---|---|---|---|---|
| reminder-scope-surface-reconcile-hk-85 | PARTLY | 73.23 / 90.53 / 55.93 | **9/95** (9.47 pct): 3 legal-but-unseen file-encoding variants | 26/59 lost. 20 are conduct (w5 procedure probes). 6 are outcome criteria with no contract sentence (R19, R23), so NOT ALLOWED |
| reminder-store-reconciliation | GENUINE | 62.25 / 83.33 / 41.18 | **13/78** (16.67 pct): one recovery bug (asserts the parameters are unique) billed across 13 tests | 30/51, all w3 conduct probe criteria |
| session-watermark-settlement | PARTLY | 60.57 / 96.70 / 24.44 | **0**. The -3 is a false-positive anti-cheat (ARTEFACT) | 34/45, all w1/w3 conduct "locate or construct edge case X" criteria. The program was correct on every one |
| wire-format-recovery | PARTLY (near ARTEFACT) | 73.37 / 55.56 / 91.18 | **0** semantic. 32/72 lost to an exact key-set gate on an object shape the spec never states (confirmation run: 32/32 equal once the key is dropped) | 0 (the 3 lost are on R11, a preference criterion against helper files) |

Bottom line:
- Only about **22 genuine test points** across 4 tasks came from real task levers (T1 9 + T2 13).
- Most of the low overall scores come from **judge conduct criteria**: about 90 rubric points across T1-T3, which the agent lost by never building its own adversarial inputs.
- Plus artefacts (T3 -3, T4 -32 and -3).

## 2. Lever patterns (SAFE or RISKY only), ranked by genuine points cost

### P1. Promise scoped to the shipped slice, with an identifiability collapse on hidden data (13 test pts, T2). RISKY → SAFE once re-billed
- **Mechanism.** The spec promises uniqueness only for the shipped slice ("in the calibration slice shipped here exactly one candidate of each reproduces every control figure"). Elsewhere it states the tie clause as a data property: a wrong value counts as wrong "unless that value reads and settles every calibration capture exactly as the right one does". Hidden corpora are degenerate (only one transform on; all gaps equal to 45), so several parameter values tie. The agent hard-asserted `len(survivors) != 1 → SystemExit` and multiplied survivors across stages, so its program crashed or timed out.
- **How the rule is written.** The promise is scoped by a locative ("shipped here"). The exception reads as a definition of equivalence, not as an instruction to handle ties. It is stacked with a generalisation clause: other parameters, bigger calibration slice, 200 s limit.
- **Why the self-test misses it.** On shipped data the uniqueness holds, so the assertion never fires. The agent never made a corpus where it fails.
- **Evidence:** B_reminder-store-reconciliation.md §3; agent transform.py L768-769; test_output.py L1466-1467 and L1479-1480; calibration.md L5-8.
- **Family:** E (stacked constraints) + NEW "scoped promise".
- **Why RISKY:** 12 weight-1 trap tests plus one more all bill the same behaviour (TS-20 / weight semantics). To make it SAFE, collapse them into 1-2 tests at w3-5.
- **Our tasks:** cohort-retention could promise "in the shipped extract each member resolves to one plan", while a hidden extract has two plan rows the stated tie rule settles identically. An agent that asserts uniqueness crashes, and one that applies the stated equivalence passes.

### P2. Legal-but-unseen encoding, under a stated reading principle (9 test pts, T1). RISKY → SAFE if the principle is stated
- **Mechanism.** Hidden variants use encodings the file format allows that the shipped files never show:
  - phonetic `rPh` runs inside xlsx shared strings
  - absolute `/xl/...` relationship targets
  - title-case SQLite column names, where SQLite is case-insensitive but a Python dict is not

  The agent's hand parser handled the shipped shapes only.
- **How the rule is written.** In general terms, a generalisation promise plus reading by format: instruction L9, "a directory holding a different ledger, journal, map or addendum must yield the values that evidence implies". There are no enumerated quirks.
- **Why the self-test misses it.** The agent mutated values (steps 28-30), never file encodings. The shipped data has 0 rPh runs, only relative targets and only lowercase columns.
- **Contrast (key finding).** T3 shipped hidden BOM/xmlns/cell variants that were **stated as instances** in spec.md L23-24 and L160-161. All of them passed and cost 0. T1's 12 variant checks that exercised a stated rule all passed too; only the 3 unstated-encoding checks failed. So the lever is "principle stated, instance not shown", not "instance hidden".
- **Evidence:** A/B_reminder-scope-surface-reconcile-hk-85.md; B_session-watermark-settlement.md §4.
- **Family:** NEW "format generality" (with D cross-file).
- **QC:** IN-15 needs the principle in writing, e.g. "the workbook is any valid OOXML package; read it as that format defines". Without that it is a HIDDEN RULE.
- **Our tasks:** vendor-archive could state "every export is RFC 4180 CSV, header-named". A hidden shard then uses quoted embedded newlines or reordered columns that the shipped shards never show.

### P3. Engine semantics vs host-language semantics (3 pts, T1, inside P2)
- **Mechanism.** The data store's own rules (SQLite identifiers are case-insensitive) differ from the agent's container (Python dict keys are case-sensitive). The stated "read columns by name" is true in the engine and false in the agent's code.
- **Why the self-test misses it.** The agent's self-test runs the same code on the same casing.
- **Family:** NEW. **Verdict:** SAFE if the spec says columns are identified as the engine identifies them.
- **Our tasks:** district-heat could keep meter readings in SQLite and state "columns are matched as SQLite matches identifiers". A hidden DB then uses different case.

### P4. Untested defensive branch (3 pts, T1, inside P2)
- **Mechanism.** The agent foresaw absolute targets and wrote a branch (`"xl/" + target.lstrip("/")` gives `xl/xl/`) that no shipped file exercises. The branch was wrong and nothing ever ran it.
- **Lesson.** Hidden variants that hit the edge cases agents *anticipate* catch sloppy branches. This is SAFE when the edge is permitted by a stated format rule.
- **Family:** F (error path) / NEW.

### P5 (judge lane). Self-built adversarial corpus criteria (T1 R20/R25 = 10, T2 R17/R21/R22 = 9, T3 R25 = 3; about 22 rubric pts). SAFE at w3
- **Mechanism.** The criterion rewards the agent for generating its own input with chosen parameters, running its program on it, and showing that the parameters are recovered or the bytes match. Opus-5 consistently verifies on shipped data only, in all 4 runs.
- **How it is written.** As a conduct criterion with no instruction sentence needed (JD-15 conduct: odds-raising at w1/3 passes, at w5 it is "minor").
- **Evidence:** B files §7 for T1, T2 and T3.
- **Our tasks:** a criterion such as "builds a synthetic extract with a known answer and checks the program reproduces it", at w3. Not w5 (T1 used w5 = minor under JD-15).

### P6 (judge lane). Named boundary-probe criteria (T3 about 30 pts, T2 R20, R23, R25-R29 = 21, T1 R26 = 5). RISKY
- **Mechanism.** The criterion asks "locates or constructs <exact boundary case> and reports what its program did". The agent coded those edges correctly (the matching tests passed in T3) but never showed them, so it loses rubric points for undemonstrated diligence, not wrong work.
- **Why RISKY.** It can drift into a preference (JD-15), and many near-identical probes inflate the rubric. One or two such criteria at w1-3 are fine; 14 (as in T3) are not.

## 3. Writing patterns (rule fully stated, not reflexively solvable)
1. **Locative scope on a promise:** "in the calibration slice shipped here exactly one candidate…" (T2 instruction L3). The promise is true but local, and a careful reader sees the scope.
2. **Exception phrased as a data property, not an instruction:** "unless that value reads and settles every calibration capture exactly as the right one does" (T2 calibration.md L5-8). It defines equivalence, so the agent has to derive "handle ties".
3. **General reading principle plus generalisation promise instead of enumerated quirks:** T1 instruction L9 "a directory holding a different ledger, journal, map or addendum must yield the values that evidence implies".
4. **Implied order:** "in an order the container contract implies rather than states" (T2 instruction). The rule follows from definitions (cost 0 in T2, but it is a legal construction).
5. **Stacked operating limits in the rerun clause:** other parameter values, more captures and records, "must finish within 200 seconds" (T2 instruction L9). This turns a brute-force-correct program into a failing one on hidden scale.
6. **Modal "may" with no shipped instance:** T1 "the workbook … may …". The rule is stated and the instance is unseen.

## 4. Anti-patterns
- **Withholding instances of a plainly stated rule** costs nothing. T4's shipped log was "deliberately NON-REPRESENTATIVE" (raw only), yet the agent coded delta/dict/LEB128/sign extension correctly from one sentence each (32/32 values right). This matches our DIAGNOSIS cause 4.
- **Stated hidden format variants** (T3 BOM, xmlns, cell variants) cost 0.
- **Instruction topic checklist** (T3 instruction L9 lists every trap topic) is a self-leak.
- **A decoy labelled as a decoy** (T3 spec precedence table: "`raw_events.csv` (a stale preview export)") is refuted on the page and cost 0. Same as our CR-2.
- **"Decide which files matter"** triage (T4 L1) is useless when every doc is short: the agent read them all (T4 step 4; T1 steps 2-13; T2 steps 2-8).
- **Hidden-rule levers, NOT ALLOWED for us:**
  - T4 exact key-set gate on delta/dict objects, whose shape is never printed (IN-15/TS-19 fail)
  - T4 R11 "no auxiliary modules" (the instruction bans only imports)
  - T1 R19/R23 outcome criteria that report candidate counts no contract sentence asks for
- **Billing one behaviour many times** (T2 12 trap tests for one bug; T4 one key gates 8 tests) inflates the score effect and breaks TS-20 weight semantics. Do not copy it.

## 5. Score artefacts (never copy as levers)
- **T3:** `negative_weight_non_stdlib_or_network_import` (-3) fired because `NETWORK_MODULES` (test_output.py L2103) includes `urllib.request`. The agent imported it only for `pathname2url` (a SQLite read-only URI). This is a false positive and breaks TS-16.
- **T4:** whole-document `_docs_equal` with exact key sets (L821-835). The spec never states the delta/dict key set. It cost 32/72, while the values were 32/32 correct (confirmation run in A_wire-format-recovery.md §2).
- **T4:** judge R4/R5 (w5) passed on the same observable the tests failed (JD-8 overlap, contradictory verdicts). No code-quality criterion exists (JD-18 fail).
- **Harness:** none of the 4 tasks has our permission bug. All copy the agent program to 0644 and run it under `setpriv nobody` (T1 L571-573, T2 L2281-2284, T4 L753-770). That is the fix to copy into our graders.
- **T2:** verifier time was 40m41s with 200 s per-run timeouts. The failure messages are not kept, so crash vs timeout is INFERRED.

## 6. Open questions for the master chat
1. Will our QC accept P1 with the trap tests merged into one or two w3-5 tests? Or does scoping a promise to "shipped here" read as a trick under IN-15?
2. For P2, how explicit must the reading principle be for IN-15? Is "valid per RFC 4180 / OOXML / SQLite identifier rules" enough when no shipped file shows the variant?
3. Judge P5: should every task carry one w3 "self-built known-answer corpus" conduct criterion? It cost opus about 22 rubric points across 3 peer tasks.
4. T2 failure messages are missing (ctrf has none). Should our graders record assertion messages so Phase A style audits can tell a crash from a timeout from a wrong value?
