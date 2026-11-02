#!/usr/bin/env python3
"""SNLSQ geodetic sensor-network adjustment driver.

Reads an extract laid out as described by ``schema.md`` from DATA_DIR and
writes the full report set into OUT_DIR.  All load-bearing arithmetic is exact
rational arithmetic (``fractions.Fraction``); no floating point enters any
reported figure.
"""

import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction

STATION_ORDER = ["ALPHA", "BRAVO", "CIVET", "DELTA", "EAGLE", "FICUS"]
SHARDS = [
    ("obs_source_district_north.csv", ",", "North"),
    ("obs_source_district_south.tsv", "\t", "South"),
    ("obs_source_district_west.psv", "|", "West"),
    ("obs_source_district_east.jsonl", None, "East"),
]
JSONL_FIELDS = {
    "id": "obs_id", "k": "kind", "v": "observed_value", "c": "computed_nominal",
    "s": "apriori_sigma", "u": "unit", "sk": "sigma_kind", "d": "dir",
    "A": "partials", "e": "epoch", "reg": "region",
}
IGNORED_ROW_FLAGS = {
    "status": {"duplicate", "void", "superseded", "retired"},
    "mark_status": {"abandoned"},
    "provenance": {"superseded"},
    "ledger_status": {"void"},
}
FOUR_HUNDRED = Fraction(400)
HALF = Fraction(1, 2)


# --------------------------------------------------------------------------
# exact rounding / rendering
# --------------------------------------------------------------------------

def round_half_even(fr):
    """Round an exact Fraction to the nearest integer, halves to even."""
    floor = fr.numerator // fr.denominator
    rem = fr - floor
    if rem < HALF:
        return floor
    if rem > HALF:
        return floor + 1
    return floor if floor % 2 == 0 else floor + 1


def quantize(fr, places):
    scale = 10 ** places
    return Fraction(round_half_even(fr * scale), scale)


def fmt(fr, places):
    q = round_half_even(Fraction(fr) * 10 ** places)
    sign = "-" if q < 0 else ""
    digits = str(abs(q)).rjust(places + 1, "0")
    if places == 0:
        return sign + digits
    return "%s%s.%s" % (sign, digits[:-places], digits[-places:])


def micro(fr):
    return round_half_even(Fraction(fr) * 1000000)


# --------------------------------------------------------------------------
# small text-format readers
# --------------------------------------------------------------------------

def read_table(path, delim):
    """Return dict rows of a delimited file, skipping '#' comment lines."""
    header = None
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.lstrip().startswith("#"):
                continue
            parts = line.split(delim)
            if header is None:
                header = [p.strip() for p in parts]
                continue
            row = {}
            for i, name in enumerate(header):
                row[name] = parts[i].strip() if i < len(parts) else ""
            rows.append(row)
    return rows


def is_ignored(row):
    for column, bad in IGNORED_ROW_FLAGS.items():
        if row.get(column, "").strip() in bad:
            return True
    return False


def read_header_tokens(path):
    """Collect key=value tokens from the leading '#' comment block."""
    toks = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)=(\S+)", line):
                toks[m.group(1)] = m.group(2)
    return toks


def read_workbook(path, preferred_sheet="datum"):
    """Return {label: value} of an xlsx workbook's label/value cell pairs.

    The preferred sheet is read first so its cells win over any same-named
    label restated on another sheet.
    """
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rels_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    doc_ns = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
              "relationships}")
    cells = {}
    with zipfile.ZipFile(path) as zf:
        members = zf.namelist()
        shared = []
        if "xl/sharedStrings.xml" in members:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(ns + "si"):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))

        targets = {}
        if "xl/_rels/workbook.xml.rels" in members:
            root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in root.findall(rels_ns + "Relationship"):
                targets[rel.get("Id")] = "xl/" + rel.get("Target").lstrip("/")
        sheets = []
        if "xl/workbook.xml" in members:
            root = ET.fromstring(zf.read("xl/workbook.xml"))
            for sheet in root.iter(ns + "sheet"):
                part = targets.get(sheet.get(doc_ns + "id"))
                if part in members:
                    sheets.append((sheet.get("name"), part))
        if not sheets:
            sheets = [(n, n) for n in sorted(members)
                      if n.startswith("xl/worksheets/sheet")]
        sheets.sort(key=lambda s: s[0] != preferred_sheet)

        for _, part in sheets:
            root = ET.fromstring(zf.read(part))
            for row in root.iter(ns + "row"):
                vals = []
                for c in row.findall(ns + "c"):
                    if c.get("t") == "inlineStr":
                        txt = "".join(t.text or "" for t in c.iter(ns + "t"))
                    else:
                        v = c.find(ns + "v")
                        txt = v.text if v is not None and v.text else ""
                        if c.get("t") == "s" and txt.isdigit():
                            txt = shared[int(txt)]
                    vals.append(txt.strip())
                if len(vals) >= 2 and vals[0] and vals[1]:
                    cells.setdefault(vals[0], vals[1])
    return cells


