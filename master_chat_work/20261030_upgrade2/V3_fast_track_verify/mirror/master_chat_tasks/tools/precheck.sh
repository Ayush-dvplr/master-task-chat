#!/usr/bin/env bash
# precheck.sh <bundle> : local QC precheck (plan v1 U11). Every build and fix session runs it until CLEAN.
# 1) the 4 kit scripts + exe_copy dry build from the LIVE kit; 2) the 5 gaps the scripts miss
# (qc_reverse/A SUMMARY:37); 3) author-note grep (leak audit); 4) mechanical gates S5, DS-22, AL-27, J3, J4 (24 Oct 13:40); 5) test and criterion counts (info only, no cap: Ayush 24 Oct 12:50).
# 6) v4 stage 2 (27 Oct): TRUTH line cites, judge type/target (FIND); TS-13 multi-file checks, JD-5 clauses (WARN, not counted); SELF_CHECKS.md note.
# Exit 0 = CLEAN (no fail, no warn except X1 and the A3 count warn), 1 = findings.
set -u
B="$(cd "${1:?usage: precheck.sh <bundle>}" && pwd)"
KIT="/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC"
N=0
flag() { echo "FINDING: $*"; N=$((N+1)); }

echo "== kit $(git -C "$KIT" rev-parse --short=8 HEAD 2>/dev/null || echo '?') on $B"
for s in structure_qc instruction_qc tests_qc judge_qc; do
  out="$(python3 "$KIT/$s.py" "$B" 2>&1)"; rc=$?
  [ $s = tests_qc ] && NT="$(grep -oE '[0-9]+ checks' <<<"$out" | head -1 | cut -d' ' -f1)"
  w=$(grep -iE '^\s*(\[)?warn' <<<"$out" | grep -vcE 'WARN \[(X1|A3|S6)\]')   # X1 = binary files skipped; A3 = more than 35 checks, no cap (Ayush 24 Oct); S6 = CRLF, kit hygiene warn, deliberate data noise (PEER_QC 24 Oct)
  echo "-- $s exit=$rc warns=$w"
  grep -iE '^\s*(\[)?(fail|warn)' <<<"$out" | head -40
  [ $rc -ne 0 ] && flag "$s exit $rc"
  [ "$w" -gt 0 ] && flag "$s $w warn line(s)"
done
TMP="$(mktemp -d)"; python3 "$KIT/exe_copy.py" "$B" "$TMP/copy" >/dev/null 2>"$TMP/err" || { flag "exe_copy refused: $(tail -3 "$TMP/err")"; }
rm -rf "$TMP"

echo "-- gaps the kit scripts miss"
g=$(grep -rnwE 'TODO|FIXME|XXX|PLACEHOLDER' "$B" --exclude-dir=.git 2>/dev/null); [ -n "$g" ] && { echo "$g" | head; flag "TODO/FIXME/XXX/PLACEHOLDER (F0a fail)"; }
g=$(grep -rnE '\{\{[^}]*\}\}' "$B" --exclude-dir=.git 2>/dev/null | grep -vE '^[^:]+\.py:[0-9]+:.*\bf["'"'"']'); [ -n "$g" ] && { echo "$g" | head; flag "{{...}} template braces"; }   # f-string brace escapes are not template braces (PEER_QC 24 Oct)
for df in "$B/environment/Dockerfile"; do
  [ -f "$df" ] || continue
  head -4 "$df" | grep -q '^ENV HOME' || flag "ENV HOME not in lines 2-3 after FROM: ${df#$B/} (FC-S24)"
done
if [ -f "$B/tests/Dockerfile" ] && grep -q 'litellm' "$B/tests/Dockerfile"; then
  grep -q 'litellm==1.105.0' "$B/tests/Dockerfile" || flag "tests/Dockerfile litellm not pinned ==1.105.0 (K8)"
fi
if [ -f "$B/instruction.md" ] && [ -f "$B/environment/Dockerfile" ]; then
  for p in $(grep -oE '/app/data/[A-Za-z0-9_./-]+' "$B/instruction.md" | sort -u); do
    rel="${p#/app/data/}"; [ -e "$B/environment/data/$rel" ] && continue
    grep -q "$p" "$B/environment/Dockerfile" && echo "note: $p is created by a RUN line; instruction_qc C4 may false-fail it (IN-5 01:35 accepts) -> FP dossier"
  done
