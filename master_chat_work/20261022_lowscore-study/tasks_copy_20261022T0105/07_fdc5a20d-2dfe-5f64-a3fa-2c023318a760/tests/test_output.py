import ast
import csv
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = 7715520411030921843
CHALLENGE_SEED = 4402318876655120097
EVAL_SEED = 9138475560012773641

_UNTRUSTED_UID = 65532
_UNTRUSTED_GID = 65532
_RUN_TIMEOUT_SEC = 25

# Bounds wide enough that no fixture value reaches them, used where a fixture
# exercises a rule other than winsorization. Every numeric spec still carries
# clip_lo, clip_hi and knots, as SCHEMA.md documents.
_WIDE_LO = -1000000.0
_WIDE_HI = 1000000.0

_VISIBLE_RECORDS = """record_id,age,income,region,plan,tenure,label
r0001,34,72000,north,pro,18,0
r0002,51,45000,south,basic,60,0
r0003,29,88000,east,max,6,1
r0004,45,53000,west,pro,36,0
r0005,38,61000,north,basic,24,1
r0006,60,120000,east,max,48,1
r0007,27,39000,south,pro,9,0
r0008,42,95000,west,max,30,1
r0009,33,67000,north,pro,15,1
r0010,55,48000,south,basic,72,0
r0011,31,81000,east,pro,12,1
r0012,47,58000,west,basic,42,0
"""
_VISIBLE_MODEL = {
    "report_id": "LBS-9F3A2C7",
    "intercept": -0.45,
    "threshold": 0.5,
    "prob_decimals": 6,
    "weights": {
        "age": 0.32,
        "income": 1.18,
        "tenure": -0.71,
        "region=east": 0.24,
        "region=north": -0.12,
        "region=south": 0.18,
        "region=west": 0.05,
        "plan=basic": -0.63,
        "plan=max": 0.74,
        "plan=pro": 0.29,
        "age|1": -0.44,
        "age|2": 0.61,
        "income|1": 0.53
    },
    "state": {
        "alpha_num": 3,
        "alpha_den": 4,
        "lambda_num": 1,
        "lambda_den": 2,
        "state_decimals": 6
    },
    "calibration": {
        "temperature_milli": 1250,
        "prior_shift_micro": -80000
    }
}
_VISIBLE_SPEC = {
    "numeric": {
        "age": {
            "mean": 41.0,
            "std": 10.5,
            "impute": 40.0,
            "clip_lo": -2.0,
            "clip_hi": 2.0,
            "knots": [
                -0.5,
                0.75
            ]
        },
        "income": {
            "mean": 68000.0,
            "std": 24000.0,
            "impute": 65000.0,
            "clip_lo": -1.75,
            "clip_hi": 1.75,
            "knots": [
                0.25
            ]
        },
        "tenure": {
            "mean": 31.0,
            "std": 19.0,
            "impute": 28.0,
            "clip_lo": -2.5,
            "clip_hi": 2.5,
            "knots": []
        }
    },
    "categorical": {
        "region": {
            "categories": [
                "east",
                "north",
                "south",
                "west"
            ]
        },
        "plan": {
            "categories": [
                "basic",
                "max",
                "pro"
            ]
        }
    }
}
_VISIBLE_POLICY = {"metric_decimals": 6, "borderline_margin": 0.05, "positive_label": "1"}
# The same batch with one record's features and label changed, used to watch whether
# a delivered script reads the records it is handed.
_PERTURBED_RECORDS = _VISIBLE_RECORDS.replace("r0003,29,88000,east,max,6,1", "r0003,58,41000,west,basic,66,0")
_VISIBLE_INPUTS = None
_PERTURBED_INPUTS = None

DEFAULT_STATE = {"alpha_num": 3, "alpha_den": 4, "lambda_num": 1, "lambda_den": 2, "state_decimals": 6}
DEFAULT_CALIBRATION = {"temperature_milli": 1250, "prior_shift_micro": -80000}
# Fixtures that grade a rule downstream of the probability use these, so the
# running state and the calibration (graded by their own checks) cannot decide them.
INERT_STATE = {"alpha_num": 0, "alpha_den": 1, "lambda_num": 0, "lambda_den": 1, "state_decimals": 6}
IDENTITY_CALIBRATION = {"temperature_milli": 1000, "prior_shift_micro": 0}


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFFFFFFFFFF or 0xA0761D6478BD642F

    def _next(self):
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo, hi):
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self._next() % len(seq)]

    def coef(self):
        return self.rand_int(-200, 200) / 100.0


def _num(mean, std, impute, clip_lo=_WIDE_LO, clip_hi=_WIDE_HI, knots=()):
    """One numeric spec entry in the documented shape."""
    return {"mean": mean, "std": std, "impute": impute,
            "clip_lo": clip_lo, "clip_hi": clip_hi, "knots": list(knots)}


def _round(value, places):
    q = Decimal(1).scaleb(-places)
    d = value if isinstance(value, Decimal) else Decimal(repr(float(value)))
    return float(d.quantize(q, rounding=ROUND_HALF_EVEN)) + 0.0


def _sigmoid(score):
    if score >= 0.0:
        return 1.0 / (1.0 + math.exp(-score))
    z = math.exp(score)
    return z / (1.0 + z)


def _expand(row, spec):
    x = {}
    for name in sorted(spec["numeric"]):
        conf = spec["numeric"][name]
        raw = row.get(name, "")
        value = float(conf["impute"]) if raw is None or str(raw).strip() == "" else float(raw)
        std = float(conf["std"])
        u = 0.0 if std == 0.0 else (value - float(conf["mean"])) / std
        u = min(max(u, float(conf["clip_lo"])), float(conf["clip_hi"]))
        x[name] = u
        for index, knot in enumerate(conf["knots"], 1):
            gap = u - float(knot)
            x["%s|%d" % (name, index)] = gap if gap > 0.0 else 0.0
    for name in sorted(spec["categorical"]):
        value = row.get(name, "")
        for category in spec["categorical"][name]["categories"]:
            x["%s=%s" % (name, category)] = 1.0 if value == category else 0.0
    return x


