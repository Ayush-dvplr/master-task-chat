#!/usr/bin/env python3
"""SNLSQ geodetic sensor-network adjustment.

Reads an extract laid out as described by schema.md from DATA_DIR and writes
the derived reports into OUT_DIR.  All load-bearing arithmetic is exact
rational arithmetic (fractions.Fraction); only the rendering step rounds.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction

STATION_AXES = ("x", "y")
SHARD_KEYS = (
    "revision",
    "length_unit",
    "angle_unit",
    "sigma_stored_as",
    "sign_flip_rev",
    "azimuth_wrap",
    "transpose_ids",
)
GON_FULL = Fraction(400)
GON_HALF = Fraction(200)


# --------------------------------------------------------------------------
# exact rounding / rendering helpers
# --------------------------------------------------------------------------
def round_half_even(value):
    """Round an exact Fraction to the nearest integer, ties to even."""
    num, den = value.numerator, value.denominator
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 == 1):
        q += 1
    return q


def quantize(value, places):
    """Exact rational `value` rounded half-even to `places` decimals."""
    scale = 10 ** places
    return Fraction(round_half_even(value * scale), scale)


def fmt(value, places):
    """Render an exact Fraction with `places` decimals, ties to even."""
    scaled = round_half_even(value * 10 ** places)
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).rjust(places + 1, "0")
    if places == 0:
        return sign + digits
    return "%s%s.%s" % (sign, digits[:-places], digits[-places:])


def micrometres(value):
    """Signed integer micrometres of an exact base-unit value."""
    return round_half_even(value * 1000000)


# --------------------------------------------------------------------------
# tabular readers
# --------------------------------------------------------------------------
def read_table(path, delimiter):
    with open(path, "r", encoding="utf-8") as handle:
        body = [line for line in handle if not line.lstrip().startswith("#")]
    return list(csv.DictReader(io.StringIO("".join(body)), delimiter=delimiter))


def delimiter_for(path):
    ext = os.path.splitext(path)[1].lower()
    return {".csv": ",", ".tsv": "\t", ".psv": "|", ".txt": ","}.get(ext, ",")


def read_shard_header(path):
    tokens = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.lstrip().startswith("#"):
                break
            for key, value in re.findall(r"(\w+)=(\S+)", line):
                if key in SHARD_KEYS:
                    tokens[key] = value
    return tokens


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


# --------------------------------------------------------------------------
# xlsx control workbook
# --------------------------------------------------------------------------
def read_workbook(path):
    """Return {sheet_name: {label: value}} for a flat label/value workbook."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

    sheets = {}
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(ns + "si"):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
        book = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {}
        for rel in rels:
            target[rel.get("Id")] = "xl/" + rel.get("Target").lstrip("/")
        for sheet in book.find(ns + "sheets"):
            name = sheet.get("name")
            part = target[sheet.get(rel_ns + "id")]
            grid = {}
            data = ET.fromstring(zf.read(part))
            for row in data.iter(ns + "row"):
                cells = {}
                for cell in row.findall(ns + "c"):
                    col = re.match(r"([A-Z]+)", cell.get("r")).group(1)
                    if cell.get("t") == "inlineStr":
                        node = cell.find(ns + "is")
                        text = "".join(t.text or "" for t in node.iter(ns + "t"))
                    else:
                        node = cell.find(ns + "v")
                        text = "" if node is None else (node.text or "")
                        if cell.get("t") == "s" and text != "":
                            text = shared[int(text)]
                    cells[col] = text.strip()
                label = cells.get("A", "")
                if label and cells.get("B", "") != "":
                    grid.setdefault(label, cells["B"])
            sheets[name] = grid
    return sheets


def workbook_value(sheets, label):
    """Fetch a control cell, preferring the 'datum' sheet."""
    order = [name for name in sheets if name == "datum"]
    order += [name for name in sheets if name != "datum"]
    for name in order:
        if label in sheets[name]:
            return sheets[name][label]
    raise KeyError(label)


# --------------------------------------------------------------------------
# extract loading
# --------------------------------------------------------------------------
class Observation(object):
    __slots__ = (
        "obs_id",
        "kind",
        "shard",
        "revision",
        "partials",
        "epoch",
        "region",
        "misclosure",
        "variance",
        "base_weight",
        "stations",
        "primary_station",
    )


