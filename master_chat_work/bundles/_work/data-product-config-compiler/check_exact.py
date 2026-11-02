"""Independent recompute of the delivered documents plus policy invariants and override-removal probes.

usage: python3 -B check_exact.py <data dir> <out dir> [hidden_seed]
"""
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK))
from gen_core import gen_corpus  # noqa: E402
from ref_core import REF_INPUTS, ref_compute  # noqa: E402


def first_diff(want, got, path="$"):
    if type(want) is not type(got):
        return f"{path}: type {type(want).__name__} != {type(got).__name__}"
    if isinstance(want, dict):
        for key in sorted(set(want) | set(got)):
            if key not in got or key not in want:
                return f"{path}.{key}: present only on one side"
            found = first_diff(want[key], got[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(want, list):
        if len(want) != len(got):
            return f"{path}: length {len(want)} != {len(got)}"
        for i, (a, b) in enumerate(zip(want, got)):
            found = first_diff(a, b, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if want == got else f"{path}: {want!r} != {got!r}"


def invariants(files, docs):
    quotas = json.loads(files["cluster_quota.json"])
    config = docs["config.json"]["products"]
    assert sum(p["quota"] for p in config.values()) == quotas["shared"]
    for env in ("dev", "prod"):
        prof = docs[f"profile_{env}.json"]["products"]
        assert sum(p["quota"] for p in prof.values()) == quotas[env]
        assert set(prof) == {pid for pid, p in config.items() if p["status"] == "active"}
    for pid, p in config.items():
        if p["status"] == "retired":
            assert p["settings"] is None and p["team"] is None and p["quota"] == 0, pid
        elif p["status"] == "orphaned":
            assert p["team"] is None and p["quota"] == 0 and p["settings"] is not None, pid
        else:
            assert p["team"] is not None and set(p["settings"]) >= {"weight", "replicas", "pii_scan"}, pid
    reasons = {r["reason"] for r in docs["validation_report.json"]["rejected_overrides"]}
    assert reasons <= {"unknown_product", "unknown_key", "type", "bounds"}, reasons
    seqs = [r["seq"] for r in docs["validation_report.json"]["rejected_overrides"] if "seq" in r]
    assert seqs == sorted(seqs)


def probes(files, docs):
    """Removing each correction mechanism must move graded figures."""
    log = b"".join(line + b"\n" for line in files["deprecation.log"].splitlines() if b" RETIRE " not in line)
    no_retire = ref_compute(dict(files, **{"deprecation.log": log}))
    assert no_retire["config.json"] != docs["config.json"], "RETIRE events are inert"
    no_prod = ref_compute(dict(files, **{"product_overrides.jsonl": b""}))
    assert no_prod["config.json"] != docs["config.json"], "product overrides are inert"
    no_team = ref_compute(dict(files, **{"team_overrides.json": b"{}\n"}))
    assert no_team["config.json"] != docs["config.json"], "team overrides are inert"
    no_rules = ref_compute(dict(files, **{"selectors.rules": b""}))
    assert no_rules["config.json"] != docs["config.json"], "selectors are inert"
    print("probes: RETIRE, product overrides, team overrides and selectors each move config.json")


def main():
    data, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = {name: (data / name).read_bytes() for name in REF_INPUTS}
    want = ref_compute(files)
    bad = 0
    for name, doc in want.items():
        got = json.loads((out / name).read_text())
        diff = first_diff(doc, got)
        print(f"{name}: {'OK' if diff is None else diff}")
        bad += diff is not None
    invariants(files, want)
    probes(files, want)
    if len(sys.argv) > 3:
        hidden = gen_corpus(int(sys.argv[3]), 450, True, "2026-11-30", "2026.12-r1", ref_compute)
        invariants(hidden, ref_compute(hidden))
        probes(hidden, ref_compute(hidden))
    print("CHECK_EXACT", "PASS" if bad == 0 else f"FAIL {bad}")


if __name__ == "__main__":
    main()
