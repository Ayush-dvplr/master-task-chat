#!/usr/bin/env python3
"""template_check.py: keep prompt templates current (W1-032 draft for P10, standard library only, read only).

  template_check.py [--root MASTER_CHAT_TASKS] [--manifest CURRENT.json] [--settings settings.json]
                    [--all] [--max-rows N] [--json]

What it checks
  1 manifest   every file in prompts/templates/ is named in the manifest (current or history), every
               current file exists, and nothing names two current versions of one family.
  2 pointers   README.md, knowledge/INDEX.md, auto/AUTO_POLICY.md, auto/auto.py and tools/issue.py name
               only the current version of each family (a "P12 v4" where the manifest says v5 is stale).
  3 templates  each current template (active ones; --all adds dormant ones) is scanned line by line for
               SETTING   a hard coded value that settings.json owns (gate, design margin, counts, oracle
                         runs, Docker limits, time limit factor, runs per task);
               RETIRED   a term or number the rules in force retired (shapes, hardness sources, old gates,
                         blinds before QC, round caps, QC-safe wording, misread levers as extras, timeout
                         as primary, no size bound, holes list, kill rule parking, J1 and J4 wording);
               POINTER   a pointer to a superseded file (older template, LEVER_RULES_vN, playbook G1-G7).
Exit 0 when nothing is found, 1 otherwise. It never writes anything.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILY_RE = re.compile(r"^(_COMMON_RULES|P\d+|QL_REPLY)")
VER_RE = re.compile(r"_v(\d+)(?:_[\w.]+)?\.md$")

# Settings keys the rules say live in settings.json. "path" is looked up in settings.json; when the key
# is absent the finding says so (the draft settings.json does not carry every key yet).
SETTING_KEYS = {
    "gate": ("gate", "RIF GATE R26, R27"),
    "design_margin": ("design_margin", "BUILD_RULES DESIGN.md, FOLD_DECISIONS T20"),
    "counts": ("counts", "RIF CAPS R15"),
    "no_core_keep_pct": ("no_core_keep_pct", "BUILD_RULES LEVERS NO CORE"),
    "oracle_runs": ("oracle_runs", "BUILD_RULES LIMITS, FOLD_DECISIONS T46"),
    "docker": ("docker", "RIF DOCKER AND COST R19 to R24"),
    "time_limit_factor": ("time_limit_factor", "BUILD_RULES LIMITS, FOLD_DECISIONS T43"),
    "runs_per_task": ("runs_per_task", "FOLD_DECISIONS T33"),
}

# (code, kind, regex, rule it breaks, proposed direction)
RULES = [
    ("SHAPE", "RETIRED", r"\bShape [BD]\b|\bSHAPE\b|design shapes?\b|shapes? B (?:and|or) D|\(B breadth|B\|D",
     "FOLD_DECISIONS T1 DROP", "primary lever from a PATTERNS.md DESIGN family (BUILD_RULES LEVERS)"),
    ("SOURCES", "RETIRED", r"HARDNESS SOURCES|[Hh]ardness sources?\b|S1-S11|\bS1 or S2\b|S3, S5, S6|S7-S11|S3/S5/S6",
     "FOLD_DECISIONS T1, T3", "PRIMARY LEVER (PATTERNS family) plus extras; misread rule levers under CR7"),
    ("OLDGATE", "RETIRED", r"tests\s*<\s*100|tests 100\b|final (?:reward )?(?:is )?above 70|final[^.\n]{0,30}>\s*70|overall\s*<\s*70|final stays below 60|\b2 valid runs\b|on 2 of 3\b|final between 65 and 75",
     "RIF GATE R26, R27", "gate from settings.json, 1 run of frozen QC passed bytes"),
    ("AIMS", "RETIRED", r"tests\s*<=\s*(?:60|65|75|80)\b|none above 70|probe mid\s*<=\s*20|>=\s*10% (?:of )?positive test points|>=\s*15% of lever points",
     "BUILD_RULES DESIGN.md (T20 only bar) and T45", "one bar: predicted final under gate.final minus design_margin"),
    ("CAP35", "RETIRED", r"(?:[Oo]ver|[Aa]bove|under|<=?|max(?:imum)?|at most)\s*35\b[^.\n]{0,25}(?:test|check|criteri|warn)|\b35/35\b|count cap option A|\b10-35\b|8-35\b",
     "RIF CAPS R15 (soft 70, hard 100)", "counts.soft_cap / counts.hard_cap from settings.json"),
    ("BLIND", "RETIRED", r"\b3 (?:fresh )?(?:P13 )?(?:v2 )?blind reads?|[Bb]lind bar|DESIGN BLIND READY|design-stage blind read|[Bb]lind reads? (?:before|with|add)|3 × P13|after 3 blind reads",
     "BUILD_RULES LIMITS T45", "blinds before QC not required; a blind is a diagnostic only"),
    ("BLINDLEVER", "RETIRED", r"every blind program|no blind program above|against [^.\n]{0,40}every blind program",
     "BUILD_RULES LEVERS CR2", "the lever is judged against the paid run program (the careful exact program)"),
    ("ROUNDS", "RETIRED", r"round \[\[ROUND\]\] of \d|ROUND LIMIT|ROUND_LIMIT|Stop after \d (?:harden|rebuild) rounds|max \d+ (?:P11 )?rounds|at most \d P12 rounds|refuses a third|no round after|marked LAST|max 2 fix rounds",
     "RIF CAPS R15, FOLD_DECISIONS T23", "no round caps; issue.py warns, never refuses"),
    ("QCSAFE", "RETIRED", r"QC-safe|\bbypass",
     "BUILD_RULES QC FIXES T22", "fix map row (FIX_MAP.md) that meets the check and keeps the hardness"),
    ("GUARD", "POINTER", r"G1-G7|QC_FIX_PLAYBOOK_v[123]",
     "RIF QC FIXES, FOLD_DECISIONS A7", "the fix map and BUILD_RULES QC FIXES and QC FIX STEPS"),
    ("MISREAD", "RETIRED", r"misread-rule levers are extras|misread[- ]rule levers? (?:are|as) extras?",
     "BUILD_RULES LEVERS CR7, FOLD_DECISIONS T3", "misread rule levers allowed under CR7"),
    ("TIMEOUT", "RETIRED", r"TIMEOUT/CRASH counts with no cap|scale TIMEOUT counts|timeout or crash loss counts|TIMEOUT or CRASH loss counts|v3\.5 hidden-scale",
     "BUILD_RULES LEVERS CR1", "timeout lever only an extra unless Ayush says so; a size bound may be stated (R30)"),
    ("SIZEBOUND", "RETIRED", r"[Nn]ever state a size|[Dd]o not state a size|stated size and runtime limits handed",
     "BUILD_RULES LEVERS R30", "a size bound may be stated for a timeout extra"),
    ("HOLES", "RETIRED", r"holes are not levers|holes list|hole from section 8",
     "BUILD_RULES LEVERS T11", "holes case by case with Ayush"),
    ("PARK", "RETIRED", r"park when|parks? the task|kill rule|redesign, never park, if",
     "RIF RUNS AND PUSH T34, BUILD_RULES T44", "no task is parked except on Ayush's word"),
    ("J1", "RETIRED", r"no figure criterion",
     "BUILD_RULES RUBRIC T42", "a what if figure criterion only when the instruction asks for it, at most 6, w <= 3"),
    ("J4", "RETIRED", r"behavioural code-quality|behavioural J4|J4 v3: every handler|exactly one behavioural",
     "BUILD_RULES RUBRIC T41", "one judgement wording, conduct label, w1 to 3"),
    ("REFLEX", "RETIRED", r"reflex gate|<=\s*0\.20|replay gate",
     "RIF ORDER T24 (gate is the paid run)", "drop; the paid run on frozen bytes decides"),
    ("LEVERRULES", "POINTER", r"LEVER_RULES_v\d|LEVER_RULES v\d|LEVER_RULES 1C|LEVER_RULES section",
     "RIF BUILD RULES (BUILD_RULES replaces LEVER_RULES_v3 text after PROCEED)", "cite BUILD_RULES.md by path"),
    ("ORACLE", "SETTING", r"[Oo]racle\s*[x×]\s*\d|oracle-1\s*\.\.\s*(?:oracle-)?\d|\b\d (?:oracle runs|oracle 1\.0)",
     "oracle_runs", "read oracle runs from settings.json"),
    ("DOCKER", "SETTING", r"--memory\s+\d+g|--cpus\s+\d+|--need-mb\s+\d+|\b4g\b",
     "docker", "read Docker limits from settings.json (or the S1 Docker room script)"),
    ("TIMEFACTOR", "SETTING", r"\b\d+x (?:the )?(?:oracle|reference)|<=\s*1/4 of the stated limit|90% of the stated verifier limit",
     "time_limit_factor", "time limit at least time_limit_factor x reference time, from settings.json"),
    ("RUNS", "SETTING", r"\b1 (?:new |harness |paid )?run on the frozen|\b1 harness run\b|\b1 new run\b",
     "runs_per_task", "runs per task per step from settings.json"),
]
GATE_RE = re.compile(r"\b(tests|rubric|final(?: reward)?|overall)\s*(<=|>=|<|>|≤)\s*(\d+)", re.I)
POINTER_RE = re.compile(r"\b(P\d{1,2})(?:_[a-z_]+?)?[_ ]v(\d+)\b|\b(_COMMON_RULES)(?:_v(\d+)|(?=\.md))")
# master notes that record history ("v4 changes ...", "Replaces v2 ...") are not instructions: skipped
HISTORY_RE = re.compile(r"^(?:# |v\d+[^ ]* (?:changes|in-place)|v\d+ \(|Changes from|Replaces|New \()")


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def family(name):
    m = FAMILY_RE.match(name)
    return m.group(1) if m else None


def derive_manifest(tdir):
    fams = defaultdict(list)
    for n in sorted(os.listdir(tdir)):
        if n.endswith(".md") and family(n) and "snapshot" not in n:
            v = VER_RE.search(n)
            fams[family(n)].append((int(v.group(1)) if v else 1, n))
    out = {}
    for f, vs in fams.items():
        vs.sort()
        out[f] = {"current": vs[-1][1], "status": "active", "history": [n for _, n in vs[:-1]]}
    return out


def gate_finding(m, settings):
    what, op, num = m.group(1).lower(), m.group(2), int(m.group(3))
    key = "final" if what.startswith(("final", "overall")) else what
    gate = (settings or {}).get("gate", {})
    margin = (settings or {}).get("design_margin")
    if op in ("<",) and gate.get(key) == num:
        return ("SETTING", "GATE", f"gate.{key} = {num} hard coded", "RIF GATE R26, R27", "read gate from settings.json")
    if key == "final" and op in ("<=", "≤") and margin is not None and gate.get("final", 0) - margin == num:
        return ("SETTING", "MARGIN", f"design bar {num} hard coded", "BUILD_RULES DESIGN.md T20",
                "predicted final under gate.final minus design_margin, both from settings.json")
    return None


def scan_line(line, settings):
    hits = []
    for m in GATE_RE.finditer(line):
        g = gate_finding(m, settings)
        if g:
            hits.append(g + (m.group(0),))
    for code, kind, rx, rule, direction in RULES:
        m = re.search(rx, line)
        if not m:
            continue
        if kind == "SETTING":
            key = rule
            sk, item = SETTING_KEYS[key]
            have = (settings or {}).get(sk)
            note = f"settings.{sk} = {json.dumps(have)}" if have is not None else f"settings.json has no '{sk}' key yet"
            hits.append(("SETTING", code, note, item, direction, m.group(0)))
        else:
            hits.append((kind, code, "", rule, direction, m.group(0)))
    return hits


def pointer_findings(root, manifest):
    cur = {}
    for f, d in manifest.items():
        if d.get("current"):
            v = VER_RE.search(d["current"])
            cur[f] = int(v.group(1)) if v else 1
    files = ["README.md", "knowledge/INDEX.md", "auto/AUTO_POLICY.md", "auto/auto.py", "tools/issue.py"]
    out = []
    for rel in files:
        p = os.path.join(root, rel)
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for m in POINTER_RE.finditer(line):
                fam = m.group(1) or m.group(3)
                ver = m.group(2) or m.group(4)
                ver = int(ver) if ver else 1
                if fam not in cur or ver == cur[fam]:
                    continue
                ctx = line[max(0, m.start() - 40):m.end() + 40].lower()
                if any(w in ctx for w in ("history", "superseded", "snapshot", "retired", "kept as", "v1 files kept", "not used", "stale")):
                    continue
                if ver < cur[fam]:
                    msg = f"{rel}:{i} names {m.group(0)} but the current {fam} is v{cur[fam]}"
                    if msg not in out:
                        out.append(msg)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.environ.get("MT_ROOT", "/home/user/master-task-chat/master_chat_tasks"))
    ap.add_argument("--manifest", default=None, help="templates/CURRENT.json (default: <root>/prompts/templates/CURRENT.json, else derived)")
    ap.add_argument("--settings", default=None, help="settings.json (default: <root>/settings.json)")
    ap.add_argument("--all", action="store_true", help="also scan dormant families")
    ap.add_argument("--max-rows", type=int, default=0, help="rows printed per template (0 = all)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    tdir = os.path.join(a.root, "prompts", "templates")
    mpath = a.manifest or os.path.join(tdir, "CURRENT.json")
    man = load(mpath)
    notes = []
    if man is None:
        notes.append(f"no manifest at {mpath}: current = highest version per family (derived)")
        fams = derive_manifest(tdir)
    else:
        fams = man["families"]
    settings = load(a.settings or os.path.join(a.root, "settings.json"), {}) or {}
    if not settings:
        notes.append("no settings.json found: SETTING rows cannot compare values")

    # 1 manifest coherence
    named = set()
    for f, d in fams.items():
        if d.get("current"):
            named.add(d["current"])
            if not os.path.isfile(os.path.join(tdir, d["current"])):
                notes.append(f"manifest: {f} current {d['current']} does not exist")
        named.update(d.get("history", []))
    for n in sorted(os.listdir(tdir)):
        if n.endswith(".md") and n not in named and n not in ("CHANGELOG.md", "CURRENT.json"):
            notes.append(f"manifest: {n} is in templates/ but not named in the manifest")

    # 2 pointers
    pointers = pointer_findings(a.root, fams)

    # 3 template scan
    report, per_t, skipped = [], {}, {}
    for f, d in fams.items():
        st = d.get("status", "active")
        if not d.get("current") or st == "retired" or (st == "dormant" and not a.all):
            continue
        name = d["current"]
        try:
            lines = open(os.path.join(tdir, name), encoding="utf-8").read().splitlines()
        except OSError:
            continue
        rows = []
        for i, line in enumerate(lines, 1):
            if HISTORY_RE.match(line):
                skipped[name] = skipped.get(name, 0) + 1
                continue
            for kind, code, note, rule, direction, text in scan_line(line, settings):
                rows.append({"file": name, "line": i, "kind": kind, "code": code, "text": text[:60],
                             "note": note, "rule": rule, "direction": direction, "status": st})
            # stale template pointers inside a current template
            for m in POINTER_RE.finditer(line):
                fam = m.group(1) or m.group(3)
                ver = int(m.group(2) or m.group(4) or 1)
                cur = fams.get(fam, {}).get("current")
                if not cur:
                    continue
                cv = VER_RE.search(cur)
                cv = int(cv.group(1)) if cv else 1
                if ver < cv:
                    rows.append({"file": name, "line": i, "kind": "POINTER", "code": "OLDTEMPLATE",
                                 "text": m.group(0), "note": f"current {fam} is v{cv}", "rule": "templates/CURRENT.json",
                                 "direction": f"point at {cur}", "status": st})
        per_t[name] = rows
        report.extend(rows)

    if a.json:
        print(json.dumps({"notes": notes, "pointers": pointers, "rows": report}, indent=1))
        return 1 if (report or pointers) else 0

    print(f"template_check.py  root={a.root}")
    print(f"manifest={mpath if man is not None else '(derived)'}  settings={a.settings or '(root)'}  scope={'active+dormant' if a.all else 'active'}")
    print()
    print("== 1 manifest")
    for n in notes or ["ok"]:
        print("  " + n)
    print("== 2 pointers to non current versions (README, INDEX, AUTO_POLICY, auto.py, issue.py)")
    for p in pointers or ["none"]:
        print("  " + p)
    print("== 3 current templates")
    total = Counter()
    for name, rows in per_t.items():
        c = Counter(r["kind"] for r in rows)
        lines_hit = len({r["line"] for r in rows})
        total.update(c)
        total["lines"] += lines_hit
        print(f"-- {name} [{fams[family(name)].get('status', 'active')}]  history lines skipped {skipped.get(name, 0)}  conflicting lines {lines_hit}  SETTING {c['SETTING']}  RETIRED {c['RETIRED']}  POINTER {c['POINTER']}")
        shown = rows if not a.max_rows else rows[:a.max_rows]
        for r in shown:
            extra = f" ({r['note']})" if r["note"] else ""
            print(f"   {r['file']}:{r['line']} {r['kind']} {r['code']} \"{r['text']}\"{extra} | {r['rule']} | {r['direction']}")
        if a.max_rows and len(rows) > a.max_rows:
            print(f"   ... {len(rows) - a.max_rows} more rows")
    print()
    print(f"TOTAL templates {len(per_t)}  conflicting lines {total['lines']}  SETTING {total['SETTING']}  RETIRED {total['RETIRED']}  POINTER {total['POINTER']}  stale pointers outside templates {len(pointers)}")
    by_code = Counter(r["code"] for r in report)
    print("BY CODE " + ", ".join(f"{k} {v}" for k, v in by_code.most_common()))
    return 1 if (report or pointers) else 0


if __name__ == "__main__":
    sys.exit(main())
