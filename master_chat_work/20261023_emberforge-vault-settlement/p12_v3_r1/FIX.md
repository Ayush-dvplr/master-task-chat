# P12 v3 r1 FIX: emberforge-vault-settlement, board 5336aa7 (24 Oct 2026, IST)

Bundle `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement`.
Tree sha b4c791a54298 before, 92b64997a5c9 after. QC kit HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e.

## 1. Original sentence and source

Deleted in harden lp1 r1 (`20261023_emberforge-vault-settlement/harden_lp1_r1/evidence/doc_edits.py:88-93`).
Pre-harden text at
`/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_emberforge-vault-settlement/harden_r2/evidence/bundle_before_r2/environment/data/rulebook_identity.md:35-36`
(same text in `QC/copies/67848e1/emberforge-vault-settlement/environment/data/rulebook_identity.md:35-36`):

> Two entries filed under the same handle on either side of a rename or merge
> therefore belong to different canonical smiths.

Restored word for word at the end of I3.

## 2. Diffs

```diff
--- environment/data/rulebook_identity.md (before)
+++ environment/data/rulebook_identity.md (after)
@@ -32,6 +32,8 @@
 Canonical identity is a function of the day as well as the handle. A handle
 filed before a rename or a merge takes effect resolves to whatever it resolved
 to on that earlier day, and a handle filed after resolves to the later result.
+Two entries filed under the same handle on either side of a rename or merge
+therefore belong to different canonical smiths.
 
 ## I4. Retirement
```

```diff
--- environment/data/rulebook_salvage.md (before)
+++ environment/data/rulebook_salvage.md (after)
@@ -16,7 +16,8 @@
 canonical smith on days strictly before the salvage's own day. The canonical
 smith is the one the salvage's own handle resolves to on the salvage day, and
 the forge entries are read against that canonical smith whatever handles they
-were filed under. Each artifact family carries its own window.
+were filed under, each forge entry's handle resolved on the forge's own day
+(I3). Each artifact family carries its own window.
 
 A salvage whose source forge falls outside that window is not settled and
 returns nothing.
```

No other bundle file changed (tests/, solve.py, instruction.md, judge untouched).

## 3. S2 decision: clause added

The restored I3 sentence speaks of the same handle on either side of a change. The a7
case is two handles: L0016 filed as S008 on day 117, salvage L0026 filed as S030-x on
day 165 (merge S008->S030 day 100, rename S030->S030-x day 129). S2's "whatever handles
they were filed under" still lets a careful reader pool every forge whose handle maps to
the salvage-day canonical, which is the salvage-day reading. So the one clause from the
master's direction was added. It cites I3 by id, as S5 already cites A4. The live-window
wording (L6) is untouched.

## 4. clerks_digest.md:10-12

"A salvage is credited when the forge it names is one of the three most recent forges of
the same artifact family that the vault settled for the salvage's smith." It names no
day and the file calls itself desk shorthand (lines 3-4). It does not state the
salvage-day reading as a rule. TRUTH.md:45-46,51-52 already says the rulebooks govern.
Not edited.

## 5. Lever safety (LEVER_RULES W1, W2, W6)

| lever | W1 no trap explanation | W2 rule in governing file | W6 no worked example where readings differ |
|---|---|---|---|
| L7 H1/H5 unit charge | holds; rulebook_charge.md untouched | holds; unchanged | holds; none added |
| L3 A4/S5 cap release | holds; A4/S5 untouched | holds; unchanged | holds; none added |
| L6 S2 live window | holds; the clause is about which day a handle resolves on, says nothing about live, credited or redeemed forges | holds; S2 still governs | holds; no example added |

Measured: all lever variants lose the same points before and after (table below).

## 6. IN-15 / IN-16 (live kit 01_Instruction_QC.md:45-46)

- IN-15: pass. The changed paragraphs describe data meaning, not a rule of engagement;
  the judge's instruction-following criteria are unaffected.
- IN-16: pass. The graded question (S2 window handle day; checks seven whole_* and
  test_live_window_refusals) had two readings. I3 sentence plus the S2 clause now pick the
  forge day. The I3 sentence agrees with I2 and I4 and stood in the QC copy 67848e1.
  instruction_qc.py exit 0, warns 0 (it checks prose mechanics only).
