"""Parse QC reports, classify finding origins by diffing consecutive QC copies. Read-only on sources."""
import csv, json, re, subprocess, sys
from pathlib import Path

ROOT = Path("/Users/mac/Desktop/Terminal Bench")
REP = ROOT / "QC/reports"
COP = ROOT / "QC/copies"
OUT = ROOT / "master_chat_work/_dev_research/qc_loop_analysis/3b00450/_work"
KIT = ROOT / "Terminal_2.0_Harbor_Harness"

# slug -> [(version, sha|None, kit8, edit type that preceded this version)]
T = {
 "emberforge-vault-settlement": [(1,None,"bde868c4","build"),(2,None,"f3765e67","harden"),(3,"3e1ce87","3fb1650b","fix"),(4,"af89dd6","3fb1650b","fix"),(5,"67848e1","71a653b2","fix"),(6,"d9fa93e","71a653b2","harden"),(7,"6ec5e57","71a653b2","fix"),(8,"391ff22","71a653b2","fix"),(9,"a493fb2","976c1666","fix")],
 "dispatch-plan-reoptimization": [(1,"4ee264e","3fb1650b","build"),(2,"cc65d11","3fb1650b","fix"),(3,"582b437","71a653b2","fix"),(4,"3a23fca","71a653b2","fix"),(5,"2966bb2","71a653b2","fix"),(6,"c2cde12","71a653b2","fix"),(7,"31e7ead","976c1666","fix"),(8,"4f99dca","976c1666","fix")],
 "schema-migration-plan-repair": [(1,None,"bde868c4","build"),(2,None,"f3765e67","harden"),(3,"524fd48","3fb1650b","fix"),(4,"d3c6a83","3fb1650b","fix"),(5,"20508e3","71a653b2","fix"),(6,"e50ca11","71a653b2","fix+harden"),(7,"8f891ea","71a653b2","fix")],
 "match-replay-desync-audit": [(1,"ebf2870","71a653b2","build"),(2,"fba1605","71a653b2","fix"),(3,"fe8dec6","976c1666","fix"),(4,"54df6dc","976c1666","fix"),(5,"d6af3da","976c1666","fix"),(6,"a9d62f3","976c1666","fix"),(7,"cfb421c","5574d77e","fix")],
 "vendor-archive-roundtrip-recovery": [(1,None,"bde868c4","build"),(2,None,"f3765e67","harden"),(3,"1ccc9c0","3fb1650b","fix"),(4,"26b3948","3fb1650b","fix"),(5,"bddf20b","71a653b2","harden"),(6,"9bc33e6","71a653b2","fix")],
 "district-heat-flex-procurement": [(1,None,"bde868c4","build"),(2,None,"f3765e67","harden"),(3,"0b460a0","3fb1650b","fix"),(4,"53c71e3","71a653b2","harden"),(5,"2fd95f2","71a653b2","fix")],
 "cohort-retention-reconciliation": [(1,"982ad8c","3fb1650b","build"),(2,"4a276af","3fb1650b","fix"),(3,"3583d79","71a653b2","harden"),(4,"4089e5c","71a653b2","fix"),(5,"07206f4","71a653b2","fix")],
}
KITORDER = ["bde868c4","f3765e67","3fb1650b","71a653b2","976c1666","5574d77e"]
RULE = re.compile(r"(IN-L\d+|(?:IN|DS|TS|JD|AL|CL|COV|FC|DS)-\d+[a-z]?|F0[a-e]|STEP ?1[01]|Step 1[01]|EXEC-\d+|W-0\d-\d|\b[SXHKOATJ]\d{1,2}\b)")
FL = re.compile(r"([\w./-]+\.(?:md|py|toml|txt|json|jsonl|jsonc|conf|csv|yaml|yml|xml|sh|cfg|ini|tsv|parquet|xlsx))(?::L?|\s+L|\s+line\s+)(\d+)(?:-(\d+))?")
FNAME = re.compile(r"([\w./-]+\.(?:md|py|toml|txt|json|jsonl|jsonc|conf|csv|yaml|yml|xml|sh|cfg|ini|tsv))")
CONSIST = {"DS-22","AL-18","AL-19","TS-24","TS-14","DS-21","AL-17","DS-18"}
SEV = [("fail", ("❌", "fail")), ("minor", ("🟡", "minor")), ("warn", ("⚠️", "⚠", "warn"))]

def kit_changed_rules(a, b):
    ia, ib = KITORDER.index(a), KITORDER.index(b)
    if ib <= ia:
        return set()
    r = subprocess.run(["git", "-C", str(KIT), "diff", f"{a}..{b}", "--", "Input_Bundle_QC/"], capture_output=True, text=True).stdout
    ids = set()
    for line in r.splitlines():
        if line[:1] in "+-" and not line.startswith(("+++", "---")):
            ids |= set(m.group(1) for m in RULE.finditer(line))
    return ids

