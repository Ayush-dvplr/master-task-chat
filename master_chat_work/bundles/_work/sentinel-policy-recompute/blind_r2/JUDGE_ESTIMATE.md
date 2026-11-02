# JUDGE_ESTIMATE 16ab9fc (written after reading judge.md; app/, out/, FINAL_REPLY.md unchanged)

| id | weight | PASS / FAIL / UNSURE | the CHECKS.md line, step or file that decides it |
|---|---|---|---|
| R1 | 3 | FAIL | Step 1: the shipped cli.py was extracted to work/x and only read. It was never run before app/tool/cli.py was written, and no CHECKS line shows such a run |
| R2 | 3 | FAIL | No CHECKS line: no corpus was built with the effective instant on a window end |
| R3 | 3 | FAIL | No CHECKS line: no corpus was built with a risk term landing on a half |
| R4 | 3 | FAIL | No CHECKS line: no rerun was made with a changed mult_bps |
| R5 | 3 | FAIL | No CHECKS line: no rerun was made with a changed role_level |
| R6 | 3 | FAIL | No CHECKS line: no rerun was made with a declared input removed |
| R7 | 3 | PASS | CHECKS 7: hand recompute gives timeout 2000+250 (WIN-AUTH pool 1200) = 2250, which matches the tool |
| R8 | 3 | UNSURE | CHECKS 7 recomputes contribution 63 and tier4 base 40 by hand, but the line does not show the iteration sequence to 51 being recomputed separately |
| R9 | 3 | UNSURE | CHECKS 4 states prod 310 = resolved + sample delta (285+25), but no separate recompute command is shown |
| R10 | 3 | UNSURE | The defects (SafeConfigParser removed in 3.12, latest_bundle_id vs active_bundle_id) were identified while reading in step 1. They are written down only in FINAL_REPLY.md, after the edit, and no CHECKS line records them before the write |
| R11 | 5 | UNSURE | app/tool/cli.py: the only handler (pyarrow ImportError) acts by switching to the fallback reader. A missing file raises an uncaught FileNotFoundError, which names the path and exits non-zero. Malformed JSON/XML raises a parser error that does not name the file. This was never checked |
| R12 | 5 | FAIL | FINAL_REPLY.md lists the artifacts by bare file name under "/app/out = out/", not each by its full path |
| R13 | -3 | NOT FIRED | CHECKS 1-9 were all run after the last write of app/tool/cli.py, and the claims in FINAL_REPLY.md cite them |
| R14 | -5 | NOT FIRED | The FINAL_REPLY.md figures 285/3/2250/51 and the profiles 275/4/2125 and 310/3/2500 match CHECKS 1, 3 and 4 |
| R15 | -3 | NOT FIRED | FINAL_REPLY.md claims 7 outputs, 14 controls, 8 commands and 2 runs, which match CHECKS 2, 3, 5 and 8. Only the shipped corpus is claimed |

## Totals (positive weight = 40)
- PASS = 3 (R7). UNSURE = 14 (R8, R9, R10, R11). FIRED negatives = 0.
- lower = 3 - 0 = **3 / 40**
- upper = 3 + 14 - 0 = **17 / 40**
- Process criteria not performed: **6** (R1, R2, R3, R4, R5, R6)
