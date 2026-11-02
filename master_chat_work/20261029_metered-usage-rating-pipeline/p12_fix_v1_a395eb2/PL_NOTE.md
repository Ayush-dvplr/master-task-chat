# PL note: metered-usage-rating-pipeline (P12 fix a395eb2)

All five fails and both minors were real and are fixed. Three warns remain; two are kept with evidence, one is fixed.

## False positive
- X1 (structure warn, collector_south.txt skipped as binary): the file is Latin-1 on purpose. The contract says so at environment/data/rating_contract.md:61 "Every file is UTF-8 except collector_south.txt, which is Latin-1." The QC re-check in v1.md:29 and :145 already verified it is text in the stated encoding.

## Kept warns
- G03-2 / A3 (110 checks, kit cap 35 at Final_checklist.md:204): kept with the count. Each check grades one document or one refusal on its own input; none is a duplicate. Merging distinct checks would hide which output failed. Count cap waived by Ayush (24 Oct 12:50; decision 3 option A, 27 Oct).

## Changes the QC will see that differ from its Fix lines
- R6 was not split into three criteria. It now grades one act (every exception handler acts on the error). The kit asks for exactly one code-quality criterion, and the other two halves (150-line functions, unused code) are not promised anywhere in the instruction.
- The north `units` clause names only the fraction and exponent forms, the two forms that were read two ways.

## Unsure
None.

## Lessons for the master
- A JD-5 split of a code-quality criterion collides with J4 (exactly one); reduce to one act instead | template_change: QC_FIX_PLAYBOOK_v3.md JD-5 row: add "for a J4 criterion, keep one act, drop the rest".
