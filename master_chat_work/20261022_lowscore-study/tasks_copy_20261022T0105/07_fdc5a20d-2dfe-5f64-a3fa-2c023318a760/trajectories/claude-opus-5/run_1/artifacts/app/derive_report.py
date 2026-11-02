#!/usr/bin/env python3
"""Score a batch of records with a logistic-regression model.

Usage:
    python3 derive_report.py RECORDS_CSV MODEL_JSON SPEC_JSON POLICY_JSON OUT_JSON
"""

import csv
import json
import math
import sys
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 60


def as_decimal(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(repr(float(value)))


def round_half_even(value, decimals):
    quantum = Decimal(1).scaleb(-int(decimals))
    return as_decimal(value).quantize(quantum, rounding=ROUND_HALF_EVEN)


def ratio(numerator, denominator, decimals):
    """Exact rational ratio rounded half-to-even; zero when the denominator is zero."""
    if denominator == 0:
        return round_half_even(0, decimals)
    return round_half_even(Decimal(numerator) / Decimal(denominator), decimals)


def to_json_number(value):
    number = float(value)
    if number == 0.0:
        return 0.0
    return number


def logistic(z):
    """Overflow-safe logistic function."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def expand_features(row, spec):
    """Expand one raw row into the model's expanded feature space."""
    values = {}

    for name, cfg in spec.get("numeric", {}).items():
        cell = row.get(name)
        cell = "" if cell is None else cell.strip()
        raw = float(cfg["impute"]) if cell == "" else float(cell)
        std = float(cfg["std"])
        x = 0.0 if std == 0.0 else (raw - float(cfg["mean"])) / std
        lo = float(cfg["clip_lo"])
        hi = float(cfg["clip_hi"])
        if x < lo:
            x = lo
        elif x > hi:
            x = hi
        values[name] = x
        for index, knot in enumerate(cfg.get("knots", []), start=1):
            hinge = x - float(knot)
            values["{0}|{1}".format(name, index)] = hinge if hinge > 0.0 else 0.0

    for name, cfg in spec.get("categorical", {}).items():
        cell = row.get(name)
        cell = "" if cell is None else cell.strip()
        for category in cfg.get("categories", []):
            key = "{0}={1}".format(name, category)
            values[key] = 1.0 if cell == str(category) else 0.0

    return values


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_records(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_report(records, model, spec, policy):
    weights = model["weights"]
    intercept = float(model["intercept"])
    threshold = as_decimal(model["threshold"])
    prob_decimals = int(model["prob_decimals"])

    state_cfg = model["state"]
    alpha = float(state_cfg["alpha_num"]) / float(state_cfg["alpha_den"])
    lam = float(state_cfg["lambda_num"]) / float(state_cfg["lambda_den"])
    state_decimals = int(state_cfg["state_decimals"])

    calibration = model["calibration"]
    temperature = float(calibration["temperature_milli"]) / 1000.0
    shift = float(calibration["prior_shift_micro"]) / 1000000.0

    metric_decimals = int(policy["metric_decimals"])
    margin = as_decimal(policy["borderline_margin"])
    positive_label = str(policy["positive_label"])

    contributions = {key: 0.0 for key in weights}
    probabilities = []
    borderline = []
    tp = fp = fn = tn = 0
    top_id = None
    top_prob = None
    state = 0.0

    for row in records:
        features = expand_features(row, spec)

        base = intercept
        for key, weight in weights.items():
            if key in features:
                term = float(weight) * features[key]
                base += term
                contributions[key] += term

        score = base + lam * state
        state = float(
            round_half_even(alpha * state + (1.0 - alpha) * score, state_decimals)
        )

        calibrated = score / temperature + shift
        probability = round_half_even(logistic(calibrated), prob_decimals)
        probabilities.append(probability)

        record_id = row.get("record_id")
        predicted_positive = probability >= threshold
        actual_positive = str(row.get("label", "")).strip() == positive_label

        if predicted_positive and actual_positive:
            tp += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        elif not predicted_positive and actual_positive:
            fn += 1
        else:
            tn += 1

        if abs(probability - threshold) < margin:
            borderline.append(record_id)

        if (
            top_prob is None
            or probability > top_prob
            or (probability == top_prob and record_id < top_id)
        ):
            top_prob = probability
            top_id = record_id

    record_count = len(records)

    if record_count:
        mean_probability = round_half_even(
            sum(probabilities, Decimal(0)) / Decimal(record_count), prob_decimals
        )
    else:
        mean_probability = round_half_even(0, prob_decimals)
        top_prob = round_half_even(0, prob_decimals)

    class_metrics = {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": to_json_number(ratio(tp, tp + fp, metric_decimals)),
        "recall": to_json_number(ratio(tp, tp + fn, metric_decimals)),
        "f1": to_json_number(ratio(2 * tp, 2 * tp + fp + fn, metric_decimals)),
        "accuracy": to_json_number(ratio(tp + tn, record_count, metric_decimals)),
    }

    return {
        "report_id": model["report_id"],
        "record_count": record_count,
        "positive_count": tp + fp,
        "negative_count": fn + tn,
        "mean_probability": to_json_number(mean_probability),
        "class_metrics": class_metrics,
        "feature_contributions": {
            key: to_json_number(round_half_even(total, metric_decimals))
            for key, total in contributions.items()
        },
        "borderline_record_ids": sorted(borderline),
        "top_record": {
            "record_id": top_id,
            "probability": to_json_number(top_prob),
        },
    }


def main(argv):
    if len(argv) != 6:
        sys.stderr.write(
            "usage: derive_report.py RECORDS_CSV MODEL_JSON SPEC_JSON "
            "POLICY_JSON OUT_JSON\n"
        )
        return 2

    records_csv, model_json, spec_json, policy_json, out_json = argv[1:]

    report = build_report(
        read_records(records_csv),
        read_json(model_json),
        read_json(spec_json),
        read_json(policy_json),
    )

    with open(out_json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
