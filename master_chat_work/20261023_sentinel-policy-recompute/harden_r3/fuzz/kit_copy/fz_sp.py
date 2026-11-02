"""Differential fuzz driver for sentinel-policy-recompute; runs inside the verifier image.
usage: python3 fz_sp.py <cases.jsonl> <results.jsonl> <workers>   |  python3 fz_sp.py --one '<case json>'
Case: {"id","profile","seed","head":[[...10 fields...]] or null,"allowance":int|null,"corrupt":tenant|null,
       "risk":{id:v}|null,"windows":{id:[start,end,version]}|null,"struct":"none|renamed|cwdroot|keyshuffle|reindent|quotashuffle"}
Reference = T.reference_documents on a VARIANTS entry injected at runtime; windows mutation goes through T._CORPUS_FILES.
"""
import json, os, random, re, shutil, subprocess, sys, tempfile, time, zipfile
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, "/tests")
import test_output as T

PROGS = {"agent": "/progs/agent/tool.zip", "oracle": "/progs/oracle_out/tool.zip"}
_ROOTS = {}


def diffs(p, w, path="$", out=None):
    out = [] if out is None else out
    if isinstance(w, dict) and isinstance(p, dict):
        for k in list(w) + [k for k in p if k not in w]:
            if k not in p or k not in w:
                out.append((path + "." + k, "only-one"))
            else:
                diffs(p[k], w[k], path + "." + k, out)
        return out
    if isinstance(w, list) and isinstance(p, list):
        for i, (a, b) in enumerate(zip(p, w)):
            diffs(a, b, "%s[%d]" % (path, i), out)
        if len(p) != len(w):
            out.append((path, "len %d vs %d" % (len(p), len(w))))
        return out
    if p != w or type(p) is not type(w):
        out.append((path, "%r vs %r" % (p, w)))
    return out


def root(who):
    if who not in _ROOTS:
        r = Path(tempfile.mkdtemp(prefix="tool-%s-" % who))
        with zipfile.ZipFile(PROGS[who]) as zf:
            zf.extractall(r)
        T._grant_read(r)
        _ROOTS[who] = r
    return _ROOTS[who]


def base_files(case):
    T._CORPUS_FILES = None
    files = dict(T.corpus_files())
    if case.get("windows"):
        xml = ET.fromstring(files["effective_windows.xml"])
        for node in xml.iter("window"):
            if node.get("id") in case["windows"]:
                s, e, v = case["windows"][node.get("id")]
                node.set("start", str(s)); node.set("end", str(e)); node.set("version", v)
        files["effective_windows.xml"] = ET.tostring(xml, encoding="utf-8", xml_declaration=True)
    T._CORPUS_FILES = files
    return files


def run(who, corpus, cwd):
    out = Path(tempfile.mkdtemp(prefix="res-"))
    out.chmod(0o1777)
    cmd = T.untrusted_command([sys.executable, "-I", str(root(who) / "cli.py"), "resolve", "--data-dir", str(corpus), "--out", str(out)])
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60,
                           env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
        code, err = p.returncode, (p.stderr or p.stdout)[-300:]
    except subprocess.TimeoutExpired:
        code, err = -9, "timeout"
    docs = {}
    for d in T.RESOLVE_DOCS:
        try:
            docs[d] = json.loads((out / d).read_text())
        except Exception as e:  # noqa: BLE001 - missing or bad JSON is itself a finding
            docs[d] = "UNREADABLE %s" % type(e).__name__
    shutil.rmtree(out, ignore_errors=True)
    return code, err, round(time.time() - t0, 2), docs


def one(case):
    rec = {"id": case["id"], "profile": case["profile"], "struct": case.get("struct", "none")}
    name = "fz-" + case["id"]
    try:
        base_files(case)
        spec = {}
        if case.get("head") is not None:
            T.HIDDEN_HEADS[name] = [tuple(r) for r in case["head"]]
            spec["head"] = name
        if case.get("allowance") is not None:
            spec["allowance"] = case["allowance"]
        if case.get("corrupt"):
            spec["corrupt"] = case["corrupt"]
        if case.get("risk"):
            spec["risk"] = case["risk"]
        T.VARIANTS[name] = spec
        files, rows, stored, allowance = T.build_variant(name)
        want = T.reference_documents(name)
    except Exception as e:  # noqa: BLE001
        rec["gen_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        return rec
    rec["applied"] = want["dependency_trace.json"]["applied_overrides"]
    rec["ctl"] = want["dependency_trace.json"]["ledger_controls"]
    st = rec["struct"]
    rnd = random.Random(case["seed"])
    if st == "keyshuffle":
        doc = json.loads(files["override_deltas.json"])
        new = []
        for r in doc["overrides"]:
            ks = list(r); rnd.shuffle(ks); new.append({k: r[k] for k in ks})
        doc["overrides"] = new
        files["override_deltas.json"] = (json.dumps(doc) + "\n").encode()
    elif st == "reindent":
        doc = json.loads(files["override_deltas.json"])
        files["override_deltas.json"] = (json.dumps(doc, indent=4, sort_keys=False) + "\n").encode()
    elif st == "quotashuffle":
        q = files["quota_limits.cfg"].decode().split("\n")
        i = q.index("[override_allowance]")
        body = [l for l in q[i + 1:] if re.match(r"^t-", l)]
        rest = [l for l in q[i + 1:] if not re.match(r"^t-", l)]
        rnd.shuffle(body)
        files["quota_limits.cfg"] = "\n".join(q[:i + 1] + body + rest).encode()
    work = Path(tempfile.mkdtemp(prefix="sp-"))
    corpus = work / ("policy data (moved) ü" if st == "renamed" else "corpus")
    corpus.mkdir()
    for fn, payload in files.items():
        (corpus / fn).write_bytes(payload)
    T._grant_read(work)
    cwd = "/" if st == "cwdroot" else "/tmp"
    for who in ("agent", "oracle"):
        code, err, secs, docs = run(who, corpus, cwd)
        d = {}
        for doc in T.RESOLVE_DOCS:
            got = docs[doc]
            if doc == "dependency_trace.json" and isinstance(got, dict):
                got = {k: got[k] for k in T.TRACE_GRADED_KEYS if k in got}
            dd = diffs(got, want[doc]) if isinstance(got, dict) else [("$", got)]
            if dd:
                d[doc] = dd[:40]
        rec[who] = {"code": code, "err": err if code else "", "secs": secs, "diff": d}
    shutil.rmtree(work, ignore_errors=True)
    return rec


def main():
    if sys.argv[1] == "--one":
        print(json.dumps(one(json.loads(sys.argv[2])), indent=1))
        return
    cases = [json.loads(l) for l in open(sys.argv[1])]
    done = set()
    if os.path.exists(sys.argv[2]):
        done = {json.loads(l)["id"] for l in open(sys.argv[2]) if l.strip()}
    todo = [c for c in cases if c["id"] not in done]
    with Pool(int(sys.argv[3])) as pool, open(sys.argv[2], "a") as fh:
        for rec in pool.imap_unordered(one, todo):
            fh.write(json.dumps(rec) + "\n"); fh.flush()


if __name__ == "__main__":
    main()
