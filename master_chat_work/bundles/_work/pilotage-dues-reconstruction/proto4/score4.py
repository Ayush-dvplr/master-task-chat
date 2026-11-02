"""Prototype scorer (proto only). usage: score4.py TRUTH.json REF_OUT MODE_OUT LABEL
Checks the reference against generator truth, then scores a mode per station:
a station is exact when its region file and its policy_audit rows equal the reference."""
import json
import os
import sys


def load(d, n):
    p = os.path.join(d, n)
    return json.load(open(p)) if os.path.isfile(p) else None


def main():
    truth, ref, out, label = sys.argv[1:5]
    t = json.load(open(truth))
    bad = []
    for s in t["stations"]:
        reg = load(ref, f"region_{s['station']}.json")
        for k, per in enumerate(reg["periods"]):
            want = None if s["ambiguous"][k] else s["tariffs"][k]
            got = per["tariff"]
            if got is not None:
                got = [round(float(got[x]) * 100) for x in
                       ("per_100_tonnes", "per_tenth", "surcharge_factor", "per_tug")]
            if got != want:
                bad.append((s["station"], k, got, want))
    ra = load(ref, "policy_audit.json")["rows"]
    oa = (load(out, "policy_audit.json") or {"rows": []})["rows"]
    kept = 0
    detail = []
    for s in t["stations"]:
        st = s["station"]
        ok = load(ref, f"region_{st}.json") == load(out, f"region_{st}.json") and \
            [r for r in ra if r["station"] == st] == [r for r in oa if r["station"] == st]
        kept += ok
        detail.append(f"{st}:{'EXACT' if ok else 'WRONG'}")
    others = all(load(ref, n) == load(out, n) for n in
                 ("summary.json", "segment_commercial.json", "segment_public.json", "data_quality.json"))
    print(f"SCORE {label} ref_vs_truth={'OK' if not bad else bad} stations_kept={kept}/4 "
          f"{' '.join(detail)} totals_equal={others}")


if __name__ == "__main__":
    main()