def _carry_settings(model):
    state = model["state"]
    alpha = float(state["alpha_num"]) / float(state["alpha_den"])
    lam = float(state["lambda_num"]) / float(state["lambda_den"])
    return alpha, lam, int(state["state_decimals"])


def _calibration(model):
    calib = model["calibration"]
    return float(calib["temperature_milli"]) / 1000.0, float(calib["prior_shift_micro"]) / 1000000.0


def derive(records_path, model_path, spec_path, policy_path):
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    with Path(records_path).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    weights = model["weights"]
    intercept = float(model["intercept"])
    threshold = float(model["threshold"])
    prob_places = int(model["prob_decimals"])
    metric_places = int(policy["metric_decimals"])
    margin = float(policy["borderline_margin"])
    positive_label = str(policy["positive_label"])
    alpha, lam, state_places = _carry_settings(model)
    temperature, prior_shift = _calibration(model)

    probs = {}
    preds = {}
    contrib = {key: 0.0 for key in weights}
    carry = 0.0
    for row in rows:
        rid = row["record_id"]
        x = _expand(row, spec)
        base = intercept
        for key in weights:
            base += float(weights[key]) * x.get(key, 0.0)
            contrib[key] += float(weights[key]) * x.get(key, 0.0)
        score = base + lam * carry
        carry = _round(alpha * carry + (1.0 - alpha) * score, state_places)
        p = _round(_sigmoid(score / temperature + prior_shift), prob_places)
        probs[rid] = p
        preds[rid] = 1 if p >= threshold else 0

    tp = fp = fn = tn = 0
    for row in rows:
        rid = row["record_id"]
        actual = 1 if str(row["label"]) == positive_label else 0
        pred = preds[rid]
        if pred == 1 and actual == 1:
            tp += 1
        elif pred == 1 and actual == 0:
            fp += 1
        elif pred == 0 and actual == 1:
            fn += 1
        else:
            tn += 1
    precision = _round(Decimal(tp) / Decimal(tp + fp), metric_places) if (tp + fp) > 0 else 0.0
    recall = _round(Decimal(tp) / Decimal(tp + fn), metric_places) if (tp + fn) > 0 else 0.0
    f1 = _round(Decimal(2 * tp) / Decimal(2 * tp + fp + fn), metric_places) if (2 * tp + fp + fn) > 0 else 0.0
    accuracy = _round(Decimal(tp + tn) / Decimal(len(rows)), metric_places) if rows else 0.0
    positive_count = sum(1 for rid in preds if preds[rid] == 1)
    ordered_ids = [row["record_id"] for row in rows]
    mean_probability = _round(sum((Decimal(repr(probs[r])) for r in ordered_ids), Decimal(0)) / Decimal(len(rows)), prob_places) if rows else 0.0
    borderline = sorted(rid for rid in probs if abs(probs[rid] - threshold) < margin)
    top = None
    for rid in sorted(probs):
        if top is None or probs[rid] > top[1]:
            top = (rid, probs[rid])
    return {
        "report_id": model["report_id"],
        "record_count": len(rows),
        "positive_count": positive_count,
        "negative_count": len(rows) - positive_count,
        "mean_probability": mean_probability,
        "class_metrics": {
            "accuracy": accuracy,
            "f1": f1,
            "fn": fn,
            "fp": fp,
            "precision": precision,
            "recall": recall,
            "tn": tn,
            "tp": tp,
        },
        "feature_contributions": {key: _round(contrib[key], metric_places) for key in sorted(contrib)},
        "borderline_record_ids": borderline,
        "top_record": {"probability": top[1] if top else 0.0, "record_id": top[0] if top else None},
    }


def _untrusted_kwargs():
    if os.name == "posix" and os.geteuid() == 0:
        return {"user": _UNTRUSTED_UID, "group": _UNTRUSTED_GID, "extra_groups": (), "umask": 0o077}
    return {}


def _input_dir(prefix):
    # Root-owned and not writable by the unprivileged script, so the files the
    # expected report is derived from cannot be rewritten by the code under test.
    root = Path(tempfile.mkdtemp(prefix=prefix))
    root.chmod(0o755)
    return root


def _output_dir(prefix):
    # A separate directory the unprivileged script may write its report into.
    root = Path(tempfile.mkdtemp(prefix=prefix))
    root.chmod(0o777)
    return root


def _write_inputs(root, records_rows, header, model, spec, policy):
    rec = root / "records.csv"
    with rec.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for row in records_rows:
            writer.writerow({k: row.get(k, "") for k in header})
    modelp = root / "model.json"
    specp = root / "feature_spec.json"
    policyp = root / "scoring_policy.json"
    modelp.write_text(json.dumps(model, sort_keys=True), encoding="utf-8")
    specp.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
    policyp.write_text(json.dumps(policy, sort_keys=True), encoding="utf-8")
    for p in (rec, modelp, specp, policyp):
        p.chmod(0o644)
    return rec, modelp, specp, policyp


def _fixture(rows, numeric, categorical, weights, intercept, threshold, report_id="FX-CASE", prob_decimals=6, metric_decimals=6, margin=0.05, positive_label="1", state=None, calibration=None):
    root = _input_dir("lbs-fix-")
    header = ["record_id"] + sorted(numeric) + sorted(categorical) + ["label"]
    spec = {"numeric": numeric, "categorical": categorical}
    model = {"report_id": report_id, "intercept": intercept, "threshold": threshold,
             "prob_decimals": prob_decimals, "weights": weights,
             "state": DEFAULT_STATE if state is None else state,
             "calibration": DEFAULT_CALIBRATION if calibration is None else calibration}
    policy = {"metric_decimals": metric_decimals, "borderline_margin": margin, "positive_label": positive_label}
    return _write_inputs(root, rows, header, model, spec, policy)


