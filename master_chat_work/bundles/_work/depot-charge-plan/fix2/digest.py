"""Per-check digest: sha of the criterion block text plus sha of the expected document the
check compares against (reference run on its data). Usage (in Docker, rewardkit image):
python3 -B digest.py /tests/test_output.py > digest.txt"""
import hashlib
import importlib.util
import json
import re
import sys

path = sys.argv[1]
src = open(path).read()
spec = importlib.util.spec_from_file_location("t", path)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def h(x):
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()[:12]


def doc_sha(tree, name):
    return h(json.dumps(t._expected(tree)[name], sort_keys=True))


blocks = re.findall(r"@criterion\(description=.*?\)\ndef (\w+)\(workspace: Path\) -> bool:\n    return _holds\(([^\n]*)\)\n", src)
regs = dict(re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", src))
trees = {}


def tree(key):
    if key not in trees:
        if key == "shipped":
            trees[key] = t._write_tree(t._shipped_files())
        else:
            seed, kind = t._FRESH[key]
            trees[key] = t._fresh_tree(seed, kind)
    return trees[key]


for name, call in blocks:
    block = re.search(r"@criterion\(description=.*?\)\ndef %s\(.*?\n.*?\n" % name, src).group(0)
    args = [a.strip().strip("'\"") for a in call.split(",")]
    fn = args[0]
    exp = "-"
    if fn == "_check_delivered":
        exp = doc_sha(tree("shipped"), args[1])
    elif fn == "_check_fresh":
        exp = doc_sha(tree(args[1]), args[2])
    elif fn == "_check_relocated":
        key = "rel" if "rel" in t._FRESH else "h3"
        exp = doc_sha(tree(key), "summary.json")
    elif fn in ("_check_flagless", "_check_default_paths"):
        exp = doc_sha(tree("dflt"), "summary.json")
    elif fn == "_check_altered":
        exp = "altered:" + h(json.dumps(t._altered.__code__.co_consts, default=str))
    body = src.split("def %s(" % fn, 1)[1].split("\ndef ", 1)[0] if ("def %s(" % fn) in src else ""
    print("%-48s w=%-3s block=%s check_fn=%s expected=%s" % (name, regs.get(name), h(block), h(body), exp))
# extra: summary of each hidden tree's data_quality reasons (AL-27 / DS-20 coverage)
for key in ["shipped"] + sorted(t._FRESH):
    e = t._expected(tree(key))
    reasons = {}
    for r in e["data_quality.json"]["rejected"]:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    s = e["summary.json"]
    print("TREE %s rejected=%s changed=%s short=%s" % (key, reasons, s["buses_changed"], s["buses_short"]))
