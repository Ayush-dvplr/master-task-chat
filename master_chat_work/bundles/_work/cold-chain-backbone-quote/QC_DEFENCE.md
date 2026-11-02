# QC_DEFENCE: cold-chain-backbone-quote

Rule quotes are from checks.json (qc_reverse/A) pass conditions with kit file:line. Fallbacks name the QC_FIX_PLAYBOOK_v2 row and its DO fix.

## LV-CC-1 exact minimum-cost network
| rule | quoted | why it passes | fallback (playbook row: DO fix) |
|---|---|---|---|
| IN-15 (01:45) | "Judge whether an agent could tell, before acting, whether a given action complies." | api_contract.md states the network rule, the quote formula and "The package quotes each project at the minimum quote over all networks." in plain sentences; the instruction points to the contract for every rule. | IN-15: add the missing sentence to api_contract.md (the governing file), never to the instruction as a hint. |
| IN-16 (01:46) | "you must show all three parts or you do not have a finding" | One reading: minimum over all networks of link costs plus activation of activated sites. Activated sites are defined, costs are positive integers, closed links are excluded by name. | IN-16: write both readings in EVIDENCE_MAP, add the settling sentence to the contract. |
| IN-17 (01:47) | instruction states WHAT, no recipe or announcement | instruction names outputs and exactness; no sentence says the heuristic is wrong or what method to use (G-8). | IN-17: delete the announcing sentence. |
| AL-1 (05:21) | "Everything graded is promised." | C02, C08-C10, C19, C20 grade module_core keys stated in the contract's Outputs section; fresh-book runs are promised ("the package is run on other quote books of the same layout within the stated limits"). | AL-1: add the promise of fresh books and CLI to the contract. |
| AL-27 (05:27) | "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" | Every hidden project carries relay hubs where the terminal MST and greedy attach are dearer (prototype 14/14); RULE_COVERAGE row "minimum quote" lists the KMB mutant and the tests it fails. | AL-27: raise hub count in the hidden generator until the mutant fails. |
| CL-4 (05:77) | "Count the independently discoverable facts ... then read how the tests compare them." | Instruction states that each document is compared whole and only an exact match counts; FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately". Partial facts are graded separately by C17 feasibility and C18 own-network rollup. | CL-4: rebut quoting FC:491 with the one-fact-wrong score from COST_TABLE; fallback partition the whole-doc check into per-project checks. |
| TS-13 (03:44) | "one property per test" | C08 reads one document of one book against the reference; feasibility (C17) and rollup-follows-network (C18) are separate tests. | TS-13: split the two-property test. |
| TS-26 (03:53) | "Same observable, same logic = keep one side" | C08 (equality with reference) and C17 (graph feasibility) read module_core with different decisive logic; H books and M books are different observables (different runs). | TS-26: rewrite one side to read a different observable or drop it. |

## P-1 wave 1 (678c839): computational core, no stated decomposition parameter (replaces LV-CC-2)
New/changed agent-visible sentences: api_contract.md:91-92 "Limit: the command must finish a book within 4 seconds per project in it plus 10 seconds of start-up." (size clause and span rule deleted; rejection list now three codes, api_contract.md:64-73). New checks: wide_1_core 5, wide_2_core 5, wide_3_core 5, wide_books_report 3, wide_books_summary 3, wide_networks_feasible 3 (tests/test_output.py criteria block).

