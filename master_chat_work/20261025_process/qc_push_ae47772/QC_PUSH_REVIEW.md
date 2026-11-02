# QC push review: Input_Bundle_QC 976c1666 -> 5574d77e (board ae47772)

Commit 5574d77e by Sugam Agrawal: "QC: the prompt is the coverage unit, plus IN-17 against pre-announced discoveries". `git diff --stat 976c1666 5574d77e`: 7 .md files, 39+/26-; no script changed (exe_copy.py, instruction_qc.py, judge_qc.py, structure_qc.py, tests_qc.py byte-identical to the old fingerprint). Every changed check is **manual**; no script-owned check moved.

Session rename: `name_session.py ae47772` printed `codex: no match` and matched opencode `ses_e8e0892c0ffeodLqXVJbWNJQ5Q` (rename OK). Clone `git status --porcelain | grep -v '^??'` was empty before and after.

Citations: `01:45` = `Input_Bundle_QC/01_Instruction_QC.md` line 45 in the working tree (== 5574d77e). `old 01:45` = `git show 976c1666:Input_Bundle_QC/01_Instruction_QC.md`. FC = Final_checklist.md. LR = knowledge/LEVER_RULES_v1.md, QR = QC_RULINGS.md, PB = QC_FIX_PLAYBOOK_v2.md, DL = DELIVERY_LEARNINGS.md, LA = LEAK_AUDIT.md.

**The push in one sentence:** for facts about the deliverable, a test is now fair if the instruction states the fact OR the shipped input settles it determinately, with no pointer needed (03:19, 03:50, 05:21, 04:92, FC:428). Rules of engagement (scope, tool use, prohibitions, operating procedure) still need a written sentence (03:50, 04:94-95, 05:21). Silence never counts (05:27). A new FAIL check, IN-17 (01:47), bans instruction sentences that announce a discovery the input already establishes.

---

## 1. Diff, hunk by hunk

