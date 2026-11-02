# PL note: schema-migration-plan-repair, QC v13

False positives: none. The three findings were real and are fixed; no doc, contract or instruction changed.

- DS-20: the reference planner was rewritten. It now works out exact remaining costs backwards over sets of field states and has no give-up limit. QC's two graphs now take 0.007 s (was 286 s) and 0.002 s (was 62-74 s), with the same answers (E_UNREACHABLE and ['E01257']). On 72 in-limit graphs we built (QC's layout, a 24-graph random family, and harder variants) every call is under 3.4 s, inside the 10 s the contract promises. Plans are identical on all 2,696 planner calls the tests make.
- DS-22: TRUTH.md now describes the three ways the reference prints its probe results and says every result is written to repair-report.json.
- AL-17 / TS-11: the verifier now shares one 3,000 s budget across all program runs, so even a delivery that hangs on every check finishes inside the 3,600 s verifier limit (worst about 3,123 s) and gets a low score instead of no reward. The budget is never reached by the oracle (41 s of program time) or by the unrepaired package (2,098 s, same 0.0102 score as before).

Kept warn:

- TS-23 (141 checks over the 35 guide): kept with the count, by the no-cap decision (24 Oct, option A 27 Oct). The extra checks are the 60 large gated worlds that carry the difficulty.

No open questions.
