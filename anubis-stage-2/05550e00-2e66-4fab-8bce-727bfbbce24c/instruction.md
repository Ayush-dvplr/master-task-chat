A model serving fleet ran a small program called the inference gate. Every shift it read the run of metered inference probes, scored each probe into a verdict, and rolled the shift up per endpoint, per precision class and for the fleet as a whole. When the serving controller was replaced the gate went with it and nobody kept a copy. What survives is in `/app/data`: one recorded shift, one older shift the team had already worked through and published the verdicts for, and a short file of digests over the four reports the gate wrote for the recorded shift.

The notes in `/app/data/gate.md` and `/app/data/reports.md` describe the gate and its four reports: the input columns, the way the meter column has to be read back, the carried endpoint state, the ordered stages, the verdict ladder, the key set of every report, the byte form each is written in, what the gate writes for a shift holding no probe at all, and how each digest is taken. What they do not give is any of the numbers, and they do not list them. Every figure the stages apply, every mode the carry update names and every threshold the ladder and the rollups consult was a controller constant nobody wrote down, and working out what that list even holds is part of the job. Together the two notes are the only description of the contract the finished program has to meet.

The evidence comes in two parts. First the worked example: `/app/data/example_probes.jsonl` with the four `example_` lookup tables beside it is an older shift, and `/app/data/example_verdicts.jsonl` holds the verdicts the gate wrote for it. Nothing else was published for that shift and nothing says which parts of the gate it exercises, so what it settles and what it leaves open is yours to work out.

The second part is thinner. `/app/data/probes.jsonl` and the four lookup tables beside it are the recorded shift, and no report for it survives. `/app/data/digest.json` carries one sha256 over each of the four reports, and a digest goes green only when every probe of the shift resolves correctly. There is no partial signal underneath it and no score is confirmed until the whole shift is. Everything the worked example leaves open has to be reasoned out of the stage order and the carried state, then confirmed in one go.

Rebuild the gate as a single reusable program at this path:

```text
/app/out/gate.py
```

The program takes two command line arguments, the input directory first and the output directory second, and writes `verdicts.jsonl`, `endpoints.json`, `precision.csv` and `shift.json` into the output directory in the exact form `/app/data/reports.md` describes, down to the key order, the separators, the integer formatting and the trailing newline of every file. It has to work on any shift in this schema rather than the recorded one alone: it will be driven over shifts you have never seen, holding endpoints, runtimes, variants and callers that are not in this directory, and over a shift holding no endpoint and no probe at all. Use only the Python standard library. Work every figure out from the input files at run time and keep precomputed answers out of the program. Two runs over one input directory must write byte identical files. Treat everything in `/app/data` as read only and leave it unchanged, and keep any scratch work elsewhere.

Check your fit rather than settling on the first reading that matches part of what you have. Set a block of the recorded shift aside while you work the constants out, then replay that held back block and check it too. Where two readings both fit what you have looked at, build a small input of your own on which they disagree and run both over it. Work one figure out a second time through a calculation separate from the program you deliver. Before you finish, take the digest of each of your own four output files and check all four against the published ones.

Run your finished program over `/app/data` and give a closing report in your final message. State each of these ten figures, using these names, as plain whole numbers measured over the recorded shift, and keep every one of them out of the report files themselves:

```text
total_score          the sum of score over every probe in the recorded shift
total_backlog        the sum of backlog_before over every probe in the recorded shift
top_score_total      the sum of top_score over every endpoint
flagged_score        the sum of score over every probe that resolved to flagged
saturate_band_score  the sum of score over every probe carrying the saturate band
high_band_score      the sum of score over every probe carrying the high band
base_band_score      the sum of score over every probe carrying the base band
clear_score          the sum of score_total over every endpoint that ended on clear
throttle_endpoints   how many endpoints ended on the throttle disposition
budget_end_total     the sum of budget_end over every endpoint
```

A partial gate that is written down and reported on is worth far more than a perfect one that never gets written. One way to manage that risk is to put a first working version at the deliverable path early and inspect its ten figures while improving it. This is optional pacing guidance, not a requirement.

A useful pacing approach is to keep a working program written down as you go, spend roughly 1500 seconds trying new readings, then consolidate the best one and produce the closing report. This is guidance rather than an additional deadline. The binding limit below is where the work is cut off, not where it is meant to finish.

You have 7200 seconds to complete this task.
