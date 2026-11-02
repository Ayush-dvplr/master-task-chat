"""Inside Docker: rebuild long-card months with the bundle's own test module and time the installed program.

Usage: python3 time_ladder.py <cap seconds> <kind:k> ...   (kind is ladder or long)
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/t")
import test_output as T  # noqa: E402

cap = float(sys.argv[1])
for spec in sys.argv[2:]:
    kind, k = spec.split(":")
    k = int(k)
    files = T._ladder_files(k) if kind == "ladder" else T._long_files(k)
    expected = T.ref_compute(files)
    work = Path(tempfile.mkdtemp(prefix="time-"))
    src, dst = work / "extract", work / "reports"
    src.mkdir()
    for name, blob in files.items():
        (src / name).write_bytes(blob)
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, "-I", "/app/out/transform.py", "--input", str(src), "--output", str(dst)],
                              cwd=str(work), capture_output=True, text=True, timeout=cap, check=False)
        seconds = time.monotonic() - start
        rc, err = proc.returncode, proc.stderr.strip()[-300:]
    except subprocess.TimeoutExpired:
        seconds, rc, err = time.monotonic() - start, None, "no result within cap %.0f s" % cap
    same = {}
    if rc == 0:
        for name in T.DOCUMENTS:
            try:
                same[name] = T._load(dst, name) == expected[name]
            except Exception as exc:  # report the document as unreadable
                same[name] = "unreadable: %s" % exc
    print("RESULT %s_%d seconds=%.2f rc=%s stderr=%r docs_equal=%s" % (kind, k, seconds, rc, err, same), flush=True)
