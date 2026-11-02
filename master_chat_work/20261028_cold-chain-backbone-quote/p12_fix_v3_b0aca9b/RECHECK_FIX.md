# RECHECK_FIX cold-chain-backbone-quote (P12 fix of QC v3, board b0aca9b)

Session renamed to `b0aca9b` (name_session.py: `opencode: ['ses_e7df6185cffea6KRfoplOTaelY']`, `codex: no match`). Kit HEAD `5574d77eb9f22c207ba05fd8f9ac31d42ba45271` (expected 5574d77e). Before any edit, BUNDLE was identical to the QC v3 copy 7304a6f (`diff -rq` returned nothing).

## Finding (QC v3, quoted)
v3.md:38-42:
> **G02-M1 — DS-20: the oracle's self-check measures the shipped book's corridor reach differently from the contract.** Bug/Error.
> - File: solution/solve.py:618-631 (`book_reach`, changed in this build); printed at :818-822.
> - Quote: api_contract.md:49-50 "The depot of a project is at position 0." and :57 (closed links are removed before any other rule); judge.toml:66 R5 "an open link spans more corridor positions than any link of the shipped book".
> - Evidence: `book_reach` counts closed links and skips depot links, so it reports the shipped book's widest link as 42; counted the contract's way (open links, depot at 0) the figure is 51. The oracle log says "widest open link spans 82 corridor positions against 42 in the shipped book" (oracle-1 agent/oracle.txt:14). The assertion at :817 still holds (82 > 51) and no test or document changes, but the printed comparison states a wrong shipped figure for the very property R5 asks about.
> - Fix: In `book_reach`, skip links listed under `[closed] links` and give the depot position 0, so the shipped figure reads 51.

v3.md:166-170:
> ### G02-M1 🟡 minor — DS-20 (oracle self-check measures corridor reach differently from the contract)
> - solution/solve.py:618-631 (changed lines) counts the span of every row of links.jsonl whose two ends both have a layout row: it keeps closed links and skips links at the depot. api_contract.md:49-50 "The depot of a project is at position 0." and :57 "A closed link is removed from the book before any other rule here is applied. Every other link is open." judge.toml:66 (R5) asks for "an open link spans more corridor positions than any link of the shipped book".
> - Measured (my script, read-only on the copy): oracle `book_reach` shipped `(52, 10, 42)`, built `(85, 30, 82)`; contract counting (depot 0, closed removed) shipped widest open link `51`, built `82`. Open non-depot links in the shipped book max out at 16, so the oracle's 42 comes from closed links.
> - Effect: the assertion at :817 still holds (82 > 51), so the oracle still meets R5, but the line it prints at :818-822 (...) states a wrong shipped figure. No test or document changes; Bug/Error (small).
> - Fix: in `book_reach` skip links listed in `[closed] links` and give the depot position 0 so the shipped figure reads 51.