| rule | quoted | why it passes | fallback (playbook row: DO fix) |
|---|---|---|---|
| IN-15 (01:45) | "Judge whether an agent could tell, before acting, whether a given action complies." | Every graded fact on the wide books is a rule already stated: network, quote, tie (api_contract.md:77-89), charging lines (96-104), documents (108-128), the run on other books (24-25) and the limit (91-92). No new rule was added; two were removed. | IN-15: add the missing sentence to api_contract.md. |
| IN-16 (01:46) | "you must show all three parts or you do not have a finding" | The limit sentence has one reading (4 x projects + 10 s per book run); the test runs exactly that (`_run_cli`, SECONDS_PER_PROJECT 4, START_UP_SECONDS 10). Tie and no-network verdicts settled by api_contract.md:85 and :70 (EVIDENCE_MAP rows). | IN-16: add the settling sentence. |
| IN-17 (01:47) | instruction states WHAT, no recipe or announcement | No sentence names a method, a structure of the hidden books, a size, width, span or 'at most' bound, or warns about them; hole grep (span, width, block, cut, articulation, at most, 52, 95, 17 cold, bound) over instruction.md, api_contract.md, build_config.json, environment/repo, solve.sh, judge.toml: 0 hits. | IN-17: delete the announcing sentence. |
| AL-1 (05:21) | "Everything graded is promised." | Fresh books are promised (api_contract.md:24-25 "The command is also run on other books in the same format."); whole-document grading promised by the instruction exactness sentence; limit promised (91-92). | AL-1: add the promise. |
| AL-2 | stated bounds hold on hidden data | No size bound is stated, so none can be broken; the only stated limit (time) is the one the test enforces; the reference finishes a wide book in <= 0.5 s of its 50 s. | AL-2: state the limit formula exactly as run. |
| AL-27 (05:27) | "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" | `_wide_book_parts` retries until every project plants all five branches (`_wide_shape`: parts joined at single sites, a part solved by subsets, a part solved by sweep, hubs, far positions with >= 28 cold rooms) and exactly one tie per book; sweep300 checks 300 seeds. Kill table (COST_TABLE.md) shows each generic solver losing the wide checks. | AL-27: raise plants in the generator. |
| CL-4 (05:77) | "Count the independently discoverable facts ... then read how the tests compare them." | Instruction: "Each output document is graded whole on fresh books, and only an exact match counts." FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately". Feasibility is graded separately (wide_networks_feasible) so a feasible non-optimal network keeps 3 of 24. | CL-4: rebut quoting FC:491; fallback split whole-doc per project. |
| TS-13 (03:44) | "one property per test" | wide_k_core reads one document of one book; wide_books_report and wide_books_summary each read one document kind (split per master go item 2); feasibility is its own test. | TS-13: split. |
| TS-19 (03:50) | "Every graded behaviour must be learnable by the agent" | Shipped data shows the structure: 20% of shipped projects are parts joined at single sites with shuffled positions, and the largest open-link gap varies 3-16 per project; the reference is exact and its decisions follow stated rules only. | TS-19: ship more such projects. |
| TS-20 (03:51) | "a core-deliverable test carrying weight 1, or an existence/formatting check carrying 5, is wrong" | wide core docs 5, report/summary/feasibility 3; weights only 1/3/5. | TS-20: remap. |
| TS-26 (03:53) | "Same observable, same logic = keep one side" | wide_k_core (equality with reference) and wide_networks_feasible (graph check of the agent's own network) read the same file with different decisive logic; wide books are different runs from fresh books. | TS-26: drop one side. |

## LV-CC-3 activation once per activated site
| rule | quoted | why it passes | fallback |
|---|---|---|---|
| IN-15 | as above | Contract: "Each activated site's activation charge is paid once, whatever the number of selected links touching it." plus booking rule, site/corridor/depot totals, share_bp formula and the coupling sentence "Every reported total of a project is computed from its minimum-cost network." | IN-15: add the sentence to the contract. |
| IN-16 | as above | Booking endpoint is unique (positions are distinct; depot 0); share uses floor division stated as `total * 10000 // quote`. | IN-16: state the formula. |
| AL-27 | as above | Every hidden project has hubs with 2 to 4 booked links and >= 1 activated site with no booked link; RULE_COVERAGE row lists the per-booked-link mutant failing C04, C11-C16, C18. | AL-27: plant more hubs. |
| AL-28 (05:28) | "one action never fires more than one max-severity penalty" | Negatives are cheating acts only (N1 replay, N2 editing the book); no negative fires for a wrong charge. | AL-28: drop the second negative. |
| TS-20 (03:51) | "a core-deliverable test carrying weight 1, or an existence/formatting check carrying 5, is wrong" | whole-doc core/report checks 5, summaries/parser/feasibility 3, existence/rerun 1. | TS-20: remap weights 5/3/1. |
| TS-26 | as above | C11 (report vs reference) and C18 (report vs agent's own network under the stated rule) differ in observable logic. | TS-26 as above. |

## LV-T secondary tie order (if kept)
| rule | quoted | why it passes | fallback |
|---|---|---|---|
| AL-27 | as above | Book T has 6 projects with exactly 2 optima; the reversed-order mutant fails C23. | AL-27: drop the sentence and C23 together. |
| IN-16 | as above | Vector over link ids ascending, 1 = selected, lexicographically smaller wins: one reading. | IN-16: add a worked example to the contract. |

## Cascade (COUPLING into every document)
| rule | quoted | why it passes | fallback |
|---|---|---|---|
| CL-4 | as above | The quote enters module_core, every share_bp in module_report and summary book_total; whole-document cascade per view per hidden extract ruled PASS (district-heat v3:185, cohort v2:183); FC:491 quote. | CL-4 partition fallback. |
| TS-13 | as above | Each cascade doc is its own test per book. C19/C20 read one run's output set as one observable (the mutated book quoted); fallback split per doc. | TS-13 split. |
| TS-26 | as above | Different docs carry different keys; no pair pays one observable twice. | TS-26 as above. |
| JD-7 (04:76) | "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle" | solve.py prints a plain-description `check ... ok` line for R1-R7 (shipped run before edits, recount, one link changed, missing files, built far book timed against the limit, two-run byte compare, built tie book) and four `defect found before editing` lines (R8); JUDGE_MAP names the oracle line for each. | JD-7: add the stage to solve.sh. |
| JD-15 (04:92) | "every criterion classified as outcome, constraint or conduct; outcome criteria trace to the contract" | R1-R8 conduct (agent behavior, trajectory) each naming an observable tied to an instruction or contract sentence; R4 requires the stated failure behaviour (non-zero exit, E_MISSING_FILE name, no document); R9 code quality; R10 instruction following; R11-R13 disjoint negatives (AL-28). | JD-15: relabel. |
| JD-6 | files a criterion rules on are artifacts | task.toml artifacts list /app/out documents and /app/repo/src/task/core.py | JD-6: add the path. |
| DS-17 | no criterion ids in solution output | solve.py prints plain descriptions only | DS-17: reword prints. |

## Law-1 fix 25c745d (fresh-book cold-room range)
| rule | quoted | why it passes | fallback |
|---|---|---|---|
| IN-15 / IN-16 / section 8 holes | no unstated size gate | No doc changed. Fresh books now sit inside the shipped size range (cold 8-10 of shipped 4-10, sites <= 52, links <= 94), so no hidden book is slower than shipped data for a non-lever check; only the wide books exceed shipped size, under the stated limit (api_contract.md:91-92). | none needed |
| TS-13 / TS-14 / TS-20 / TS-25 / TS-26 / CL-2 / CL-4 | check bodies | All check bodies and weights byte-unchanged (AST compare, only helper `_fresh_book_parts` changed); expected values recomputed by the test's own `_optimum` at run time; nop still 0. | none |
| DS-22 | TRUTH digests | TRUTH.md rewritten by script last (fresh-book sizes, timing table, sha256). | rerun finalize |
| TS-24 / AL-18 / AL-19 (FIX_SIDE_EFFECTS of a regeneration) | hidden data regenerated | Generator sweep 300 seeds (runs/sweep_l1.log) asserts bounds, unique optimum, rescaled and rejection shapes; oracle 108/108 on the new books. | rerun sweep |

## P12 QC v1 fixes (28 Oct, board 5951927)
| rule | quoted | our design now | fallback if QC insists |
|---|---|---|---|
| DS-24 (02:69) | "What is not legitimate is the oracle importing, copying or restating the logic that decides the grade." | The verifier finds blocks by taking each site away in turn (BFS side labels, not Tarjan) and solves each block link by link (frontier over links) or from one price-ordered queue over (site, joined set); uniqueness from plus/minus rank bits, not by banning links. Cross-checked: 1200 random small projects vs `_enumerate` (582 feasible, 0 bad), 2648 generator and book calls equal to the oracle-style solver, every expected document byte-identical. solve.py unchanged in method. | Third method (whole-block branch and bound) for one book family. |
| TS-24 / TS-7 (03:68-72, 03:34) | "Every agent subprocess has exited before its check returns (killing the process group)" | Verifier trees 0755/0644; only each run's out/ and cwd 0777; every agent call in its own session, group SIGKILLed on return and timeout (`_run_untrusted`). | Also kill by uid after each call (serialised checks). |
| TS-26 (03:53) relocated | "Same observable, same logic = keep one side, or rewrite one to read a different observable." | relocated_book_documents compares the relocated run with the package's own fresh_2 run (path and cwd independence), with the guard that the fresh_2 run quotes at least one project and its four documents differ from those the unedited shipped package writes for that book (embedded digest; P12 v2 905cf6e, QC v2 G03-W1: the guard reads a different observable from fresh_networks_feasible). rerun_identical takes the same guard on fresh_1 (G5: the shipped package is deterministic, so without a guard it would earn the rerun points). | Guard must stay on an observable no positive check pays for; never drop it (the unedited package would earn 4 points). |
| TS-13 (03:44) | "One property per test." | archive_follows_build_config = archive members only; archived_package_metadata (w1) = pyproject deps, requires-python, version, import probe. | none |
| AL-27 (05:38) | "find the graded input with both conditions present" | Rejection project P9310 carries a duplicate site and a link to an unknown site; mutant unknown_before_dup loses rejection_book_parser (RULE_COVERAGE L15). | none |
| JD-5 / JD-7 / JD-14 / JD-15 | R9, R4, R10, R5 | R9 one facet (function split) with an edit precondition; R4 "one or more"; R10 names every rejected project and gives a code for each (presence; code correctness stays with R12's negative, so different acts; QC v2 G11-1 AL-2); R5 names its two dimensions against the shipped book, no figures (QC v2 G04-M1); oracle prints both books' figures. | none |
| CL-10 / AL-4 (FC:498) | "long or difficult work is not a defect here" | KEEP: no sentence on the size of other books (would name the P-1 lever). | State "other books in the same format" only (already at api_contract.md:24-25). |

## Cap-60 build (30 Oct, board b223662): held-out far-reaching tier wide_4 to wide_10
New checks: wide_K_core 5, wide_K_report 5, wide_K_summary 3 for K = 4..10 (21 checks, 91 points; tests/test_output.py criteria block, `HELD_WIDE_BOOKS`). Positive test weight 109 -> 200. No agent-visible file changed (instruction.md, api_contract.md, environment/ data, judge.toml byte-unchanged); only tests/test_output.py, tests/reward.toml (test_output 0.0025 = 0.5/200) and solution/TRUTH.md changed.

| rule | quoted | why it passes | fallback (playbook row: DO fix) |
|---|---|---|---|
| IN-15 / IN-16 (01:45-46) | "whether an agent could tell, before acting, whether a given action complies" | Same stated rules as wide_1 to wide_3 (network, quote, tie api_contract.md:77-89; lines 96-104; documents 108-128; other books 24-25; limit 91-92). The new books come from the same builder (`_make_wide`, seeds 8-14 past the book seed). No new rule, no new value form. | IN-15: add the missing sentence to api_contract.md (none expected). |
| IN-17 (01:47) | no announcement of a shipped-established discovery | No agent-visible sentence added or changed; hole grep unchanged (0 hits). | IN-17: delete the announcing sentence. |
| AL-1 (05:21) | "Everything graded is promised." | "The command is also run on other books in the same format." (api_contract.md:24-25) + "Each output document is graded whole on fresh books, and only an exact match counts." (instruction.md:11) + limit (91-92). | AL-1: add the promise. |
| AL-27 (05:27) | the graded input must construct the situation | Every new book passes `_wide_book_parts` plants (parts joined at single sites, subset part, sweep part, one tie); 31-41 cold rooms per book (WORK/wide_stats.py), so exponential-in-cold-room programs cannot finish. | AL-27: raise plants. |
| CL-4 (05:77) | whole-document grading | Exactness sentence instruction.md:11; FC:491. Each new check reads one document of one book (G1a ownership per book). | CL-4: rebut quoting FC:491; fallback split per project. |
| TS-13 (03:44) | one property per test | wide_K_core/report/summary each read one document of one book. | TS-13: split. |
| TS-19 (03:50) | hidden within stated bounds; learnable | Same as wide_1 to wide_3: no size bound stated, only the time limit, which the test runs exactly; memory = declared container 4096 MB (task.toml). Reference 0.13-0.17 s per new book on the CLI of a 50 s cap. | TS-19: ship more far-reaching projects (would weaken the lever; prefer rebuttal). |
| TS-20 (03:51) | weights | core and report 5 (core deliverables), summary 3; no 1 on a core check. | TS-20: remap. |
| TS-23 (03:52) | lever share > 35% warns | Kept on purpose: master cap-60 exception for this bundle (30 Oct 12:00 go), crash + timeout share of the a4 program <= 60% of positive weight. | Drop wide_8 to wide_10 (39 points) if QC rules it a FAIL, not a WARN. |
| TS-26 (03:53) | no double pay | Each check is a separate run of a separate book; wide_books_report / wide_books_summary / wide_networks_feasible still read wide_1 to wide_3 only, so no file of wide_4 to wide_10 is paid twice. | TS-26: drop one side. |
| Law-1 v3.5 condition 3 | cost confined to lever checks | Every new book is its own `_run_cli` call with its own 50 s cap; no non-lever check reads a wide book. | none |
