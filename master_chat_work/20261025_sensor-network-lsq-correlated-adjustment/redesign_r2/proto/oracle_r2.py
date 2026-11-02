"""Phase 1 prototype of the r2 levers, as flags over a scratch copy of the oracle.

Levers (each mode 'correct' or 'reflex'):
  A  scale closure distributed over a district+epoch group of length legs by
     largest remainder; legs whose first share falls below the floor drop and
     the WHOLE closure is shared again over the survivors (no fits branch on
     the second pass). Reflex: the second pass re-enters the whole rule.
  B  centring variance of a setup follows set_out_from through the control
     mark register recursively. Reflex: one level (own + named mark's own).
  C  district of an observation = district of the shard that supplied its
     kept record. Reflex: the per-line region field.
Never imported by the bundle.
"""
from __future__ import annotations

import csv
import io
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_base as T  # noqa: E402

SHARD_DISTRICT = {fname: T.REGIONS[i] for i, (fname, _) in enumerate(T.SHARD_FILES)}
CLOSURE_FILE = "scale_closure_register.csv"
MARK_FILE = "control_mark_register.csv"

# ---------------------------------------------------------------------------
# generator hooks
# ---------------------------------------------------------------------------
FEATS: dict = {}
_orig_plan = T._plan_duplicates