| # | file:line (new) | check id | old wording (short) | new wording (short) | severity | owner | kind |
|---|---|---|---|---|---|---|---|
| 1 | 01:44 | IN-14 | fine example "make sure the totals match across both sources" | example becomes "the figures in your summary must agree with the ledger". New clause: orientation or finished-shape sentences are fine "without telling it what it will find in the data, the line IN-17 draws" | unchanged | manual | clarified |
| 2 | 01:45 | IN-15 | rule must be in "the instruction itself, or a specification or rules file the instruction points the agent to" | "stated in a sentence the agent can read: the instruction itself, or any file inside the input directories `environment/Dockerfile` copies" and "need not name the file". Count any criterion that enforces a rule of engagement whatever its label. Conduct criteria (verification, honest reporting, restraint) need no sentence; conduct wearing an `instruction following` label is a gate-04 labelling defect | unchanged | manual | loosened (locus) + clarified (conduct excluded) |
| 3 | 01:46 | IN-16 | — | byte-identical; only the surrounding lines changed | — | manual | unchanged |
| 4 | 01:47 | **IN-17 (new)** | — | "The instruction must not pre-announce what the agent is supposed to discover. Withholding is the default and difficulty is the point". Two conditions must both hold: (1) the sentence announces something meant to be found (an input property, edge case or branch); (2) the shipped input already establishes it (AL-1 determinate). If the input does not establish it, the sentence is a requirement and stays. Rules of engagement, CL-6 signposts, IN-16 settlers and DS-25 literals are never hints. "Default to keeping the sentence"; to fail it you must "name the discovery the sentence replaces, and point to where the shipped input already establishes it" | **FAIL** (01:91) | manual | new |
| 5 | 01:61 | manual-only list | — | adds "IN-17 pre-announced discoveries" | — | manual | new |
| 6 | 01:87 | IN-17 checklist | — | "no sentence announcing a discovery the shipped input already establishes (name both ...), anything the data cannot establish, rules of engagement included, is a requirement and stays" | — | manual | new |
| 7 | 01:91 | severity line | fail list without IN-17 | fail list adds IN-17 (both the discovery and the input evidence named) | FAIL | manual | new |
| 8 | 02:67 | DS-19 | "contract is the instruction plus any specification or rules file it points the agent to" | rule of engagement counts when "stated in a sentence the agent can read, in the instruction or in any file inside the input directories" Dockerfile copies | unchanged | manual | loosened (locus) |
| 9 | 03:3 | gate-03 header | read "instruction.md together with any specification ... it points" | read "instruction.md and the input directories environment/Dockerfile copies into the agent image" | — | manual | loosened |
| 10 | 03:19 | gate-03 intro | "The contract is the instruction together with any specification, schema or rules file the instruction points the agent to" | "A test is fair when what it reads is either promised by the instruction or determinate in the input the agent was handed, and the prompt does not have to point at the file" | — | manual | loosened |
| 11 | 03:50 | TS-19 | learnable = instruction or the specs it points to | "stated in the instruction OR determinate in the input the agent is handed ... need not name the file". New carve-out: "a check on what the agent left alone, or on which paths it touched, needs a sentence that states the rule, because discovery establishes facts and never prohibitions"; "every promise the instruction makes" | unchanged | manual | loosened (outcome) + tightened (rules-of-engagement carve-out) |
| 12 | 03:120 | TS-19 checklist | — | adds "reading the shipped input as well as the prompt; a check on what was left alone rests on a stated sentence, not on discovery" | — | manual | loosened + tightened |
| 13 | 04:3 | gate-04 header | spec files it points to | input directories Dockerfile copies | — | manual | loosened |
| 14 | 04:92 | JD-15 | outcome criteria: "only meet it if the contract said so" (instruction plus pointed-to specs) | "if it could have known. Two grounds count and either one is enough: the instruction states it, or it is determinate in the input"; "Name the sentence it traces to, or the shipped fact it reads". Constraint criteria: "it has to be STATED ... a prohibition cannot be inferred from a CSV"; output-shape rules keep the outcome burden ("a shipped example included"); a rule that cannot be stated without disclosing the approach is conduct | unchanged | manual | loosened (outcome) + clarified (constraint) |
| 15 | 04:94 | JD-16 item 1 | rule must be in the contract (pointer form) | "STATED in a sentence the agent can read, in instruction.md or in any file inside the input directories"; "Discovery counts for the two shape kinds in item 2 and not for the other four" | unchanged | manual | reworded |
| 16 | 04:95 | JD-16 item 2 | six kinds, one burden | format/output-shape = outcome burden (instruction sentence or example actually given in copied input); scope, tool-use, negative, procedural = must be stated. Ordering splits: "which error wins when a fixture carries two faults" is an output property; "reconcile before you export" must be stated; "parse the header before the body" is approach = preference | unchanged | manual | loosened (shape) + clarified |
| 17 | 04:139 | JD-15 checklist | contract pointer form | rewritten to the two grounds | — | manual | loosened |
| 18 | 05:21 | AL-1 | tests may read only what the instruction or the specs it points to promise | "Two grounds count and either one is enough. The instruction states it, or the fact is there to be found in the input ... whatever that directory is called. The prompt does not have to point at the file ... what the fact does have to be is determinate, something the agent can read off the shipped input rather than something the input merely fails to contradict". tests/ and solution/ never count. Rules of engagement need a sentence or must be met by every competent route; "No amount of discovery substitutes, because a prohibition cannot be inferred from a CSV" | unchanged | manual | loosened + clarified |
| 19 | 05:22-32 | AL-1 worked table (new) | — | 05:26 timestamps can be absent / 3 of 40 rows empty / yes; 05:27 ids can repeat / all shipped ids distinct / no, "silence settles nothing"; 05:28 round half to even / amounts already two decimals / no for the rule, yes for the width, "the samples show the shape and not the rule behind it"; 05:29 fiscal year April / `fiscal_start = "04-01"` in config / yes; 05:30 vendor off limits / vendor/ ships / "no, a prohibition is never determinate". 05:32 "one file can settle one demand and leave the next one open" | — | manual | new (clarifying) |
| 20 | 05:33 | AL-2 | "For each instruction requirement: point to the test (or criterion)" | "Enumerate from `instruction.md` alone. The unit here is what the PROMPT promises"; a spec's spare detail is not an ungraded promise; delegation is expanded into "the delegated rules the delegation actually invokes, not the whole file" | unchanged (strict) | manual | reworded (unit narrowed, delegation expanded) |
| 21 | 05:34 | AL-3 | "can see" = instruction plus the specs it points to | instruction "and anything shipped in the input directories ... whether or not the prompt names them" | unchanged | manual | loosened |
| 22 | 05:35 | AL-4 | contract = instruction plus pointed-to specs | "the instruction together with whatever the copied input establishes (AL-1)" | unchanged | manual | loosened |
| 23 | 05:38 | AL-27 | "every ordering, precedence, or tie-break rule the instruction states" | "every ordering, precedence, or tie-break rule the bundle grades, whether the instruction states it or the copied input establishes it (AL-1)" | unchanged | manual | tightened (scope widened to evidence-established orderings) |
| 24 | 05:95-96 | AL-1 / AL-2 checklist | pointer form | AL-2: "every promise enumerated from `instruction.md` alone, delegating sentences expanded into the rules they invoke, each graded by a test or a criterion" | — | manual | reworded |
| 25 | FC:426 | double-check material | "any specification ... it points the agent at under environment/" | "the input directories `environment/Dockerfile` copies"; rationale: otherwise "every test reading a fact the agent could discover from its own data looks unpromised" | — | manual | loosened |
| 26 | FC:428 | Coverage item 1 | instruction requirements plus pointed specs | enumerate from the prompt alone and expand delegation; reverse direction: no test may verify anything "neither promised by the instruction nor determinate in the input"; "name either the sentence it enforces or the shipped fact it reads"; a rule-of-engagement test needs a sentence | unchanged | manual | loosened + reworded |
| 27 | FC:491 | CL-4 | — | byte-identical (kit exemption "states out loud that only an exact match counts" kept) | — | manual | unchanged |
| 28 | FC:492 | CL-5 | "stated in the contract (`instruction.md` or a spec file it points the agent to)" | "stated in the instruction, or be established by an example the agent is actually given in the copied input, or be compared in a way that does not care" | unchanged | manual | loosened |
| 29 | Starter:50-51 | gate 7 / gate 8 evidence | "any spec file it points at under environment/" | "the input directories environment/Dockerfile copies" | — | manual | clarified |

**Unchanged, context only:** IN-16 01:46, CL-4 FC:491 and 05:88, TS-18 03:49 (tolerances still stated in the instruction), DS-21 02:70, DS-25 02:71, CL-6 FC:493 / 05:90, AL-28 05:39, IN-9 01:39.
**Kit inconsistency:** the CL-5 checklist line 05:89 still reads "stated in the contract", while FC:492 now accepts a shipped example. A reviewer working from gate 05 alone could still raise the old CL-5. We should cite FC:492.

**Changed check ids (13):** IN-14, IN-15, IN-17 (new), DS-19, TS-19, JD-15, JD-16, AL-1, AL-2, AL-3, AL-4, AL-27, CL-5. Lines without a check id: 01:61, 01:91, 03:3, 03:19, 04:3, 05:22-32, FC:426, FC:428, Starter:50-51.

---

## 2. What it does to our rules

