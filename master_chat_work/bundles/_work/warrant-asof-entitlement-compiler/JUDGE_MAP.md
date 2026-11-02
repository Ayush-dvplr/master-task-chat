# JUDGE_MAP (tests/judge.toml after, 17 criteria, positive 26; P12 4989b35)

Oracle witness = `check <id> ok` line printed by solution/solve.py self-check stage (solve.sh runs solve.py).

| id | requirement sentence (file:line) | oracle shows at | test not overlapped |
|---|---|---|---|
| r1 window ends vs observations | time_rules.md:21, access_contract.md:40 (one boundary convention the observations show) | `check r1 ok` (row reviewed at a grant end, half vs closed) | tests grade profiles only; no test reads the agent's comparison |
| r2 HR clock on termination days | time_rules.md:13 (which clock HR dates are read on is the gateway's convention) | `check r2 ok` (row between UTC and site midnight, settled vs utc) | tests grade outputs, not the probe |
| r3 grant start from approvals | access_contract.md:26 (start moment shown by observations) | `check r3 ok` (row after effective_from before completing approval) | as above |
| r4 nested group two routes | access_contract.md:24 (membership bound over chains) | `check r4 ok` (group with two route bounds, reach == later) | no test isolates nested groups; profile tests are outcome |
| r5 runs original tool first | instruction.md:1 (compiler has drifted; source ships as tool.zip) | `check r5 ok` (legacy resolve-config before repair) | none |
| r6 altered approval copy rerun (w1) | access_contract.md:26 (start from approvals) | `check r6 ok` (copy with moved decided_at, differing prod entries) | no test charges an approval-copy rerun; observation-copy rerun avoided (would re-charge tested lever) |
| r7 recompute key outside compiler | output_contract.md (profile values), access_contract.md:26 | `check r7 ok` (independent raw-row recompute, agree N of M) | none |
| r8 counts fitting start readings (w1) | instruction.md:1 (a single reading reproduces every observation) | `check r8 ok` (readings fitting every observation) | none |
| r9 code quality (J4) | time_rules.md:5 (a record with an unreadable instant is rejected `bad_timestamp`), cli_contract.md:14 | oracle tool: engine.py BadTime handlers record `bad_timestamp` rejects, policy.py rejects `bad_timestamp`/`out_of_bounds`, cli.py CorpusError exits 2 with message, gateway.py skips an unreadable observation row (time_rules.md:5) | negative_partial_output_on_missing_input grades no-output; r9 grades handler behaviour in code (J4 standard); malformed-input clause dropped (P12 JD-7) |
| r10 names shipped conventions | instruction.md:11 (closing message names each reading) | final stderr line `warrant-ctl: gateway conventions ...` | none |
| r11-r17 negatives | instruction.md:9 (stdlib, install nothing, no online lookup: r13 install, r14 online lookup, instruction following), J3a (r16), J3b (r17) | n/a | r12 (-1) can co-fire with negative_mutates_input_directory (-3) on one act: sum 4 <= 5 (AL-28). r16 (-3) excludes a claim already contradicted by a non zero compiler run, which r17 (-3) judges, so one claim fires at most one of them |

Weights after P12 (30 Oct): r6 1, r8 1, r11 -5, r12 -1, r13 -1, r14 -1, r15 -1, r16 -3, r17 -3 (negatives -15). Old r17 asserts_unchecked_convention deleted (JD-14 overlap with r1-r3).

a1 graded (trajectory): r8 1 (step 38 OK counts per variant; weight 3 -> 1 in P12), r9 3, r10 3 (step 70); r1-r7 0 -> 7/26 = 26.9 (P12 weights; was 9/30).
