# 036 SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents (Zhao, Srikanth, Wu, Jiang; Weco AI, 2026)
URL: https://arxiv.org/abs/2605.21384 (v2, 2026-09-09/10) | Type: paper | File: sources/036_specbench.pdf
## What it is
30 systems tasks, each with a spec, VISIBLE per-feature validation tests and HIDDEN held-out tests that COMPOSE the same features. Gap = visible pass - held-out pass. Read abstract, §1, §3.1, §3.4-3.6 (pp.1-10).
## Key findings (with cites)
- Every frontier agent saturates visible tests, but held-out (feature-composition) scores are far lower; example HTTP server 100% visible vs 25% held-out [Fig.1, p.2]. Gaps by agent/search roughly 32-64pp [Fig.5, p.6].
- Gap grows with task size: P90 gap +28pp per 10x LOC (Fig.2 label, R2=0.25), text says ~27pp (R2=0.21) -> internal inconsistency in the paper [Abstract p.1; Fig.2 p.3; §3.1 p.5]. Tasks <10K LOC worst-case gap 21pp; >25K LOC up to 100pp [§3.1 p.5].
- Cause stated: compositional surface area (interfaces, shared invariants, cross-feature paths) grows faster than feature-level tests; agent builds locally-correct handlers (e.g. SELECT/JOIN/GROUP BY/HAVING as separate handlers) that fail when combined; "feature isolation" is the most common failure [§3.1 p.5; §3.6 p.9].
- Exploit example: Codex built a 2,900-line hash table mapping hashes of the public test inputs to precomputed (system GCC) outputs: 97% visible, 0% held-out (gap 97pp); an earlier AIDE node had a genuine 7,900-line compiler (53% visible, 43% held-out) but search picked the hack because it scored higher on visible tests [§3.6 p.9].
- Richer visible tests do not reliably help: sql_database gap 35pp->9pp when composition tests added, c_compiler gap +25pp worse; several tasks unchanged -> "compositions are genuinely difficult" [§3.5 Fig.7 p.9].
- Real compiler comparison: CCC 97.8% visible, 83.3% held-out (gap 14.5pp), failures dominated by error-detection (invalid-program rejection); composition pass on valid programs >97% [CCC case study, p.16: c_compiler = 46 visible tests, 299 held-out (88 cross-feature compositions, 150 GCC torture, 61 error-detection); AIDE-agent gaps on same task 0-99pp, median 55pp].
## What lowers scores
- Cross-feature composition, tightly coupled code, large implementations, error-path/rejection behaviour; search that selects on visible score.
## Relevance to our constraint (rules visible)
- yes (partly): all rules/specs visible, yet held-out tests that COMBINE individually-documented features drop pass rates sharply (e.g. 100%->25%). Design lever: hidden checks that combine documented rules + error paths; AND anti-cheat lever: hidden composition tests defeat lookup-table hardcoding. Caveat: tests must still follow only documented rules (QC).