Verdict key: **still required** = QC still demands it (or it guards difficulty in a way QC backs); **looser** = our rule now demands more than QC; **conflicts** = our rule now breaks QC; **unchanged** = QC basis untouched.

### LEVER_RULES_v1

| our rule | old QC basis | new QC text | verdict |
|---|---|---|---|
| LR:24 never-used list (as a whole) | old IN-15 pointer form (old 01:45), IN-16 01:46 | 01:45 any copied file, no pointer; 05:21 determinate input is a ground; 05:27 silence settles nothing | **looser**: items whose answer the input determinately settles are now QC-legal; silence items still forbidden (item list in Q3) |
| LR:48 W1 never explain a trap, no "note that", no trap lists or rule counts | DS-21 (02:70); our own difficulty rule | **01:47 IN-17** (FAIL) now bans announcing a discovery the input establishes | still required. QC now backs it. Ours is stricter (bans counts and lists even when the input does not establish them; IN-17 keeps such sentences as requirements) |
| LR:49 W2 rule sits in the governing file, instruction only points | old 01:45 delegation | 01:45 "need not name the file" | **looser**: a pointer is optional; a sentence in any copied file counts |
| LR:50 W3 plain forms | IN-16 | 01:46 unchanged | unchanged |
| LR:51 W4 an override names its field exactly | IN-16 | 01:46 unchanged; 05:32 one file can settle one demand only | unchanged |
| LR:52 W5 shipped separating case for L5 only; others hidden-only; shipped never contradicts | IN-15 + TS-19 | 03:50, 05:21 | still required for stated levers. For an evidence-ground lever it inverts: the shipped input MUST hold the separating case or the fact is not determinate (05:27, 05:28) |
| LR:53 W6 no worked example where readings differ | difficulty rule (not QC) | 05:21 a worked example is now a ground; FC:492 | unchanged (QC-neutral). Note: the shipped separating example is exactly what makes an unwritten rule legal |
| LR:54 W7 shipped control honest; what it checks stated in the same file | TS-19 contradiction | 03:50, 05:21 | still required (a control that contradicts a graded value fails TS-19). The "stated in the same file" half is now looser (05:21) |
| LR:55 W8 one instruction sentence names which document wins | IN-16 | 01:46 unchanged; 01:47 exempts settlers of graded ambiguity | unchanged |
| LR:56 W9 literal-reading self-test | IN-16 | unchanged | unchanged |
| LR:57 W10 one rule document; instruction states no rule of its own | old 01:45 pointer | 01:45; 05:33 AL-2 enumerates from the prompt, delegation expanded | **looser** (QC-neutral on where rules sit). Wholesale delegation still pulls every invoked rule into AL-2 |
| LR:61 G1 owned rows; coupling "stated in the instruction or contract" | CL-4, IN-15 | FC:491 unchanged; 05:21 a coupling the input determines is a ground | **looser** on the coupling sentence; CL-4 part unchanged |
| LR:62 G2 each test asserts its own rows | TS-13 | unchanged | unchanged |
| LR:63 G3 hidden reruns >=30% weight | ours (not QC) | — | unchanged |
| LR:64 G4 negatives only for cheating acts | AL-28, TS-19 | 03:50 carve-out "needs a sentence that states the rule"; 05:21; 04:95 | still required (now explicit in QC) |
| LR:65 G5 instruction states whole-document exactness | CL-4 exemption FC:491, TS-19 | FC:491 unchanged; 01:47 "any statement of finished-work shape" fine | still required for the exactness clause |
| LR:66 G6 >=2 mutation tests | TS-26 | unchanged | unchanged |
| LR:67 G7 assertion messages | ours | — | unchanged |
| LR:68 G8 hidden seeded generator | TS-19 bounds | 03:50 | unchanged |
| LR:69 G9 expected values independent of the oracle | ours | — | unchanged |
| LR:70 G10 cost table + differential fuzz | ours | — | unchanged |
| LR:71 G11 RULE_COVERAGE one row per rule in the contract file | AL-27 (old: "rule the instruction states") | 05:38 AL-27 now covers rules "the copied input establishes"; 05:33 AL-2 unit = prompt + invoked delegated rules | still required, and it must **widen** to orderings the evidence establishes |
| LR:72 G12 generator bounds + plants every branch | TS-19 | 03:50; 05:28 a sample shows the shape, not the bound | still required |
| LR:76 J1 no figure restating output | JD-8 | unchanged | unchanged |
| LR:77 J2 conduct criteria on a self-constructed case | JD-15 conduct | 04:92 conduct branch unchanged; 01:45 conduct needs no sentence | unchanged (no instruction sentence needed for J2) |
| LR:78 J3 honesty negative | JD conduct | unchanged | unchanged |
| LR:79 J4 code quality | JD-18 | unchanged | unchanged |
| LR:80 J5 no criterion endorses a penalised reading | JD-7 | unchanged | unchanged |
| LR:81 J6 per-item enumeration | JD | unchanged | unchanged |
| LR:82 J9 altered-copy run | conduct | 01:45 | unchanged |
| LR:83 J7 deterministic behaviour = test | JD-9 | unchanged | unchanged |
| LR:84 J8 no criterion restating a graded method | JD | 04:95 approach = preference | unchanged |

### QC_RULINGS

