#!/usr/bin/env python3
"""Tests QC: the deterministic checks on the reward function of one bundle.

Background every reader needs: grading runs in a SEPARATE verifier container
built from tests/Dockerfile with tests/ as the build context. That container
does NOT contain /app/data (the agent's corpus) - only the declared artifacts
are copied in at their exact absolute paths. test.sh hardens the verifier and
ends with `exec rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`; rewardkit scores tests/test_output.py (the
deterministic channel) and tests/judge.toml (the judged channel) and combines
them into the one `reward` as tests/reward.toml declares. test.sh writes no
reward bytes itself.

What this script enforces:

  A1-A5  test_output.py: parses and imports criteria and criterion from
         rewardkit, no duplicate function names, 10-35 checks, every check a
         well-formed top-level @criterion function, checks return bools.
  W1-W7  registrations criteria.<name>(weight=W): module-level, weight only,
         integer literal in {5,3,1,-1,-3,-5}, bijection with the checks,
         weights not all identical, at least one positive and one negative,
         negative_ prefix iff negative weight, negatives never outweigh
         positives.
  D1     no unconditional grade-time read of an agent input path (/app/data
         or wherever environment/Dockerfile COPYs an input directory).
  B1-B5  test.sh: ends with the exact rewardkit line run once, no skip
         switches, no sourcing or PATH shadowing, writes no reward itself,
         no exit/return/|| path that skips rewardkit.
  K1-K8  tests/Dockerfile: FROM, COPY . /tests/, mkdir -p /app (warn),
         every third-party import installed, harbor-rewardkit==0.2.1 pinned,
         Python 3.12 or newer, LITELLM_LOCAL_MODEL_COST_MAP=True, litellm
         pinned to an exact version.
  R1-R5  tests/reward.toml: parses with only reward and scoring tables,
         one [[reward]] of the pinned shape, channel weights equal to
         0.5 / positive total, [scoring.test_output] pinned, no other
         criteria-bearing input under tests/.
  O1     solve.py is an independent implementation, not a copy of the
         verifier.
  H1,H3-H6 verifier hardening: util-linux installed when setpriv/runuser is
         used, /tests restricted, stale reward files cleared, log directory
         locked to root, agent-written programs made readable before the
         uid drop.

Every ID:

  A1  test_output.py parses and does `from rewardkit import criteria, criterion`.
  A2  no function name is defined twice at module level.
  A3  10..35 checks (fail below 10, warn above 35).
  A4  each check is a top-level function decorated
      @criterion(description="<non-empty>") whose only parameter is workspace.
  A5  no check returns a literal non-bool (None, number, string); a check
      reading files with no try/except warns.
  W1  every criteria.<name>(...) is a module-level statement passing only
      weight=W.
  W2  W is an integer literal in {5, 3, 1, -1, -3, -5} (5.0 fails).
  W3  checks and registrations map one-to-one: unregistered check,
      registration naming no check, double registration all fail.
  W4  weights not all identical.
  W5  at least one positive and at least one negative weight.
  W6  a name starts with negative_ if and only if its weight is negative.
  W7  sum of |negative weights| <= sum of positive weights.
  D1  no unconditional read of an agent input path under tests/: /app/data and
      every destination environment/Dockerfile COPYs an input directory to.
  B1  the last code line of test.sh is exactly
      `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`,
      and rewardkit is invoked once.
  B2  no SKIP-style switch.
  B3  nothing sourced from /app, no agent-writable directory on PATH.
  B4  test.sh writes no reward file (only `rm -f` of one is allowed) and no
      .py file under tests/ names the reward files or /logs/verifier.
  B5  no exit, return or || in test.sh.
  K1  tests/Dockerfile has a FROM.
  K2  tests/Dockerfile copies the whole tests/ tree: COPY . /tests/.
  K3  RUN mkdir -p /app (warn).
  K4  every third-party import of test_output.py is installed.
  K5  rewardkit installed as exactly harbor-rewardkit==0.2.1.
  K6  a python:X.Y base image is 3.12 or newer.
  K7  ENV LITELLM_LOCAL_MODEL_COST_MAP=True. Without it litellm (imported by
      rewardkit) fetches its cost map from GitHub at import; the verifier's
      allowlist blocks that, and the failure warning races interpreter
      shutdown into an import deadlock that kills rewardkit before it writes
      reward.json (about half of runs with no route to GitHub).
  K8  litellm installed with an exact == pin. rewardkit accepts litellm>=1.83
      with no upper bound, so an unpinned verifier image takes whatever PyPI
      serves while holding the judge key and the hidden tests.
  R1  reward.toml parses; top level is exactly reward and scoring.
  R2  exactly one [[reward]] with keys name, aggregation, weights;
      name = "reward", aggregation = "weighted-sum", weights naming exactly
      test_output and judge.
  R3  weights.test_output == 0.5 / positive total of test_output.py and
      weights.judge == 0.5 / positive total of judge.toml, as exact floats.
  R4  [scoring] holds exactly test_output = { aggregation = "weighted-sum" }.
  R5  no other .py under tests/ defines criteria, no other .toml carries
      [judge] or [[criterion]], no tests/ subdirectory holds either.
  O1  solve.py shares under 35% of its substantive lines with
      test_output.py (warn from 20%).
  H1  util-linux installed when test.sh or a tests/ .py uses setpriv/runuser.
  H3  /tests restricted (chmod -R go-rwx /tests) (warn).
  H4  test.sh removes stale reward files (warn).
  H5  test.sh locks the log directory: chown root + chmod 755 (warn; 700 also warns).
  H6  when checks drop the uid, the agent-written program they execute is made
      readable first (chmod, or run a copy the verifier wrote). An agent editor
      leaves it at mode 0600; solve.sh uses cp, so only a real trajectory feels it.

Usage: python3 tests_qc.py /path/to/bundle
Exit codes: 0 = pass (warns allowed), 1 = fail, 2 = usage error.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

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


def warns_for(check: str) -> int:
    return sum(1 for line in WARNS if line.startswith(f"WARN [{check}] "))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def load_toml(p: Path) -> dict | None:
    try:
        return tomllib.loads(read(p))
    except (tomllib.TOMLDecodeError, OSError):
        return None


ALLOWED_WEIGHTS = {5, 3, 1, -1, -3, -5}
REWARDKIT_PIN = "harbor-rewardkit==0.2.1"
# rewardkit requires litellm>=1.83 with no upper bound, so an unpinned verifier
# install takes whatever PyPI serves at build time. On 2026-10-21 that was a
# litellm 1.107.0 stable (since withdrawn) carrying a .pth plus sitecustomize
# that fetched and executed remote code and reached the cloud metadata endpoint,
# inside the one image that holds the judge key and the hidden tests. The pin is
# the same version the agent image pins (structure_qc S9, DS-29).
LITELLM_PIN = "litellm==1.105.0"
# Versions known to carry the payload; never accept them even when pinned.
LITELLM_QUARANTINE = {"1.107.0"}
# Authoritative stdlib list from the interpreter itself; a hand-maintained
# set drifts across Python versions and produces false positives.
STDLIB = frozenset(sys.stdlib_module_names)
# Import name -> pip distribution name for common mismatches.
PIP_ALIASES = {"yaml": "pyyaml", "PIL": "pillow", "cv2": "opencv", "sklearn": "scikit-learn",
               "bs4": "beautifulsoup4", "dateutil": "python-dateutil", "Crypto": "pycryptodome"}
GUARD_RE = re.compile(r"\.exists\(\)|\.is_dir\(\)|\.is_file\(\)|os\.path\.(exists|isdir|isfile)"
                      r"|os\.environ|environ\.get")
READ_CALL_RE = re.compile(r"\.(read_text|read_bytes|open)\(|\bopen\(|json\.loads?\(|subprocess\.")
RUN_LINE_RE = re.compile(r"^exec\s+rewardkit\s+/tests/?\s+--workspace\s+/app/?\s+--output"
                         r"\s+/logs/verifier/reward\.json\s*$")
RUN_LINE = "exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json"

Func = ast.FunctionDef | ast.AsyncFunctionDef


def criterion_decorator(fn: Func) -> ast.expr | None:
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if (isinstance(target, ast.Name) and target.id == "criterion") or (
                isinstance(target, ast.Attribute) and target.attr == "criterion"):
            return d
    return None


def literal_number(node: ast.expr) -> Any:
    """The value of a numeric literal (signed or not), else None. A bool or
    string constant comes back as itself so the integer test rejects it."""
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)):
        v = node.operand.value
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return -v if isinstance(node.op, ast.USub) else v
        return None
    if isinstance(node, ast.Constant):
        return node.value
    return None


def is_int_weight(v: Any) -> bool:
    return type(v) is int and v in ALLOWED_WEIGHTS


def registration_name(node: ast.AST) -> str | None:
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "criteria"):
        return node.func.attr
    return None


def check_test_output(bundle: Path) -> tuple[ast.Module | None, str, dict[str, Func], set[str]]:
    """A1-A4: test_output.py holds rewardkit criteria, not pytest tests.

    A1  parses, and imports both criteria and criterion from rewardkit.
    A2  no function name defined twice: Python keeps only the last, so a
        check the author believes exists never runs.
    A3  10..35 checks: fewer than 10 cannot differentiate partial work
        (fail), more than 35 is usually redundancy (warn).
    A4  each check is a top-level function decorated with
        @criterion(description="...") carrying a non-empty string, whose only
        parameter is workspace. A decorated nested function fails.

    Returns the tree, the source, the checks by name and every imported
    top-level module (for K4)."""
    p = bundle / "tests" / "test_output.py"
    if not p.is_file():
        fail("A1", "tests/test_output.py missing")
        return None, "", {}, set()
    src = read(p)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        fail("A1", f"test_output.py does not parse: {e}")
        return None, src, {}, set()

    imports: set[str] = set()
    rk_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imports.add(node.module.split(".")[0])
            if node.module == "rewardkit":
                rk_names.update(a.name for a in node.names)
    missing = {"criterion", "criteria"} - rk_names
    if missing:
        fail("A1", f"test_output.py must import {', '.join(sorted(missing))} from rewardkit "
                   "(from rewardkit import criteria, criterion)")
    else:
        ok("A1", "test_output.py parses and imports criteria, criterion from rewardkit")

    seen: dict[str, int] = {}
    checks: dict[str, Func] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in seen:
            fail("A2", f"function {node.name} defined twice (lines {seen[node.name]} and "
                       f"{node.lineno}); only the last survives")
        seen[node.name] = node.lineno
        dec = criterion_decorator(node)
        if dec is None:
            continue
        checks[node.name] = node
        desc = next((k.value for k in getattr(dec, "keywords", []) if k.arg == "description"), None)
        if not (isinstance(desc, ast.Constant) and isinstance(desc.value, str) and desc.value.strip()):
            fail("A4", f"check {node.name} (line {node.lineno}) needs "
                       '@criterion(description="...") with a non-empty string')
        elif "{" in desc.value or "}" in desc.value:
            fail("A4", f"check {node.name} (line {node.lineno}) description contains a brace; "
                       "rewardkit 0.2.1 runs str.format on it at import, raises KeyError "
                       "and writes no reward")
        a = node.args
        params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
        if params != ["workspace"] or a.vararg or a.kwarg:
            fail("A4", f"check {node.name} (line {node.lineno}) must take exactly one "
                       f"parameter, workspace; got {params}")
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node not in tree.body
                and criterion_decorator(node)):
            fail("A4", f"check {node.name} (line {node.lineno}) is not a top-level function")
    if not fails_for("A2"):
        ok("A2", "no duplicate function names")
    if not fails_for("A4"):
        ok("A4", "every check is a top-level @criterion(description=...) function of workspace")

    n = len(checks)
    if n < 10:
        fail("A3", f"only {n} checks; minimum is 10")
    elif n > 35:
        warn("A3", f"{n} checks; cap is 35 (warn)")
    else:
        ok("A3", f"{n} checks")
    return tree, src, checks, imports


def check_returns(src: str, checks: dict[str, Func]) -> None:
    """A5: any exception inside a check aborts the whole rewardkit run and no
    reward is written, and a check returns a bool. A literal non-bool return
    (bare return, None, a number, a string) fails. A check that reads files
    or runs a subprocess with no try/except warns: trace it by hand against
    an empty workspace and against garbage in every artifact."""
    for name, fn in checks.items():
        nested = {id(r) for inner in ast.walk(fn) if inner is not fn
                  and isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                  for r in ast.walk(inner)}
        for r in ast.walk(fn):
            if not isinstance(r, ast.Return) or id(r) in nested:
                continue
            if r.value is None or (isinstance(r.value, ast.Constant)
                                   and not isinstance(r.value.value, bool)):
                shown = "bare return" if r.value is None else repr(r.value.value)
                fail("A5", f"check {name} line {r.lineno} returns {shown}; a check returns a bool")
        body = ast.get_source_segment(src, fn) or ""
        has_try = any(isinstance(x, ast.Try) for x in ast.walk(fn))
        if READ_CALL_RE.search(body) and not has_try:
            warn("A5", f"check {name} (line {fn.lineno}) reads agent output with no "
                       "try/except; confirm bad output returns False instead of raising")
    if checks and not fails_for("A5") and not warns_for("A5"):
        ok("A5", "no literal non-bool returns; every reading check guarded (trace by hand)")


def check_registrations(tree: ast.Module, checks: dict[str, Func]) -> dict[str, int]:
    """W1-W7: the weight contract. Weights live on the registrations in
    test_output.py and nowhere else.

    W1  every criteria.<name>(...) is a module-level statement of its own
        passing only weight=W (no positional args, no other keyword).
    W2  W is an integer literal from {5, 3, 1, -1, -3, -5}; 0, 2, floats
        (5.0), strings and expressions fail.
    W3  exact bijection: an unregistered check is scored at rewardkit's
        default weight without anyone choosing it; a registration naming no
        check pulls in a rewardkit built-in or crashes; a check registered
        twice is scored twice.
    W4  weights must not all be identical; they differentiate.
    W5  at least one positive and at least one negative weight.
    W6  a check is named negative_<cheat> if and only if its weight is
        negative.
    W7  sum of |negative weights| <= sum of positive weights, so the worst
        run scores no lower than -1.

    Returns name -> weight for checks registered exactly once with a valid
    weight."""
    top_calls = {id(s.value) for s in tree.body if isinstance(s, ast.Expr)}
    regs: dict[str, list[tuple[int, int | None]]] = {}
    for node in ast.walk(tree):
        name = registration_name(node)
        if name is None or not isinstance(node, ast.Call):
            continue
        if id(node) not in top_calls:
            fail("W1", f"line {node.lineno}: criteria.{name}(...) must be a module-level "
                       "statement of its own")
            continue
        kw = {k.arg: k.value for k in node.keywords}
        if node.args or set(kw) != {"weight"}:
            fail("W1", f"line {node.lineno}: criteria.{name}(...) must pass only weight=W "
                       f"(got {len(node.args)} positional, keywords "
                       f"{sorted(k or '**' for k in kw)})")
            regs.setdefault(name, []).append((node.lineno, None))
            continue
        w = literal_number(kw["weight"])
        if not is_int_weight(w):
            fail("W2", f"line {node.lineno}: criteria.{name} weight "
                       f"{ast.unparse(kw['weight'])} must be an integer literal in "
                       f"{sorted(ALLOWED_WEIGHTS)}")
            regs.setdefault(name, []).append((node.lineno, None))
            continue
        regs.setdefault(name, []).append((node.lineno, w))
    if not fails_for("W1"):
        ok("W1", f"{sum(len(v) for v in regs.values())} module-level registrations")
    if not fails_for("W2"):
        ok("W2", "every weight is an integer on the locked scale")

    for name in sorted(set(checks) - set(regs)):
        fail("W3", f"check {name} is never registered (rewardkit would score it at the "
                   "default weight)")
    for name in sorted(set(regs) - set(checks)):
        fail("W3", f"criteria.{name} names no check in test_output.py (built-in or crash)")
    for name, lst in sorted(regs.items()):
        if len(lst) > 1:
            fail("W3", f"check {name} registered {len(lst)} times (lines "
                       f"{', '.join(str(ln) for ln, _ in lst)}); it would be scored each time")
    if not fails_for("W3"):
        ok("W3", "bijection checks <-> registrations")

    weights: dict[str, int] = {}
    for name, lst in regs.items():
        w = lst[0][1]
        if name in checks and len(lst) == 1 and w is not None:
            weights[name] = w
    vals = list(weights.values())
    if vals and len(set(vals)) == 1:
        fail("W4", f"all weights identical ({vals[0]}); weights must differentiate")
    elif vals:
        ok("W4", "weights differentiate")

    pos_total = sum(w for w in vals if w > 0)
    neg_total = -sum(w for w in vals if w < 0)
    if vals and not pos_total:
        fail("W5", "no check carries a positive weight")
    if vals and not neg_total:
        fail("W5", "no check carries a negative weight; at least one is mandatory")
    if vals and not fails_for("W5"):
        ok("W5", f"{sum(1 for w in vals if w < 0)} negative check(s)")

    for name, w in sorted(weights.items()):
        if name.startswith("negative_") and w > 0:
            fail("W6", f"{name} is named negative but weighs {w}")
        if not name.startswith("negative_") and w < 0:
            fail("W6", f"{name} weighs {w} but lacks the negative_ prefix")
    if vals and not fails_for("W6"):
        ok("W6", "negative_ prefix matches weight sign")

    if neg_total > pos_total:
        fail("W7", f"negatives outweigh positives: sum |negative| {neg_total} > sum "
                   f"positive {pos_total}; the worst run would score below -1")
    elif vals:
        ok("W7", f"positive total {pos_total}, negative total {neg_total}")
    return weights


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Collect the id() of every Constant node that is a docstring, so the D1
    scan can skip prose that merely documents the /app/data hazard."""
    found: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            found.add(id(body[0].value))
    return found


