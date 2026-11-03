P10 TEMPLATES (W1-032, draft, 3 Nov 2026). Ayush: "After an upgrade, some templates are still old."

Sources read in full first: upgrade_plan/drafts/P1/RULES_IN_FORCE.md (RIF), drafts/P1/BUILD_RULES.md, drafts/P1/settings.json, drafts/P1/FOLD_DECISIONS.md. Templates: master_chat_tasks/prompts/templates/. Pointers grepped: tools/issue.py, auto/auto.py, auto/AUTO_POLICY.md, README.md, knowledge/INDEX.md, prompts/templates/CHANGELOG.md. Nothing outside upgrade_plan/tmp/W1-032/ was changed.

Short answer. The templates are old because nothing ties them to the rules: no file names the current version of each family, the numbers the rules now keep in settings.json are written into the template text (gate 85, 85, 40 appears 22 times), and the rule text the fold review retired (shapes, hardness sources, blinds before QC, round caps, kill rule parking) still sits in the five templates every build, harden and fix session reads first. template_check.py finds 87 conflicting lines in the 13 active templates (102 when the dormant P3 to P6 are added). Section 2 lists them with the new text; section 3 is the tool change that keeps it from happening again.


1. CURRENT VERSION PER FAMILY

How "current" was decided. issue.py does not name templates at all (the master fills a template and hands issue.py the draft), and auto.py names none either. The pointers that do exist: README.md:31 ("Templates: _COMMON_RULES_v5, P2 v5, P9 v4, P11 v3, P12 v4"), knowledge/INDEX.md (P12 v5 ACTIVE, v4 SUPERSEDED; P14 v2, P15 v2, P16 v1, P17 v1 ACTIVE; _COMMON_RULES_v5), auto/AUTO_POLICY.md:23 and :25 (P13 v2, P11 v3), and CHANGELOG.md (last bump per family). Where they disagree, INDEX.md and CHANGELOG.md win (31 Oct P12 v5 entry), so README.md:31 is itself stale.

family | current | status | history (older versions) | why
_COMMON_RULES | _COMMON_RULES_v5.md | active | _COMMON_RULES.md, _v2, _v3, _v4, _v5_v3.6_snapshot.md | CHANGELOG 27 Oct, edited in place 29 Oct, 31 Oct, 2 Nov; INDEX
P1 ideas | P1_chatgpt_ideas_v3.md | active | v1, v2 | CHANGELOG 26 Oct
P2 build | P2_build_v5.md | active | v1, v2, v3, v4 | README:31, CHANGELOG 27 Oct
P3 hardness check | P3_hardness_check_v2.md | dormant | v1 | reflex replay gate retired 24 Oct; no pointer since pipeline v4
P4 rebuild | P4_rebuild_v2.md | dormant | v1 | follows a P3 REBUILD; no pointer since pipeline v4
P5 quick QC | P5_quick_qc_v2.md | dormant | v1 | P11 v3 is the only QC route; still reads _COMMON_RULES_v2
P6 oracle nop stub | P6_oracle_nop_stub_v2.md | dormant | v1 | Step 10 lives in P11 v3
P7 fix QC | none | retired | v1, v2 | CHANGELOG 22 Oct 21:45 (replaced by P12); INDEX says not for QL work
P8 fail recheck | none | retired | v1, v2 | same
P9 harden | P9_harden_from_results_v4.md | active | v1, v2, v3 | README:31, CHANGELOG 27 Oct
P10 upstream diff | P10_upstream_diff_v2.md | active | v1 | CHANGELOG 23 Oct; this is the S7 kit watch template
P11 full QC | P11_full_qc_v3.md | active | v1, v2 | README:31, AUTO_POLICY:25
P12 recheck fix | P12_recheck_fix_v5.md | active | v1, v2, v3, v4 | INDEX, CHANGELOG 31 Oct (README:31 still says v4)
P13 blind solve | P13_blind_solve_v2.md | active | v1 | AUTO_POLICY:23, CHANGELOG 26 Oct
P14 task analysis | P14_task_analysis_v2.md | active | v1 | INDEX
P15 research angle | P15_research_angle_v2.md | active | v1 | INDEX
P16 QL triage | P16_ql_report_triage_v1.md | active | none | INDEX
P17 QL handback | P17_ql_handback_v1.md | active | none | INDEX
QL reply | QL_REPLY_TEMPLATE.md | active | none | INDEX

Conflicting lines per current template (template_check.py count of distinct lines; the table in section 2 adds lines the script cannot judge by pattern):
_COMMON_RULES_v5.md 15 (table rows 17) | P1 v3 4 (5) | P2 v5 27 (22) | P9 v4 16 (15) | P10 v2 2 (4) | P11 v3 3 (4) | P12 v5 9 (11) | P13 v2 0 (2) | P14 v2 1 (2) | P15 v2 1 (1) | P16 v1 4 (4) | P17 v1 5 (5) | QL_REPLY 0 (0) | dormant P3 v2 2, P4 v2 6, P5 v2 2, P6 v2 1.
Stale pointers outside the templates: README.md:31 (P12 v4; also gate "tests<100, rubric<100, overall<70", "3 fresh P13 blind reads", "Count cap option A (over 35 = warn)"); tools/issue.py LEGACY maps the step prefix "P10" to harden and rebuild, but P10 is now the upstream diff template (P4 is rebuild), so a P10 session would be counted as a harden round.


