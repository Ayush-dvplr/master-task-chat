"""Score the harden_r2 (probe-1) agent program (read only): its out/ with tool.zip cli.py swapped for adapted/cli.py.

Usage: reflex_score.py [original|build] [data_src]   (env SPR_TESTS picks the tests file)
  default: agent out/ with tool.zip cli.py swapped for adapted/cli.py
  original: agent out/ as delivered
  build: run the agent's build/build.py with adapted/cli.py on data_src/environment/data (default BUNDLE) into a fresh out
"""
import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
AGENT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_sentinel-policy-recompute/harden_r2/agent_program")
root = Path("/var/folders/13/lkwk3zl54tvf9xz694_t4rvm0000gn/T/opencode/spr_p12/reflex")
if root.exists():
    shutil.rmtree(root)
shutil.copytree(AGENT / "out", root / "app" / "out")
if "build" in sys.argv[1:]:
    data_src = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute")
    shutil.rmtree(root)
    app = root / "app"
    shutil.copytree(data_src / "environment" / "data", app / "data")
    shutil.copytree(AGENT / "tool", app / "tool")
    shutil.copy(AGENT / "adapted" / "cli.py", app / "tool" / "cli.py")
    if not (app / "data" / "decoy_alias_table.jsonc").exists():
        cli = app / "tool" / "cli.py"
        cli.write_text(cli.read_text().replace("decoy_alias_table.jsonc", "principal_alias_table.jsonc"))
    (app / "build").mkdir()
    if (AGENT / "build" / "sentinel-ctl").exists():
        launcher = app / "sentinel-ctl"
        launcher.write_text((AGENT / "build" / "sentinel-ctl").read_text().replace('"/app/', '"' + str(app) + '/').replace("#!/usr/bin/env python3", "#!" + sys.executable))
        launcher.chmod(0o755)
    script = (AGENT / "build" / "build.py").read_text().replace('"/app/', '"' + str(app) + '/').replace('"/app"', '"' + str(app) + '"')
    (app / "build" / "build.py").write_text(script)
    run = subprocess.run([sys.executable, str(app / "build" / "build.py")], capture_output=True, text=True, cwd=app)
    print("build exit", run.returncode, run.stderr[-400:])
elif "original" not in sys.argv[1:]:
    with zipfile.ZipFile(AGENT / "out" / "tool.zip") as archive:
        members = [(info, archive.read(info.filename)) for info in archive.infolist()]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for info, data in members:
            archive.writestr(info, (AGENT / "adapted" / "cli.py").read_bytes() if info.filename == "cli.py" else data)
    (root / "app" / "out" / "tool.zip").write_bytes(buffer.getvalue())
out = subprocess.run([sys.executable, str(WORK / "local_score.py"), str(root)], capture_output=True, text=True)
print("\n".join(line for line in out.stdout.splitlines() if " w=" in line or line.startswith("SCORE") or line.startswith("[check] shipped")))
shutil.rmtree(root)