def load_unit_factors(data_dir):
    factors = {}
    rows = read_table(os.path.join(data_dir, "reference_unit_registry.csv"), ",")
    for row in rows:
        if row.get("status") != "authoritative":
            continue
        if row.get("unit_scope") == "informational":
            continue
        key = (row["unit"], row["quantity"])
        factors[key] = Fraction(int(row["factor_num"]), int(row["factor_den"]))
    return factors


def load_stations(data_dir):
    rows = read_table(os.path.join(data_dir, "station_registry.csv"), ",")
    stations = {}
    for row in rows:
        if row.get("mark_status") == "abandoned":
            continue
        name = row["station"]
        if name in stations:
            continue
        stations[name] = {
            "ordinal": int(row["ordinal"]),
            "mount": row["mount"],
            "centring_mm": Fraction(row["centring_mm"]),
        }
    return stations


def restore_obs_id(raw, epoch, transpose):
    if transpose and str(epoch).strip() == "2":
        return raw[-3:] + raw[:-3]
    return raw


def parse_partials(text):
    partials = {}
    for token in str(text).split(";"):
        token = token.strip()
        if not token:
            continue
        index, ratio = token.split(":")
        num, den = ratio.split("/")
        index = int(index)
        partials[index] = partials.get(index, Fraction(0)) + Fraction(
            int(num), int(den)
        )
    return {i: c for i, c in partials.items() if c != 0}


def shard_files(data_dir):
    return sorted(
        name
        for name in os.listdir(data_dir)
        if name.startswith("obs_source_district_")
    )


def read_shard(data_dir, name):
    """Return (list of normalized raw rows, shard metadata) for one shard."""
    path = os.path.join(data_dir, name)
    if name.lower().endswith((".jsonl", ".ndjson")):
        meta = None
        rows = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if meta is None and "id" not in obj:
                    meta = obj
                    continue
                rows.append(
                    {
                        "obs_id": obj["id"],
                        "kind": obj["k"],
                        "observed_value": obj["v"],
                        "computed_nominal": obj["c"],
                        "apriori_sigma": obj["s"],
                        "unit": obj["u"],
                        "sigma_kind": obj["sk"],
                        "dir": obj["d"],
                        "partials": obj["A"],
                        "epoch": obj["e"],
                        "region": obj["reg"],
                    }
                )
        return rows, meta
    return read_table(path, delimiter_for(path)), read_shard_header(path)


