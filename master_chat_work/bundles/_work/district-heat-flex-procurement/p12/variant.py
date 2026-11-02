"""Agent-program stand-in: writes the test reference with one wrong-reading flag. Usage: variant.py DATA OUT
Flag from env VARIANT_FLAG; test module from env VARIANT_TESTS."""
import importlib.util, json, os, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, "/k/stub")
spec = importlib.util.spec_from_file_location("tmod", os.environ["VARIANT_TESTS"])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
flags = frozenset(filter(None, os.environ.get("VARIANT_FLAG", "").split(",")))
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for name, payload in sorted(m.reference(Path(sys.argv[1]), flags).items()):
    (out / name).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
