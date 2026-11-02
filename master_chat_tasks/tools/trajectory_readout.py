"""Trajectory read-out for one harness run (read-only). Pipeline v4 section T.

Usage:
  python3 trajectory_readout.py "<run folder>" [--out OUT/TRIP.md]

<run folder> is a saved harness run, e.g.
  Terminal_2.0_Harbor_Harness/jobs/<slug>/trajectory/claude-opus-5/Run 1
Ground truth for every score is verifier/reward-details.json (criterion value;
on a negative, value > 0 means it fired). report.json only adds the judge
evaluation_target. Never prints a whole trajectory; snippets <= 240 chars.

Classes written automatically: LOST_GRADED, EASY, SKIPPED, FALSE_CLAIM.
WRONG_UNGRADED is never guessed by keyword: the master fills it by hand in the
TRIP table at the end (step | what the agent did | docs file:line | check | class).
"""
import argparse
import json
import re
import sys
from pathlib import Path

EASY_NAME = re.compile(r"(^|_)(shipped|sample|exists?|present|cli|schema|format|parse|loads?|keys|smoke|help|usage|readable|json|zip|layout|shape)(_|$)")
CLAIM = re.compile(r"\b(all (\d+ )?(tests?|checks?|cases?|scenarios?|controls?)[^.]{0,60}(pass|match|reproduce|green|correct)|verified|reproduces? .{0,40}exactly|100 ?%|byte[- ]identical|every .{0,40}(pass|match))", re.I)
TIMEOUT = re.compile(r"(timed? ?out|exited -9|Killed|TimeoutExpired)", re.I)
KILLED = re.compile(r"(exit -9\b|SIGKILL|OOM|out of memory|exit(?:ed)? 137\b)", re.I)  # killed by the verifier: OOM or wall limit
CRASH = re.compile(r"(Traceback|exited [1-9]\d*|exit code [1-9]|RecursionError|MemoryError|No such file|not found)", re.I)


def snip(s, n=240):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def stdout_msgs(run):
    """Returns ({check name: (line, msg)}, [(helper tokens, line, msg)]).
    The second list holds helper lines such as `_check_wide: exit -9: timed out after 50 s`,
    matched to a lost check later by name tokens."""
    f = run / "verifier/test-stdout.txt"
    out, helpers = {}, []
    if f.exists():
        for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            m = re.match(r"\[check\] (\{.*\})\s*$", line)
            if m:
                try:
                    j = json.loads(m.group(1))
                except json.JSONDecodeError:
                    j = {}
                if isinstance(j, dict) and j.get("check"):
                    name = re.sub(r"^test_", "", str(j["check"]))
                    out.setdefault(name, (i, str(j.get("message", ""))))
                    continue
            m = re.match(r"\[check\] (?:test_)?([\w\-]+): (.*)", line)
            if m:
                out.setdefault(m.group(1), (i, m.group(2)))
                continue
            m = re.match(r"_(?:check|run)_([\w]+): (.*)", line)
            if m:
                helpers.append((set(m.group(1).split("_")), i, m.group(2)))
    return out, helpers


def helper_msg(key, helpers):
    """Most specific helper line whose name tokens all occur in the check name;
    among equally specific lines, a timeout/kill line wins."""
    toks = set(str(key).split("_"))
    best = None
    for h, ln, msg in helpers:
        if h and h <= toks:
            rank = (len(h), 1 if TIMEOUT.search(msg) else 0)
            if best is None or rank > best[0]:
                best = (rank, ln, msg)
    return (best[1], best[2]) if best else (None, "")


def loss_kind(msg):
    if TIMEOUT.search(msg or ""):
        return "TIMEOUT"
    if KILLED.search(msg or ""):
        return "KILLED"
    if CRASH.search(msg or ""):
        return "CRASH"
    return "WRONG"