def read_policy(path):
    policy = {}
    if not os.path.exists(path):
        return policy
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            policy[key.strip()] = value.strip()
    return policy


# --------------------------------------------------------------------------
# extract loading
# --------------------------------------------------------------------------

def centring_variances(data_dir):
    """Exact centring variance in m^2 keyed by station ordinal."""
    marks = {}
    for row in read_table(os.path.join(data_dir, "control_mark_register.csv"), ","):
        if is_ignored(row):
            continue
        marks.setdefault(row["mark_id"], row)

    def own_var(row):
        if row.get("mount", "").strip() != "tripod":
            return Fraction(0)
        return (Fraction(row["centring_mm"].strip()) / 1000) ** 2

    cache = {}

    def mark_var(mark_id):
        if mark_id in cache:
            return cache[mark_id]
        row = marks[mark_id]
        cache[mark_id] = Fraction(0)
        var = own_var(row)
        parent = row.get("set_out_from", "").strip()
        if parent:
            var += mark_var(parent)
        cache[mark_id] = var
        return var

    out = {}
    for row in read_table(os.path.join(data_dir, "station_registry.csv"), ","):
        if is_ignored(row):
            continue
        ordinal = int(row["ordinal"])
        var = own_var(row)
        parent = row.get("set_out_from", "").strip()
        if parent:
            var += mark_var(parent)
        out[ordinal] = var
    return out


def unit_factors(data_dir):
    factors = {}
    for row in read_table(os.path.join(data_dir, "reference_unit_registry.csv"), ","):
        if row.get("status") != "authoritative":
            continue
        if row.get("unit_scope") == "informational":
            continue
        key = (row["unit"], row["quantity"])
        factors[key] = Fraction(int(row["factor_num"]), int(row["factor_den"]))
    return factors


def load_shard_rows(data_dir):
    """Every raw shard record paired with its shard's declared conventions."""
    records = []
    for fname, delim, district in SHARDS:
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            continue
        if delim is None:
            meta = None
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if meta is None:
                        meta = obj
                        continue
                    row = {}
                    for short, full in JSONL_FIELDS.items():
                        row[full] = str(obj.get(short, ""))
                    records.append((fname, district, meta, row))
        else:
            toks = read_header_tokens(path)
            for row in read_table(path, delim):
                records.append((fname, district, toks, row))
    return records


def truthy(value):
    return str(value).strip().lower() == "true"


def restore_obs_id(obs_id, epoch, toks):
    if truthy(toks.get("transpose_ids")) and str(epoch).strip() == "2":
        return obs_id[-3:] + obs_id[:-3]
    return obs_id


def parse_partials(text):
    out = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        idx, frac = part.split(":")
        num, den = frac.split("/")
        coeff = Fraction(int(num), int(den))
        if coeff != 0:
            out.append((int(idx), coeff))
    return out


