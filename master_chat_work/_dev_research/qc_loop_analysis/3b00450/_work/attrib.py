"""Attribute FIX_CAUSED rows to prompts, tag edit pattern, and compute per-round difficulty deltas from QC copies."""
import csv, re, subprocess, os, difflib
from pathlib import Path
exec(open(Path(__file__).with_name("classify.py")).read().split("KITORDER")[0])

PR = ROOT / "master_chat_tasks/prompts/issued"

def mt(p):
    return os.stat(p).st_mtime

def prompts_between(slug, v):
    a = mt(REP / slug / f"v{v-1}.md"); b = mt(REP / slug / f"v{v}.md")
    out = []
    for p in sorted((PR / slug).glob("*.md")):
        if re.search(r"_qc|P11|probe|_go|blind|_run|IDEA|P13|P14|_note", p.name):
            continue
        if a <= mt(p) <= b:
            out.append(p)
    return out

def fix_lines(slug, v):
    t = (REP / slug / f"v{v}.md").read_text(errors="replace")
    return [l.strip() for l in t.splitlines() if "Fix:" in l or "Fix " in l[:12]]

def overlap(a, b):
    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size

rows = list(csv.DictReader(open(OUT / "auto_findings.csv")))
for r in rows:
    r["prompt_attrib"] = ""; r["pattern"] = ""
    if r["origin"] not in ("FIX_CAUSED", "HARDEN_CAUSED", "RULE_CONFLICT"):
        continue
    v = int(r["qc_version"][1:]); slug = r["task"]
    fname = Path(r["file_line"].split(":")[0]).name if r["file_line"] else ""
    ps = prompts_between(slug, v)
    hit = None
    for p in ps:
        for i, l in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if fname and fname in l and re.search(r"\b(FIX|F\d+|fix|change|replace|add|split|move|drop|delete|set|rewrite|reword)\b", l):
                hit = (p, i, l.strip()); break
        if hit:
            break
    if hit:
        fx = fix_lines(slug, v - 1)
        cp = max((overlap(hit[2][:600], f[:600]) for f in fx), default=0)
        r["prompt_attrib"] = f"prompt-asked {hit[0].name}:{hit[1]}" + (f" (copies QC v{v-1} Fix text, {cp}-char overlap)" if cp >= 40 else "")
    else:
        r["prompt_attrib"] = "session own choice (no direction naming " + (fname or "the file") + " in " + ",".join(p.name for p in ps) + ")"
    # edit pattern from the diff hunk
    prev = T[slug][v - 2][1]; sha = T[slug][v - 1][1]
    pat = []
    if prev and sha and (COP / prev / slug).is_dir() and (COP / sha / slug).is_dir() and fname:
        hits = [q for q in (COP / sha / slug).rglob(fname) if "__pycache__" not in q.parts]
        if hits:
            q = hits[0]; pq = COP / prev / slug / q.relative_to(COP / sha / slug)
            d = subprocess.run(["diff", "-U0", str(pq), str(q)], capture_output=True, text=True, errors="replace").stdout if pq.exists() else "+new file"
            ch = [l for l in d.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
            txt = "\n".join(ch)
            if re.search(r"weight\s*=", txt): pat.append("weight change")
            if re.search(r"^\+\s*(def test_|@criterion|criteria\.)", txt, re.M): pat.append("added/split check")
            if re.search(r"^-\s*(def test_|@criterion|criteria\.)", txt, re.M): pat.append("removed/merged check")
            if re.search(r"^\+.*assert", txt, re.M): pat.append("assert added/moved")
            if fname == "judge.toml" and re.search(r"description", txt): pat.append("criterion reworded")
            if fname == "judge.toml" and re.search(r'^[-+]id = ', txt, re.M): pat.append("renumbered")
            if fname.endswith((".md", ".txt", ".conf")) and not pat: pat.append("doc/spec sentence edited")
            if not pat and ch: pat.append("other code/data edit")
    r["pattern"] = ";".join(pat) or ("unknown (no copy)" if not (prev and sha) else "consistency (cited text unchanged)")

cols = list(rows[0].keys())
with open(OUT / "auto_findings_attrib.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)

# difficulty deltas per round
def wsum(p):
    if not p.exists():
        return None
    t = p.read_text(errors="replace")
    ws = [float(x) for x in re.findall(r"criteria\.\w+\(weight=(-?[\d.]+)\)", t)]
    return (len(ws), sum(w for w in ws if w > 0), sum(w for w in ws if w < 0))

def jsum(p):
    if not p.exists():
        return None
    t = p.read_text(errors="replace")
    ws = [float(x) for x in re.findall(r"^weight = (-?[\d.]+)", t, re.M)][1:] if t.count("[[criterion]]") < len(re.findall(r"^weight = ", t, re.M)) else [float(x) for x in re.findall(r"^weight = (-?[\d.]+)", t, re.M)]
    return (t.count("[[criterion]]"), sum(w for w in ws if w > 0), sum(w for w in ws if w < 0))

def nlines(a, b):
    if not (a.exists() and b.exists()):
        return "?"
    d = subprocess.run(["diff", "-U0", str(a), str(b)], capture_output=True, text=True, errors="replace").stdout
    return sum(1 for l in d.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))

with open(OUT / "difficulty_deltas.tsv", "w") as fh:
    fh.write("task\tround\tedit\ttests(n,pos,neg)\tjudge(n,pos,neg)\ttest_output_lines\tjudge_lines\tinstruction_lines\tdata_files_changed\tsolution_lines\n")
    for slug, vers in T.items():
        for i in range(1, len(vers)):
            (pv, ps, _, _), (v, s, _, et) = vers[i - 1], vers[i]
            if not (ps and s and (COP / ps / slug).is_dir() and (COP / s / slug).is_dir()):
                fh.write(f"{slug}\tv{pv}->v{v}\t{et}\tno copy\n"); continue
            A, B = COP / ps / slug, COP / s / slug
            dd = subprocess.run(["diff", "-rq", "-x", "__pycache__", str(A / "environment"), str(B / "environment")], capture_output=True, text=True).stdout
            nd = sum(1 for l in dd.splitlines() if l.strip())
            sl = sum(nlines(A / "solution" / f, B / "solution" / f) if isinstance(nlines(A / "solution" / f, B / "solution" / f), int) else 0 for f in ("solve.py", "TRUTH.md", "solve.sh"))
            fh.write(f"{slug}\tv{pv}->v{v}\t{et}\t{wsum(A/'tests/test_output.py')}->{wsum(B/'tests/test_output.py')}\t{jsum(A/'tests/judge.toml')}->{jsum(B/'tests/judge.toml')}\t{nlines(A/'tests/test_output.py', B/'tests/test_output.py')}\t{nlines(A/'tests/judge.toml', B/'tests/judge.toml')}\t{nlines(A/'instruction.md', B/'instruction.md')}\t{nd}\t{sl}\n")
print("ok")
