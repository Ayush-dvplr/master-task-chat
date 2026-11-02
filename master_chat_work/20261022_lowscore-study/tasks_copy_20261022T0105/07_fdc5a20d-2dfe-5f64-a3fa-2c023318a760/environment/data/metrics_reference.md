# Metric reference

Definitions for the aggregate fields. All ratios use the counts from the
confusion matrix built over the whole batch; every rounding step is
round-half-to-even. The `class_metrics` ratios and `feature_contributions` round
to `metric_decimals`; per-record probabilities and `mean_probability` round to
`prob_decimals`.

- `tp` / `fp` / `fn` / `tn`: predicted-vs-actual counts, positive class only.
- `precision` = `tp / (tp + fp)`; defined as `0.0` when `tp + fp` is zero.
- `recall` = `tp / (tp + fn)`; defined as `0.0` when `tp + fn` is zero.
- `f1` = `2*tp / (2*tp + fp + fn)`; defined as `0.0` when the denominator is zero.
- `accuracy` = `(tp + tn) / record_count`; defined as `0.0` when `record_count`
  is zero, which happens only for a batch with no data rows. Such a batch reports
  zero counts, zero ratios, a zero `mean_probability`, zero for every
  `feature_contributions` entry, an empty `borderline_record_ids`, and a
  `top_record` whose `record_id` is null and whose `probability` is `0.0`.
- `mean_probability`: the arithmetic mean of the per-record rounded
  probabilities, taken over records in file order, rounded once more to
  `prob_decimals`.
- `feature_contributions`: for each model weight, the sum over all records of
  `weight * feature_value` after standardization, winsorization, hinge expansion
  and one-hot expansion. The sum is taken over the expanded feature the weight
  key names, so a hinge key contributes its own hinge values and not the linear
  ones. Contributions are formed from the base score inputs, so the running state
  and the calibration do not enter them.
- `top_record`: the record with the greatest rounded probability; ties resolve to
  the lexicographically smallest `record_id`.
