A country grain elevator kept a small program called the settlement engine. It read a whole intake shift of scale tickets, resolved each ticket into a settled line, and then rolled the shift up per bin and for the elevator as a whole. When the scale house was recabled the engine was lost, and the firmware that held its constants went with it. What survives is in `/app/data`.

The notes in `/app/data/engine.md` and `/app/data/reports.md` give the file shapes, how the engine screens the retransmitted, conflicting, re-entered and damaged lines that `tickets.jsonl` can carry, the carried bin state, the ordered list of stages, the status ladder, the key set of all three reports, the byte form each report is written in, and the two digests the intake manifest carries. They give none of the numbers, and they do not say what any bit of the intake's mode word does.

Two worked intakes ship under the prefixes `example_a_` and `example_b_`. Both have a mode word of zero, and each ships with the three files the engine wrote for it. Those two intakes are the evidence for the plain chain: the normalisation factor, the per commodity and per contract adjustments, the band edges, the role tolerances, the dockage charge and its ceiling, the disposition thresholds and the two tie breaks can all be pinned down from them.

The intake you are asked to reproduce is the unprefixed one, and its mode word is `0x1fff`, so all thirteen bits are set. No worked output ships for it. What ships instead is `/app/data/manifest.json`, which carries a sha256 digest for each bin and one for the whole intake, computed as `/app/data/reports.md` describes. Those digests are how a reading of the mode word is settled: resolve the intake under a candidate reading, digest the result, and compare. A wrong reading of any bit moves at least one bin digest, so the search is decidable one bin at a time rather than a guess.

Rebuild the engine as a single reusable program at this path:

```text
/app/out/settle.py
```

The program takes two command line arguments, the input directory first and the output directory second, and it writes `settlements.jsonl`, `binroll.json` and `elevator.json` into the output directory in the exact form `/app/data/reports.md` describes. It reads the mode word out of the manifest in its input directory and honours it, because it will be driven over intakes you have never seen, at mode words you have never seen, holding bins, dryers, haulers and graders that are not in this directory. Use only the Python standard library. Derive every figure from the input files at run time and keep precomputed answers out of the program. Running it twice over the same input directory must write byte identical files. Treat everything in `/app/data` as read only input and leave it unchanged.

Run your finished program over `/app/data` and then give a closing report in your final message. State each of these eleven figures, using these names, as plain whole numbers measured over the unprefixed intake:

```text
scrap_rejects       how many resolved tickets landed on the rejected status
weighman_flags      how many resolved tickets landed on flagged whose own grader is a weighman
off_role_flags      how many resolved tickets landed on flagged whose own grader is an inspector, an apprentice or a relief grader
hold_bins           how many bins ended on the hold disposition
capped_tickets      how many resolved tickets carry a dockage_before sitting exactly at the dockage ceiling
light_grain_total   the sum of bushels over every resolved ticket whose bin is written corn or milo in bins.csv
heavy_grain_total   the sum of bushels over every resolved ticket whose bin is written barley or oats in bins.csv
hedge_clear_total   the sum of bushels over every resolved ticket that landed on clear whose contract is written board or hedge in contracts.csv
prime_tickets       how many resolved tickets carry the prime band
tare_end_total      the sum of tare_end over every bin
set_aside_lines     how many lines of tickets.jsonl screening set aside, whether as damaged, for a conflict or as a re-entry
```

Alongside the eleven figures, say in the closing report how many of the thirteen mode bits you settled and which ones are still open, give the count of bins the unprefixed intake holds and the count of tickets it resolves, and say whether every bin digest in `/app/data/manifest.json` and the whole intake digest agree with what your program produced.

A partial engine that is written down and reported on is worth more than a perfect one that never gets written, so put the program in place and give the closing report before you spend whatever time is left on the bits you are still unsure of.

You have 7200 seconds to complete this task.
