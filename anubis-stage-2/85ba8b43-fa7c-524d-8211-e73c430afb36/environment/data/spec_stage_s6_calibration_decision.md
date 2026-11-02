# S6 Calibration and Decision

Calibrate each `p_eff` in log-odds space:
`p_cal = sigmoid(a_s + b_s * logit(p_eff))` using the per-stratum `a_s`, `b_s`
from the LIVE spreadsheet sheet. The DRAFT sheet and the plaintext legacy
multipliers are superseded decoys. Decide with an inclusive comparison against
the per-stratum `tau_s`: `yhat = 1 if p_cal >= tau_s`.
