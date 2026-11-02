A number theory group ran a small program called the residue mill. Every pass it read a run of metered samples, reduced each against its lane's modulus, resolved it into a residue line, and rolled the pass up per lane, per form and for the sieve as a whole. When the workstation was reimaged the mill went with it, and so did the per sample ledger and the per lane rollup for the last recorded pass. What survives is that pass's input, the two coarser rollups written for it, and the input of a second pass for which nothing survives, all of it in `/app/data`.

The notes in `/app/data/engine.md` and `/app/data/reports.md` describe the mill and its four reports: the input columns, the eight pieces of carried lane state, the fourteen ordered stages, the status ladder, the key set, byte form and row order of every report, and what the mill writes for a pass holding nothing. What they do not give, apart from three figures `engine.md` says survived on a whiteboard, is any of the numbers. Every constant those two notes name as missing is missing, from the block factor, the governing size column, the terms offset, the gain and the modulus offset through the reduction rule, the four adjustment tables, the band edges and the record size to the drift arithmetic, the sealing threshold, the form ordering rule and the tie breaks the notes leave open. Read both notes end to end first: they bound the search and they are the only description of the contract you have to meet.

The evidence you fit against is the recorded pass and the two rollups that survived it. The file `/app/data/samples.jsonl` and the four lookup tables beside it are the input. The files `/app/data/ref_forms.csv` and `/app/data/ref_sieve.json` are what the mill wrote for exactly that input. Nothing survives at the level of one lane or one sample, so a wrong constant shows up only as a wrong figure on one of a handful of form rows or in the one whole pass rollup, and it will not say which lane or which stage it came from. Readings that reproduce both rollups and are still wrong exist, so treat agreement there as a floor rather than a proof. No lane sits on more than one of the three plain keyed values at once either, so no lane isolates one adjustment.

Beside it sit `carry_moduli.csv`, `carry_forms.csv`, `carry_analysts.csv`, `carry_lanes.csv` and `carry_samples.jsonl`. Those five are a second pass in the same schema, the carry pass, and no rollup of any kind survives for it. It is longer than the recorded pass, rests on its own lanes, moduli, forms and analysts, and reaches corners of the mill the recorded pass never visits.

Rebuild the mill as a single reusable program at this path:

```text
/app/out/sieve.py
```

The program takes two command line arguments, the input directory first and the output directory second, and writes `residues.jsonl`, `lanes.json`, `forms.csv` and `sieve.json` there in the exact form `/app/data/reports.md` describes, down to the key order, the row order, the separators and the trailing newline. It has to work on any pass in this schema rather than the recorded one alone: it will be driven over passes you have never seen and over a pass holding nothing at all. Use only the Python standard library. Work every figure out from the input files at run time and keep precomputed answers out. Two runs over one input directory must write byte identical files. Treat everything in `/app/data` as read only and leave it unchanged, and keep any scratch work elsewhere.

Check your fit rather than settling on the first reading that reproduces the two rollups. Set a block of the recorded pass aside while you work the constants out, then replay that held back block and check it too. Where two readings both fit what you have looked at, build a small input of your own on which they disagree and run both over it. Where two lanes share two keyed columns and differ on the third, use that pair to narrow the adjustment on the column they differ on. Work at least one figure out a second time through a calculation separate from the program you deliver. Before you finish, compare both of your own rollups against the shipped reference files byte for byte.

Run your finished program over `/app/data`, then copy the five carry files into a directory of your own under their plain names and run it over that too. Give a closing report in your final message. State these three figures, as plain whole numbers over the recorded pass, each the total weight of the samples named beside it:

```text
setup_weight    resolving to setup
voided_weight   resolving to voided
folded_weight   on lanes in the folded sector
```

Then state these seventeen, using these names, as plain whole numbers over the carry pass, and keep all twenty out of the report files themselves:

```text
carry_total_weight       every sample
carry_kept_weight        resolving to kept
carry_flagged_weight     resolving to flagged
carry_refused_weight     resolving to refused
carry_peak_band_weight   in the peak band
carry_high_band_weight   in the high band
carry_base_band_weight   in the base band
carry_sieve_weight       carrying the sieve action
carry_senior_weight      whose analyst is graded senior
carry_night_weight       in the night window
carry_cubic_weight       charged on the cubic kind
carry_quadratic_weight   charged on the quadratic kind
carry_prime_weight       on a prime modulus
carry_cleared_weight     lanes cleared, summing weight_total
carry_held_weight        lanes held, summing weight_total
carry_sealed_weight      lanes sealed, summing weight_total
carry_total_drift        every sample, summing drift_before
```

A partial mill that is written down and reported on is worth far more than a perfect one that never gets written, so put the program in place and give the closing report before spending what time is left on the constants you are unsure of. Give the hard part at most half your working time. Once that is spent, rewrite the program from your best reading, state the figures, and end your turn.

You have 7200 seconds to complete this task.