def final_message(steps):
    for s in reversed([s for s in steps if s.get("source") == "agent"]):
        fin = [tc for tc in (s.get("tool_calls") or []) if tc.get("function_name") == "finish"]
        text = (fin[0].get("arguments") or {}).get("message") if fin else s.get("message")
        if text:
            return str(text), s.get("step_id")
    return "", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out")
    a = ap.parse_args()
    run = Path(a.run)
    det = load(run / "verifier/reward-details.json")
    if not det:
        sys.exit(f"no verifier/reward-details.json under {run}")
    rew = det.get("reward") or {}
    rep = load(run / "report.json") or {}
    targets = {f"R{r.get('number')}": r.get("evaluation_target") for r in rep.get("rubric") or []}
    traj = load(run / "agent/trajectory.json") or {}
    steps = traj.get("steps") or []
    msgs, helpers = stdout_msgs(run)

    rows, layers = [], {}
    for comp in rew.get("components") or []:
        layer = comp.get("name")
        crits = (comp.get("detail") or {}).get("criteria") or []
        pos = sum(c.get("weight", 0) for c in crits if c.get("weight", 0) > 0)
        got = sum(c.get("weight", 0) * (c.get("value") or 0) for c in crits)
        layers[layer] = (got, pos)
        for c in crits:
            w, v = c.get("weight", 0), c.get("value") or 0
            key = c.get("id") or c.get("name")
            label = f"{key} {c.get('name')}" if c.get("id") else key
            if layer == "judge":
                why = c.get("reasoning")
                tgt = targets.get(str(key), "?")
            else:
                ln, why = msgs.get(str(key)) or helper_msg(key, helpers)
                why = f"test-stdout.txt:{ln} {why}" if ln else why
                tgt = "output"
            if w > 0 and v < 1:
                cls = "SKIPPED" if tgt == "trajectory" else "LOST_GRADED"
                kind = loss_kind(why) if layer != "judge" else "-"
                rows.append((cls, layer, label, w, tgt, kind, snip(why)))
            elif w < 0 and v > 0:
                rows.append(("LOST_GRADED", layer + " negative", label, w, tgt, "-", snip(why)))
            elif w > 0 and v >= 1 and layer != "judge" and (w <= 1 or EASY_NAME.search(str(key))):
                rows.append(("EASY", layer, label, w, tgt, "-", "passed; weight 1 or sample/interface-level name"))

    final, sid = final_message(steps)
    failed_pos = sum(1 for r in rows if r[0] in ("LOST_GRADED", "SKIPPED") and r[3] > 0 and r[1] != "judge")
    claim = CLAIM.search(final)
    if claim and failed_pos:
        rows.append(("FALSE_CLAIM", "final message", f"step {sid}", "", "trajectory", "-",
                     f"claims '{claim.group(0)}' while {failed_pos} positive tests failed"))

    agent_steps = [s for s in steps if s.get("source") == "agent"]
    fm = traj.get("final_metrics") or {}
    kinds = {}
    for r in rows:
        if r[0] == "LOST_GRADED" and r[5] != "-":
            kinds[r[5]] = kinds.get(r[5], 0) + r[3]
    out = [f"# Trajectory read-out: {run}", "",
           f"- final {rep.get('final_reward', rew.get('score'))}; agent steps {len(agent_steps)}; cost_usd {fm.get('total_cost_usd')}"]
    for layer, (got, pos) in layers.items():
        pct = 100 * got / pos if pos else 0
        out.append(f"- {layer}: {got:g}/{pos:g} ({pct:.2f}%)")
    out.append(f"- lost test points by kind (Law 1: TIMEOUT/KILLED/CRASH give a recovery signal, WRONG is silent): {kinds or 'none'}")
    out.append(f"- final message (step {sid}): {snip(final, 300)}")
    out += ["", "## Scored items", "", "| class | layer | item | weight | target | kind | evidence |", "|---|---|---|---|---|---|---|"]
    order = {"LOST_GRADED": 0, "SKIPPED": 1, "FALSE_CLAIM": 2, "EASY": 3}
    for r in sorted(rows, key=lambda r: (order[r[0]], r[1], str(r[2]))):
        out.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
    out += ["", "## TRIP table (master fills by hand; WRONG_UNGRADED only here)", "",
            "| step | what the agent did | what the docs require (file:line) | check/criterion | class |", "|---|---|---|---|---|", ""]
    text = "\n".join(out)
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}: {len(rows)} rows")
    else:
        print(text)


if __name__ == "__main__":
    main()
