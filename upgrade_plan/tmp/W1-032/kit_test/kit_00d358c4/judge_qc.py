#!/usr/bin/env python3
"""Judge QC: schema, enums, numbering, weights, phrasing of tests/judge.toml.

tests/judge.toml is the LLM-judged half of grading (the deterministic half
lives in test_output.py). rewardkit consumes it at run time and it is as
important as the tests. The file carries a pinned [judge] header, a [scoring]
table, and one [[criterion]] table per criterion, each with its own mandatory
[criterion.annotations] table. The sign of a criterion's integer weight is
its only polarity marker; tests/reward.toml divides the channel's
weighted-sum by its positive total and halves it.

What this script enforces, per criterion:

  J1      criterion keys are exactly id, name, description, type, weight in
          that order (then annotations); any other key fails, negate and
          points included.
  J2      ids are R1, R2, R3... sequential, no gaps, no R1a variants.
  J3      name is unique in the file and matches ^[a-zA-Z0-9_-]{1,64}$ (it
          becomes a property key in the judge's structured output).
  J4      type is "binary".
  J5      weight is an integer in {1, 3, 5, -1, -3, -5}; floats (3.0), zero
          and other magnitudes fail.
  J6      [criterion.annotations] exists with exactly the keys mode, type,
          evaluation_target, importance, in that order, nothing else, all
          non-empty strings. The retired keys category, kind, serves,
          residue, evidence, contract_sentence and contract_file fail.
  J7      annotation values: mode = "judged"; type is the criterion's
          category (task completion, instruction following, tool use, agent
          behavior, factuality and hallucination, safety and boundaries -
          "safety and boundaries" with "and"); evaluation_target and
          importance from the allowed sets.
  J8      description is present and non-empty. J9-J12 are skipped for a
          criterion without one.
  J9      phrasing prefix follows the target: "The response ..." for
          final_answer/user_facing_message, "The agent ..." for
          trajectory/state_change.
  J10     no negative grammar (not, without, fails to, cannot, instead of):
          a negative criterion describes the bad behaviour happening and
          carries a negative weight.
  J11     no vague qualifiers (approximately, properly, correctly...) and
          no threshold-free quantifiers (many, several, few, repeatedly);
          "some" warns.
  J12     no brackets, placeholders, em/en dashes, or tag prefixes inside
          description text.
  J13     importance pairs with |weight|: critically_important needs 3 or
          5; important needs 1 or 3.

And whole-file:

  G1      judge.toml parses and carries a [judge] table plus at least one
          [[criterion]].
  G2      [judge] is exactly judge = "openai/gpt-5.6-sol", mode =
          "batched", timeout = 300, atif-trajectory =
          "/logs/agent/trajectory.json", weight = 1.0, in that order (no
          reasoning_effort key);
          [scoring] is exactly aggregation = "weighted-sum"; no other
          top-level key.
  G3      8..35 criteria (more than 35 warns).
  G4      at least one positive and at least one negative weight.
  G5      weights must not all be identical.
  G6      sum of |negative weights| <= sum of positive weights, so the judge
          channel's share never drops below -0.5.

Usage: python3 judge_qc.py /path/to/bundle
Exit codes: 0 = pass (warns allowed), 1 = fail, 2 = usage error.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

FAILS: list[str] = []
WARNS: list[str] = []
PASSES: list[str] = []


def fail(check: str, msg: str) -> None:
    FAILS.append(f"FAIL [{check}] {msg}")


def warn(check: str, msg: str) -> None:
    WARNS.append(f"WARN [{check}] {msg}")


def ok(check: str, msg: str) -> None:
    PASSES.append(f"pass [{check}] {msg}")


def fails_for(check: str) -> int:
    return sum(1 for line in FAILS if line.startswith(f"FAIL [{check}] "))


# The pinned header, identical in every task. reasoning_effort is not part of
# it: the key is left out and fails as an extra key.
JUDGE_HEADER: list[tuple[str, object]] = [
    ("judge", "openai/gpt-5.6-sol"),
    # rewardkit's own default. "individual" would judge each criterion in its
    # own concurrent call, which re-sends the whole trajectory once per
    # criterion; on a 30-criterion file that is 30x the input tokens for the
    # same verdicts. Its one advantage, per-criterion "files", is already
    # forbidden by J1, so batched costs this contract nothing.
    ("mode", "batched"),
    ("timeout", 300),
    # Without this key rewardkit 0.2.1 never hands the trajectory to the judge,
    # so every trajectory / state_change criterion would be judged blind.
    ("atif-trajectory", "/logs/agent/trajectory.json"),
    ("weight", 1.0),
]
SCORING_HEADER: list[tuple[str, object]] = [("aggregation", "weighted-sum")]
TOP_LEVEL = {"judge", "scoring", "criterion"}

CRITERION_KEYS = ["id", "name", "description", "type", "weight"]
WEIGHTS = {1, 3, 5, -1, -3, -5}
NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

MODE = "judged"
RETIRED_ANNOTATIONS = ["category", "kind", "serves", "residue", "evidence",
                       "contract_sentence", "contract_file"]
CATEGORIES = {
    "task completion", "instruction following", "tool use", "agent behavior",
    "factuality and hallucination", "safety and boundaries",
}
TARGETS = {"final_answer", "user_facing_message", "trajectory", "state_change"}
RESPONSE_TARGETS = {"final_answer", "user_facing_message"}
IMPORTANCE = {"critically_important", "important"}
ANNOTATION_KEYS = ["mode", "type", "evaluation_target", "importance"]

NEGATIVE_TOKENS = [
    (re.compile(r"\bnot\b", re.I), "not"),
    (re.compile(r"\bwithout\b", re.I), "without"),
    (re.compile(r"\bfails? to\b", re.I), "fails to"),
    (re.compile(r"\bcannot\b", re.I), "cannot"),
    (re.compile(r"\binstead of\b", re.I), "instead of"),
]
VAGUE = [
    "approximately", "around", "about", "roughly", "mostly", "typically",
    "often", "properly", "correctly", "clearly", "adequately",
    # Threshold-free quantifiers: a judge has no way to decide how many is
    # enough, so two judges reach different verdicts on the same transcript.
    # Criteria must state counts ("at least five") instead.
    "many", "several", "few", "repeatedly",
]
DASH_RE = re.compile("[\u2013\u2014]")
PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}|<[A-Z_]+>|\bTODO\b|\bFIXME\b")


def is_int_weight(v: object) -> bool:
    return type(v) is int and v in WEIGHTS


def key_order_msg(want: list[str], got: list[str]) -> str:
    missing = [k for k in want if k not in got]
    extra = [k for k in got if k not in want]
    parts = ([f"missing {missing}"] if missing else []) + ([f"extra {extra}"] if extra else [])
    return "; ".join(parts) or "wrong order"


def check_header(data: dict) -> None:
    """Run G2: the [judge] and [scoring] tables are pinned, and no other
    top-level key exists."""
    for table_name, pinned in (("judge", JUDGE_HEADER), ("scoring", SCORING_HEADER)):
        table = data.get(table_name)
        if not isinstance(table, dict):
            fail("G2", f"[{table_name}] table is missing")
            continue
        expected = [k for k, _ in pinned]
        got = list(table.keys())
        if got != expected:
            fail("G2", f"[{table_name}] keys must be exactly {expected} in that order, got {got}")
        for key, value in pinned:
            if key not in table:
                continue
            if isinstance(value, set):
                if table[key] not in value:
                    fail("G2", f"[{table_name}] {key} must be one of {sorted(value)}, got {table[key]!r}")
            elif table[key] != value or type(table[key]) is not type(value):
                fail("G2", f"[{table_name}] {key} must be {value!r}, got {table[key]!r}")

    extra = [k for k in data if k not in TOP_LEVEL]
    if extra:
        fail("G2", f"unexpected top-level key(s) {sorted(extra)}; only {sorted(TOP_LEVEL)} are allowed")
    if not fails_for("G2"):
        ok("G2", "pinned [judge] and [scoring] header exact")


def check_annotations(ident: str, c: dict) -> dict:
    """Run J6-J7 on one criterion's annotations table and return it (empty
    dict when absent, so callers can keep going)."""
    ann = c.get("annotations")
    if not isinstance(ann, dict):
        fail("J6", f"{ident}: [criterion.annotations] table is missing")
        return {}

    got = list(ann.keys())
    if got != ANNOTATION_KEYS:
        retired = [k for k in got if k in RETIRED_ANNOTATIONS]
        hint = (f"; {retired} are retired keys: remove them"
                + (" (the category value goes in type)" if "category" in retired else "")) if retired else ""
        fail("J6", f"{ident}: annotations keys must be exactly {ANNOTATION_KEYS} in that order "
             f"({key_order_msg(ANNOTATION_KEYS, got)}), got {got}{hint}")
    for key in ANNOTATION_KEYS:
        if key in ann and not (isinstance(ann[key], str) and ann[key].strip()):
            fail("J6", f"{ident}: annotations {key} must be a non-empty string")

    if ann.get("mode") != MODE:
        fail("J7", f"{ident}: annotations mode must be {MODE!r}, got {ann.get('mode')!r}")

    t = ann.get("type")
    if t == "safety & boundaries":
        fail("J7", f"{ident}: annotations type must be written 'safety and boundaries' "
             "with the word 'and', got '&'")
    elif t not in CATEGORIES:
        fail("J7", f"{ident}: annotations type {t!r} not in allowed set {sorted(CATEGORIES)}")

    tgt = ann.get("evaluation_target")
    if tgt not in TARGETS:
        fail("J7", f"{ident}: annotations evaluation_target {tgt!r} not in {sorted(TARGETS)}")

    imp = ann.get("importance")
    if imp not in IMPORTANCE:
        fail("J7", f"{ident}: annotations importance {imp!r} not in {sorted(IMPORTANCE)}")

    return ann


def check_criterion(i: int, c: dict, seen_names: dict[str, str]) -> None:
    """Run J1-J13 (see module docstring) on one criterion; i is the zero-based
    position used to enforce sequential ids."""
    ident = str(c.get("id") or f"index {i}")

    got = [k for k in c if k != "annotations"]
    if got != CRITERION_KEYS:
        fail("J1", f"{ident}: criterion keys must be exactly {CRITERION_KEYS} in that order "
             f"({key_order_msg(CRITERION_KEYS, got)}), got {got}")
    if "negate" in c:
        fail("J1", f"{ident}: no negate key; a negative criterion carries a negative weight")
    if "points" in c:
        fail("J1", f"{ident}: no points key; every criterion is binary")

    cid = c.get("id")
    if cid != f"R{i + 1}":
        fail("J2", f"{ident}: ids must be sequential R1, R2, ...; expected {f'R{i + 1}'!r}, got {cid!r}")

    name = c.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        fail("J3", f"{ident}: name must match {NAME_RE.pattern} (it becomes a key in the "
             f"judge's structured output), got {name!r}")
    elif name in seen_names:
        fail("J3", f"{ident}: name {name!r} already used by {seen_names[name]}; duplicate names "
             f"collapse two criteria into one")
    else:
        seen_names[name] = ident

    if c.get("type") != "binary":
        fail("J4", f"{ident}: type must be 'binary', got {c.get('type')!r}")

    weight = c.get("weight")
    weight_ok = is_int_weight(weight)
    if not weight_ok:
        fail("J5", f"{ident}: weight must be an integer in {sorted(WEIGHTS)}, got {weight!r}")

    ann = check_annotations(ident, c)

    imp = ann.get("importance")
    if weight_ok and isinstance(weight, int):
        mag = abs(weight)
        if imp == "critically_important" and mag not in (3, 5):
            fail("J13", f"{ident}: critically_important needs |weight| 3 or 5, got {weight}")
        if imp == "important" and mag not in (1, 3):
            fail("J13", f"{ident}: important needs |weight| 1 or 3, got {weight}")

    desc = c.get("description")
    if not isinstance(desc, str) or not desc.strip():
        fail("J8", f"{ident}: description missing or empty")
        return

    tgt = ann.get("evaluation_target")
    if tgt in RESPONSE_TARGETS and not desc.startswith("The response"):
        fail("J9", f"{ident}: evaluation_target {tgt!r} requires the description to start "
             f"with 'The response', got {desc[:40]!r}")
    if tgt in {"trajectory", "state_change"} and not desc.startswith("The agent"):
        fail("J9", f"{ident}: evaluation_target {tgt!r} requires the description to start "
             f"with 'The agent', got {desc[:40]!r}")

    for rx, label in NEGATIVE_TOKENS:
        if rx.search(desc):
            fail("J10", f"{ident}: negative-grammar token {label!r} (describe the behaviour "
                 f"as happening; a negative criterion carries a negative weight)")
    for w in VAGUE:
        if re.search(rf"\b{w}\b", desc, re.I):
            fail("J11", f"{ident}: vague qualifier {w!r}")
    if re.search(r"\bsome\b", desc, re.I):
        warn("J11", f"{ident}: 'some' present; judge whether it is threshold-free")
    if "[" in desc or "]" in desc:
        fail("J12", f"{ident}: square brackets in description")
    if PLACEHOLDER_RE.search(desc):
        fail("J12", f"{ident}: placeholder/marker in description")
    if DASH_RE.search(desc):
        fail("J12", f"{ident}: em/en dash in description")
    if re.match(r"^[A-Z]+\d*\s*[:\-]", desc):
        fail("J12", f"{ident}: tag prefix inside description text")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    bundle = Path(sys.argv[1]).resolve()
    p = bundle / "tests" / "judge.toml"
    if not bundle.is_dir() or not p.is_file():
        print(f"usage error: {bundle} is not a bundle with tests/judge.toml")
        return 2

    try:
        data = tomllib.loads(p.read_text(encoding="utf-8", errors="replace"))
    except tomllib.TOMLDecodeError as e:
        print(f"FAIL [G1] judge.toml does not parse: {e}")
        return 1

    criteria = data.get("criterion")
    if "judge" not in data:
        print("FAIL [G1] judge.toml has no [judge] table; without it rewardkit does not "
              "treat the file as the judged channel")
        return 1
    if not isinstance(criteria, list) or not criteria:
        print("FAIL [G1] judge.toml must carry at least one [[criterion]] table")
        return 1
    ok("G1", f"judge.toml parses ({len(criteria)} criteria)")

    check_header(data)

    seen_names: dict[str, str] = {}
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            fail("J1", f"index {i}: criterion is not a table")
            continue
        check_criterion(i, c, seen_names)
    for cid in ("J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10", "J11", "J12", "J13"):
        if not fails_for(cid):
            ok(cid, "all criteria")

    tables = [c for c in criteria if isinstance(c, dict)]

    n = len(criteria)
    if n < 8:
        fail("G3", f"only {n} criteria; minimum is 8")
    elif n > 35:
        warn("G3", f"{n} criteria; cap is 35 (warn)")
    else:
        ok("G3", f"{n} criteria")

    weights = [c["weight"] for c in tables if is_int_weight(c.get("weight"))]
    pos_total = sum(w for w in weights if w > 0)
    neg_total = -sum(w for w in weights if w < 0)
    if not pos_total:
        fail("G4", "no criterion carries a positive weight")
    if not neg_total:
        fail("G4", "no criterion carries a negative weight; at least one negative criterion is mandatory")
    if not fails_for("G4"):
        ok("G4", f"{sum(1 for w in weights if w < 0)} negative criteria")

    if weights and len(set(weights)) == 1:
        fail("G5", f"all weights identical ({weights[0]}); weights must differentiate")
    elif weights:
        ok("G5", "weights differentiate")

    if neg_total > pos_total:
        fail("G6", f"negatives outweigh positives: sum |negative| {neg_total} > sum positive "
             f"{pos_total}; the judge channel's share would drop below -0.5")
    else:
        ok("G6", f"positive total {pos_total}, negative total {neg_total}")

    print(f"judge_qc: {bundle.name}")
    print("=" * 60)
    for line in PASSES + WARNS + FAILS:
        print(line)
    print("=" * 60)
    print(f"SUMMARY: {len(PASSES)} pass, {len(WARNS)} warn, {len(FAILS)} fail")
    print("VERDICT:", "FAIL" if FAILS else ("WARN - tasker approval needed" if WARNS else "PASS"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
