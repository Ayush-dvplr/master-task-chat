import sys, shutil, json
from pathlib import Path
sys.path.insert(0, "/w/harness")
import rk
rk.load("/b/tests")
neg_net = rk.REG["negative_module_opens_network_or_shells_out"]
neg_extra = rk.REG["negative_output_directory_holds_extra_files"]
base = Path("/w/runs/trap_v3_after/ws_oracle")
res = {}
def ws_with(src_extra=None, extra_file=None, tag="x"):
    ws = Path("/tmp/hyg_" + tag); shutil.rmtree(ws, ignore_errors=True)
    shutil.copytree(base, ws)
    if src_extra is not None:
        p = ws / "out" / "reserving.py"; p.write_text(src_extra + "\n" + p.read_text())
    if extra_file:
        (ws / "out" / extra_file).write_text("x")
    return ws
res["oracle_net"] = neg_net(ws_with(tag="o"))
res["oracle_extra"] = neg_extra(ws_with(tag="o2"))
for tag, line in [("numpy", "import numpy"), ("pandas_from", "from pandas import DataFrame"), ("relative", "from . import helper"), ("socket", "import socket"), ("json_ok", "import json"), ("os_path_ok", "from os import path")]:
    res["net_" + tag] = neg_net(ws_with(src_extra=line, tag=tag))
res["extra_notes"] = neg_extra(ws_with(extra_file="notes.txt", tag="e1"))
res["extra_pycache"] = neg_extra(ws_with(extra_file="__pycache__", tag="e2"))
print(json.dumps(res))
