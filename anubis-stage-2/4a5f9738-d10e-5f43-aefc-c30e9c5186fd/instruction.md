# Close the coexistence measurement year

The national band coexistence register must publish its occupancy measurement. Its corpus sits at `/app/data`: monthly register extracts, zone office logs, committee minute books, reference tables, observation records, configuration layers and policy notes. Everything that governs the measurement is written in that corpus and nowhere else.

Work offline. Online lookup of any kind is not allowed, and no outside source describes this register. You have 14400 seconds to complete this task.

## Deliverables

Write exactly these files into `/app/out`, and nothing else:

`/app/out/derive_report.py`, `/app/out/summary.json`, `/app/out/policy_audit.json`, `/app/out/data_quality.json`, `/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`, `/app/out/region_East.json`, `/app/out/segment_commercial.json` and `/app/out/segment_public.json`.

`output_contract.md` in the corpus fixes every key name, every value type, the ordering of every list and the exactness of every figure. Follow it to the letter. Every measure is an exact integer count of kilohertz seconds and no document may carry a floating point value. A document counts only when every figure in it is exact. A figure that is close is a figure that is wrong, and no rounded, scaled or abbreviated measure is accepted anywhere.

## What the measurement must satisfy

1. The measurable spectrum follows the band plan and the channel raster, including every channel the raster withdraws.
2. Every holder reference reaches its canonical form, and the redirections are closed to a fixpoint.
3. Each grant carries the licence segment and the filing zone that the registry and the status history give it.
4. The visibility cutoff of `measure_config.ini` governs every source record, every state event and every notice.
5. The governing record of each layer is chosen under the tiebreak this register uses, which you must settle from the corpus rather than assume.
6. Each field group of each grant is settled by precedence, including the documented exception, which you must also settle from the corpus rather than assume.
7. The clock keying of the zone summer windows is settled from the corpus evidence.
8. Every stamp reaches universal time under the unit and clock declarations of the corpus.
9. Every grant the register withdrew is withdrawn, and every remaining grant is tested against the reject codes in the published order, with one code recorded for each rejected grant.
10. The active intervals of every surviving grant follow its state events.
11. Every extent is trimmed to the usable channels and to the measurement horizon.
12. The reservation recurrences are expanded, the exceptions are applied, and the reserved spectrum is subtracted.
13. Every subordinate grant is clipped to the measurable extent of its parent, in dependency order.
14. The final extents of each grant are reduced as the contract describes before anything counts them.
15. The covered set, the part covered once and the part covered twice or more are measured per zone and in total.
16. The excess of every overlap cell is charged as the contract describes, and each zone names its highest charged grants.
17. Each zone union is broken down by local calendar month and by band.
18. Each segment is measured and names its largest holders.
19. The duty audit runs over the local months of every audited holder.
20. Every record file is recounted, compared against the manifest, and every reject code and note code of the vocabulary is tallied.
21. `/app/out/derive_report.py` is rerunnable. Invoked as `python3 derive_report.py <corpus_dir> <output_dir>` it reads a corpus laid out like this one, writes the same nine json documents into the output directory, uses only the python standard library, reads nothing outside the corpus directory it is given, writes nothing outside the output directory it is given, and leaves the corpus unchanged.

## Closing message

Finish with a message that states, as exact integers in plain prose:

1. the number of grant identifiers that carry a visible governing record in all three layers, counted over every grant identifier in the register including the withdrawn ones;
2. the union measure this register would publish if the visibility cutoff admitted every record;
3. the number of reservation occurrences across the four zones if the exceptions file were ignored;
4. the number of grants whose governing layer for the exception field group is moved by the exception, counted over the grants that survive withdrawal and pass every reject test;
5. the number of alias identifiers that need three or more redirections;
6. the number of distinct frequency bounds among the final extents of the East zone, counting a shared lower and upper bound once;
7. the number of grants that take their time group and their frequency group from different layers, counted over the grants that survive withdrawal;
8. the total of every declared row count in the manifest;
9. the number of grants that carry more than one final extent.

None of those nine figures belongs in any document. In the same message name, for each of the three rules you had to settle from evidence, the corpus file that settled it and what that file showed. State the residual of three identities: the four zone unions against the total union, the once covered part plus the twice or more covered part against the union, and the charged excess against the excess. Say plainly anything you could not finish.