| our rule | old QC basis | new QC text | verdict |
|---|---|---|---|
| QR:12 IN-15 dispatch v1:35 FAIL | old 01:45 | 01:45 | unchanged (INFERRED: no locus fact in the row changes it) |
| QR:13 IN-15 dispatch v2:40 "every negative's trigger list must match an instruction sentence" | old 01:45 | 01:45, 03:50 carve-out, 04:95 negative kind stated | still required (any copied file may now hold the sentence) |
| QR:14-17 IN-15 cohort / vendor / emberforge / district-heat | old 01:45 | 01:45 | unchanged (INFERRED) |
| QR:22 IN-16 emberforge FAIL | 01:46 | 01:46 unchanged | unchanged |
| QR:23 IN-16 schema float cast FAIL | 01:46 + old CL-5 | FC:492 an example actually given can establish the type; 04:95 shape = outcome burden | **looser**: a shipped example output now settles a type |
| QR:24-27 IN-16 district / vendor decoy / cohort gaps / district default | 01:46 | unchanged | unchanged |
| QR:43 TS-19 district bounds FAIL | TS-19 | 03:50; 05:28 | still required |
| QR:44-48 TS-19 vendor / emberforge / schema K19 | TS-19 | 03:50 | unchanged |
| QR:49 TS-19 dispatch value type, "state types for every graded key" | old CL-5 | FC:492; 04:95; 05:28 (width yes) | **looser**: an example in the copied input settles a type |
| QR:50-52 TS-19 run cap WARN / cohort / district traced | TS-19 | 03:50 | unchanged |
| CL-4 (no QR row; see PB:51) | FC:491 | FC:491 byte-identical | unchanged |

### QC_FIX_PLAYBOOK_v2

| our rule | old QC basis | new QC text | verdict |
|---|---|---|---|
| PB:8 bypass = satisfy exactly | — | — | unchanged |
| PB:13 "every rule of engagement (how the program works, formats, literals, conventions, precedence) stated in a file the agent can read" | old 01:45, CL-5 | 04:95 formats/shape = outcome burden; FC:492; 05:21 | **looser**: our "rule of engagement" bundles in formats, literals and precedence, which QC now lets the input settle |
| PB:14 IN-16 three parts | 01:46 | unchanged | unchanged |
| PB:15 AL-2/AL-27 | old 05 | 05:33, 05:38 | still required (re-key to the prompt unit; widen AL-27) |
| PB:18 DS-4 | — | — | unchanged |
| PB:21 fix directions order ((5) state the missing rule once) | old 01:45 | 05:21 | **looser**: a new direction "ship a determinate fact" now fixes AL-1/TS-19 |
| PB:22 soft directions never | — | — | unchanged |
| PB:27 IN-15 row (state once in the governing file; precedent "kit 01:45 delegation allowed") | old 01:45 | 01:45 | **looser** (no pointer needed); re-quote the new wording |
| PB:28 IN-16 | 01:46 | unchanged | unchanged |
| PB:29 AL-2/CL-1 | old AL-2 | 05:33 | still required (enumerate from the prompt) |
| PB:30 AL-2b, PB:31 AL-18 | — | — | unchanged |
| PB:32 AL-27 RULE_COVERAGE one mutant per contract rule | old AL-27 | 05:38 | still required, widen to established orderings |
| PB:33 AL-28, :34 S6, :35 TS-26/JD-14, :36 TS-13, :37 TS-23, :38 TS-20, :39 TS-16 | — | unchanged | unchanged |
| PB:40 TS-19 (add grader + generated case; never describe the hidden distribution) | TS-19 | 03:50 | still required |
| PB:41 TS-25, :42 JD-7, :43 DS-22, :44 DS-20 | — | unchanged | unchanged |
| PB:45 JD-15/JD-16 never announce in the instruction what the judge looks for | JD | 04:92-95; 01:45 conduct needs no sentence | unchanged (QC now agrees conduct needs no sentence) |
| PB:46 JD-18, :47 DS-4, :48 DS-6 | — | — | unchanged |
| PB:49 SUGGEST KEEP with kit line 01:45/01:46 | old 01:45 | 01:45 | unchanged (re-cite the new 01:45 text) |
| PB:50 JD-5, :52 JD-8, :53 NEW-CHECK, :54 NOISE | — | — | unchanged |
| PB:51 CL-4 partition, or kit exemption | FC:491 | FC:491 unchanged | unchanged |

### Templates

| our rule | old QC basis | new QC text | verdict |
|---|---|---|---|
| P2_build_v3.md:43 "Every graded rule is fully stated in a visible file (IN-15) ... never from secrecy" | old 01:45 | 01:45 (rules of engagement only), 05:21, 03:50, 01:47 "Withholding is the default" | **looser**: for deliverable-property rules QC accepts determinate evidence |
| P2_build_v3.md:88 G11 RULE_COVERAGE one row per contract rule | old AL-27 | 05:38, 05:33 | still required (widen) |
| P2_build_v3.md:97 Phase 5 J1-J9, J2 performed by the solve.sh self-check stage | JD-15 conduct | 04:92 conduct unchanged | unchanged |
| P2_build_v3.md:105 state whole-document exactness "on these files and on fresh extracts at other scales"; "there is no count to check yourself against" | FC:491, TS-19 | FC:491 unchanged; 01:47 shape fine | **looser**: QC requires only the exactness clause. "Other scales" and "no count" are not QC-required, and LA §2 rank 2 says they leak |
| P9_harden_from_results_v2.md:53 G5 mandate | FC:491 | FC:491 | **looser** (same reasoning as P2:105) |

**Tally:** 12 rules now looser than QC needs (LR:24, W2, W10, G1, QR:23, QR:49, PB:13, PB:21, PB:27, P2:43, P2:105, P9:53). 0 now conflict. The rest are still required or unchanged.

---

## 3. Lever shapes under the new QC

The dividing line (05:21-32): an input fact counts if the agent can **read it off** the shipped input, and that holds only when the input *contradicts* the wrong reading. These count: a present data property (05:26), a config value (05:29), or an example actually given, which settles shape (FC:492, 04:95). These do not count: inputs that merely fail to contradict (05:21), all-distinct samples (05:27), pre-formatted values, which show the shape but not the rule (05:28), and any prohibition (05:30). A file may settle one axis and leave the next open (05:32).

