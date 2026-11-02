#!/usr/bin/env python3
"""Batch logistic-regression scorer, written from SCHEMA.md and metrics_reference.md.

Usage: derive_report.py RECORDS_CSV MODEL_JSON SPEC_JSON POLICY_JSON OUT_JSON

Ratios and means are carried as exact fractions, and every rounding goes through
`half_even`, which rounds the decimal value a number prints as.
"""
import csv
import json
import math
import sys
import tempfile
from fractions import Fraction
from pathlib import Path


def half_even(value, places):
    """Round half to even at `places` decimals and return a float."""
    exact = value if isinstance(value, (int, Fraction)) else Fraction(repr(float(value)))
    scale = 10 ** places
    scaled = Fraction(exact) * scale
    whole, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * remainder
    if twice > scaled.denominator or (twice == scaled.denominator and whole % 2 == 1):
        whole += 1
    if whole == 0:
        return 0.0
    return float(Fraction(whole, scale))


def logistic(z):
    """Logistic function that never exponentiates a positive argument."""
    damped = math.exp(-abs(z))
    return 1.0 / (1.0 + damped) if z >= 0 else damped / (1.0 + damped)


class Encoder:
    """Turns one CSV row into the expanded feature map the weights are keyed by."""

    def __init__(self, spec):
        self.numeric = [(name, spec["numeric"][name]) for name in sorted(spec["numeric"])]
        self.categorical = [(name, list(spec["categorical"][name]["categories"]))
                            for name in sorted(spec["categorical"])]

    @staticmethod
    def _held(entry, cell):
        if cell is None or str(cell).strip() == "":
            raw = float(entry["impute"])
        else:
            raw = float(cell)
        spread = float(entry["std"])
        z = 0.0 if spread == 0.0 else (raw - float(entry["mean"])) / spread
        return min(float(entry["clip_hi"]), max(float(entry["clip_lo"]), z))

    def encode(self, row):
        out = {}
        for name, entry in self.numeric:
            x = self._held(entry, row.get(name))
            out[name] = x
            for position, knot in enumerate(entry["knots"], start=1):
                gap = x - float(knot)
                out["%s|%d" % (name, position)] = gap if gap > 0.0 else 0.0
        for name, levels in self.categorical:
            seen = row.get(name)
            for level in levels:
                out["%s=%s" % (name, level)] = 1.0 if seen == level else 0.0
        return out


def safe_ratio(numerator, denominator, places):
    return half_even(Fraction(numerator, denominator), places) if denominator else 0.0


