# LOOPS: round accounting per task

Counts F/M/W come from `OUT/fires.json` and match each report's Verdict line. New-finding causes come from
`OUT/cascades.json` (r = reviewer-variance, h = harden-induced, f = fix-induced, n = new-scope, e = escalation).
A round is marked **OWN** when at least one new blocking finding (fail or minor) in it is fix-induced or harden-induced.
PASS means 0 fails and 0 minors (board usage: timeline from board.json, e.g. cohort "QC v2 PASS 0/0/0", vendor "QC v4 PASS 0/0/2").

Stop rule used here. A task stops at its first PASS. Failing that, it stops at the QC run after its 3rd edit round (P12, rebuild or harden) without a PASS. Sources:
`master_chat_tasks/state.json:89` "P11 v2 QC -> P12 recheck+fix (separate session) -> P11 v2 re-run, max 3 rounds" and
`master_chat_tasks/decisions.jsonl:64` "DROP RULE (Ayush 22:34, permanent): a task is dropped after 3 rebuild/harden rounds without passing the gate (2a)."

| Task | Rounds | F/M/W per round | New per round (cause) | OWN rounds | Right stop | Rounds after it |
|---|---|---|---|---|---|---|
| cohort | 5 | v1 6/3/0, v2 0/0/0, v3 4/2/0, v4 2/3/0, v5 1/2/1 | v3 6h, v4 1r | v3 (harden_r2 7cbd9f5 after PASS) | **v2** PASS | 3 (v3-v5; parked state.json:132 "AL-27 loop, 3 rounds") |
| dispatch | 5 | v1 4/3/2, v2 3/1/3, v3 15/0/2, v4 0/3/4, v5 3/4/3 | v2 1f 1r; v3 6f 2n 2r 1e; v4 5f; v5 3h 2r 1e | v2, v3, v4, v5 | **v4** (3 edit rounds, no PASS) | 1 (v5 after judge rework cc4bb7f), P12 r4 running |
| district | 5 | v1 11/5/4, v2 0/0/3, v3 0/0/1, v4 4/3/1, v5 0/2/2 | v2 2h (warns); v4 5h; v5 2r | v4 (harden_lp1_r1 0154d63 after PASS) | **v2** PASS (warn-only) | 3 (v3-v5) |
| emberforge | 7 | v1 3/3/3, v2 1/2/4, v3 2/0/1, v4 2/1/1, v5 0/0/1, v6 8/0/1, v7 2/0/2 | v2 5h; v3 1r 1n; v4 1r; v6 8h 1r; v7 1f 2r | v2, v6, v7 | rule says **v4**; the override (decisions.jsonl:68 "one more fix round (P12 r3 0188698) instead of drop") passed at **v5** | 2 (v6-v7 after harden_lp1_r1 e215748), P12 r6 running |
| match | 2 | v1 4/0/6, v2 2/0/3 | v2 2f 2r | v2 (both fails fix-induced) | not reached (1 edit round) | 0 |
| schema | 7 | v1 8/2/5, v2 1/2/2, v3 5/1/3, v4 1/2/2, v5 1/2/1, v6 1/2/2, v7 0/1/3 | v2 1f 1h; v3 2f 4r 1n; v4 2f; v5 1f 1r; v6 1f 2h; v7 1r | v2, v3, v4, v5, v6 | **v4** (rebuild + r1 + r2, no PASS) | 3 (v5-v7; P14 a4 recommends PARK) |
| sensor | 2 | v1 2/4/1, v2 2/1/1 | v2 1f 1r | v2 (IN-8 from the P12 r2 JD-5 direction) | not reached | 0, P12 r3 done |
| sentinel | 3 | v1 5/6/3, v2 2/4/7, v3 1/2/3 | v2 3f 5r; v3 2f 1r 1e | v2, v3 | not reached (limit is v4) | 0, P12 r3 running |
| vendor | 6 | v1 26/10/4, v2 7/0/1, v3 2/0/2, v4 0/0/2, v5 0/3/3, v6 0/2/3 | v2 3h 1f; v3 2r 1f(w) 1r(w); v4 1r; v5 1n 3r; v6 3r | v2 | **v4** PASS | 2 (v5-v6 after harden_lp1_r1 52dbb3c) |

## Totals

- 42 QC rounds in all. **14 rounds came after the right stop**: cohort 3, dispatch 1, district 3, emberforge 2, schema 3, vendor 2.
  Emberforge's v5 overrode the drop rule and passed, so it is not counted.
- **4 tasks passed and were then hardened, which restarted the loop**: cohort v2->v3, district v3->v4, emberforge v5->v6 and vendor v4->v5.
  That cost 9 rounds and 19 harden-induced new findings (cohort 6, district 5, emberforge 8; vendor v5's are UNVERIFIED because its copies were pruned).
- 19 of the 33 non-first rounds are OWN. In 10 rounds every new blocking finding was ours: cohort v3, dispatch v4, district v4, emberforge v2, emberforge v6, match v2, schema v2, schema v4, schema v6 and vendor v2.
- The worst single round is dispatch v3, with 15 fails. 6 of them came from P12 r2 regenerating test_output.py from a stale generator (20261022 dispatch p12_r3/RECHECK_FIX.md:108).