fi

echo "-- author notes in environment/ (leak audit)"
g=$(grep -rnE '\bTRAPS?\b|_traps\b|\bLEVERS?\b' "$B/environment" 2>/dev/null; grep -rniE '\bgrader\b|hidden test|answer key|author note|\blever L[0-9]' "$B/environment" 2>/dev/null)
[ -n "$g" ] && { echo "$g" | head -15; flag "author-note words in environment/"; }
f=$(find "$B/environment" "$B/instruction.md" -iname '*trap*' -o -iname '*footgun*' -o -iname '*pitfall*' -o -iname '*decoy*' 2>/dev/null)
[ -n "$f" ] && { echo "$f" | head -5; flag "trap-list file names in agent-visible paths"; }
g2=$(grep -rniE 'footgun|known (traps|pitfalls)|common (mistakes|pitfalls)' "$B/environment" "$B/instruction.md" 2>/dev/null)
[ -n "$g2" ] && { echo "$g2" | head -10; flag "pitfall-list wording in agent-visible files"; }

echo "-- mechanical gates for our top QC fails (24 Oct 13:40: S5, DS-22, AL-27, J3, J4; 25 Oct: IN-17/G5 warns, EVIDENCE-MAP)"
f=$(find "$B" -name __pycache__ -o -name '*.pyc' 2>/dev/null)
[ -n "$f" ] && { echo "$f" | head -5; flag "bytecode in bundle (S5 structure fail; run python with -B)"; }
WK="$(dirname "$B")/_work/$(basename "$B")"
out="$(PYTHONDONTWRITEBYTECODE=1 python3 - "$B" "$WK" <<'PY'
import hashlib, os, re, sys
B, WK = sys.argv[1], sys.argv[2]
files = {}
for root, dirs, names in os.walk(B):
    dirs[:] = [d for d in dirs if d != ".git"]
    for n in names:
        files.setdefault(n, []).append(os.path.join(root, n))
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
t = os.path.join(B, "solution", "TRUTH.md")
if os.path.isfile(t):
    for i, line in enumerate(open(t, encoding="utf-8"), 1):
        m = re.match(r"\s*([A-Za-z0-9_.\-]+):\s*([0-9a-f]{64})\s*$", line)
        if not m:
            continue
        name, want = m.groups()
        base = re.sub(r"_sha256$", "", name)
        cands = [name, base, base + ".py"]
        if "_" in base:
            cands.append(base[::-1].replace("_", ".", 1)[::-1])
        paths = [p for c in dict.fromkeys(cands) for p in files.get(c, [])]
        if not paths:
            print(f"NOTE DS-22 TRUTH.md:{i} {name}: no file of that name in the bundle")
        elif all(sha(p) != want for p in paths):
            print(f"FIND DS-22 TRUTH.md:{i} {name} = {want[:12]} but {os.path.relpath(paths[0], B)} is {sha(paths[0])[:12]}")
rc = os.path.join(WK, "RULE_COVERAGE.md")
if os.path.isfile(rc):
    rows = [l for l in open(rc, encoding="utf-8") if l.startswith("|") and not re.match(r"\|\s*(rule|-)", l)]
    zero = [l.split("|")[1].strip() for l in rows if l.rstrip().rstrip("|").split("|")[-1].strip() in ("0", "")]
    print(f"NOTE AL-27 RULE_COVERAGE.md {len(rows)} rule rows")
    for r in zero:
        print(f"FIND AL-27 rule {r}: no test fails under its mutant (RULE_COVERAGE.md)")
else:
    print(f"NOTE AL-27 no {rc} (LEVER_RULES G11; required for new builds and AL-27 fixes)")
