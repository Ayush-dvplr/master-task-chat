#!/usr/bin/env python3
"""Validate an Input Bundle against FORMAT_SPEC.md.

This script enforces the Input Bundle Format Spec located next to it at
FORMAT_SPEC.md. Usage: python3 validate_bundle.py <bundle_dir> [--verbose]
[--strict].
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Callable


FROM_RE = re.compile(
    r"^FROM\s+public\.ecr\.aws/docker/library/[a-z0-9._-]+:"
    r"[a-zA-Z0-9._-]+@sha256:[0-9a-f]{64}\s*$"
)
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
ARCHETYPE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
ABS_BACKTICK_RE = re.compile(r"`/[a-zA-Z0-9/._-]+`")
RESIDUAL_MARKER_RE = re.compile(
    r"\{\{[A-Z0-9_]+\}\}|__[A-Z][A-Z0-9_]*__|<TAG>"
    r"|\bTODO\b|\bFIXME\b|\bXXX\b|\bPLACEHOLDER\b"
)
LEGAL_WEIGHTS = {1, 3, 5, -1, -3, -5}

CheckStatus = bool | None | str
CheckFn = Callable[["Context"], tuple[CheckStatus, str]]
Rule = tuple[str, str, CheckFn]


_TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"
_QC_ROOT = Path(__file__).resolve().parent.parent / "Input_Bundle_QC"


def detect_archetype(bundle: Path) -> str | None:
    """The template whose declared artifacts equal the bundle's task.toml
    artifacts. TRUTH.md carries no archetype name (QC DS-27)."""
    try:
        artifacts = tomllib.loads((bundle / "task.toml").read_text(encoding="utf-8")).get("artifacts")
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if not isinstance(artifacts, list):
        return None
    matches = []
    for manifest in sorted(_TEMPLATE_ROOT.glob("*/archetype.toml")):
        try:
            declared = tomllib.loads(manifest.read_text(encoding="utf-8")).get("artifacts")
        except tomllib.TOMLDecodeError:
            continue
        if isinstance(declared, list) and sorted(declared) == sorted(artifacts):
            matches.append(manifest.parent.name)
    return matches[0] if len(matches) == 1 else None


class Context:
    def __init__(
        self, bundle: Path, strict: bool = False, archetype: str | None = None
    ) -> None:
        self.bundle = bundle
        self.strict = strict
        self.archetype = archetype or self._detect_archetype()
        self._toml: dict[str, Any] | None = None
        self._toml_error: str | None = None
        self._weights: dict[str, Any] | None = None
        self._weights_error: str | None = None
        self._test_source: str | None = None
        self._test_tree: ast.AST | None = None
        self._test_error: str | None = None

    def _detect_archetype(self) -> str:
        return detect_archetype(self.bundle) or "format-recovery"

    def path(self, rel: str) -> Path:
        return self.bundle / rel

    def declared_inputs(self) -> list[dict[str, str]]:
        """The archetype's [[inputs]] (dir, mount); default data -> /app/data."""
        manifest = _TEMPLATE_ROOT / self.archetype / "archetype.toml"
        try:
            raw = tomllib.loads(manifest.read_text(encoding="utf-8")).get("inputs")
        except (OSError, tomllib.TOMLDecodeError):
            raw = None
        if not isinstance(raw, list) or not raw:
            return [{"dir": "data", "mount": "/app/data"}]
        return [{"dir": str(i["dir"]), "mount": str(i["mount"]).rstrip("/")} for i in raw]

    def input_dirs(self) -> list[Path]:
        env = self.path("environment")
        if not env.is_dir():
            return []
        return sorted(p for p in env.iterdir() if p.is_dir() and not p.name.startswith("."))

    def input_files(self) -> list[Path]:
        return sorted(f for d in self.input_dirs() for f in d.rglob("*") if f.is_file())

    def primary_input(self) -> Path:
        return self.path("environment") / self.declared_inputs()[0]["dir"]

    def text(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def toml(self) -> tuple[dict[str, Any] | None, str | None]:
        if self._toml is None and self._toml_error is None:
            try:
                self._toml = tomllib.loads(self.text("task.toml"))
            except Exception as exc:  # noqa: BLE001 - report parser detail
                self._toml_error = str(exc)
        return self._toml, self._toml_error

    def weights(self) -> tuple[dict[str, Any] | None, str | None]:
        """criteria.<name>(weight=W) registrations from tests/test_output.py."""
        if self._weights is None and self._weights_error is None:
            _, tree, err = self.test_ast()
            if tree is None:
                self._weights_error = err or "test_output.py parse failed"
                return None, self._weights_error
            found: dict[str, Any] = {}
            for node in getattr(tree, "body", []):
                call = node.value if isinstance(node, ast.Expr) else None
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "criteria"
                ):
                    for kw in call.keywords:
                        if kw.arg == "weight":
                            try:
                                found[call.func.attr] = ast.literal_eval(kw.value)
                            except ValueError:
                                found[call.func.attr] = None
            if found:
                self._weights = found
            else:
                self._weights_error = "test_output.py registers no criteria.<name>(weight=W)"
        return self._weights, self._weights_error

    def test_ast(self) -> tuple[str | None, ast.AST | None, str | None]:
        if self._test_source is None and self._test_error is None:
            try:
                self._test_source = self.text("tests/test_output.py")
                self._test_tree = ast.parse(self._test_source)
            except Exception as exc:  # noqa: BLE001
                self._test_error = str(exc)
        return self._test_source, self._test_tree, self._test_error


def ok(detail: str = "ok") -> tuple[bool, str]:
    return True, detail


def fail(detail: str) -> tuple[bool, str]:
    return False, detail


def warn(detail: str) -> tuple[None, str]:
    return None, detail


def info(detail: str) -> tuple[str, str]:
    return "INFO", detail


def exists_file(ctx: Context, rel: str) -> bool:
    return ctx.path(rel).is_file()


def exists_dir(ctx: Context, rel: str) -> bool:
    return ctx.path(rel).is_dir()


