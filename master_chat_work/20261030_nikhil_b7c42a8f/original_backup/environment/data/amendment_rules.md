# Amendment rules

A treaty endorsement circular counts only when (a) it was recorded strictly after the claim row it amends and (b) it is signed by an underwriter who held authority for that LOB at the audit instant. A circular that fails either condition is dropped; a circular that passes both is applied once.

## Honoured circular effect

When a circular is counted, the governing ALAE for its claim is raised by the ratio declared below. The ratio is applied to the unamended `alae` figure (post-settlement, before any clash-cover walk) with half-up rounding to a whole dollar.

## `cede_cap_raise` ratio

The `cede_cap_raise` amendment type lifts ALAE by `0.25` on each counted circular. The ratio is read at run time from this file. A delivered module that holds this ratio as a Python literal fails the hidden-extract check, because A and B each ship a different ratio.

## Audit resolution

Three rotations of `endorsement_audit.log` carry the sign-off records. A circular is signed off iff its `claim_ref` appears in at least one rotation, dated no earlier than the amended row and no later than the audit instant. Rotations are read in file-name order and merged.
