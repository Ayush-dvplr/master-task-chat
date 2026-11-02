"""Trip-point extractor (read-only). Usage:
  perl -e 'alarm 300; exec @ARGV' python3 trip_points.py OUT_DIR
Reads the latest saved run of every task, writes OUT_DIR/TRIP_POINTS.csv and
OUT_DIR/_trip_summary.json. Never prints a whole trajectory; snippets <= 240 chars.
"""
import csv, json, re, sys
from pathlib import Path

H = Path("/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness")
OUT = Path(sys.argv[1])

RUNS = sorted(H.glob("jobs/*/trajectory/claude-opus-5/Run 1"))
RUNS = [r for r in RUNS if "_archive" not in str(r)]
RUNS.append(H / "Output_RFP/kvec-meter-settlement-reconciliation/trajectories/claude-opus-5/run_1")

EASY_NAME = re.compile(r"(^|_)(shipped|sample|exists?|present|cli|schema|format|parse|loads?|keys|smoke|help|usage|readable|json|zip|layout|shape)(_|$)")
CLAIM = re.compile(r"\b(all (\d+ )?(tests?|checks?|cases?|scenarios?|controls?)[^.]{0,60}(pass|match|reproduce|green|correct)|verified|reproduces? .{0,40}exactly|100 ?%|byte[- ]identical|every .{0,40}(pass|match))", re.I)
CAVEAT = re.compile(r"\b(assum\w*|approximat\w*|heuristic\w*|fallback|not (implemented|handled|supported)|unsupported|could ?n.t|unable|skipp\w*|ignor\w*|limitation\w*|TODO|best[- ]effort|may not|might not|not verified|left as)\b", re.I)
SELFFAIL = re.compile(r"(Traceback|AssertionError|\bFAIL(ED)?\b|MISMATCH|mismatch|does not match|differs?\b|WARN(ING)?\b|Killed|timed? ?out|exit code [1-9])")


def slug_of(run: Path) -> str:
    p = run.parts
    if "Output_RFP" in p:
        return p[p.index("Output_RFP") + 1]
    return p[p.index("jobs") + 1]


def snip(s, n=240):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:n]


