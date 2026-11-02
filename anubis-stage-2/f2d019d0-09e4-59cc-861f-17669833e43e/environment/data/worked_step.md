# One worked step

This walk uses `sample_run_config.json`, whose promotion sentinel is off, whose
bias is off, whose jitter slot count is zero and whose mesh has a single rank.
Several layers of the contract are therefore inert here. The walk is a
calibration aid, not a representative case.

Step 1 of that configuration draws 64 token salts and 4 expert phases and
consumes nothing else. Every logit reduces to the affinity term alone because the
bias and the jitter terms vanish. Quantisation still applies and ties still occur, so the
sealed key still decides selection, but the placement rank and the bias rank are
constant across experts on this configuration and cannot separate the candidate
keys on their own.

Capacity uses a factor of 1.5 over 128 assignments and 4 experts, so the ideal is
48 and every demand is below it. The aligned value is the demand rounded up to a
multiple of 8 and the minimum of 8 then holds only for an expert whose demand is
zero. No assignment is dropped. The single rank makes the rank bucket and the all
to all bucket equal, so the two quantities cannot be told apart here either.

The compiled cache sees one key per code object per step and the token count is
constant, so nothing recompiles after the first step and nothing is evicted.
