#!/usr/bin/env python3
"""R4 Phase A facts for the 13 models (read only). Re-run: python3 OUT/scripts/genuineness.py
Writes OUT/genuineness_facts.md. Verifier test-stdout.txt holds only 'reward: x' in this repo, so failure
reasons come from: artifacts present, result.json exception/timing, agent final message, test/solution design scans."""
import json, os, glob, re
from datetime import datetime

REPO = "/Users/mac/Desktop/Terminal Bench/anubis-stage-1"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ["8defd7be", "42e79476", "59417607", "aa314fee", "9f5486ac", "d49e259f", "5b2b0901",
          "df8f123b", "b5c7b14c", "6d12f970", "80202e15", "725e575c", "18b5d99f"]
GEN = r"random\.Random|Random\(|seed"
TMO = r"timeout\s*=\s*([0-9.]+)"
FIT = r"\b(fit|search|infer|recover|candidate|brute)"
KW = {
    "rerun_promise": r"(unseen|fresh|different|other|new|held[- ]out|hidden)\s+(input|extract|run|shift|corpus|data|intake|instance|month)s?",
    "time_budget_stated": r"(seconds|second budget|within \d+|time limit|finishes? in|wall)",
    "no_tests_peek": r"/tests|grading",
}


def ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00"))


def lines_hit(text, pat, n=3):
    out = []
    for i, l in enumerate(text.splitlines(), 1):
        if re.search(pat, l, re.I):
            out.append(f"L{i}: {l.strip()[:200]}")
            if len(out) >= n: break
    return out


def main():
    md = ["# Phase A facts (script output; see scripts/genuineness.py)\n"]
    for tid in MODELS:
        td = glob.glob(os.path.join(REPO, tid + "*"))[0]
        run = sorted(glob.glob(os.path.join(td, "trajectories", "*", "run_1")))[0]
        res = json.load(open(os.path.join(run, "result.json")))
        instr = open(os.path.join(td, "instruction.md"), errors="ignore").read()
        tp = open(os.path.join(td, "tests", "test_output.py"), errors="ignore").read()
        sol_files = [f for f in glob.glob(os.path.join(td, "solution", "**", "*"), recursive=True) if os.path.isfile(f)]
        sol = "".join(open(f, errors="ignore").read() for f in sol_files)
        man = json.load(open(os.path.join(run, "artifacts", "manifest.json")))
        arts = [(m["source"], m["status"]) for m in man]
        traj = json.load(open(os.path.join(run, "agent", "trajectory.json")))
        steps = traj["steps"]
        final_msg = ""
        for s in reversed(steps):
            if s.get("source") == "agent" and s.get("message"):
                final_msg = s["message"]; break
        ae = res.get("agent_execution") or {}
        amin = round((ts(ae["finished_at"]) - ts(ae["started_at"])).total_seconds() / 60, 1) if ae.get("finished_at") else None
        md.append(f"## {tid}")
        md.append(f"- exception_info: {res.get('exception_info')!r}; agent minutes {amin}; agent steps {len(steps)}")
        md.append(f"- artifacts: {arts}")
        md.append(f"- instruction words {len(instr.split())}; rerun-promise hits: {lines_hit(instr, KW['rerun_promise'])}")
        md.append(f"- instruction time-budget hits: {lines_hit(instr, KW['time_budget_stated'], 2)}")
        md.append(f"- tests: loc {tp.count(chr(10))}; subprocess={'subprocess' in tp}; seeded generator={bool(re.search(GEN, tp))}; "
                  f"reads /app/data={'/app/data' in tp}; base64/zlib blobs={bool(re.search(r'b64decode|zlib|lzma|gzip', tp))}; timeout= {re.findall(TMO, tp)[:4]}")
        md.append(f"- solution files {[os.path.relpath(f, td) for f in sol_files][:6]}; sol bytes {len(sol)}; "
                  f"sol mentions fit/search/infer/recover: {len(re.findall(FIT, sol, re.I))}")
        fm = final_msg.replace("\n", " ")
        md.append(f"- agent final message ({len(final_msg)} chars), head: {fm[:700]}")
        md.append(f"- final message admits gaps: {lines_hit(final_msg, r'not (yet )?(settled|resolved|match|agree)|do(es)? not (match|agree)|unresolved|could not|remain(s|ing)? open|mismatch|differ', 4)}")
        md.append("")
    open(os.path.join(OUT, "genuineness_facts.md"), "w").write("\n".join(md))
    print("wrote genuineness_facts.md")


if __name__ == "__main__":
    main()
