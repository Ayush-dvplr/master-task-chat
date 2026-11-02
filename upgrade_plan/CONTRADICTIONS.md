CONTRADICTIONS IN THE CURRENT RECORDS

Places where two files disagree. Claude does not pick a winner. Ayush decides each one.

C1. Docker limits
  master_chat_tasks/README.md line 31: "one Docker task at a time, max 2 Docker heavy jobs on the Mac".
  state.json rules: "Docker heavy jobs still max 2".
  auto/AUTO_POLICY.md Limits: dockfree.py "replaces the 27 Oct 'at most 2 Docker heavy' advice" (31 Oct).
  Question: which one is in force? (Q17)

C2. Count cap on tests and judge criteria
  state.json targets.caps: "tests<=35, judge criteria<=35 ... PL acceptance = zero findings incl. warns".
  feedback 24 Oct 12:52: "there is not cap on number of test and rubrics".
  README line 31 and QC_FIX_PLAYBOOK_v3: "count cap option A (over 35 = warn)".
  Question: Q30.

C3. Template versions
  state.json template_versions: P12_recheck_fix "v4".
  knowledge/INDEX.md: P12_recheck_fix_v5.md ACTIVE 31 Oct, v4 SUPERSEDED.
  README line 31: "P12 v4".
  Question: Q31.

C4. Gate values inside state.json
  state.json targets.test_phase_gate: "tests<100, rubric<100, overall<70%".
  state.json test_phase_gate (top level): "tests<85, rubric<85, final<40".
  Question: Q32.

C5. Harness runs per task
  state.json rules: "1 run per task while building/hardening; 8 runs only on final approval".
  GOALS end outcome and AUTO_POLICY: push needs 1 run on frozen QC passed bytes.
  Question: Q33.

C6. Harness concurrency
  lessons 24 Oct 10:45 and 11:15: "one Docker task at a time" on the harness.
  auto.py MAX_HARNESS = 2.
  Question: Q17.
