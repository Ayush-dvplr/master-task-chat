#!/usr/bin/env python3
"""Build a deep research prompt (ChatGPT or Gemini) from the current knowledge files.

Kinds:
  verify          check what we believe against outside evidence
  discover        propose new task ideas under the design rotation
  explore         find new lever angles outside the known families
  teammate_study  study teammate task ids not yet carded

Every run reads the files again, so the prompt grows with the knowledge base and
survives compaction. Standard library only.

Usage:
  python3 research_prompt.py --kind discover [--root REPO] [--out FILE] [--n 5]
"""

import argparse
import csv
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

KINDS = ("verify", "discover", "explore", "teammate_study")

# Relative to the repository root.
SOURCES = {
    "patterns": "upgrade_plan/knowledge/PATTERNS.md",
    "confirm": "upgrade_plan/knowledge/CONFIRM.md",
    "settings": "upgrade_plan/drafts/P1/settings.json",
    "registry": "master_chat_tasks/registry/tasks.json",
    "ideas": "master_chat_tasks/registry/ideas.jsonl",
    "leaks": "master_chat_tasks/knowledge/LEAK_LIBRARY.md",
    "angles": "master_chat_tasks/knowledge/ANGLES.md",
    "index": "upgrade_plan/tmp/S2-INDEX/INDEX.csv",
    "cards_dir": "upgrade_plan/tmp/S2-CARDS",
    "study_cards_dir": "master_chat_work/20261102_test_design_study/cards",
    "r4_cards_dir": "master_chat_work/20261028_upgrade/R4_teammate_repo/cards",
    "features": "upgrade_plan/tmp/S2-FEATURES/FEATURES.csv",
    "card_log": "master_chat_tasks/registry/design_cards.jsonl",
    "intake": "master_chat_work/research/INTAKE.jsonl",
}

# Used only when design_cards.jsonl does not exist yet: families and domains of
# Ayush's new builds as labelled in W1-034 WHY_NEW_FAILS.md section 3 (INFERRED).
SEED_CARD_LOG = [
    ("metered-usage-rating-pipeline", "D3", "billing"),
    ("tariff-engine-audit-repair", "D3", "billing"),
    ("data-product-config-compiler", "D3", "config tooling"),
    ("cleanroom-window-schedule", "D4", "scheduling optimization"),
    ("cold-chain-backbone-quote", "D4", "network optimization"),
    ("counter-page-crash-recovery", "D1", "storage recovery"),
    ("batch-lease-scheduler-replay", "D1", "scheduling"),
    ("fuel-card-settlement-consolidation", "D3", "settlement"),
    ("pilotage-dues-reconstruction", "D3", "port dues"),
    ("outage-window-replan", "D4", "scheduling optimization"),
    ("backdated-entitlement-replay", "D3", "entitlements"),
    ("flood-repair-portfolio", "D4", "portfolio optimization"),
    ("hangar-check-replan", "D4", "scheduling optimization"),
    ("depot-charge-plan", "D4", "scheduling optimization"),
]

# Family order for the rotation: confirmed teammate evidence first (PATTERNS.md, CONFIRM.md).
FAMILY_RANK = ["D2", "D1", "D8", "D5", "D6", "D9", "D3", "D4"]
NEVER_PRIMARY = {"D7"}
EXTRA_ONLY = {"D4"}

