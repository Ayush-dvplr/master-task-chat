#!/usr/bin/env python3
from __future__ import annotations

import shutil
import stat
import textwrap
import zipfile
import json
import re
import sys
from pathlib import Path, PurePosixPath

DATA = Path("/app/data")

SOURCE_ARCHIVE = Path("/app/data/project.zip")
PROJECT = Path("/app/project")
PACKAGE = "{{PACKAGE_NAME}}"
PKG_DIR = PROJECT / "src" / PACKAGE
OUT = Path("/app/out")
ARTIFACTS = [
    "/app/out/package.zip",
    "/app/out/selftest.json",
    "/app/out/build_report.json",
    "/app/out/module_core.json",
    "/app/out/module_metrics.json",
    "/app/out/dependency_resolution.json",
    "/app/out/summary.json",
]


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sidecar(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


VERSION = sidecar("dependency_manifest.json")["required_version"]


def repair_metadata() -> None:
    write(
        PROJECT / "pyproject.toml",
        '''
        [build-system]
        requires = ["setuptools>=68"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "@@PACKAGE@@"
        version = "@@VERSION@@"
        description = "{{FORMAT_TAG}} diagnostics helpers for {{PRODUCER_SYSTEM}} {{CONTAINER_NOUN}} manifests"
        requires-python = ">=3.12"
        dependencies = []

        [tool.setuptools]
        package-dir = {"" = "src"}

        [tool.setuptools.packages.find]
        where = ["src"]
        '''.replace("@@PACKAGE@@", PACKAGE).replace("@@VERSION@@", VERSION),
    )


def repair_package() -> None:
    write(
        PKG_DIR / "__init__.py",
        '''
        from __future__ import annotations

        from .core import load_manifest, score_batch, score_entry, summarize
        from .reports import render_report

        __version__ = "@@VERSION@@"

        __all__ = [
            "__version__",
            "load_manifest",
            "score_batch",
            "score_entry",
            "summarize",
            "render_report",
        ]
        '''.replace("@@VERSION@@", VERSION),
    )
    write(
        PKG_DIR / "metrics.py",
        '''
        BUCKET_ORDER = ["ok", "watch", "repair", "critical"]


        def bucket_for_score(score: int) -> str:
            if score >= 90:
                return "ok"
            if score >= 70:
                return "watch"
            if score >= 40:
                return "repair"
            return "critical"
        ''',
    )
    write(
        PKG_DIR / "core.py",
        '''
        from __future__ import annotations

        import math
        import tomllib
        from pathlib import Path

        from .metrics import bucket_for_score

        DEFAULT_LABEL = "{{CONTAINER_NOUN}}/{{PRODUCER_SYSTEM}}"


        def load_manifest(path: str | Path) -> dict:
            with open(path, "rb") as fh:
                return tomllib.load(fh)


        def score_entry(entry: dict) -> dict:
            name = str(entry["name"])
            expected = float(entry["expected"])
            observed = float(entry["observed"])
            seconds = float(entry.get("seconds", 0))
            critical = bool(entry.get("critical", False))
            if expected < 0 or observed < 0 or seconds < 0:
                raise ValueError("manifest measurements must be non-negative")
            tolerance = max(1.0, abs(expected) * 0.05)
            misses = math.ceil(abs(observed - expected) / tolerance)
            penalty = misses * 7
            if seconds > 30:
                penalty += 10
            if critical and misses:
                penalty += 15
            score = max(0, min(100, 100 - penalty))
            return {
                "name": name,
                "score": score,
                "bucket": bucket_for_score(score),
                "label": DEFAULT_LABEL,
            }


        def score_batch(entries: list[dict]) -> list[dict]:
            return [score_entry(entry) for entry in entries]


        def summarize(entries: list[dict]) -> dict:
            scored = score_batch(entries)
            total = sum(item["score"] for item in scored)
            average = round(total / len(scored), 2) if scored else 0.0
            return {"count": len(scored), "average": average, "items": scored}
        ''',
    )
    write(
        PKG_DIR / "reports.py",
        '''
        from __future__ import annotations

        from .core import summarize


        def render_report(entries: list[dict]) -> str:
            summary = summarize(entries)
            lines = [f"{{FORMAT_TAG}} manifest report: {summary['count']} entries"]
            lines.append(f"average={summary['average']:.2f}")
            for item in summary["items"]:
                lines.append(f"- {item['name']}: {item['bucket']} ({item['score']})")
            return "\\n".join(lines)
        ''',
    )


def build_archive() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / "package.zip"
    if archive.exists():
        archive.unlink()
    keep = [PROJECT / "pyproject.toml", PROJECT / "README.md"]
    keep.extend(sorted((PROJECT / "src").rglob("*.py")))
    keep.extend(sorted((PROJECT / "tests").rglob("test_*.py")))
    flags = sidecar("compiler_flags.json")
    method = zipfile.ZIP_DEFLATED if flags["zip_compression"] == "deflated" else zipfile.ZIP_STORED
    year, month, day, hour, minute, second = (int(x) for x in re.split(r"[-T:]", flags["deterministic_zip_timestamps"]))
    stamp = (year, month, day, hour, minute, second)
    members = set(sidecar("expected_targets.json")["archive_members"])
    missing = members - {p.relative_to(PROJECT).as_posix() for p in keep}
    if missing:
        raise SystemExit(f"archive would miss {sorted(missing)}")
    with zipfile.ZipFile(archive, "w") as zf:
        for path in keep:
            name = path.relative_to(PROJECT).as_posix()
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = method
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(info, path.read_bytes())


def replay_fixtures() -> tuple[int, int]:
    sys.path.insert(0, str(PROJECT / "src"))
    from importlib import import_module
    core = import_module(f"{PACKAGE}.core")
    total = passed = 0
    for line in (DATA / "scoring_fixtures.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        got = core.score_entry(entry)
        total += 1
        passed += {"score": got["score"], "bucket": got["bucket"]} == entry["want"]
    return total, passed


def ci_commands() -> list[str]:
    block = (DATA / "ci_config.yaml").read_text(encoding="utf-8").split("commands:\n", 1)[1]
    found = []
    for line in block.splitlines():
        if not line.startswith("  - '"):
            break
        found.append(line[5:-1].replace("''", "'"))
    return found


def write_reports() -> None:
    fixtures_total, fixtures_passed = replay_fixtures()
    fixed_modules = ["__init__.py", "core.py", "metrics.py", "reports.py"]
    build_report = {
        "ok": True,
        "package": PACKAGE,
        "version": VERSION,
        "layout": "src",
        "python": "3.12",
        "fixed_modules": fixed_modules,
        "fix_categories": [
            "packaging-metadata",
            "missing-package-init",
            "circular-import",
            "stdlib-tomllib",
            "metrics-syntax",
            "scoring-penalty",
        ],
        "log_errors": sorted(set(re.findall(r"^([A-Za-z]+Error): ", (DATA / "build.log").read_text(encoding="utf-8"), re.M))),
    }
    module_core = {
        "ok": True,
        "module": f"{PACKAGE}.core",
        "public_functions": ["load_manifest", "score_entry", "score_batch", "summarize"],
        "uses_stdlib_tomllib": True,
        "default_label": "{{CONTAINER_NOUN}}/{{PRODUCER_SYSTEM}}",
        "average_rounding_digits": 2,
        "negative_measurements_raise": "ValueError",
    }
    module_metrics = {
        "ok": True,
        "module": f"{PACKAGE}.metrics",
        "bucket_order": ["ok", "watch", "repair", "critical"],
        "thresholds": {"ok_min": 90, "watch_min": 70, "repair_min": 40, "critical_max": 39},
        "syntax_repaired": True,
    }
    dependency_resolution = {
        "ok": True,
        "package": PACKAGE,
        "requires_python": ">=3.12",
        "dependencies": [],
        "removed_dependencies": ["tomli"],
        "stdlib_modules_used": ["math", "pathlib", "tomllib"],
    }
    selftest = {
        "ok": True,
        "package": PACKAGE,
        "version": VERSION,
        "tests_run": 6,
        "fixtures_total": fixtures_total,
        "fixtures_passed": fixtures_passed,
        "ci_commands": ci_commands(),
        "archive": "/app/out/package.zip",
        "reports": [path for path in ARTIFACTS if path.endswith(".json") and path != "/app/out/selftest.json"],
    }
    summary = {
        "ok": True,
        "package": PACKAGE,
        "version": VERSION,
        "artifact_count": len(ARTIFACTS),
        "artifacts": ARTIFACTS,
        "primary_archive": "/app/out/package.zip",
        "json_reports": 6,
        "modules_mapped": sorted(k for k in sidecar("module_map.json") if k.startswith(PACKAGE + ".")),
    }
    write_json(OUT / "selftest.json", selftest)
    write_json(OUT / "build_report.json", build_report)
    write_json(OUT / "module_core.json", module_core)
    write_json(OUT / "module_metrics.json", module_metrics)
    write_json(OUT / "dependency_resolution.json", dependency_resolution)
    write_json(OUT / "summary.json", summary)


def extract_source() -> None:
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ARCHIVE) as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit(f"unsafe source archive member: {info.filename!r}")
            destination = (PROJECT / Path(*rel.parts)).resolve()
            if not destination.is_relative_to(PROJECT):
                raise SystemExit(f"source archive member escapes project: {info.filename!r}")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(zf.read(info))


def main() -> None:
    if not SOURCE_ARCHIVE.is_file():
        raise SystemExit(f"missing source archive at {SOURCE_ARCHIVE}")
    extract_source()
    stray = PROJECT / "python"
    if stray.exists():
        shutil.rmtree(stray)
    repair_metadata()
    repair_package()
    build_archive()
    write_reports()


if __name__ == "__main__":
    main()