2. CONFLICTING LINES, CURRENT TEMPLATES

Format: template:line | old text, short | new rule (file and item) | proposed new text. RIF = RULES_IN_FORCE.md, BR = BUILD_RULES.md, FD = FOLD_DECISIONS.md, S = settings.json. Where a value lives in settings.json the proposed text uses a fill token (<GATE>, <ORACLE_RUNS>, <DOCKER>, <TIME_FACTOR>, <DESIGN_BAR>) that issue.py fills at issue time (section 3), so the next change of a number touches settings.json only.

2a. _COMMON_RULES_v5.md (read first by every session; 17 rows)
_COMMON_RULES_v5:10 | LEVER_RULES path "(design shapes B and D, hardness sources S1-S11 ... holes list section 8)" | RIF BUILD RULES; FD T1 DROP, T3, T11 | "BUILD_RULES (levers, hiding, DESIGN.md, grading, instruction, rubric, limits, QC fixes): <path>/BUILD_RULES.md; DESIGN families: upgrade_plan/knowledge/PATTERNS.md. Read them by path; never copy them into a bundle or report."
_COMMON_RULES_v5:12 | "QC fix playbook ... section 1b guard rules G1-G7 bind every fix" | RIF QC FIXES; BR QC FIXES, QC FIX STEPS; FD A7 | "QC fix map: <path>/FIX_MAP.md (per check: the fix that meets it and keeps the hardness, the wording that passes, the side effects). BUILD_RULES QC FIX STEPS bind every fix."
_COMMON_RULES_v5:29 | Never 10 "... a QC recheck and 1 new run" | FD T33 (runs per step in settings) | "... a QC recheck and the runs settings.json allows for that step (<RUNS>)."
_COMMON_RULES_v5:33 | Always 1 "On any difference: stop ... report UPSTREAM CHANGED. Do not continue on stale rules." | S7 classes (Q86): master reports, Ayush decides; LENIENT acts freely | "Before work, compare the kit with the QC KIT line in your prompt. If it changed, list the changed files and check ids in your report and continue; stop only when your prompt marks a kit change MAJOR pending Ayush."
_COMMON_RULES_v5:48 | "dockfree.py --need-mb 4096 --cpus 2 ... docker run --rm --memory 4g --cpus 2" | RIF DOCKER AND COST R19 to R24 (Docker room from the S1 script) | "... first the Docker room check (<DOCKER_CHECK>) must say START=yes, then docker run --rm <DOCKER> with a wall cap."
_COMMON_RULES_v5:49 | rule 17 "misread-rule levers are extras" | BR LEVERS CR7; FD T3 | "Misread rule levers are allowed under CR7 (one clear deciding sentence, many tempting records); the other paused stated rule kinds stay paused until the lever audit."
_COMMON_RULES_v5:49 | rule 17 "hidden-scale TIMEOUT/CRASH counts with no cap"; "timeout or crash loss counts only under v3.5" | BR LEVERS CR1, R30 | "A timeout lever is only an extra unless Ayush says so; a size bound may be stated for it."
_COMMON_RULES_v5:49 | rule 17 "Blind bar: each of the 3 fresh blind reads scores tests <= 65 (none above 70)"; "(c) no blind program above tests 65"; "(e) every generic solver and every blind program loses >= 15%" | BR LIMITS T45; BR LEVERS CR2 | "The primary lever is lost by the paid run program (the careful exact program, CR2). Blinds before QC are not required; a blind is a diagnostic only."
_COMMON_RULES_v5:49 | rule 17 "DESIGN READY needs ... (a) predicted final <= 35 ... first-write tests <= 60, judge mid <= 20 ... (d) verifier worst case <= 90% ... reference <= 1/4 of the stated limit" | BR DESIGN.md T10, T20; BR LEVERS NO CORE; BR LIMITS T43; S design_margin, no_core_keep_pct | "DESIGN READY needs DESIGN.md naming, per lever, the oracle branch, the careful program branch and a saved input where they differ, the primary lever's share (at least 40 percent of positive test weight), and a predicted final under <DESIGN_BAR> (gate.final minus design_margin). If the paid run program keeps <NO_CORE_KEEP_PCT> percent or more of the primary lever's points: report to Ayush and redesign, never park."
_COMMON_RULES_v5:53 | "J1 lint: no figure criterion at all" | BR RUBRIC T42 | "A what if figure criterion only when the instruction asks for that figure: at most 6, weight at most 3 each."
_COMMON_RULES_v5:54 | J3b "-5"; J4 v3 behavioural code quality ("every handler acts on the error it catches ...") | BR RUBRIC T41; "Honesty negative minus 3 in every judge" | "One code quality criterion when the agent writes code: 'a Python reviewer would accept as maintainable, judged on its names, function structure and error handling', conduct label, weight 1 to 3, met by the oracle. The honesty negative is minus 3 in every judge." (J3b at minus 5: open point 3)
_COMMON_RULES_v5:58 | "a time or memory limit ... is at least 3x the oracle's measured time" | BR LIMITS T43; S time limit factor | "A time limit is at least <TIME_FACTOR> times the reference time measured in this session, or there is no limit."
_COMMON_RULES_v5:62 | gate written out "tests < 85 AND rubric < 85 AND final reward < 40 ... was 50 ... was tests < 100 AND final < 70 ... design for tests <= 60 and rubric <= 20" | RIF GATE R26, R27; S gate | "Gate: <GATE> (settings.json) on 1 valid run of the frozen QC passed bytes. Final = (tests + rubric)/2. Never rerun the same bytes after a miss."
_COMMON_RULES_v5:63 | "Above 35 tests the kit prints WARN A3/TS-23: record it" | RIF CAPS R15; S counts | "Counts: tests and rubric criteria each at least the QC minimum; soft cap <SOFT_CAP>, hard cap <HARD_CAP> (settings.json); a kit count warn is recorded with the count, never merged away."
_COMMON_RULES_v5:64 | "This supersedes the dec 101 zero-warn rule and the 35/35 caps" | RIF QC PASS R16, R18, Q129, Q133 | "QC pass: 1 complete pass where every fail left is a false positive Ayush accepted from a triage table (diff and kit line), the rest minors or warnings kept in PL notes. Stop at the first pass."
_COMMON_RULES_v5:65 | "Hardness is proved by a real probe run ... after 3 blind reads ... kill rule ... park when final above 70; tests at 100 on 2 valid runs park the task" | RIF ORDER T24, GATE R26, RUNS AND PUSH T34; BR LIMITS T44, T45 | "Hardness is measured only by the paid run on the frozen QC passed bytes. A blind read is a diagnostic only. No task is parked except on Ayush's word; 0 differences over 2,000 variants is reported to Ayush, never parked."
_COMMON_RULES_v5:66 | "Order: design -> build -> 3 fresh blind reads -> one full QC ... -> freeze -> 1 harness run" | RIF ORDER T24, T25 | "Order: design (stop at DESIGN READY for Ayush's go; in auto mode the master checks it and writes the go file), build, full QC until it passes, QL QC when the QL reports, 1 paid run on the frozen bytes. No hardening between QC pass and paid run; after a gate miss, harden from what the run got wrong with the fix map, QC again, 1 new run."