def input_mounts(bundle: Path) -> list[str]:
    """Image paths the agent's input lands at: /app/data (the convention) plus the
    destination of every environment/Dockerfile COPY/ADD that reads an
    environment/ input directory. The verifier container has none of them."""
    mounts = {"/app/data"}
    env = bundle / "environment"
    df = env / "Dockerfile"
    if not df.is_file():
        return sorted(mounts)
    workdir = "/"
    for raw in read(df).splitlines():
        line = raw.strip()
        head = line.split(None, 1)
        if len(head) < 2:
            continue
        if head[0].upper() == "WORKDIR":
            workdir = head[1].strip()
            continue
        if head[0].upper() not in {"COPY", "ADD"} or "--from" in head[1]:
            continue
        args = [a for a in head[1].split() if not a.startswith("--")]
        if len(args) < 2:
            continue
        dest = args[-1] if args[-1].startswith("/") else workdir.rstrip("/") + "/" + args[-1]
        for src in args[:-1]:
            name = src.strip("./").split("/")[0]
            if name in {"", "*"}:
                for d in env.iterdir():
                    if d.is_dir() and not d.name.startswith("."):
                        mounts.add(dest.rstrip("/") + "/" + d.name)
                continue
            if name and (env / name).is_dir():
                target = dest.rstrip("/") + ("/" + name if len(args) > 2 or dest.endswith("/") else "")
                if target not in {"", "/", "/app"}:
                    mounts.add(target)
    return sorted(mounts)


