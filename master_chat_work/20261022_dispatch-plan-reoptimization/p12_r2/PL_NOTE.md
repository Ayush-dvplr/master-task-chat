# PL note: dispatch-plan-reoptimization (eec3fbe), P12 r2

QC v2 found 3 fails (IN-15, JD-7, AL-28), 1 minor and 3 warns. We agree with all 3 fails, the minor and 2 of the warns, and fixed those 6. One warn is answered by the judge channel and is kept as is.

## False positive (rebuttal)
- TS-19 "shipped artifacts in /app/out are only checked for existence": the rule itself allows this. 03_Tests_QC.md:50 says "a promise may legitimately be graded by a judged criterion instead ... Flag a promise nothing grades at all, never one the judged channel handles." The judge grades the five shipped figures from the final reply, and every hidden-set group grades the same `solver.py` that must have produced `/app/out`. Adding a shipped re-run check would also push shipped read checks past the 5 percent cap of our common rule 10. No change.

## Kept minors
- None besides the warn above. Process rows (oracle x5 instead of x3, warn approval) follow Ayush's decisions; X1 (binary files skipped by the script) is an information line, QC already checked them by hand.

## UNSURE questions
- None.

## What changed (for the re-run)
- IN-15: the shell/network negative no longer fires on `__import__` or `importlib.import_module` by themselves. They only count when they load a module the instruction already forbids (for example `__import__("subprocess")`).
- JD-7: the reference solver is split into short per-stage functions (longest is now 40 lines, was 423 and 334). All outputs are byte for byte the same on the shipped set and the four hidden sets.
- AL-28: the writes-outside negative now watches only scratch space, shared temp and the output's parent. Changes under `/app/data` are penalised once, by the judge criterion alone.
- TS-16 minor: hidden sets H2 and H4 now re-author the PDF (holding rate, shortfall penalty), the DOCX (energy surcharge) and the XLSX (capital budget, committed volumes), so hardcoding those figures fails.
- TS-16 warn: the clock and process probes also catch `time.monotonic`, `time.perf_counter`, `time.localtime`, `date.today`, `datetime.today`, `os.exec*`, `os.spawn*`, `os.posix_spawn`, `os.fork`, `multiprocessing` and `pty`, all already forbidden in the instruction.
- TS-19 warn: the instruction now says each run on one export set must finish within 400 seconds.
