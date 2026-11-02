A bench that runs microplate assays kept a small program called the triage engine. It read a whole run of well reads, resolved each read into a graded reading, and then rolled the run up per plate and for the bench as a whole. When the bench controller was rebuilt the engine was lost, and the firmware that held its constants went with it. What survives is in `/app/data`.

The notes in `/app/data/engine.md` and `/app/data/reports.md` give the file shapes, the carried plate state, the ordered list of stages, the status ladder, the key set of each report, the byte form each report is written in, and the two digests the run manifest carries. They give none of the numbers, and they do not say what any bit of the run's mode word does.

Two worked runs ship under the prefixes `example_a_` and `example_b_`. Both have a mode word of zero, and each ships with the files the engine wrote for it. Those two runs are the evidence for the plain chain: the gain, the per matrix and per panel adjustments, the band edges, the role tolerances, the drift charge and its ceiling, the disposition thresholds and the two tie breaks can all be pinned down from them.

The run you are asked to reproduce is the unprefixed one, and its mode word is `0xfff`, so every bit is set. No worked output ships for it. What ships instead is `/app/data/manifest.json`, which carries a sha256 digest for each plate and one for the whole run, computed as `/app/data/reports.md` describes, and the folder `/app/data/bits/`, which holds one manifest per bit with the same two kinds of digest for the unprefixed run resolved with only that bit set. Those digests are how a reading of the mode word is settled: resolve the run under a candidate reading, digest the result, and compare. A second run with every bit set ships under the prefix `trial_`, with its own `trial_manifest.json` of the same two kinds of digest and no worked output; it holds a different set of instruments, a different operator count and a different plate count.

Rebuild the engine as a single reusable program at this path:

```text
/app/out/triage.py
```

The program takes two command line arguments, the input directory first and the output directory second, and it writes `readings.jsonl`, `plates.json` and `bench.json` into the output directory in the exact form `/app/data/reports.md` describes. Each output file is graded whole on fresh runs, and only an exact match counts. It reads the mode word out of the manifest in its input directory and honours it, because it will be driven over runs you have never seen, at mode words you have never seen, holding plates, instruments and operators that are not in this directory. Use only the Python standard library. Derive every figure from the input files at run time and keep precomputed answers out of the program. Running it twice over the same input directory must write byte identical files. Treat everything in `/app/data` as read only input and leave it unchanged.

Run your finished program over `/app/data` and then give a closing report in your final message. State each of these figures, using these names, as plain whole numbers measured over the unprefixed run:

```text
trace_rejects        how many resolved reads landed on the reject status
technician_reviews   how many resolved reads landed on review whose own operator is a technician
off_role_reviews     how many resolved reads landed on review whose own operator is a scientist, a trainee or a service operator
hold_plates          how many plates ended on the hold disposition
saturated_reads      how many resolved reads carry a drift_before sitting exactly at the drift ceiling
thin_matrix_total    the sum of value over every resolved read whose plate is written saliva or urine in plates.csv
rich_matrix_total    the sum of value over every resolved read whose plate is written serum or lysate in plates.csv
assay_family_total   the sum of value over every resolved read whose panel is written pcr or turbidity in panels.csv
high_reads           how many resolved reads carry the high grade
blank_end_total      the sum of blank_end over every plate
```

A partial engine that is written down and reported on is worth more than a perfect one that never gets written, so put the program in place and give the closing report before you spend whatever time is left on the bits you are still unsure of.

You have 5400 seconds to complete this task.
