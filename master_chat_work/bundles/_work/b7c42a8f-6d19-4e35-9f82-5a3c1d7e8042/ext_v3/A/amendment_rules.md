# Amendment rules

A treaty endorsement circular counts only when it is signed off in the audit trail and it is signed by an underwriter who holds authority for that LOB. A circular that fails either condition is dropped; a circular that passes both is counted once.

## Audit resolution

Three rotations of `endorsement_audit.log` carry the sign-off records. A circular is signed off iff its `claim_ref` appears in an `ENDORSE` line of at least one rotation. Rotations are read in file-name order and merged.

## Signing authority

A circular's underwriter holds authority for its LOB iff `authority_roles.csv` has a row for that `(underwriter_id, lob)` pair.

## `cede_cap_raise` ratio

The `cede_cap_raise` amendment type lifts ALAE by `0.25` on its claim. The raise belongs to the unendorsed-amendments counterfactual in `counterfactual_parameters.md` only: the governing run books no raise, so a counted circular leaves the governing `alae` of its claim unchanged.