- Always 14 side effects:
  - DS-22: TRUTH.md:32-40,48-55 still true ("identity is a function of the day (I2 to I4)"). OK.
  - TS-17, TS-24: n/a, no test or code change.
  - AL-18: tests/test_output.py RULEBOOK_TEXTS (:1467; identity :1959, salvage :2065) now
    hold the old rulebook text. Used only at :2196 to write rulebooks into hidden corpus
    dirs; nothing hashes /app/data against them and solve.py reads no .md, so grading is
    unaffected. tests/ is out of scope, see Lessons.
  - AL-19: n/a.

## 7. Trap table (tests channel, local scorer `score_local.py`, loss of P=54)

| variant | before | after |
|---|---|---|
| oracle | 0 | 0 |
| L7_rebased | 32 | 32 |
| L3_rebased | 38 | 38 |
| L6_rebased | 38 | 38 |
| no_reinstate | 35 | 35 |
| no_apprentice_relief | 20 | 20 |
| salvage_day_window (new) | 38 | 38 |

Identical row by row. salvage_day_window = oracle with the window forge-handle
resolution moved to the salvage day (one change, mirrors agent_settle.py:733-735); it
fails the seven whole_* checks and test_live_window_refusals. JSON in `before/`, `after/`.
The variant is `WORK/wrong/salvage_day_window.py` (built by `WORK/wrong/make_salvage_day_window.py`).

xref_check: 61 entries, 0 findings before and after.

## 8. PRECHECK (after)

```
== kit 71a653b2 on /Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement
-- structure_qc exit=0 warns=0
-- instruction_qc exit=0 warns=0
-- tests_qc exit=0 warns=0
-- judge_qc exit=0 warns=0
-- gaps the kit scripts miss
-- author notes in environment/ (leak audit)
-- caps (kit warns above 35)
tests 22 (tests_qc A3 count), judge criteria 8
PRECHECK CLEAN
```

## 9. Docker (tests only, copies from live kit exe_copy.py)

Root `/tmp/emberforge-p12v3r1-20261024T121032-23e2` (plain, owner = `--owner-only`).
Chain `docker_chain.sh`, log `docker_chain.log`, warm image `warm-emberforge-vault-settlement` (warm.log).

| job | copy | agent | reward | errors |
|---|---|---|---|---|
| oracle-1 | plain | oracle | 1.000 | 0 |
| oracle-2 | plain | oracle | 1.000 | 0 |
| oracle-3 | plain | oracle | 1.000 | 0 |
| owner-1 | owner (--owner-only) | oracle | 1.000 | 0 |
| nop-1 | plain | nop | 0.000 | 0 |

Chain ran 12:10:40-12:15:19, ended ALL_DONE; at most 2 Docker jobs ran at once.

## 10. File hashes (sha256, only scope files differ)

| file | before | after |
|---|---|---|
| environment/data/rulebook_identity.md | 4bd6b34f7dbb03407854422cb7b03d417f3ccf9eef3fd194b91d270081716dda | 5cd5bd4617186eb76ecca2845dc105baa95ce66a72cd719ea47f3cd4e1c2718d |
| environment/data/rulebook_salvage.md | c1427f4ca7a51dcbe75f7c51cfa8df8376368b183ef9cef63d7c7b216459e3bc | 81e84a498a5db9ad71266328419beb89a0fe9cdef51e653201c74eb4d993275d |

The other 33 files are identical (`before/file_hashes.txt` vs `after/file_hashes.txt`).
TRUTH.md has no hash or line count covering these files, so it was not changed.

WORK updated: DESIGN.md (line 66 note, new section "P12 v3 r1"), LEVERS.md (new section,
not a lever, salvage_day_window measured), QC_DEFENCE.md:100 (I3 no longer in removed
list), wrong/salvage_day_window.py + make_salvage_day_window.py, TODO.md, LOG.md. XREF.md
holds no I3 text, unchanged.

## Lessons for the master

- Rulebook edits leave tests/test_output.py RULEBOOK_TEXTS (:1467) stale; COMMON_RULES Always 6 says regenerate, but the scope lock forbids tests/ | template_change: prompts/templates/_COMMON_RULES_v3.md:37 and the P12_recheck_fix_v3.md scope lock: allow `WORK/embed_rulebooks.py` regen of tests/test_output.py RULEBOOK_TEXTS when environment/data rulebooks change.
- A closing sentence deleted as a "giveaway" was the only tiebreak for a graded question | no change: LEVER_RULES W1 already separates trap explanation from rule statement; harden r1 misapplied it.
