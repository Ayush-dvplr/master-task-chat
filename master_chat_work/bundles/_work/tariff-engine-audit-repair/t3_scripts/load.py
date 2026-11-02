"""Load the WORK test source as a module with the rewardkit stub (authoring helper)."""
import importlib.util, os, sys
from pathlib import Path
WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
def load(path=None):
    sys.path.insert(0, str(WORK / "rewardkit_stub"))
    os.environ.setdefault("APP_ROOT", "/tmp/nonexistent_app")
    p = Path(path or BUNDLE / "tests" / "test_output.py")
    spec = importlib.util.spec_from_file_location("bundle_tests", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