def check_app_data_reads(bundle: Path, tree: ast.Module | None, src: str) -> None:
    """D1: nothing under tests/ may read /app/data at grade time. The verifier
    container is built from tests/ only; /app/data exists in the AGENT image
    and is not propagated, so an unconditional read crashes the trial.

    The scan is AST-based for test_output.py: comments never reach the AST,
    docstrings are skipped, and only string constants used by code count.
    A read guarded by an existence check or environment override in the same
    function is safe and is not flagged. .sh files and the Dockerfile keep
    the line scan (comments skipped)."""
    hits: list[str] = []
    mounts = input_mounts(bundle)

    def names_input(value: str) -> bool:
        return any(value == m or value.startswith(m + "/") or (m + "/") in value or value.endswith(m)
                   for m in mounts)

    if tree is not None:
        skip = _docstring_nodes(tree)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in ast.walk(tree):
            if (not isinstance(node, ast.Constant) or id(node) in skip
                    or not isinstance(node.value, str) or not names_input(node.value)):
                continue
            enclosing = None
            for fn in funcs:
                if fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
                    if enclosing is None or fn.lineno > enclosing.lineno:
                        enclosing = fn
            scope_src = ast.get_source_segment(src, enclosing) if enclosing else src
            if not (scope_src and GUARD_RE.search(scope_src)):
                hits.append(f"test_output.py:{node.lineno}")
    for p in sorted((bundle / "tests").glob("*")):
        if p.suffix == ".sh" or p.name == "Dockerfile":
            for i, line in enumerate(read(p).splitlines(), 1):
                if any(m in line for m in mounts) and not line.strip().startswith("#"):
                    hits.append(f"{p.name}:{i}")
    if hits:
        fail("D1", f"unconditional grade-time read of an agent input path {mounts} (does "
             f"NOT exist in the verifier container, guaranteed crash): {', '.join(hits)}")
    else:
        ok("D1", f"no unconditional reads of the agent input paths {mounts} under tests/")