| shape (DL line) | verdict | deciding new sentence |
|---|---|---|
| S1 whole-doc exact per hidden corpus, exactness stated (DL:133) | allowed | FC:491 unchanged; 03:50 |
| S2 data rule that is a no-op on shipped data, rule stated (DL:134) | allowed if stated. Unstated plus no-op = silence, still forbidden | 05:27, 05:28 |
| S3 held corpora reorder decoys / swap base config (DL:135) | allowed inside bounds that are stated or determinate | 03:50; 05:28 (bounds are not readable from samples) |
| S4 listed candidate set + single-feature seal (DL:136) | allowed: a listed set is determinate | 05:21, 05:29 analog |
| S5 anchored mirror views (DL:137) | allowed | 05:21 |
| S6 quiet shipped run + "idle rules are live elsewhere" (DL:138) | allowed only if the idle rules are stated; the idle line itself passes IN-17 | 05:27 (an idle rule is unestablished); 01:47 |
| R1 withheld constant recovered by calibration (DL:144) | **now allowed** if the calibration pins a unique value; still risky if several values fit | 05:21 "read off ... rather than ... merely fails to contradict"; 02:70; 01:39 |
| R2 defined quantity, binding time unstated (DL:145) | **now allowed** if a shipped record separates the binding times; risky otherwise | 05:21, 05:28; IN-16 01:46 part 3 |
| R3 ordering with open operand (DL:146) | **now allowed** if the input establishes the operand (AL-27 then needs a mutant); risky otherwise | 05:38, 05:21 |
| R4 scope by omission (DL:147) | still risky. Path or edit scope is forbidden unless stated | 05:27; 04:95; 03:50 |
| R5 bare definition + residue fitting the narrow reading (DL:148) | still risky unless the residue contradicts the wide reading | 05:21 "merely fails to contradict" |
| R6 silent shipped-code fault (DL:149) | still risky / forbidden | 05:27; CL-6 FC:493 |
| R7 overloaded term (DL:150) | still risky | 01:46 |
| R8 closed-list definition with an arguable absent input (DL:151) | still risky | 01:46 |
| R9 stated core gate on whole-doc checks (DL:152) | allowed | FC:491 |
| R10 whole-report mutation tier, no partial credit (DL:153) | allowed | FC:491; TS-26 unchanged |
| R11 combined-axis hidden store (DL:154) | still risky | 03:50 bounds |
| N1 unstated key vocabulary / value type gate (DL:160) | **now allowed** if a shipped example establishes the keys or types; forbidden otherwise | FC:492; 04:95; 02:71; 05:28 |
| N2 test stricter than the contract (DL:161) | forbidden | FC:428 reverse direction |
| N3 hidden rule with no evidence path (DL:162) | forbidden | 02:70; 05:27 |
| N4 negatives grading a lever (DL:163) | forbidden | 05:39 AL-28; 03:50 carve-out |
| N5 format carried only by shipped working code (DL:164) | still risky. Code is not "an example the agent is actually given" (INFERRED reading of FC:492) | FC:492; FC:493 |
| N6 hidden tests reachable in the image (DL:165) | forbidden | unchanged |
| N7 exact match on a judgement field (DL:166) | forbidden | unchanged |

---

## 4. IN-17 scan of our 8 bundles (instruction.md only)

How the scan worked: I read only the 8 `instruction.md` files. **Every input-side claim below is INFERRED** from the instruction's own wording and the task design; I did not open the shipped input to confirm. A sentence counts as a hit when (1) it announces a property, edge case or branch of the input, and (2) that input (named) would establish it. Strength: strong = names the exact discovery; moderate = names the family or branch; weak = conditional on how the input looks.

### Hits (sentences IN-17 would remove)

| id | bundle:line | sentence (short) | discovery it replaces | input that carries it (INFERRED) | strength |
|---|---|---|---|---|---|
| C-2 | caldermoor:64-70 | rule-family list: "which classes read that order backwards", "the intervals inside which an alias holds", "which reference takes which instant" | that some classes reverse the rank order; that aliases are interval-bound; per-reference instants | precedence charter / identity register in /app data | strong |
| M-2 | match-replay:3 | "Two captures carry a flag word of zero and can be read straight off the wire" | which captures are untransformed, and how many | capture headers | strong |
| M-3 | match-replay:3 | "Eleven numeric quantities ... appear in no shipped file" + calibration "ordered so that each figure is fixed by the quantities pinned by the figures ahead of it together with one further quantity" | how many unknowns there are and that calibration is triangular | calibration slice + notes candidate sets | strong |
| M-4 | match-replay:5 | "Unit identity is not what a capture recorded: the roster carries openings, closings, successions and merges" | that ids are remapped by roster events | roster file | strong. The "identity in force at that entry's tick" clause stays as a binding-time requirement |
| M-5 | match-replay:5 | charter stocks "stand in a coupled relation ... a unique stable assignment exists and has to be solved for rather than approached by repeated substitution" | the system is coupled with a unique fixed point; iteration traps | engine notes | strong |
| S-2 | sentinel:3 | "rather than by reading a value from a file reached out of order" | that an out-of-order file carries a different value | the reference corpus dependency chain | moderate. "in its documented order" stays |
| C-1 | caldermoor:1-2 | "eight local feeds that disagree with each other" | that the feeds conflict | the eight feeds | moderate |
| M-1 | match-replay:3 | flag word names transforms; notes state them "in no particular order of application" | that the notes' order is not the application order | capture headers / serializer notes | moderate |
| M-7 | match-replay:5 | "exactly one set drawn from the bench candidates meets the upkeep target exactly" | uniqueness of the bench solution | bench candidate list | moderate |
| S-1 | sentinel:1 | "Several of those files are superseded or retired." | which files are stale | version/status fields in the reference files | weak (exempt as a CL-6 signpost if nothing in the input marks them) |
| T-1 | tariff:1 | "some of the repository's own unit tests ... pass only because they assert the drifted behaviour" | that the unit tests encode the bug | /app tests + failing log | weak (the line 3 requirement "correct any unit test that asserts something the contract contradicts" carries the duty) |
| MU-1 | metered:9 | contract contents list "which records are quarantined and why, how plans and segments change during the month" | that plans change mid-month; that quarantine exists | rating_contract.md + collector files | weak (the list describes where the rules are) |
| M-6 | match-replay:5 | "a binary floating-point pipeline will not reproduce the settled charter stocks" | float drift breaks the result | engine figures | weak ("Work ... in exact rational arithmetic" stays as a procedural requirement) |

