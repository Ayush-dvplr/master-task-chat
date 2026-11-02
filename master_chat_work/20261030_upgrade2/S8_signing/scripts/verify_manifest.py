#!/usr/bin/env python3
"""DRAFT: verify Ayush's signed rule-file inventory. Not installed."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

NAMESPACE = "tb-master-rules-v1"
IDENTITY = "ayush-tb-master"


def regular_file(path: Path) -> bool:
    # Do not follow links: a link could redirect a protected path after signing.
    if path.is_symlink():
        raise ValueError(f"symlink in protected scope: {path}")
    return path.is_file()


def collect(tb: Path, home: Path) -> dict[str, str]:
    roots = {"tb": tb, "home": home}
    individual = [
        "tb/master_chat_tasks/README.md",
        "tb/master_chat_tasks/GOALS.md",
        "tb/master_chat_tasks/state.json",
        "tb/master_chat_tasks/auto/AUTO_POLICY.md",
        "tb/master_chat_tasks/auto/PLAN_TEMPLATE.md",
        "tb/master_chat_tasks/auto/auto.py",
        "tb/master_chat_work/_dev_research/pipeline_v4/PLAN.md",
        "tb/master_chat_work/20261024_process/MASTER_UPGRADE_PLAN_v1.md",
        "tb/Terminal_2.0_Harbor_Harness/scripts/master_queue.py",
        "home/.config/opencode/opencode.jsonc",
        "home/.config/opencode/tui.json",
        "home/.config/opencode/dcp.jsonc",
        "home/.config/opencode/package.json",
        "home/.config/opencode/package-lock.json",
        "home/.config/opencode/oh-my-openagent/native-nudge.json",
    ]
    trees = [
        ("tb/master_chat_tasks/knowledge", None),
        ("tb/master_chat_tasks/prompts/templates", None),
        ("tb/master_chat_tasks/tools", {".py", ".sh"}),
        ("tb/master_chat_tasks/auto/plans", {".md"}),
        ("home/.config/opencode/plugins", None),
        ("home/.config/opencode/rules", {".md"}),
        ("home/.config/opencode/patches", {".js", ".sh", ".diff"}),
    ]
    paths = set(individual)
    for prefix, suffixes in trees:
        base_name, rel = prefix.split("/", 1)
        base = roots[base_name] / rel
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"protected directory missing or symlinked: {base}")
        for current, dirs, files in os.walk(base, followlinks=False):
            for name in dirs:
                if (Path(current) / name).is_symlink():
                    raise ValueError(f"symlinked protected directory: {Path(current) / name}")
            for name in files:
                path = Path(current) / name
                if path.is_symlink():
                    raise ValueError(f"symlinked protected file: {path}")
                if suffixes is None or path.suffix in suffixes:
                    paths.add(f"{base_name}/{path.relative_to(roots[base_name]).as_posix()}")
    result = {}
    for label in sorted(paths):
        base_name, rel = label.split("/", 1)
        path = roots[base_name] / rel
        if not regular_file(path):
            raise ValueError(f"protected file missing: {path}")
        result[label] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def encode(files: dict[str, str]) -> bytes:
    return (json.dumps({"schema": 1, "files": files}, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["snapshot", "verify"])
    p.add_argument("--tb", type=Path, required=True)
    p.add_argument("--home", type=Path, required=True)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--signature", type=Path)
    p.add_argument("--allowed-signers", type=Path)
    a = p.parse_args()
    current = encode(collect(a.tb, a.home))
    if a.mode == "snapshot":
        sys.stdout.buffer.write(current)
        return 0
    if not all((a.manifest, a.signature, a.allowed_signers)):
        p.error("verify requires manifest, signature, and allowed-signers")
    approved = a.manifest.read_bytes()
    if encode(json.loads(approved)) != approved:
        raise ValueError("manifest is not canonical")
    verified = subprocess.run(
        ["ssh-keygen", "-Y", "verify", "-f", str(a.allowed_signers),
         "-I", IDENTITY, "-n", NAMESPACE, "-s", str(a.signature)],
        input=approved, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if verified.returncode:
        raise ValueError("signature rejected: " + verified.stderr.decode(errors="replace"))
    if current != approved:
        old = json.loads(approved)["files"]
        now = json.loads(current)["files"]
        changed = [name for name in sorted(old.keys() | now.keys()) if old.get(name) != now.get(name)]
        raise ValueError("protected scope differs: " + ", ".join(changed[:30]) +
                         (f" ... ({len(changed)} total)" if len(changed) > 30 else ""))
    print(f"VERIFIED: signature and {len(json.loads(current)['files'])} protected files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DENY: {exc}", file=sys.stderr)
        raise SystemExit(1)