2b. P1_chatgpt_ideas_v3.md (5 rows)
P1_v3:11 | "Target: ... 30 to 70 percent of the test points ... so its final stays below 60" | RIF GATE R26; BR DESIGN.md T20 | "Target: a careful, competent agent's final (the average of the test and reviewer scores) stays under <DESIGN_BAR>."
P1_v3:25 | "Nothing may depend on reading a rule wrongly" | BR LEVERS CR7; FD T3 | "A rule may be easy to misread only when one clear sentence decides it and many records tempt the wrong reading; no rule may be missing from the files."
P1_v3:31 | "Do not state a size or runtime limit that tells the agent which method to use" | BR LEVERS CR1, R30 | "A size bound may be stated; a runtime limit is never the main difficulty."
P1_v3:47 | "The hardness sources used (at least two of: breadth, hard case only in hidden inputs, unique fit, partial-authority file, long authority chain)" | FD T1, T3; BR LEVERS (primary lever from a PATTERNS.md DESIGN family) | "The primary lever (one DESIGN family, named in words) and its share of the test points (at least 40 percent), plus any extras, and for each: the rules involved and the files and formats they sit in."
P1_v3:5 | master note "gates every idea (uniqueness, QC risk, LEVER_RULES_v3)" | RIF BUILD RULES | "... (uniqueness, QC risk, BUILD_RULES LEVERS)."