**Count:** 13 listed: 5 strong, 4 moderate, 4 weak. **9 strong+moderate** are the ones a reviewer could name with both parts. Spread: match-replay 6, caldermoor 2, sentinel 2, tariff 1, metered 1. sensor, district-heat and data-product have no hits.

### Sentences IN-17 lets stay

| bundle:line | sentence (short) | why it stays (kit line) |
|---|---|---|
| district:7, tariff:13, metered:28, data-product:14, match-replay:13, caldermoor:18-25, sentinel:5 | G5 "graded whole on fresh inputs / fresh corpora of other periods and sizes / other scales" | states the finished work's shape and the grading regime, not an input property (01:47 "any statement of finished-work shape"). IN-17 does not remove them. Whether to keep "other scales" is a difficulty question (LA §2 rank 2), not a QC one |
| metered:28-32, data-product:16, district:9 | self-check paragraphs ("recompute ... a second way, outside the program", "copy of the data whose contents you have changed", "Work out the expected figures ... on your own") | conduct guidance, no input property (01:47). Since 01:45 conduct criteria need no sentence, so these are optional for QC and droppable for difficulty |
| metered:28 | "Apart from the record counts in collector_controls.json, nothing in /app/data gives an expected count" | a statement about what is absent, not a discovery |
| sensor:1 | "An earlier adjustment run ... cannot be reused" | CL-6 not-authoritative signpost (01:47 exempts it) |
| tariff:3, data-product:3, metered:9, caldermoor:70-72 | "the contract wins" / "Where a rule and a habit disagree, the rule stands" | settles a graded ambiguity (IN-16; 01:47 exempts it) |
| caldermoor:79-83, match-replay:11, sentinel:9 | nothing edited / staging dir / enumerate candidates first / stdlib + pyarrow | rules of engagement, requirements by construction (01:47; 03:50; 04:95) |
| sentinel:7, match-replay:9, caldermoor:27-30, :74 "five identities" | output fields and report shape | finished-work shape (01:47; DS-25). Our W1 still dislikes the count in caldermoor:74 |
| match-replay:5 "to the identity in force at that entry's tick", "Entries outside every live window are set aside" | binding time and scope | rules the input cannot establish (a binding time is not determinate from samples, 05:28), so they are requirements |
| metered:1 "each write their own file in their own format" | orientation | borderline. Not counted: it names no specific discovery |
| district:1 "work out from them how the files fit together", caldermoor:7-8 "working out which feeds govern which figure is part of the work" | orientation | discloses nothing (01:47) |

### Peer patterns (card quotes only)

| pattern | IN-17 verdict |
|---|---|
| T1 instruction bullets "Rules for the calculation" (smaller lot, floor before reweight, LIVE sheet ...) (poonam C_00372225 card :14) | pass: the bullets state rules (requirements). "DRAFT ... not authoritative" is a CL-6 signpost (01:47). Its 0 yield on those levers (DL:107) comes from difficulty, not QC |
| chainfold "The run you can see is a quiet one. Rules that sit idle in it are live in other runs" (dinshi card :49) | pass: it names no discovery the input establishes, and the hidden part cannot be established (01:47 condition 2) |
| b47 "written down nowhere in the rulebooks" (sugam_b card :50) | likely pass: it says THAT conventions are unwritten, not WHICH ones. Residual risk: a reviewer may call it the announcement of a hidden branch. To fail it they would have to name the convention and the register line that establishes it |

---

## 5. Open questions under the new QC

