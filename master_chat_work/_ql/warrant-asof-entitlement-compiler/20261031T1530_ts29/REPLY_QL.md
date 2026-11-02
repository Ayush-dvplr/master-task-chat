Hi, thanks for the TS-29 check. I compared it with the bytes we pushed (tree 97f574111b58), and this code path is not in our version:

- Our `tests/test_output.py:29716-29717` has `_CALL_SECONDS = 450` and `_BUDGET_SECONDS = 2400`, and `task.toml:22` has `timeout_sec = 2700.0`.
- There is no `_GradingAbort` class and no `_abort` call in our file.
- Our `_invoke` (`:29868-29900`) returns `None` once the budget is spent (`left <= 1`), and each call waits at most `min(_CALL_SECONDS, left)`. So a hanging tool makes the remaining checks score False, the trial still gets a (low) score, and the worst case stays near 2,400 s, under the 2,700 s verifier limit.

So the abort path, the 5,400 s budget and the 6,000 s timeout look like they came in with an edit made after QC. If your edited copy is the one we should continue from, please send it (zip with the bundle) and we will apply your suggested fix on those bytes: on a timeout or spent budget, mark the tool failed and let every remaining check return False without calling it again, keep `_GradingAbort` only for authoring errors, and keep the worst case under the verifier timeout. Then we re-run QC and a fresh trajectory.
