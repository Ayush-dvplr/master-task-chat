"""Time the delivered package CLI per book (oracle timing for TRUTH.md). Run in the verifier image with APP_ROOT=/app."""
import importlib.util, json, sys, time
spec = importlib.util.spec_from_file_location("tt", sys.argv[1])
tt = importlib.util.module_from_spec(spec); spec.loader.exec_module(tt)
rows = {}
names = sys.argv[2].split(",") if len(sys.argv) > 2 else ("fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "rejections", "ties") + tt.WIDE_BOOKS + tt.HELD_WIDE_BOOKS
for name in names:
    book = tt._book(name)
    n = tt._book_projects(book)
    t0 = time.perf_counter()
    r, _ = tt._run_cli(book, n, isolated=name == "relocated")
    cli = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    tt._expected(name)
    rows[name] = [n, 4 * n + 10, cli, r.returncode, round(time.perf_counter() - t0, 2)]
    print(name, rows[name], flush=True)
print(json.dumps(rows))
