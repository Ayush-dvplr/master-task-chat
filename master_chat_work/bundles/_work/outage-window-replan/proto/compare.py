#!/usr/bin/env python3
"""Compare a candidate output dir with a reference output dir, document by document.
python3 compare.py <ref_dir> <cand_dir>"""
import json
import os
import sys

DOCS = ["policy_audit.json", "summary.json", "data_quality.json", "region_North.json", "region_South.json",
        "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json"]


def first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return path, a, b
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s" % (path, k), a.get(k, "<missing>"), b.get(k, "<missing>")
            r = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if r:
                return r
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            r = first_diff(x, y, "%s[%d]" % (path, i))
            if r:
                return r
        if len(a) != len(b):
            return "%s.len" % path, len(a), len(b)
        return None
    return None if a == b else (path, a, b)


def main():
    ref, cand = sys.argv[1], sys.argv[2]
    ok = 0
    for d in DOCS:
        try:
            with open(os.path.join(cand, d)) as fh:
                c = json.load(fh)
        except (OSError, ValueError) as exc:
            print("%-26s MISSING/BAD %s" % (d, exc))
            continue
        with open(os.path.join(ref, d)) as fh:
            r = json.load(fh)
        diff = first_diff(r, c)
        if diff:
            print("%-26s DIFF %s ref=%s got=%s" % (d, diff[0], json.dumps(diff[1])[:80], json.dumps(diff[2])[:80]))
        else:
            ok += 1
            print("%-26s EXACT" % d)
    print("EXACT %d/%d" % (ok, len(DOCS)))


if __name__ == "__main__":
    main()
