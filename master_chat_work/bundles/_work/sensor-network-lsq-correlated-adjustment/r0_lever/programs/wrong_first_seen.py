"""Reference derivation program for the district sensor-network adjustment.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Written from /app/data/schema.md. Every convention is read from DATA_DIR.
All load-bearing arithmetic uses fractions.Fraction.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path

STATION_NAMES = ("ALPHA", "BRAVO", "CIVET", "DELTA", "EAGLE", "FICUS")
UNKNOWN_COUNT = 2 * len(STATION_NAMES)
UNKNOWN_LABELS = [f"{STATION_NAMES[i // 2]}.{'xy'[i % 2]}" for i in range(UNKNOWN_COUNT)]
DISTRICTS = ("North", "South", "West", "East")
EPOCHS = (1, 2, 3)
SHARDS = (
    ("obs_source_district_north.csv", ","),
    ("obs_source_district_south.tsv", "\t"),
    ("obs_source_district_west.psv", "|"),
    ("obs_source_district_east.jsonl", "json"),
)
JSONL_FIELDS = {"id": "obs_id", "k": "kind", "v": "observed_value",
                "c": "computed_nominal", "s": "apriori_sigma", "u": "unit",
                "sk": "sigma_kind", "d": "dir", "A": "partials", "e": "epoch",
                "reg": "region"}
DECOYS_REJECTED = [
    "archive_backfill.db",
    "deprecated_precorrection_coords.csv",
    "iteration_policy.yaml:default_tuning_k",
    "legacy_orientation_offsets.tsv",
    "observation_weight_manifest.csv:naive_weight",
    "residual_prior_epoch.tsv",
    "scale_factor_table.csv",
    "stale_cached_solution.json",
]
XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
           "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
           "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


# ----------------------------------------------------------------- rounding
def round_places(value: Fraction, places: int) -> Fraction:
    """Exact half-even rounding of a rational to `places` decimals."""
    step = 10 ** places
    return Fraction(round(value * step), step)


def fixed(value: Fraction, places: int) -> str:
    units = round(value * 10 ** places)
    text = str(abs(units)).rjust(places + 1, "0")
    body = text if places == 0 else text[:-places] + "." + text[-places:]
    return ("-" if units < 0 else "") + body


def micro(value: Fraction) -> int:
    return round(value * 1_000_000)


# ------------------------------------------------------------- file readers
def table_rows(path: Path, delimiter: str = ","):
    """Rows of a delimited file whose '#' lines form a header comment block."""
    lines = path.read_text(encoding="utf-8").splitlines()
    data = [ln for ln in lines if not ln.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(data)), delimiter=delimiter))


def declared_tokens(lines) -> dict:
    found = {}
    for line in lines:
        for word in line.lstrip("#").split():
            key, sep, val = word.partition("=")
            if sep and key not in found:
                found[key] = val
    return found


def is_true(value) -> bool:
    return str(value).strip().lower() == "true"


def unit_factors(data_dir: Path) -> dict:
    factors = {}
    for row in table_rows(data_dir / "reference_unit_registry.csv"):
        if row["status"] != "authoritative":
            continue
        factor = Fraction(int(row["factor_num"]), int(row["factor_den"]))
        known = factors.setdefault(row["unit"], factor)
        if known != factor:
            raise ValueError(f"conflicting authoritative factor for {row['unit']}")
    return factors


def shard_records(data_dir: Path):
    """Yield (record dict, shard declaration dict, shard file name) per shard row."""
    for name, delim in SHARDS:
        path = data_dir / name
        if delim == "json":
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            decl = json.loads(lines[0])
            for ln in lines[1:]:
                raw = json.loads(ln)
                yield ({JSONL_FIELDS[k]: str(v) for k, v in raw.items() if k in JSONL_FIELDS},
                       decl, name)
        else:
            text = path.read_text(encoding="utf-8").splitlines()
            decl = declared_tokens(ln for ln in text if ln.startswith("#"))
            for row in table_rows(path, delim):
                yield dict(row), decl, name


class Observation:
    def __init__(self, ident, kind, misclosure, variance, design, epoch, region):
        self.ident = ident
        self.kind = kind
        self.l = misclosure
        self.variance = variance
        self.design = design
        self.epoch = epoch
        self.region = region


def centring_variances(data_dir: Path) -> dict:
    """Station ordinal -> centring variance in m^2 from its first active row."""
    found = {}
    for row in table_rows(data_dir / "station_registry.csv"):
        if row["mark_status"] != "active" or int(row["ordinal"]) in found:
            continue
        sigma = Fraction(row["centring_mm"]) / 1000
        found[int(row["ordinal"])] = sigma * sigma if row["mount"] == "tripod" else Fraction(0)
    return found


def load_observations(data_dir: Path):
    """Return (observations sorted by obs_id, superseded record list)."""
    chosen = {}
    carriers = {}
    for rec, decl, shard in shard_records(data_dir):
        ident = rec["obs_id"]
        if is_true(decl.get("transpose_ids")) and rec["epoch"].strip() == "2":
            ident = ident[-3:] + ident[:-3]
        revision = int(decl["revision"])
        carriers.setdefault(ident, []).append(shard)
        if ident not in chosen:
            chosen[ident] = (revision, shard, rec, decl)
    factors = unit_factors(data_dir)
    centring = centring_variances(data_dir)
    result, superseded = [], []
    for ident in sorted(chosen):
        _, shard, rec, decl = chosen[ident]
        result.append(to_observation(ident, rec, decl, factors, centring))
        superseded.extend({"obs_id": ident, "kept_shard": shard, "superseded_shard": other}
                          for other in carriers[ident] if other != shard)
    superseded.sort(key=lambda d: (d["obs_id"], d["superseded_shard"]))
    return result, superseded


def to_observation(ident, rec, decl, factors, centring) -> Observation:
    scale = factors[rec["unit"].strip()]
    observed = Fraction(rec["observed_value"].strip()) * scale
    nominal = Fraction(rec["computed_nominal"].strip()) * scale
    if rec["dir"].strip() == "R":
        observed, nominal = -observed, -nominal
    angle = rec["kind"] == "angle"
    if angle and is_true(decl.get("azimuth_wrap")):
        observed %= 400
        nominal %= 400
    misclosure = observed - nominal
    if angle:
        misclosure %= 400
        if misclosure > 200:
            misclosure -= 400
    stored = Fraction(rec["apriori_sigma"].strip())
    variance = stored * stored * scale * scale if rec["sigma_kind"] == "stddev" else stored * scale * scale
    design = {}
    for term in rec["partials"].split(";"):
        if term.strip():
            idx, ratio = term.split(":")
            design[int(idx)] = Fraction(ratio)
    if not angle:
        for station in sorted({i // 2 for i, a in design.items() if a != 0}):
            variance += centring[station]
    return Observation(ident, rec["kind"], misclosure, variance,
                       design, int(rec["epoch"]), rec["region"])


def workbook_controls(data_dir: Path) -> dict:
    """Read the label/value pairs on the workbook sheet named 'datum'."""
    with zipfile.ZipFile(data_dir / "adjustment_control_workbook.xlsx") as book:
        wb = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", XLSX_NS)}
        rid = next(s.get(f"{{{XLSX_NS['r']}}}id") for s in wb.iter(f"{{{XLSX_NS['m']}}}sheet")
                   if s.get("name") == "datum")
        sheet = ET.fromstring(book.read("xl/" + target[rid]))
    values = {}
    for row in sheet.iter(f"{{{XLSX_NS['m']}}}row"):
        cells = ["".join(t.text or "" for t in c.iter(f"{{{XLSX_NS['m']}}}t"))
                 for c in row.findall("m:c", XLSX_NS)]
        if len(cells) >= 2:
            values.setdefault(cells[0].strip(), cells[1].strip())
    return {"u": int(values["u_constrained"]),
            "k": Fraction(values["tuning_k"]),
            "crit": Fraction(values["blunder_crit"]),
            "origin": int(values["datum_origin_station"])}


def iteration_policy(data_dir: Path) -> tuple[int, int]:
    settings = {}
    for line in (data_dir / "iteration_policy.yaml").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and ":" in line:
            key, _, val = line.partition(":")
            settings[key.strip()] = val.strip()
    return int(settings["irls_iterations"]), int(settings["weight_quant_decimal_places"])


def correlated_sessions(data_dir: Path):
    return [(row["member_a_obs_id"], row["member_b_obs_id"],
             Fraction(int(row["cov_num"]), int(row["cov_den"])))
            for row in table_rows(data_dir / "session_correlation.csv")
            if row["status"] == "authoritative"]


def acceptance_interval(data_dir: Path, dof: int) -> tuple[Fraction, Fraction]:
    for row in table_rows(data_dir / "chi_square_bounds_table.csv"):
        if int(row["dof"]) == dof:
            centre = Fraction(int(row["center_num"]), int(row["center_den"]))
            return centre - Fraction(1, 2), centre + Fraction(1, 2)
    raise LookupError(f"no acceptance row for dof={dof}")


def first_mapping(path: Path, key: str, value: str, cast=str) -> dict:
    mapping = {}
    for row in table_rows(path):
        mapping.setdefault(cast(row[key]), row[value])
    return mapping


# ----------------------------------------------------------- linear algebra
def gauss_solve(matrix, rhs):
    """Gaussian elimination with partial pivoting (largest |pivot|, lowest row
    on ties) followed by back substitution, in exact rationals."""
    size = len(rhs)
    rows = [list(matrix[i]) + [rhs[i]] for i in range(size)]
    for col in range(size):
        best = max(range(col, size), key=lambda r: (abs(rows[r][col]), -r))
        if rows[best][col] == 0:
            raise ArithmeticError("singular normal matrix")
        rows[col], rows[best] = rows[best], rows[col]
        pivot_row = rows[col]
        for r in range(col + 1, size):
            ratio = rows[r][col] / pivot_row[col]
            if ratio:
                target = rows[r]
                for c in range(col, size + 1):
                    target[c] -= ratio * pivot_row[c]
    solution = [Fraction(0)] * size
    for r in range(size - 1, -1, -1):
        acc = rows[r][size] - sum(rows[r][c] * solution[c] for c in range(r + 1, size))
        solution[r] = acc / rows[r][r]
    return solution


class Network:
    """One weighted adjustment of a fixed set of observations."""

    def __init__(self, observations, sessions, k_squared, passes, places):
        self.obs = observations
        self.k_squared = k_squared
        self.passes = passes
        self.places = places
        position = {o.ident: i for i, o in enumerate(observations)}
        self.blocks = []
        self.in_block = set()
        for a, b, cov in sessions:
            if a in position and b in position:
                ia, ib = position[a], position[b]
                va, vb = observations[ia].variance, observations[ib].variance
                det = va * vb - cov * cov
                inverse = [[round_places(vb / det, places), round_places(-cov / det, places)],
                           [round_places(-cov / det, places), round_places(va / det, places)]]
                self.blocks.append((ia, ib, inverse))
                self.in_block.update((ia, ib))
        self.base = [round_places(1 / o.variance, places) for o in observations]

    def normal_equations(self, diagonal):
        n_mat = [[Fraction(0)] * UNKNOWN_COUNT for _ in range(UNKNOWN_COUNT)]
        rhs = [Fraction(0)] * UNKNOWN_COUNT

        def couple(row_obs, col_obs, weight):
            for i, ai in row_obs.design.items():
                for j, aj in col_obs.design.items():
                    n_mat[i][j] += weight * ai * aj
                rhs[i] += weight * ai * col_obs.l

        for idx, obs in enumerate(self.obs):
            if idx not in self.in_block:
                couple(obs, obs, diagonal[idx])
        for ia, ib, inv in self.blocks:
            pair = (self.obs[ia], self.obs[ib])
            for r in range(2):
                for c in range(2):
                    couple(pair[r], pair[c], inv[r][c])
        return n_mat, rhs

    def residuals(self, x):
        return [sum((a * x[i] for i, a in o.design.items()), Fraction(0)) - o.l for o in self.obs]

    def run(self):
        weights = list(self.base)
        flagged = [False] * len(self.obs)
        n_mat, rhs = self.normal_equations(weights)
        x = gauss_solve(n_mat, rhs)
        for _ in range(self.passes):
            v = self.residuals(x)
            weights, flagged = [], []
            for idx, (p, vi) in enumerate(zip(self.base, v)):
                test = vi * vi * p
                if idx not in self.in_block and test > self.k_squared:
                    weights.append(round_places(p * self.k_squared / test, self.places))
                    flagged.append(True)
                else:
                    weights.append(p)
                    flagged.append(False)
            n_mat, rhs = self.normal_equations(weights)
            x = gauss_solve(n_mat, rhs)
        v = self.residuals(x)
        reported = list(weights)
        quadratic = sum((weights[i] * v[i] * v[i] for i in range(len(v))
                         if i not in self.in_block), Fraction(0))
        for ia, ib, inv in self.blocks:
            pair_v = (v[ia], v[ib])
            quadratic += sum(pair_v[r] * inv[r][c] * pair_v[c] for r in range(2) for c in range(2))
            reported[ia], reported[ib] = inv[0][0], inv[1][1]
        trace = sum((n_mat[i][i] for i in range(UNKNOWN_COUNT)), Fraction(0))
        return {"x": x, "v": v, "flags": flagged, "weights": reported,
                "vtpv": quadratic, "trace": trace}


# ------------------------------------------------------------------ pipeline
def adjust_extract(data_dir: Path) -> dict:
    observations, superseded = load_observations(data_dir)
    control = workbook_controls(data_dir)
    passes, places = iteration_policy(data_dir)
    sessions = correlated_sessions(data_dir)
    k_squared = control["k"] ** 2
    crit_squared = control["crit"] ** 2

    first = Network(observations, sessions, k_squared, passes, places).run()
    blunders = sorted(o.ident for o, vi in zip(observations, first["v"])
                      if vi * vi * round_places(1 / o.variance, places) > crit_squared)
    removed = set(blunders)
    kept = [o for o in observations if o.ident not in removed]
    final = Network(kept, sessions, k_squared, passes, places).run()

    origin = control["origin"]
    free = final["x"]
    shift = (free[2 * origin], free[2 * origin + 1])
    shifted = [free[i] - shift[i % 2] for i in range(UNKNOWN_COUNT)]
    dof = len(kept) - control["u"]
    low, high = acceptance_interval(data_dir, dof)
    q = final["vtpv"]
    verdict = "REJECT_LOW" if q < low else "REJECT_HIGH" if q > high else "PASS"
    return {"obs": kept, "free": free, "shifted": shifted, "final": final,
            "control": control, "blunders": blunders, "dof": dof,
            "sigma0_sq": q / dof, "low": low, "high": high, "verdict": verdict,
            "superseded": superseded}


def dump_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_reports(data_dir: Path, out_dir: Path) -> None:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = adjust_extract(data_dir)
    obs, fin, ctl = res["obs"], res["final"], res["control"]
    v, flags = fin["v"], fin["flags"]
    origin_name = STATION_NAMES[ctl["origin"]]
    sigma0 = fixed(res["sigma0_sq"], 10)
    vtpv = fixed(fin["vtpv"], 10)
    k_text = fixed(ctl["k"], 6)
    crit_text = fixed(ctl["crit"], 6)
    downweighted = [o.ident for o, f in zip(obs, flags) if f]
    shifted_um = {lab: micro(val) for lab, val in zip(UNKNOWN_LABELS, res["shifted"])}

    dump_json(out_dir / "adjusted_state.json", {
        "unknowns": {lab: fixed(val, 10) for lab, val in zip(UNKNOWN_LABELS, res["shifted"])},
        "unknowns_micrometres": shifted_um,
        "n_observations": len(obs),
        "u_constrained": ctl["u"],
        "degrees_of_freedom": res["dof"],
        "variance_of_unit_weight": sigma0,
        "quadratic_form_vtpv": vtpv,
        "tuning_constant_k": k_text,
        "blunder_critical_value": crit_text,
        "blunders_removed": len(res["blunders"]),
        "datum_origin_station": origin_name,
        "model_test_verdict": res["verdict"],
    })
    dump_json(out_dir / "model_test.json", {
        "degrees_of_freedom": res["dof"], "quadratic_form_vtpv": vtpv,
        "acceptance_low": fixed(res["low"], 6), "acceptance_high": fixed(res["high"], 6),
        "verdict": res["verdict"], "passed": res["verdict"] == "PASS",
    })
    dump_json(out_dir / "downweighted_observations.json",
              {"count": len(downweighted), "obs_ids": downweighted})
    dump_json(out_dir / "removed_blunders.json",
              {"count": len(res["blunders"]), "obs_ids": res["blunders"], "critical_value": crit_text})
    dump_json(out_dir / "datum_transformation.json", {
        "origin_station": origin_name, "origin_station_index": ctl["origin"],
        "free_corrections_micrometres": {lab: micro(val) for lab, val in zip(UNKNOWN_LABELS, res["free"])},
        "shifted_corrections_micrometres": shifted_um,
    })
    largest = max(abs(r) for r in v)
    dump_json(out_dir / "residual_summary.json", {
        "n": len(v), "sum_signed_micrometres": micro(sum(v, Fraction(0))),
        "max_abs_residual_micrometres": micro(largest),
        "max_abs_residual_obs_id": min(o.ident for o, r in zip(obs, v) if abs(r) == largest),
    })

    with open(out_dir / "unknowns.csv", "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, lineterminator="\n")
        out.writerow(["unknown_index", "label", "correction_metres", "correction_micrometres"])
        for i, (lab, val) in enumerate(zip(UNKNOWN_LABELS, res["shifted"])):
            out.writerow([i, lab, fixed(val, 10), micro(val)])
    with open(out_dir / "residuals.csv", "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, lineterminator="\n")
        out.writerow(["obs_id", "kind", "residual_micrometres", "downweighted"])
        for o, r, f in zip(obs, v, flags):
            out.writerow([o.ident, o.kind, micro(r), 1 if f else 0])
    with open(out_dir / "residuals.tsv", "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, delimiter="\t", lineterminator="\n")
        out.writerow(["obs_id", "residual_micrometres"])
        out.writerows([o.ident, micro(r)] for o, r in zip(obs, v))
    with open(out_dir / "final_weights.psv", "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, delimiter="|", lineterminator="\n")
        out.writerow(["obs_id", "weight_num", "weight_den"])
        out.writerows([o.ident, w.numerator, w.denominator] for o, w in zip(obs, fin["weights"]))
    with open(out_dir / "observation_stream.jsonl", "w", encoding="utf-8") as fh:
        for o, r, f in zip(obs, v, flags):
            fh.write(json.dumps({"downweighted": f, "kind": o.kind, "obs_id": o.ident,
                                 "residual_micrometres": micro(r)}, sort_keys=True) + "\n")
    with open(out_dir / "observation_stream.ndjson", "w", encoding="utf-8") as fh:
        for o, r in zip(obs, v):
            fh.write(json.dumps({"id": o.ident, "r": micro(r)}, sort_keys=True) + "\n")

    def rollup(members):
        return (len(members), sum(1 for _, f in members if f),
                micro(sum((abs(r) for r, _ in members), Fraction(0))))

    for district in DISTRICTS:
        count, dw, total = rollup([(r, f) for o, r, f in zip(obs, v, flags) if o.region == district])
        dump_json(out_dir / f"district_{district}.json", {
            "district": district, "observation_count": count,
            "downweighted_count": dw, "sum_abs_residual_micrometres": total})
    for epoch in EPOCHS:
        count, _, total = rollup([(r, f) for o, r, f in zip(obs, v, flags) if o.epoch == epoch])
        dump_json(out_dir / f"epoch_{epoch}.json", {
            "epoch": epoch, "observation_count": count, "sum_abs_residual_micrometres": total})
    frame_of = first_mapping(data_dir / "station_frame_map.csv", "station", "frame")
    campaign_of = first_mapping(data_dir / "epoch_campaign_map.csv", "epoch", "campaign", int)
    groups = {}
    for o, r, f in zip(obs, v, flags):
        key = (frame_of[STATION_NAMES[min(o.design) // 2]], campaign_of[o.epoch])
        groups.setdefault(key, []).append((r, f))
    for (frame, campaign), members in sorted(groups.items()):
        count, dw, total = rollup(members)
        dump_json(out_dir / f"rollup_{frame}_{campaign}.json", {
            "frame": frame, "campaign": campaign, "observation_count": count,
            "downweighted_count": dw, "sum_abs_residual_micrometres": total})

    trace = fin["trace"]
    dump_json(out_dir / "normal_matrix_trace.json", {
        "trace_num": trace.numerator, "trace_den": trace.denominator,
        "trace_decimal": fixed(trace, 6)})
    dump_json(out_dir / "provenance_summary.json", {
        "control_values_source": "adjustment_control_workbook.xlsx",
        "u_constrained": ctl["u"], "tuning_constant_k": k_text,
        "blunder_critical_value": crit_text, "datum_origin_station": origin_name,
        "superseded_records": res["superseded"],
        "decoys_ignored": DECOYS_REJECTED})

    root = ET.Element("adjustment")
    for tag, text in (("verdict", res["verdict"]), ("degrees_of_freedom", str(res["dof"])),
                      ("u_constrained", str(ctl["u"])), ("variance_of_unit_weight", sigma0)):
        ET.SubElement(root, tag).text = text
    block = ET.SubElement(root, "unknowns")
    for lab in UNKNOWN_LABELS:
        ET.SubElement(block, "unknown", label=lab, correction_micrometres=str(shifted_um[lab]))
    ET.indent(root)
    (out_dir / "adjustment_report.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
        encoding="utf-8")
    (out_dir / "adjustment_summary.yaml").write_text(
        f"model_test_verdict: {res['verdict']}\n"
        f"degrees_of_freedom: {res['dof']}\n"
        f"u_constrained: {ctl['u']}\n"
        f"variance_of_unit_weight: '{sigma0}'\n"
        f"downweighted_count: {len(downweighted)}\n"
        f"tuning_constant_k: '{k_text}'\n", encoding="utf-8")
    (out_dir / "adjustment_report.md").write_text(
        "# Adjustment report\n\n"
        f"Model test verdict: {res['verdict']}\n\n"
        f"Degrees of freedom: {res['dof']} (n = {len(obs)}, u = {ctl['u']})\n\n"
        f"Variance of unit weight: {sigma0}\n\n"
        f"Downweighted observations: {len(downweighted)}\n\n"
        f"Robust tuning constant k: {k_text}\n", encoding="utf-8")
    (out_dir / "status.txt").write_text(
        f"verdict={res['verdict']} dof={res['dof']} u={ctl['u']} n={len(obs)} "
        f"blunders_removed={len(res['blunders'])} datum_origin={origin_name} "
        f"sigma0_sq={sigma0} downweighted={len(downweighted)}\n", encoding="utf-8")


def main(argv) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    write_reports(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