def read_tests_py(bundle: Path) -> str:
    """Every .py under tests/, comment lines dropped."""
    return "\n".join(
        "\n".join(ln for ln in read(f).splitlines() if not ln.strip().startswith("#"))
        for f in sorted((bundle / "tests").rglob("*.py")) if f.is_file())


def check_test_sh(bundle: Path) -> None:
    """B1-B5: test.sh hands grading to rewardkit and cannot be subverted.

    B1  the last code line is exactly RUN_LINE and rewardkit is invoked once.
        A rewardkit crash leaves no reward.json and Harbor records a verifier
        error: the intended outcome for an authoring defect.
    B2  no SKIP-style environment switches that bypass grading.
    B3  never source files from agent-writable paths (/app) and never put an
        agent-writable directory on PATH.
    B4  test.sh writes no reward bytes: a line naming a reward file is
        allowed only as `rm -f` (clearing stale files) or the rewardkit line.
        No .py file under tests/ names the reward files or /logs/verifier:
        only rewardkit writes the reward.
    B5  no exit, return or || anywhere in test.sh: each is a path that can
        skip rewardkit.
    """
    p = bundle / "tests" / "test.sh"
    if not p.is_file():
        fail("B1", "tests/test.sh missing")
        return
    lines = [ln.strip() for ln in read(p).splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    code = "\n".join(lines)

    runs = [ln for ln in lines if re.search(r"\brewardkit\b", ln)]
    if not runs:
        fail("B1", "test.sh never runs rewardkit")
    elif not RUN_LINE_RE.match(lines[-1]):
        fail("B1", f"test.sh must end with: {RUN_LINE}")
    if len(runs) > 1:
        fail("B1", f"rewardkit invoked {len(runs)} times; run it once, as the last line")
    if not fails_for("B1"):
        ok("B1", "rewardkit runs once, as the last line")

    if re.search(r"\bSKIP[_A-Z]*\b", code):
        fail("B2", "test.sh contains a SKIP-style switch")
    else:
        ok("B2", "no skip switches")

    for m in re.finditer(r"^.*?(?:^|[\s;&|])(?:source|\.)\s+/app/\S+", code, re.M):
        fail("B3", f"test.sh sources an agent-writable path: {m.group(0).strip()[:70]!r}")
    if re.search(r"^.*\bPATH=[^\n]*?(/app|\$PWD|(?<=[=:\"'])\.(?=[:\"'\s]|$))", code, re.M):
        fail("B3", "test.sh puts an agent-writable directory on PATH")
    if not fails_for("B3"):
        ok("B3", "no sourcing or PATH shadowing")

    for ln in lines:
        if re.search(r"\breward[\w-]*\.(txt|json)", ln) and not re.match(r"^rm\b", ln) and ln not in runs:
            fail("B4", f"test.sh touches a reward file itself: {ln[:80]!r}")
    if re.search(r"/logs/verifier|reward(-details)?\.(txt|json)", read_tests_py(bundle)):
        fail("B4", "a .py file under tests/ names the reward files or /logs/verifier; "
                   "only rewardkit writes the reward")
    if not fails_for("B4"):
        ok("B4", "test.sh writes no reward itself (read the whole script)")

    if re.search(r"\bexit\b|\breturn\b|\|\|", code):
        fail("B5", "test.sh has an exit, return or || path that can skip rewardkit")
    else:
        ok("B5", "no exit, return or || paths")


def check_dockerfile(bundle: Path, imports: set[str]) -> None:
    """K1-K6: the verifier image must be self-sufficient.

    K1  a FROM line exists.
    K2  'COPY . /tests/' is mandatory: separate-mode verifiers skip the
        runtime tests/ upload, so the image itself must own every test file.
    K3  'RUN mkdir -p /app' is the reference convention (warn only - the
        harness auto-creates artifact parent dirs).
    K4  every third-party import in test_output.py other than rewardkit must
        be installed by THIS Dockerfile; packages in the agent image do not
        exist here. Known import-name/pip-name mismatches are mapped.
    K5  rewardkit is installed as exactly harbor-rewardkit==0.2.1 (the version
        Harbor 0.24.0 names); missing, unpinned, ranged or other versions fail.
    K6  a python:X.Y base image is 3.12 or newer (rewardkit requires it).
    K8  litellm carries an exact == pin on a pip install line, is not a
        withdrawn version, and matches the version the agent image pins.
    """
    p = bundle / "tests" / "Dockerfile"
    if not p.is_file():
        fail("K1", "tests/Dockerfile missing")
        return
    text = read(p)
    if not re.search(r"^FROM\s+\S+", text, re.M):
        fail("K1", "tests/Dockerfile has no FROM")
    else:
        ok("K1", "FROM present")
    if not re.search(r"^\s*COPY\s+(--\S+\s+)*\./?\s+/tests/?\s*$", text, re.M):
        fail("K2", "tests/Dockerfile must contain 'COPY . /tests/' (separate-mode "
             "verifiers skip the tests/ upload; the image must own the files)")
    else:
        ok("K2", "COPY . /tests/ present")
    if not re.search(r"mkdir\s+-p\s+(\S+\s+)*/app\b", text):
        warn("K3", "tests/Dockerfile lacks 'RUN mkdir -p /app' (reference convention; "
             "harness auto-creates artifact parents, so warn only)")
    else:
        ok("K3", "mkdir -p /app present")

    third_party = sorted(i for i in imports if i not in STDLIB and i not in {"test_output", "rewardkit"})
    for mod in third_party:
        cands = {mod, mod.replace("_", "-"), PIP_ALIASES.get(mod, mod)}
        if not any(re.search(rf"(?i)(?<![\w-]){re.escape(c)}(?![\w-])", text) for c in cands):
            fail("K4", f"test_output.py imports {mod!r} but tests/Dockerfile never installs it "
                 "(agent-image packages are NOT available in the verifier)")
    if not fails_for("K4"):
        ok("K4", f"third-party imports installed ({', '.join(third_party) or 'none beyond stdlib'})")

    specs = re.findall(r"harbor-rewardkit\S*", text)
    if not specs:
        fail("K5", f"tests/Dockerfile never installs rewardkit; pin {REWARDKIT_PIN}")
    for spec in specs:
        if spec.strip("'\"") != REWARDKIT_PIN:
            fail("K5", f"rewardkit installed as {spec!r}; pin exactly {REWARDKIT_PIN}")
    if not fails_for("K5"):
        ok("K5", f"{REWARDKIT_PIN} pinned")

    joined = re.sub(r"\\\s*\n", " ", text)
    install_text = "\n".join(l for l in joined.splitlines() if "pip install" in l and not l.lstrip().startswith("#"))
    litellm_specs = re.findall(r"(?<![\w-])litellm(?![\w-])\s*([=<>!~]=?[^\s'\"\\]*)?", install_text)
    if not litellm_specs:
        fail("K8", f"tests/Dockerfile installs rewardkit without pinning litellm; add {LITELLM_PIN} "
             "to the pip line (rewardkit accepts litellm>=1.83 with no upper bound, so the build "
             "takes whatever PyPI serves)")
    flagged = not litellm_specs
    for spec in litellm_specs:
        version = spec[2:] if spec.startswith("==") else ""
        if not version:
            fail("K8", f"litellm installed as 'litellm{spec}'; pin exactly {LITELLM_PIN}")
        elif version in LITELLM_QUARANTINE:
            fail("K8", f"litellm=={version} is withdrawn and shipped remote-code-execution "
                 f"hooks in site-packages; pin {LITELLM_PIN}")
        elif f"litellm=={version}" != LITELLM_PIN:
            warn("K8", f"litellm pinned to {version}, not the {LITELLM_PIN} the agent image pins "
                 "(S9/DS-29); a deliberate bump needs tasker approval")
        else:
            continue
        flagged = True
    if not flagged:
        ok("K8", f"{LITELLM_PIN} pinned in the verifier image")

    if re.search(r"^ENV\s+LITELLM_LOCAL_MODEL_COST_MAP=(?:True|true|1)\s*$", text, re.M):
        ok("K7", "LITELLM_LOCAL_MODEL_COST_MAP=True set")
    else:
        fail("K7", "tests/Dockerfile must set 'ENV LITELLM_LOCAL_MODEL_COST_MAP=True': without "
             "it litellm fetches its cost map from GitHub, the verifier allowlist blocks it, and "
             "rewardkit can deadlock at shutdown before writing reward.json")

    m = re.search(r"^FROM\s+(?:\S+/)?python:(\d+)\.(\d+)", text, re.M)
    if m and (int(m.group(1)), int(m.group(2))) < (3, 12):
        fail("K6", f"verifier base is Python {m.group(1)}.{m.group(2)}; rewardkit needs 3.12 or newer")
    else:
        ok("K6", "verifier base Python 3.12 or newer (or not a python:X.Y image)")


def holds_criteria(p: Path) -> bool:
    if p.suffix == ".py":
        return bool(re.search(r"@\s*(\w+\.)?criterion\b|\bcriteria\.\w+\(", read(p)))
    if p.suffix == ".toml":
        data = load_toml(p)
        return isinstance(data, dict) and ("judge" in data or "criterion" in data)
    return False


def judge_positive_total(bundle: Path) -> int:
    p = bundle / "tests" / "judge.toml"
    data = load_toml(p) if p.is_file() else None
    crits = data.get("criterion") if isinstance(data, dict) else None
    if not isinstance(crits, list):
        return 0
    return sum(c["weight"] for c in crits if isinstance(c, dict)
               and is_int_weight(c.get("weight")) and c["weight"] > 0)


def check_reward_toml(bundle: Path, test_weights: dict[str, int]) -> None:
    """R1-R5: tests/reward.toml combines the two channels into `reward`.

    R1  parses; top level is exactly the reward and scoring tables.
    R2  exactly one [[reward]] table, keys name, aggregation, weights;
        name = "reward", aggregation = "weighted-sum", weights naming exactly
        test_output and judge.
    R3  weights.test_output == 0.5 / (positive total of test_output.py) and
        weights.judge == 0.5 / (positive total of judge.toml), floats
        compared exactly (write Python's repr of the division). A stale
        weight means the score no longer runs from -1 to 1. Not recomputed
        for test_output while W1-W3 fail (warn instead).
    R4  [scoring] holds exactly [scoring.test_output] and that table is
        exactly { aggregation = "weighted-sum" }.
    R5  rewardkit scores every criteria-bearing file at the top of tests/ as
        its own input: no other .py defines criteria, no other .toml carries
        [judge] or [[criterion]], and no tests/ subdirectory holds either.
    """
    tests = bundle / "tests"
    for p in sorted(tests.iterdir()):
        if p.is_file() and p.name not in {"test_output.py", "judge.toml"} and holds_criteria(p):
            fail("R5", f"tests/{p.name} defines criteria; rewardkit would score it as an extra input")
        if p.is_dir() and not p.name.startswith((".", "__")):
            extra = [f for f in sorted(p.rglob("*")) if f.is_file() and holds_criteria(f)]
            if extra:
                fail("R5", f"tests/{p.name}/ holds criteria ({extra[0].relative_to(tests)}); "
                           "rewardkit would score it as an extra input")
    if not fails_for("R5"):
        ok("R5", "no criteria-bearing input beyond test_output.py and judge.toml")

    p = tests / "reward.toml"
    if not p.is_file():
        fail("R1", "tests/reward.toml missing")
        return
    data = load_toml(p)
    if data is None:
        fail("R1", "reward.toml does not parse")
        return
    if set(data) != {"reward", "scoring"}:
        fail("R1", f"reward.toml top level must be exactly [[reward]] and [scoring.test_output], "
                   f"got {sorted(data)}")
    else:
        ok("R1", "reward.toml parses with reward and scoring tables only")

    rewards = data.get("reward")
    spec = rewards[0] if isinstance(rewards, list) and len(rewards) == 1 and isinstance(rewards[0], dict) else None
    if spec is None:
        fail("R2", "reward.toml needs exactly one [[reward]] table")
    else:
        if set(spec) != {"name", "aggregation", "weights"}:
            fail("R2", f"[[reward]] keys must be name, aggregation, weights; got {sorted(spec)}")
        if spec.get("name") != "reward":
            fail("R2", f'[[reward]] name must be "reward", got {spec.get("name")!r}')
        if spec.get("aggregation") != "weighted-sum":
            fail("R2", f'[[reward]] aggregation must be "weighted-sum", got {spec.get("aggregation")!r}')
        w = spec.get("weights")
        if not isinstance(w, dict) or set(w) != {"test_output", "judge"}:
            shown = sorted(w) if isinstance(w, dict) else w
            fail("R2", f"[[reward]] weights must name exactly test_output and judge, got {shown!r}")
        else:
            blocked = any(fails_for(x) for x in ("W1", "W2", "W3"))
            for key, pos in (("test_output", sum(v for v in test_weights.values() if v > 0)),
                             ("judge", judge_positive_total(bundle))):
                if key == "test_output" and blocked:
                    warn("R3", "weights.test_output not recomputed until W1-W3 pass")
                    continue
                if not pos:
                    continue
                want = 0.5 / pos
                got = w[key]
                if not isinstance(got, float) or got != want:
                    fail("R3", f"weights.{key} is {got!r}; with positive total {pos} it must be "
                               f"{want!r} (0.5 / {pos})")
            if not fails_for("R3") and not warns_for("R3"):
                ok("R3", "channel weights equal 0.5 / positive total")
        if not fails_for("R2"):
            ok("R2", "[[reward]] shape pinned")

    scoring = data.get("scoring")
    if not isinstance(scoring, dict) or set(scoring) != {"test_output"}:
        shown = sorted(scoring) if isinstance(scoring, dict) else scoring
        fail("R4", f"reward.toml needs exactly one [scoring.test_output] table, got {shown!r}")
    elif scoring["test_output"] != {"aggregation": "weighted-sum"}:
        fail("R4", '[scoring.test_output] must hold only aggregation = "weighted-sum", '
                   f"got {scoring['test_output']!r}")
    else:
        ok("R4", '[scoring.test_output] aggregation = "weighted-sum"')


def _substantive_lines(text: str) -> list[str]:
    """Code lines worth comparing: no blanks, comments, imports or short noise.

    Lines under 12 characters are dropped because `else:`, `return`, `pass`
    and closing brackets collide between any two Python files and would
    manufacture overlap that means nothing.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 12 or line.startswith("#"):
            continue
        if re.match(r"(import|from)\s+\w", line):
            continue
        out.append(line)
    return out


def check_oracle_independence(bundle: Path) -> None:
    """O1: solution/solve.py must not be a copy of tests/test_output.py.

    An oracle lifted out of the verifier is guaranteed to score 1.000, so the
    oracle run returns a green light while proving nothing about whether the
    task is solvable. Some overlap is legitimate (a mirror encoder used to
    build the corpus), so fail at 35% of substantive lines and warn from 20%.
    Under 30 substantive lines the percentage is unreliable and warns.
    """
    solve = bundle / "solution" / "solve.py"
    tout = bundle / "tests" / "test_output.py"
    if not solve.is_file() or not tout.is_file():
        ok("O1", "no solve.py to compare; judge solve.sh by reading")
        return
    s_lines = _substantive_lines(read(solve))
    t_set = set(_substantive_lines(read(tout)))
    if not s_lines:
        ok("O1", "solve.py has no substantive lines; judge by reading")
        return
    shared = sum(1 for ln in s_lines if ln in t_set)
    pct = 100.0 * shared / len(s_lines)
    detail = f"{pct:.0f}% of solve.py's {len(s_lines)} substantive lines also appear in test_output.py"
    if len(s_lines) < 30:
        warn("O1", f"small solve.py, percentage unreliable: {detail}; judge by reading")
    elif pct >= 35:
        fail("O1", f"oracle is not independent: {detail}. Rewrite solve.py from the task "
             "contract, not from the tests")
    elif pct >= 20:
        warn("O1", f"oracle overlaps the verifier: {detail}. Under the 35% limit but "
             "reduce it further; shared lines cannot catch each other's bugs")
    else:
        ok("O1", f"oracle independent of the verifier ({detail})")


def check_hardening(bundle: Path) -> None:
    """H1, H3-H5: the verifier must survive executing hostile agent code.

    The reference verifier installs util-linux so checks can drop privileges
    with setpriv, makes /tests unreadable to the unprivileged user, clears
    stale reward files before grading, and locks the log directory to root.

    H1 is a fail because it is guaranteed runtime breakage: a check calling a
    binary the image never installed cannot grade anything. H3-H5 are warns
    because whether they matter depends on whether agent code runs at all,
    which only a reader can determine.
    """
    dockerfile = bundle / "tests" / "Dockerfile"
    test_sh = bundle / "tests" / "test.sh"
    if not dockerfile.is_file():
        return
    dtext = read(dockerfile)
    stext = read(test_sh) if test_sh.is_file() else ""

    droppers = [t for t in ("setpriv", "runuser")
                if re.search(rf"\b{t}\b", stext + "\n" + read_tests_py(bundle))]
    if droppers:
        if re.search(r"\butil-linux\b", dtext):
            ok("H1", f"util-linux installed for {', '.join(droppers)}")
        else:
            fail("H1", f"grading calls {', '.join(droppers)} but tests/Dockerfile never installs "
                 "util-linux, so the binary is absent and grading aborts")

    if re.search(r"chmod[^\n]*go-rwx[^\n]*/tests|chmod\s+-R\s+[0-7]?700\s+/tests", dtext + "\n" + stext):
        ok("H3", "/tests restricted from unprivileged readers")
    else:
        warn("H3", "/tests not restricted (chmod -R go-rwx /tests); required if grading "
             "executes agent code")

    if stext:
        if re.search(r"rm\s+-[a-z]*f[a-z]*[^\n]*reward", stext):
            ok("H4", "stale reward files cleared before grading")
        else:
            warn("H4", "test.sh never removes a pre-existing reward file")
        locked_root = re.search(r"chown[^\n]*root[^\n]*(/logs|LOGS)", stext)
        mode = re.search(r"chmod\s+(?:-R\s+)?0?(7[0-7][0-7])[^\n]*(?:/logs|LOGS)", stext)
        if locked_root and mode and mode.group(1) == "755":
            ok("H5", "verifier log directory owned by root and not writable by others")
        elif locked_root and mode:
            warn("H5", f"verifier log directory is chmod {mode.group(1)}; prefer 755. Harbor reads "
                 "the bind-mounted reward file back as the host user, and a directory it cannot "
                 "traverse makes that read fail on Linux (RewardFileNotFoundError, trial errored) "
                 "even though grading succeeded. Root ownership already blocks other writers, so "
                 "755 keeps the protection and allows the read")
        else:
            warn("H5", "verifier log directory not locked (chown root:root + chmod 755)")


DROPS_PRIVILEGES = re.compile(r"setpriv|runuser|setuid|setresuid|preexec_fn|extra_groups")
GRANTS_READ = re.compile(r"chmod|grant|readable|share")
STAGES_FILE = re.compile(r"copyfile|copy2|copytree|shutil\.copy|write_text|write_bytes")
PY_LITERAL = re.compile(r"""['"][^'"\s]*\.py['"]""")


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


# Interpreter switches that sit between sys.executable and the program path.
# -c and -m take code or a module name, so the list holds no program file at
# all and there is nothing for H6 to look for; -X and -W take a value of their
# own, so the token after them is not the program either.
NO_PROGRAM_FLAGS = {"-c", "-m"}
FLAGS_WITH_VALUE = {"-X", "-W", "-Q", "--check-hash-based-pycs"}
STRING_LITERAL = re.compile(r"""^['"](.*)['"]$""", re.S)


def _executed_programs(tree: ast.AST) -> list[ast.expr]:
    """The program each `[sys.executable, ...]` list runs, skipping switches.

    `python -I program.py` is the usual hardening form, so the token after
    sys.executable is frequently `-I` and not the program. Reporting that
    asks the author to chmod a command-line switch.
    """
    programs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List):
            continue
        parts = [ast.unparse(e) for e in node.elts]
        if "sys.executable" not in parts:
            continue
        index = parts.index("sys.executable") + 1
        while index < len(parts):
            literal = STRING_LITERAL.match(parts[index])
            if literal is None or not literal.group(1).startswith("-"):
                break
            switch = literal.group(1)
            if switch in NO_PROGRAM_FLAGS:
                index = len(parts)
                break
            index += 2 if switch in FLAGS_WITH_VALUE else 1
        if index < len(parts):
            programs.append(node.elts[index])
    return programs


