# Chainfold run ledger repair

A sharded training run finished with bookkeeping nobody trusts. Twenty three log segments were uploaded by workers that reconnected at different times, so the segment files hold overlapping stretches of the run and three of them carry the earliest part of it. Two restarts resumed from checkpoints whose recorded cursors disagree with the stream. One shard changed hands while the run was live. Held out and duplicated examples were pulled from several shards after the manifests were cut, and nobody re-derived the step ledger afterwards.

The archive sits at `/app/data`. Explore it. Alongside the run material you will find the operator notes on record layout, ordering, precedence, arithmetic, validation, serialization and the output contract, plus a worked miniature run. Those notes are the specification. Every rule the task depends on is written there with examples. Read them before you build anything.

## What you must deliver

Write a run auditor to `/app/out/optimize.py`. It takes a data directory and an output directory, audits whatever conforming archive it is pointed at, and writes its reports into the output directory by base name. It reads nothing outside those two directories, needs no network and nothing beyond the Python standard library, and produces byte identical output every time it runs on the same archive.

Run it against `/app/data` with `/app/out` as the output directory so these land too:

- `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json` and `/app/out/scenario_latency.json`, one per training profile
- `/app/out/perf_report.json` the cross profile summary with signed deltas against the baseline profile
- `/app/out/bottleneck_analysis.json` the ranked account of where records and examples leave the stream
- `/app/out/recommendations.json` the ordered remediation codes
- `/app/out/data_quality.json` the rejection, drift and reconciliation account

Every profile named in the archive gets its own scenario file, and every report carries the self describing fingerprint field the notes define.

## What the end state has to satisfy

The run is one ordered stream. File order, line order and file names carry no authority over it, and a segment uploaded late still belongs where its records say it belongs.

The optimizer step ledger is a running state. Each accumulation window closes against the width that is in force at the record being counted, and that width comes from the layered settings in the notes, resolved by the documented precedence and its named tie breaker. A restart boundary acts on whatever window is open when the stream reaches it, and the fate of that open window is itself a layered decision.

Work the restarts withdrew is withdrawn. Work a checkpoint never held was never held, whatever the recorded cursor says, and a cursor that disagrees with the reconstruction is an observation you must report rather than a number you may trust.

Every rejected, skipped and withdrawn record is counted once, attributed to exactly one documented reason resolved in the documented order, and the two reconciliation identities in the notes hold in every report at once.

All arithmetic is exact integer arithmetic under the named rounding rule, applied in the stated order. No floating point value may appear in any output. A zero denominator has a stated answer and a stated side effect, and both are the ones you must produce.

## Working conditions

You have 5400 seconds. Treat `/app/data` as read only and leave every file under it unchanged. Work only from the material under `/app/data` and your own reasoning; do not search online, do not fetch anything, and do not ask another person or service for the answer.

The run you can see is a quiet one. Rules that sit idle in it are live in other runs, and your auditor will be pointed at archives you have never seen, so build the policy rather than the answer. Hard coding values read off the visible run, branching on file names, or depending on anything outside the two directories will all come apart on another archive.

Leave `/app/out` holding only the ten deliverables above, each one complete, each one consistent with the others.

## Before you finish

Run the completed auditor twice against the same archive using two disposable output directories and compare every emitted file byte for byte. Remove those disposable directories, then make the required final run into `/app/out`.

In your final response, name all ten delivered paths, identify the archive evidence you used to reconstruct the optimizer step ledger, explain how the layered settings resolve the window width, and give the operator a short account of the run state and produced reports.
