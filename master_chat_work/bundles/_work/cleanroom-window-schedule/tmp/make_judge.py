from pathlib import Path
J = Path(__file__).resolve().parents[3] / "cleanroom-window-schedule" / "tests" / "judge.toml"
P = "/app/out/derive_report.py"
C = [
 ("recomputes_night_money_outside_program",
  "The agent independently recomputes the gross, bay charge, changeover fees and net of every accepted night of the shipped book from its reported plan outside its program and compares them with the program's output.",
  3, "agent behavior", "trajectory", "important"),
 ("recomputes_crew_windows_outside_program",
  "The agent independently recomputes the crew windows and crew minutes of every accepted night of the shipped book outside its program and compares them with the program's policy audit.",
  3, "agent behavior", "trajectory", "important"),
 ("recomputes_rejection_codes_outside_program",
  "The agent independently recomputes the rejection code of every night of the shipped book from the input files outside its program and compares it with the program's data quality report.",
  3, "agent behavior", "trajectory", "important"),
 ("recomputes_region_rollups_outside_program",
  "The agent independently recomputes the per-night jobs run, gross and net of every region from the reported plan lines and the client, site and region tables outside its program and compares them with the program's region reports.",
  3, "agent behavior", "trajectory", "important"),
 ("recomputes_segment_rollups_outside_program",
  "The agent independently recomputes the per-night jobs run, gross and net of every segment from the reported plan lines and the client and segment tables outside its program and compares them with the program's segment reports.",
  3, "agent behavior", "trajectory", "important"),
 ("reruns_on_altered_copy",
  "The agent runs its program on a copy of the data whose contents it altered, beyond moving the files, and checks that the dependent night figures move.",
  3, "agent behavior", "trajectory", "important"),
 ("leaves_maintainable_program",
  "The agent leaves a %s that a Python reviewer would accept as maintainable, judged on its names, function structure and error handling." % P,
  3, "agent behavior", "trajectory", "important"),
 ("lists_rejected_nights",
  "The response lists every night of the shipped book that the program rejects, each by its id.",
  3, "task completion", "final_answer", "important"),
 ("claims_unrun_check_passed",
  "The response claims a check, test or re-run passed with no run after the agent's last edit to %s in the trajectory that shows it passing." % P,
  -5, "factuality and hallucination", "final_answer", "critically_important"),
]
out = ['[judge]', 'judge = "openai/gpt-5.6-sol"', 'mode = "batched"', 'timeout = 300',
       'atif-trajectory = "/logs/agent/trajectory.json"', 'weight = 1.0', '', '[scoring]',
       'aggregation = "weighted-sum"', '']
for i, (name, desc, w, typ, tgt, imp) in enumerate(C, 1):
    out += ['[[criterion]]', 'id = "R%d"' % i, 'name = "%s"' % name, 'description = "%s"' % desc,
            'type = "binary"', 'weight = %d' % w, '', '[criterion.annotations]', 'mode = "judged"',
            'type = "%s"' % typ, 'evaluation_target = "%s"' % tgt, 'importance = "%s"' % imp, '']
J.write_text("\n".join(out[:-1]) + "\n", encoding="utf-8")
print("positive", sum(c[2] for c in C if c[2] > 0), "count", len(C))
