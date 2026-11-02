# Batch scoring inputs

Four machine-readable inputs drive one scored report over a batch of records.

## `records.csv`

One row per record. `record_id` is a unique string key. `label` is the observed
ground-truth class used only for the confusion matrix and derived metrics. The
remaining columns are raw feature values: `age`, `income`, `tenure` are numeric;
`region` and `plan` are categorical. A numeric cell may be blank, meaning the
value is missing and must be imputed. A categorical cell may hold a value that is
not among the declared categories. A batch may also carry only the header row and
no records at all.

## `model.json`

A trained logistic-regression model. `intercept` is the bias term. `weights`
maps each expanded feature name to its coefficient: numeric features appear under
their own name (`income`), and every categorical level appears as
`feature=level` (`region=east`, `plan=max`). `threshold` is the decision cutoff
on the rounded probability. `prob_decimals` fixes probability precision.
`report_id` is echoed verbatim into the report. `state` carries the running-state
settings `alpha_num`, `alpha_den`, `lambda_num`, `lambda_den` and
`state_decimals`. `calibration` carries `temperature_milli` and
`prior_shift_micro`.

## The running state

Records are visited in file order, not sorted order, and each record's score
depends on the records before it. Let `alpha` be `alpha_num / alpha_den` and
`lambda` be `lambda_num / lambda_den`. Write `s` for the running state, which
starts at zero before the first record.

For each record in file order, first form the base score as `intercept` plus the
sum of `weight * feature_value` over the model weights. The record's linear score
is `score = base + lambda * s`. After the score is formed, the state advances to
`s = round(alpha * s + (1 - alpha) * score)`, rounded half to even at
`state_decimals`. The next record uses that advanced state.

Worked example with `alpha` 3/4, `lambda` 1/2 and `state_decimals` 6. The first
record has base 0.4, so `s` is zero and `score` is 0.4; the state advances to
`0.75 * 0 + 0.25 * 0.4`, which is 0.1. A second record with base 0.4 scores
`0.4 + 0.5 * 0.1`, which is 0.45, so two records carrying identical features do
not share a score.

## Calibration

The probability comes from the calibrated score, not the linear score. Let
`temperature` be `temperature_milli / 1000` and `shift` be
`prior_shift_micro / 1000000`. The calibrated score is
`score / temperature + shift`, and the probability is the logistic function of
that calibrated score, evaluated so extreme scores do not overflow, then rounded
half to even at `prob_decimals`.

Worked example with `temperature_milli` 1250 and `prior_shift_micro` -80000. A
linear score of 1.35 calibrates to `1.35 / 1.25 - 0.08`, which is exactly 1.0, so
the probability is the logistic function of 1.0.

## `feature_spec.json`

`numeric` gives per-feature `mean`, `std`, and `impute` used for
standardization; `impute` is the declared fill value for a blank cell and is not
required to equal `mean`. Each numeric feature also carries `clip_lo` and
`clip_hi`, the bounds the standardized value is held to, and `knots`, the ordered
list of hinge positions described below. `categorical` gives the ordered list of
known `categories` per feature; each becomes a one-hot indicator column.

## Expanded feature names

The model weights are keyed by expanded feature name. A numeric feature `f`
contributes its own clipped standardized value under the key `f`. Each declared
knot adds one more key, `f|1` for the first knot in `knots`, `f|2` for the
second, and so on in the order the knots are listed. A categorical feature
contributes one key per declared category as `feature=level`. A weight key with
no matching expanded feature contributes nothing, and an expanded feature with no
weight key contributes nothing.

## Winsorization and the hinge basis

For a numeric feature, first impute a blank cell with `impute`, then standardize
as `(value - mean) / std`, using zero when `std` is zero. Then hold that result
to the declared bounds: anything below `clip_lo` becomes `clip_lo` and anything
above `clip_hi` becomes `clip_hi`. Call the held value `x`. The key `f` carries
`x`. For the knot at position `k`, the key `f|i` carries `x - k` when that
difference is above zero and carries zero otherwise.

Worked example. A feature declares `mean` 0, `std` 1, `clip_lo` -1.5,
`clip_hi` 1.5 and `knots` `[-0.5, 1.0]`. A raw value of 9 standardizes to 9 and
is held down to 1.5, so `f` is 1.5, `f|1` is `1.5 - (-0.5)` which is 2.0, and
`f|2` is `1.5 - 1.0` which is 0.5. A raw value of -4 is held up to -1.5, so `f`
is -1.5, `f|1` is zero because `-1.5 - (-0.5)` is negative, and `f|2` is zero.

## `scoring_policy.json`

`metric_decimals` fixes the rounding precision for the `class_metrics` ratios and
for `feature_contributions`. Per-record probabilities and `mean_probability`
instead use `prob_decimals` from `model.json`. `borderline_margin` is the
half-width band around the threshold that flags a record as borderline.
`positive_label` is the string label counted as positive.
