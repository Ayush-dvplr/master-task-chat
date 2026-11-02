#!/usr/bin/env python3
"""Pre-QC stacking self-check (IMPROVEMENT_PLAN_v1 C2; LEVER_RULES_v2 section 5).

Usage: stacking_check.py <bundle_or_task_dir> [--classes classes.json] [--json]

Reads tests/test_output.py (AST only, never imported or run) and tests/judge.toml and prints:
  1. test -> observable map, with TS-26 duplicate candidates (same observable AND same logic);
  2. TS-13 multi-assert hints (several asserts / and-chained comparisons in one check);
  3. AL-28 penalty groups by act across tests and judge, with sums (limit 5 per act);
  4. weight shares: isolated / whole-document / shipped-only / format-on-hidden / mutation;
  5. counts (no cap, Ayush 24 Oct; kit floors 10 tests / 8 criteria), TS-20 weight-1 checks.
Everything is a HINT from static analysis. The session must confirm each row by reading the code
and write the corrected table into STACKING_CHECK.md. Classes can be overridden with
--classes '{"check_name": "whole_doc|isolated|mutation|format_hidden|hidden_rows|shipped_only|negative"}'.

Recognised registration styles: `criteria.<name>(weight=W)` calls, `@criterion(..., weight=W)`
decorators, and (fallback, weight unknown) bare `def test_*` functions.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

FILE_RE = re.compile(r"\.(json|jsonl|csv|tsv|txt|md|log|ini|xml|sqlite|db|gz|zip|bin|varc)\b|^/app/|/out/", re.I)
ACTS = [  # (act label, regex over name + description); first match wins, most specific first
    ("rebinds verifier dependencies", r"rebind|\.pth|module named after"),
    ("hardcoding the shipped answers", r"hardcod|hard-cod|sample_answers|shipped answers"),
    ("naming or reading grader files", r"reads_tests|reward_files|verifier'?s? files|/tests|test_output|grader"),
    ("third-party or network import", r"network|external_dep|third.party|non-stdlib"),
    ("output depends on file names", r"filename|file name|data directory's name"),
    ("reads data beyond its argument", r"training_corpus|reads .*?/app/data|beyond its argument"),
    ("nondeterministic output", r"nondetermin|different documents for one"),
    ("edits outside its scope", r"outside (its|the) scope|edits? .*(tests|solution)"),
    ("claims a check passed that its output contradicts (honesty)", r"claim|honest|asserts? .*passed|reports? .*passed"),
]


def act_of(text: str) -> str:
    for label, rx in ACTS:
        if re.search(rx, text, re.I):
            return label
    return "UNMATCHED act (name it by hand)"


class Module:
    def __init__(self, src: str):
        self.tree = ast.parse(src)
        self.funcs: dict[str, ast.FunctionDef] = {}
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[node.name] = node

    def registrations(self) -> list[dict]:
        regs: dict[str, dict] = {}
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "criteria"):
                w = _kw(node, "weight")
                if w is None and node.args:
                    w = _num(node.args[0])
                regs[node.func.attr] = {"name": node.func.attr, "weight": w, "style": "criteria.call"}
        for name, fn in self.funcs.items():
            for dec in fn.decorator_list:
                if isinstance(dec, ast.Call) and _callee(dec) == "criterion":
                    r = regs.setdefault(name, {"name": name, "weight": None, "style": "@criterion"})
                    w = _kw(dec, "weight")
                    if w is not None and r["weight"] is None:
                        r["weight"] = w
                    d = dec.keywords and next((k.value for k in dec.keywords if k.arg == "description"), None)
                    r["description"] = _str(d) if d is not None else ""
        if not regs:
            for name in self.funcs:
                if name.startswith("test_"):
                    regs[name] = {"name": name, "weight": None, "style": "pytest (weight unknown)"}
        return list(regs.values())

    def callees(self, fn: ast.AST) -> list[str]:
        out = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                c = _callee(node)
                if c in self.funcs:
                    out.append(c)
                for a in node.args:  # functions passed by reference, e.g. _passes(test_x)
                    if isinstance(a, ast.Name) and a.id in self.funcs:
                        out.append(a.id)
        return list(dict.fromkeys(out))

    def literals(self, fn: ast.AST, own: str) -> list[str]:
        lits = []
        body = fn.body if hasattr(fn, "body") else []
        skip = body[0] if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) else None
        for node in ast.walk(fn):
            if node is skip:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value.strip()
                if s and len(s) <= 60 and s != own and s.removeprefix("test_") != own.removeprefix("test_"):
                    lits.append(s)
        # drop decorator description strings
        return list(dict.fromkeys(lits))

    def asserts(self, fn: ast.AST) -> tuple[int, int]:
        n_assert = sum(isinstance(n, ast.Assert) for n in ast.walk(fn))
        n_and_cmp = 0
        for n in ast.walk(fn):
            if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.And):
                n_and_cmp = max(n_and_cmp, sum(isinstance(v, ast.Compare) for v in n.values))
        return n_assert, n_and_cmp


def _callee(call: ast.Call) -> str:
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def _num(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return -node.operand.value
    return None


def _kw(call: ast.Call, key: str):
    for k in call.keywords:
        if k.arg == key:
            return _num(k.value)
    return None


def _str(node) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant))
    return ""


def resolve(mod: Module, reg: dict) -> dict:
    """Follow thin wrappers (criterion -> _passes(test_x) -> ...) until literals appear, max depth 3."""
    name = reg["name"]
    fn = mod.funcs.get(name) or mod.funcs.get("test_" + name)
    path, lits, calls, n_assert, n_and = [], [], [], 0, 0
    seen = set()
    depth = 0
    while fn is not None and depth <= 3 and fn.name not in seen:
        seen.add(fn.name)
        path.append(fn.name)
        a, b = mod.asserts(fn)
        n_assert += a
        n_and = max(n_and, b)
        lits = mod.literals(fn, name)
        calls = mod.callees(fn)
        if lits:
            break
        nxt = [c for c in calls if c.startswith("test_")] or calls[:1]
        fn = mod.funcs.get(nxt[0]) if nxt else None
        depth += 1
    files = [l for l in lits if FILE_RE.search(l)]
    observable = files or lits
    return {"path": path, "observable": observable, "logic": calls, "asserts": n_assert, "and_compares": n_and}


def classify(reg: dict, info: dict) -> tuple[str, str]:
    n, d = reg["name"].lower(), (reg.get("description") or "").lower()
    w = reg["weight"]
    text = n + " " + d
    if (w is not None and w < 0) or n.startswith("negative") or n.startswith("test_negative"):
        return "negative", "weight < 0 or negative_ name"
    if "mutation" in n or d.startswith("mutation"):
        return "mutation", "mutation in name or description lead"
    if n.endswith("_hard") or re.search(r"^(trap|general|damage)_|_probe", n) or re.search(r"\b(fresh|hidden|unseen|seeded|reseeded)\b", d):
        return "hidden_rows", "row-owned check on hidden/fresh inputs (_hard, trap_, fresh)"
    if re.search(r"serializ|canonical|determin|rerun", n):
        if re.search(r"hidden|fresh|unseen|seeded|reseeded", text):
            return "format_hidden", "format/determinism check on hidden inputs"
        return "shipped_only", "format check, no hidden-input wording"
    if re.search(r"artifact|exists|shipped|keys_match_schema|arrays_in_schema", text):
        return "shipped_only", "artifact/shipped wording"
    if re.search(r"^hidden_|_documents?_match|_doc_|document|whole|equals the reference|matches the contract in every entry", text):
        return "whole_doc", "whole-document wording"
    return "isolated", "default (rule/fixture/case check)"


def judge_info(path: Path) -> dict:
    if not path.is_file():
        return {"present": False, "criteria": []}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    crit = data.get("criterion", [])
    return {"present": True, "mode": data.get("judge", {}).get("mode"), "criteria": [
        {"id": c.get("id"), "name": c.get("name", ""), "weight": c.get("weight"), "description": c.get("description", "")} for c in crit]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle")
    ap.add_argument("--classes", help="JSON object or file mapping check name -> class")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON instead of markdown")
    args = ap.parse_args()
    root = Path(args.bundle)
    tpath = root / "tests" / "test_output.py"
    if not tpath.is_file():
        print(f"no tests/test_output.py under {root}", file=sys.stderr)
        return 2
    overrides = {}
    if args.classes:
        p = Path(args.classes)
        overrides = json.loads(p.read_text() if p.is_file() else args.classes)
    mod = Module(tpath.read_text(encoding="utf-8"))
    rows = []
    for reg in mod.registrations():
        info = resolve(mod, reg)
        cls, why = classify(reg, info)
        if reg["name"] in overrides:
            cls, why = overrides[reg["name"]], "override"
        rows.append({**reg, **info, "class": cls, "class_basis": why})
    judge = judge_info(root / "tests" / "judge.toml")

    # TS-26 candidates: same observable AND same logic
    groups = defaultdict(list)
    for r in rows:
        if r["class"] == "negative":
            continue
        groups[(tuple(sorted(r["observable"])), tuple(sorted(r["logic"])))].append(r["name"])
    dups = [names for names in groups.values() if len(names) > 1]
    # TS-13 hints
    ts13 = [r for r in rows if r["class"] != "negative" and (r["asserts"] >= 3 or r["and_compares"] >= 3)]
    # AL-28 penalty groups
    pen = defaultdict(lambda: {"tests": [], "judge": [], "sum": 0.0})
    for r in rows:
        if r["class"] == "negative" and r["weight"] is not None:
            g = pen[act_of(r["name"] + " " + r.get("description", ""))]
            g["tests"].append(f"{r['name']} {r['weight']:g}")
            g["sum"] += abs(r["weight"])
    for c in judge["criteria"]:
        if isinstance(c["weight"], (int, float)) and c["weight"] < 0:
            g = pen[act_of(c["name"] + " " + c["description"])]
            g["judge"].append(f"{c['id']} {c['weight']:g}")
            g["sum"] += abs(c["weight"])
    # weight shares
    pos = [r for r in rows if r["class"] != "negative" and isinstance(r["weight"], (int, float)) and r["weight"] > 0]
    P = sum(r["weight"] for r in pos)
    share = defaultdict(float)
    for r in pos:
        share[r["class"]] += r["weight"]
    unknown_w = [r["name"] for r in rows if r["weight"] is None]
    w1 = [r["name"] for r in pos if r["weight"] == 1]
    jpos = [c for c in judge["criteria"] if isinstance(c["weight"], (int, float)) and c["weight"] > 0]
    j1 = [c["id"] for c in judge["criteria"] if re.search(r"\b\d{2,}\b", c["description"]) and not re.search(r"its own|builds|constructs", c["description"], re.I)]
    j2 = [c["id"] for c in judge["criteria"] if re.search(r"(constructs|builds) its own|its own (extract|input|segment|manifest|study)|an extract it built", c["description"], re.I)]
    iso = (share["isolated"] + share["mutation"]) / P if P else 0
    whole = share["whole_doc"] / P if P else 0
    ship = share["shipped_only"] / P if P else 0
    n_tests, n_crit = len(rows), len(judge["criteria"])

    verdicts = []
    verdicts.append(("TS-26 duplicate candidates", "none" if not dups else f"{len(dups)} group(s): CHECK BY HAND"))
    verdicts.append(("AL-28 groups <= 5", "PASS" if all(g["sum"] <= 5 for g in pen.values()) else "FAIL"))
    hid = (share["whole_doc"] + share["mutation"] + share["format_hidden"] + share["hidden_rows"]) / P if P else 0
    verdicts.append(("G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15)", f"{hid:.1%} " + ("PASS" if hid >= 0.30 else "FAIL")))
    verdicts.append(("G3 isolated / shipped-only (info, no cap)", f"{iso:.1%} / {ship:.1%}"))
    verdicts.append(("tests >= 10 (no cap)", f"{n_tests} " + ("FAIL" if n_tests < 10 else "PASS")))
    verdicts.append(("criteria >= 8 (no cap)", f"{n_crit} " + ("FAIL" if n_crit < 8 else "PASS")))
    verdicts.append(("judge mode batched", str(judge.get("mode"))))

    if args.json:
        print(json.dumps({"bundle": str(root), "tests": rows, "ts26_candidates": dups,
                          "ts13_hints": [r["name"] for r in ts13], "penalty_groups": pen,
                          "shares": {k: v / P for k, v in share.items()} if P else {}, "positive_total": P,
                          "weight_1": w1, "unknown_weight": unknown_w, "judge": judge,
                          "j1_figure_hints": j1, "j2_conduct": j2, "verdicts": verdicts}, indent=1, default=list))
        return 0

    out = [f"# stacking_check: {root.name}", "",
           f"tests/test_output.py: {n_tests} checks, positive total {P:g}, negatives {sum(r['weight'] for r in rows if r['class']=='negative' and r['weight']):g}; "
           f"judge: {n_crit} criteria, positive {sum(c['weight'] for c in jpos):g}, mode {judge.get('mode')}. Static hints only; confirm by reading the code.", "",
           "## 1. Test -> observable map", "", "| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |", "|---|---|---|---|---|---|"]
    for r in rows:
        obs = ", ".join(r["observable"][:4]) + (" ..." if len(r["observable"]) > 4 else "")
        out.append(f"| {r['name']} | {r['weight'] if r['weight'] is not None else '?'} | {r['class']} ({r['class_basis']}) | {obs or '-'} | {', '.join(r['logic'][:3]) or '-'} | {r['asserts']}/{r['and_compares']} |")
    out += ["", "TS-26 duplicate candidates (same observable AND same logic): " + ("none" if not dups else "; ".join(" = ".join(g) for g in dups))]
    out += ["", "## 2. TS-13 multi-assert hints", ""]
    out += [f"- {r['name']}: {r['asserts']} asserts, {r['and_compares']} and-chained comparisons" for r in ts13] or ["- none"]
    out += ["", "## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)", "", "| act | tests | judge | sum |w| | |", "|---|---|---|---|---|"]
    for act, g in pen.items():
        out.append(f"| {act} | {', '.join(g['tests']) or '-'} | {', '.join(g['judge']) or '-'} | {g['sum']:g} | {'PASS' if g['sum'] <= 5 else 'FAIL'} |")
    if not pen:
        out.append("| (no negatives) | - | - | 0 | |")
    out += ["", "## 4. Weight shares (of positive test weight)", ""]
    for k in ("whole_doc", "format_hidden", "hidden_rows", "isolated", "mutation", "shipped_only"):
        out.append(f"- {k}: {share[k]:g} ({share[k] / P:.1%})" if P else f"- {k}: 0")
    out.append(f"- G3: hidden or mutated reruns {(share['whole_doc'] + share['mutation'] + share['format_hidden'] + share['hidden_rows']) / P if P else 0:.1%} (>= 30%); isolated+mutation {iso:.1%}, whole-document {whole:.1%}, shipped-only {ship:.1%} (info, no cap)")
    if unknown_w:
        out.append(f"- weight unknown (not counted): {', '.join(unknown_w)}")
    out += ["", "## 5. Caps and weights", "",
            f"- tests {n_tests}, criteria {n_crit} (no cap; kit floors 10 / 8)",
            f"- weight-1 checks (TS-20: never on a core check): {', '.join(w1) or 'none'}",
            f"- judge J1 hints (criterion quotes a figure): {', '.join(j1) or 'none'}",
            f"- judge J2 conduct criteria: {', '.join(j2) or 'none'}",
            "", "## Verdict hints", ""]
    out += [f"- {k}: {v}" for k, v in verdicts]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
