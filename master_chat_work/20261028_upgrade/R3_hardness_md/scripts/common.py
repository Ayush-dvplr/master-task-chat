"""Shared loader for R3 hardness.md verification. Read-only over Final_Delivery.

Field semantics (verified in s01_reconcile.py against stored percentages):
  test check: weight > 0 positive (passed True = earned); weight < 0 negative (passed True = cheat fired)
  judge criterion: is_positive True (passed True = earned); is_positive False (passed False = fired)
"""
import json, os, re, statistics, tomllib
from pathlib import Path

ROOT = Path("/Users/mac/Desktop/Terminal Bench")
FD = ROOT / "Anubis_Tasks_Samples" / "Final_Delivery"
STAGE1 = ROOT / "anubis-stage-1"
REL = Path("trajectories/claude-opus-5/run_1")


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")


def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    return pearson(rank(x), rank(y))


def input_stats(task_dir: Path):
    data = task_dir / "environment" / "data"
    files = bytes_ = lines = 0
    if data.exists():
        for p in data.rglob("*"):
            if p.is_file():
                files += 1
                b = p.read_bytes()
                bytes_ += len(b)
                lines += b.count(b"\n")
    return files, bytes_, lines


def load_task(task_dir: Path, rel=REL, with_inputs=True):
    rp = task_dir / rel / "report.json"
    if not rp.exists():
        return None
    r = json.loads(rp.read_text())
    tests = r["pytest"]["tests"]
    rub = r["rubric"]
    pos_t = [t for t in tests if t["weight"] > 0]
    neg_t = [t for t in tests if t["weight"] < 0]
    pos_j = [c for c in rub if c["is_positive"]]
    neg_j = [c for c in rub if not c["is_positive"]]
    tw = sum(t["weight"] for t in pos_t)
    tearn = sum(t["weight"] for t in pos_t if t["passed"])
    tpen = sum(t["weight"] for t in neg_t if t["passed"])  # weights are negative
    jw = sum(c["score"] for c in pos_j)
    jearn = sum(c["score"] for c in pos_j if c["passed"])
    jpen = sum(c["score"] for c in neg_j if not c["passed"])  # scores negative
    d = dict(
        id=task_dir.name, path=str(rp), report=r, tests=tests, rubric=rub,
        pos_t=pos_t, neg_t=neg_t, pos_j=pos_j, neg_j=neg_j,
        tw=tw, tearn=tearn, tpen=tpen, jw=jw, jearn=jearn, jpen=jpen,
        final=r["final_reward"], tests_pct=r["test_weights_percentage"],
        judge_pct=r["rubric_weights_percentage"], judge_model=r.get("judge_model"),
    )
    res = task_dir / rel / "result.json"
    if res.exists():
        rj = json.loads(res.read_text())
        d["started_at"] = rj.get("started_at")
        d["exception"] = rj.get("exception_info")
    u = task_dir / rel / "trajectory_usage.json"
    if u.exists():
        uj = json.loads(u.read_text())
        uj = uj[0] if isinstance(uj, list) else uj
        d["cost"] = uj.get("trajectory_cost_usd")
        d["tokens"] = (uj.get("trajectory_input_tokens") or 0) + (uj.get("trajectory_output_tokens") or 0)
    tt = task_dir / "task.toml"
    if tt.exists():
        try:
            t = tomllib.loads(tt.read_text())
            d["author"] = (t.get("task", {}).get("authors") or [{}])[0].get("name")
            d["category"] = t.get("metadata", {}).get("category")
        except Exception as e:  # malformed toml is reported, not hidden
            d["author"] = f"TOML_ERR:{e}"
    ins = task_dir / "instruction.md"
    d["instr_len"] = len(ins.read_text()) if ins.exists() else 0
    if with_inputs:
        d["in_files"], d["in_bytes"], d["in_lines"] = input_stats(task_dir)
    return d


def load_all(root=FD, rel=REL, with_inputs=True):
    out = []
    for p in sorted(root.iterdir()):
        if p.is_dir():
            d = load_task(p, rel, with_inputs)
            if d:
                out.append(d)
    return out


# Bundles added to Final_Delivery after commit 95f8fb386 (27 Oct 18:23 IST, "...for 85 tasks").
# `git diff --name-status 95f8fb386 HEAD -- Final_Delivery` shows only additions in these 7 dirs (s03_snapshot.py).
ADDED_AFTER_DOC = {"75407a55", "8956ff8b", "98ed74c1", "9bb234eb", "b6237098", "f3381a1c", "fa7c65bd"}
REL55 = Path("trajectories/claude-opus-5-5/run_1")


def load_doc85(with_inputs=True):
    """The doc's set: 85 dirs at 95f8fb386; 83 opus-5 reports + 2 opus-5-5 fallbacks (11750b7a, 4ef4340d)."""
    out = []
    for p in sorted(FD.iterdir()):
        if p.is_dir() and p.name[:8] not in ADDED_AFTER_DOC:
            d = load_task(p, REL, with_inputs) or load_task(p, REL55, with_inputs)
            if d:
                d["model"] = "opus-5" if (p / REL / "report.json").exists() else "opus-5-5"
                out.append(d)
    return out


def recompute(d):
    tests = max(0.0, (d["tearn"] + d["tpen"]) / d["tw"] * 100) if d["tw"] else 0.0
    judge = (d["jearn"] + d["jpen"]) / d["jw"] * 100 if d["jw"] else 0.0
    return tests, judge, round((tests + judge) / 2, 2)


HELDOUT = re.compile(r"hidden|heldout|held_out|unseen|challenge|corpus|generalis|generaliz|reseed|fresh|novel", re.I)
EXACT = re.compile(r"exact|match|byte|equal|correct|identical", re.I)
PLUMB = re.compile(r"exist|runs|parse|cli|deliver|artifact|present|writes|program|script|entry|invok|exit", re.I)
SHAPE = re.compile(r"shape|key|schema|serial|format|header|column|field|layout|form\b", re.I)
SHIPPED = re.compile(r"shipped|sample|visible|given|public", re.I)


def summary(v):
    v = sorted(v)
    return dict(n=len(v), mean=round(statistics.mean(v), 2), median=round(statistics.median(v), 2), min=v[0], max=v[-1])