def _plan_aligned(obs):
    shards = _orig_plan(obs)
    for si, shard in enumerate(shards):
        for o in shard:
            o.region = T.REGIONS[si]
    n_mis = FEATS.get("mislabel", 0)
    if n_mis:
        rng = T.Rng(FEATS["seed"] ^ 21)
        counts: dict = {}
        for sh in shards:
            for o in sh:
                counts[o.oid] = counts.get(o.oid, 0) + 1
        cands = [(si, o) for si, sh in enumerate(shards) for o in sh
                 if counts[o.oid] == 1 and o.kind == "length"]
        cands += [(si, o) for si, sh in enumerate(shards) for o in sh
                  if counts[o.oid] == 1 and o.kind == "angle"][: n_mis // 4]
        step = max(1, len(cands) // n_mis)
        for j in range(0, len(cands), step)[:n_mis]:
            si, o = cands[j]
            o.region = T.REGIONS[(si + 1 + rng.randint(0, 2)) % 4]
    return shards


T._plan_duplicates = _plan_aligned


def _registry_rows(data_dir: Path):
    text = (data_dir / "station_registry.csv").read_text(encoding="utf-8")
    head = [ln for ln in text.splitlines() if ln.startswith("#")]
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    rows = list(csv.reader(io.StringIO(body)))
    return head, rows


def _emit_marks(data_dir: Path, seed: int, chain: str) -> dict:
    """Write control_mark_register.csv and the set_out_from column. Returns
    station -> set_out_from."""
    rng = T.Rng(seed ^ 22)
    marks = []  # (mark_id, mount, centring_mm, set_out_from)
    for i in range(1, 41):
        mt = "tripod" if rng.randint(0, 2) else "pillar"
        cm = f"{rng.randint(5, 40) / 10:.1f}"
        marks.append([f"CM{i:02d}", mt, cm, ""])
    # unreferenced chains among marks 21..40 so the column is visibly in use
    for i in range(21, 40, 2):
        marks[i][3] = f"CM{i + 2:02d}" if i + 2 <= 40 else ""
    link = {st: "" for st in T.STATIONS}
    if chain in ("depth1", "deep"):
        # depth-1 links: named mark has no set_out_from of its own
        link["BRAVO"] = "CM03"
        link["CIVET"] = "CM05"
        marks[2][1:] = ["tripod", "1.5", ""]
        marks[4][1:] = ["tripod", "2.0", ""]
    if chain == "deep":
        # DELTA -> CM07 (pillar) -> CM08 (tripod 3.0)
        # FICUS -> CM10 (tripod 1.2) -> CM11 (pillar) -> CM12 (tripod 2.5)
        pick = rng.randint(0, 1)
        link["DELTA" if pick else "EAGLE"] = "CM07"
        marks[6][1:] = ["pillar", "0.4", "CM08"]
        marks[7][1:] = ["tripod", "3.0", ""]
        link["FICUS"] = "CM10"
        marks[9][1:] = ["tripod", "1.2", "CM11"]
        marks[10][1:] = ["pillar", "0.7", "CM12"]
        marks[11][1:] = ["tripod", "2.5", ""]
    rows = [["mark_id", "mount", "centring_mm", "set_out_from"]] + marks
    T._write_csv_rows(data_dir / MARK_FILE,
                      "# control_mark_register: control marks a setup may be set out from.\n",
                      rows)
    head, reg = _registry_rows(data_dir)
    hdr = reg[0] + ["set_out_from"]
    out = [hdr]
    for r in reg[1:]:
        st = r[0]
        val = link[st] if r[10] == "active" else f"CM{rng.randint(13, 20):02d}"
        out.append(r + [val])
    T._write_csv_rows(data_dir / "station_registry.csv", "\n".join(head) + "\n", out)
    return link


# ---------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------
def _kept_records(data_dir: Path):
    best, seen = {}, {}
    for fname, delim in T.SHARD_FILES:
        path = Path(data_dir) / fname
        raws, wrap, rev = (T.read_jsonl(path) if delim is None
                           else T.read_delimited(path, delim))
        for r in raws:
            seen.setdefault(r.oid, []).append((rev, fname))
            cur = best.get(r.oid)
            if cur is None or rev > cur[0]:
                best[r.oid] = (rev, fname, r, wrap)
    return best, seen


def _basis(r) -> int:
    nom = abs(Fraction(Decimal(r.nominal_disp)) * T.LEN_TO_M[r.unit])
    return int(nom // 1)


def _largest_remainder(total: int, legs):
    """legs: list of (oid, basis). Whole-unit shares summing to total."""
    s = sum(b for _, b in legs)
    quot = {oid: Fraction(total * b, s) for oid, b in legs}
    share = {oid: int(q // 1) for oid, q in quot.items()}
    rest = total - sum(share.values())
    order = sorted(legs, key=lambda t: (-(quot[t[0]] - share[t[0]]), t[0]))
    for oid, _ in order[:rest]:
        share[oid] += 1
    return share


def distribute(total: int, legs, floor: int, mode: str, depth: int = 0) -> dict:
    """Return oid -> whole micrometres absorbed (magnitude)."""
    if not legs or total == 0:
        return {oid: 0 for oid, _ in legs}
    s = sum(b for _, b in legs)
    if s <= total:
        return {oid: b for oid, b in legs}
    share = _largest_remainder(total, legs)
    keep = [(oid, b) for oid, b in legs if share[oid] >= floor]
    if len(keep) == len(legs):
        return share
    out = {oid: 0 for oid, _ in legs}
    if not keep:
        return out
    if mode == "correct":
        out.update(_largest_remainder(total, keep))
    else:  # reflex: the second pass re-enters the whole rule
        out.update(distribute(total, keep, floor, mode, depth + 1))
    return out


def read_closures(data_dir: Path) -> dict:
    p = Path(data_dir) / CLOSURE_FILE
    if not p.is_file():
        return {}
    body = "\n".join(ln for ln in p.read_text(encoding="utf-8").splitlines()
                     if not ln.startswith("#"))
    return {(r["district"], int(r["epoch"])): (int(r["closure_micrometres"]),
                                                int(r["floor_micrometres"]))
            for r in csv.DictReader(io.StringIO(body))}


def centring_by_ordinal(data_dir: Path, mode: str) -> dict:
    head, reg = _registry_rows(Path(data_dir))
    hdr = reg[0]
    ix = {k: i for i, k in enumerate(hdr)}
    marks = {}
    mp = Path(data_dir) / MARK_FILE
    if mp.is_file():
        body = "\n".join(ln for ln in mp.read_text(encoding="utf-8").splitlines()
                         if not ln.startswith("#"))
        for r in csv.DictReader(io.StringIO(body)):
            marks[r["mark_id"]] = (r["mount"], r["centring_mm"], r["set_out_from"])

    def own(mount, cmm):
        if mount != "tripod":
            return Fraction(0)
        c = Fraction(Decimal(cmm)) / 1000
        return c * c

    def mark_var(mid, seen=()):
        mt, cm, parent = marks[mid]
        v = own(mt, cm)
        if parent and mode == "correct":
            assert parent not in seen
            v += mark_var(parent, seen + (mid,))
        return v

    out = {}
    for r in reg[1:]:
        if r[ix["mark_status"]] != "active":
            continue
        ordi = int(r[ix["ordinal"]])
        if ordi in out:
            continue
        v = own(r[ix["mount"]], r[ix["centring_mm"]])
        parent = r[ix["set_out_from"]] if "set_out_from" in ix else ""
        if parent:
            v += mark_var(parent) if mode == "correct" else own(*marks[parent][:2])
        out[ordi] = v
    return out


def read_r2(data_dir: Path, modes: dict):
    best, seen = _kept_records(data_dir)
    centring = centring_by_ordinal(data_dir, modes["B"])
    closures = read_closures(data_dir)
    all_obs, superseded, groups = [], [], {}
    for oid in sorted(best):
        rev, fname, r, wrap = best[oid]
        o = T.to_base_observation(r, wrap)
        o.region = SHARD_DISTRICT[fname] if modes["C"] == "correct" else r.region
        if o.kind == "length":
            for st in sorted({idx // 2 for idx, c in o.coeffs.items() if c != 0}):
                o.variance_base += centring[st]
            groups.setdefault((o.region, o.epoch), []).append((o, _basis(r)))
        all_obs.append(o)
        for other_rev, other_f in seen[oid]:
            if other_f != fname:
                superseded.append({"obs_id": oid, "kept_shard": fname,
                                   "superseded_shard": other_f})
    shares = {}
    for key, members in groups.items():
        c, floor = closures.get(key, (0, 0))
        legs = [(o.obs_id, b) for o, b in members]
        got = distribute(abs(c), legs, floor, modes["A"])
        sign = 1 if c > 0 else -1
        for o, _ in members:
            o.value_base -= Fraction(sign * got[o.obs_id], 10 ** 6)
            shares[o.obs_id] = sign * got[o.obs_id]
    superseded.sort(key=lambda d: (d["obs_id"], d["superseded_shard"]))
    read_r2.last_shares = shares
    return all_obs, superseded


def solve_r2(data_dir: Path, modes: dict) -> dict:
    orig = T.read_source_shards
    T.read_source_shards = lambda d: read_r2(d, modes)
    try:
        ref = T.solve(Path(data_dir))
    finally:
        T.read_source_shards = orig
    ref["shares"] = dict(read_r2.last_shares)
    return ref


# ---------------------------------------------------------------------------
# closure planting
# ---------------------------------------------------------------------------
def classify(total: int, legs, floor: int) -> str:
    if total == 0:
        return "zero"
    s = sum(b for _, b in legs)
    if s <= total:
        return "fits"
    share = _largest_remainder(total, legs)
    keep = [(oid, b) for oid, b in legs if share[oid] >= floor]
    if len(keep) == len(legs):
        return "prop"
    if not keep:
        return "none_held"
    if sum(b for _, b in keep) <= total:
        return "SEPARATING"
    return "drop"


def _emit_closures(data_dir: Path, seed: int, closure: str, floor_hi: int) -> dict:
    rng = T.Rng(seed ^ 23)
    best, _ = _kept_records(data_dir)
    groups = {}
    for oid in sorted(best):
        rev, fname, r, wrap = best[oid]
        if r.kind != "length":
            continue
        groups.setdefault((SHARD_DISTRICT[fname], int(r.epoch)), []).append((oid, _basis(r)))
    keys = sorted(groups)
    plan = {}
    floors = {k: rng.randint(floor_hi * 3 // 5, floor_hi) for k in keys}
    if closure != "none":
        base = ["fits", "prop", "drop", "none_held", "zero", "drop", "prop", "fits",
                "drop", "prop", "zero", "drop"]
        off = rng.randint(0, len(keys) - 1)
        want = {k: base[(i + off) % len(base)] for i, k in enumerate(keys)}
        if closure == "sep":
            want[keys[rng.randint(0, len(keys) - 1)]] = "SEPARATING"
        for k in keys:
            legs = groups[k]
            s = sum(b for _, b in legs)
            w = want[k]
            if w == "prop":
                floors[k] = rng.randint(4, 11)
            floor = floors[k]
            if w == "zero":
                c = 0
            elif w == "fits":
                c = s + rng.randint(0, 900)
            elif w == "none_held":
                c = rng.randint(1, floor // 2)
            elif w == "SEPARATING":
                c = s - 1
                while classify(c, legs, floor) != "SEPARATING":
                    c -= 1
            else:
                lo, hi = (75, 99) if w == "prop" else (55, 75)
                c = s * rng.randint(lo, hi) // 100
                tries = 0
                while classify(c, legs, floor) != w:
                    c = s * rng.randint(40, 99) // 100
                    tries += 1
                    assert tries < 500, (k, w)
                # non-separating second pass must agree under both readings
                if w == "drop":
                    while distribute(c, legs, floor, "correct") != distribute(c, legs, floor, "reflex") \
                            or classify(c, legs, floor) != "drop":
                        c = s * rng.randint(40, 85) // 100
            got = classify(c, legs, floor)
            assert got == w, (k, w, got)
            plan[k] = c * (1 if rng.randint(0, 1) else -1)
    else:
        plan = {k: 0 for k in keys}
    rows = [["district", "epoch", "closure_micrometres", "floor_micrometres"]]
    for (d, e) in keys:
        rows.append([d, str(e), str(plan[(d, e)]), str(floors[(d, e)])])
    T._write_csv_rows(data_dir / CLOSURE_FILE,
                      "# scale_closure_register: signed scale closure per district and epoch.\n",
                      rows)
    return {k: classify(abs(plan[k]), groups[k], floors[k]) for k in keys}


def emit_r2(data_dir: Path, seed: int, closure="nonsep", chain="depth1",
            mislabel=0, floor=300) -> dict:
    FEATS.clear()
    FEATS.update(seed=seed, mislabel=mislabel)
    data_dir = Path(data_dir)
    T.emit_corpus(data_dir, seed)
    link = _emit_marks(data_dir, seed, chain)
    branches = _emit_closures(data_dir, seed, closure, floor)
    return {"branches": branches, "link": link}