| Q | verdict | deciding kit line | residual QC risk |
|---|---|---|---|
| Q1 graded rule recoverable from shipped evidence without a sentence? | **YES, for deliverable-property rules; NO for rules of engagement.** Determinate: a config value (05:29); a present data property (05:26); an example actually given, for output shape and types (FC:492, 04:95); a worked example, digest or calibration record **only if it contradicts every wrong reading** (05:21, 05:32). Silence: all-distinct or pre-formatted samples (05:27, 05:28); a branch that never fires in shipped data; readings that coincide on shipped data; any prohibition (05:30) | 05:21, 05:22-32, 03:50, 04:92, FC:428 | the reviewer judges "determinate" by hand. Ship an EVIDENCE_MAP naming the file:line that separates the readings. The CL-5 checklist (05:89) still has the old wording |
| Q2 leave one axis unwritten when the input settles it? | **YES when the input settles it; NO when it is silent.** Binding time, operand and candidate set can be settled by a separating record or a listed set. Path or edit scope never can (04:95). An empty value is settled only if a shipped row shows it | 05:21, 05:27, 05:32, 01:46 (part 3 unchanged), 05:38 | AL-27 now asks for a mutant on each established ordering. If the axis is graded but the input is silent, IN-16 still fails |
| Q3 LR:24 item by item | **partly**: (1) undefined symbol: looser if a config value defines it; (2) ambiguous fallback scope: still forbidden unless settled; (3) "shipped slice only" promise: still forbidden (TS-19 contradiction; INFERRED meaning); (4) override with different vocabulary: looser if a mapping table ships; (5) unstated tie-break: looser if a shipped case separates (05:38), silence still forbidden; (6) flag vs date: looser with a separating record; (7) unmapped code with no outcome: still forbidden (silence); (8) nullable field without null condition: looser only with an example plus a determinate condition; (9) merge winner: looser if the register is determinate; (10) two-antecedent pronoun: unchanged (IN-16); (11) answer key contradicting the contract: unchanged (TS-19, CL-6); (12) malformed reference row with no outcome: unchanged (silence) | 05:21-32; 01:46; 03:50 | 6 items loosen, 6 hold |
| Q4 does IN-17 forbid G5 / self-check / coupling / "idle rules" sentences? | **NO** to all four. None announces an input property: G5 and coupling state the finished shape, the self-check is conduct, and the idle line names no discovery | 01:47 "any statement of finished-work shape", "name the discovery the sentence replaces"; 01:45 conduct needs no sentence | a coupling sentence that names a specific input property ("rows X and Y share Z") would be a hit. Dropping the self-check and "other scales" is a difficulty choice (LA §2 rank 2) |
| Q5 does AL-2 "from instruction.md alone" remove G11? | **NO.** AL-2 narrows the promise unit (spare spec detail is not a promise), but wholesale delegation still invokes every rule. AL-27 now also covers orderings the input establishes, so G11 must grow | 05:33, 05:38 | an evidence lever with no mutant row fails AL-27 |
| Q6 is whole-document exact grading per hidden corpus affected? | **NO.** CL-4 is byte-identical and the exemption still needs the instruction to state exactness. FC:492 helps: output conventions may now come from a shipped example | FC:491, FC:492 | none new |
| Q7 DL §8 and LA §5 | see the table below | — | — |

| question | verdict | basis |
|---|---|---|
| DL8(1) keep LR:24 or admit R2/R3 with one settling sentence? | **SETTLED**: admit R2/R3 when the input determinately settles them, even with no sentence; silence still needs a sentence | 05:21, 05:27, 05:38 |
| DL8(2) adopt stated exactness + stated core gate? | STILL OPEN (QC-neutral; CL-4 unchanged) | FC:491 |
| DL8(3) retire H7, move to repair-with-kept-operand or evidence induction? | **SETTLED (QC side)**: evidence induction with a listed candidate set is QC-legal; the choice is now about yield | 05:21, 05:29 |
| DL8(4) ban all shipped expected output vs an honest control? | STILL OPEN. Examples are now a contract ground; a contradicting example is a TS-19 fail | FC:492, 03:50 |
| DL8(5) blind fresh-agent read in harden rounds? | STILL OPEN (process) | — |
| DL8(6) treat "QC deferred" as passed for IN-16? | STILL OPEN (IN-16 unchanged; keep "no") | 01:46 |
| LA5(1) retire the second-pass re-share family? | STILL OPEN (QC-neutral) | — |
| LA5(2) wording Opus cannot transliterate, or move difficulty elsewhere? | **SETTLED**: difficulty may move into determinate evidence with no sentence ("Withholding is the default") | 01:47, 05:21 |
| LA5(3) drop the G5 fresh-inputs sentence and the self-check paragraph? | PARTIAL: QC needs neither the self-check (01:45) nor "other scales"; keep the exactness clause (FC:491) | 01:45, FC:491 |
| LA5(4) widen Never 11 to consistent answer keys? | STILL OPEN (difficulty; now in tension with FC:492, which makes examples a ground) | FC:492 |
| LA5(5) match-replay probe first or fix blind? | STILL OPEN; IN-17 adds a QC reason to fix its instruction first (6 hits) | 01:47 |

**questions_settled = 9** (Q1-Q6, DL8(1), DL8(3), LA5(2)); LA5(3) is partial and not counted.

---

## 6. Proposed changes (NOT applied)

### LEVER_RULES v2 delta

| id | change | rests on | risk |
|---|---|---|---|
| D1 | Split LR:24 into (a) a silence list, still never used: items 2, 3, 7, 10, 11, 12; and (b) a determinate-evidence list, allowed with an EVIDENCE_MAP row: items 1, 4, 5, 6, 8, 9 | 05:21, 05:27, Q3 | the reviewer may judge a borderline case "merely fails to contradict" |
| D2 | Add a "determinate test" section copying the 05:22-32 table: the fact must contradict the wrong reading; one file settles one axis | 05:22-32 | none |
| D3 | W1: cite IN-17 (01:47) and add the two-condition self-check; keep our stricter ban on counts and trap lists | 01:47, 01:87 | none |
| D4 | W2/W10: the pointer is optional (01:45). Wholesale delegation still makes every invoked rule an AL-2 row (05:33) | 01:45, 05:33 | none |
| D5 | W5: an evidence-ground lever must ship its separating case (in a non-answer-key carrier), unlike a stated lever | 05:27-28 | leak risk: the agent sees the rule fire (LL :10). Use a single separating record, never a solved list |
| D6 | G4: every negative quotes the sentence that states its rule | 03:50, 05:21, 04:95 | none |
| D7 | G5: keep "each output document is graded whole on fresh inputs"; drop "at other scales" and "no count to check yourself against" | FC:491, LA §2 rank 2 | CL-4 exemption intact |
| D8 | G11: RULE_COVERAGE rows = AL-2 units (prompt + invoked delegated rules) + every ordering or tie-break the input establishes | 05:33, 05:38 | more rows |
| D9 | New lever family L11 "evidence induction": a rule with no sentence, settled by one determinate shipped fact (a config value, a separating record, a listed candidate set), with its EVIDENCE_MAP row naming file:line | 05:21, 05:29, FC:428 "name ... the shipped fact it reads", DL R1-R3 yields 36-74% | IN-16 if the fact is not truly separating; test with W9 on the evidence |
| D10 | J2/J9: never echo the conduct wording in the instruction | 01:45 conduct needs no sentence | none |

