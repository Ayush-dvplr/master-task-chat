Score a batch of records with a trained logistic-regression model and produce an
exact aggregate report. The inputs live in `/app/data`. `records.csv` has one
row per record, each with a unique `record_id`, raw feature columns, and an
observed `label`. `model.json` gives the `intercept`, per-expanded-feature
`weights`, the decision `threshold`, `prob_decimals`, a `report_id`, the
running-state settings under `state`, and the `calibration` settings.
`feature_spec.json` gives numeric `mean`, `std`, `impute`, `clip_lo`, `clip_hi`
and `knots` values and the categorical `categories`. `scoring_policy.json` gives
`metric_decimals`, `borderline_margin`, and `positive_label`. The files
`SCHEMA.md` and `metrics_reference.md` document every field and formula.

Produce two artifacts. Write the report to `/app/report.json`, and write a
reusable standard-library-only script to `/app/derive_report.py` that runs as
`python3 /app/derive_report.py RECORDS_CSV MODEL_JSON SPEC_JSON POLICY_JSON
OUT_JSON`. The report must be computed from the inputs, not written by hand for
the sample.

For each record, standardize every numeric feature as `(value - mean) / std`,
except that when `std` is zero the standardized value is zero, and a blank
numeric cell is first imputed with `impute`. Hold each standardized value to the
declared `clip_lo` and `clip_hi` bounds, then expand it into the hinge terms its
declared `knots` call for, as `SCHEMA.md` sets out. Expand each categorical
feature into one indicator per declared category, and let a value that is not
among the declared categories produce all-zero indicators. The base score is
`intercept` plus the sum of `weight * feature_value` over the model weights.

Records are scored in file order and each one carries a running state forward,
so no record scores in isolation. The state starts at zero, the linear score
adds `lambda` times the state to the base score, and the state then advances
from that linear score as `SCHEMA.md` describes, rounded half-to-even at
`state_decimals`. Divide the linear score by the declared `temperature` and add
the declared prior shift, then take the logistic function of that calibrated
score, evaluated so that extreme scores do not overflow, and round it to
`prob_decimals` using round-half-to-even. A record is predicted positive when
its rounded probability is greater than or equal to the threshold.

The report must contain exactly `report_id`, `record_count`, `positive_count`,
`negative_count`, `mean_probability`, `class_metrics`, `feature_contributions`,
`borderline_record_ids`, and `top_record`. The `class_metrics` object holds
`tp`, `fp`, `fn`, `tn`, `precision`, `recall`, `f1`, and `accuracy` as defined
in `metrics_reference.md`, where every ratio is zero when its denominator is
zero. Accuracy divides by `record_count`, so a batch with no data rows makes
every count zero, every `class_metrics` ratio and `mean_probability` zero, every
`feature_contributions` entry zero, `borderline_record_ids` empty, and
`top_record` a null `record_id` with a `probability` of zero. `mean_probability`
is the mean of the per-record rounded probabilities taken in file order, itself
rounded to `prob_decimals`. `feature_contributions` maps each model weight to
the sum of `weight * feature_value` across all records. `borderline_record_ids`
lists, in sorted order, the ids whose rounded probability differs from the
threshold by strictly less than `borderline_margin`. `top_record` is an object
with a `record_id` field naming the record of largest rounded probability, ties
broken by the smallest `record_id`, and a `probability` field holding that
record's rounded probability. Round each per-record probability and
`mean_probability` half-to-even to `prob_decimals`, and round every ratio in
`class_metrics` and every value in `feature_contributions` half-to-even to
`metric_decimals`. Serialize the report as JSON with two-space indentation,
lexicographically sorted keys, and a trailing newline.

Use only the Python standard library, leave every input file unchanged, and do
not embed a precomputed answer for the shipped inputs. The report must be
byte-identical when the script is rerun on the same inputs, including when those
four machine-readable inputs have different filenames. When you finish, state
that probabilities and report values use round-half-to-even, unknown categories
contribute all-zero indicators, a rounded probability equal to the threshold
predicts positive, and the running state is replayed over the records in file
order.

You have 7200 seconds to complete this task.
