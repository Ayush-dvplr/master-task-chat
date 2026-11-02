# ALAE rules

The ALAE allocation convention is a methodology reading reported in `methodology_audit.json` under `settlement.alae_convention`. It is settled from the observations in `claim_adjustment_log.log` by enumeration against the two candidate readings `pro_rata` and `excess_only`. A reading that fits only some of the observations is the wrong reading; the surviving reading is unique.

Under `pro_rata`, ALAE is a near-constant fraction of the settled amount on every row, regardless of layer. The fraction is fixed at `0.08` and is declared in `counterfactual_parameters.md`; see that document for the derivation of `0.08` from the observed log lines. Under `pro_rata`, a claim whose row carries no explicit `alae` adjustment takes `alae = half_up_round(0.08 * paid_to_date)`.

Under `excess_only`, retention-layer rows carry zero ALAE and excess-layer rows carry positive ALAE.

The settled reading is applied uniformly to every claim in the ledger when deriving `alae` on each ledger row.
