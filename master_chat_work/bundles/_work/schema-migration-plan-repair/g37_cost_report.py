from __future__ import annotations

import json
import re
from pathlib import Path

WORK = Path(__file__).resolve().parent
PROTO = WORK / "proto"
HEADING = "## Gate v3.7 measured final costs (board 9111ecc)"
CAP = 70.0
LABELS = {
    "a6": "a6 final repo (bar)", "a5": "a5 agent program", "blind": "blind cee149a", "blind2": "blind 4f7606c",
    "tb_d721": "blind d721", "tb_d2fb": "blind d2fb", "tb_9179": "blind 9179", "tb_b686": "blind b686",
    "opus": "first write (Opus a4)", "abo": "all-but-one (oracle + plain Dijkstra planner)",
    "gen_astar": "generic A* schema bound", "gen_signature_keyed": "generic prerequisite-keyed",
    "gen_dominance": "generic dominance", "gen_incumbent": "generic incumbent", "gen_greedy": "generic greedy",
    "gen_exhaustive": "generic exhaustive", "gen_bidirectional": "generic bidirectional",
    "gen_schema_only": "generic schema-only",
}


def finished() -> list[str]:
    done = ["a6", "a5"]
    for chain in ("g37_chainA.log", "g37_chainA2.log", "g37_chainB.log"):
        path = PROTO / chain
        if path.exists():
            done += [line.split()[1] for line in path.read_text().splitlines() if line.startswith("RUN ")]
    return done


def kind(check: dict[str, object], difference: str) -> str:
    if int(check["weight"]) < 0:
        return "TRIGGERED" if check["pass"] else "NOT_TRIGGERED"
    if check["pass"]:
        return "EXACT"
    if "TimeoutExpired" in difference:
        return "TIMEOUT"
    if re.match(r"(?:CalledProcessError|MemoryError|BrokenPipeError):", difference):
        return "CRASH"
    return "WRONG"


def summarise(program: str) -> dict[str, object]:
    data = json.loads((PROTO / f"g37_cost_{program}.json").read_text())
    witnesses = {}
    for line in (PROTO / f"g37_cost_{program}.txt").read_text().splitlines():
        if line.startswith("[check] "):
            witness = json.loads(line.removeprefix("[check] "))
            witnesses[witness["name"]] = witness
    groups = {g: {"EXACT": 0, "WRONG": 0, "TIMEOUT": 0, "CRASH": 0} for g in ("old_core", "new_tier", "other")}
    seconds = {"old_core": 0.0, "new_tier": 0.0, "other": 0.0}
    other_lost = []
    for name, check in data["checks"].items():
        number_match = re.match(r"world_(\d+)_core", name)
        number = int(number_match[1]) if number_match else 0
        group = "new_tier" if number >= 47 else "old_core" if number >= 29 else "other"
        seconds[group] += check["sec"]
        result = kind(check, witnesses.get(name, {}).get("first_difference", ""))
        if result in groups[group]:
            groups[group][result] += check["weight"]
        if group == "other" and result in ("WRONG", "TIMEOUT", "CRASH", "TRIGGERED"):
            other_lost.append(f"{name} {result} w{check['weight']}")
    positive = data["positive"]
    lost = positive - data["earned"]
    ct = sum(groups[g]["TIMEOUT"] + groups[g]["CRASH"] for g in groups)
    lever_lost = 300 - groups["new_tier"]["EXACT"]
    lever_ct = groups["new_tier"]["TIMEOUT"] + groups["new_tier"]["CRASH"]
    return {
        "tests_percent": 100 * data["score"], "earned": data["earned"], "positive": positive,
        "wall_seconds": data["wall_seconds"], "groups": groups,
        "crash_timeout_points": ct, "crash_timeout_share_of_positive": 100 * ct / positive,
        "crash_timeout_share_of_lost": 100 * ct / lost if lost else 0.0,
        "lever_lost_points": lever_lost, "lever_lost_percent": 100 * lever_lost / 300,
        "lever_wrong_points": groups["new_tier"]["WRONG"],
        "lever_crash_timeout_share_of_lever_lost": 100 * lever_ct / lever_lost if lever_lost else 0.0,
        "old_core_seconds": round(seconds["old_core"], 2), "new_tier_seconds": round(seconds["new_tier"], 2),
        "check_seconds": round(sum(seconds.values()), 2), "other_lost": other_lost,
    }


def main() -> None:
    summaries = {}
    rows = [
        "| Program | Earned / positive | Tests % | Wall s | Lever lost (WRONG / TIMEOUT+CRASH) | Old core lost (T+C) | Crash+timeout / positive | Crash+timeout / lost | Cap 70% |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for program in finished():
        s = summarise(program)
        summaries[program] = s
        g = s["groups"]
        rows.append(
            f"| {LABELS.get(program, program)} | {s['earned']}/{s['positive']} | {s['tests_percent']:.2f} | {s['wall_seconds']} | "
            f"{s['lever_lost_points']}/300 ({g['new_tier']['WRONG']} / {g['new_tier']['TIMEOUT'] + g['new_tier']['CRASH']}) | "
            f"{g['old_core']['TIMEOUT'] + g['old_core']['CRASH']}/90 | {s['crash_timeout_share_of_positive']:.2f}% | "
            f"{s['crash_timeout_share_of_lost']:.2f}% | {'ok' if s['crash_timeout_share_of_positive'] <= CAP else 'OVER'} |"
        )
    (PROTO / "g37_cost_summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    worst = max(summaries.items(), key=lambda item: item[1]["wall_seconds"])
    report = "\n\n" + HEADING + "\n\n" + "\n".join(rows) + "\n\n"
    report += (
        "Each row is a complete final-test run (141 checks, 591 positive) in Docker, 4 GiB and 2 CPUs. Loss kinds come from each "
        "check's emitted first_difference. The cap column uses the master's measure (crash+timeout points / positive test points, "
        "under which a5 390/591 = 65.99% is inside the raised 70% limit); the share of lost points is shown beside it. "
        f"Slowest measured verifier run: {LABELS.get(worst[0], worst[0])}, {worst[1]['wall_seconds']} s (limit 2,430 s).\n\n"
    )
    report += "### Lost points outside the core worlds\n\n" + "\n".join(
        f"- {LABELS.get(p, p)}: {', '.join(s['other_lost']) or 'none'}" for p, s in summaries.items()
    ) + "\n"
    cost_file = WORK / "COST_TABLE.md"
    before = cost_file.read_text().split(HEADING)[0].rstrip()
    cost_file.write_text(before + report)
    print("\n".join(rows))


if __name__ == "__main__":
    main()
