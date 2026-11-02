"""Seeded stdlib generator for environment/data of counter-page-crash-recovery.

Writes the shipped book (journal.jsonl, disk_pages.bin, page_map.ini, checkpoint.toml,
txn_catalog.csv, audit_queries.json), project.zip (from WORK/project), recovery_contract.md
(from WORK), dependency_manifest.json, compiler_flags.json, expected_targets.json and
ci_config.yaml.  Scaffold leftovers that the task does not use are removed.
"""
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "counter-page-crash-recovery"
DATA = BUNDLE / "environment" / "data"
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))

import bookgen  # noqa: E402

SEED = 806610
REQUIRED_VERSION = "2.4.0"
ZIP_STAMP = "2019-03-14T09:26:52"
ARCHIVE_MEMBERS = [
    "pyproject.toml",
    "README.md",
    "src/pagerecover/__init__.py",
    "src/pagerecover/__main__.py",
    "src/pagerecover/cli.py",
    "src/pagerecover/loader.py",
    "src/pagerecover/pages.py",
    "src/pagerecover/recovery.py",
    "src/pagerecover/reports.py",
    "tests/test_smoke.py",
]
ARTIFACTS = [
    "/app/out/package.zip",
    "/app/out/selftest.json",
    "/app/out/build_report.json",
    "/app/out/module_core.json",
    "/app/out/module_metrics.json",
    "/app/out/dependency_resolution.json",
    "/app/out/summary.json",
]
CI_YAML = """runtime: python3.12
network: disabled
commands:
  - 'python -m unittest discover -s tests -v'
  - 'python -c "import pagerecover; print(pagerecover.__version__)"'
  - 'python -c ''import pagerecover.cli'''
  - 'python -m compileall -q src'
artifact_policy:
  archive: /app/out/package.zip
  report: /app/out/selftest.json
  deterministic_json: true
"""
STALE = ["build.log", "module_map.json", "scoring_fixtures.jsonl", "report_contract.md"]


def dump(obj):
    return (json.dumps(obj, indent=2) + "\n").encode("utf-8")


def project_zip(path):
    src = HERE / "project"
    files = sorted(p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        for f in files:
            info = zipfile.ZipInfo("project/" + f.relative_to(src).as_posix(), (2024, 6, 3, 11, 20, 14))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, f.read_bytes())


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    for name in STALE:
        (DATA / name).unlink(missing_ok=True)
    book = bookgen.shipped_book(SEED)
    files = bookgen.render_book(book, bookgen.Rng(SEED ^ 0xF11E))
    files["dependency_manifest.json"] = dump({
        "package": "pagerecover",
        "python_runtime": "3.12",
        "allowed_dependency_policy": "stdlib-only",
        "forbidden_runtime_dependencies": ["tomli", "requests", "httpx", "aiohttp"],
        "required_version": REQUIRED_VERSION,
    })
    files["compiler_flags.json"] = dump({
        "python": "3.12",
        "bytecode_check": True,
        "isolated_import": True,
        "zip_compression": "stored",
        "deterministic_zip_timestamps": ZIP_STAMP,
    })
    files["expected_targets.json"] = dump({"archive_members": ARCHIVE_MEMBERS, "artifacts": ARTIFACTS})
    files["ci_config.yaml"] = CI_YAML.encode("utf-8")
    files["recovery_contract.md"] = (HERE / "recovery_contract.md").read_bytes()
    for name, data in files.items():
        (DATA / name).write_bytes(data)
    project_zip(DATA / "project.zip")
    for p in sorted(DATA.iterdir()):
        print("%-26s %9d bytes %7d lines" % (p.name, p.stat().st_size, p.read_bytes().count(b"\n")))


if __name__ == "__main__":
    main()
