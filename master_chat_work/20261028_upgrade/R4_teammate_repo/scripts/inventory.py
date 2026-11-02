#!/usr/bin/env python3
"""R4 inventory of anubis-stage-1 (read only). Writes OUT/inventory.csv and OUT/inventory.json.

Re-run from scratch:  python3 OUT/scripts/inventory.py
All numbers come from report.json / result.json / trajectory.json / task files.
Heuristic columns are prefixed h_ and are INFERRED (keyword scans of test_output.py).
"""
import csv, json, os, re, subprocess, glob, tomllib
from datetime import datetime

REPO = "/Users/mac/Desktop/Terminal Bench/anubis-stage-1"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY_DIRS = ["/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research"]


def band(f):
    if f >= 87.5: return "Trivial"
    if f >= 50: return "Easy"
    if f >= 37.5: return "Medium"
    if f >= 25: return "Hard"
    return "Expert"


def studied_ids():
    """uuid prefixes (8 hex) that appear in any file name or file body under _dev_research."""
    seen = {}
    for root in STUDY_DIRS:
        for dp, dn, fn in os.walk(root):
            for f in fn:
                p = os.path.join(dp, f)
                if not f.endswith((".md", ".json", ".txt", ".csv")):
                    continue
                try:
                    if os.path.getsize(p) > 3_000_000: continue
                    s = open(p, errors="ignore").read()
                except Exception:
                    continue
                for m in set(re.findall(r"\b([0-9a-f]{8})(?:-[0-9a-f]{4})?", f + " " + s)):
                    seen.setdefault(m, set()).add(os.path.relpath(p, root).split(os.sep)[0])
    return seen


def git_author(task):
    r = subprocess.run(["git", "-C", REPO, "log", "--diff-filter=A", "--format=%an|%ad", "--date=short", "--", f"{task}/task.toml"],
                       capture_output=True, text=True)
    lines = [l for l in r.stdout.strip().splitlines() if l]
    return lines[-1].split("|") if lines else ["?", "?"]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def traj_stats(path):
    t = json.load(open(path))
    steps = t.get("steps", [])
    agent_steps = [s for s in steps if s.get("source") == "agent"]
    calls = [c for s in agent_steps for c in (s.get("tool_calls") or [])]
    t0 = ts(steps[0]["timestamp"]) if steps else None
    first_write = None
    selftests = 0
    reads = 0
    for s in agent_steps:
        for c in s.get("tool_calls") or []:
            a = json.dumps(c.get("arguments", {}))
            fn = c.get("function_name", "")
            is_write = (fn in ("str_replace_editor", "file_editor") and '"create"' in a) or re.search(r"cat\s*>\s*/app/out|> ?/app/out/[\w.]+\.py|tee /app/out", a)
            if is_write and first_write is None and t0:
                first_write = round((ts(s["timestamp"]) - t0).total_seconds() / 60, 1)
            if re.search(r"python3? [^\"]*(/app/out/|test|check|verify)", a):
                selftests += 1
            if re.search(r"\b(cat|head|sed -n|less|view)\b", a) and "/app/data" in a:
                reads += 1
    dur = round((ts(steps[-1]["timestamp"]) - t0).total_seconds() / 60, 1) if len(steps) > 1 else None
    last = steps[-1].get("message", "") if steps else ""
    return dict(steps=len(steps), tool_calls=len(calls), minutes=dur, first_write_min=first_write,
                h_selftest_cmds=selftests, h_data_reads=reads,
                says_time_limit=bool(re.search(r"time limit|out of time|ran out", last, re.I)))


