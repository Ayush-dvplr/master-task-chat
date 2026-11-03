CONFLICT REVIEW (hardening rules)

Source: tmp/W1-002/CONFLICTS.md (44 conflicts, C1 to C44). Reviewed one at a time with Ayush, most serious first. Each gets a decision word for word, then what the upgrade must change (applied only after PROCEED). Ids here are CR1, CR2 ... to avoid clashing with CONTRADICTIONS.md C1 to C6.

Order: CR1 = W1-002 C3 (timeouts), CR2 = C5 (careful program), CR3 = C25 with C6 (how much may be written), CR4 = C1 (parking), CR5 = C2 with C22 (carriers and encodings), then the rest.

CR1. Timeout and crash losses (W1-002 C3). Status: DECIDED 3 Nov (ENTRY 18 and 22).
  New rule: route 1 notes R0 1(c), 2 Nov, Ayush "yes i approve" 09:40: losses by TIMEOUT or CRASH on hidden scale count, with no 30% cap.
  Old text still in the bodies of: _COMMON_RULES_v5 rule 17 (line 49), P9_harden_from_results_v4 (line 67), P2_build_v5 (line 66), KNOWLEDGE.md section T (line 108), GOALS.md line 18, LEVER_RULES_v3 lines 87 to 88, pipeline_v4 PLAN, state.json kill_rule. They say 10 to 30% cap, or timeouts do not count. Only a bracket note in front marks the new rule.
  Question: which rule holds? If R0 holds, the upgrade rewrites those bodies so only one rule exists.
  Decision (Ayush, ENTRY 18, summary; full words in ANSWERS.md): he approved it because it worked on one or two tasks. Relying on this one lever in every task is not good, even though nobody has flagged it. Use it less. It stays allowed in an emergency, when a task must be submitted.
  CR1a (open): which form should the rule take?
    (a) Timeout or crash loss may count, but only as an EXTRA lever: every task still needs a primary lever of kind (a) carrier or (b) unfired branch that carries the 40%.
    (b) Timeout may be the primary lever in at most a set share of tasks (a setting, like the gate), tracked in the registry.
    (c) Timeout as primary lever only with Ayush's explicit word for that task (the emergency case), logged.
    Or a mix, for example (a) by default plus (c) for emergencies.
  CR1a decided (ENTRY 22): extra lever by default; main lever only with Ayush's explicit word for that task, until something more reliable is found.

CR2. Careful exact program (W1-002 C5). Status: DECIDED 3 Nov (ENTRY 61): only a real paid run program counts; before the first paid run the lever is judged by prediction; NO CORE at 60 percent kept (setting no_core_keep_pct), report and redesign, never park on its own. P13 v2 blind stays a quick diagnostic only (T45).

CR4. Parking (W1-002 C1). DECIDED 3 Nov (ENTRY 62): never park on its own; report to Ayush (T34, T44).
CR5. Carriers as primary lever (W1-002 C2 with C22). DECIDED 3 Nov (ENTRY 62): carriers are valid (D2, T4); old SHAPE and S code fields go (T1, T3); template fields cleaned in P10.

DECIDED FROM THE CARDS
CR6. Amended or retyped field (cards 058cbab3, 88ee425d, af780bef; Q104, ENTRY 34): allowed in Ayush's tasks only when one sentence in the shipped docs decides how the amended value is read.
CR7. Misread rule as primary lever (Q111, ENTRY 39; evidence tmp/W1-025/CONFIRM.md): ALLOWED as a primary lever when the rule has one clear deciding sentence in the shipped docs and many records tempt the wrong or too wide reading. Replaces route 1 R0 point 2 ("extras only") after PROCEED.

PAUSE NOTE (3 Nov): while Claude was writing up the case by case review of the DEFECT families (tmp/S2-CARDS/SUMMARY.md F1 to F6) after Q107 (b), an automatic safety check stopped the write up before anything was saved. Claude paused that review and told Ayush. Do not restart it without Ayush. CR2 to CR5 (from tmp/W1-002/CONFLICTS.md C5, C25 with C6, C1, C2 with C22) and the other W1-002 conflicts are still open; they are planned after the system fix drafts (RESUME NEXT STEPS).
