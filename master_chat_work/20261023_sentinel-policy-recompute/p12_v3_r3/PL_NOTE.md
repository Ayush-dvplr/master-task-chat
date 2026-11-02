# PL_NOTE sentinel-policy-recompute P12 v3 r3 (7e07424)

## False positives

none. All nine QC v3 / master items rechecked REAL (OUT/RECHECK_FIX.md).

## Kept items

- X1 (structure_qc warn): 8 files skipped as binary (7 parquet/xlsx inputs and tool.zip). They are genuine binary formats the task requires; no text file carries a dash or author word (precheck leak audit clean). Evidence: `structure_qc.py` SUMMARY "17 pass, 1 warn, 0 fail", exit 0.

## Accepted cost (recorded, not a keep)

- Trap survival v0 condition FAIL: v0 adapted agent program (harden_r1, reflex build) 5/31 = 0.161 before, 12/33 = 0.364 after (bound 0.181). Cause: +3 the init/set rebuild check (F1, its init/set are right), +4 the five-way shipped split (M1, it is right on every shipped artifact). Ayush chose "Split as directed" on 24 Oct 19:53 with these numbers. Every lever variant keeps 0.939 of its (F1-adjusted) loss; separating hidden cases all kept, plus OV-K042-c0.
- g10 FAIL (report only): L7 per-term 0.242 and L1 controls 0.152 alone (< 0.25); L2, L7, L1 all-but-one rows overall 79.8 / 82.9 / 87.4 (>= 70). Before this round the same gate failed (L7 0.258, L1 0.161). No levers added (out of scope).

## UNSURE questions

none.

## Open note for the master

- instruction.md uses the word "decoy(s)" twice ("Several of those files are superseded, retired, or decoys ...", "never a superseded, retired, or decoy value"). Not in this round's directions and instruction QC passed (5 pass); flagged under Lessons.
