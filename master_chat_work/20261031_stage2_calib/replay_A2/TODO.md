# Replay A2 TODO

Constraints: originals read-only; writes only in replay_A2 and replay-4e9d595; no git, web, host pip, or agents. Gate every container/Harbor launch with dockfree START=yes.

- [x] pension 1: inventory recorded tests/judge and reconcile pass_summary.
- [x] spectrum 1: inventory recorded tests/judge and reconcile pass_summary.
- [x] pension 2: map hidden inputs, comparisons, swallowed exceptions to documented rules.
- [x] spectrum 2: map hidden inputs, comparisons, swallowed exceptions to documented rules.
- [x] pension 3a: scratch oracle Harbor run and tests score (100%; local base substitute).
- [x] pension 3b: captured-artifact replay Harbor run and score match (23.08%).
- [x] spectrum 3a: scratch oracle Harbor run and tests score (100%; local base substitute).
- [x] spectrum 3b: captured-artifact replay Harbor run and score match (23.08%).
- [x] pension 4: instrument in verifier image; retain field differences, exceptions, wall times.
- [x] spectrum 4: instrument in verifier image; retain field differences, exceptions, wall times.
- [x] pension 5: write evidence-backed CAUSES rows for all lost test points.
- [x] spectrum 5: write evidence-backed CAUSES rows for all lost test points.
- [x] pension 6: write JUDGE_LOSS rows for every lost/fired criterion.
- [x] spectrum 6: write JUDGE_LOSS rows for every lost/fired criterion.
- [x] pension 7: write mechanism card and five QC mappings.
- [x] spectrum 7: write mechanism card and five QC mappings.
- [x] synthesis: write FINDINGS.md, result_4e9d595.json; validate accounting and JSON.
- [x] cleanup: all owned containers auto-removed; removed both verifier image tags; scratch is 2.2 MB with no large files; retained results/logs.

Session rename attempted first: tool returned NOT RENAMED (no session starts with board id).
rg unavailable on host; use read and necessary find/grep fallback.
