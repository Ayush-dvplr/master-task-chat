# S8 Uncertainty and Payout

Report 95% Wilson score intervals on the Kish effective sample size
`n_eff = (sum w)^2 / sum(w^2)` computed over the correct denominator subset:
actual positives for recall, predicted positives for precision. The z value is
in the policy PDF only. Rewarded credits count true positives times the
per-stratum recovery factor; forfeited credits count false negatives. The
review unit cost (PDF only) is charged per flagged match, weighted. The net
BEFORE levy and floor = rewarded - review cost. Round half-to-even at each
stage.