def write_case(seed, n=44):
    root = _input_dir("lbs-case-")
    rng = Rng(seed)
    # The generated tier carries the winsorization bounds and the hinge knots too,
    # so the hidden corpus exercises the whole documented grammar rather than the
    # linear part of it.
    numeric = {
        "f_a": _num(50.0, 12.0, 50.0, -1.5, 1.5, [-0.5, 0.75]),
        "f_b": _num(0.0, 3.5, 2.5, -2.0, 2.0, [0.25]),
        "f_c": _num(7.0, 2.0, 7.0, -1.25, 1.25, []),
        "f_d": _num(100.0, 40.0, 130.0, -1.75, 1.75, [0.0]),
    }
    categorical = {
        "cat_p": {"categories": ["alpha", "beta", "gamma"]},
        "cat_q": {"categories": ["low", "high"]},
    }
    weights = {}
    for name in numeric:
        weights[name] = rng.coef()
        for index in range(1, len(numeric[name]["knots"]) + 1):
            weights["%s|%d" % (name, index)] = rng.coef()
    for name in categorical:
        for level in categorical[name]["categories"]:
            weights["%s=%s" % (name, level)] = rng.coef()
    # The hidden tier declares its own state and calibration settings, so they must
    # be read from model.json rather than copied from the shipped model.
    model = {"report_id": "HID-%012x" % (seed & 0xFFFFFFFFFFFF), "intercept": rng.coef(),
             "threshold": 0.5, "prob_decimals": 6, "weights": weights,
             "state": {"alpha_num": 2, "alpha_den": 5, "lambda_num": 3, "lambda_den": 4, "state_decimals": 5},
             "calibration": {"temperature_milli": 1600, "prior_shift_micro": -150000}}
    spec = {"numeric": numeric, "categorical": categorical}
    policy = {"metric_decimals": 6, "borderline_margin": 0.05, "positive_label": "1"}
    header = ["record_id", "f_a", "f_b", "f_c", "f_d", "cat_p", "cat_q", "label"]
    p_levels = ["alpha", "beta", "gamma"]
    q_levels = ["low", "high"]
    rows = []
    for i in range(1, n + 1):
        row = {
            "record_id": "h%04d" % i,
            "f_a": rng.rand_int(10, 90),
            "f_b": rng.rand_int(-9, 9),
            "f_c": rng.rand_int(1, 14),
            "f_d": rng.rand_int(20, 180),
            "cat_p": rng.choice(p_levels),
            "cat_q": rng.choice(q_levels),
            "label": str(rng.rand_int(0, 1)),
        }
        # Blank cells on features whose impute value differs from the mean, so the
        # generated corpus separates the declared impute value from the mean.
        if i % 7 == 0:
            row["f_b"] = ""
        if i % 11 == 0:
            row["f_d"] = ""
        rows.append(row)
    # Emit the batch in descending id order so file order is never sorted order.
    rows.reverse()
    return _write_inputs(root, rows, header, model, spec, policy)


def _write_fixed(prefix, records_text):
    root = _input_dir(prefix)
    rec = root / "records.csv"
    rec.write_text(records_text, encoding="utf-8")
    modelp = root / "model.json"
    specp = root / "feature_spec.json"
    policyp = root / "scoring_policy.json"
    modelp.write_text(json.dumps(_VISIBLE_MODEL, sort_keys=True), encoding="utf-8")
    specp.write_text(json.dumps(_VISIBLE_SPEC, sort_keys=True), encoding="utf-8")
    policyp.write_text(json.dumps(_VISIBLE_POLICY, sort_keys=True), encoding="utf-8")
    for p in (rec, modelp, specp, policyp):
        p.chmod(0o644)
    return rec, modelp, specp, policyp


def visible_inputs():
    global _VISIBLE_INPUTS
    if _VISIBLE_INPUTS is None:
        _VISIBLE_INPUTS = _write_fixed("lbs-visible-", _VISIBLE_RECORDS)
    return _VISIBLE_INPUTS


def perturbed_visible_inputs():
    """The visible corpus with one record changed, written under the conventional
    file names. A script that keys a memorised answer on those names sees exactly
    the layout it expects and still has to follow the changed content."""
    global _PERTURBED_INPUTS
    if _PERTURBED_INPUTS is None:
        _PERTURBED_INPUTS = _write_fixed("lbs-perturbed-", _PERTURBED_RECORDS)
    return _PERTURBED_INPUTS


def _script(workspace):
    return Path(workspace) / "derive_report.py"


def _report(workspace):
    return Path(workspace) / "report.json"