# LV-ENUM (LEVER_RULES 1b H1, test-depth 840adf9): a contract that lists the malformed values of a typed field
# hands the lever to the agent (tariff api_contract.md:76-79, config config_contract.md:103-106 held 0% on 300+ corpora).
VAR = re.compile(r"JSON string|JSON number|JSON boolean|decimal point|exponent|\bfraction\b|\x60?\bnull\b\x60?|\x60true\x60|\x60false\x60|negative integer|leading zero|padded|quoted", re.I)
KW = re.compile(r"reject|malformed|exception|is not|does not have|invalid|never converted|refused", re.I)
for root, _, fs in os.walk(os.path.join(B, "environment")):
    for f in fs:
        if not f.endswith((".md", ".txt", ".yml", ".yaml", ".toml")):
            continue
        p = os.path.join(root, f)
        try:
            L = open(p, encoding="utf-8").read().splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        last = -9
        for i in range(len(L)):
            win = " ".join(L[i:i + 3])
            kinds = {m.group(0).lower().strip(chr(96)) for m in VAR.finditer(win)}
            if i > last + 2 and len(kinds) >= 3 and KW.search(win):
                print(f"FIND LV-ENUM {os.path.relpath(p, B)}:{i + 1}-{i + 3} lists malformed values of a typed field ({', '.join(sorted(kinds))}); state the bare type only (LEVER_RULES 1b H1)")
                last = i
# 25 Oct (QC push 5574d77e, LEVER_RULES_v2 W1/G5/0b): warn-only phrase lints on instruction.md (not counted), EVIDENCE_MAP rows checked.
ins = os.path.join(B, "instruction.md")
if os.path.isfile(ins):
    LINTS = [
        ("IN17-PHRASE", re.compile(r"note that|watch out|remember that|be careful|exactly one|is not what|in no particular order|will not reproduce|superseded or retired|disagree with each other|\b(Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)\s+\w+s\b", re.I), "justify as a requirement or delete (IN-17 01:47, W1)"),
        ("SELF-CHECK-INVITE", re.compile(r"a second way|outside the (program|tool)|check yourself|on your own, outside|copy of the data whose contents", re.I), "drop the self-check paragraph (LEVER_RULES G5, J2/J9 never echoed)"),
        ("G5-SCALES", re.compile(r"other scales|other (periods and )?sizes|no count to check", re.I), "keep the exactness clause only (LEVER_RULES G5)"),
    ]
    for i, line in enumerate(open(ins, encoding="utf-8"), 1):
        for tag, rx, why in LINTS:
            m = rx.search(line)
            if m:
                print(f"WARN {tag} instruction.md:{i} '{m.group(0)}': {why}")
em = os.path.join(WK, "EVIDENCE_MAP.md")
if os.path.isfile(em):
    erows = [l for l in open(em, encoding="utf-8") if l.startswith("|") and not re.match(r"\|\s*(rule|-)", l)]
    print(f"NOTE EVIDENCE-MAP {len(erows)} rows")
    for l in erows:
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        fact = cells[2] if len(cells) > 2 else ""
        m = re.match(r"`?([^`:\s]+):(\d+)", fact)
        if not m:
            print(f"FIND EVIDENCE-MAP rule {cells[0]}: shipped fact has no file:line ({fact or 'empty'})")
            continue
        hits = [q for q in files.get(os.path.basename(m.group(1)), []) if os.sep + "environment" + os.sep in q]
        if not hits:
            print(f"FIND EVIDENCE-MAP rule {cells[0]}: {m.group(1)} is not a shipped file under environment/")
else:
    print(f"NOTE EVIDENCE-MAP no {em} (LEVER_RULES_v2 0b; required when a graded rule has no sentence)")
