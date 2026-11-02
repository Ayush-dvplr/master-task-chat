import ast, sys, zlib, base64, io, tarfile, json, os
src = open(sys.argv[1]).read()
dest = sys.argv[2]
tree = ast.parse(src)
vals = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("_EXPECTED_BLOB", "_EXTRACTS"):
        vals[node.targets[0].id] = ast.literal_eval(node.value)
exp = json.loads(zlib.decompress(base64.b64decode(vals["_EXPECTED_BLOB"])))
json.dump(exp, open(os.path.join(dest, "expected.json"), "w"), indent=1, sort_keys=True)
for k, blob in vals["_EXTRACTS"].items():
    raw = zlib.decompress(base64.b64decode(blob))
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        names = tf.getnames()
        tf.extractall(os.path.join(dest, k))
    print(k, len(names), names[:3])