## My own count of the shipped book (contract rules)
A separate script (`/tmp/ccq-p12v3/count.py`, read-only on the QC copy's environment/ci) follows api_contract.md:48-51 (depot at 0, other sites ranked 1.. by `[corridors] order` place, then slot) and :56-57 (closed links removed first). It found 2904 layout rows, 0 depot rows in layout.tsv, 146 closed links, and 5 links with an end that has no position. **Widest open link = 51** (project P9582, link L81912, S604-S144). This matches QC's 51, so no PAUSE. Widest open non-depot link = 16, which agrees with QC.
The new `book_reach`, pulled out with ast and run on the shipped book, returns `(52, 10, 51)`.

## The fix
I made one edit, in WORK/solve_body.py `book_reach` only, and regenerated solution/solve.py with WORK/build_solve.py. Before the edit, regeneration reproduced the old solve.py byte for byte. No other function changed, and nothing in tests/, environment/, instruction.md, judge.toml, reward.toml or task.toml changed. TRUTH.md was the last bundle edit, rewritten by finalize_truth.py. Only line 180 (`solve_py_sha256`) changed, and it now equals `shasum -a 256 solution/solve.py` = `22ca6e5c…a3c9a8`. `grep -w` found no 42 or 82 figure in TRUTH.md, so nothing else needed correcting.
The code lines moved. The assertion that QC cites at :817 is now at solve.py:827, and the print is at :828-832.

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| G02-M1 DS-20 | solve.py `book_reach` (:610-641): skip `[closed] links`, depot rank 0, skip depot layout rows | api_contract.md:48-51, :56-57; judge.toml:66 R5; assertion :827 built > shipped on all three figures | fixed: shipped 51 (was 42), built 82; assertion holds in oracle x3 |
| DS-22 | TRUTH.md:180 solve_py_sha256 by script | sha256 of new solve.py | matches |

### diff -u solution/solve.py (QC v3 copy -> BUNDLE)
```diff
--- /Users/mac/Desktop/Terminal Bench/QC/copies/7304a6f/cold-chain-backbone-quote/solution/solve.py	2026-10-28 12:31:05
+++ /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/solution/solve.py	2026-10-28 15:55:34
@@ -608,23 +608,33 @@
 
 
 def book_reach(book: Path) -> tuple[int, int, int]:
-    """Largest site count and cold-room count of one project, and the widest corridor-position span of a link."""
+    """Largest site count and cold-room count of one project, and the widest corridor-position span of an open link."""
     sites: dict[str, int] = {}
     cold: dict[str, int] = {}
+    depots: set[tuple[str, str]] = set()
     with open(book / "sites.csv", newline="", encoding="utf-8") as handle:
         for row in csv.DictReader(handle):
             sites[row["project"]] = sites.get(row["project"], 0) + 1
             cold[row["project"]] = cold.get(row["project"], 0) + (row["role"] == "cold_room")
-    order = tomllib.loads((book / "access_rules.toml").read_text(encoding="utf-8"))["corridors"]["order"]
+            if row["role"] == "depot":
+                depots.add((row["project"], row["site"]))
+    rules = tomllib.loads((book / "access_rules.toml").read_text(encoding="utf-8"))
+    order = rules["corridors"]["order"]
+    closed = set(rules.get("closed", {}).get("links", []))
     places: dict[str, list] = {}
     with open(book / "layout.tsv", newline="", encoding="utf-8") as handle:
         for row in csv.DictReader(handle, delimiter="\t"):
+            if (row["project"], row["site"]) in depots:
+                continue
             if row["corridor"] in order and row["slot"].strip().isdigit():
                 places.setdefault(row["project"], []).append((order.index(row["corridor"]), int(row["slot"]), row["site"]))
     rank = {(pid, site): k + 1 for pid, rows in places.items() for k, (_c, _s, site) in enumerate(sorted(rows))}
+    rank.update({depot: 0 for depot in depots})
     span = 0
     for line in (book / "links.jsonl").read_text(encoding="utf-8").splitlines():
         row = json.loads(line)
+        if row["link"] in closed:
+            continue
         a, b = (row["project"], row["a"]), (row["project"], row["b"])
         if a in rank and b in rank:
             span = max(span, abs(rank[a] - rank[b]))
```

### diff -u solution/TRUTH.md (QC v3 copy -> BUNDLE)
~~~diff
--- /Users/mac/Desktop/Terminal Bench/QC/copies/7304a6f/cold-chain-backbone-quote/solution/TRUTH.md	2026-10-28 12:58:01
+++ /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/solution/TRUTH.md	2026-10-28 15:55:48
@@ -177,6 +177,6 @@
 instance_id: cold-chain-backbone-quote
 task_name: terminal-bench/cold-chain-backbone-quote
 fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680
-solve_py_sha256: 95357e7b9606c85e29b998e53ca6c19a4b9bb06a0cfb9bf2538ddf2ebfe10166
+solve_py_sha256: 22ca6e5c14cb080b8aaff3ecfd8b8151ca9cb3719329e5500dbfbd6288a3c9a8
 language: python
 ```
~~~

## Check 1: diff -rq BUNDLE vs QC v3 copy
```
Files /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/solution/TRUTH.md and /Users/mac/Desktop/Terminal Bench/QC/copies/7304a6f/cold-chain-backbone-quote/solution/TRUTH.md differ
Files /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote/solution/solve.py and /Users/mac/Desktop/Terminal Bench/QC/copies/7304a6f/cold-chain-backbone-quote/solution/solve.py differ
```
Only solution/solve.py and solution/TRUTH.md differ. The `diff -u` of both files is shown above.

## Check 2: precheck
```
NOTE AL-27 RULE_COVERAGE.md 42 rule rows
NOTE EVIDENCE-MAP 25 rows
NOTE SELF-CHECKS missing: /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cold-chain-backbone-quote/SELF_CHECKS.md (P2 v5 Phase 8 step 3b: vacuity probe, TS-16 negatives, promise table, literal table)
-- counts (no cap; kit floors 10 tests, 8 criteria)
tests 33 (tests_qc A3 count), judge criteria 13
PRECHECK CLEAN
```
Exit code 0. The last line is `PRECHECK CLEAN`. The bundle has no `__pycache__` and no .pyc files (`find` count: 0).

## Check 3: lever unchanged (tests/ byte-identical to QC v3 copy)
```
$ diff -r BUNDLE/tests QCcopy/tests
rc=0
```
tests/ is identical byte for byte. So the six wide-book lever checks (24/108 pts) and every hidden book are untouched.

## Check 4: Docker gate block (runs/v3_chain.sh, copies from live kit exe_copy.py plain + --owner-only, warm verifier image built first)
G=/tmp/ccq_v3_gate_20261028T155638-6577. Runs were one at a time in one nohup chain, under the lock, with at most 1 other task container up. Each reward below was read from that trial's result.json:
```
=== oracle-1 start 15:57:47
rc oracle-1 0
RESULT oracle-1 /tmp/ccq_v3_gate_20261028T155638-6577/jobs_oracle-1/oracle-1/main__EKEkFTT/result.json
REWARD oracle-1 {'reward': 1.0} exc None
=== oracle-1 end 16:03:03
=== oracle-2 start 16:03:03
rc oracle-2 0
RESULT oracle-2 /tmp/ccq_v3_gate_20261028T155638-6577/jobs_oracle-2/oracle-2/main__NMxGC7o/result.json
REWARD oracle-2 {'reward': 1.0} exc None
=== oracle-2 end 16:08:21
=== oracle-3 start 16:08:21
rc oracle-3 0
RESULT oracle-3 /tmp/ccq_v3_gate_20261028T155638-6577/jobs_oracle-3/oracle-3/main__Heca3p6/result.json
REWARD oracle-3 {'reward': 1.0} exc None
=== oracle-3 end 16:13:54
=== owner-1 start 16:13:54
rc owner-1 0
RESULT owner-1 /tmp/ccq_v3_gate_20261028T155638-6577/jobs_owner-1/owner-1/owner__f8838ga/result.json
REWARD owner-1 {'reward': 1.0} exc None
=== owner-1 end 16:19:56
=== nop-1 start 16:19:56
rc nop-1 0
RESULT nop-1 /tmp/ccq_v3_gate_20261028T155638-6577/jobs_nop-1/nop-1/main__hvSbib4/result.json
REWARD nop-1 {'reward': 0.0} exc None
=== nop-1 end 16:25:19
ALL_DONE
```
Results: oracle x3 = 1.0, 1.0, 1.0; owner-only x1 = 1.0; nop x1 = 0.0. No trial raised an exception.

New self-check line, oracle-1 agent/oracle.txt:14 (copy at OUT/oracle-1_oracle.txt):
> check built far-reaching book ok: 2 projects; largest project 85 sites and 30 cold rooms against 52 sites and 10 cold rooms in the shipped book; widest open link spans 82 corridor positions against 51 in the shipped book; finished in 0.22 s of the 18 s limit, quotes recomputed from the raw files and every cold room joined to the depot

The built book still beats the shipped book on all three figures (85 > 52 sites, 30 > 10 cold rooms, 82 > 51 widest open link), so the assertion at :827 passed in all three oracle runs.

## Check 5: Tasks_INPUT sync
```
$ cp -Rp BUNDLE/solution/solve.py BUNDLE/solution/TRUTH.md -> Tasks_INPUT/cold-chain-backbone-quote/solution/
$ diff -rq BUNDLE Tasks_INPUT/cold-chain-backbone-quote
rc=0
```

## Check 6: KEPT
OUT/KEPT.md is a byte-for-byte copy of QC/reports/cold-chain-backbone-quote/KEPT.md (`cmp` reports them the same). The G05-3 row is unchanged.

## Lessons for the master
- An oracle self-check that prints a figure tied to a judged rule should count with the contract's own rules (closed-first, depot at 0). It should not use a looser helper, because the assertion can pass while the printed number is still wrong.
- When solve.py is generated, regenerate it first, before any edit. That shows the source and the output still match, and the diff then covers only the intended function.