def load_inputs(records_path, model_path, spec_path, policy_path):
    def read_json(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    with open(records_path, newline="", encoding="utf-8") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return rows, read_json(model_path), read_json(spec_path), read_json(policy_path)


def score_batch(rows, model, spec):
    """Replay the batch in file order. Returns (id, rounded probability) pairs in
    file order and the per-weight lists of weight * feature value products."""
    weights = [(key, float(coef)) for key, coef in model["weights"].items()]
    intercept = float(model["intercept"])
    state_cfg = model["state"]
    alpha = state_cfg["alpha_num"] / state_cfg["alpha_den"]
    lam = state_cfg["lambda_num"] / state_cfg["lambda_den"]
    state_places = int(state_cfg["state_decimals"])
    temperature = model["calibration"]["temperature_milli"] / 1000
    shift = model["calibration"]["prior_shift_micro"] / 1000000
    prob_places = int(model["prob_decimals"])

    encoder = Encoder(spec)
    products = {key: [] for key, _ in weights}
    scored = []
    s = 0.0
    for row in rows:
        features = encoder.encode(row)
        base = intercept
        for key, coef in weights:
            term = coef * features.get(key, 0.0)
            base += term
            products[key].append(term)
        score = base + lam * s
        s = half_even(alpha * s + (1 - alpha) * score, state_places)
        scored.append((row["record_id"], half_even(logistic(score / temperature + shift), prob_places)))
    return scored, products


def build_report(rows, model, spec, policy):
    scored, products = score_batch(rows, model, spec)
    threshold = float(model["threshold"])
    prob_places = int(model["prob_decimals"])
    metric_places = int(policy["metric_decimals"])
    margin = float(policy["borderline_margin"])
    positive = str(policy["positive_label"])

    cells = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for row, (_, p) in zip(rows, scored):
        predicted = p >= threshold
        actual = str(row["label"]) == positive
        cells[("t" if predicted == actual else "f") + ("p" if predicted else "n")] += 1
    n = len(scored)
    tp, fp, fn, tn = cells["tp"], cells["fp"], cells["fn"], cells["tn"]
    predicted_positive = tp + fp

    if n:
        mean = half_even(sum((Fraction(repr(p)) for _, p in scored), Fraction(0)) / n, prob_places)
        best_id, best_p = min(scored, key=lambda item: (-item[1], item[0]))
    else:
        mean, best_id, best_p = 0.0, None, 0.0

    return {
        "report_id": model["report_id"],
        "record_count": n,
        "positive_count": predicted_positive,
        "negative_count": n - predicted_positive,
        "mean_probability": mean,
        "class_metrics": {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": safe_ratio(tp, tp + fp, metric_places),
            "recall": safe_ratio(tp, tp + fn, metric_places),
            "f1": safe_ratio(2 * tp, 2 * tp + fp + fn, metric_places),
            "accuracy": safe_ratio(tp + tn, n, metric_places),
        },
        "feature_contributions": {key: half_even(math.fsum(terms), metric_places)
                                  for key, terms in sorted(products.items())},
        "borderline_record_ids": sorted(rid for rid, p in scored if abs(p - threshold) < margin),
        "top_record": {"probability": best_p, "record_id": best_id},
    }


def render(report):
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


# Self-checks on the SCHEMA.md worked-example settings. They never read the
# caller's inputs, so their outcome does not depend on the batch being scored.
def _probe(weights, state, calibration, numeric_entry, csv_text):
    model = {"report_id": "probe", "intercept": 0.0, "threshold": 0.5, "prob_decimals": 6,
             "weights": weights, "state": state, "calibration": calibration}
    spec = {"numeric": {"x": numeric_entry}, "categorical": {}}
    policy = {"metric_decimals": 6, "borderline_margin": 0.05, "positive_label": "1"}
    with tempfile.TemporaryDirectory(prefix="scorer-probe-") as scratch:
        records = Path(scratch) / "records.csv"
        records.write_text(csv_text, encoding="utf-8")
        rows = list(csv.DictReader(records.open(newline="", encoding="utf-8")))
    return build_report(rows, model, spec, policy)


def run_self_checks():
    carry = {"alpha_num": 3, "alpha_den": 4, "lambda_num": 1, "lambda_den": 2, "state_decimals": 6}
    still = {"alpha_num": 0, "alpha_den": 1, "lambda_num": 0, "lambda_den": 1, "state_decimals": 6}
    plain = {"temperature_milli": 1000, "prior_shift_micro": 0}
    wide = {"mean": 0.0, "std": 1.0, "impute": 0.0, "clip_lo": -1000.0, "clip_hi": 1000.0, "knots": []}
    results = []

    twin = _probe({"x": 1.0}, carry, plain, wide, "record_id,x,label\np1,1.5,1\np2,1.5,1\n")
    apart = twin["top_record"]["probability"] != twin["mean_probability"]
    print("state probe: two records with x=1.5 score %s (top %s, mean %s)"
          % ("apart" if apart else "the same", twin["top_record"]["probability"], twin["mean_probability"]))
    results.append(("running state", apart))

    hinged = dict(wide, clip_lo=-1.5, clip_hi=1.5, knots=[-0.5, 1.0])
    hinge = _probe({"x": 2.0, "x|1": 3.0, "x|2": 5.0}, still, plain, hinged, "record_id,x,label\nh1,9,1\n")
    sums = hinge["feature_contributions"]
    print("hinge probe: raw 9 held to 1.5 gives x=%s, x|1=%s, x|2=%s (expected 3.0, 6.0, 2.5)"
          % (sums["x"], sums["x|1"], sums["x|2"]))
    results.append(("hinge basis", sums == {"x": 3.0, "x|1": 6.0, "x|2": 2.5}))

    calibrated = _probe({"x": 1.0}, still, {"temperature_milli": 1250, "prior_shift_micro": -80000}, wide,
                        "record_id,x,label\nk1,1.35,1\n")
    by_hand = half_even(1.0 / (1.0 + math.exp(-1.0)), 6)
    got = calibrated["top_record"]["probability"]
    print("calibration probe: 1.35 / 1.25 - 0.08 = 1.0, logistic(1.0) by hand %s, scorer %s" % (by_hand, got))
    results.append(("calibration", got == by_hand == 0.731059))
    return results


def main(argv):
    if len(argv) != 6:
        print("usage: derive_report.py RECORDS_CSV MODEL_JSON SPEC_JSON POLICY_JSON OUT_JSON", file=sys.stderr)
        return 2
    report = build_report(*load_inputs(*argv[1:5]))
    Path(argv[5]).write_text(render(report), encoding="utf-8")

    cm = report["class_metrics"]
    balanced = (cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"] == report["record_count"]
                and report["positive_count"] + report["negative_count"] == report["record_count"])
    print("reconciliation: tp+fp+fn+tn = %d, record_count = %d, %s"
          % (cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"], report["record_count"], "match" if balanced else "MISMATCH"))
    for name, passed in run_self_checks():
        if not passed:
            print("self-check failed: %s" % name, file=sys.stderr)
    print("assumptions: probabilities and report values use round-half-to-even; unknown categories "
          "contribute all-zero indicators; a rounded probability equal to the threshold predicts "
          "positive; the running state is replayed over the records in file order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