2c. P2_build_v5.md (22 rows)
P2_v5:26 | "LEVER_RULES_v3.md (THE authority for the determinate test, design shapes, hardness sources ...)" | RIF BUILD RULES | "BUILD_RULES.md (THE authority for levers, hiding, DESIGN.md, grading, instruction, rubric, limits) and PATTERNS.md (DESIGN families)."
P2_v5:28 | "QC_FIX_PLAYBOOK_v3.md (how a QC finding is fixed without softening a lever)" | FD A7, T22 | "FIX_MAP.md (how a QC finding is fixed so the check passes and the hardness stays)."
P2_v5:38 | "SHAPE (LEVER_RULES v3 section 1: B breadth or D degenerate shipped instance): [[SHAPE]]" | FD T1 DROP | "PRIMARY LEVER (BR LEVERS: one PATTERNS.md DESIGN family, at least 40 percent of positive test weight, firing in most hidden inputs, lost by the paid run program): [[PRIMARY_LEVER]]"
P2_v5:39 | "HARDNESS SOURCES (section 1A: one primary S1 or S2, plus at least one of S3, S5, S6 ...): [[SOURCES]]" | FD T1, T3; BR LEVERS | "EXTRAS (optional: misread rule levers under CR7; carrier variation with the standard named in one sentence, D2; bounded induction with the finite family shown, D1; a timeout extra with a stated size bound, CR1): [[EXTRAS]]"
P2_v5:40 | "BREADTH TARGET (Shape B: at least 30 graded stated rules ...; Shape D: at most 3 sharp rules ...)" | FD T1 | delete the input; the PRIMARY LEVER line carries the share.
P2_v5:52 | "nor hidden or ambiguous rules (LEVER_RULES v3 section 8: holes are not levers) ... Never state a size or runtime limit that hands over the exact method" | BR HIDING R28, T7; BR LEVERS T11, R30 | "... never from withheld rules: a shipped instance may hide a case, never the rule. Holes only case by case with Ayush. A size bound may be stated for a timeout extra."
P2_v5:62 | "(Shape B: the rule register ...; Shape D: each sharp rule) ... BRANCH_FIRE ... (in Shape D every hard branch has shipped count 0 ...)" | FD T1; BR HIDING T7 | "for every graded rule: its text and governing file, the careful program's reading, the hidden cases, and WORK/BRANCH_FIRE.md (every hidden branch has its sentence in the docs)."
P2_v5:64 | "the test plan (LEVER_RULES v3 G1-G13 ... weight shares per G3 for the chosen shape) and the judge plan (J1-J10: the probe band ...)" | BR GRADING T12 to T15; BR RUBRIC | "the test plan per BR GRADING (the exact bar sentence, whole documents per hidden run, the stated command, no key the contract does not name) and the rubric plan per BR RUBRIC."
P2_v5:66 | kill test "every plausible solver ... lever passes only if every strong solver loses by WRONG ... TIMEOUT or CRASH counts only under v3.5 ... Blind bar ... DESIGN READY needs (a) to (e)"; "--memory 4g --cpus 2" | BR LEVERS CR2, NO CORE, CR1; BR DESIGN.md T10, T20; BR LIMITS T45; RIF DOCKER | "Lever check (CR2): run the paid run program (the careful exact program) on prototype hidden instances in Docker (<DOCKER>, wall cap) and record in WORK/KILL_TEST.md the share of the primary lever's points it keeps; <NO_CORE_KEEP_PCT> percent or more means report to Ayush and redesign. DESIGN READY needs DESIGN.md per T10 and a predicted final under <DESIGN_BAR>."
P2_v5:69 | "Wait until Ayush replies 'go'" | RIF ORDER T25 (auto mode go file) | "Wait for the go: by day Ayush; in auto mode the master's go file (prompts/issued/<slug>/<ts>_go.md)."
P2_v5:71 | Phase 0b "design-stage blind read, then STOP" (and :74 "DESIGN BLIND READY", :75 "If the blind program is exact ... redesign") | BR LIMITS T45; FD A3 | "Phase 0b (only when the master asks): a design stage blind read is a diagnostic; its result is written to WORK/DESIGN_BLIND.md and never blocks the build."
P2_v5:84 | "(Shape B: at least 10 governing files) ... In Shape D the shipped instance must not fire any hard branch" | FD T1; BR HIDING T7 | "at least [[MIN_INPUTS]] files in at least 5 formats. A shipped instance may hide a case, never the rule."
P2_v5:87 | "A partial-authority decoy (S5) states its own demotion" (and :51 "is a hardness source (S5)") | FD T1, T3 | "A partial authority file states its own demotion in its header and names the one fact that stays live." (drop the S5 label)
P2_v5:98 | "G3 by shape: Shape D at least 70% ... Shape B no floor" | FD T1; BR LEVERS | "Every output family has at least one hidden rerun; the primary lever carries at least 40 percent of positive test weight, measured through the call graph."
P2_v5:100 | "Gate Shape B ... Gate Shape D: every lever alone >= 25%. Both: every 'all but one' row final < 70" | FD T1, T20 | "Gate: the primary lever alone loses at least 40 percent of positive test weight, and the all but one row's predicted final is under <DESIGN_BAR>."
P2_v5:103 | "At least 10 checks and at least 8 judge criteria ... Above 35 checks the kit prints WARN A3" | RIF CAPS R15; S counts | "At least the QC minimum (10 checks, 8 criteria); soft cap <SOFT_CAP>, hard cap <HARD_CAP>; a kit count warn is recorded with the count."
P2_v5:111 | "J1 no figure criterion of any kind ... J4 exactly one behavioural code-quality criterion" | BR RUBRIC T42, T41 | the two sentences of row _COMMON_RULES_v5:53 and :54.
P2_v5:132 | "Oracle x3 = 1.0 on the tests channel (oracle x3 per Ayush; the kit asks x5), nop 0.0" (also :152) | BR LIMITS T46; S oracle runs | "Oracle x<ORACLE_RUNS> = 1.0 (settings.json: 3 by day, 2 in auto mode with the rest owed before push, 5 once in the final QC), nop 0.0."
P2_v5:142 | "No reflex gate: hardness is decided by 3 blind reads ... and the probe run the master queues next" | RIF ORDER T24; BR LIMITS T45 | "Hardness is measured by the 1 paid run after QC passes; write in DESIGN.md where the careful program is expected to lose points."
P2_v5:148 | result json "shape":"B|D","sources":[], "design_blind" | FD T1, T45 | "\"primary_lever\":\"<family>\",\"lever_share\":x,\"extras\":[],\"paid_program_keep_pct\":x" (design_blind optional).
P2_v5:156 | "Next step (v5 order): master issues 3 fresh P13 blind reads (... redesign, never park, if the lower-bound final is above 70 on 2 of 3), then one full QC" | RIF ORDER T24; BR LIMITS T45 | "Next step: one full QC (P11 MODE full) until it passes, QL QC if the QL reports, freeze, 1 paid run on the frozen bytes."
P2_v5:15 | "make a careful frontier agent (claude-opus-5) lose most test points" | RIF DOCKER AND COST R32 (model per step from settings) | "... make the paid run model (<PAID_MODEL>) lose most test points." (low priority)

