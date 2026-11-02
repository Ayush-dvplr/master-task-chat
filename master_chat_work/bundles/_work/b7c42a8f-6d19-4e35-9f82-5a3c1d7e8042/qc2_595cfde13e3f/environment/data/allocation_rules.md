# Allocation rules

Within each `(lob, cycle)` cell, the ceded recoverable dollar grant to each claim is determined by a three-step allocation under the capacity declared in `layer_capacity_declarations.csv`.

## Preconditions

Each claim entering the cell carries an unmet dollar amount `want = max(0, ultimate + alae - paid_to_date)`. The cell's capacity is `cap = layer_capacity[(lob, cycle)]`. The pool of dollars available to grant is initially `pool = cap`. The claims entering the cell are ordered by `(claim_ref, reinsurer_canonical)` for the first two steps.

If `cap` is zero, every claim in the cell receives a `ceded_hours` grant of zero with `outcome = "ZERO"` and `reason = "CAP_ZERO"`; the three steps below are skipped. Retracted claims (see outcome precedence below) do not enter the three-step allocation at all; they keep a ledger row with the retracted outcome and reason and are placed in their LOB document's ledger with `ceded_hours = 0` and `alae = 0`.

## Step 1: honoured minimums

For each claim in the ordered sequence, the commitment minimum for `(reinsurer_canonical.base, lob)` is read from `commitment_agreements.csv`. If `(reinsurer_canonical.base, lob, cycle)` appears in `commitment_exceptions.csv`, the minimum is overridden to zero. The share paid to the claim is `share = min(minimum, want, pool)`. The grant, the unmet amount, and the pool are each decremented by `share`.

The reinsurer canonical base is the identifier with any `#1` or `#2` epoch suffix stripped. The ordering of claims within the cell for this step is `(claim_ref, reinsurer_canonical)`.

## Step 2: shared fill level

If `pool > 0` and at least one claim still has `unmet > 0`, raise a shared fill level to the greatest whole-dollar amount capacity allows: each claim with positive `unmet` receives `give = min(unmet, pool // live_claims)` where `live_claims` is the count of claims whose unmet is positive. The grant, the unmet amount, and the pool are each decremented accordingly.

## Step 3: indivisible remainder

While `pool > 0` and at least one claim has `unmet > 0`, hand out one dollar at a time by this tie-break: sort claims by `(-unmet, recorded_instant, reinsurer_canonical, claim_ref)` and iterate; each iteration grants one dollar to the next claim with positive unmet, decrementing its unmet and the pool, incrementing the cell's remainder count. The loop ends when the pool is exhausted or every claim's unmet is zero.

The total dollars handed out by Step 3 across every `(lob, cycle)` cell is reported row-by-row in each LOB document's `remainder_dollars_per_cycle` map. No separate `counterfactual_summary` key exists in `methodology_audit.json`; the counterfactual quantities asked for in the closing message are reported only in the agent's final message, per `output_contract.md`.

## Outcome and reason precedence

Each ledger row carries exactly one outcome and exactly one reason, chosen by the precedence declared in `reason_codes.json#outcome_precedence` and `reason_codes.json#reason_precedence`. When more than one outcome or reason could apply to a row, the earlier entry in the precedence list wins. Two reasons can co-apply to one state (for example `UNRESOLVABLE_CHAIN` and `CAP_ZERO`); the precedence list, read left to right, resolves such a tie.

For reference, under the shipped precedence:

- `outcome = "RETRACTED"` and `reason = "RETRACTED"` if the claim appears in `retraction_notices.csv`; the three steps are skipped and the row carries `ceded_hours = 0`, `alae = 0`.
- `outcome = "EXCLUDED"` and `reason = "UNRESOLVABLE_CHAIN"` if the claim is in horizon but its reinsurer cannot be resolved to a canonical identifier through `reinsurer_alias_map.csv` and `reinsurer_master.csv`. The row carries `ceded_hours = 0`, `alae = 0`, `reinsurer_canonical = null`.
- `outcome = "ZERO"` and `reason = "CAP_ZERO"` if the cell's capacity was zero and the claim was not retracted and the reinsurer resolved.
- `outcome = "FULL"` and `reason = "NONE"` if `want > 0` and `unmet == 0` after allocation.
- `outcome = "PARTIAL"` and `reason = "NONE"` if `grant > 0` and `unmet > 0`.
- `outcome = "ZERO"` and `reason = "NO_QUALIFIED_LAYER"` if `grant == 0` and the cell's capacity was positive.

The outcome vocabulary is declared in `reason_codes.json#outcomes`; the reason vocabulary is declared in `reason_codes.json#reasons`.