### QC_RULINGS / QC_FIX_PLAYBOOK rows

- QR: add an **IN-17** section (empty, with the 01:47 two-condition test and the 01:87 checklist wording). Add an IN-15 note "locus = any copied file, 01:45". Annotate TS-19 :49 and IN-16 :23: an example in the copied input now settles the type (FC:492, 04:95). Add an AL-1 row with the determinate table.
- PB:13: narrow "rule of engagement" to scope / tool / negative / procedural (04:95). Formats, literals and output precedence may be settled by a shipped example or a determinate fact (FC:492, 05:21).
- PB:21: add direction "(4b) ship one determinate fact that contradicts the wrong reading" for AL-1/TS-19 findings on deliverable properties.
- PB:27 and PB:49: re-quote 01:45 ("any file inside the input directories ... need not name the file").
- PB new row **IN-17**: fix = delete the announcing sentence, or keep it if the input does not establish the fact (then it is a requirement). Never move the sentence into a "known traps" file (W1; that is the same announcement). Risk: deletion can open an IN-16 gap. Re-run W9.
- PB:15 / PB:32: widen AL-27 to established orderings (05:38). PB:29: enumerate AL-2 from the prompt (05:33).

### Templates

| file:line | proposed change | rests on | risk |
|---|---|---|---|
| P2_build_v3.md:43 | "Every rule of engagement is stated in a copied file (IN-15). A deliverable-property rule is either stated or settled by one determinate shipped fact listed in EVIDENCE_MAP (AL-1 05:21). Never by silence (05:27). No sentence announces what the input establishes (IN-17)" | 01:45, 05:21, 01:47 | IN-16 on borderline evidence |
| P2_build_v3.md:44, :104 | pointer optional (01:45) | 01:45 | none |
| P2_build_v3.md:60 | add IN-17, AL-1, AL-27 to the QC_DEFENCE ids | 01:47, 05:21, 05:38 | none |
| P2_build_v3.md:88 | G11 rows per AL-2 unit + established orderings | 05:33, 05:38 | none |
| P2_build_v3.md:97 | keep J2/J9 as judge criteria; the instruction carries no self-check paragraph | 01:45 | conduct points depend on agent habit |
| P2_build_v3.md:105 | drop "and on fresh extracts at other scales" and "there is no count to check yourself against"; keep whole-document exactness | FC:491; LA §2 rank 2 | none |
| P2_build_v3.md:106 | add the IN-17 two-condition self-check to the "no trap explanations" line | 01:47 | none |
| P9_harden_from_results_v2.md:53 | G5 mandate = exactness clause only | FC:491 | none |
| P9:56 | add IN-17 to QC_DEFENCE; repoint :19/:22 to v3 / PB_v2 (stale); P9:62 diff base -> 5574d77e | 01:47 | none |
| _COMMON_RULES_v3.md:25 Never 6 | narrow to rules of engagement (04:95). Allow deliverable-property rules settled by a determinate shipped fact. Keep the list of forbidden *silent* gaps (unmapped codes, malformed rows) | 01:45, 05:21, 05:27 | none |
| _COMMON_RULES_v3.md:27 Never 8 | cite IN-17 01:47 alongside W1 | 01:47 | none |
| qc_authoring_checklist_9b8229f6.md:46, :53 | item 6: drop "or point to the spec file" (any copied file counts); add IN-17 to the cited ids | 01:45, 01:47 | none |

### Lint lines (precheck.sh / issue.py; script structure INFERRED, LA §3 cites issue.py:110-113)

- WARN `IN17-PHRASE` in instruction.md: `note that|watch out|remember that|exactly one|is not what|in no particular order|will not reproduce|superseded or retired|disagree with each other`, and number words before plural nouns (`\b(Two|Three|Eleven|five)\b \w+s\b`). The author must justify each hit as a requirement (01:47). Risk: false positives; warn only.
- WARN `SELF-CHECK-INVITE`: `a second way|outside the (program|tool)|check yourself|on your own, outside` (LA §2 rank 2; 01:45 makes them unnecessary).
- WARN `G5-SCALES`: `other scales|other sizes|at other scales`.
- FAIL `EVIDENCE-MAP`: every test id in RULE_COVERAGE without an instruction or contract sentence must name a shipped fact file:line (FC:428 "name either the sentence it enforces or the shipped fact it reads").

---

## Lessons for the master
1. For deliverable-property rules, QC no longer needs a sentence. One determinate shipped fact that contradicts the wrong reading is a contract ground (05:21, FC:428), so our "state every rule" habit (P2:43, Never 6, LR:24) is stricter than QC and is the reason our tests sit at 98-100.
2. Silence and prohibitions still need a sentence (05:27, 05:30, 03:50). Build evidence levers on a separating record, a config value or a listed candidate set, never on an unfired branch.
3. IN-17 is a FAIL check, and match-replay (6 hits) and caldermoor (2) announce discoveries their input establishes. Strip those sentences before the next QC.
4. G11 must grow: AL-27 now covers orderings the input establishes (05:38). Each evidence lever needs a RULE_COVERAGE row and an EVIDENCE_MAP line.
5. CL-4 whole-document exactness is untouched. Keep the G5 exactness clause and drop "other scales" and the self-check paragraph, which QC no longer needs (01:45).
