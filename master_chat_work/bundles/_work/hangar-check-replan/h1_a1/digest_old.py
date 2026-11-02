"""Compare every top-level def/assignment of pre_build tests/test_output.py with the built file (text only)."""
import ast, hashlib, sys
def parts(path):
    src = open(path).read(); tree = ast.parse(src); out = {}
    for n in tree.body:
        seg = ast.get_source_segment(src, n)
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): key = n.name
        elif isinstance(n, ast.Assign): key = "=" + ",".join(ast.unparse(t) for t in n.targets)
        elif isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Call): key = "call:" + seg
        else: key = type(n).__name__ + ":" + seg[:60]
        out[key] = hashlib.sha256(seg.encode()).hexdigest()[:12]
    return out
a, b = parts(sys.argv[1]), parts(sys.argv[2])
same = [k for k in a if k in b and a[k] == b[k]]
changed = [k for k in a if k in b and a[k] != b[k]]
gone = [k for k in a if k not in b]
new = [k for k in b if k not in a]
print("same %d changed %d removed %d added %d" % (len(same), len(changed), len(gone), len(new)))
for k in changed: print("CHANGED", k[:110])
for k in gone: print("REMOVED", k[:110])
for k in new: print("ADDED", k[:110])
