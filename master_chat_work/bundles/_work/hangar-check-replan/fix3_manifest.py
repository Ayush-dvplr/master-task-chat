import hashlib
import json
import ast
import base64
import zlib
from pathlib import Path

work = Path(__file__).parent
before = work / "fix3_pre"
bundle = work.parent.parent / "hangar-check-replan"

def manifest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}

pre, post = manifest(before), manifest(bundle)
(work / "fix3_pre_digests.json").write_text(json.dumps(pre, indent=2) + "\n")
for name in pre:
    if name.startswith("environment/") or name in {"instruction.md", "task.toml", "solution/solve.py"}:
        assert pre[name] == post[name], name
print("UNCHANGED environment, instruction, resources, solve.py; pre manifest", len(pre))
tree = ast.parse((bundle / "tests/test_output.py").read_text())
docs = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_GOVERNING_DOCS" for t in n.targets))
for name, blob in docs.items():
    assert zlib.decompress(base64.b64decode(blob)) == (bundle / "environment/data/docs" / name).read_bytes()
print("DOCS_BYTE_IDENTICAL", 6)
