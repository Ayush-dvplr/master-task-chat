CONFLICT REVIEW (hardening rules)

Source: tmp/W1-002/CONFLICTS.md (44 conflicts, C1 to C44). Reviewed one at a time with Ayush, most serious first. Each gets a decision word for word, then what the upgrade must change (applied only after PROCEED). Ids here are CR1, CR2 ... to avoid clashing with CONTRADICTIONS.md C1 to C6.

Order: CR1 = W1-002 C3 (timeouts), CR2 = C5 (careful program), CR3 = C25 with C6 (how much may be written), CR4 = C1 (parking), CR5 = C2 with C22 (carriers and encodings), then the rest.

CR1. Timeout and crash losses (W1-002 C3). Status: PARTLY DECIDED 3 Nov (ENTRY 18), form open (CR1a).
  New rule: route 1 notes R0 1(c), 2 Nov, Ayush "yes i approve" 09:40: losses by TIMEOUT or CRASH on hidden scale count, with no 30% cap.
  Old text still in the bodies of: _COMMON_RULES_v5 rule 17 (line 49), P9_harden_from_results_v4 (line 67), P2_build_v5 (line 66), KNOWLEDGE.md section T (line 108), GOALS.md line 18, LEVER_RULES_v3 lines 87 to 88, pipeline_v4 PLAN, state.json kill_rule. They say 10 to 30% cap, or timeouts do not count. Only a bracket note in front marks the new rule.
  Question: which rule holds? If R0 holds, the upgrade rewrites those bodies so only one rule exists.
  Decision (Ayush, ENTRY 18, summary; full words in ANSWERS.md): he approved it because it worked on one or two tasks. Relying on this one lever in every task is not good, even though nobody has flagged it. Use it less. It stays allowed in an emergency, when a task must be submitted.
  CR1a (open): which form should the rule take?
    (a) Timeout or crash loss may count, but only as an EXTRA lever: every task still needs a primary lever of kind (a) carrier or (b) unfired branch that carries the 40%.
    (b) Timeout may be the primary lever in at most a set share of tasks (a setting, like the gate), tracked in the registry.
    (c) Timeout as primary lever only with Ayush's explicit word for that task (the emergency case), logged.
    Or a mix, for example (a) by default plus (c) for emergencies.