def main():
    seen = studied_ids()
    rows = []
    for task in sorted(d for d in os.listdir(REPO) if os.path.isfile(os.path.join(REPO, d, "task.toml"))):
        td = os.path.join(REPO, task)
        toml = tomllib.load(open(os.path.join(td, "task.toml"), "rb"))
        runs = sorted(glob.glob(os.path.join(td, "trajectories", "*", "run_*")))
        run = runs[0]
        rep = json.load(open(os.path.join(run, "report.json")))
        res = json.load(open(os.path.join(run, "result.json")))
        tests = rep["pytest"]["tests"]
        pos = [t for t in tests if t["weight"] > 0]
        neg = [t for t in tests if t["weight"] < 0]
        wsum = sum(t["weight"] for t in pos)
        ws = sorted((t["weight"] for t in pos), reverse=True)
        lost = sum(t["weight"] for t in pos if not t["passed"])
        neg_fired = [t["name"] for t in neg if t["passed"]]  # convention varies; recorded raw
        rub = rep.get("rubric", [])
        rpos = [c for c in rub if c.get("is_positive", True)]
        rneg = [c for c in rub if not c.get("is_positive", True)]
        targets = {}
        for c in rub:
            targets[c.get("evaluation_target", "?")] = targets.get(c.get("evaluation_target", "?"), 0) + 1
        tp = open(os.path.join(td, "tests", "test_output.py"), errors="ignore").read()
        data_files = [f for f in glob.glob(os.path.join(td, "environment", "**", "*"), recursive=True) if os.path.isfile(f) and os.path.basename(f) != "Dockerfile"]
        instr = open(os.path.join(td, "instruction.md"), errors="ignore").read()
        name_hidden = sum(1 for t in pos if re.search(r"unseen|hidden|fresh|held|novel|generated|random|secret|scale|large", t["name"], re.I))
        name_hidden_w = sum(t["weight"] for t in pos if re.search(r"unseen|hidden|fresh|held|novel|generated|random|secret|scale|large", t["name"], re.I))
        auth, added = git_author(task)
        tr = traj_stats(os.path.join(run, "agent", "trajectory.json"))
        ae = res.get("agent_execution") or {}
        ver = res.get("verifier") or {}
        agent_min = None
        if ae.get("started_at") and ae.get("finished_at"):
            agent_min = round((ts(ae["finished_at"]) - ts(ae["started_at"])).total_seconds() / 60, 1)
        exc = res.get("exception_info")
        stdout_p = os.path.join(run, "verifier", "test-stdout.txt")
        stdout = open(stdout_p, errors="ignore").read() if os.path.exists(stdout_p) else ""
        final = rep["final_reward"]
        rows.append(dict(
            id=task[:8], uuid=task, author=auth, added=added,
            toml_author=(toml.get("task", {}).get("authors") or [{}])[0].get("name", ""),
            category=toml.get("metadata", {}).get("category", ""),
            model=rep.get("model"), final=final, band=band(final),
            tests_pct=rep["test_weights_percentage"], rubric_pct=rep["rubric_weights_percentage"],
            n_tests=len(pos), n_neg_tests=len(neg), test_wsum=wsum,
            top1_share=round(ws[0] / wsum, 3) if ws else 0,
            top3_share=round(sum(ws[:3]) / wsum, 3) if ws else 0,
            maxw_count=sum(1 for w in ws if ws and w == ws[0]),
            distinct_weights=len(set(ws)),
            tests_passed=sum(1 for t in pos if t["passed"]), tests_lost_w=lost,
            h_hidden_named=name_hidden, h_hidden_named_wshare=round(name_hidden_w / wsum, 3) if wsum else 0,
            h_tp_random=bool(re.search(r"random\.Random|Random\(|seed", tp)),
            h_tp_subprocess=bool(re.search(r"subprocess", tp)),
            h_tp_tmpdir=bool(re.search(r"tmp_path|tempfile|mkdtemp", tp)),
            h_tp_reads_app_data=bool(re.search(r"/app/data", tp)),
            h_tp_timeout=bool(re.search(r"timeout\s*=", tp)),
            tp_loc=tp.count("\n"),
            n_rubric=len(rub), n_rubric_pos=len(rpos), n_rubric_neg=len(rneg),
            rubric_wsum=sum(c.get("score", 0) for c in rpos),
            rubric_passed=sum(1 for c in rpos if c.get("passed")),
            rubric_targets=";".join(f"{k}:{v}" for k, v in sorted(targets.items())),
            rubric_neg_fired=sum(1 for c in rneg if c.get("passed")),
            n_data_files=len(data_files), data_kb=round(sum(os.path.getsize(f) for f in data_files) / 1024, 1),
            instr_words=len(instr.split()), instr_lines=instr.count("\n"),
            agent_timeout=toml.get("agent", {}).get("timeout_sec"),
            agent_min=agent_min, exception=(exc or {}).get("exception_type", "") if isinstance(exc, dict) else str(exc or ""),
            stdout_traceback=("Traceback" in stdout), stdout_permission=("Permission denied" in stdout or "PermissionError" in stdout),
            stdout_timeout=bool(re.search(r"TimeoutExpired|timed out", stdout)),
            studied_in=";".join(sorted(seen.get(task[:8], []))),
            **tr,
        ))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "inventory.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    json.dump(rows, open(os.path.join(OUT, "inventory.json"), "w"), indent=1)
    print(len(rows), "tasks")


if __name__ == "__main__":
    main()
