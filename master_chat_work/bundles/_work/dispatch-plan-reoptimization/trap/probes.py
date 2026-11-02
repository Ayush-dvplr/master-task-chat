#!/usr/bin/env python3
"""Focused author-side probes for the P12 r3 verifier changes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT.parents[1] / "dispatch-plan-reoptimization"
fake = types.ModuleType("rewardkit")
fake.criteria = type("Register", (), {"__getattr__": lambda self, n: lambda **kw: None})()
fake.criterion = lambda **kw: lambda fn: fn
sys.modules["rewardkit"] = fake
os.environ["APP_ROOT"] = "/nonexistent"
spec = importlib.util.spec_from_file_location("probe_target", BUNDLE / "tests/test_output.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
results = {}

with tempfile.TemporaryDirectory(prefix="dpr-probes-") as tmp:
    tmp = Path(tmp)
    data = tmp / "data"
    data.mkdir()
    out = tmp / "out"
    program = tmp / "solver.py"
    t.SOLVER = program

    program.write_text("import json,os,sys\nfrom pathlib import Path\n"
                       "Path(sys.argv[2], 'env.json').write_text(json.dumps(dict(os.environ)))\n")
    result = t._run_solver(data, out, env={"OPENAI_API_KEY": "probe", "MY_SECRET": "probe",
                                           "X_TOKEN": "probe", "PASSWORD": "probe",
                                           "TMPDIR": str(tmp)}, tag="env")
    env = json.loads((out / "env.json").read_text()) if result else {}
    results["env"] = {"ran": result, "OPENAI_API_KEY": "OPENAI_API_KEY" in env,
                      "secret_names": sorted(k for k in env if any(x in k.upper() for x in
                                                 ("KEY", "TOKEN", "SECRET", "PASSWORD"))),
                      "PATH": "PATH" in env, "LANG": "LANG" in env,
                      "TMPDIR": env.get("TMPDIR") == str(tmp)}
    results["types"] = {"true_vs_1": t._same_value(True, 1),
                        "1_vs_1.0": t._same_value(1, 1.0),
                        "dict_key_order": t._same_value({"a": 1, "b": 2}, {"b": 2, "a": 1})}
    program.write_text("# shipped total 446527364\nprint('446527364')\n")
    results["comment_total_penalized"] = t._hardcodes_sample_answers(program.read_text())
    results["unsorted_json_matches"] = t._artifact_matches(
        "objective.json", b'{\n "b": 2,\n "a": 1\n}\n',
        b'{\n "a": 1,\n "b": 2\n}\n')

    cases = {
        "outside_read": "open('/etc/hosts').read()\n",
        "transient_outside_write": "from pathlib import Path\nimport os\np=Path(os.environ['TMPDIR'])/'transient'\np.write_text('x')\np.unlink()\n",
        "nonstdlib_import": "from pathlib import Path\nimport sys\nq=Path(sys.argv[2]); (q/'probe_extra.py').write_text('x=1\\n')\nsys.path.insert(0,str(q))\nimport probe_extra\n",
        "asyncio_child": "import asyncio\nasync def go():\n p=await asyncio.create_subprocess_exec(sys.executable,'-c','pass')\n await p.wait()\nasyncio.run(go())\n",
        "socket": "import socket\ns=socket.socket()\ns.close()\n",
    }
    for name, body in cases.items():
        program.write_text("import sys\n" + body)
        this_out = tmp / ("out_" + name)
        ok = t._run_solver(data, this_out, env={"TMPDIR": str(tmp)}, tag=name)
        events = t._AUDITS.get(name, [])
        t._RUNS["H1"] = {} if ok else None
        t._AUDITS["H1"] = events
        hits = [check for check, fn in [
            ("negative_reads_outside_input_dir", t.negative_reads_outside_input_dir),
            ("negative_network_dependency_or_shell_cheat", t.negative_network_dependency_or_shell_cheat),
            ("negative_writes_outside_output_dir", t.negative_writes_outside_output_dir),
        ] if (check != "negative_writes_outside_output_dir" or name == "transient_outside_write")
             and fn(tmp)]
        results[name] = {"ran": ok, "events": events, "criteria_hit": hits}

    shutil.copy2(ROOT / "trap/variants/oracle.py", program)
    for name in ["shipped", "H1", "H2", "H3", "H4"]:
        d = tmp / ("data_" + name)
        t._write_corpus(name, d)
        ok = t._run_solver(d, tmp / ("oracle_" + name), tag="oracle_" + name)
        results["oracle_" + name] = {"ran": ok,
                                     "events": len(t._AUDITS.get("oracle_" + name, []))}

(ROOT / "trap/probe_results.json").write_text(json.dumps(results, indent=2) + "\n")
for name, value in results.items():
    if isinstance(value, dict) and "events" in value and isinstance(value["events"], list):
        print(name, value["ran"], [(e["kind"], e["event"]) for e in value["events"]])
    else:
        print(name, value)