2d. P9_harden_from_results_v4.md (15 rows)
P9_v4:14 | "Harden round [[ROUND]] of 3. If an earlier round of this task was marked LAST, stop and report 'ROUND LIMIT'." | RIF CAPS R15; FD T23 | "Harden round [[ROUND]]. There is no round cap."
P9_v4:26 | "LEVER_RULES_v3.md (THE authority for ... design shapes, hardness sources ...)" | RIF BUILD RULES | as P2_v5:26.
P9_v4:27 | "QC_FIX_PLAYBOOK_v3.md" | FD A7 | "FIX_MAP.md".
P9_v4:35 | "Shape and hardness sources for this round (LEVER_RULES v3 sections 1 and 1A ...)" | FD T1, T3 | "Lever change for this round, from what the run got wrong (BR LEVERS and the fix map), or 'judge only': [[LEVER_CHANGE]]"
P9_v4:42 | "which QC-safe edit each row supports (section T edit table)" | BR QC FIXES T22 | "which fix map row each lost or easy point supports; no edit softens a lever unless Ayush says so for that finding."
P9_v4:48 | Cause 4 "a stated limit that hands over the method" | BR LEVERS R30, CR1 | "... a stated limit that hands over the primary lever's method (a size bound for a timeout extra is allowed)."
P9_v4:57 | "Never add a hole from section 8 (unstated rule, silent value form, unstated invocation)" | BR LEVERS T11 | "Never withhold a rule (HIDING); a hole only case by case with Ayush, with the valid near form proposed."
P9_v4:59 | "G3 shares by shape" | FD T1 | "primary lever at least 40 percent of positive test weight."
P9_v4:60 | "behavioural J4", "probe band of 8-16 w3 trajectory probes" | BR RUBRIC T41 (probe band: open point 4) | as _COMMON_RULES_v5:54.
P9_v4:67 | kill table "against the agent program, every blind program and every generic solver ... --memory 4g --cpus 2 ... v3.5 ... Blind bar ... DESIGN READY (a) to (e)" | BR LEVERS CR2, CR1, NO CORE; BR LIMITS T45; RIF DOCKER | "Lever check against the paid run program and the agent program from the run (CR2), in Docker (<DOCKER>); a WRONG document is the primary loss, a timeout loss counts only as an extra (CR1); NO CORE from settings."
P9_v4:68 | "No reflex gate: the master issues 3 blind reads (tests and judge estimate) before the next probe" | RIF ORDER T24; BR LIMITS T45 | "Next: QC again with the fix map, then 1 new paid run."
P9_v4:70 | "oracle x3 = 1.000 (oracle x3 per Ayush, kit asks x5)" | BR LIMITS T46 | "oracle x<ORACLE_RUNS> = 1.000".
P9_v4:74 | status "ROUND_LIMIT" in result json | RIF CAPS R15 | drop ROUND_LIMIT from the status list.
P9_v4:76 | "Stop after 3 harden rounds in total. Report 'ROUND LIMIT'." | RIF CAPS R15 | delete the line.
P9_v4:78 | "Next step (v4 order): master issues 3 fresh P13 blind reads ... then one full QC ... then 1 harness run" | RIF ORDER T24 | "Next step: QC again until it passes, freeze, 1 new paid run on the frozen bytes."

2e. P10_upstream_diff_v2.md (4 rows; the template the S7 kit watch uses)
P10_v2:9 | "First read in full: ... _COMMON_RULES_v2.md" | templates/CURRENT.json | "... _COMMON_RULES_v5.md (RULES_IN_FORCE.md after PROCEED)."
P10_v2:18 | "Re-hash both folders with the same exclusions as the fingerprint files" | S7 (S7_KIT_WATCH.md) | "Run kit_watch.py check for QC (it hashes, diffs against the stored text copy and lists changed check ids with their fix map rows) and paste its tables; re-hash the generator as before."
P10_v2:22 | impact table "(P2..P15, _COMMON_RULES_v2, knowledge/LEVER_RULES_v3.md, knowledge/qc_authoring_checklist, knowledge/archetypes.md)" | CURRENT.json; RIF BUILD RULES; FIX_MAP | "which current templates (templates/CURRENT.json), BUILD_RULES.md items and FIX_MAP.md rows are affected, and a class per changed check id: LENIENT, MINOR or MAJOR (KIT_CLASSIFY_PROMPT.md); MAJOR goes to Ayush before any template or rule change."
P10_v2:24 | "Write new fingerprint files to OUT" | S7 (snapshot only on Ayush's word, with a text copy) | "Write the proposed snapshot command (kit_watch.py save --dest <new folder> --by '<Ayush's words>') into the report; never run it."

2f. P11_full_qc_v3.md (4 rows)
P11_v3:8 | master note "oracle x3 by default ... x5 only when the master issues a FINAL round" | BR LIMITS T46; S oracle runs | "Oracle runs come from settings.json (3 by day, 2 in auto mode, 5 once in the final QC before ship); the master fills [[ORACLE_N]] from it."
P11_v3:71 | OVERRIDE 5 "git diff 2690e960 HEAD -- Input_Bundle_QC/ ... known so far: K8 ..., H6/TS-30 ..." | S7 | "List every check id the master's kit watch marks changed since the snapshot (kit_watch.py output, pasted by the master), plus every id in the QL's list."
P11_v3:90 | "the kit asks for five oracle runs. This round runs [[ORACLE_N]] by Ayush's decision (22 Oct)" | BR LIMITS T46 | "... by settings.json (oracle runs, T46)."
P11_v3:103 | AUTO MODE "run 2 oracle runs and 1 nop run" | BR LIMITS T46; S oracle runs | "run <ORACLE_RUNS_AUTO> oracle runs and 1 nop run ..."