def _run_raw(workspace, paths):
    """Run the delivered script once as an unprivileged user. Returns the bytes it
    wrote as text, or None when it is missing, fails, times out or writes nothing."""
    script = _script(workspace)
    if not script.is_file():
        return None
    out = _output_dir("lbs-out-") / "out.json"
    cmd = [sys.executable, str(script), str(paths[0]), str(paths[1]), str(paths[2]), str(paths[3]), str(out)]
    try:
        proc = subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, **_untrusted_kwargs())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    # Wait without reaping (WNOWAIT), so the pid and its process group stay reserved
    # while the group is killed; checks run concurrently, and killing after the
    # reap could hit a recycled pid belonging to another check.
    exited = False
    deadline = time.monotonic() + _RUN_TIMEOUT_SEC
    try:
        while True:
            try:
                if os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                    exited = True
                    break
            except ChildProcessError:
                exited = True
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
    finally:
        # Kill the whole session on every exit path so nothing the script spawned
        # outlives the check, then reap the child.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        returncode = proc.wait()
    if not exited or returncode != 0:
        return None
    try:
        return out.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _run(workspace, paths):
    text = _run_raw(workspace, paths)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _same(actual, expected):
    """Type-aware equality: bool never passes for a number, and int never passes for bool."""
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual == expected
    if isinstance(expected, int):
        return not isinstance(actual, bool) and isinstance(actual, int) and actual == expected
    if isinstance(expected, float):
        return not isinstance(actual, bool) and isinstance(actual, (int, float)) and float(actual) == expected
    if isinstance(expected, str):
        return isinstance(actual, str) and actual == expected
    if expected is None:
        return actual is None
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_same(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(_same(actual[k], expected[k]) for k in expected)
    return actual == expected


def _field(report, *keys):
    """Walk nested keys of an agent report; a missing key or wrong shape is a miss."""
    node = report
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(key)
        node = node[key]
    return node


def _fresh_matches(workspace, paths, *keys):
    """Derive the expected value first, then run the script and compare one field."""
    expected = derive(*paths)
    out = _run(workspace, paths)
    if out is None:
        return False
    try:
        return _same(_field(out, *keys), _field(expected, *keys))
    except KeyError:
        return False


def _load_report(workspace):
    try:
        data = json.loads(_report(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _content_blind(workspace):
    """True when the delivered script returns the same bytes for the visible batch
    and for the changed copy of it, which is what an embedded answer looks like from
    outside. The two correct reports are compared first, so the probe reads the
    script rather than a fixture that would score the same either way."""
    if derive(*visible_inputs()) == derive(*perturbed_visible_inputs()):
        return False
    first = _run_raw(workspace, visible_inputs())
    second = _run_raw(workspace, perturbed_visible_inputs())
    return first is not None and second is not None and first == second


@criterion(description="report.json exists and parses as a JSON object")
def report_artifact_exists_and_is_json(workspace: Path) -> bool:
    try:
        return _load_report(workspace) is not None
    except Exception:
        return False


@criterion(description="report.json has exactly the required top-level and nested keys")
def report_schema_is_exact(workspace: Path) -> bool:
    try:
        report = _load_report(workspace)
        if report is None:
            return False
        if set(report) != {"report_id", "record_count", "positive_count", "negative_count", "mean_probability",
                           "class_metrics", "feature_contributions", "borderline_record_ids", "top_record"}:
            return False
        cm = report["class_metrics"]
        top = report["top_record"]
        return (isinstance(cm, dict) and set(cm) == {"accuracy", "f1", "fn", "fp", "precision", "recall", "tn", "tp"}
                and isinstance(top, dict) and set(top) == {"probability", "record_id"})
    except Exception:
        return False


@criterion(description="the shipped report equals an independent derivation of the visible batch")
def visible_report_matches_independent_derivation(workspace: Path) -> bool:
    try:
        expected = derive(*visible_inputs())
        report = _load_report(workspace)
        return report is not None and _same(report, expected)
    except Exception:
        return False


@criterion(description="report.json bytes are two-space, sorted-key JSON ending in one newline")
def report_canonical_serialization(workspace: Path) -> bool:
    try:
        text = _report(workspace).read_text(encoding="utf-8")
        return text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    except Exception:
        return False


@criterion(description="the reusable script reproduces the full report on a fresh hidden batch")
def hidden_full_report_matches_fresh_derivation(workspace: Path) -> bool:
    try:
        paths = write_case(EVAL_SEED, 60)
        expected = derive(*paths)
        out = _run(workspace, paths)
        return out is not None and _same(out, expected)
    except Exception:
        return False


@criterion(description="the script's output on a fresh batch uses the canonical JSON bytes")
def fresh_report_canonical_serialization(workspace: Path) -> bool:
    try:
        text = _run_raw(workspace, write_case(CHALLENGE_SEED, 18))
        return text is not None and text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    except Exception:
        return False


@criterion(description="a class_metrics ratio on a rounding tie rounds half-to-even at metric_decimals")
def fresh_banker_rounding_precision(workspace: Path) -> bool:
    # precision is exactly 1/8 = 0.125, which half-to-even reports as 0.12 at two places.
    try:
        rows = [{"record_id": "p%02d" % i, "x": 1, "label": "1" if i == 0 else "0"} for i in range(8)]
        rows.append({"record_id": "p99", "x": -1, "label": "0"})
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 100.0}, 0.0, 0.5, metric_decimals=2)
        if derive(*paths)["class_metrics"]["precision"] != 0.12:
            return False
        return _fresh_matches(workspace, paths, "class_metrics", "precision")
    except Exception:
        return False


@criterion(description="a zero-standard-deviation feature standardizes to zero contribution")
def fresh_zero_variance_feature_zeroed(workspace: Path) -> bool:
    try:
        rows = [{"record_id": "a", "z": 99, "label": "1"}, {"record_id": "b", "z": -40, "label": "0"}]
        paths = _fixture(rows, {"z": _num(7.0, 0.0, 7.0)}, {}, {"z": 9.0}, 0.1, 0.5)
        if derive(*paths)["feature_contributions"]["z"] != 0.0:
            return False
        return _fresh_matches(workspace, paths, "feature_contributions", "z")
    except Exception:
        return False


@criterion(description="an undeclared category value, and a weight key naming no expanded feature, contribute zero")
def fresh_unseen_category_contributes_zero(workspace: Path) -> bool:
    # "purple" is a record value and a weight key level, but not a declared
    # category, so "color=purple" names no expanded feature and must sum to 0.0;
    # deriving indicators from the weight keys reports 5.0, indexing the expanded
    # features by weight key raises.
    try:
        categorical = {"color": {"categories": ["red", "blue"]}}
        weights = {"color=red": 5.0, "color=blue": 5.0, "color=purple": 5.0}
        rows = [{"record_id": "a", "color": "red", "label": "1"}, {"record_id": "b", "color": "blue", "label": "1"},
                {"record_id": "c", "color": "green", "label": "0"}, {"record_id": "d", "color": "purple", "label": "0"}]
        paths = _fixture(rows, {}, categorical, weights, 0.0, 0.5)
        if derive(*paths)["feature_contributions"] != {"color=blue": 5.0, "color=purple": 0.0, "color=red": 5.0}:
            return False
        return _fresh_matches(workspace, paths, "feature_contributions")
    except Exception:
        return False


@criterion(description="a blank numeric cell is imputed with the declared impute value, not the mean")
def fresh_missing_numeric_imputed_to_declared_value(workspace: Path) -> bool:
    # impute (30.0) differs from mean (10.0). The imputed cell standardizes to 4.0
    # and is then held down to the declared clip_hi of 2.0, so the pair sums to 3.0
    # and the linear term reaches 12.0. Substituting the mean sums to 1.0 and
    # substituting zero sums to -1.0, so only the declared value lands here, and a
    # solver that skips the clip reaches 5.0 instead.
    try:
        numeric = {"m": _num(10.0, 5.0, 30.0, -2.0, 2.0, [0.5])}
        rows = [{"record_id": "a", "m": "", "label": "1"}, {"record_id": "b", "m": 15, "label": "1"}]
        paths = _fixture(rows, numeric, {}, {"m": 4.0, "m|1": 3.0}, 0.0, 0.5)
        if derive(*paths)["feature_contributions"]["m"] != 12.0:
            return False
        return _fresh_matches(workspace, paths, "feature_contributions", "m")
    except Exception:
        return False


@criterion(description="extreme linear scores yield saturated probabilities without error")
def fresh_sigmoid_extreme_scores_stable(workspace: Path) -> bool:
    try:
        rows = [{"record_id": "hi", "x": 1000, "label": "1"}, {"record_id": "lo", "x": -1000, "label": "0"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.0, 0.5)
        if derive(*paths)["top_record"] != {"probability": 1.0, "record_id": "hi"}:
            return False
        return _fresh_matches(workspace, paths, "top_record")
    except Exception:
        return False


@criterion(description="precision, recall and f1 are exactly zero when their denominators are zero")
def fresh_zero_denominator_ratios_are_zero(workspace: Path) -> bool:
    # One record predicted negative and labelled negative leaves tp, fp and fn all
    # zero, so all three ratios reach a zero denominator on the same corpus.
    try:
        paths = _fixture([{"record_id": "a", "x": -1, "label": "0"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 50.0}, 0.0, 0.5)
        out = _run(workspace, paths)
        if out is None:
            return False
        return all(_same(_field(out, "class_metrics", cell), 0.0) for cell in ("precision", "recall", "f1"))
    except Exception:
        return False


@criterion(description="a batch with no data rows produces the zero-filled report")
def fresh_empty_batch_report_is_zero_filled(workspace: Path) -> bool:
    # record_count is the accuracy denominator, so only an empty batch reaches it.
    try:
        paths = _fixture([], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 50.0}, 0.0, 0.5)
        expected = derive(*paths)
        if expected["record_count"] != 0 or expected["top_record"] != {"probability": 0.0, "record_id": None}:
            return False
        out = _run(workspace, paths)
        if out is None:
            return False
        for field in ("record_count", "positive_count", "negative_count", "mean_probability",
                      "feature_contributions", "borderline_record_ids", "top_record"):
            if not _same(_field(out, field), expected[field]):
                return False
        # precision, recall and f1 keep their own zero-denominator check on a
        # non-empty batch; only accuracy reaches a zero denominator here.
        return all(_same(_field(out, "class_metrics", cell), expected["class_metrics"][cell])
                   for cell in ("tp", "fp", "fn", "tn", "accuracy"))
    except Exception:
        return False


@criterion(description="the confusion matrix counts the policy-declared positive label")
def fresh_positive_label_from_policy(workspace: Path) -> bool:
    try:
        rows = [{"record_id": "yes", "x": 1, "label": "yes"}, {"record_id": "no", "x": -1, "label": "no"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 20.0}, 0.0, 0.5, positive_label="yes")
        if derive(*paths)["class_metrics"]["tp"] != 1:
            return False
        return _fresh_matches(workspace, paths, "class_metrics", "tp")
    except Exception:
        return False


@criterion(description="a per-record probability rounds to the model's prob_decimals")
def fresh_probability_precision_from_model(workspace: Path) -> bool:
    # Inert state and identity calibration, so only the precision is decided here:
    # the logistic of 1.35 is 0.794130, which reports as 0.79 at prob_decimals 2.
    try:
        paths = _fixture([{"record_id": "a", "x": 1.35, "label": "1"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0},
                         0.0, 0.5, prob_decimals=2, state=INERT_STATE, calibration=IDENTITY_CALIBRATION)
        if derive(*paths)["top_record"]["probability"] != 0.79:
            return False
        return _fresh_matches(workspace, paths, "top_record", "probability")
    except Exception:
        return False


@criterion(description="a per-record probability on a prob_decimals tie rounds half-to-even")
def fresh_probability_half_even_tie_at_prob_decimals(workspace: Path) -> bool:
    # Inert state and identity calibration, so a zero linear score reaches the
    # logistic as exactly zero and the raw probability is exactly 0.5; at
    # prob_decimals=0 the retained digit is even, so half-to-even keeps 0.0 while
    # half-up would report 1.0. metric_decimals matches prob_decimals so that only
    # the tie rule is decisive.
    try:
        paths = _fixture([{"record_id": "a", "x": 0, "label": "1"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0},
                         0.0, 0.5, prob_decimals=0, metric_decimals=0,
                         state=INERT_STATE, calibration=IDENTITY_CALIBRATION)
        if derive(*paths)["top_record"] != {"probability": 0.0, "record_id": "a"}:
            return False
        return _fresh_matches(workspace, paths, "top_record")
    except Exception:
        return False


@criterion(description="a rounded probability exactly equal to the threshold predicts positive")
def fresh_threshold_tie_counts_as_positive(workspace: Path) -> bool:
    try:
        paths = _fixture([{"record_id": "a", "x": 0, "label": "1"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.1, 0.5)
        if derive(*paths)["positive_count"] != 1:
            return False
        return _fresh_matches(workspace, paths, "positive_count")
    except Exception:
        return False


@criterion(description="feature contributions sum each weight times value across the whole batch")
def fresh_feature_contributions_are_corpus_sums(workspace: Path) -> bool:
    try:
        rows = [{"record_id": "a", "x": 2, "label": "1"}, {"record_id": "b", "x": 4, "label": "0"},
                {"record_id": "c", "x": -6, "label": "0"}]
        paths = _fixture(rows, {"x": _num(0.0, 2.0, 0.0)}, {}, {"x": 3.0}, 0.0, 0.5)
        if derive(*paths)["feature_contributions"]["x"] != 0.0:
            return False
        return _fresh_matches(workspace, paths, "feature_contributions")
    except Exception:
        return False


@criterion(description="equal top probabilities resolve to the smallest record id")
def fresh_top_record_tiebreak_smallest_id(workspace: Path) -> bool:
    # Inert state and identity calibration make the three probabilities exactly
    # equal, so only the tie-break decides. The smallest id sits mid-file: keeping
    # the first maximum in file order reports b_rec, keeping the last reports c_rec.
    try:
        rows = [{"record_id": "b_rec", "x": 3, "label": "1"}, {"record_id": "a_rec", "x": 3, "label": "1"},
                {"record_id": "c_rec", "x": 3, "label": "1"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 2.0}, 0.0, 0.5,
                         state=INERT_STATE, calibration=IDENTITY_CALIBRATION)
        if derive(*paths)["top_record"]["record_id"] != "a_rec":
            return False
        return _fresh_matches(workspace, paths, "top_record")
    except Exception:
        return False


@criterion(description="borderline ids are those within the margin band around the threshold")
def fresh_borderline_band_selection(workspace: Path) -> bool:
    try:
        rows = [{"record_id": "near", "x": 0.08, "label": "1"}, {"record_id": "far", "x": 0.5, "label": "1"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.0, 0.5, margin=0.05)
        if derive(*paths)["borderline_record_ids"] != ["near"]:
            return False
        return _fresh_matches(workspace, paths, "borderline_record_ids")
    except Exception:
        return False


@criterion(description="the borderline band keeps a record inside it and drops one exactly on the edge")
def fresh_borderline_exact_boundary_is_excluded(workspace: Path) -> bool:
    # edge scores 0.5, which sits exactly one margin away from the 0.375 threshold, so
    # the strict comparison drops it while inside at 0.450166 stays. Reading the rule
    # as "at most one margin away" would report both ids.
    try:
        rows = [{"record_id": "edge", "x": 0, "label": "1"}, {"record_id": "inside", "x": -0.2625, "label": "0"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.1, 0.375, margin=0.125)
        if derive(*paths)["borderline_record_ids"] != ["inside"]:
            return False
        return _fresh_matches(workspace, paths, "borderline_record_ids")
    except Exception:
        return False


@criterion(description="borderline ids come back sorted rather than in file order")
def fresh_borderline_ids_are_sorted(workspace: Path) -> bool:
    # Both records qualify and the file lists them in descending id order, so
    # emitting file order would report ["z_rec", "a_rec"].
    try:
        rows = [{"record_id": "z_rec", "x": 0.02, "label": "1"}, {"record_id": "a_rec", "x": -0.04, "label": "0"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.0, 0.5, margin=0.05)
        if derive(*paths)["borderline_record_ids"] != ["a_rec", "z_rec"]:
            return False
        return _fresh_matches(workspace, paths, "borderline_record_ids")
    except Exception:
        return False


@criterion(description="the threshold decision compares the rounded probability, not the raw one")
def fresh_threshold_uses_rounded_probability(workspace: Path) -> bool:
    try:
        paths = _fixture([{"record_id": "a", "x": 0, "label": "1"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0},
                         0.09375, 0.5, prob_decimals=2)
        if derive(*paths)["positive_count"] != 1:
            return False
        return _fresh_matches(workspace, paths, "positive_count")
    except Exception:
        return False


@criterion(description="borderline membership uses the rounded probability, not the raw one")
def fresh_borderline_uses_rounded_probability(workspace: Path) -> bool:
    # Identity calibration: the raw probability 0.497500 is 0.0025 from the
    # threshold, outside a 0.001 margin, but it rounds to 0.50 at prob_decimals 2,
    # which sits on the threshold and inside the band.
    try:
        paths = _fixture([{"record_id": "in", "x": 0, "label": "1"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0},
                         -0.01, 0.5, prob_decimals=2, margin=0.001, state=INERT_STATE, calibration=IDENTITY_CALIBRATION)
        if derive(*paths)["borderline_record_ids"] != ["in"]:
            return False
        return _fresh_matches(workspace, paths, "borderline_record_ids")
    except Exception:
        return False


@criterion(description="the top record is selected on rounded probability with id tie-breaking")
def fresh_top_record_uses_rounded_probability(workspace: Path) -> bool:
    try:
        rows = [{"record_id": "a", "x": 1.617, "label": "1"}, {"record_id": "b", "x": 1.631, "label": "1"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=1)
        if derive(*paths)["top_record"] != {"probability": 0.8, "record_id": "a"}:
            return False
        return _fresh_matches(workspace, paths, "top_record")
    except Exception:
        return False


@criterion(description="a feature contribution on a rounding tie rounds half-to-even at metric_decimals")
def fresh_contribution_half_even_at_metric_decimals(workspace: Path) -> bool:
    try:
        paths = _fixture([{"record_id": "a", "x": 1, "label": "1"}], {"x": _num(0.0, 8.0, 0.0)}, {}, {"x": 1.0},
                         0.0, 0.5, metric_decimals=2)
        if derive(*paths)["feature_contributions"]["x"] != 0.12:
            return False
        return _fresh_matches(workspace, paths, "feature_contributions", "x")
    except Exception:
        return False


@criterion(description="mean_probability rounds at prob_decimals, not metric_decimals")
def fresh_mean_probability_uses_prob_decimals(workspace: Path) -> bool:
    # Inert state and identity calibration: the rounded probabilities 0.12 and 0.13
    # average to exactly 0.125, which reports as 0.12 at prob_decimals 2 and as
    # 0.125 at metric_decimals 4.
    try:
        rows = [{"record_id": "a", "x": -2.0, "label": "1"}, {"record_id": "b", "x": -1.9, "label": "1"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=2,
                         metric_decimals=4, state=INERT_STATE, calibration=IDENTITY_CALIBRATION)
        if derive(*paths)["mean_probability"] != 0.12:
            return False
        return _fresh_matches(workspace, paths, "mean_probability")
    except Exception:
        return False


@criterion(description="mean_probability averages the rounded probabilities and rounds half-to-even")
def fresh_mean_probability_averages_rounded_values(workspace: Path) -> bool:
    # Neither raw probability sits on a tie, so per-record rounding is not in
    # play here: they round to 0.0 and 1.0, whose mean is exactly 0.5, and
    # half-to-even at prob_decimals=0 gives 0.0. Averaging the raw 0.299433 and
    # 0.880797 gives 0.590115 and reports 1.0, and half-up on the mean of the
    # rounded values also reports 1.0. metric_decimals matches prob_decimals so
    # that precision selection is graded only by the neighbouring check.
    try:
        rows = [{"record_id": "a", "x": -0.85, "label": "1"}, {"record_id": "b", "x": 2, "label": "1"}]
        paths = _fixture(rows, {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=0, metric_decimals=0)
        if derive(*paths)["mean_probability"] != 0.0:
            return False
        return _fresh_matches(workspace, paths, "mean_probability")
    except Exception:
        return False


@criterion(description="the running state is replayed over the records in file order and rounded at state_decimals")
def fresh_carry_state_replays_in_file_order(workspace: Path) -> bool:
    # Three identical records: without the carry every probability is the same, so a
    # solver that scores records in isolation reports one value three times. The same
    # records in reverse file order must also produce a different report, which
    # catches a solver that carries state but replays it in sorted order. The last
    # leg declares its own alpha, lambda and a coarse state_decimals, so the state
    # settings must be read from model.json and the state rounding is decisive.
    # The tie leg uses alpha 1/2, lambda 1 and state_decimals 1: the first record
    # scores 0.5, so the state advances to exactly 0.25, which half-to-even holds
    # at 0.2 while half-up gives 0.3 and an unrounded state keeps 0.25; the second
    # record's score, and so the mean, tells the three apart.
    try:
        numeric = {"x": _num(0.0, 1.0, 0.0)}
        same = [{"record_id": "c%d" % i, "x": 1.5, "label": "1"} for i in range(1, 4)]
        forward = [{"record_id": "a", "x": 2.0, "label": "1"},
                   {"record_id": "b", "x": -1.0, "label": "0"},
                   {"record_id": "c", "x": 0.5, "label": "1"}]
        declared = {"alpha_num": 2, "alpha_den": 5, "lambda_num": 3, "lambda_den": 4}
        tie_state = {"alpha_num": 1, "alpha_den": 2, "lambda_num": 1, "lambda_den": 1}
        pair = [{"record_id": "t1", "x": 0.5, "label": "1"}, {"record_id": "t2", "x": 0.5, "label": "0"}]
        base = _fixture(same, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6)
        fwd = _fixture(forward, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6)
        rev = _fixture(list(reversed(forward)), numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6)
        coarse = _fixture(same, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6,
                          state=dict(declared, state_decimals=1))
        fine = _fixture(same, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6,
                        state=dict(declared, state_decimals=6))
        coarse_default = _fixture(same, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6,
                                  state=dict(DEFAULT_STATE, state_decimals=1))
        tie = _fixture(pair, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6,
                       state=dict(tie_state, state_decimals=1))
        tie_unrounded = _fixture(pair, numeric, {}, {"x": 1.0}, 0.0, 0.5, prob_decimals=6,
                                 state=dict(tie_state, state_decimals=6))
        exp_base, exp_fwd, exp_rev, exp_coarse = derive(*base), derive(*fwd), derive(*rev), derive(*coarse)
        exp_tie = derive(*tie)
        if exp_base["mean_probability"] == exp_base["top_record"]["probability"]:
            return False
        if exp_fwd["mean_probability"] == exp_rev["mean_probability"]:
            return False
        if exp_coarse["mean_probability"] in (derive(*fine)["mean_probability"],
                                              derive(*coarse_default)["mean_probability"]):
            return False
        if exp_tie["mean_probability"] == derive(*tie_unrounded)["mean_probability"]:
            return False
        for paths, expected in ((base, exp_base), (fwd, exp_fwd), (rev, exp_rev), (coarse, exp_coarse),
                                (tie, exp_tie)):
            out = _run(workspace, paths)
            if out is None or not _same(_field(out, "mean_probability"), expected["mean_probability"]):
                return False
        return True
    except Exception:
        return False


@criterion(description="a numeric feature is held to its clip bounds before feeding its hinge terms")
def fresh_hinge_basis_and_winsorization(workspace: Path) -> bool:
    # The raw value sits far above clip_hi, so the clipped value decides both the
    # linear term and every hinge above a knot. A solver that skips the clip or
    # the hinge expansion reports a different contribution for each key.
    try:
        numeric = {"x": _num(0.0, 1.0, 0.0, -1.25, 1.25, [-0.75, 0.5])}
        weights = {"x": 2.0, "x|1": 3.0, "x|2": 5.0}
        paths = _fixture([{"record_id": "a", "x": 7.0, "label": "1"}], numeric, {}, weights, 0.0, 0.5, metric_decimals=6)
        if derive(*paths)["feature_contributions"] != {"x": 2.5, "x|1": 6.0, "x|2": 3.75}:
            return False
        return _fresh_matches(workspace, paths, "feature_contributions")
    except Exception:
        return False


@criterion(description="the score is divided by the temperature before the prior shift is added")
def fresh_calibration_temperature_and_prior_shift(workspace: Path) -> bool:
    # 2.24 / 1.6 - 0.15 is 1.25, whose logistic is 0.777300. Multiplying by the
    # temperature, or adding the shift before dividing, lands elsewhere.
    try:
        paths = _fixture([{"record_id": "a", "x": 2.24, "label": "1"}], {"x": _num(0.0, 1.0, 0.0)}, {}, {"x": 1.0},
                         0.0, 0.5, prob_decimals=6,
                         calibration={"temperature_milli": 1600, "prior_shift_micro": -150000})
        if derive(*paths)["top_record"]["probability"] != 0.7773:
            return False
        return _fresh_matches(workspace, paths, "top_record")
    except Exception:
        return False


@criterion(description="the delivered script returns one report for two batches whose content differs")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened: the script hands back the same report for two
    # different batches, which is what an embedded answer for the shipped inputs
    # looks like from outside. The probe watches behaviour rather than source text.
    try:
        return _content_blind(workspace)
    except Exception:
        return False


def _dynamic_import_target(call):
    """The module a runtime import call names, so a dependency pulled in through
    __import__ or importlib is read the same way as an import statement."""
    name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
    if name not in ("__import__", "import_module"):
        return None
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


@criterion(description="a delivered Python file imports a module outside the standard library")
def negative_third_party_dependency(workspace: Path) -> bool:
    # Holds when the cheat happened: some import names a non-stdlib, non-local module.
    try:
        root = Path(workspace)
        stdlib = sys.stdlib_module_names
        local = {p.stem for p in root.glob("*.py")} | {p.name for p in root.glob("*") if p.is_dir() and (p / "__init__.py").is_file()}
        for path in sorted(root.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                elif isinstance(node, ast.Call) and _dynamic_import_target(node):
                    names = [_dynamic_import_target(node)]
                for full in names:
                    top = full.split(".")[0]
                    if top not in stdlib and top not in local:
                        return True
        return False
    except Exception:
        return False


@criterion(description="two runs of the script on identical inputs disagree byte for byte")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened: both runs succeed and their bytes differ.
    try:
        paths = write_case(CHALLENGE_SEED, 30)
        first = _run_raw(workspace, paths)
        second = _run_raw(workspace, paths)
        return first is not None and second is not None and first != second
    except Exception:
        return False


@criterion(description="renaming the four input files changes the report the script writes")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Holds when the cheat happened: the file names, rather than the content, move
    # the report. Each layout runs twice and the content probe runs first, so a
    # script that repeats one memorised answer stays with the embedded-answer
    # detector and an unstable one stays with the determinism detector; one
    # mistake therefore costs one penalty.
    try:
        paths = write_case(SAMPLE_SEED, 24)
        alt = _input_dir("lbs-name-b-")
        renamed = []
        for src, name in zip(paths, ["batch.csv", "coeffs.json", "columns.json", "rules.json"]):
            dst = alt / name
            dst.write_text(Path(src).read_text(encoding="utf-8"), encoding="utf-8")
            dst.chmod(0o644)
            renamed.append(dst)
        first_a = _run_raw(workspace, paths)
        second_a = _run_raw(workspace, paths)
        first_b = _run_raw(workspace, renamed)
        second_b = _run_raw(workspace, renamed)
        if None in (first_a, second_a, first_b, second_b):
            return False
        stable = first_a == second_a and first_b == second_b
        return stable and not _content_blind(workspace) and first_a != first_b
    except Exception:
        return False


criteria.report_artifact_exists_and_is_json(weight=1)
criteria.report_schema_is_exact(weight=1)
criteria.visible_report_matches_independent_derivation(weight=5)
criteria.report_canonical_serialization(weight=1)
criteria.hidden_full_report_matches_fresh_derivation(weight=5)
criteria.fresh_report_canonical_serialization(weight=1)
criteria.fresh_banker_rounding_precision(weight=1)
criteria.fresh_zero_variance_feature_zeroed(weight=1)
criteria.fresh_unseen_category_contributes_zero(weight=1)
criteria.fresh_missing_numeric_imputed_to_declared_value(weight=1)
criteria.fresh_sigmoid_extreme_scores_stable(weight=1)
criteria.fresh_zero_denominator_ratios_are_zero(weight=1)
criteria.fresh_empty_batch_report_is_zero_filled(weight=1)
criteria.fresh_positive_label_from_policy(weight=1)
criteria.fresh_probability_precision_from_model(weight=1)
criteria.fresh_probability_half_even_tie_at_prob_decimals(weight=1)
criteria.fresh_threshold_tie_counts_as_positive(weight=1)
criteria.fresh_feature_contributions_are_corpus_sums(weight=1)
criteria.fresh_top_record_tiebreak_smallest_id(weight=1)
criteria.fresh_borderline_band_selection(weight=1)
criteria.fresh_borderline_exact_boundary_is_excluded(weight=1)
criteria.fresh_borderline_ids_are_sorted(weight=1)
criteria.fresh_threshold_uses_rounded_probability(weight=1)
criteria.fresh_borderline_uses_rounded_probability(weight=1)
criteria.fresh_top_record_uses_rounded_probability(weight=1)
criteria.fresh_contribution_half_even_at_metric_decimals(weight=1)
criteria.fresh_mean_probability_uses_prob_decimals(weight=1)
criteria.fresh_mean_probability_averages_rounded_values(weight=1)
criteria.fresh_carry_state_replays_in_file_order(weight=5)
criteria.fresh_hinge_basis_and_winsorization(weight=5)
criteria.fresh_calibration_temperature_and_prior_shift(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
