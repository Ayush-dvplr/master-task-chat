import sys
sys.path.insert(0, sys.argv[1])
import importlib.util
spec = importlib.util.spec_from_file_location("t", sys.argv[2] + "/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for name in ["HELD_EVERY","HELD_PUBLISHED"]:
    seed, legacy = getattr(t, name)
    root = t._held_corpus(seed, legacy)
    print(name, {f.name: f.read_text(errors="ignore").count("OLD-") for f in sorted(root.iterdir()) if f.suffix in (".csv",".psv",".tsv",".jsonl",".ndjson",".json")})
