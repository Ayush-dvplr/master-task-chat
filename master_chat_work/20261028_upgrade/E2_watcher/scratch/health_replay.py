"""Drive the module's real watch_once with worker health F,T,T,F,F,T (net down so nothing is delivered)."""
import importlib.util, sys, tempfile
from datetime import timedelta
from pathlib import Path
spec = importlib.util.spec_from_file_location("a", sys.argv[1]); a = importlib.util.module_from_spec(spec)
sys.modules["a"] = a; spec.loader.exec_module(a)
a.use_run(Path(tempfile.mkdtemp(prefix="E2-replay-")) / "run").dir.mkdir()
pat = iter([False, True, True, False, False, True])
a.healthy = lambda u: next(pat) if u == "http://w" else True
a.net_up = lambda: False
for f in ("poll_workers", "poll_harness", "check_limit", "write_hold", "notify"):
    setattr(a, f, lambda *x, **k: None)
st = {"worker_url": "http://w", "master_url": "http://m", "events": [], "stopping": False, "workers": {},
      "retries": {}, "started": a.ts(), "until": (a.now() + timedelta(hours=2)).isoformat(timespec="minutes")}
for i, h in enumerate("FTTFFT"):
    n = len(st["events"]); a.watch_once(st)
    print(f"poll{i} health={h} new events: {[e[:70] for e in st['events'][n:]]}")
print("worker_down_reported at end:", st.get("worker_down_reported"))
