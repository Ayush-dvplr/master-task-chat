The flat files under `/app/data` are what a service fleet left behind after one incident window in which its worker threads stalled on locks: what the stall reporter captured on the wire, what the thread probe measured, what the hosts parked to the log, the registry the workers live under, and the written rules its subsystems run under. Your job is to reconstruct that window and the roll ups that hang off it. The rules are complete and the materials are self describing, but nothing tells you which of them bears on which figure, or in what order they bite, so treat the directory as something to explore rather than a list handed to you. The stall reporter holds back nine wire constants; the fleet published enough held out control figures for exactly one assignment of them to survive.

Deliver a reusable program at `/app/out/derive_report.py`. It runs as a script over an input directory and an output directory and writes the whole post mortem set under the output directory, so that the same code produces correct results for stall captures it has never seen. Nothing in it may depend on the particular identifiers, counts or totals present in the shipped capture. A later capture carries only its own stall journal, thread probe and park export beside the same side tables: the calibration population and its published control figures ship once, with this window, so the program must carry the constants you settle here and still produce correct results when it is pointed at a directory that holds no control figures at all.

```bash
python3 /app/out/derive_report.py <DATA_DIR> <OUT_DIR>
```

Called with no arguments it falls back to reading `/app/data` and writing `/app/out`. Use only the Python standard library; anything you install now will be gone when the program is run again later, and the delivered program may not read `/app/data` when it is pointed somewhere else.

The window roll up goes to `/app/out/summary.json` and the lock class and worker audit to `/app/out/policy_audit.json`. One report goes to each of `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json` and `/app/out/region_East.json` for the fleet's service cells, and one to each of `/app/out/segment_commercial.json` and `/app/out/segment_public.json` for its tenant segments. The shipped materials fix what those files hold and how they are written.

`/app/out/data_quality.json` is the reconciliation and derivation record. Beyond the window's counted and set aside tallies and its byte conservation, it records the work: the candidate space you enumerated, the verdict you reached on every candidate, the control figure that falsified each rejection, the number of passes your blame settlement took to reach a stable assignment counting the pass that left it unchanged, and your comparison against every published control figure. It has this shape:

```json
{
  "accepted_count": 0,
  "calibration_comparison": [{"control": "", "published": 0, "reproduced": 0}],
  "candidate_search": {
    "evaluations": 0,
    "parameters": [
      {"name": "", "candidates": 0, "control": "", "selected": 0,
       "rejected": [{"value": 0, "control": ""}]}
    ]
  },
  "event_count": 0,
  "reconciliation": {"emitted_bytes": 0, "logged_bytes": 0, "residual_bytes": 0},
  "rejections": {"": 0},
  "settlement": {"passes": 0, "quarantined_classes": [""]}
}
```

Five rules govern how you work. Settle the withheld wire constants against the published control figures before you compute any figure for the incident window. Record a verdict for every candidate value in a constant's candidate list before you select that constant's value. Check the shipped segment and line check totals against the fields they cover before you trust a decoded field. Once the constant set is settled, run your whole derivation again from the start into a second, empty output directory. Carry the tick, byte and span arithmetic in Python integers rather than in binary floating point.

Leave everything under `/app/data` as you found it. The program writes nothing outside the output directory it was given.

You have 21600 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