def build_observations(data_dir):
    factors = unit_factors(data_dir)
    centring = centring_variances(data_dir)

    by_id = {}
    for fname, district, toks, row in load_shard_rows(data_dir):
        obs_id = restore_obs_id(row["obs_id"].strip(), row["epoch"], toks)
        rev = int(toks.get("revision", "0"))
        by_id.setdefault(obs_id, []).append((rev, fname, district, toks, row))

    superseded = []
    observations = []
    for obs_id, cands in by_id.items():
        cands.sort(key=lambda c: (-c[0], c[1]))
        kept = cands[0]
        for other in cands[1:]:
            superseded.append({"obs_id": obs_id, "kept_shard": kept[1],
                               "superseded_shard": other[1]})
        _, _, district, toks, row = kept

        kind = row["kind"].strip()
        quantity = "length" if kind == "length" else "angle"
        factor = factors[(row["unit"].strip(), quantity)]

        value = Fraction(row["observed_value"].strip()) * factor
        nominal = Fraction(row["computed_nominal"].strip()) * factor

        if row["dir"].strip().upper() == "R":
            value = -value
            nominal = -nominal

        if kind == "angle" and truthy(toks.get("azimuth_wrap")):
            value -= FOUR_HUNDRED * (value // FOUR_HUNDRED)
            nominal -= FOUR_HUNDRED * (nominal // FOUR_HUNDRED)

        stored_sigma = Fraction(row["apriori_sigma"].strip())
        if row["sigma_kind"].strip() == "stddev":
            variance = (stored_sigma * factor) ** 2
        else:
            variance = stored_sigma * factor * factor

        partials = parse_partials(row["partials"])
        if kind == "length":
            for ordinal in sorted({idx // 2 for idx, _ in partials}):
                variance += centring[ordinal]

        misclosure = value - nominal
        if kind == "angle":
            misclosure -= FOUR_HUNDRED * (misclosure // FOUR_HUNDRED)
            if misclosure > 200:
                misclosure -= FOUR_HUNDRED

        observations.append({
            "obs_id": obs_id,
            "kind": kind,
            "district": district,
            "epoch": int(row["epoch"].strip()),
            "partials": partials,
            "variance": variance,
            "l": misclosure,
            "nominal_metres": nominal,
            "primary_station": min(idx // 2 for idx, _ in partials),
        })

    observations.sort(key=lambda o: o["obs_id"])
    superseded.sort(key=lambda s: (s["obs_id"], s["superseded_shard"]))
    return observations, superseded


# --------------------------------------------------------------------------
# section 8b -- traverse closure absorption
# --------------------------------------------------------------------------

def largest_remainder(total, members):
    """Share ``total`` whole units over (obs_id, basis) by largest remainder."""
    basis_sum = sum(b for _, b in members)
    if basis_sum == 0 or total == 0:
        return {oid: 0 for oid, _ in members}
    shares = {}
    remainders = []
    allocated = 0
    for oid, basis in members:
        exact = Fraction(total * basis, basis_sum)
        base = exact.numerator // exact.denominator
        shares[oid] = base
        allocated += base
        remainders.append((exact - base, oid))
    remainders.sort(key=lambda t: (-t[0], t[1]))
    for i in range(total - allocated):
        shares[remainders[i][1]] += 1
    return shares


def apply_traverse_closure(data_dir, observations):
    path = os.path.join(data_dir, "traverse_closure_register.csv")
    if not os.path.exists(path):
        return
    register = {}
    for row in read_table(path, ","):
        if is_ignored(row):
            continue
        register[(row["district"], int(row["epoch"]))] = (
            int(row["closure_micrometres"]), int(row["floor_micrometres"]))

    groups = {}
    for obs in observations:
        if obs["kind"] != "length":
            continue
        groups.setdefault((obs["district"], obs["epoch"]), []).append(obs)

    for key, members in groups.items():
        if key not in register:
            continue
        closure, floor = register[key]
        magnitude = abs(closure)
        sign = 1 if closure >= 0 else -1
        basis = []
        for obs in members:
            value = abs(obs["nominal_metres"])
            basis.append((obs["obs_id"], value.numerator // value.denominator))
        basis_sum = sum(b for _, b in basis)

        if basis_sum <= magnitude:
            absorbed = dict(basis)
        else:
            shares = largest_remainder(magnitude, basis)
            eligible = [(oid, b) for oid, b in basis if shares[oid] >= floor]
            absorbed = {oid: 0 for oid, _ in basis}
            if eligible:
                absorbed.update(largest_remainder(magnitude, eligible))

        for obs in members:
            amount = absorbed.get(obs["obs_id"], 0)
            if amount:
                obs["l"] -= Fraction(sign * amount, 1000000)


# --------------------------------------------------------------------------
# exact linear algebra
# --------------------------------------------------------------------------

def solve(matrix, rhs):
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = None
        for r in range(col, n):
            if a[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            raise ValueError("singular normal matrix at column %d" % col)
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        prow = a[col]
        inv = 1 / prow[col]
        for j in range(col, n + 1):
            prow[j] *= inv
        for r in range(n):
            if r == col:
                continue
            f = a[r][col]
            if f:
                row = a[r]
                for j in range(col, n + 1):
                    row[j] -= f * prow[j]
    return [a[i][n] for i in range(n)]


# --------------------------------------------------------------------------
# the adjustment
# --------------------------------------------------------------------------

class Adjustment(object):
    """One staged robust (IRLS) weighted least-squares solve."""

    def __init__(self, observations, sessions, n_unknowns, quant, iterations,
                 k_squared):
        self.obs = observations
        self.n = n_unknowns
        self.quant = quant
        self.iterations = iterations
        self.k2 = k_squared
        self.index = {o["obs_id"]: i for i, o in enumerate(observations)}
        self.base = [quantize(1 / o["variance"], quant) for o in observations]

        self.blocks = []
        self.in_session = {}
        for sess in sessions:
            if sess["a"] not in self.index or sess["b"] not in self.index:
                continue
            ia, ib = self.index[sess["a"]], self.index[sess["b"]]
            va = observations[ia]["variance"]
            vb = observations[ib]["variance"]
            cov = sess["cov"]
            det = va * vb - cov * cov
            inv = [[quantize(vb / det, quant), quantize(-cov / det, quant)],
                   [quantize(-cov / det, quant), quantize(va / det, quant)]]
            slot = len(self.blocks)
            self.blocks.append((ia, ib, inv))
            self.in_session[ia] = (slot, 0)
            self.in_session[ib] = (slot, 1)

    def _solve_with(self, weights):
        n = self.n
        N = [[Fraction(0)] * n for _ in range(n)]
        b = [Fraction(0)] * n
        for i, obs in enumerate(self.obs):
            if i in self.in_session:
                continue
            w = weights[i]
            if w == 0:
                continue
            row = obs["partials"]
            wl = w * obs["l"]
            for idx, ci in row:
                b[idx] += wl * ci
                wci = w * ci
                for jdx, cj in row:
                    N[idx][jdx] += wci * cj
        for ia, ib, W in self.blocks:
            rows = (self.obs[ia]["partials"], self.obs[ib]["partials"])
            ls = (self.obs[ia]["l"], self.obs[ib]["l"])
            for p in (0, 1):
                for q in (0, 1):
                    w = W[p][q]
                    if w == 0:
                        continue
                    for idx, ci in rows[p]:
                        b[idx] += w * ci * ls[q]
                        wci = w * ci
                        for jdx, cj in rows[q]:
                            N[idx][jdx] += wci * cj
        x = solve(N, b)
        v = []
        for obs in self.obs:
            acc = Fraction(0)
            for idx, c in obs["partials"]:
                acc += c * x[idx]
            v.append(acc - obs["l"])
        return N, x, v

    def _reweight(self, residuals):
        weights = list(self.base)
        flags = [False] * len(self.obs)
        for i in range(len(self.obs)):
            if i in self.in_session:
                continue
            test = residuals[i] * residuals[i] * self.base[i]
            if test > self.k2:
                flags[i] = True
                weights[i] = quantize(self.base[i] * self.k2 / test, self.quant)
        return weights, flags

    def run(self):
        weights = list(self.base)
        flags = [False] * len(self.obs)
        N, x, v = self._solve_with(weights)
        for _ in range(self.iterations):
            weights, flags = self._reweight(v)
            N, x, v = self._solve_with(weights)
        self.N, self.x, self.v = N, x, v
        self.weights, self.flags = weights, flags
        return self

    def vtpv(self):
        total = Fraction(0)
        for i, w in enumerate(self.weights):
            if i in self.in_session:
                continue
            total += w * self.v[i] * self.v[i]
        for ia, ib, W in self.blocks:
            va, vb = self.v[ia], self.v[ib]
            total += (W[0][0] * va * va + W[0][1] * va * vb
                      + W[1][0] * vb * va + W[1][1] * vb * vb)
        return total

    def final_weight(self, i):
        if i in self.in_session:
            slot, member = self.in_session[i]
            return self.blocks[slot][2][member][member]
        return self.weights[i]

    def trace(self):
        return sum(self.N[j][j] for j in range(self.n))


def load_sessions(data_dir):
    path = os.path.join(data_dir, "session_correlation.csv")
    if not os.path.exists(path):
        return []
    out = []
    for row in read_table(path, ","):
        if row.get("status") != "authoritative":
            continue
        out.append({"a": row["member_a_obs_id"].strip(),
                    "b": row["member_b_obs_id"].strip(),
                    "cov": Fraction(int(row["cov_num"]), int(row["cov_den"]))})
    return out


# --------------------------------------------------------------------------
# report writing
# --------------------------------------------------------------------------

def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)
        fh.write("\n")


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def first_occurrence_map(rows, key, value):
    out = {}
    for row in rows:
        if is_ignored(row):
            continue
        k = row[key].strip()
        if k not in out:
            out[k] = row[value].strip()
    return out


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    out = lambda name: os.path.join(out_dir, name)

    control = read_workbook(os.path.join(data_dir,
                                         "adjustment_control_workbook.xlsx"))
    u_constrained = int(control["u_constrained"])
    tuning_k = Fraction(control["tuning_k"])
    blunder_crit = Fraction(control["blunder_crit"])
    origin_index = int(control["datum_origin_station"])

    policy = read_policy(os.path.join(data_dir, "iteration_policy.yaml"))
    iterations = int(policy.get("irls_iterations", 4))
    quant = int(policy.get("weight_quant_decimal_places", 34))

    observations, superseded = build_observations(data_dir)
    apply_traverse_closure(data_dir, observations)
    sessions = load_sessions(data_dir)

    order = {}
    for row in read_table(os.path.join(data_dir, "station_registry.csv"), ","):
        if is_ignored(row):
            continue
        order.setdefault(row["station"], int(row["ordinal"]))
    names = [name for name, _ in sorted(order.items(), key=lambda kv: kv[1])]
    if not names:
        names = STATION_ORDER
    n_unknowns = 2 * len(names)
    labels = []
    for name in names:
        labels.append(name + ".x")
        labels.append(name + ".y")

    k2 = tuning_k * tuning_k
    crit2 = blunder_crit * blunder_crit

    stage1 = Adjustment(observations, sessions, n_unknowns, quant, iterations,
                        k2).run()
    removed = sorted(obs["obs_id"] for i, obs in enumerate(observations)
                     if stage1.v[i] * stage1.v[i] * stage1.base[i] > crit2)
    removed_set = set(removed)

    kept = [o for o in observations if o["obs_id"] not in removed_set]
    stage2 = Adjustment(kept, sessions, n_unknowns, quant, iterations, k2).run()

    n_obs = len(kept)
    dof = n_obs - u_constrained
    vtpv = stage2.vtpv()
    sigma0_sq = vtpv / dof if dof else Fraction(0)

    free_x = stage2.x
    ox, oy = free_x[2 * origin_index], free_x[2 * origin_index + 1]
    shifted = [free_x[j] - (ox if j % 2 == 0 else oy)
               for j in range(n_unknowns)]
    origin_name = names[origin_index]

    centre = None
    for row in read_table(os.path.join(data_dir,
                                       "chi_square_bounds_table.csv"), ","):
        if int(row["dof"]) == dof:
            centre = Fraction(int(row["center_num"]), int(row["center_den"]))
            break
    if centre is None:
        raise ValueError("no chi-square acceptance row for dof=%d" % dof)
    lo, hi = centre - HALF, centre + HALF
    if vtpv < lo:
        verdict = "REJECT_LOW"
    elif vtpv > hi:
        verdict = "REJECT_HIGH"
    else:
        verdict = "PASS"

    downweighted = sorted(kept[i]["obs_id"]
                          for i in range(n_obs) if stage2.flags[i])
    down_set = set(downweighted)
    residual = {kept[i]["obs_id"]: stage2.v[i] for i in range(n_obs)}

    frame_of = first_occurrence_map(
        read_table(os.path.join(data_dir, "station_frame_map.csv"), ","),
        "station", "frame")
    campaign_of = first_occurrence_map(
        read_table(os.path.join(data_dir, "epoch_campaign_map.csv"), ","),
        "epoch", "campaign")

    def sum_abs(group):
        return micro(sum((abs(residual[o["obs_id"]]) for o in group),
                         Fraction(0)))

    write_json(out("adjusted_state.json"), {
        "unknowns": {labels[j]: fmt(shifted[j], 10) for j in range(n_unknowns)},
        "unknowns_micrometres": {labels[j]: micro(shifted[j])
                                 for j in range(n_unknowns)},
        "n_observations": n_obs,
        "u_constrained": u_constrained,
        "degrees_of_freedom": dof,
        "variance_of_unit_weight": fmt(sigma0_sq, 10),
        "quadratic_form_vtpv": fmt(vtpv, 10),
        "tuning_constant_k": fmt(tuning_k, 6),
        "blunder_critical_value": fmt(blunder_crit, 6),
        "blunders_removed": len(removed),
        "datum_origin_station": origin_name,
        "model_test_verdict": verdict,
    })

    write_json(out("model_test.json"), {
        "degrees_of_freedom": dof,
        "quadratic_form_vtpv": fmt(vtpv, 10),
        "acceptance_low": fmt(lo, 6),
        "acceptance_high": fmt(hi, 6),
        "verdict": verdict,
        "passed": verdict == "PASS",
    })

    write_json(out("downweighted_observations.json"), {
        "count": len(downweighted),
        "obs_ids": downweighted,
    })

    write_json(out("removed_blunders.json"), {
        "count": len(removed),
        "obs_ids": removed,
        "critical_value": fmt(blunder_crit, 6),
    })

    write_json(out("datum_transformation.json"), {
        "origin_station": origin_name,
        "origin_station_index": origin_index,
        "free_corrections_micrometres": {labels[j]: micro(free_x[j])
                                         for j in range(n_unknowns)},
        "shifted_corrections_micrometres": {labels[j]: micro(shifted[j])
                                            for j in range(n_unknowns)},
    })

    best_id, best_abs = None, None
    for obs in kept:
        value = abs(residual[obs["obs_id"]])
        if best_abs is None or value > best_abs:
            best_abs, best_id = value, obs["obs_id"]
        elif value == best_abs and obs["obs_id"] < best_id:
            best_id = obs["obs_id"]
    write_json(out("residual_summary.json"), {
        "n": n_obs,
        "sum_signed_micrometres": micro(sum((residual[o["obs_id"]]
                                             for o in kept), Fraction(0))),
        "max_abs_residual_micrometres": micro(best_abs) if kept else 0,
        "max_abs_residual_obs_id": best_id if kept else "",
    })

    lines = ["unknown_index,label,correction_metres,correction_micrometres"]
    for j in range(n_unknowns):
        lines.append("%d,%s,%s,%d" % (j, labels[j], fmt(shifted[j], 10),
                                      micro(shifted[j])))
    write_text(out("unknowns.csv"), "\n".join(lines) + "\n")

    csv_lines = ["obs_id,kind,residual_micrometres,downweighted"]
    tsv_lines = ["obs_id\tresidual_micrometres"]
    jsonl_lines = []
    ndjson_lines = []
    for obs in kept:
        oid = obs["obs_id"]
        r = micro(residual[oid])
        flag = oid in down_set
        csv_lines.append("%s,%s,%d,%d" % (oid, obs["kind"], r, 1 if flag else 0))
        tsv_lines.append("%s\t%d" % (oid, r))
        jsonl_lines.append(json.dumps({"obs_id": oid, "kind": obs["kind"],
                                       "residual_micrometres": r,
                                       "downweighted": flag}, sort_keys=True))
        ndjson_lines.append(json.dumps({"id": oid, "r": r}, sort_keys=True))
    write_text(out("residuals.csv"), "\n".join(csv_lines) + "\n")
    write_text(out("residuals.tsv"), "\n".join(tsv_lines) + "\n")
    write_text(out("observation_stream.jsonl"), "\n".join(jsonl_lines) + "\n")
    write_text(out("observation_stream.ndjson"), "\n".join(ndjson_lines) + "\n")

    lines = ["obs_id|weight_num|weight_den"]
    for i, obs in enumerate(kept):
        w = stage2.final_weight(i)
        lines.append("%s|%d|%d" % (obs["obs_id"], w.numerator, w.denominator))
    write_text(out("final_weights.psv"), "\n".join(lines) + "\n")

    for district in ("North", "South", "West", "East"):
        group = [o for o in kept if o["district"] == district]
        write_json(out("district_%s.json" % district), {
            "district": district,
            "observation_count": len(group),
            "downweighted_count": sum(1 for o in group
                                      if o["obs_id"] in down_set),
            "sum_abs_residual_micrometres": sum_abs(group),
        })

    for epoch in sorted({o["epoch"] for o in observations}
                        | {int(e) for e in campaign_of}):
        group = [o for o in kept if o["epoch"] == epoch]
        write_json(out("epoch_%d.json" % epoch), {
            "epoch": epoch,
            "observation_count": len(group),
            "sum_abs_residual_micrometres": sum_abs(group),
        })

    pairs = {}
    for obs in kept:
        key = (frame_of.get(names[obs["primary_station"]], ""),
               campaign_of.get(str(obs["epoch"]), ""))
        pairs.setdefault(key, []).append(obs)
    wanted = set(pairs)
    for frame in set(frame_of.values()):
        for campaign in set(campaign_of.values()):
            wanted.add((frame, campaign))
    for frame, campaign in sorted(wanted):
        group = pairs.get((frame, campaign), [])
        write_json(out("rollup_%s_%s.json" % (frame, campaign)), {
            "frame": frame,
            "campaign": campaign,
            "observation_count": len(group),
            "downweighted_count": sum(1 for o in group
                                      if o["obs_id"] in down_set),
            "sum_abs_residual_micrometres": sum_abs(group),
        })

    trace = stage2.trace()
    write_json(out("normal_matrix_trace.json"), {
        "trace_num": trace.numerator,
        "trace_den": trace.denominator,
        "trace_decimal": fmt(trace, 6),
    })

    write_json(out("provenance_summary.json"), {
        "control_values_source": "adjustment_control_workbook.xlsx",
        "u_constrained": u_constrained,
        "tuning_constant_k": fmt(tuning_k, 6),
        "blunder_critical_value": fmt(blunder_crit, 6),
        "datum_origin_station": origin_name,
        "superseded_records": superseded,
        "decoys_ignored": [
            "archive_backfill.db",
            "deprecated_precorrection_coords.csv",
            "legacy_orientation_offsets.tsv",
            "observation_weight_manifest.csv:naive_weight",
            "residual_prior_epoch.tsv",
            "scale_factor_table.csv",
            "stale_cached_solution.json",
        ],
    })

    write_text(out("status.txt"),
               "verdict=%s dof=%d u=%d n=%d blunders_removed=%d "
               "datum_origin=%s sigma0_sq=%s downweighted=%d\n"
               % (verdict, dof, u_constrained, n_obs, len(removed),
                  origin_name, fmt(sigma0_sq, 10), len(downweighted)))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<adjustment>",
           "  <verdict>%s</verdict>" % verdict,
           "  <degrees_of_freedom>%d</degrees_of_freedom>" % dof,
           "  <u_constrained>%d</u_constrained>" % u_constrained,
           "  <variance_of_unit_weight>%s</variance_of_unit_weight>"
           % fmt(sigma0_sq, 10), "  <unknowns>"]
    for j in range(n_unknowns):
        xml.append('    <unknown label="%s" correction_micrometres="%d"/>'
                   % (labels[j], micro(shifted[j])))
    xml.extend(["  </unknowns>", "</adjustment>"])
    write_text(out("adjustment_report.xml"), "\n".join(xml) + "\n")

    write_text(out("adjustment_summary.yaml"),
               "model_test_verdict: %s\n"
               "degrees_of_freedom: %d\n"
               "u_constrained: %d\n"
               "variance_of_unit_weight: %s\n"
               "downweighted_count: %d\n"
               "tuning_constant_k: %s\n"
               % (verdict, dof, u_constrained, fmt(sigma0_sq, 10),
                  len(downweighted), fmt(tuning_k, 6)))

    write_text(out("adjustment_report.md"),
               "# Adjustment Report\n\n"
               "Two-stage robust weighted least-squares adjustment of the "
               "sensor-network extract.\n\n"
               "- Model test verdict: %s\n"
               "- Degrees of freedom: %d\n"
               "- Variance of unit weight: %s\n"
               "- Downweighted count: %d\n"
               "- Tuning constant k: %s\n\n"
               "Stage-2 observations: %d. Stage-1 blunders removed: %d. "
               "Constrained components u: %d. Datum origin station: %s.\n"
               % (verdict, dof, fmt(sigma0_sq, 10), len(downweighted),
                  fmt(tuning_k, 6), n_obs, len(removed), u_constrained,
                  origin_name))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
