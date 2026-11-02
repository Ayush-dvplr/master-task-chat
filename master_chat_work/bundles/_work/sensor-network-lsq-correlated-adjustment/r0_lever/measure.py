"""R0 lever measurement (868afdf). Runs inside Docker (python:3.12-slim).

usage: python3 measure.py BUNDLE PROGDIR RUNDIR VARIANT[,VARIANT...] PROG[,PROG...]

For each variant: regenerate the three hidden extracts with the bundle's own
generator, optionally writing one text field as an RFC 4180 quoted field (same
value) in every third data row of the chosen delimited shards; derive the
verifier reference; run each program; grade with the bundle's own checks.
"""
import csv
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import time
import types
from pathlib import Path

BUNDLE, PROGDIR, RUNDIR = (Path(a) for a in sys.argv[1:4])
VARIANTS = sys.argv[4].split(",")
PROGS = sys.argv[5].split(",")

# rewardkit stub (the verifier image installs harbor-rewardkit)
rk = types.ModuleType("rewardkit")


class _Crit:
    def __getattr__(self, name):
        return lambda **kw: None


rk.criteria = _Crit()
rk.criterion = lambda **kw: (lambda f: f)
sys.modules["rewardkit"] = rk
spec = importlib.util.spec_from_file_location("T", BUNDLE / "tests" / "test_output.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

ORIG_WRITE_CSV = T.write_csv
HEADER = ["obs_id", "kind", "observed_value", "computed_nominal", "apriori_sigma",
          "unit", "sigma_kind", "dir", "partials", "epoch", "region"]
KEYS = ["oid_field", "kind", "value", "nominal", "sigma", "unit", "sigma_kind",
        "direction", "coeffs", "epoch", "region"]

# variant -> (quoted header field, delimiters that get quoting, swap north/south sigma kind)
VDEF = {
    "plain": (None, (), False),
    "sk_csv": ("sigma_kind", (",",), False),
    "sk_csv_tsv": ("sigma_kind", (",", "\t"), False),
    "sk_csv_swap": ("sigma_kind", (",",), True),
    "plain_swap": (None, (), True),
    "dir_csv": ("dir", (",",), False),
    "kind_csv": ("kind", (",",), False),
    "unit_csv": ("unit", (",",), False),
    "id_csv": ("obs_id", (",",), False),
    "epoch_csv": ("epoch", (",",), False),
    "region_csv": ("region", (",",), False),
    "skdir_csv": ("sigma_kind+dir", (",",), False),
    "rng_csv": ("*", (",",), False),
    "rngtext_csv": ("~", (",",), False),
}


def _minimal(v, d):
    return '"' + v.replace('"', '""') + '"' if any(c in v for c in (d, '"', "\n", "\r")) else v


def quoting_writer(field, delims):
    import random
    TEXT = {HEADER.index(f) for f in ("obs_id", "kind", "unit", "sigma_kind", "dir", "region")}
    cols = {} if field in "*~" else {HEADER.index(f): n for n, f in enumerate(field.split("+"))}

    def write_csv(recs, header_note, delimiter=","):
        if delimiter not in delims:
            return ORIG_WRITE_CSV(recs, header_note, delimiter)
        out = [header_note, delimiter.join(HEADER) + "\n"]
        rng = random.Random(len(recs) * 7919 + sum(map(ord, header_note)))
        for i, r in enumerate(recs):
            cells = [str(r[k]) for k in KEYS]
            line = []
            for j, v in enumerate(cells):
                if (field == "*" and rng.random() < 0.2) or (field == "~" and j in TEXT and rng.random() < 0.2) or (j in cols and i % 3 == (1 + cols[j]) % 3):
                    line.append('"' + v.replace('"', '""') + '"')
                else:
                    line.append(_minimal(v, delimiter))
            out.append(delimiter.join(line) + "\n")
        return "".join(out).encode("utf-8")
    return write_csv


ORIG_VARIANTS = json.loads(json.dumps({k: v["shard_plan"] for k, v in T.CORPUS_VARIANTS.items()}))


def set_variant(name):
    field, delims, swap = VDEF[name]
    T.write_csv = quoting_writer(field, delims) if field else ORIG_WRITE_CSV
    for seed in (T.CHALLENGE_SEED, T.EVAL_SEED):
        plan = [tuple(x) for x in ORIG_VARIANTS[str(seed)]]
        if swap:
            n, s = list(plan[0]), list(plan[1])
            n[4], s[4] = s[4], n[4]
            plan[0], plan[1] = tuple(n), tuple(s)
        T.CORPUS_VARIANTS[seed]["shard_plan"] = plan


def tree_digest(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(d).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:12]


def ref_digest(ref) -> str:
    keys = ["vtpv", "sigma0_sq", "dof", "n_obs", "x", "residuals", "weights_final", "flags", "verdict"]
    return hashlib.sha256(repr([ref.get(k) for k in keys]).encode()).hexdigest()[:12]


HIDDEN_TESTS = [n for n in dir(T) if n.startswith("test_") and any(
    n.startswith(f"test_{e}_") for e in ("challenge", "eval", "audit"))] + [
    "test_control_values_on_hidden_extracts", "test_superseded_records_on_hidden_extracts",
    "test_canonical_serialization_on_hidden_extracts"]


def weight_of(test_name):
    src = (BUNDLE / "tests" / "test_output.py").read_text()
    crit = test_name[len("test_"):]
    for ln in src.splitlines():
        if ln.startswith(f"criteria.{crit}(weight="):
            return int(ln.split("weight=")[1].rstrip(")"))
    raise KeyError(crit)


WEIGHTS = {t: weight_of(t) for t in HIDDEN_TESTS}
RUNDIR.mkdir(parents=True, exist_ok=True)

for vname in VARIANTS:
    set_variant(vname)
    vdir = RUNDIR / vname
    roots, refs, meta = {}, {}, {}
    for ext, seed in T.HIDDEN_SEEDS.items():
        root = vdir / ext / "data"
        root.mkdir(parents=True, exist_ok=True)
        T.emit_corpus(root, seed)
        t0 = time.perf_counter()
        refs[ext] = T.solve(root)
        meta[ext] = {"verifier_ref_seconds": round(time.perf_counter() - t0, 2),
                     "ref_digest": ref_digest(refs[ext]), "data_digest": tree_digest(root)}
        roots[ext] = root
    result = {"variant": vname, "extracts": meta, "programs": {}}
    for prog in PROGS:
        pr = {"runs": {}, "tests": {}}
        for ext in T.HIDDEN_SEEDS:
            out = vdir / ext / f"out_{prog}"
            out.mkdir(parents=True, exist_ok=True)
            t0 = time.perf_counter()
            try:
                cp = subprocess.run([sys.executable, str(PROGDIR / f"{prog}.py"), str(roots[ext]), str(out)],
                                    capture_output=True, text=True, timeout=120, cwd="/tmp")
                code, err = cp.returncode, cp.stderr[-400:]
            except subprocess.TimeoutExpired:
                code, err = -9, "TIMEOUT"
            pr["runs"][ext] = {"code": code, "seconds": round(time.perf_counter() - t0, 2),
                               "out_digest": tree_digest(out), "stderr_tail": err if code else ""}
            T._HIDDEN_CACHE[ext] = {"root": roots[ext], "out": out, "code": code, "ref": refs[ext]}
        pts = 0
        for t in HIDDEN_TESTS:
            try:
                getattr(T, t)()
                ok, why = True, ""
            except Exception as e:  # graded as a failure, reason kept
                ok, why = False, f"{type(e).__name__}: {str(e)[:160]}"
            pr["tests"][t] = {"pass": ok, "w": WEIGHTS[t], "why": why}
            pts += WEIGHTS[t] if ok else 0
        pr["hidden_points"] = pts
        pr["hidden_points_max"] = sum(WEIGHTS.values())
        result["programs"][prog] = pr
        T._HIDDEN_CACHE.clear()
        print(vname, prog, pts, {e: r["code"] for e, r in pr["runs"].items()},
              {e: r["seconds"] for e, r in pr["runs"].items()}, flush=True)
    (RUNDIR / f"{vname}.json").write_text(json.dumps(result, indent=1, sort_keys=True))
print("ALL_DONE", flush=True)
