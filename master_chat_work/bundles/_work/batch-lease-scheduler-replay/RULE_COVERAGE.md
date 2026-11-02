# RULE_COVERAGE (G11)

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| lease ticks govern deadline s+ticks | replay_contract.md:11 | HBFROMDL | 22 |
| retry delay: ready at t+delay | replay_contract.md:11 | DELAYOFF | 22 |
| pool preempt flag | replay_contract.md:12 | PREEMPTALL | 22 |
| ids compared as numbers (dispatch tie) | replay_contract.md:9 | IDTEXT | 16 |
| ids compared as numbers (worker choice) | replay_contract.md:9 | WORKERTEXT | 20 |
| blank lines in events.jsonl carry no meaning | replay_contract.md:9 | BLANKCRASH | 6 |
| redelivered copy = identical id and content | replay_contract.md:25 | REDUP | 21 |
| attempt ends -> dead at retry_limit+1 | replay_contract.md:38 | LIMITOFF | 22 |
| lost units = work minus remaining at attempt end | replay_contract.md:38 | FW3 | 11 |
| preemption keeps attempt and remaining | replay_contract.md:40 | PREFAIL | 22 |
| eviction keeps attempt and remaining | replay_contract.md:40 | EVICTFAIL | 22 |
| cascade to every non-terminal dependent | replay_contract.md:42 | FW5 | 22 |
| cascade (and no release) on dead/cancelled parent | replay_contract.md:42 | ANYTERM | 22 |
| every whole-number time is an instant | replay_contract.md:46 | LAZY | 22 |
| phase 1 completion before external events | replay_contract.md:48 | FW2 | 22 |
| phase 1 completion before phase 2 expiry | replay_contract.md:49 | EXPFIRST | 16 |
| completion only for the current run | replay_contract.md:48 | FW1 | 22 |
| phase 3 events in ascending id | replay_contract.md:50 | EVDESC | 13 |
| phase 4 dispatch once per instant | replay_contract.md:51 | PEREVENT | 22 |
| checkpoint state after phase 4 | replay_contract.md:53 | SNAPBEFORE | 6 |
| worker_down evicts and frees the worker | replay_contract.md:60 | DOWNKEEP | 23 |
| terminal job events audited finished | replay_contract.md:61 | FINLAST | 2 |
| release at submit recorded | replay_contract.md:62 | NORELREC | 5 |
| boost applies to any non-terminal job | replay_contract.md:63 | BOOSTSUB | 22 |
| cancel lost = work minus current remaining | replay_contract.md:64 | FW3b | 17 |
| stale_attempt row before not_running | replay_contract.md:65 | PRECSWAP | 11 |
| stale token audited, no effect | replay_contract.md:65 | STALE | 22 |
| not_running audit for preempted job | replay_contract.md:66 | FW4 | 22 |
| heartbeat renews to t+ticks | replay_contract.md:67 | HBNOP | 22 |
| dispatch order priority then job id | replay_contract.md:72 | SUBORDER | 22 |
| lowest idle worker id | replay_contract.md:74 | WORKERHI | 22 |
| victim tie: latest start | replay_contract.md:75 | VICEARLY | 21 |
| victim tie: highest job id | replay_contract.md:75 | VICLOWID | 20 |
| checkpoint remaining interpolated | replay_contract.md:83 | FW2R | 6 |
| executed counted through last checkpoint | replay_contract.md:87 | EXECLAST | 6 |
| edges ordered by parent then child | replay_contract.md:90 | EDGEORDER | 5 |
| final.other counts non-terminal incl unsubmitted | replay_contract.md:94 | OTHERSUB | 6 |
| dispatch_sha256 line format | replay_contract.md:94 | SHAFMT | 6 |
| output deterministic across hash seeds (parsed JSON equal) | replay_contract.md:80 | HASHORDER | 24 |
| refusal order: MISSING_INPUT file order | replay_contract.md:100 | MISSREV | 1 |
| MISSING_INPUT names the file | replay_contract.md:100 | MISSDETAIL | 1 |
| INVALID_POLICY before UNKNOWN_ENTITY | replay_contract.md:98 | POLAFTER | 1 |
| UNKNOWN_ENTITY for undefined worker | replay_contract.md:102 | UNKWORKER | 1 |
| EVENT_ID_CONFLICT detected | replay_contract.md:103 | NOCONFLICT | 1 |
| EVENT_ID_CONFLICT before DEPENDENCY_CYCLE | replay_contract.md:98 | CYCLEFIRST | 1 |
| DEPENDENCY_CYCLE detected | replay_contract.md:104 | NOCYCLE | 1 |
| refusal line on standard output | replay_contract.md:106 | STDERR | 5 |
| refusal status 2 | replay_contract.md:106 | EXIT1 | 5 |
| refusal writes no document | replay_contract.md:106 | WRITEFIRST | 5 |
| python -m leasebook runs main | replay_contract.md:80 | NOMAIN | 1 |
| __version__ equals pyproject version | replay_contract.md:110 | VERSION | 1 |
| shipped test files unchanged | replay_contract.md:110 | TESTEDIT | 1 |
| selftest.json counts from the archive run | replay_contract.md:112 | SELFTEST | 1 |
| build_report files sorted | replay_contract.md:114 | UNSORTED | 1 |
| build_report archive_sha256 | replay_contract.md:114 | SHA | 1 |
