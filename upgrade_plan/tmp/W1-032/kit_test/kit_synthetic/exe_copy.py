#!/usr/bin/env python3
"""Build the tests-only copy of a bundle that the Step 10 execution gate runs.

Why a copy exists: the shipped bundle grades with both channels, and the judged
channel calls an LLM through tests/judge.toml. The oracle, nop and stub agents
make no model calls and leave no real trajectory, so running the judge on them
either aborts the verifier (no OPENAI_API_KEY: rewardkit raises and writes no
reward.json) or scores the trajectory criteria against nothing. Step 10 measures
whether the declared artifacts and the deterministic reward function agree, so
it runs on a copy whose reward is the test channel alone. The bundle under
review is never touched.

What the copy changes, and nothing else:

  1. Refuses to build when tests/judge.toml does not load under the rewardkit
     0.2.1 schema (judged offline, never executed) or when the test channel's
     weights fail tests_qc.py A1-A4 / W1-W7.
  2. Deletes tests/judge.toml.
  3. Rewrites tests/reward.toml to weights = { test_output = 1 / positive total },
     so a full pass reads exactly 1.0 and doing nothing reads exactly 0.0.
  4. Sets network_mode = "public" in [environment], [verifier],
     [verifier.environment] and [agent] and drops their allowed_hosts lines,
     because Harbor refuses no-network/allowlist on hosts whose Docker kernel
     cannot enforce them (Docker Desktop). [agent] must move too: Harbor checks
     the agent-phase policy before the run starts, whatever the agent is, so an
     [agent] allowlist over a public [environment] still refuses to start.
  5. Drops the pre-baked OpenHands SDK install from environment/Dockerfile, so
     the image builds in seconds instead of minutes. Step 10 runs the oracle
     (uploads solution/ and execs solve.sh), nop (does nothing) and stub agents,
     and none of them start an installed agent, so the venv is dead weight here.
     A real openhands-sdk run must use the bundle itself, never this copy.
  6. With --stub, replaces solution/ with a solve.sh that only creates each
     declared artifact empty ({} for .json), for the stub run.
  7. With --owner-only, appends a trailer to solution/solve.sh that strips group
     and other access from every file the run wrote under /app (0600, or 0700
     where the owner could already execute it), the mode an agent editor leaves
     behind, for the owner-only oracle run.

Every change is printed. Exit codes: 0 copy built, 1 refused, 2 usage error.

Usage:
  python3 exe_copy.py <BUNDLE_PATH> <DEST_DIR> [--stub] [--owner-only]
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Key sets of rewardkit 0.2.1 models.py (JudgeTomlConfig, JudgeConfig,
# CriterionConfig, ScoringConfig), all extra="forbid". Used only when rewardkit
# itself is not importable on the host.
TOP_KEYS = {"judge", "criterion", "scoring"}
JUDGE_KEYS = {
    "judge", "model", "version", "files", "mode", "timeout", "reasoning_effort",
    "isolated", "cwd", "reference", "atif-trajectory", "atif_trajectory",
    "mcp_servers", "weight", "prompt_template",
}
CRITERION_KEYS = {
    "description", "type", "name", "id", "points", "min", "max", "weight",
    "files", "negate", "optional", "annotations",
}
SCORING_KEYS = {"aggregation", "threshold"}
NETWORK_TABLES = {"environment", "verifier", "verifier.environment", "agent"}
# The pre-baked agent runtime (S9 / DS-29) is the slowest layer in the image and
# no Step 10 agent uses it: harbor 0.24.0 oracle.py execs solution/solve.sh and
# nop.py does nothing, so neither reads /opt/openhands-sdk-venv.
OPENHANDS_RE = re.compile(r"openhands[-_.](?:sdk|tools)|/opt/openhands-sdk-venv")
GATING_IDS = re.compile(r"^FAIL \[(A[1-4]|W[1-7])\]")


def log(msg: str) -> None:
    print(f"[exe-copy] {msg}")


def judge_load_errors(path: Path) -> list[str]:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"tests/judge.toml does not parse: {exc}"]
    try:
        from rewardkit.models import JudgeTomlConfig  # type: ignore[import-not-found]
    except ImportError:
        JudgeTomlConfig = None
    if JudgeTomlConfig is not None:
        try:
            JudgeTomlConfig.model_validate(raw)
        except Exception as exc:
            return [f"tests/judge.toml rejected by rewardkit: {exc}"]
        return []
    errors = [f"unknown top-level key {k!r}" for k in sorted(set(raw) - TOP_KEYS)]
    judge = raw.get("judge")
    if not isinstance(judge, dict):
        errors.append("[judge] table missing")
    else:
        errors += [f"unknown [judge] key {k!r}" for k in sorted(set(judge) - JUDGE_KEYS)]
    errors += [
        f"unknown [scoring] key {k!r}"
        for k in sorted(set(raw.get("scoring") or {}) - SCORING_KEYS)
    ]
    crits = raw.get("criterion")
    if not isinstance(crits, list) or not crits:
        errors.append("no [[criterion]] table")
    else:
        for i, c in enumerate(crits, 1):
            if "description" not in c:
                errors.append(f"criterion #{i} has no description")
            errors += [f"criterion #{i} unknown key {k!r}" for k in sorted(set(c) - CRITERION_KEYS)]
    return errors


def test_channel_errors(bundle: Path) -> list[str]:
    proc = subprocess.run(
        [sys.executable, str(HERE / "tests_qc.py"), str(bundle)],
        capture_output=True, text=True, check=False,
    )
    return [ln for ln in proc.stdout.splitlines() if GATING_IDS.match(ln)]


def positive_total(test_output: Path) -> int:
    tree = ast.parse(test_output.read_text(encoding="utf-8"))
    total = 0
    for node in tree.body:
        call = node.value if isinstance(node, ast.Expr) else None
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "criteria"
        ):
            for kw in call.keywords:
                if (
                    kw.arg == "weight"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, int)
                    and kw.value.value > 0
                ):
                    total += kw.value.value
    return total


def tests_only_reward_toml(pos: int) -> str:
    return (
        "[[reward]]\n"
        'name = "reward"\n'
        'aggregation = "weighted-sum"\n'
        f"weights = {{ test_output = {1 / pos!r} }}\n"
        "\n"
        "[scoring.test_output]\n"
        'aggregation = "weighted-sum"\n'
    )


def open_network(task_toml: Path) -> list[str]:
    changes: list[str] = []
    table = ""
    out: list[str] = []
    for line in task_toml.read_text(encoding="utf-8").splitlines(keepends=True):
        header = re.match(r"^\s*\[([^\[\]]+)\]\s*$", line)
        if header:
            table = header.group(1).strip()
        elif table in NETWORK_TABLES:
            key = line.split("=", 1)[0].strip()
            if key == "allowed_hosts":
                changes.append(f"[{table}] dropped {line.strip()}")
                continue
            if key == "network_mode":
                changes.append(f"[{table}] {line.strip()} -> network_mode = \"public\"")
                line = 'network_mode = "public"\n'
        out.append(line)
    task_toml.write_text("".join(out), encoding="utf-8")
    return changes


def dockerfile_instructions(text: str) -> list[str]:
    """Split a Dockerfile into instructions, keeping backslash continuations whole."""
    out: list[str] = []
    buf: list[str] = []
    for line in text.splitlines(keepends=True):
        buf.append(line)
        if not line.rstrip("\r\n").rstrip().endswith("\\"):
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return out


def strip_openhands(dockerfile: Path) -> list[str]:
    if not dockerfile.is_file():
        return []
    groups = dockerfile_instructions(dockerfile.read_text(encoding="utf-8"))
    kept = [g for g in groups if not OPENHANDS_RE.search(g)]
    if len(kept) == len(groups):
        return []
    dockerfile.write_text("".join(kept), encoding="utf-8")
    changes = [
        f"environment/Dockerfile dropped: {' '.join(g.split())[:70]}..."
        for g in groups
        if OPENHANDS_RE.search(g)
    ]
    changes.append(
        "environment/Dockerfile: the pre-baked OpenHands SDK venv is gone from the copy "
        "(build speed only; oracle, nop and stub never start an installed agent)"
    )
    return changes


def write_stub(dest: Path) -> list[str]:
    artifacts = tomllib.loads((dest / "task.toml").read_text(encoding="utf-8")).get("artifacts") or []
    lines = ["#!/bin/bash", "set -euo pipefail"]
    for path in artifacts:
        body = "echo '{}' > \"$P\"" if path.endswith(".json") else ': > "$P"'
        lines.append(f"P={path}; mkdir -p \"$(dirname \"$P\")\"; {body}")
    shutil.rmtree(dest / "solution")
    (dest / "solution").mkdir()
    stub = dest / "solution" / "solve.sh"
    stub.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stub.chmod(0o755)
    return [f"solution/ replaced by a stub solve.sh creating {len(artifacts)} empty artifact(s)"]


def write_owner_only(dest: Path) -> list[str]:
    """Make the oracle leave its files at mode 0600, the mode an agent editor leaves.

    The OpenHands file_editor writes through a temp file in the same directory
    and renames it, and temp files are created owner-only, so a program the
    agent wrote is readable by uid 1000 alone. A verifier that runs that program
    after dropping to an unprivileged uid cannot open it and fails every check
    that executes it. solution/solve.sh installs its program with cp, which
    leaves 0644, so the plain oracle run scores 1.000 and the hole stays
    invisible until a real trajectory is graded. This variant reproduces the
    agent's mode, so the same oracle has to score 1.000 against it.

    The owner's own execute bit survives: an agent told to deliver an executable
    entry point runs chmod +x and lands at 0700, not 0600, so stripping that bit
    would fail the task for a reason no agent could avoid. Only group and other
    access, which an editor never grants, is taken away.
    """
    solve = dest / "solution" / "solve.sh"
    trailer = (
        "\n# Owner-only variant (QC Step 10): leave every file this run wrote readable by its\n"
        "# owner alone, the mode an agent editor leaves behind, keeping the owner execute bit.\n"
        "find /app -xdev -type f -user 1000 -perm -u+x -print0 2>/dev/null"
        " | xargs -0 -r chmod 700 || true\n"
        "find /app -xdev -type f -user 1000 ! -perm -u+x -print0 2>/dev/null"
        " | xargs -0 -r chmod 600 || true\n"
    )
    solve.write_text(solve.read_text(encoding="utf-8") + trailer, encoding="utf-8")
    return [
        "solution/solve.sh: appended a trailer leaving every file the run wrote under /app at"
        " mode 0600, or 0700 where the owner could already execute it (agent editor mode)"
    ]


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("-")}
    args = [a for a in argv if not a.startswith("-")]
    stub = "--stub" in flags
    owner_only = "--owner-only" in flags
    unknown = sorted(flags - {"--stub", "--owner-only"})
    if len(args) != 2 or unknown:
        if unknown:
            print(f"usage error: unknown flag(s) {' '.join(unknown)}", file=sys.stderr)
        print((__doc__ or "").split("Usage:")[-1].strip(), file=sys.stderr)
        return 2
    bundle, dest = Path(args[0]).resolve(), Path(args[1]).resolve()
    if not (bundle / "task.toml").is_file() or not (bundle / "tests").is_dir():
        print(f"usage error: {bundle} is not a bundle", file=sys.stderr)
        return 2
    if dest.exists():
        print(f"usage error: {dest} already exists; pick a fresh directory", file=sys.stderr)
        return 2

    refusals = judge_load_errors(bundle / "tests" / "judge.toml")
    refusals += test_channel_errors(bundle)
    if refusals:
        for r in refusals:
            log(f"REFUSED: {r}")
        return 1
    pos = positive_total(bundle / "tests" / "test_output.py")
    if pos <= 0:
        log("REFUSED: test_output.py registers no positive weight")
        return 1

    shutil.copytree(bundle, dest)
    log(f"copied {bundle} -> {dest}")
    log("tests/judge.toml loads under the rewardkit 0.2.1 schema (validated, not executed)")
    (dest / "tests" / "judge.toml").unlink()
    log("deleted tests/judge.toml")
    (dest / "tests" / "reward.toml").write_text(tests_only_reward_toml(pos), encoding="utf-8")
    log(f"tests/reward.toml -> weights = {{ test_output = {1 / pos!r} }} (1 / positive total {pos})")
    for change in open_network(dest / "task.toml"):
        log(f"task.toml {change}")
    for change in strip_openhands(dest / "environment" / "Dockerfile"):
        log(change)
    if stub:
        for change in write_stub(dest):
            log(change)
    if owner_only:
        for change in write_owner_only(dest):
            log(change)
    log("scores from this copy are TESTS-ONLY; the bundle under review was not edited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