FAIL_WORDS = {"NO CORE": "NO CORE", "exact": "blind or program exact", "kill rule": "kill rule",
              "leak": "levers leaked", "blind reads 3/3": "3 of 3 blinds full marks",
              "ROUND LIMIT": "harden round limit", "no lever": "no lever found",
              "transliterat": "contract transliterated"}


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def digest(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    except OSError:
        return "missing"


def plain(text, limit=220):
    """Shorten a line and turn arrow and dash punctuation into words."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" -> ", " to ").replace("->", " to ").replace(" - ", ", ")
    text = text.replace("**", "")
    if len(text) > limit:
        text = text[: limit - 3].rsplit(" ", 1)[0] + " ..."
    return text


def load_settings(root):
    try:
        data = json.loads(read_text(root / SOURCES["settings"]))
    except ValueError:
        data = {}
    gate = data.get("gate", {"tests": 85, "rubric": 85, "final": 40})
    return {
        "gate": gate,
        "design_margin": data.get("design_margin", 5),
        "no_core_keep_pct": data.get("no_core_keep_pct", 60),
        "unique_last": data.get("card", {}).get("unique_last", 3),
    }


def parse_families(root):
    """Return {id: {"name", "cost", "recipe"}} from PATTERNS.md section 1."""
    families = {}
    current = None
    for line in read_text(root / SOURCES["patterns"]).splitlines():
        head = re.match(r"^(D\d+)\.?\s*(?:\(NOT IN SUMMARY\)\.)?\s*(.+)$", line)
        if head:
            current = head.group(1)
            families[current] = {"name": plain(head.group(2), 120), "cost": "", "recipe": ""}
            continue
        if line.startswith("2. TEST STRUCTURE"):
            current = None
        if current:
            item = re.match(r"^\d+\.\s*(Cost|Recipe):\s*(.+)$", line)
            if item:
                families[current][item.group(1).lower()] = plain(item.group(2), 200)
    return families


def parse_confirm(root):
    """Return list of (id, line) from CONFIRM.md numbered section heads."""
    rows = []
    for line in read_text(root / SOURCES["confirm"]).splitlines():
        head = re.match(r"^(\d)\.\s+([A-Z].+:\s*(?:PARTLY )?CONFIRMED.*)$", line)
        if head:
            rows.append(("C" + head.group(1), plain(head.group(2), 160)))
    return rows


def parse_registry(root, gate_tests):
    """Classify tasks into held (paid tests under the gate) and failed (lever kept)."""
    try:
        data = json.loads(read_text(root / SOURCES["registry"]))
    except ValueError:
        return [], []
    held, failed = [], []
    for task in data.get("tasks", []):
        pipe = task.get("pipeline", {})
        slug = task.get("slug", "?")
        kind = pipe.get("kind", "?")
        stage = pipe.get("stage", "?")
        nxt = str(pipe.get("next", ""))
        try:
            tests = float(pipe.get("traj_tests"))
        except (TypeError, ValueError):
            tests = None
        final = pipe.get("traj_overall", "?")
        if tests is not None and tests < gate_tests and stage in ("pushed", "fix", "qc", "gate_runs"):
            held.append(f"{slug} ({kind}, {stage}): paid tests {tests:g}, final {final}")
        elif (tests is not None and tests >= 95) or (
                stage in ("parked", "dropped") and any(w.lower() in nxt.lower() for w in FAIL_WORDS)):
            why = [label for w, label in FAIL_WORDS.items() if w.lower() in nxt.lower()]
            reason = ", ".join(why) if why else "tests at or above 95"
            shown = f"paid tests {tests:g}" if tests is not None else "no paid score"
            failed.append(f"{slug} ({kind}, {stage}): {shown}; record says {reason}")
    return held, failed


def parse_leaks(root):
    causes, in_causes = [], False
    rows = 0
    for line in read_text(root / SOURCES["leaks"]).splitlines():
        if line.startswith("## Common causes"):
            in_causes = True
            continue
        if line.startswith("## "):
            in_causes = False
        if in_causes and line.startswith("- "):
            causes.append(plain(line[2:].split(" Fix:")[0], 160))
        if line.startswith("| ") and not line.startswith("| lever") and not line.startswith("|---"):
            rows += 1
    return causes, rows


def parse_angles(root):
    tried, untried = [], []
    for line in read_text(root / SOURCES["angles"]).splitlines():
        row = re.match(r"^\|\s*(A\d+)\s*\|\s*([^|]+)\|.*\|\s*([SMWN])[^|]*\|\s*$", line)
        if row:
            tried.append(f"{row.group(1)} ({row.group(3)}): {plain(row.group(2), 120)}")
            continue
        item = re.match(r"^\d+\.\s+(U\d+)\s+([^.]+)\.", line)
        if item:
            untried.append(f"{item.group(1)}: {plain(item.group(2), 90)}")
    return tried, untried


def parse_ideas(root):
    titles = []
    for line in read_text(root / SOURCES["ideas"]).splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        title = row.get("title")
        if title:
            titles.append(f"{plain(title, 80)} ({row.get('verdict', row.get('status', '?'))})")
    return titles


def parse_intake(root):
    """Items stored by RESEARCH_INTAKE.md; optional."""
    items = []
    for line in read_text(root / SOURCES["intake"]).splitlines():
        try:
            items.append(json.loads(line))
        except ValueError:
            continue
    return items


def card_log(root):
    rows = []
    for line in read_text(root / SOURCES["card_log"]).splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        rows.append((row.get("slug", "?"), row.get("family", "?"), row.get("domain", "?")))
    return (rows, "design_cards.jsonl") if rows else (SEED_CARD_LOG, "seed list (INFERRED, W1-034)")


def rotation(root, settings):
    rows, origin = card_log(root)
    recent = rows[-settings["unique_last"]:]
    recent_fams = {fam for _, fam, _ in recent}
    recent_doms = {dom for _, _, dom in recent}
    counts = {}
    for _, fam, _ in rows:
        counts[fam] = counts.get(fam, 0) + 1
    allowed = [f for f in FAMILY_RANK if f not in recent_fams and f not in NEVER_PRIMARY and f not in EXTRA_ONLY]
    return {"origin": origin, "recent": recent, "avoid_families": sorted(recent_fams),
            "avoid_domains": sorted(recent_doms), "allowed": allowed, "counts": counts}


def teammate_unstudied(root, n):
    studied = set()
    for key in ("cards_dir", "study_cards_dir", "r4_cards_dir"):
        folder = root / SOURCES[key]
        if folder.is_dir():
            studied.update(p.stem[:8] for p in folder.glob("*.md"))
    # FEATURES.csv holds only teammate tasks (Ayush's own are left out there), so it is the filter.
    teammates = set()
    try:
        with open(root / SOURCES["features"], newline="", encoding="utf-8") as handle:
            teammates = {row.get("task", "")[:8] for row in csv.DictReader(handle)}
    except OSError:
        pass
    studied &= teammates
    rows = []
    try:
        with open(root / SOURCES["index"], newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                tid = row.get("task", "")[:8]
                if not tid or tid in studied or tid not in teammates:
                    continue
                try:
                    final = float(row.get("opus_final") or 999)
                except ValueError:
                    final = 999.0
                rows.append((final, tid, row.get("category", "?"), plain(row.get("description", ""), 110)))
    except OSError:
        return studied, []
    rows.sort()
    return studied, rows[:n]


CONTEXT = (
    "We design hard but fair tasks for a terminal agent benchmark. A frontier coding agent "
    "(Claude Opus class) gets a Linux container with Python 3 standard library, input files and a "
    "written instruction, and must deliver a program plus exact output files. Hidden tests rerun its "
    "program on fresh inputs and compare whole documents; a judge reads its work log. A task counts "
    "only if every graded value is decided by the shipped instruction and data (no unwritten rule, "
    "constant, form or tie break), it passes a strict quality review, and the agent scores under the "
    "gate. Hiding a case in the hidden data is normal design; hiding a rule is not allowed."
)

ANSWER_FORMAT = """BEGIN RESEARCH ANSWER
prompt_id: {pid}
tool: <ChatGPT | Gemini | other>
items: <number of ITEM blocks>
ITEM 1
type: <claim | idea | angle | teammate_pattern>
family: <one of D1 to D9, or NEW>
relation: <confirms ID | refutes ID | new> (ID is an id from this prompt: K, C, F, A, U or I)
title: <at most 12 words>
statement: <two to four sentences>
evidence: <source with a link or full citation; write none if it is your reasoning only>
confidence: <high | medium | low>
check: <one measurable check we can run on our own records or a small prototype>
domain: <idea and teammate_pattern only, else n/a>
data_shape: <idea only: what the shipped files look like, else n/a>
deliverable: <idea only, else n/a>
deciding_sentence: <idea only: the one doc sentence that decides the lever, else n/a>
hidden_plan: <idea only: what the hidden inputs carry that the shipped ones never show, else n/a>
careful_program_path: <idea and angle: what a careful exact program writes and where it goes wrong, else n/a>
solvability: <idea only: why every graded value follows from the shipped docs and data, else n/a>
END ITEM
(repeat ITEM blocks, numbered)
END RESEARCH ANSWER"""


def build(kind, root, n):
    settings = load_settings(root)
    gate = settings["gate"]
    families = parse_families(root)
    confirms = parse_confirm(root)
    held, failed = parse_registry(root, gate.get("tests", 85))
    causes, leak_rows = parse_leaks(root)
    tried, untried = parse_angles(root)
    idea_titles = parse_ideas(root)
    intake = parse_intake(root)
    rot = rotation(root, settings)

    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    stamp = datetime.datetime.now(ist).strftime("%Y%m%dT%H%M")
    digests = {k: digest(root / SOURCES[k]) for k in ("patterns", "confirm", "registry", "leaks", "angles", "ideas")}
    pid = f"{kind}-{stamp}-" + hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()[:8]

    out = [f"RESEARCH PROMPT {pid}",
           "Sources: " + ", ".join(f"{k} {v}" for k, v in digests.items()),
           "", "CONTEXT", CONTEXT,
           f"Gate: tests under {gate.get('tests')}, rubric under {gate.get('rubric')}, final under {gate.get('final')}.",
           "", "WHAT WE KNOW (short; ids are for your answer)"]

    for fid, fam in families.items():
        if fid in NEVER_PRIMARY:
            continue
        line = f"{fid}: {fam['name']}."
        if fam["cost"]:
            line += f" Measured cost: {fam['cost']}"
        out.append(line)
    for cid, text in confirms:
        out.append(f"{cid}: {text}")
    out.append(f"K1: in our own builds a careful exact program, written from complete docs, transliterated "
               f"stated rule, unique fit over a stated domain and exact optimum levers in 2 to 4 minutes "
               f"(13 design rounds lost; W1-034 WHY_NEW_FAILS.md).")
    out.append(f"K2: tasks whose paid run kept tests under the gate ({len(held)}; final may still be over it): " + ("; ".join(held[:8]) or "none"))
    out.append(f"K3: tasks whose lever was kept by the agent or a blind ({len(failed)}): " + ("; ".join(failed[:10]) or "none"))
    for i, cause in enumerate(causes[:6], 1):
        out.append(f"F{i}: leak cause: {cause}")
    out.append(f"(leak library rows: {leak_rows})")

    out += ["", "WHAT WE WANT"]
    if kind == "verify":
        out.append(f"Check the K, C and family statements above against outside evidence: papers, public "
                   f"benchmark reports, agent evaluation write ups, parser and standard conformance studies. "
                   f"For each one say confirms or refutes, with the source, and give one check we can run. "
                   f"Start with items marked PARTLY. Return {n} to {2 * n} items of type claim.")
        pending = [x for x in intake if x.get("status") == "new" and x.get("type") == "claim"]
        if pending:
            out.append("Also verify these received but unchecked claims:")
            out += [f"I{x.get('id', '?')}: {plain(x.get('title', x.get('statement', '')), 140)}" for x in pending[:10]]
    elif kind == "discover":
        out.append(f"Propose {n} new task ideas. Start each from a domain and a data shape, then use one primary "
                   f"family from the allowed list. Each idea needs its deciding sentence, a hidden data plan in "
                   f"which most hidden inputs fire the lever with varied count and shape, the careful program's "
                   f"path to a wrong answer, and a solvability argument. Return items of type idea.")
        out.append("Allowed primary families, in order of preference: " + ", ".join(rot["allowed"]) + ".")
        out.append("Recent builds (" + rot["origin"] + "): " +
                   "; ".join(f"{s} {f} {d}" for s, f, d in rot["recent"]) + ".")
        out.append("Avoid these domains: " + ", ".join(rot["avoid_domains"]) + "; and optimization, scheduling, "
                   "billing and settlement, which carried "
                   + str(sum(1 for _, _, d in card_log(root)[0] if any(w in d for w in ("optim", "schedul", "billing", "settle"))))
                   + " of our builds.")
    elif kind == "explore":
        out.append(f"Find mechanisms outside D1 to D9 by which a careful exact program, written from complete "
                   f"and correct docs, gives a wrong answer on legal hidden inputs, and which a task can state "
                   f"in one deciding sentence. Look at parser differential studies, conformance test suites of "
                   f"public standards, data format edge cases, carried state bugs in incident reports, and "
                   f"specification ambiguity research. Also propose new research angles for our own teammate "
                   f"task corpus. Return {n} items of type angle, each with its careful_program_path.")
    else:
        studied, rows = teammate_unstudied(root, n)
        out.append(f"This kind runs where the teammate corpus is readable (an own session with the repository, "
                   f"or uploaded task folders). We have carded {len(studied)} teammate tasks. Study these "
                   f"uncarded ids, lowest Opus final first. For each, name the family (D1 to D9 or NEW), the "
                   f"deciding line as file:line, the points lost by the careful program, and whether every "
                   f"graded value is decided by the shipped files. Return items of type teammate_pattern. "
                   f"Patterns only: never copy task text, data or code.")
        out += [f"T{i}: {tid} ({cat}, Opus final {fin:g}): {desc}" for i, (fin, tid, cat, desc) in enumerate(rows, 1)]

    out += ["", "WHAT TO AVOID REPEATING"]
    out.append("Research angles already run: " + "; ".join(tried) + ".")
    if untried and kind in ("explore", "teammate_study"):
        out.append("Ranked untried angles you may take: " + "; ".join(untried[:8]) + ".")
    if idea_titles and kind == "discover":
        out.append("Ideas already received: " + "; ".join(idea_titles) + ".")
    received = [x for x in intake if x.get("status") in ("kept", "rejected", "verified", "new")]
    if received:
        out.append(f"Items already received from earlier answers ({len(received)}): " +
                   "; ".join(plain(x.get("title", ""), 60) for x in received[:15]) + ".")
    out.append("Do not propose: a stated rule that a careful reader writes as code (F and K1); rules that are "
               "unwritten or confirmed only by examples or digests; exact optimum or runtime as the main "
               "difficulty; textbook puzzles; volume alone.")

    out += ["", "RULES FOR YOUR ANSWER",
            "Do not invent sources. Mark reasoning without a source as evidence: none. No implementation code, "
            "no generated data, no task text. Use the exact format below so it can be stored by a script; "
            "nothing outside the BEGIN and END lines is read.",
            "", "ANSWER FORMAT", ANSWER_FORMAT.format(pid=pid)]
    return "\n".join(out) + "\n", pid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[3]),
                        help="repository root (default: three folders above this script)")
    parser.add_argument("--out", help="write the prompt here instead of standard output")
    parser.add_argument("--n", type=int, default=5, help="number of items or ids asked for")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not (root / SOURCES["patterns"]).exists():
        print(f"error: {root / SOURCES['patterns']} not found; pass --root", file=sys.stderr)
        return 2
    text, pid = build(args.kind, root, args.n)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{pid} {len(text)} chars {len(text.split())} words -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