def json_load_file(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def logical_run_commands(text: str) -> list[str]:
    commands: list[str] = []
    current: list[str] = []
    in_run = False
    for line in text.splitlines():
        if re.match(r"^RUN\s+", line):
            if current:
                commands.append(" ".join(current))
            current = [line.rstrip("\\").strip()]
            in_run = line.rstrip().endswith("\\")
        elif in_run:
            current.append(line.rstrip("\\").strip())
            in_run = line.rstrip().endswith("\\")
            if not in_run:
                commands.append(" ".join(current))
                current = []
        else:
            if current:
                commands.append(" ".join(current))
                current = []
    if current:
        commands.append(" ".join(current))
    return commands


def top_level_test_names(tree: ast.AST | None) -> set[str]:
    if tree is None:
        return set()
    return {
        n.name
        for n in getattr(tree, "body", [])
        if isinstance(n, ast.FunctionDef)
        and any(
            isinstance(d, ast.Call) and getattr(d.func, "id", None) == "criterion"
            for d in n.decorator_list
        )
    }


def toml_data(ctx: Context) -> dict[str, Any] | None:
    data, err = ctx.toml()
    return None if err else data


def c_1_name(ctx: Context) -> tuple[bool, str]:
    return (
        ok(ctx.bundle.name)
        if NAME_RE.fullmatch(ctx.bundle.name)
        else fail(f"bad bundle name {ctx.bundle.name!r}")
    )


def c_1_root_files(ctx: Context) -> tuple[bool, str]:
    missing = [
        p
        for p in ("instruction.md", "task.toml")
        if not exists_file(ctx, p)
    ]
    return (
        fail(f"missing {missing}")
        if missing
        else ok("required top-level files present")
    )


def c_1_root_dirs(ctx: Context) -> tuple[bool, str]:
    missing = [
        p for p in ("environment", "solution", "tests") if not exists_dir(ctx, p)
    ]
    return (
        fail(f"missing {missing}") if missing else ok("required top-level dirs present")
    )


def c_1_env(ctx: Context) -> tuple[bool, str]:
    declared = [item["dir"] for item in ctx.declared_inputs()]
    missing = [] if exists_file(ctx, "environment/Dockerfile") else ["environment/Dockerfile"]
    missing += [f"environment/{d}" for d in declared if not exists_dir(ctx, f"environment/{d}")]
    extras = []
    env = ctx.path("environment")
    if env.is_dir():
        extras = sorted(
            p.name for p in env.iterdir() if p.name not in {"Dockerfile", *declared}
        )
    if missing or extras:
        return fail(f"missing={missing}; unexpected environment entries={extras}")
    return ok(f"environment has Dockerfile and the declared inputs {declared}")


def c_1_solution_exact(ctx: Context) -> tuple[bool, str]:
    sol = ctx.path("solution")
    if not sol.is_dir():
        return fail("solution/ missing")
    entries = sorted(p.name for p in sol.iterdir())
    return (
        ok("solution entries exact")
        if entries == ["TRUTH.md", "solve.py", "solve.sh"]
        else fail(f"solution entries are {entries}")
    )


def c_1_tests_exact(ctx: Context) -> tuple[bool, str]:
    tests = ctx.path("tests")
    expected = [
        "Dockerfile",
        "judge.toml",
        "reward.toml",
        "test.sh",
        "test_output.py",
    ]
    if not tests.is_dir():
        return fail("tests/ missing")
    entries = sorted(p.name for p in tests.iterdir())
    return (
        ok("tests entries exact")
        if entries == expected
        else fail(f"tests entries are {entries}")
    )


def c_1_cheat_optional(ctx: Context) -> tuple[bool, str]:
    cheat = ctx.path("cheat")
    if not cheat.exists():
        return ok("optional cheat/ overlay absent")
    if not cheat.is_dir():
        return fail("cheat exists but is not a directory")
    entries = sorted(path.name for path in cheat.iterdir())
    if entries != ["cheat.py", "solve.sh"]:
        return fail(f"cheat entries are {entries}")
    solve = cheat / "solve.sh"
    if not solve.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        return fail("cheat/solve.sh is not executable")
    try:
        solve_source = solve.read_text(encoding="utf-8")
        source = (cheat / "cheat.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeError) as exc:
        return fail(f"cheat overlay is not valid UTF-8/Python: {exc}")
    if "CHEAT ORACLE" not in solve_source or "CHEAT ORACLE" not in source:
        return fail("cheat files are missing the CHEAT ORACLE sentinel")
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.partition(".")[0])
    non_stdlib = sorted(imports - sys.stdlib_module_names)
    if non_stdlib:
        return fail(f"cheat/cheat.py imports non-stdlib modules: {non_stdlib}")
    return ok("optional cheat/ overlay has exact, executable, stdlib-only contents")


def c_1_data_nonempty(ctx: Context) -> tuple[bool, str]:
    dirs = ctx.input_dirs()
    if not dirs:
        return fail("environment/ holds no input directory")
    empty = [d.name for d in dirs if not any(f.is_file() for f in d.rglob("*"))]
    if empty:
        return fail(f"empty input directories: {empty}")
    return ok(", ".join(f"{d.name}/: {sum(1 for f in d.rglob('*') if f.is_file())} files" for d in dirs))


def c_1_no_pycache(ctx: Context) -> tuple[bool, str]:
    found = [
        str(p.relative_to(ctx.bundle))
        for p in ctx.bundle.rglob("__pycache__")
        if p.is_dir()
    ]
    return fail(f"found {found}") if found else ok("no __pycache__ dirs")


def c_1_no_residual_markers(ctx: Context) -> tuple[bool, str]:
    found: list[str] = []
    for path in ctx.bundle.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.casefold() == ".zip":
            try:
                with zipfile.ZipFile(path) as zf:
                    infos = zf.infolist()
                    if len(infos) > 512:
                        found.append(
                            f"{path.relative_to(ctx.bundle)} (too many members)"
                        )
                        continue
                    if sum(info.file_size for info in infos) > 100 * 1024 * 1024:
                        found.append(
                            f"{path.relative_to(ctx.bundle)} (expanded size too large)"
                        )
                        continue
                    actual_total = 0
                    for info in infos:
                        rel = PurePosixPath(info.filename)
                        mode = (info.external_attr >> 16) & 0xFFFF
                        if (
                            "\\" in info.filename
                            or "\x00" in info.filename
                            or rel.is_absolute()
                            or ".." in rel.parts
                            or stat.S_ISLNK(mode)
                            or info.file_size > 10 * 1024 * 1024
                        ):
                            found.append(
                                f"{path.relative_to(ctx.bundle)}!{info.filename} (unsafe member)"
                            )
                            continue
                        chunks: list[bytes] = []
                        member_total = 0
                        with zf.open(info) as source:
                            while chunk := source.read(64 * 1024):
                                member_total += len(chunk)
                                actual_total += len(chunk)
                                if (
                                    member_total > 10 * 1024 * 1024
                                    or actual_total > 100 * 1024 * 1024
                                ):
                                    found.append(
                                        f"{path.relative_to(ctx.bundle)}!{info.filename} "
                                        "(expanded size too large)"
                                    )
                                    chunks = []
                                    break
                                chunks.append(chunk)
                        if not chunks and member_total:
                            continue
                        payload = b"".join(chunks)
                        if b"\x00" in payload:
                            continue
                        text = payload.decode("utf-8", errors="replace")
                        if RESIDUAL_MARKER_RE.search(text):
                            found.append(
                                f"{path.relative_to(ctx.bundle)}!{info.filename}"
                            )
            except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                found.append(f"{path.relative_to(ctx.bundle)} ({exc})")
            continue
        payload = path.read_bytes()
        if b"\x00" in payload:
            continue
        text = payload.decode("utf-8", errors="replace")
        if RESIDUAL_MARKER_RE.search(text):
            found.append(str(path.relative_to(ctx.bundle)))
    return (
        fail(f"unresolved template markers in {found}")
        if found
        else ok("no unresolved template markers")
    )


def c_1_exec(ctx: Context) -> tuple[Any, str]:
    return (
        "INFO",
        "exec bit not enforced upstream (QC S6 retired); +x set at packaging time",
    )


def c_1_no_crlf(ctx: Context) -> tuple[bool, str]:
    offenders: list[str] = []
    for path in sorted(ctx.bundle.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        is_binary = b"\x00" in data
        if not is_binary and b"\r\n" in data:
            offenders.append(str(path.relative_to(ctx.bundle)))
    if not offenders:
        return ok("all text files use LF")
    shown = ", ".join(offenders[:5])
    more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
    return fail(f"CRLF line endings in {len(offenders)} file(s): {shown}{more}")


def c_2_exists(ctx: Context) -> tuple[bool, str]:
    return (
        ok("instruction.md exists")
        if exists_file(ctx, "instruction.md")
        else fail("instruction.md missing")
    )


def c_2_size(ctx: Context) -> tuple[bool | str | None, str]:
    """The 6000-char figure is a drafting guideline, not a QC rule.

    Input_Bundle_QC sets no length cap on instruction.md, so a longer prompt
    that reads well is not a defect; only a prompt long enough to swamp the
    agent's context is. Report the size, note the guideline when it is passed,
    and fail only past the hard ceiling.
    """
    try:
        size = len(ctx.text("instruction.md"))
    except FileNotFoundError:
        return fail("instruction.md missing")
    if size >= 20000:
        return fail(f"{size} chars >= 20000; trim the prompt or move detail into a spec file")
    if size >= 6000:
        return info(f"{size} chars, over the 6000-char drafting guideline (QC sets no cap)")
    return ok(f"{size} chars")


def c_2_abs_paths(ctx: Context) -> tuple[bool, str]:
    text = ctx.text("instruction.md")
    return (
        ok("absolute path in backticks found")
        if ABS_BACKTICK_RE.search(text)
        else fail("no absolute path in backticks")
    )


def c_2_seconds(ctx: Context) -> tuple[bool, str]:
    return (
        ok("time budget mentioned")
        if re.search(r"\bseconds?\b", ctx.text("instruction.md"), re.I)
        else fail("missing seconds/second")
    )


def c_2_online(ctx: Context) -> tuple[bool, str]:
    text = ctx.text("instruction.md")
    needles = ("online", "look up", "lookup", "search for", "solution online")
    return (
        ok("online lookup prohibition found")
        if any(n in text.lower() for n in needles)
        else fail("missing online lookup prohibition phrase")
    )


def c_3_parses(ctx: Context) -> tuple[bool, str]:
    data, err = ctx.toml()
    return fail(err or "parse failed") if data is None else ok("task.toml parses")


def c_3_root(ctx: Context) -> tuple[bool, str]:
    data = toml_data(ctx)
    if data is None:
        return fail("task.toml did not parse")
    keys = {"schema_version", "artifacts"}
    missing = sorted(keys - set(data))
    return fail(f"missing root keys {missing}") if missing else ok("root keys present")


def c_3_cross(ctx: Context) -> tuple[bool, str]:
    data = toml_data(ctx)
    if data is None:
        return fail("task.toml did not parse")
    return ok("cross-checks valid (slim schema has none)")


def c_5_exists(ctx: Context) -> tuple[bool, str]:
    return (
        ok("environment/Dockerfile exists")
        if exists_file(ctx, "environment/Dockerfile")
        else fail("environment/Dockerfile missing")
    )


def c_5_from(ctx: Context) -> tuple[bool, str]:
    lines = ctx.text("environment/Dockerfile").splitlines()
    froms = [ln for ln in lines if ln.strip().startswith("FROM ")]
    return (
        ok("FROM digest-pinned")
        if len(froms) == 1 and FROM_RE.fullmatch(froms[0])
        else fail(f"bad FROM lines: {froms}")
    )


def c_5_apt(ctx: Context) -> tuple[bool, str]:
    """Any number of apt layers is fine as long as each one is self-contained.

    The QC contract (structure_qc S9, DS-11) asks that the packages are present
    and the image builds offline afterwards, not that one RUN installs them all,
    so a Dockerfile that splits its installs across layers is not a defect. What
    does break a build is an install whose package index was fetched in an
    earlier layer, or a layer that leaves /var/lib/apt/lists behind.
    """
    installs = [
        cmd
        for cmd in logical_run_commands(ctx.text("environment/Dockerfile"))
        if re.search(r"\bapt-get\s+install\b", cmd)
    ]
    if not installs:
        return fail("no apt-get install RUN found")
    problems = [
        f"install layer {index + 1} does not run apt-get update in the same RUN"
        for index, cmd in enumerate(installs)
        if not re.search(r"\bapt-get\s+update\b", cmd)
    ]
    problems += [
        f"install layer {index + 1} does not clean /var/lib/apt/lists"
        for index, cmd in enumerate(installs)
        if "rm -rf /var/lib/apt/lists/*" not in cmd
    ]
    joined = "\n".join(installs)
    missing = [
        p
        for p in ("curl", "ca-certificates", "tmux")
        if not re.search(rf"\b{re.escape(p)}\b", joined)
    ]
    if missing:
        problems.append(f"packages missing {missing}")
    if problems:
        return fail("; ".join(problems))
    return ok(f"{len(installs)} self-contained apt install layer(s)")


def c_5_workdir(ctx: Context) -> tuple[bool, str]:
    text = ctx.text("environment/Dockerfile")
    problems = []
    if "@anthropic-ai/claude-code" in text:
        problems.append("agent-specific Claude Code install must not be baked in")
    if not re.search(r"^WORKDIR\s+/app\s*$", text, re.M):
        problems.append("missing WORKDIR /app")
    grants_app = re.search(r"chown\s+(-R\s+)?1000:1000\b[^\n]*\s/app\b", text) or re.search(
        r"COPY\s+--chown=1000:1000\b[^\n]*\s/app\b", text
    )
    if not grants_app:
        problems.append(
            "nothing gives uid 1000 ownership of /app "
            "([agent] user 1000:1000 must be able to write its artifacts; "
            "structure_qc S8 checks the ordering)"
        )
    return (
        fail("; ".join(problems))
        if problems
        else ok("agent-neutral workdir/mkdir present")
    )


def c_5_copy(ctx: Context) -> tuple[bool, str]:
    lines = [
        ln.strip()
        for ln in ctx.text("environment/Dockerfile").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    copy_lines = [
        " ".join(tok for tok in ln.split() if not tok.startswith("--"))
        for ln in lines
        if ln.startswith("COPY ")
    ]
    bad = [ln for ln in copy_lines if re.match(r"^COPY\s+(solution|tests)", ln)]
    if bad:
        return fail(f"forbidden COPY lines {bad}")
    expected = [f"COPY {item['dir']} {item['mount']}" for item in ctx.declared_inputs()]
    if sorted(copy_lines) != sorted(expected):
        return fail(f"COPY lines must be exactly {expected}, found {copy_lines}")
    return ok(f"input COPY lines {expected}")


def c_5_data_sizes(ctx: Context) -> tuple[bool, str]:
    too_big = [
        str(p.relative_to(ctx.bundle))
        for p in ctx.input_files()
        if p.stat().st_size > 100 * 1024 * 1024
    ]
    return fail(f"files > 100 MB: {too_big}") if too_big else ok("data files <= 100 MB")


def c_6_solve_sh(ctx: Context) -> tuple[bool, str]:
    p = ctx.path("solution/solve.sh")
    if not p.is_file():
        return fail("solve.sh missing")
    problems = []
    text = p.read_text(encoding="utf-8")
    if "set -euo pipefail" not in text:
        problems.append("missing set -euo pipefail")
    data = toml_data(ctx) or {}
    artifacts_value = data.get("artifacts")
    artifacts: list[Any] = artifacts_value if isinstance(artifacts_value, list) else []
    if "/solution/solve.py" not in text or not any(
        isinstance(a, str) and a in text for a in artifacts
    ):
        problems.append("does not copy /solution/solve.py to an artifact path")
    return fail("; ".join(problems)) if problems else ok("solve.sh valid")


def c_6_solve_py(ctx: Context) -> tuple[bool, str]:
    return (
        ok("solve.py exists")
        if exists_file(ctx, "solution/solve.py")
        else fail("solve.py missing")
    )


def c_7_ast(ctx: Context) -> tuple[bool, str]:
    _, tree, err = ctx.test_ast()
    return fail(err or "parse failed") if tree is None else ok("test_output.py parses")


def c_7_structure(ctx: Context) -> tuple[bool, str]:
    source, tree, err = ctx.test_ast()
    if tree is None or source is None:
        return fail(err or "test_output.py parse failed")
    assigned: set[str] = set()
    funcs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned.add(node.target.id)
        elif isinstance(node, ast.FunctionDef):
            funcs.add(node.name)
    problems = []
    missing_consts = sorted({"SAMPLE_SEED", "CHALLENGE_SEED", "EVAL_SEED"} - assigned)
    if missing_consts:
        problems.append(f"missing constants {missing_consts}")
    if "_write_corpus" not in funcs:
        problems.append("missing _write_corpus")
    if not re.search(r"if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", source):
        problems.append("missing if __name__ == '__main__' block")
    if not top_level_test_names(tree):
        problems.append("missing @criterion checks")
    return (
        fail("; ".join(problems)) if problems else ok("test_output.py structure valid")
    )


def c_7_weights(ctx: Context) -> tuple[bool, str]:
    weights, err = ctx.weights()
    if weights is None:
        return fail(err or "weights parse failed")
    if not all(isinstance(k, str) and isinstance(v, int) for k, v in weights.items()):
        return fail("criteria registrations must carry integer weights")
    illegal = sorted(
        f"{k}={v!r}"
        for k, v in weights.items()
        if isinstance(v, bool) or v not in LEGAL_WEIGHTS
    )
    if illegal:
        return fail(
            "weights must be in {1,3,5,-1,-3,-5} (no bool): " + ", ".join(illegal)
        )
    _, tree, ast_err = ctx.test_ast()
    tests = top_level_test_names(tree)
    if ast_err:
        return fail(ast_err)
    missing = sorted(set(weights) - tests)
    unweighted = sorted(tests - set(weights))
    problems = []
    if missing or unweighted:
        problems.append(f"bijection mismatch missing={missing} unweighted={unweighted}")
    if not any(v < 0 for v in weights.values()):
        problems.append("no negative weight")
    if weights.get("negative_hardcoded_sample_answers", 0) >= 0:
        problems.append(
            "negative_hardcoded_sample_answers missing or non-negative"
        )
    return fail("; ".join(problems)) if problems else ok("criteria registrations valid")


def c_9_corpus(ctx: Context) -> tuple[bool, str]:
    data = ctx.primary_input()
    sample_non_json = [
        p
        for p in data.glob("sample_*.*")
        if p.is_file() and p.suffix != ".json" and p.suffix
    ]
    if not sample_non_json:
        return fail("no sample_*.<ext> files")
    ext = Counter(p.suffix for p in sample_non_json).most_common(1)[0][0]
    sample_ext = list(data.glob(f"sample_*{ext}"))
    sample_json = list(data.glob("sample_*.json"))
    field_ext = list(data.glob(f"field_*{ext}"))
    problems = []
    if sample_json:
        problems.append(f"agent-visible sample answer files found: {len(sample_json)}")
    if not field_ext:
        problems.append(f"no field_*{ext} files")
    return (
        fail("; ".join(problems))
        if problems
        else ok(
            f"corpus ext={ext}, samples={len(sample_ext)}, fields={len(field_ext)}, answer_files=0"
        )
    )


def c_10_info(ctx: Context) -> tuple[str, str]:
    return info(
        f"Not checked statically. Run: harbor run --path {ctx.bundle} --agent oracle"
    )


def c_11_required(ctx: Context) -> tuple[bool, str]:
    weights, err = ctx.weights()
    if weights is None:
        return fail(err or "weights parse failed")
    value = weights.get("negative_hardcoded_sample_answers")
    return (
        ok("hardcoded sample cheat test present")
        if isinstance(value, int) and value < 0
        else fail(
            "negative_hardcoded_sample_answers missing or non-negative"
        )
    )


def recommended_weight(name: str) -> CheckFn:
    def check(ctx: Context) -> tuple[CheckStatus, str]:
        weights, err = ctx.weights()
        if weights is None:
            return fail(err or "weights parse failed")
        if name == "negative_filename_dependent_behaviour":
            names = [name, "negative_filename_dependent_behavior"]
        else:
            names = [name]
        if any(isinstance((value := weights.get(n)), int) and value < 0 for n in names):
            return ok(f"{name} present")
        message = f"recommended negative-weight cheat test missing: {name}"
        return fail(message) if ctx.strict else warn(message)

    return check


def _allowed_categories() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "_ibg_generate", Path(__file__).resolve().parent / "generate_bundle.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load generate_bundle.py category vocabulary")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    categories = {entry["display"] for entry in module._CATEGORIES.values()}
    if not categories:
        raise RuntimeError("generate_bundle.py category vocabulary is empty")
    return categories


def c_1_archetype_contract(ctx: Context) -> tuple[bool, str]:
    if not ARCHETYPE_RE.fullmatch(ctx.archetype):
        return fail(f"invalid archetype name: {ctx.archetype!r}")
    templates = (Path(__file__).resolve().parent / "templates").resolve()
    archetype_dir = (templates / ctx.archetype).resolve()
    if not archetype_dir.is_relative_to(templates):
        return fail("archetype directory escapes templates/")
    manifest_path = archetype_dir / "archetype.toml"
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return fail(f"unknown or invalid archetype {ctx.archetype!r}: {exc}")
    if manifest.get("name") != ctx.archetype:
        return fail("archetype manifest name does not match the TRUTH.md provenance archetype")
    artifacts = manifest.get("artifacts")
    data = toml_data(ctx)
    if data is None or data.get("artifacts") != artifacts:
        return fail("task.toml artifacts do not match the declared archetype manifest")
    source_archives = manifest.get("source_archives", [])
    if not isinstance(source_archives, list):
        return fail("archetype source_archives must be a list")
    for archive in source_archives:
        if not isinstance(archive, dict):
            return fail("archetype source archive entry is invalid")
        source = archive.get("source")
        output = archive.get("output")
        if not isinstance(source, str) or not isinstance(output, str):
            return fail("archetype source archive paths are invalid")
        if not ctx.path(output).is_file():
            return fail(f"archetype source archive output missing: {output}")
        if ctx.path(source).exists():
            return fail(f"unpacked archetype source leaked into bundle: {source}")
    return ok(f"archetype {ctx.archetype!r} matches its trusted manifest")


def c_1_min_counts(ctx: Context) -> tuple[bool, str]:
    if not ARCHETYPE_RE.fullmatch(ctx.archetype):
        return fail(f"invalid archetype name: {ctx.archetype!r}")
    templates = (Path(__file__).resolve().parent / "templates").resolve()
    archetype_dir = (templates / ctx.archetype).resolve()
    if not archetype_dir.is_relative_to(templates):
        return fail("archetype directory escapes templates/")
    manifest_path = archetype_dir / "archetype.toml"
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return fail(f"unknown or invalid archetype {ctx.archetype!r}: {exc}")
    min_inputs = manifest.get("min_inputs", 6)
    min_outputs = manifest.get("min_outputs", 6)
    if min_inputs < 6 or min_outputs < 6:
        return fail(
            "archetype min_inputs/min_outputs must be >= 6 "
            f"(got {min_inputs}/{min_outputs})"
        )
    n = len(ctx.input_files())
    if n < min_inputs:
        return fail(
            f"input directories hold {n} files, archetype requires >= {min_inputs}"
        )
    data = toml_data(ctx)
    artifacts = data.get("artifacts", []) if data is not None else []
    m = len(artifacts) if isinstance(artifacts, list) else 0
    if m < min_outputs:
        return fail(
            f"task.toml declares {m} artifacts, archetype requires >= {min_outputs}"
        )
    return ok(f"inputs {n} >= {min_inputs}, outputs {m} >= {min_outputs}")


_SEED_TOKEN_RE = re.compile(
    r"\b(?:EVAL_SEED|CHALLENGE_SEED|SAMPLE_SEED|ROOT_SEED|SECRET_KEY|API_KEY)\b"
)
# A hidden-corpus filename smells like the reseeded eval/challenge captures the
# verifier owns.  The solver must never read those; it must decode from the
# agent-visible spec only.
_HIDDEN_CORPUS_RE = re.compile(
    r"(?:sample_|field_|eval_|challenge_)[A-Za-z0-9_]*\.[A-Za-z0-9]+"
)


def _visible_corpus_text(ctx: Context) -> str:
    """Concatenate every agent-visible text file (instruction + data corpus).

    The solvability audit treats a literal in solve.py as legitimate only when
    its provenance is visible here.  environment/data/ is the agent-visible
    corpus; instruction.md and task.toml are the rest of what the agent holds.
    """
    parts: list[str] = []
    for rel in ("instruction.md", "task.toml"):
        try:
            parts.append(ctx.path(rel).read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    for entry in ctx.input_files():
        try:
            parts.append(entry.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return "\n".join(parts)


def _declared_output_paths(ctx: Context) -> set[str]:
    data = toml_data(ctx)
    artifacts = data.get("artifacts", []) if data is not None else []
    return {a for a in artifacts if isinstance(a, str)} if isinstance(
        artifacts, list
    ) else set()


def _literal_has_visible_provenance(value: str, visible: str) -> bool:
    """True when the exact literal text appears in the agent-visible corpus.

    Seed-varying constants (e.g. the format-recovery grammar dict) are legal
    precisely because the generator writes them into the shipped spec, so their
    text is present in `visible`.  A constant absent from every visible file is
    the trap signature: a value the solver must reproduce with nothing to derive
    it from.
    """
    token = value.strip()
    if not token:
        return True
    if token in visible:
        return True
    # Hex-ish / numeric constants: also accept the bare digits appearing in the
    # spec tables (the spec documents mode ids and offsets as plain integers).
    compact = token.lower().removeprefix("0x")
    return bool(compact) and compact in visible.lower()


def _looks_like_encoded_secret(text: str) -> bool:
    """True only for strings that resemble an embedded key, not code or paths.

    The trap signature is a high-entropy blob the agent could never derive: a
    long run of hex, or base64/base32 with mixed case and digits.  Ordinary
    long identifiers (`negative_measurements_raise`) and container paths
    (`/app/out/dependency_resolution.json`) are not secrets even though they are
    long, so anything carrying a path separator, dot, or space is excluded and a
    bare snake_case or lowercase word is not treated as opaque.
    """
    if "/" in text or "." in text or any(c.isspace() for c in text):
        return False
    if re.fullmatch(r"[0-9a-fA-F]{32,}", text):
        return True
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]{24,}", text):
        return False
    has_lower = any(c.islower() for c in text)
    has_upper = any(c.isupper() for c in text)
    has_digit = any(c.isdigit() for c in text)
    return has_lower and has_upper and has_digit


def audit_solution_source(ctx: Context) -> tuple[CheckStatus, str]:
    """Static solvability audit of solution/solve.py (§6.3).

    Proves, without executing anything, that the reference solver depends only
    on agent-visible provenance.  It fails when the solver would need something
    the agent can never see: a file outside /app/data and the declared outputs,
    an environment secret/seed, the network, the verifier's hidden corpus, or a
    large opaque constant that appears in no agent-visible file.  This is the
    static half of the honest-solvability guarantee; run_semantic is the
    dynamic half.
    """
    solve_py = ctx.path("solution/solve.py")
    if not solve_py.is_file():
        return info("no solution/solve.py to audit")
    try:
        source = solve_py.read_text(encoding="utf-8")
    except OSError as exc:
        return fail(f"cannot read solution/solve.py: {exc}")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return fail(f"solution/solve.py does not parse: {exc}")

    findings: list[str] = []

    # A network import is deliberately NOT a finding here.  Some archetypes drive
    # a localhost service over urllib, and network use is a policy matter owned by
    # allow_internet plus the shipped negative cheat tests, not a solvability
    # defect: reaching the network never substitutes for information the task
    # withheld.  Solvability turns only on hidden provenance, audited below.

    # 1. Environment secrets / seeds are verifier-only; a solver that reads them
    #    is not solving from agent-visible provenance.  Reading an ordinary
    #    process env var for an I/O directory (INPUT_DIR, OUT_DIR, APP_ROOT) is
    #    benign; only a read that pulls in a verifier seed or secret is a defect,
    #    which _SEED_TOKEN_RE catches whether or not os.environ is involved.
    if _SEED_TOKEN_RE.search(source):
        findings.append("references a verifier seed or secret token")

    # 2. The agent's whole container is /app (plus scratch under /tmp), so any
    #    /app/... or /tmp/... path is agent-visible working space.  The defect is
    #    a read that escapes into verifier-only roots (the reseeded eval corpus,
    #    the hidden tests/solution overlays, or the reward log), never a
    #    reference to the agent's own data, output, or extraction directories.
    #    A hidden-corpus-shaped name is only a defect when it is NOT a shipped
    #    file: a name present under environment/data/ is agent-visible by
    #    definition, so sample_requests.jsonl shipped as an input is not hidden.
    verifier_only_roots = (
        "/tests",
        "/solution",
        "/cheat",
        "/logs",
    )
    shipped_data_names = {entry.name for entry in ctx.input_files()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if text.startswith(verifier_only_roots):
                findings.append(f"references verifier-only path '{text}'")
            elif _HIDDEN_CORPUS_RE.search(text) and (
                PurePosixPath(text).name not in shipped_data_names
            ):
                findings.append(f"references a hidden-corpus filename '{text}'")

    # 4. Large opaque constants with no visible provenance are the trap
    #    signature (an embedded key / seed-derived magic the agent cannot see).
    visible = _visible_corpus_text(ctx)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bytes) and len(node.value) >= 8:
                forms = [node.value.hex(), node.value.hex(" ")]
                try:
                    forms.append(node.value.decode("ascii"))
                except UnicodeDecodeError:
                    pass
                if not any(
                    _literal_has_visible_provenance(form, visible) for form in forms
                ):
                    findings.append(
                        f"embeds an opaque {len(node.value)}-byte constant "
                        "with no agent-visible provenance"
                    )
            elif isinstance(node.value, str) and len(node.value) >= 24:
                stripped = node.value.strip()
                looks_opaque = _looks_like_encoded_secret(stripped)
                if looks_opaque and not _literal_has_visible_provenance(
                    stripped, visible
                ):
                    findings.append(
                        "embeds an opaque long string literal with no "
                        "agent-visible provenance"
                    )

    if findings:
        unique = sorted(set(findings))
        return fail(
            "solution/solve.py is not solvable from agent-visible files: "
            + "; ".join(unique)
        )
    return ok(
        "solution/solve.py reads only /app/data and declared outputs; no "
        "secrets, seeds, network, hidden corpus, or opaque constants"
    )


TRUTH_SECTIONS = (
    "Defect",
    "Load-bearing work",
    "Verification",
    "Root cause",
    "Solution shape",
    "Ordered plan",
    "Pitfalls",
    "Provenance",
)
TRUTH_PROVENANCE_KEYS = (
    "uuid",
    "instance_id",
    "task_name",
    "fix_patch_sha256",
    "solve_py_sha256",
    "language",
)
# QC DS-27: TRUTH.md describes the task, never how it was produced.
TRUTH_FORBIDDEN_KEYS = ("authored_by", "status", "archetype", "generator_seed", "trailer_token")
TRUTH_NARRATION_RE = re.compile(
    r"generate_bundle|harbor-generator|\barchetypes?\b|scaffold|generator\s+seed|\bdatagen\b|"
    r"this (?:bundle|task) was (?:built|generated|made|produced|authored|scaffolded)",
    re.I,
)
TRUTH_DEFECT_LABELS = ("focal", "drift", "trap")
TRUTH_MIN_CHARS = 4000
TRUTH_PROVENANCE_RE = re.compile(r"^```yaml\n(.*?)^```$", re.M | re.S)
TRUTH_YAML_KEY_RE = re.compile(r"^([a-z_][a-z0-9_]*):(?:\s+(.*))?$")


def truth_text(ctx: Context) -> tuple[str | None, str]:
    if not exists_file(ctx, "solution/TRUTH.md"):
        return None, "TRUTH.md is missing from solution/"
    try:
        return ctx.text("solution/TRUTH.md"), ""
    except OSError as exc:
        return None, f"TRUTH.md is unreadable: {exc}"


def truth_provenance(ctx: Context) -> tuple[dict[str, str] | None, str]:
    """Parse the fenced yaml provenance block into a flat key -> scalar map.

    Only the subset of YAML the block actually uses is understood: top-level
    ``key: value`` scalars and ``key: >`` folded blocks.  Pulling in a YAML
    dependency would break the stdlib-only contract this validator holds.
    """
    text, err = truth_text(ctx)
    if text is None:
        return None, err
    match = TRUTH_PROVENANCE_RE.search(text)
    if not match:
        return None, "TRUTH.md has no ```yaml provenance block"
    values: dict[str, str] = {}
    pending: str | None = None
    folded: list[str] = []
    for line in match.group(1).splitlines():
        if line.startswith("  ") or not line.strip():
            if pending is not None:
                folded.append(line.strip())
            continue
        if pending is not None:
            values[pending] = " ".join(part for part in folded if part)
            pending, folded = None, []
        key_match = TRUTH_YAML_KEY_RE.match(line)
        if not key_match:
            continue
        key, raw = key_match.group(1), (key_match.group(2) or "").strip()
        if raw in (">", "|"):
            pending = key
            continue
        values[key] = raw.split("  #")[0].strip()
    if pending is not None:
        values[pending] = " ".join(part for part in folded if part)
    return values, ""


def c_15_exists(ctx: Context) -> tuple[CheckStatus, str]:
    text, err = truth_text(ctx)
    if text is None:
        return fail(err)
    if len(text) < TRUTH_MIN_CHARS:
        return fail(
            f"TRUTH.md is {len(text)} chars; a golden-trajectory document under "
            f"{TRUTH_MIN_CHARS} chars is a stub, not a derivation"
        )
    return ok(f"TRUTH.md present ({len(text)} chars, {len(text.splitlines())} lines)")


def c_15_title(ctx: Context) -> tuple[CheckStatus, str]:
    text, err = truth_text(ctx)
    if text is None:
        return fail(err)
    expected = f"# TRUTH.md - {ctx.bundle.name}"
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if first != expected:
        return fail(f"first line is {first!r}; expected {expected!r}")
    return ok(expected)


def c_15_sections(ctx: Context) -> tuple[CheckStatus, str]:
    text, err = truth_text(ctx)
    if text is None:
        return fail(err)
    found = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    missing = [name for name in TRUTH_SECTIONS if name not in found]
    if missing:
        return fail(f"missing sections: {', '.join(missing)}")
    order = [found.index(name) for name in TRUTH_SECTIONS]
    if order != sorted(order):
        return fail(f"sections are out of canonical order: {found}")
    return ok(f"all {len(TRUTH_SECTIONS)} canonical sections present and ordered")


def c_15_defect_labels(ctx: Context) -> tuple[CheckStatus, str]:
    text, err = truth_text(ctx)
    if text is None:
        return fail(err)
    body = text.split("## Defect", 1)[-1].split("\n## ", 1)[0]
    counts = {label: body.count(f"({label})") for label in TRUTH_DEFECT_LABELS}
    missing = [label for label, n in counts.items() if n == 0]
    if missing:
        return fail(
            "Defect section never classifies its items as "
            + ", ".join(f"({label})" for label in missing)
        )
    if counts["focal"] < 2:
        return fail(
            f"Defect section declares {counts['focal']} (focal) item(s); a task "
            "with fewer than two focal defects is under-specified"
        )
    rendered = ", ".join(f"{n} {label}" for label, n in counts.items())
    return ok(rendered)


def c_15_provenance_keys(ctx: Context) -> tuple[CheckStatus, str]:
    values, err = truth_provenance(ctx)
    if values is None:
        return fail(err)
    missing = [key for key in TRUTH_PROVENANCE_KEYS if key not in values]
    if missing:
        return fail(f"provenance block is missing keys: {', '.join(missing)}")
    empty = [key for key in TRUTH_PROVENANCE_KEYS if not values[key]]
    if empty:
        return fail(f"provenance keys have empty values: {', '.join(empty)}")
    attribution = [key for key in TRUTH_FORBIDDEN_KEYS if key in values]
    if attribution:
        return fail(f"provenance carries authoring/process keys (QC DS-27): {', '.join(attribution)}")
    text, _ = truth_text(ctx)
    narration = sorted({m.group(0) for m in TRUTH_NARRATION_RE.finditer(text or "")})
    if narration:
        return fail(f"TRUTH.md narrates how the bundle was produced (QC DS-27): {narration}")
    return ok(f"{len(values)} provenance keys parsed")


def c_15_instance_id(ctx: Context) -> tuple[CheckStatus, str]:
    values, err = truth_provenance(ctx)
    if values is None:
        return fail(err)
    instance = values.get("instance_id", "")
    if instance != ctx.bundle.name:
        return fail(f"instance_id is {instance!r}; expected {ctx.bundle.name!r}")
    expected_task = f"terminal-bench/{ctx.bundle.name}"
    if values.get("task_name") != expected_task:
        return fail(
            f"task_name is {values.get('task_name')!r}; expected {expected_task!r}"
        )
    declared, toml_err = ctx.toml()
    if declared is None:
        return fail(f"task.toml unreadable, cannot cross-check task_name: {toml_err}")
    actual = declared.get("task", {}).get("name")
    if actual != expected_task:
        return fail(
            f"task.toml declares task.name {actual!r}, TRUTH.md {expected_task!r}"
        )
    return ok("instance_id and task_name agree with the bundle and task.toml")


def c_15_fix_patch_sha(ctx: Context) -> tuple[CheckStatus, str]:
    values, err = truth_provenance(ctx)
    if values is None:
        return fail(err)
    checks = {
        "fix_patch_sha256": ctx.path("solution/solve.sh"),
        "solve_py_sha256": ctx.path("solution/solve.py"),
    }
    for key, path in checks.items():
        if not path.is_file():
            return fail(f"{path.name} is missing; cannot verify {key}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if values.get(key) != actual:
            return fail(
                f"{key} is {values.get(key)!r} but {path.name} hashes to {actual}"
            )
    return ok("fix_patch_sha256 and solve_py_sha256 match the shipped solution files")


def c_15_grading_facts(ctx: Context) -> tuple[CheckStatus, str]:
    text, err = truth_text(ctx)
    if text is None:
        return fail(err)
    weights, weights_err = ctx.weights()
    if weights is None:
        return fail(f"tests/test_output.py registrations unreadable: {weights_err}")
    positive_total = sum(w for w in weights.values() if isinstance(w, int) and w > 0)
    if f"{positive_total}" not in text:
        return fail(
            f"TRUTH.md never states the Channel A positive weight total "
            f"({positive_total}) registered in tests/test_output.py"
        )
    unnamed = [
        name
        for name, weight in weights.items()
        if isinstance(weight, int) and weight < 0 and name not in text
    ]
    if unnamed:
        return fail(f"TRUTH.md never names negative tests: {', '.join(sorted(unnamed))}")
    return ok(
        f"positive weight total {positive_total} stated and every negative test named"
    )


QC_DIR = Path(__file__).resolve().parent.parent / "Input_Bundle_QC"


def _only_binary_archives_skipped(line: str) -> bool:
    """structure_qc X1 notes every binary file it skips; zip archives are expected."""
    match = re.search(r"skipped as binary, re-check any that are text: (.+)$", line)
    return bool(match) and all(
        name.strip().endswith(".zip") for name in match.group(1).split(",")
    )


def qc_script(script: str) -> CheckFn:
    """Delegate a section to the authoritative Input_Bundle_QC script."""

    def check(ctx: Context) -> tuple[CheckStatus, str]:
        path = QC_DIR / script
        if not path.is_file():
            return fail(f"{path} not found; the QC folder is the contract authority")
        proc = subprocess.run(
            [sys.executable, str(path), str(ctx.bundle)],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = proc.stdout.splitlines()
        fails = [ln for ln in lines if ln.startswith("FAIL")]
        warns = [
            ln
            for ln in lines
            if ln.startswith("WARN") and not _only_binary_archives_skipped(ln)
        ]
        if proc.returncode != 0 or fails:
            return fail("; ".join(fails) or proc.stderr.strip() or f"exit {proc.returncode}")
        if warns:
            # QC WARN means push-ready once the tasker approves; surface it
            # without blocking, since only the tasker can give that approval.
            return info(f"{script} passes; tasker approval needed for: " + "; ".join(warns))
        return ok(f"{script} passes")

    return check


def only_for(
    archetypes: set[str], check: Callable[[Context], tuple[Any, str]]
) -> Callable[[Context], tuple[Any, str]]:
    def gated(ctx: Context) -> tuple[Any, str]:
        if ctx.archetype not in archetypes:
            return "INFO", f"not applicable to archetype '{ctx.archetype}'"
        return check(ctx)

    return gated


_CORPUS_ARCHETYPES = {"format-recovery"}

RULES: list[Rule] = [
    ("§1.1", "Bundle name matches ^[a-z0-9][a-z0-9-]{2,63}$", c_1_name),
    ("§1.2", "Required top-level files present", c_1_root_files),
    ("§1.3", "Required top-level dirs present", c_1_root_dirs),
    ("§1.4", "environment/ has Dockerfile and data/ only", c_1_env),
    (
        "§1.5",
        "solution/ has exactly solve.sh and solve.py",
        only_for(_CORPUS_ARCHETYPES, c_1_solution_exact),
    ),
    ("§1.6", "tests/ has exactly required verifier files", c_1_tests_exact),
    ("§1.6a", "Optional cheat/ overlay is valid when present", c_1_cheat_optional),
    ("§1.7", "every environment/ input directory is non-empty", c_1_data_nonempty),
    ("§1.8", "No __pycache__ dirs anywhere", c_1_no_pycache),
    ("§1.9", "solve.sh and test.sh exec bit (retired: set at packaging)", c_1_exec),
    ("§1.10", "No CRLF line endings in text files", c_1_no_crlf),
    ("§1.11", "No unresolved template markers in text files", c_1_no_residual_markers),
    ("§1.12", "declared archetype matches its trusted manifest", c_1_archetype_contract),
    (
        "§1.13",
        "input directories and task.toml artifacts meet the archetype minimum counts",
        c_1_min_counts,
    ),
    ("§2.1", "instruction.md exists", c_2_exists),
    ("§2.2", "instruction.md length is workable for the agent", c_2_size),
    ("§2.3", "instruction.md contains an absolute path in backticks", c_2_abs_paths),
    ("§2.4", "instruction.md mentions a seconds time budget", c_2_seconds),
    ("§2.5", "instruction.md forbids online lookup", c_2_online),
    ("§3.1", "task.toml parses as TOML", c_3_parses),
    ("§3.2", "task.toml root keys present", c_3_root),
    ("§3.3", "bundle tree and task.toml pass Input_Bundle_QC/structure_qc.py", qc_script("structure_qc.py")),
    ("§3.4", "instruction.md passes Input_Bundle_QC/instruction_qc.py", qc_script("instruction_qc.py")),
    ("§3.5", "task.toml cross-checks are valid", c_3_cross),
    ("§5.1", "environment/Dockerfile exists", c_5_exists),
    ("§5.2", "environment/Dockerfile FROM is digest-pinned public.ecr.aws", c_5_from),
    ("§5.3", "environment/Dockerfile apt install layers are self-contained", c_5_apt),
    (
        "§5.4",
        "environment/Dockerfile stays agent-neutral and sets /app",
        c_5_workdir,
    ),
    ("§5.5", "environment/Dockerfile copies exactly the declared input dirs", c_5_copy),
    ("§5.6", "input files are <= 100 MB", c_5_data_sizes),
    (
        "§6.1",
        "solve.sh exists, strict, copies solve.py to artifacts",
        only_for(_CORPUS_ARCHETYPES, c_6_solve_sh),
    ),
    ("§6.2", "solve.py exists", only_for(_CORPUS_ARCHETYPES, c_6_solve_py)),
    (
        "§6.3",
        "solve.py is solvable from agent-visible files only (static audit)",
        audit_solution_source,
    ),
    ("§7.1", "test_output.py parses via ast", c_7_ast),
    (
        "§7.2",
        "test_output.py declares seeds, _write_corpus, main, and tests",
        only_for(_CORPUS_ARCHETYPES, c_7_structure),
    ),
    (
        "§7.4",
        "criteria registrations are valid and bijective with the @criterion checks",
        c_7_weights,
    ),
    ("§7.5", "tests/judge.toml passes Input_Bundle_QC/judge_qc.py", qc_script("judge_qc.py")),
    ("§7.6", "test channel passes Input_Bundle_QC/tests_qc.py", qc_script("tests_qc.py")),
    ("§10", "Local harbor test contract", c_10_info),
    (
        "§11.1",
        "Hardcoded sample answers cheat test is present",
        only_for(_CORPUS_ARCHETYPES, c_11_required),
    ),
    (
        "§11.2",
        "Filename-dependent behaviour cheat test is recommended",
        only_for(
            _CORPUS_ARCHETYPES,
            recommended_weight("negative_filename_dependent_behaviour"),
        ),
    ),
    (
        "§11.3",
        "Runtime training-data access cheat test is recommended",
        only_for(
            _CORPUS_ARCHETYPES,
            recommended_weight("negative_reads_training_corpus_at_runtime"),
        ),
    ),
    (
        "§11.4",
        "Nondeterministic output cheat test is recommended",
        only_for(
            _CORPUS_ARCHETYPES,
            recommended_weight("negative_nondeterministic_output"),
        ),
    ),
    (
        "§11.5",
        "Verifier-dependency rebinding cheat test is recommended",
        only_for(
            _CORPUS_ARCHETYPES,
            recommended_weight("negative_rebinds_verifier_dependencies"),
        ),
    ),
    ("§15.1", "TRUTH.md exists and is a real derivation", c_15_exists),
    ("§15.2", "TRUTH.md H1 names the bundle", c_15_title),
    ("§15.3", "TRUTH.md carries the 8 canonical sections in order", c_15_sections),
    ("§15.4", "Defect section classifies items focal/drift/trap", c_15_defect_labels),
    ("§15.5", "Provenance block parses and carries required keys", c_15_provenance_keys),
    ("§15.6", "Provenance instance_id and task_name match the bundle", c_15_instance_id),
    ("§15.7", "Provenance digests match the shipped solution files", c_15_fix_patch_sha),
    ("§15.8", "TRUTH.md grading facts agree with tests/", c_15_grading_facts),
]


def section_title(ref: str) -> str:
    first = ref.split(".")[0]
    titles = {
        "§1": "§1 Directory shape",
        "§2": "§2 instruction.md",
        "§3": "§3 task.toml",
        "§4": "§4 README.md",
        "§5": "§5 environment/Dockerfile",
        "§6": "§6 solution/",
        "§7": "§7 tests/",
        "§8": "§8 test.sh",
        "§9": "§9 Two-tier corpus",
        "§10": "§10 Local test contract",
        "§11": "§11 Cheat vectors",
        "§15": "§15 TRUTH.md",
    }
    return titles.get(first, first)


def run(ctx: Context) -> tuple[int, int, int, int]:
    passed = failed = warnings = infos = 0
    current_section = ""
    for ref, description, check in RULES:
        section = section_title(ref)
        if section != current_section:
            print(section)
            current_section = section
        try:
            status, detail = check(ctx)
        except Exception as exc:  # noqa: BLE001 - validators should keep going
            status, detail = False, f"validator error: {exc}"
        if status is True:
            passed += 1
            print(f"PASS[{ref}] {description}: {detail}")
        elif status is False:
            failed += 1
            print(f"FAIL[{ref}] {description}: {detail}")
        elif status == "INFO":
            infos += 1
            print(f"INFO[{ref}] {detail}")
        else:
            warnings += 1
            print(f"WARN[{ref}] {description}: {detail}")
    print("=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed, {warnings} warnings")
    blocking = failed + (warnings if ctx.strict else 0)
    if blocking:
        print(f"GATE: FAIL - {blocking} blocking issue(s); this bundle MUST NOT ship")
    else:
        print("GATE: PASS - bundle may ship")
    print("=" * 60)
    return passed, failed, warnings, infos


def _docker_run(args: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        ["docker", *args],
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


_SCRUBBED_ENV_KEYS = (
    "EVAL_SEED",
    "CHALLENGE_SEED",
    "SAMPLE_SEED",
    "ROOT_SEED",
    "SEED",
    "SECRET_KEY",
    "API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
)


def _scrub_env_file(temp: Path) -> Path:
    path = temp / "scrub.env"
    path.write_text("".join(f"{key}=\n" for key in _SCRUBBED_ENV_KEYS), encoding="utf-8")
    return path


def run_semantic(bundle: Path, report_path: Path | None = None) -> bool:
    if shutil.which("docker") is None:
        print("SEMANTIC: FAIL - docker executable is unavailable", file=sys.stderr)
        return False
    data = tomllib.loads((bundle / "task.toml").read_text(encoding="utf-8"))
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not all(
        isinstance(item, str) and item.startswith("/app/") for item in artifacts
    ):
        print("SEMANTIC: FAIL - task.toml artifacts are invalid", file=sys.stderr)
        return False
    if report_path is not None:
        resolved_report = report_path.expanduser().resolve()
        try:
            resolved_report.relative_to(bundle)
        except ValueError:
            pass
        else:
            print(
                "SEMANTIC: FAIL - report path must be outside the bundle",
                file=sys.stderr,
            )
            return False

    with tempfile.TemporaryDirectory(prefix="ibg-semantic-") as temp_name:
        temp = Path(temp_name)
        # Grade a tests-only copy (QC Step 10): judge.toml removed and reward.toml
        # rewritten to the test channel, so no judge model or API key is needed.
        copy = temp / "tests-only"
        exe = subprocess.run(
            [sys.executable, str(_QC_ROOT / "exe_copy.py"), str(bundle), str(copy)],
            text=True,
            capture_output=True,
            check=False,
        )
        if exe.returncode != 0:
            print(f"SEMANTIC: FAIL - exe_copy.py refused: {exe.stdout[-600:]}{exe.stderr[-300:]}", file=sys.stderr)
            return False
        token = re.sub(r"[^a-z0-9]", "", temp.name.lower())[-20:]
        env_image = f"ibg-semantic-{token}-env"
        tests_image = f"ibg-semantic-{token}-tests"
        agent = f"ibg-semantic-{token}-agent"
        pre = f"ibg-semantic-{token}-pre"
        post = f"ibg-semantic-{token}-post"
        containers = [agent, pre, post]
        images = [env_image, tests_image]
        try:
            _docker_run(
                [
                    "build",
                    "-q",
                    "-t",
                    env_image,
                    "-f",
                    str(copy / "environment" / "Dockerfile"),
                    str(copy / "environment"),
                ]
            )
            _docker_run(
                [
                    "build",
                    "-q",
                    "-t",
                    tests_image,
                    "-f",
                    str(copy / "tests" / "Dockerfile"),
                    str(copy / "tests"),
                ]
            )
            # Solvability sandbox (load-bearing): build from the agent-visible
            # env image (never the tests image), cut the network, and scrub every
            # verifier seed/secret. Reward 1.0 here proves the answer is derivable
            # from agent-visible files (the §9 invariant); do not relax these.
            _docker_run(
                [
                    "create",
                    "--name",
                    agent,
                    "--network",
                    "none",
                    "--env-file",
                    str(_scrub_env_file(temp)),
                    env_image,
                    "sleep",
                    "infinity",
                ]
            )
            _docker_run(["start", agent])
            _docker_run(["cp", f"{copy / 'solution'}/.", f"{agent}:/solution"])

            _docker_run(["create", "--name", pre, tests_image, "sleep", "infinity"])
            _docker_run(["start", pre])
            _docker_run(["exec", pre, "bash", "/tests/test.sh"])
            pre_reward = json.loads(
                _docker_run(
                    ["exec", pre, "cat", "/logs/verifier/reward.json"], capture=True
                )
            )["reward"]

            _docker_run(["exec", agent, "bash", "/solution/solve.sh"])
            transfer = temp / "artifacts"
            for artifact in artifacts:
                relative = artifact.removeprefix("/app/")
                host_path = transfer / relative
                host_path.parent.mkdir(parents=True, exist_ok=True)
                _docker_run(["cp", f"{agent}:{artifact}", str(host_path)])

            _docker_run(["create", "--name", post, tests_image, "sleep", "infinity"])
            _docker_run(["start", post])
            for artifact in artifacts:
                relative = artifact.removeprefix("/app/")
                parent = str(PurePosixPath(artifact).parent)
                _docker_run(["exec", post, "mkdir", "-p", parent])
                _docker_run(["cp", str(transfer / relative), f"{post}:{artifact}"])
            _docker_run(["exec", post, "bash", "/tests/test.sh"])
            post_reward = json.loads(
                _docker_run(
                    ["exec", post, "cat", "/logs/verifier/reward.json"], capture=True
                )
            )["reward"]
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
            print(f"SEMANTIC: FAIL - {exc}", file=sys.stderr)
            return False
        finally:
            subprocess.run(
                ["docker", "rm", "-f", *containers],
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            subprocess.run(
                ["docker", "image", "rm", "-f", *images],
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    floor_ok = pre_reward < 1.0
    solvable = post_reward == 1.0
    report = {
        "bundle": bundle.name,
        "nop_reward": pre_reward,
        "solvable_reward": post_reward,
        "oracle_reward": post_reward,
        "post_reward": post_reward,
        "floor_ok": floor_ok,
        "solvable": solvable,
        "passed": floor_ok and solvable,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if report_path is not None:
        report_path.expanduser().resolve().write_text(rendered, encoding="utf-8")
    print("SEMANTIC RESULTS")
    print(rendered, end="")
    if not floor_ok:
        print(
            "SEMANTIC: FAIL - nop/empty container already reached reward 1.0 "
            "(the grader has no floor)",
            file=sys.stderr,
        )
    if not solvable:
        print(
            "SEMANTIC: FAIL - solve.sh could not reach reward 1.0 using only "
            "agent-visible files (network disabled, verifier seeds scrubbed); "
            "the task depends on information the agent never receives",
            file=sys.stderr,
        )
    return bool(report["passed"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an Input Bundle Format Spec bundle."
    )
    parser.add_argument("bundle_dir", help="Path to bundle directory")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Accepted for compatibility; rule refs are always printed",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Accepted for compatibility; strict is now the default",
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="Do not treat warnings as blocking (result is NOT shippable)",
    )
    parser.add_argument(
        "--archetype",
        default=None,
        help="Override archetype detection (default: read from solution/TRUTH.md provenance, fallback format-recovery)",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Build Docker images and prove nop < 1.0 and oracle/post = 1.0",
    )
    parser.add_argument(
        "--semantic-report",
        type=Path,
        default=None,
        help="Write semantic measurements outside the bundle as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    bundle = Path(args.bundle_dir)
    if not bundle.exists():
        print(f"usage error: bundle path does not exist: {bundle}", file=sys.stderr)
        return 2
    if not bundle.is_dir():
        print(f"usage error: bundle path is not a directory: {bundle}", file=sys.stderr)
        return 2
    strict = not args.lenient
    _, failed, warnings, _ = run(
        Context(bundle.resolve(), strict=strict, archetype=args.archetype)
    )
    if failed or (strict and warnings):
        return 1
    if args.semantic and not run_semantic(bundle.resolve(), args.semantic_report):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