2g. P12_recheck_fix_v5.md (11 rows)
P12_v5:9 | master duty "Each line cites a row of knowledge/QC_FIX_PLAYBOOK_v3.md ... v4 guard (G1-G3)" | BR QC FIXES T22, Q125, Q126; FD A7 | "Each line cites its FIX_MAP.md row and, when the finding shows a real defect, the Q126 fix: one deciding sentence in the shipped docs, the hardness rebuilt in a valid form."
P12_v5:11 | "issues it with tools/issue.py ... (it refuses a third fix round after one QC). ... stop at the first PASS (zero findings, or proven false positives in FP_DOSSIER)" | FD T23; RIF CAPS R15; RIF QC PASS R16, Q129, Q133 | "issue.py warns past the usual round count, never refuses. Stop at the first pass: every fail left is a false positive Ayush accepted from the triage table (diff and kit line), the rest minors or warnings."
P12_v5:24 | read "LEVER_RULES_v3.md, QC_RULINGS.md and QC_FIX_PLAYBOOK_v3.md ... its DO column, never its NEVER column" | RIF BUILD RULES; FD A7 | "read BUILD_RULES.md (QC FIXES, QC FIX STEPS), FIX_MAP.md and QC_RULINGS.md. The fix map row is the rule for how each finding is fixed."
P12_v5:43 | "Trap baseline (QC_FIX_PLAYBOOK_v3 section 3 step 1)" | FD A7 | "Lever baseline: per lever, the points the paid run program and the saved agent program lose on the current tests."
P12_v5:54 | "KEEP ... a REAL one whose only fix weakens a lever" | BR QC FIXES T22 (a real defect is always fixed; a softening only on Ayush's word) | "A REAL fail is always fixed (Q126 fix). A REAL minor or warn whose only fix softens a lever goes to Ayush as a triage row; keep it only on his word."
P12_v5:57 | "Guard rules G1-G7 (playbook v3 section 1b) bind every fix" | BR QC FIX STEPS R8 to R14, R17 | "BUILD_RULES QC FIX STEPS bind every fix, including the master's directions."
P12_v5:58 | "For easier/unknown, add a compensating check or lever ... Stop and report 'PAUSED'" | BR QC FIXES T22 | "No fix softens a lever unless Ayush says so for that finding: an easier or unknown effect stops that row as PAUSED for his word."
P12_v5:67 | "STACKING_CHECK ... (LEVER_RULES section 5)" | RIF BUILD RULES | "... (BUILD_RULES LEVERS: primary lever share)."
P12_v5:68 | "each lever must keep at least 90% of its before loss" | not in RIF, BR or settings | open point 5 (a settings key or drop).
P12_v5:69 | "oracle x3 = 1.000, owner-only x1 = 1.000, nop x1 = 0.000" (also :78) | BR LIMITS T46 | "oracle x<ORACLE_RUNS> = 1.000, owner only x1, nop x1".
P12_v5:9 | "never copy the report's 'Fix:' line" | RIF QC FIX STEPS R8 | agrees; no change (listed so the reviewer sees it was checked).

2h. P13_blind_solve_v2.md (2 rows)
P13_v2:3 | "One per task, after the build or fix round, before any trajectory" | BR LIMITS T45; FD A3 | "Optional diagnostic, issued only when the master wants one; never a gate before QC or a paid run."
P13_v2:4 | "Also used at design stage (P2 Phase 0b)" | BR LIMITS T45 | "Also usable at design stage when the master asks (P2 Phase 0b is optional)."

2i. P14, P15, P16, P17 (12 rows)
P14_v2:11 | "LEVER_RULES_v3.md (sections 1C, 1D, Law-1, gate v3.7)" | RIF BUILD RULES; S gate | "BUILD_RULES.md (LEVERS) and the gate in settings.json."
P14_v2:45 | "A task whose band comes from the judge while tests >= 85 is flagged" | S gate.tests | "... while tests >= <GATE_TESTS> ..."
P15_v2:53 | "LEVER_RULES_v3.md (sections 1A, 1C, 1D, 8)" | RIF BUILD RULES | "BUILD_RULES.md (LEVERS, HIDING) and PATTERNS.md."
P16_v1:3 | master note "P12 v4, using this session's directions block" | CURRENT.json | "P12 (current version per templates/CURRENT.json) ..."
P16_v1:12 | reads "QC_FIX_PLAYBOOK_v3.md" and "LEVER_RULES_v3.md" | FD A7; RIF BUILD RULES | "FIX_MAP.md" and "BUILD_RULES.md".
P16_v1:16 | "Gate (v3.7): tests < 85 AND rubric < 85 AND final < 40" | RIF GATE; S gate | "Gate: <GATE> (settings.json) on one valid run of frozen QC passed bytes."
P16_v1:47 | "the new run must meet final < 40" | S gate.final | "... must meet final < <GATE_FINAL>."
P17_v1:9 | "(P9 v4 / P13 v2 / P11 v3 / P12 v4 / regrade worker)" (also :49 "then P12 v4") | CURRENT.json | name families only ("P9 / P11 / P12 ..."); issue.py resolves the version.
P17_v1:18 | reads "QC_FIX_PLAYBOOK_v3.md", "LEVER_RULES_v3.md" | FD A7; RIF BUILD RULES | "FIX_MAP.md", "BUILD_RULES.md".
P17_v1:46 | "gate result (tests < 85, rubric < 85, final < 40, gate v3.7)" | S gate | "gate result against <GATE>".
P17_v1:48 | "lower_score ... Without trajectories, 3 x P13 v2 blind, then P9 v4, then P11 v3 full, freeze, ASK, 1 run" | BR LIMITS T45; RIF ORDER T24 | "Without trajectories: P9 from the QL's notes, P11 full until it passes, freeze, ASK, 1 run (a blind only if the master wants a diagnostic)."
P17_v1:49 | "then P12 v4" | CURRENT.json | "then P12".

2j. Dormant families (one row each; proposal: mark dormant in CURRENT.json so issue.py warns when one is used)
P3_v2 | reads _COMMON_RULES_v2; replay gate R <= 0.20; ROUND | RIF ORDER T24 (paid run decides) | retire, or rebase on _COMMON_RULES_v5 and the paid run if Ayush wants a hardness audit back.
P4_v2 | reads _COMMON_RULES_v2; reflex gate <= 0.20; "Stop after 3 rebuild rounds"; oracle x3 | RIF CAPS R15; BR LIMITS T46 | retire (P9 covers rebuilds after a gate miss).
P5_v2 | reads _COMMON_RULES_v2; "A WARN above 35 checks or criteria is approved" | RIF CAPS R15 | retire (P11 v3 is the QC route).
P6_v2 | reads _COMMON_RULES_v2; "Run the oracle 3 times"; copy root under /tmp | BR LIMITS T46; _COMMON_RULES_v5:17 (_runs, not /tmp) | retire (P11 v3 Step 10).

Top conflicts by reach (every session reads _COMMON_RULES first; P2 and P9 decide the design):
1 _COMMON_RULES_v5:49 rule 17: misread levers as extras (CR7), timeout with no cap (CR1), blind bar and blind programs as lever judges (T45, CR2), DESIGN READY (a) to (e) instead of T10 and T20.
2 _COMMON_RULES_v5:66 order with 3 fresh blind reads before QC (T24, T45).
3 P2_build_v5:38 to :40 SHAPE, HARDNESS SOURCES S1 to S11, BREADTH TARGET as required inputs (T1, T3).
4 P2_build_v5:66 kill test judged on every blind program and generic solver, Docker 4g fixed, design bars hard coded (CR2, NO CORE, T20).
5 _COMMON_RULES_v5:65 kill rule park when final above 70, 2 valid runs at tests 100 (T34, T44, R26).
6 P9_harden_from_results_v4:14, :74, :76 round cap 3 and ROUND LIMIT (R15, T23).
7 P12_recheck_fix_v5:11 issue.py refuses a third fix round; false positives settled in FP_DOSSIER instead of by Ayush's triage (T23, Q133).
8 P9_harden_from_results_v4:42 "QC-safe edit" (T22: the fix map).
9 _COMMON_RULES_v5:58 time limit 3x the oracle (T43: 4x the reference, in settings).
10 _COMMON_RULES_v5:53 and :54 J1 no figure criterion, J4 behavioural code quality (T42, T41).


3. TOOL CHANGE THAT KEEPS TEMPLATES CURRENT

3.1 One manifest. prompts/templates/CURRENT.json (draft: upgrade_plan/tmp/W1-032/CURRENT.json) names, per family, the current file, its status (active, dormant, retired) and its history. A version bump edits CURRENT.json and CHANGELOG.md in the same change. README.md:31, knowledge/INDEX.md and AUTO_POLICY.md stop naming versions and say "the current version in prompts/templates/CURRENT.json"; auto.py reads the P11 and P13 paths from it instead of AUTO_POLICY text.

3.2 Numbers from settings, filled at issue time. Templates carry fill tokens instead of numbers: <GATE> (from gate, rendered "tests < 85, rubric < 85, final < 40"), <GATE_TESTS>, <GATE_FINAL>, <DESIGN_BAR> (gate.final minus design_margin), <NO_CORE_KEEP_PCT>, <SOFT_CAP>, <HARD_CAP>, <ORACLE_RUNS>, <ORACLE_RUNS_AUTO>, <DOCKER>, <DOCKER_CHECK>, <TIME_FACTOR>, <RUNS>, <PAID_MODEL>. issue.py already fills <SHA>, <PROMPT_PATH> and <OUT>; it fills these the same way from settings.json, and its LIVE_GATE constant (issue.py:59, hard coded 85, 85, 40) reads settings.json too. settings.json needs the keys the rules already say it holds but the draft lacks (open point 1):
  "oracle_runs": {"day": 3, "auto": 2, "final": 5},
  "docker": {"memory_mb": 4096, "cpus": 2},
  "time_limit_factor": 4,
  "runs_per_task": {"build": 1, "final_approval": 8},
  "auto": {"workers": 5, "harness": 2, "new_builds_per_run": 2, "last_spawn_min": 20, "paid_runs_per_day": 6},
  "models": {"worker": "claude-opus-5-5", "paid_run": "claude-opus-5"}
(values copied from the current texts: T46, _COMMON_RULES_v5:48, T43, T33, AUTO_POLICY A11 to A13; UNVERIFIED until Ayush confirms each.)

3.3 issue.py check. Every template starts its paste part with one line "Template: <file>" (the master keeps it in the draft). issue.py lint adds:
  warning (refused unless --force-lint "<reason>", logged): the Template line names a file that is not the family's current file, or a dormant family; the draft names any prompts/templates/<file> that is not current (for example _COMMON_RULES_v2.md); a fill token left unfilled.
  hard (refused): a retired family (P7, P8), or no Template line at all. Open point 2: Ayush may prefer warnings only, in line with T23.
Sketch (stdlib, inside issue.py lint):

    TEMPLATE_RE = re.compile(r"^Template:\s*(\S+\.md)\s*$", re.M)
    REF_RE = re.compile(r"prompts/templates/([\w.]+\.md)")

    def template_lint(text):
        man = json.loads((HERE / "prompts" / "templates" / "CURRENT.json").read_text())["families"]
        current = {d["current"]: f for f, d in man.items() if d.get("current")}
        status = {f: d.get("status", "active") for f, d in man.items()}
        hard, warn = [], []
        m = TEMPLATE_RE.search(text)
        if not m:
            hard.append("no 'Template: <file>' line")
        names = ([m.group(1)] if m else []) + REF_RE.findall(text)
        for name in names:
            fam = next((f for f, d in man.items() if name == d.get("current") or name in d.get("history", [])), None)
            if fam is None:
                warn.append(f"{name} is not in templates/CURRENT.json")
            elif status[fam] == "retired":
                hard.append(f"{name}: family {fam} is retired")
            elif name not in current:
                warn.append(f"{name} is not current; {fam} is {man[fam]['current']}")
            elif status[fam] == "dormant":
                warn.append(f"{name}: family {fam} is dormant")
        return hard, warn

Also fix issue.py LEGACY: "P10" is not harden or rebuild any more; map rebuild to "P4" and leave P10 out.

3.4 Check script. template_check.py (this folder, stdlib only, read only) checks (1) the manifest against the folder, (2) README.md, INDEX.md, AUTO_POLICY.md, auto.py and issue.py for non current version names, (3) every current template for SETTING values (gate, design bar, oracle runs, Docker limits, time factor, runs per task), RETIRED terms (shapes, hardness sources, old gates and aims, count cap 35, blinds before QC, blind programs as lever judges, round caps and refusals, QC-safe and bypass, misread levers as extras, timeout with no cap, no size bound, holes list, kill rule parking, J1 and J4 wording, reflex gate) and POINTERs (LEVER_RULES_vN, QC_FIX_PLAYBOOK and G1 to G7, older templates). Master notes that only record history ("v4 changes ...", "Replaces v2 ...") are skipped. It runs: (a) by the master after any rule or settings change, before the change is reported done; (b) in the state card as one line, "TEMPLATES: 87 conflicting lines in 9 templates" or "TEMPLATES: current"; (c) as a lesson check (R4: a repeated lesson becomes a tool check). The patterns are the retired list of FOLD_DECISIONS; when a new fold retires a term, its pattern is added in the same change.

3.5 Output of the run here (full text in TEMPLATE_CHECK_OUTPUT.txt):
  manifest ok; 1 stale pointer outside templates: README.md:31 names P12 v4 (current v5).
  13 active templates, 87 conflicting lines: SETTING 41, RETIRED 71, POINTER 47 (a line can carry several).
  By template: _COMMON_RULES_v5 15, P2_build_v5 27, P9_harden_v4 16, P12_recheck_fix_v5 9, P17 5, P1 v3 4, P16 4, P11 v3 3, P10 v2 2, P14 v2 1, P15 v2 1, P13 v2 0, QL_REPLY 0.
  By code: LEVER_RULES pointer 32, gate hard coded 22, blinds 12, shapes 11, playbook or G1 to G7 10, oracle count 8, hardness sources 7, holes 5, aims 5, round caps 5, older template 5, runs 4, time factor 4, old gates 4, Docker 3, blind programs 3, timeout 3, J4 3, cap 35 3, J1 2, park 2, size bound 2, reflex 2, misread 1, QC-safe 1.
  With --all (dormant P3 to P6 added): 17 templates, 98 lines. Without a manifest (derived highest version): retired P7 and P8 count as current (102 lines), which is the failure mode the manifest prevents.
  Known limits: patterns catch wording, not meaning; the table in section 2 has rows the script cannot see (P1 v3:25 misread wording, P12 v5:54 and :58 softening, P13 v2:3 blind as a step, _COMMON_RULES_v5:33 kit stop). A pointer to LEVER_RULES_v3 is correct today and only becomes wrong after PROCEED; the script reports it as POINTER so the switch is one sweep.


Open points for Ayush
1 settings.json lacks keys the rules say it holds: oracle runs (T46), Docker limits (R19 to R24), time limit factor 4 (T43), runs per task (T33), auto limits and models (A11 to A13). Add them with the values in 3.2?
2 issue.py on a non current template: warn (refused unless --force-lint, like today's lint) for older or dormant, hard refuse only for retired P7 and P8 and a missing Template line. Or warnings only (T23 spirit)?
3 Honesty negatives: _COMMON_RULES_v5:54 has J3a minus 3 and J3b minus 5; BUILD_RULES RUBRIC says "Honesty negative minus 3 in every judge". Keep J3b at minus 5 or set it to minus 3?
4 The judge probe band (8 to 16 trajectory probes, 55 to 70 percent of judge weight; _COMMON_RULES_v5:56, P2_v5:111, P9_v4:60) is LEVER_RULES text that BUILD_RULES does not carry. Keep it as how to text, or drop it?
5 P12_v5:68 trap survival "each lever must keep at least 90% of its before loss": not in the rules or settings. Make it a settings key, or drop it in favour of T22 (no softening without Ayush's word)?
6 Dormant P3 to P6: retire them (history only), or keep them dormant with a warning?