def _drop_builders(tree: ast.AST) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and re.search(r"setpriv|runuser|_SETPRIV", ast.unparse(n))]


def check_agent_program_readable(bundle: Path) -> None:
    """H6: a verifier that drops privileges must make the agent's program readable.

    Agent editors write through a temp file and rename it, so a program the agent
    wrote lands at mode 0600 (owner-only). Checks that run it as an unprivileged
    user then cannot open it and fail even on a correct submission. The oracle's
    solve.sh installs its program with cp, which leaves 0644, so Step 10 reads
    1.000 and the hole stays invisible until a real trajectory is graded. Passing
    shapes: the privilege dropper grants read to its arguments, a grant call names
    the executed program, or the verifier executes a python file it staged itself.
    """
    path = bundle / "tests" / "test_output.py"
    if not path.is_file():
        return
    src = read(path)
    if not DROPS_PRIVILEGES.search(src):
        return
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return
    programs = _executed_programs(tree)
    if not programs:
        return

    if any(GRANTS_READ.search(ast.unparse(f)) for f in _drop_builders(tree)):
        ok("H6", "the privilege dropper grants read on the program it is about to run")
        return

    staged_py = {t.id for node in ast.walk(tree)
                 if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None
                 and PY_LITERAL.search(ast.unparse(node.value))
                 for t in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
                 if isinstance(t, ast.Name)}
    calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call)]
    granted: set[str] = set()
    staged: set[str] = set()
    for call in calls:
        text = ast.unparse(call)
        if GRANTS_READ.search(text):
            granted |= _names(call)
        if STAGES_FILE.search(text) and _names(call) & staged_py:
            staged |= _names(call) | staged_py

    aliases: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
            bound = {t.id for t in targets if isinstance(t, ast.Name)}
            aliases.setdefault(ast.unparse(node.value), set()).update(bound)

    unguarded = sorted({ast.unparse(p) for p in programs
                        if not ((_names(p) | aliases.get(ast.unparse(p), set()))
                                & (granted | staged))})
    if unguarded:
        fail("H6", "grading runs an agent-written program under a dropped uid without making it "
             f"readable first: {', '.join(unguarded)}. An agent editor leaves that file at mode "
             "0600, so every check that executes it fails on a correct submission. chmod the "
             "program and its parents (the verifier is root) or run a copy the verifier staged, "
             "then prove it with the --owner-only oracle run in Step 10")
    else:
        ok("H6", "the agent-written program is made readable before the uid drop")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    bundle = Path(sys.argv[1]).resolve()
    if not bundle.is_dir() or not (bundle / "tests").is_dir():
        print(f"usage error: {bundle} is not a bundle with tests/")
        return 2

    tree, src, checks, imports = check_test_output(bundle)
    weights: dict[str, int] = {}
    if tree is not None:
        check_returns(src, checks)
        weights = check_registrations(tree, checks)
    check_app_data_reads(bundle, tree, src)
    check_test_sh(bundle)
    check_dockerfile(bundle, imports)
    check_reward_toml(bundle, weights)
    check_oracle_independence(bundle)
    check_hardening(bundle)
    check_agent_program_readable(bundle)

    print(f"tests_qc: {bundle.name}")
    print("=" * 60)
    for line in PASSES + WARNS + FAILS:
        print(line)
    print("=" * 60)
    print(f"SUMMARY: {len(PASSES)} pass, {len(WARNS)} warn, {len(FAILS)} fail")
    print("VERDICT:", "FAIL" if FAILS else ("WARN - tasker approval needed" if WARNS else "PASS"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