def load(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def stdout_msgs(run):
    f = run / "verifier/test-stdout.txt"
    m = {}
    if f.exists():
        for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            mm = re.match(r"\[check\] (test_)?([\w\-]+): (.*)", line)
            if mm:
                m.setdefault(mm.group(2), (i, mm.group(3)))
    return m


rows, summary = [], {}
for run in RUNS:
    slug = slug_of(run)
    rel = str(run.relative_to(H))
    rep = load(run / "report.json") or {}
    py = rep.get("pytest") or {}
    tests = py.get("tests") or []
    rub = rep.get("rubric") or []
    traj = load(run / "agent/trajectory.json") or {}
    steps = traj.get("steps") or []
    msgs = stdout_msgs(run)
    # report.json 'passed' on NEGATIVES is inconsistent across finalize versions
    # (cohort-uplift: True = avoided; match-replay: False = fired). Ground truth is
    # verifier/reward-details.json criterion value (>0 on a negative = fired).
    det = load(run / "verifier/reward-details.json") or {}
    val = {}
    for comp in ((det.get("reward") or {}).get("components") or []):
        for cr in ((comp.get("detail") or {}).get("criteria") or []):
            key = cr.get("id") or cr.get("name")
            val[(comp.get("name"), str(key))] = cr.get("value")

    def neg_fired(layer, key, rep_passed):
        v = val.get((layer, key))
        if v is not None:
            return (v or 0) > 0
        return rep_passed is False  # fallback (no reward-details): treat False as fired
    c = {k: 0 for k in ["WRONG_AND_GRADED", "WRONG_NOT_GRADED", "RIGHT_EASY", "SKIPPED_BEHAVIOUR", "STATED_WRONG_FACT"]}

    def add(cls, layer, item, weight, evidence, note):
        c[cls] += 1
        rows.append(dict(slug=slug, run=rel, cls=cls, layer=layer, item=item, weight=weight, evidence=evidence, note=snip(note)))

    failed_pos = 0
    for t in tests:
        name, w, ok = t.get("name"), t.get("weight", 0), t.get("passed")
        short = re.sub(r"^test_", "", str(name))
        if w is not None and w > 0 and not ok:
            failed_pos += 1
            ln, msg = msgs.get(short, (None, ""))
            add("WRONG_AND_GRADED", "test", short, w, f"{rel}/verifier/test-stdout.txt:{ln}" if ln else f"{rel}/report.json", msg)
        elif w is not None and w > 0 and ok and (EASY_NAME.search(short) or w <= 1):
            add("RIGHT_EASY", "test", short, w, f"{rel}/report.json", "passed; name/weight marks a sample-, existence- or interface-level check")
        elif w is not None and w < 0 and neg_fired("test_output", short, ok):
            add("WRONG_AND_GRADED", "test-negative", short, w, f"{rel}/report.json", "negative test fired (passed=True on negative)")
    for r in rub:
        w = r.get("score")
        tgt = r.get("evaluation_target")
        pos = r.get("is_positive", (w or 0) > 0)
        ok = r.get("passed")
        crit = snip(r.get("criterion"), 160)
        if pos and not ok:
            cls = "SKIPPED_BEHAVIOUR" if tgt == "trajectory" else "WRONG_AND_GRADED"
            add(cls, f"judge:{tgt}", f"R{r.get('number')}", w, f"{rel}/report.json", crit)
        elif (not pos) and neg_fired("judge", f"R{r.get('number')}", ok):
            add("WRONG_AND_GRADED", f"judge-negative:{tgt}", f"R{r.get('number')}", w, f"{rel}/report.json", "negative fired: " + crit)

    agent_steps = [s for s in steps if s.get("source") == "agent"]
    final, final_sid = "", None
    for s in reversed(agent_steps):
        fin = [tc for tc in (s.get("tool_calls") or []) if tc.get("function_name") == "finish"]
        text = (fin[0].get("arguments") or {}).get("message") if fin else s.get("message")
        if text:
            final, final_sid = str(text), s.get("step_id")
            break
    claim = CLAIM.search(final or "")
    if claim and failed_pos:
        add("STATED_WRONG_FACT", "final_message", "claim", "", f"{rel}/agent/trajectory.json step {final_sid}",
            f"claims '{claim.group(0)}' while {failed_pos} positive tests failed")
    for m in CAVEAT.finditer(final or ""):
        a = max(0, m.start() - 100)
        add("WRONG_NOT_GRADED" if failed_pos == 0 else "WRONG_NOT_GRADED", "final_message", "caveat:" + m.group(0).lower(), "",
            f"{rel}/agent/trajectory.json step {final_sid}", "candidate (admitted gap): ..." + (final or "")[a:m.end() + 120])
        break  # one caveat row per run; the rest are reviewed by hand

    # last self-check: last tool observation whose command looks like a run of the agent's own checks
    last_check = None
    for s in agent_steps:
        tcs = s.get("tool_calls") or []
        obs = (s.get("observation") or {}).get("results") or []
        for tc in tcs:
            cmd = str((tc.get("arguments") or {}).get("command", ""))
            if re.search(r"(python3?|pytest|bash|sh)\b.*(test|check|verif|valid|diff|cmp|compare|selftest|run)", cmd):
                text = " ".join(str(o.get("content", "")) for o in obs)
                last_check = (s.get("step_id"), cmd, text)
    if last_check:
        sid, cmd, text = last_check
        hit = SELFFAIL.search(text)
        if hit:
            a = max(0, hit.start() - 120)
            add("WRONG_NOT_GRADED", "trajectory:last_self_check", "self-check-signal:" + hit.group(0), "",
                f"{rel}/agent/trajectory.json step {sid}", "candidate: final self-check output still shows '" + hit.group(0) + "': " + text[a:hit.end() + 100])

    fm = traj.get("final_metrics") or {}
    summary[slug] = dict(run=rel, tests_total=len(tests), tests_failed_pos=failed_pos, rubric_n=len(rub),
                         final_reward=rep.get("final_reward"), steps=len(steps), agent_steps=len(agent_steps),
                         cost_usd=fm.get("total_cost_usd"), counts=c, final_msg_head=snip(final, 300),
                         last_check_step=last_check[0] if last_check else None,
                         last_check_cmd=snip(last_check[1], 160) if last_check else None)

with open(OUT / "TRIP_POINTS.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["slug", "run", "cls", "layer", "item", "weight", "evidence", "note"])
    w.writeheader()
    w.writerows(rows)
(OUT / "_trip_summary.json").write_text(json.dumps(summary, indent=1))
print("runs", len(RUNS), "rows", len(rows))
for k, v in summary.items():
    print(k[:34].ljust(34), v["tests_total"], v["tests_failed_pos"], v["rubric_n"], v["final_reward"], v["agent_steps"], v["counts"])
