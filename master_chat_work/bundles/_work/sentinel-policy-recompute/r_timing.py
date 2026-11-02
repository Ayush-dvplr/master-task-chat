"""t3 timing: run each ledger_repair program's resolve on every R corpus under the stated 60 s limit; report seconds and
whether ledger_repair.json equals the authoritative document.

Usage: r_timing.py <tests/test_output.py> <oracle tool.zip> <work dir> <scratch dir>   (python with rewardkit + pyarrow)
"""
import importlib.util
import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

tests_file, tool_zip, work, scratch = (Path(arg) for arg in sys.argv[1:5])
spec = importlib.util.spec_from_file_location("t3_tests", tests_file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

namespace: dict = {}
lever_source = (work / "t3_levers.py").read_text()
exec(lever_source[lever_source.index("FLOOR = "):lever_source.index("VARIANTS = {name")], namespace)
R = namespace["R"]
base = zipfile.ZipFile(tool_zip).read("cli.py").decode()
programs = {"reference": base}
for label in ("r-greedy", "r-dp2", "r-dp", "r-mitm", "r-naive"):
    cli = base
    for old, new in R[label]:
        assert cli.count(old) == 1, (label, old)
        cli = cli.replace(old, new)
    programs[label] = cli
programs["blind-r2"] = (work / "blind_r2" / "app" / "tool" / "cli.py").read_text()

scratch.mkdir(parents=True, exist_ok=True)
paths = {}
for label, cli in programs.items():
    folder = scratch / label
    folder.mkdir(exist_ok=True)
    for name in ("README.md", "schema.json"):
        (folder / name).write_bytes(zipfile.ZipFile(tool_zip).read(name))
    (folder / "cli.py").write_text(cli)
    paths[label] = folder / "cli.py"

for name in [name for family in (sys.argv[5:] or module.REPAIR_FAMILIES) for name in module.REPAIR_CORPORA[family]]:
    corpus = module.write_corpus(name)
    want = module.reference_repair(name)
    files, rows, stored = module.build_variant(name)
    spare = module.spare_seqs(rows)
    sizes = {tenant: sum(1 for row in rows if row["tenant"] == tenant and int(row["seq"]) in spare) for tenant in want}
    for label, path in paths.items():
        out = scratch / f"out-{name}-{label}"
        out.mkdir(exist_ok=True)
        start = time.time()
        try:
            proc = subprocess.run([sys.executable, "-I", str(path), "resolve", "--data-dir", str(corpus), "--out", str(out)],
                                  capture_output=True, text=True, timeout=60)
            seconds, rc = time.time() - start, proc.returncode
        except subprocess.TimeoutExpired:
            seconds, rc = time.time() - start, "TIMEOUT"
        doc = out / "ledger_repair.json"
        got = json.loads(doc.read_text()) if rc == 0 and doc.exists() else None
        verdict = "TIMEOUT" if rc == "TIMEOUT" else ("no-file" if got is None else ("exact" if got == want else "wrong"))
        print(f"| {name} | spare {sizes} | {label} | {seconds:.2f} | {verdict} |", flush=True)
print("ALL_DONE")
