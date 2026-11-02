# PL_NOTE, schema-migration-plan-repair, P12 r5 (3b74d43)

Author: Ayush Sah.

False positives: none.

Kept items:
- TS-13 🟡 `receipt_counts_partner_rejected_lines` (tests/test_output.py:9786-9793): kept as a minor. The second condition (rejected records keep a null fingerprint) is the L2 separating observable. Dropping it was tried and raised the reflex replay from 39/201 = 0.194 to 42/201 = 0.209, over the 0.20 gate, so it was reverted.
- A3 / TS-23 ⚠️ 63 checks above the 35 warn line: kept, Ayush approved (23 Oct 18:20); under the 70 cap.
- TS-15 ⚠️ `negative_unsafe_archive_members` lacks the inversion comment; polarity is correct. Kept as-is, Ayush accepted (23 Oct 18:20).

UNSURE questions: none.

## Lessons for the master
- Kept TS-13 needs the reflex number in the defence each time QC re-flags it.