j = os.path.join(B, "tests", "judge.toml")
if os.path.isfile(j):
    import tomllib
    crit = tomllib.load(open(j, "rb")).get("criterion", [])
    neg = [c for c in crit if c.get("weight", 0) < 0 and re.search(r"claim|report|state|assert|says? .*(pass|succeed|complet)|re-?run|verified", c.get("description", ""), re.I)]
    cq = [c for c in crit if c.get("weight", 0) > 0 and re.search(r"code quality|maintainab|exception handler|ordinary python|dead code|unreachable|function (is )?longer|except clause|split into functions", c.get("description", ""), re.I)]
    fig = [c["id"] for c in crit if c.get("weight", 0) > 0 and re.search(r"\d{3,}", c.get("description", ""))]
    if not neg:
        print("FIND J3 judge.toml has no honesty negative (a negative criterion on a claimed check or re-run)")
    if len(cq) != 1:
        print(f"FIND J4 judge.toml has {len(cq)} code-quality criteria, want exactly 1 (JD-18)")
    if fig:
        print(f"NOTE J1 figure criteria {len(fig)} ({', '.join(fig)}): final-reply figures are fine; what-if figures max 6, oracle-printed")
    # v4 stage 2 (PLAN pipeline_v4, Ayush 27 Oct 'proceed'): type/target table (JD-15), one verb clause (JD-5, warn only)
    for c in crit:
        an = c.get("annotations") or {}
        miss = [k for k in ("type", "evaluation_target") if not an.get(k)]
        if miss:
            print(f"FIND JD-15 criterion {c.get('id')}: annotations missing {', '.join(miss)}")
        d = c.get("description", "")
        if len(re.findall(r"[.;](\s|$)", d.strip())) > 1:
            print(f"WARN JD-5 criterion {c.get('id')}: more than one sentence or clause; one verb clause per criterion")
# v4 stage 2: TRUTH.md line cites resolve (DS-22/AL-18)
if os.path.isfile(t):
    for i, line in enumerate(open(t, encoding="utf-8"), 1):
        for m in re.finditer(r"([\w./-]+\.(?:py|md|json|jsonl|csv|toml|ya?ml|sh|txt)):(\d+)", line):
            paths = files.get(os.path.basename(m.group(1)), [])
            if not paths:
                continue
            try:
                n = sum(1 for _ in open(paths[0], encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if int(m.group(2)) > n:
                print(f"FIND DS-22 TRUTH.md:{i} cites {m.group(1)}:{m.group(2)} but the file has {n} lines")
# v4 stage 2: TS-13 one artifact per check (warn only; a summary check may name several paths on purpose)
import ast
for tp in files.get("test_output.py", []) + files.get("test_outputs.py", []):
    if os.sep + "tests" + os.sep not in tp:
        continue
    tree = ast.parse(open(tp, encoding="utf-8").read())
    outs = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            if isinstance(v, ast.BinOp) and isinstance(v.right, ast.Constant) and isinstance(v.left, ast.Name) and v.left.id == "OUT":
                outs[node.targets[0].id] = str(v.right.value)
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]:
        seen = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and n.id in outs:
                seen.add(outs[n.id])
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("/app/out/"):
                seen.add(n.value[9:])
            elif isinstance(n, ast.BinOp) and isinstance(n.left, ast.Name) and n.left.id == "OUT" and isinstance(n.right, ast.Constant):
                seen.add(str(n.right.value))
        if len(seen) >= 2:
            print(f"WARN TS-13 {os.path.relpath(tp, B)}:{fn.lineno} {fn.name} reads {len(seen)} /app/out files ({', '.join(sorted(seen))}); one artifact per check unless QC_DEFENCE says why")
sc = os.path.join(WK, "SELF_CHECKS.md")
print(f"NOTE SELF-CHECKS {'present' if os.path.isfile(sc) else 'missing'}: {sc} (P2 v5 Phase 8 step 3b: vacuity probe, TS-16 negatives, promise table, literal table)")
PY
)"
[ -n "$out" ] && echo "$out"
while IFS= read -r l; do case "$l" in FIND*) N=$((N+1));; esac; done <<<"$out"

echo "-- counts (no cap; kit floors 10 tests, 8 criteria)"
nt="${NT:-0}"
nc=$(grep -cE '^\s*\[\[criterion\]\]' "$B/tests/judge.toml" 2>/dev/null || echo 0)
echo "tests $nt (tests_qc A3 count), judge criteria $nc"
[ "$nc" -lt 8 ] && flag "criteria $nc < 8 (kit floor)"

if [ $N -eq 0 ]; then echo "PRECHECK CLEAN"; exit 0; else echo "PRECHECK: $N finding(s)"; exit 1; fi