def build_observations(data_dir, factors, stations):
    by_ordinal = {info["ordinal"]: name for name, info in stations.items()}
    candidates = {}
    superseded = []
    for name in shard_files(data_dir):
        rows, meta = read_shard(data_dir, name)
        revision = int(meta["revision"])
        transpose = as_bool(meta.get("transpose_ids", False))
        wrap = as_bool(meta.get("azimuth_wrap", False))
        for row in rows:
            obs = Observation()
            obs.shard = name
            obs.revision = revision
            obs.obs_id = restore_obs_id(
                str(row["obs_id"]).strip(), row["epoch"], transpose
            )
            obs.kind = str(row["kind"]).strip()
            obs.epoch = int(str(row["epoch"]).strip())
            obs.region = str(row["region"]).strip()
            obs.partials = parse_partials(row["partials"])
            quantity = "length" if obs.kind == "length" else "angle"
            factor = factors[(str(row["unit"]).strip(), quantity)]

            value = Fraction(str(row["observed_value"]).strip()) * factor
            nominal = Fraction(str(row["computed_nominal"]).strip()) * factor
            if str(row["dir"]).strip().upper() == "R":
                value = -value
                nominal = -nominal
            if obs.kind == "angle" and wrap:
                value = value % GON_FULL
                nominal = nominal % GON_FULL
            misclosure = value - nominal
            if obs.kind == "angle":
                misclosure = misclosure % GON_FULL
                if misclosure > GON_HALF:
                    misclosure -= GON_FULL
            obs.misclosure = misclosure

            sigma = Fraction(str(row["apriori_sigma"]).strip())
            if str(row["sigma_kind"]).strip() == "stddev":
                variance = (sigma * factor) ** 2
            else:
                variance = sigma * factor * factor

            obs.stations = sorted({index // 2 for index in obs.partials})
            if obs.kind == "length":
                for ordinal in obs.stations:
                    info = stations[by_ordinal[ordinal]]
                    if info["mount"] == "tripod":
                        variance += (info["centring_mm"] / 1000) ** 2
            obs.variance = variance
            obs.primary_station = obs.stations[0]

            previous = candidates.get(obs.obs_id)
            if previous is None:
                candidates[obs.obs_id] = obs
                continue
            if obs.revision > previous.revision:
                candidates[obs.obs_id] = obs
                kept_shard, dropped_shard = obs.shard, previous.shard
            else:
                kept_shard, dropped_shard = previous.shard, obs.shard
            superseded.append(
                {
                    "obs_id": obs.obs_id,
                    "kept_shard": kept_shard,
                    "superseded_shard": dropped_shard,
                }
            )
    superseded.sort(key=lambda r: (r["obs_id"], r["superseded_shard"]))
    return candidates, superseded


def load_sessions(data_dir):
    path = os.path.join(data_dir, "session_correlation.csv")
    sessions = []
    for row in read_table(path, ","):
        if row.get("status") != "authoritative":
            continue
        sessions.append(
            {
                "session_id": row["session_id"],
                "a": row["member_a_obs_id"].strip(),
                "b": row["member_b_obs_id"].strip(),
                "cov": Fraction(int(row["cov_num"]), int(row["cov_den"])),
            }
        )
    return sessions


# --------------------------------------------------------------------------
# linear algebra (exact)
# --------------------------------------------------------------------------
def solve_exact(matrix, rhs):
    size = len(rhs)
    aug = [list(matrix[i]) + [rhs[i]] for i in range(size)]
    for col in range(size):
        pivot = None
        for row in range(col, size):
            if aug[row][col] != 0:
                pivot = row
                break
        if pivot is None:
            raise ValueError("singular normal matrix at column %d" % col)
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        prow = aug[col]
        inv = Fraction(1) / prow[col]
        for j in range(col, size + 1):
            prow[j] = prow[j] * inv
        for row in range(size):
            if row == col:
                continue
            factor = aug[row][col]
            if factor == 0:
                continue
            arow = aug[row]
            for j in range(col, size + 1):
                arow[j] -= factor * prow[j]
    return [aug[i][size] for i in range(size)]


# --------------------------------------------------------------------------
# adjustment stage
# --------------------------------------------------------------------------
class Stage(object):
    """One weighted-least-squares solve with robust IRLS reweighting."""

    def __init__(self, observations, sessions, n_unknowns, places, k_squared,
                 iterations):
        self.obs = observations
        self.index = {o.obs_id: i for i, o in enumerate(observations)}
        self.n = len(observations)
        self.n_unknowns = n_unknowns
        self.places = places
        self.k_squared = k_squared
        self.iterations = iterations
        self.blocks = []
        self.member_of = {}
        for session in sessions:
            if session["a"] in self.index and session["b"] in self.index:
                ia, ib = self.index[session["a"]], self.index[session["b"]]
                var_a = observations[ia].variance
                var_b = observations[ib].variance
                cov = session["cov"]
                det = var_a * var_b - cov * cov
                block = {
                    "ia": ia,
                    "ib": ib,
                    "w11": quantize(var_b / det, places),
                    "w22": quantize(var_a / det, places),
                    "w12": quantize(-cov / det, places),
                }
                self.blocks.append(block)
                self.member_of[ia] = block
                self.member_of[ib] = block
        self.free = [i for i in range(self.n) if i not in self.member_of]

    def assemble(self, weights):
        size = self.n_unknowns
        normal = [[Fraction(0)] * size for _ in range(size)]
        rhs = [Fraction(0)] * size
        for i in self.free:
            obs = self.obs[i]
            weight = weights[i]
            if weight == 0:
                continue
            items = list(obs.partials.items())
            weighted_l = weight * obs.misclosure
            for col, coeff in items:
                wc = weight * coeff
                row = normal[col]
                for col2, coeff2 in items:
                    row[col2] += wc * coeff2
                rhs[col] += coeff * weighted_l
        for block in self.blocks:
            obs_a = self.obs[block["ia"]]
            obs_b = self.obs[block["ib"]]
            pa = list(obs_a.partials.items())
            pb = list(obs_b.partials.items())
            w11, w12, w22 = block["w11"], block["w12"], block["w22"]
            for col, ca in pa:
                row = normal[col]
                for col2, ca2 in pa:
                    row[col2] += w11 * ca * ca2
                for col2, cb2 in pb:
                    row[col2] += w12 * ca * cb2
            for col, cb in pb:
                row = normal[col]
                for col2, cb2 in pb:
                    row[col2] += w22 * cb * cb2
                for col2, ca2 in pa:
                    row[col2] += w12 * cb * ca2
            ta = w11 * obs_a.misclosure + w12 * obs_b.misclosure
            tb = w12 * obs_a.misclosure + w22 * obs_b.misclosure
            for col, ca in pa:
                rhs[col] += ca * ta
            for col, cb in pb:
                rhs[col] += cb * tb
        return normal, rhs

    def residuals(self, solution):
        out = []
        for obs in self.obs:
            total = Fraction(0)
            for col, coeff in obs.partials.items():
                if solution[col]:
                    total += coeff * solution[col]
            out.append(total - obs.misclosure)
        return out

    def base_weights(self):
        return [obs.base_weight for obs in self.obs]

    def reweight(self, residuals):
        weights = self.base_weights()
        flags = [False] * self.n
        for i in self.free:
            base = weights[i]
            stat = residuals[i] * residuals[i] * base
            if stat > self.k_squared:
                weights[i] = quantize(base * self.k_squared / stat, self.places)
                flags[i] = True
        return weights, flags

    def run(self):
        weights = self.base_weights()
        flags = [False] * self.n
        normal, rhs = self.assemble(weights)
        solution = solve_exact(normal, rhs)
        for _ in range(self.iterations):
            weights, flags = self.reweight(self.residuals(solution))
            normal, rhs = self.assemble(weights)
            solution = solve_exact(normal, rhs)
        return {
            "solution": solution,
            "residuals": self.residuals(solution),
            "weights": weights,
            "flags": flags,
            "normal": normal,
        }

    def quadratic_form(self, residuals, weights):
        total = Fraction(0)
        for i in self.free:
            total += weights[i] * residuals[i] * residuals[i]
        for block in self.blocks:
            va = residuals[block["ia"]]
            vb = residuals[block["ib"]]
            total += block["w11"] * va * va
            total += 2 * block["w12"] * va * vb
            total += block["w22"] * vb * vb
        return total

    def reported_weight(self, i, weights):
        block = self.member_of.get(i)
        if block is None:
            return weights[i]
        return block["w11"] if block["ia"] == i else block["w22"]


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------
def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def read_policy(path):
    policy = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            policy[key.strip()] = value.strip()
    return policy


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    factors = load_unit_factors(data_dir)
    stations = load_stations(data_dir)
    station_by_ordinal = {info["ordinal"]: name for name, info in stations.items()}
    labels = []
    for ordinal in sorted(station_by_ordinal):
        for axis in STATION_AXES:
            labels.append("%s.%s" % (station_by_ordinal[ordinal], axis))
    n_unknowns = len(labels)

    policy = read_policy(os.path.join(data_dir, "iteration_policy.yaml"))
    iterations = int(policy["irls_iterations"])
    places = int(policy["weight_quant_decimal_places"])

    sheets = read_workbook(
        os.path.join(data_dir, "adjustment_control_workbook.xlsx")
    )
    u_constrained = int(workbook_value(sheets, "u_constrained"))
    tuning_k = Fraction(workbook_value(sheets, "tuning_k"))
    blunder_crit = Fraction(workbook_value(sheets, "blunder_crit"))
    origin_index = int(workbook_value(sheets, "datum_origin_station"))
    origin_station = station_by_ordinal[origin_index]
    k_squared = tuning_k * tuning_k
    crit_squared = blunder_crit * blunder_crit

    candidates, superseded = build_observations(data_dir, factors, stations)
    sessions = load_sessions(data_dir)
    for obs in candidates.values():
        obs.base_weight = quantize(Fraction(1) / obs.variance, places)

    all_obs = [candidates[key] for key in sorted(candidates)]

    stage1 = Stage(all_obs, sessions, n_unknowns, places, k_squared, iterations)
    result1 = stage1.run()
    blunders = sorted(
        obs.obs_id
        for i, obs in enumerate(all_obs)
        if result1["residuals"][i] ** 2 * obs.base_weight > crit_squared
    )
    removed = set(blunders)

    kept = [obs for obs in all_obs if obs.obs_id not in removed]
    stage2 = Stage(kept, sessions, n_unknowns, places, k_squared, iterations)
    result2 = stage2.run()

    solution = result2["solution"]
    residuals = result2["residuals"]
    weights = result2["weights"]
    flags = result2["flags"]
    n_obs = len(kept)
    dof = n_obs - u_constrained
    vtpv = stage2.quadratic_form(residuals, weights)
    sigma0_sq = vtpv / dof

    shift_x = solution[2 * origin_index]
    shift_y = solution[2 * origin_index + 1]
    shifted = list(solution)
    for ordinal in station_by_ordinal:
        shifted[2 * ordinal] -= shift_x
        shifted[2 * ordinal + 1] -= shift_y

    bounds = {
        int(row["dof"]): Fraction(int(row["center_num"]), int(row["center_den"]))
        for row in read_table(
            os.path.join(data_dir, "chi_square_bounds_table.csv"), ","
        )
    }
    center = bounds[dof]
    acc_lo = center - Fraction(1, 2)
    acc_hi = center + Fraction(1, 2)
    if vtpv < acc_lo:
        verdict = "REJECT_LOW"
    elif vtpv > acc_hi:
        verdict = "REJECT_HIGH"
    else:
        verdict = "PASS"

    downweighted = sorted(kept[i].obs_id for i in range(n_obs) if flags[i])

    unknown_strings = {labels[i]: fmt(shifted[i], 10) for i in range(n_unknowns)}
    unknown_micro = {labels[i]: micrometres(shifted[i]) for i in range(n_unknowns)}

    write_json(
        os.path.join(out_dir, "adjusted_state.json"),
        {
            "unknowns": unknown_strings,
            "unknowns_micrometres": unknown_micro,
            "n_observations": n_obs,
            "u_constrained": u_constrained,
            "degrees_of_freedom": dof,
            "variance_of_unit_weight": fmt(sigma0_sq, 10),
            "quadratic_form_vtpv": fmt(vtpv, 10),
            "tuning_constant_k": fmt(tuning_k, 6),
            "blunder_critical_value": fmt(blunder_crit, 6),
            "blunders_removed": len(blunders),
            "datum_origin_station": origin_station,
            "model_test_verdict": verdict,
        },
    )

    write_json(
        os.path.join(out_dir, "model_test.json"),
        {
            "degrees_of_freedom": dof,
            "quadratic_form_vtpv": fmt(vtpv, 10),
            "acceptance_low": fmt(acc_lo, 6),
            "acceptance_high": fmt(acc_hi, 6),
            "verdict": verdict,
            "passed": verdict == "PASS",
        },
    )

    write_json(
        os.path.join(out_dir, "downweighted_observations.json"),
        {"count": len(downweighted), "obs_ids": downweighted},
    )

    write_json(
        os.path.join(out_dir, "removed_blunders.json"),
        {
            "count": len(blunders),
            "obs_ids": blunders,
            "critical_value": fmt(blunder_crit, 6),
        },
    )

    write_json(
        os.path.join(out_dir, "datum_transformation.json"),
        {
            "origin_station": origin_station,
            "origin_station_index": origin_index,
            "free_corrections_micrometres": {
                labels[i]: micrometres(solution[i]) for i in range(n_unknowns)
            },
            "shifted_corrections_micrometres": unknown_micro,
        },
    )

    best_index = None
    best_abs = None
    for i in range(n_obs):
        value = abs(residuals[i])
        if best_abs is None or value > best_abs:
            best_abs, best_index = value, i
    write_json(
        os.path.join(out_dir, "residual_summary.json"),
        {
            "n": n_obs,
            "sum_signed_micrometres": micrometres(sum(residuals, Fraction(0))),
            "max_abs_residual_micrometres": micrometres(best_abs),
            "max_abs_residual_obs_id": kept[best_index].obs_id,
        },
    )

    rows = ["unknown_index,label,correction_metres,correction_micrometres"]
    for i in range(n_unknowns):
        rows.append(
            "%d,%s,%s,%d"
            % (i, labels[i], fmt(shifted[i], 10), micrometres(shifted[i]))
        )
    write_lines(os.path.join(out_dir, "unknowns.csv"), rows)

    rows = ["obs_id,kind,residual_micrometres,downweighted"]
    for i in range(n_obs):
        rows.append(
            "%s,%s,%d,%d"
            % (
                kept[i].obs_id,
                kept[i].kind,
                micrometres(residuals[i]),
                1 if flags[i] else 0,
            )
        )
    write_lines(os.path.join(out_dir, "residuals.csv"), rows)

    rows = ["obs_id\tresidual_micrometres"]
    for i in range(n_obs):
        rows.append("%s\t%d" % (kept[i].obs_id, micrometres(residuals[i])))
    write_lines(os.path.join(out_dir, "residuals.tsv"), rows)

    rows = ["obs_id|weight_num|weight_den"]
    for i in range(n_obs):
        weight = stage2.reported_weight(i, weights)
        rows.append(
            "%s|%d|%d" % (kept[i].obs_id, weight.numerator, weight.denominator)
        )
    write_lines(os.path.join(out_dir, "final_weights.psv"), rows)

    def sum_abs(members):
        return micrometres(sum((abs(residuals[i]) for i in members), Fraction(0)))

    for region in sorted({obs.region for obs in all_obs}):
        members = [i for i in range(n_obs) if kept[i].region == region]
        write_json(
            os.path.join(out_dir, "district_%s.json" % region),
            {
                "district": region,
                "observation_count": len(members),
                "downweighted_count": sum(1 for i in members if flags[i]),
                "sum_abs_residual_micrometres": sum_abs(members),
            },
        )

    campaign_of = {}
    for row in read_table(os.path.join(data_dir, "epoch_campaign_map.csv"), ","):
        campaign_of.setdefault(int(row["epoch"]), row["campaign"])
    for epoch in sorted(set(campaign_of) | {obs.epoch for obs in all_obs}):
        members = [i for i in range(n_obs) if kept[i].epoch == epoch]
        write_json(
            os.path.join(out_dir, "epoch_%d.json" % epoch),
            {
                "epoch": epoch,
                "observation_count": len(members),
                "sum_abs_residual_micrometres": sum_abs(members),
            },
        )

    frame_of_station = {}
    for row in read_table(os.path.join(data_dir, "station_frame_map.csv"), ","):
        frame_of_station.setdefault(row["station"], row["frame"])
    frames = sorted({frame_of_station[name] for name in stations})
    campaigns = sorted(set(campaign_of.values()))
    frame_of_obs = [
        frame_of_station[station_by_ordinal[kept[i].primary_station]]
        for i in range(n_obs)
    ]
    for frame in frames:
        for campaign in campaigns:
            members = [
                i
                for i in range(n_obs)
                if frame_of_obs[i] == frame
                and campaign_of.get(kept[i].epoch) == campaign
            ]
            write_json(
                os.path.join(out_dir, "rollup_%s_%s.json" % (frame, campaign)),
                {
                    "frame": frame,
                    "campaign": campaign,
                    "observation_count": len(members),
                    "downweighted_count": sum(1 for i in members if flags[i]),
                    "sum_abs_residual_micrometres": sum_abs(members),
                },
            )

    trace = sum((result2["normal"][i][i] for i in range(n_unknowns)), Fraction(0))
    write_json(
        os.path.join(out_dir, "normal_matrix_trace.json"),
        {
            "trace_num": trace.numerator,
            "trace_den": trace.denominator,
            "trace_decimal": fmt(trace, 6),
        },
    )

    write_json(
        os.path.join(out_dir, "provenance_summary.json"),
        {
            "control_values_source": "adjustment_control_workbook.xlsx",
            "u_constrained": u_constrained,
            "tuning_constant_k": fmt(tuning_k, 6),
            "blunder_critical_value": fmt(blunder_crit, 6),
            "datum_origin_station": origin_station,
            "superseded_records": superseded,
            "decoys_ignored": [
                "deprecated_precorrection_coords.csv",
                "stale_cached_solution.json",
                "legacy_orientation_offsets.tsv",
                "residual_prior_epoch.tsv",
                "observation_weight_manifest.csv:naive_weight",
                "scale_factor_table.csv",
                "archive_backfill.db",
            ],
        },
    )

    write_lines(
        os.path.join(out_dir, "status.txt"),
        [
            "verdict=%s dof=%d u=%d n=%d blunders_removed=%d datum_origin=%s "
            "sigma0_sq=%s downweighted=%d"
            % (
                verdict,
                dof,
                u_constrained,
                n_obs,
                len(blunders),
                origin_station,
                fmt(sigma0_sq, 10),
                len(downweighted),
            )
        ],
    )

    xml_lines = [
        "<adjustment>",
        "  <verdict>%s</verdict>" % verdict,
        "  <degrees_of_freedom>%d</degrees_of_freedom>" % dof,
        "  <u_constrained>%d</u_constrained>" % u_constrained,
        "  <variance_of_unit_weight>%s</variance_of_unit_weight>"
        % fmt(sigma0_sq, 10),
        "  <unknowns>",
    ]
    for i in range(n_unknowns):
        xml_lines.append(
            '    <unknown label="%s" correction_micrometres="%d"/>'
            % (labels[i], micrometres(shifted[i]))
        )
    xml_lines.append("  </unknowns>")
    xml_lines.append("</adjustment>")
    write_lines(os.path.join(out_dir, "adjustment_report.xml"), xml_lines)

    write_lines(
        os.path.join(out_dir, "adjustment_summary.yaml"),
        [
            "model_test_verdict: %s" % verdict,
            "degrees_of_freedom: %d" % dof,
            "u_constrained: %d" % u_constrained,
            "variance_of_unit_weight: %s" % fmt(sigma0_sq, 10),
            "downweighted_count: %d" % len(downweighted),
            "tuning_constant_k: %s" % fmt(tuning_k, 6),
        ],
    )

    write_lines(
        os.path.join(out_dir, "adjustment_report.md"),
        [
            "# Adjustment Report",
            "",
            "The global model test verdict is %s." % verdict,
            "",
            "- degrees_of_freedom: %d" % dof,
            "- variance_of_unit_weight: %s" % fmt(sigma0_sq, 10),
            "- downweighted_count: %d" % len(downweighted),
            "- tuning_constant_k: %s" % fmt(tuning_k, 6),
            "",
            "Stage-2 observations: %d; constrained components u: %d; "
            "blunders removed: %d; datum origin: %s."
            % (n_obs, u_constrained, len(blunders), origin_station),
        ],
    )

    stream = []
    nd_stream = []
    for i in range(n_obs):
        micro = micrometres(residuals[i])
        stream.append(
            json.dumps(
                {
                    "obs_id": kept[i].obs_id,
                    "kind": kept[i].kind,
                    "residual_micrometres": micro,
                    "downweighted": bool(flags[i]),
                },
                sort_keys=True,
            )
        )
        nd_stream.append(
            json.dumps({"id": kept[i].obs_id, "r": micro}, sort_keys=True)
        )
    write_lines(os.path.join(out_dir, "observation_stream.jsonl"), stream)
    write_lines(os.path.join(out_dir, "observation_stream.ndjson"), nd_stream)

    sys.stderr.write(
        "n=%d u=%d dof=%d blunders=%d downweighted=%d verdict=%s\n"
        % (n_obs, u_constrained, dof, len(blunders), len(downweighted), verdict)
    )
    sys.stderr.write(
        "vtpv=%s sigma0_sq=%s trace=%s\n"
        % (fmt(vtpv, 10), fmt(sigma0_sq, 10), fmt(trace, 6))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
