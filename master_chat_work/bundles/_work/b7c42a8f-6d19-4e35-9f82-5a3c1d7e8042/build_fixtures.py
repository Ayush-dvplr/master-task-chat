"""Write _EXPECTED_BLOB and _EXTRACTS into a test_output.py from seal json files and extract dirs."""
import base64, io, json, re, sys, tarfile, zlib
from pathlib import Path

src, seal_dir, ext_dir, dst = (Path(a) for a in sys.argv[1:5])
blob = {}
for corpus in ("shipped", "A", "B"):
    seal = json.loads((seal_dir / ("seal_%s.json" % corpus)).read_text())
    blob[corpus] = {"digests": seal["digests"], "scalars": seal["scalars"], "audit": seal["audit"]}
enc = lambda raw: base64.b64encode(zlib.compress(raw, 9)).decode()
blob_text = enc(json.dumps(blob, sort_keys=True, separators=(",", ":")).encode())

def tar_of(directory):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for path in sorted(directory.iterdir()):
            data = path.read_bytes()
            info = tarfile.TarInfo(path.name)
            info.size = len(data); info.mode = 0o644; info.mtime = 0
            info.uid = info.gid = 0; info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()

text = src.read_text()
text, n1 = re.subn(r"^_EXPECTED_BLOB = '[^']*'$", "_EXPECTED_BLOB = '%s'" % blob_text, text, flags=re.M)
n2 = 0
for corpus in ("A", "B"):
    text, k = re.subn(r"^    '%s': '[^']*',$" % corpus, "    '%s': '%s'," % (corpus, enc(tar_of(ext_dir / corpus))), text, flags=re.M)
    n2 += k
assert n1 == 1 and n2 == 2, (n1, n2)
dst.write_text(text)
print("fixtures written", len(blob_text))
