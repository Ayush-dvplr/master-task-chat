# QL reply template v1 DRAFT

Save as `master_chat_work/_ql/<slug>/<TS>_{report|zip}/REPLY_QL.md`. Use plain words. Never write lever, trap, probe, harden, tool or session names, and never say why a rule is hidden (W1).

---

Hi Sugam,

Thank you for the review of **<task name>** (<date of your report>). Here is what we found for each point.

| # | Your point (short) | Our verdict | Evidence | What changed |
|---|---|---|---|---|
| F1 | <one line> | Fixed | <rule ID + one-line wording>; <file:line> | `<file>:<line>` before: "<old>" → after: "<new>" |
| F2 | <one line> | Not changed: this is how the rule reads | <rule ID + wording, file:line>; <bundle file:line> shows <fact> | none |
| F3 | <one line> | Partly fixed | <what was right, what we kept and why> | `<file>:<line>` ... |
| F4 | <one line> | Outside QC scope | no QC rule asks for this (<nearest rule ID>); noted for the author | none |

**Checks after the changes:** local QC scripts clean; reference solution 1.0 (3 runs); empty submission 0.0; recheck <PASS / result>.

**New run** (<date>, same files as delivered): tests <t>, rubric <r>, final <f>. <"The delivered package is updated." / "No new run was needed: no graded file changed.">

**Files delivered:** <path or "same folder as before">, version <tree sha first 12>.

If you see any of the "not changed" points differently, please tell us which rule line you read, and we will look again.

Regards,
Ayush
