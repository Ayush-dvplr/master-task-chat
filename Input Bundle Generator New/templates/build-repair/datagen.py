"""Seeded repair context for the build-repair archetype.

The project (environment/data/project -> project.zip) is a template. This
writes the sidecars around it; each feeds a value the repaired deliverable must
carry:

  dependency_manifest.json  required_version for __version__, pyproject, reports
  compiler_flags.json       zip compression and member timestamp of package.zip
  expected_targets.json     archive members and artifact paths
  module_map.json           module roles; summary.json lists the mapped modules
  ci_config.yaml            the CI commands selftest.json reports
  scoring_fixtures.jsonl    entries the repaired package must score as listed
  build.log                 the failing pre-repair build; build_report lists its error types
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path


def _score(entry: dict) -> dict:
    tolerance = max(1.0, abs(float(entry["expected"])) * 0.05)
    misses = math.ceil(abs(float(entry["observed"]) - float(entry["expected"])) / tolerance)
    penalty = misses * 7 + (10 if float(entry["seconds"]) > 30 else 0) + (15 if entry["critical"] and misses else 0)
    score = max(0, min(100, 100 - penalty))
    bucket = "ok" if score >= 90 else "watch" if score >= 70 else "repair" if score >= 40 else "critical"
    return {"score": score, "bucket": bucket}


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    rng = random.Random(seed)
    package = subs["{{PACKAGE_NAME}}"]
    for stale in data_dir.iterdir():
        if stale.is_file() and stale.name != "report_contract.md":
            stale.unlink()

    version = f"{rng.randint(1, 5)}.{rng.randint(0, 12)}.{rng.randint(0, 9)}"
    subs["{{REQUIRED_VERSION}}"] = version
    (data_dir / "dependency_manifest.json").write_text(json.dumps({
        "package": package,
        "python_runtime": "3.12",
        "allowed_dependency_policy": "stdlib-only",
        "forbidden_runtime_dependencies": ["tomli", "requests", "httpx", "aiohttp"],
        "expected_public_api": ["load_manifest", "score_entry", "score_batch", "summarize", "render_report"],
        "required_version": version,
    }, indent=2) + "\n", encoding="utf-8")

    stamp = f"{rng.randint(1990, 2019)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T{rng.randint(0, 23):02d}:{rng.randrange(0, 60, 2):02d}:00"
    (data_dir / "compiler_flags.json").write_text(json.dumps({
        "python": "3.12",
        "bytecode_check": True,
        "isolated_import": True,
        "max_api_call_seconds": 5,
        "zip_compression": rng.choice(["stored", "deflated"]),
        "deterministic_zip_timestamps": stamp,
    }, indent=2) + "\n", encoding="utf-8")

    (data_dir / "expected_targets.json").write_text(json.dumps({
        "archive_members": ["pyproject.toml", "README.md", f"src/{package}/__init__.py", f"src/{package}/core.py",
                            f"src/{package}/metrics.py", f"src/{package}/reports.py", "tests/test_smoke.py"],
        "artifacts": ["/app/out/package.zip", "/app/out/selftest.json", "/app/out/build_report.json",
                      "/app/out/module_core.json", "/app/out/module_metrics.json",
                      "/app/out/dependency_resolution.json", "/app/out/summary.json"],
    }, indent=2) + "\n", encoding="utf-8")

    roles = {
        f"{package}.__init__": "export the public API and version",
        f"{package}.core": "load manifests, score entries, and summarize batches",
        f"{package}.metrics": "classify scores into stable buckets",
        f"{package}.reports": "render deterministic human-readable summaries",
        "tests.test_smoke": "retain visible smoke coverage for import and scoring behavior",
    }
    for extra in rng.sample(["cli", "compat", "plugins", "exporters", "legacy"], 2):
        roles[f"tools.{extra}"] = "out-of-tree helper; not part of the package"
    (data_dir / "module_map.json").write_text(json.dumps(roles, indent=2) + "\n", encoding="utf-8")

    commands = ["python -m unittest discover -s tests -v",
                f'python -c "import {package}; print({package}.__version__)"']
    commands += rng.sample([
        "python -m compileall -q src",
        f"python -c \"import {package}.metrics as m; print(m.BUCKET_ORDER)\"",
        "python -m zipfile -l /app/out/package.zip",
        f"python -c \"import {package}; print(sorted(n for n in dir({package}) if not n.startswith('_')))\"",
    ], rng.randint(1, 3))
    yaml = ["runtime: python3.12", "network: disabled", "commands:"]
    yaml += ["  - '" + c.replace("'", "''") + "'" for c in commands]
    yaml += ["artifact_policy:", "  archive: /app/out/package.zip", "  report: /app/out/selftest.json", "  deterministic_json: true"]
    (data_dir / "ci_config.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")

    fixtures = []
    for index in range(5500):
        expected = rng.randint(0, 900)
        drift = rng.randint(-max(1, expected // 2), max(1, expected // 2))
        entry = {"name": f"fixture-{index:04d}", "expected": expected, "observed": max(0, expected + drift),
                 "seconds": rng.randint(0, 60), "critical": rng.random() < 0.3}
        entry["want"] = _score(entry)
        fixtures.append(json.dumps(entry, separators=(",", ":")))
    (data_dir / "scoring_fixtures.jsonl").write_text("\n".join(fixtures) + "\n", encoding="utf-8")

    log = ["$ python -m pip install --no-build-isolation --no-index -e .", "Obtaining file:///app/project"]
    for index in range(rng.randint(6000, 6600)):
        log.append(f"  Compiling /usr/local/lib/python3.12/site-packages/_vendor/pkg{index // 40:03d}/mod{index % 40:02d}.py ...")
    log += [
        "  error: subprocess-exited-with-error",
        "  × Getting requirements to build editable did not run successfully.",
        "  error: package directory 'python' does not exist",
        "ERROR: Package requires a different Python: 3.12.4 not in '>=3.13'",
        "$ python -m compileall -q src",
        f'  File "src/{package}/metrics.py", line 3',
        '    return "ok"',
        "TabError: inconsistent use of tabs and spaces in indentation",
        f'  File "src/{package}/metrics.py", line 12',
        "    BUCKET_ORDER = [\"ok\", \"watch\", \"repair\", \"critical\"",
        "SyntaxError: '[' was never closed",
        "$ python -m unittest discover -s tests -v",
    ]
    for index in range(rng.randint(8800, 9400)):
        log.append(f"test_vendor_{index:05d} (vendor.tests.test_vendor.VendorCase.test_vendor_{index:05d}) ... ok")
    log += [
        "test_smoke (unittest.loader._FailedTest.test_smoke) ... ERROR",
        "Traceback (most recent call last):",
        '  File "tests/test_smoke.py", line 3, in <module>',
        f"    from {package} import score_entry, summarize",
        f"ModuleNotFoundError: No module named '{package}'",
        f'  File "src/{package}/core.py", line 6, in <module>',
        "    import tomli",
        "ModuleNotFoundError: No module named 'tomli'",
        f'  File "src/{package}/core.py", line 8, in <module>',
        "    from .reports import DEFAULT_LABEL",
        f"ImportError: cannot import name 'DEFAULT_LABEL' from partially initialized module '{package}.reports'",
        "",
        "FAILED (errors=1)",
    ]
    (data_dir / "build.log").write_text("\n".join(log) + "\n", encoding="utf-8")