def findings(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = None
    for i, l in enumerate(lines):
        if re.match(r"^#{1,3}\s.*Findings", l):
            start = i; lvl = len(l) - len(l.lstrip("#")); break
    if start is None:
        return []
    out, cur = [], None
    for l in lines[start + 1:]:
        m = re.match(r"^(#{1,4})\s+(.*)", l)
        if m:
            h = m.group(2).lower()
            if len(m.group(1)) <= lvl or any(k in h for k in ("sign-off", "compared", "evidence", "consolidated")):
                if not any(k in h for k in ("fail", "minor", "warn")) or len(m.group(1)) <= lvl:
                    break
            for s, keys in SEV:
                if any(k in h for k in keys):
                    cur = s
            continue
        st = l.strip().strip("*:").lower()
        if st and len(st) < 40 and not re.match(r"^(?:\d+\.|[-*])\s", l.strip()):
            for s, keys in SEV:
                if any(k in st for k in keys):
                    cur = s
        if re.match(r"^\s{0,3}(?:\d+\.|[-*])\s", l) and not re.match(r"^\s*(?:\d+\.|[-*])\s+\**Fix", l):
            body = l.strip()
            head = body[:160]
            sev = None
            for s, keys in SEV:
                if keys[0] in head[:40] or (len(keys) > 1 and keys[1] in head[:40]):
                    sev = s; break
            sev = sev or cur
            rm = RULE.search(head)
            if not rm or not sev:
                continue
            fm = FL.search(body)
            fn = FNAME.search(body)
            gid = re.search(r"\b(G0\d-\d+)\b", head)
            out.append(dict(sev=sev, rule=rm.group(1).replace("Step ", "STEP").replace("STEP ", "STEP"),
                            file=(fm.group(1) if fm else (fn.group(1) if fn else "")),
                            line=(int(fm.group(2)) if fm else None), line2=(int(fm.group(3)) if fm and fm.group(3) else None),
                            text=re.sub(r"[*`]", "", body), gid=gid.group(1) if gid else None))
    return out

def locate(root, name):
    p = root / name
    if p.exists():
        return p
    base = Path(name).name
    hits = [q for q in root.rglob(base) if "__pycache__" not in q.parts]
    return hits[0] if hits else None

def changed_ranges(a, b):
    if a is None or b is None or not a.exists() or not b.exists():
        return None
    r = subprocess.run(["diff", "-U0", str(a), str(b)], capture_output=True, text=True, errors="replace").stdout
    rng = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", r, re.M):
        s = int(m.group(1)); n = int(m.group(2)) if m.group(2) is not None else 1
        rng.append((s, s + max(n, 1) - 1))
    return rng

def key(f):
    return (f["rule"], Path(f["file"]).name)

rows, stats = [], {}
for slug, vers in T.items():
    allf = {}
    for v, sha, kit, et in vers:
        allf[v] = findings(REP / slug / f"v{v}.md")
    for idx, (v, sha, kit, et) in enumerate(vers):
        prev = vers[idx - 1] if idx else None
        nxt = vers[idx + 1] if idx + 1 < len(vers) else None
        newrules = kit_changed_rules(prev[2], kit) if prev else set()
        for n, f in enumerate(allf[v], 1):
            fid = f["gid"] or f"F{n}"
            k = key(f)
            prevkeys = {key(x) for x in allf[prev[0]]} if prev else set()
            earlier = {key(x) for vv, *_ in vers[:max(idx - 1, 0)] for x in allf[vv]}
            ev = ""
            if not prev:
                origin, ev = "BASELINE", "first QC round; authored by build/harden"
            elif k in prevkeys and f["file"]:
                origin, ev = "REFLAG_KEPT", f"same rule on {k[1]} in v{prev[0]} (not cleared, kept or still open)"
            elif k in earlier and f["file"]:
                origin, ev = "REFLAG_FIXED", f"same rule on {k[1]} in an earlier round, absent in v{prev[0]}"
            else:
                ch = None
                if prev[1] and sha and (COP / prev[1] / slug).is_dir() and (COP / sha / slug).is_dir():
                    ra, rb = COP / prev[1] / slug, COP / sha / slug
                    pb = locate(rb, f["file"]) if f["file"] else None
                    pa = (ra / pb.relative_to(rb)) if pb else None
                    if pb is None:
                        ch = None
                    elif pa is not None and not pa.exists():
                        ch = True; ev = f"{pb.relative_to(rb)} new in {sha}"
                    else:
                        rng = changed_ranges(pa, pb)
                        if f["line"] is None:
                            ch = bool(rng); ev = f"{pb.relative_to(rb)} {'changed' if rng else 'unchanged'} {prev[1]}->{sha} (no line cited)"
                        else:
                            lo, hi = f["line"] - 2, (f["line2"] or f["line"]) + 2
                            hit = [r for r in rng if r[0] <= hi and r[1] >= lo]
                            ch = bool(hit)
                            ev = (f"hunk +{hit[0][0]}-{hit[0][1]} at cited {pb.relative_to(rb)}:{f['line']} ({prev[1]}->{sha})" if hit
                                  else f"cited {pb.relative_to(rb)}:{f['line']} not in any hunk {prev[1]}->{sha}")
                if f["rule"] in ("X1", "STEP10", "STEP11") and not ch:
                    ch = False
                if ch is False and f["rule"] in CONSIST and prev[1] and sha and (COP / prev[1] / slug).is_dir() and (COP / sha / slug).is_dir():
                    d = subprocess.run(["diff", "-rq", "-x", "__pycache__", str(COP / prev[1] / slug / "tests"), str(COP / sha / slug / "tests")], capture_output=True, text=True).stdout
                    d += subprocess.run(["diff", "-rq", "-x", "__pycache__", str(COP / prev[1] / slug / "solution"), str(COP / sha / slug / "solution")], capture_output=True, text=True).stdout
                    if d.strip():
                        ch = True
                        ev += "; consistency rule: cited text unchanged but tests/ or solution/ changed under it this round"
                if f["rule"] in ("TS-23", "A3") and ch:
                    origin = "RULE_CONFLICT"; ev += "; check count grew from splits/added checks (TS-13/TS-20/AL-2/CL-4 fixes) vs A3 cap 35"
                elif ch:
                    origin = "HARDEN_CAUSED" if "harden" in et else "FIX_CAUSED"
                    if et == "fix+harden":
                        ev += "; preceding round had both P12 fix and P9 harden"
                elif ch is False:
                    origin = "NEW_RULE" if f["rule"] in newrules else "MISSED_EARLIER"
                    if origin == "NEW_RULE":
                        ev += f"; kit {prev[2]}->{kit} edited {f['rule']} text"
                else:
                    if f["rule"] in newrules:
                        origin = "NEW_RULE"; ev = f"kit {prev[2]}->{kit} edited {f['rule']} text; no copy diff"
                    else:
                        origin = "HARDEN_CAUSED" if "harden" in et else "FIX_CAUSED"
                        ev = f"UNVERIFIED: no QC copy for v{prev[0]} or file not located; attributed to preceding {et} round"
            if nxt:
                nk = {key(x) for x in allf[nxt[0]]}
                res = "still-open" if k in nk else "fixed"
            else:
                res = "last-round"
            rows.append(dict(task=slug, qc_version=f"v{v}", qc_sha=sha or "", finding_id=fid, rule_id=f["rule"], severity=f["sev"],
                             file_line=f"{f['file']}:{f['line'] or ''}" if f["file"] else "", summary=f["text"][:120], origin=origin,
                             cause_evidence=ev[:250], resolution_next_round=res, caused_new_finding="n", _file=Path(f["file"]).name, _v=v))
# caused_new_finding: fixed finding whose file hosts a FIX_CAUSED/RULE_CONFLICT finding next round
for r in rows:
    if r["resolution_next_round"] != "fixed" or not r["_file"]:
        continue
    nx = [x for x in rows if x["task"] == r["task"] and x["_v"] == r["_v"] + 1 and x["_file"] == r["_file"] and x["origin"] in ("FIX_CAUSED", "RULE_CONFLICT")]
    if nx:
        r["caused_new_finding"] = "y:" + ",".join(f"v{x['_v']} {x['finding_id']} {x['rule_id']}" for x in nx)[:120]

cols = ["task","qc_version","qc_sha","finding_id","rule_id","severity","file_line","summary","origin","cause_evidence","resolution_next_round","caused_new_finding"]
with open(OUT / "auto_findings.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_MINIMAL)
    w.writeheader(); w.writerows(rows)
# count check vs result json
for slug, vers in T.items():
    for v, sha, kit, et in vers:
        got = [r for r in rows if r["task"] == slug and r["_v"] == v]
        c = {s: sum(1 for r in got if r["severity"] == s) for s in ("fail", "minor", "warn")}
        txt = (REP / slug / f"v{v}.md").read_text(errors="replace")
        m = re.search(r"Verdict[^\n]*?(\d+)\s*fails?[^\n]*?(\d+)\s*minors?[^\n]*?(\d+)\s*warns?", txt) or re.search(r"Verdict[^\n]*?❌\s*(\d+)[^\n]*?🟡\s*(\d+)[^\n]*?⚠️\s*(\d+)", txt)
        exp = tuple(int(x) for x in m.groups()) if m else None
        flag = "" if exp == (c["fail"], c["minor"], c["warn"]) else f" MISMATCH expected {exp}"
        orig = {}
        for r in got:
            orig[r["origin"]] = orig.get(r["origin"], 0) + 1
        print(f"{slug[:12]} v{v} {et:10} F/M/W {c['fail']}/{c['minor']}/{c['warn']}{flag} {orig}")
