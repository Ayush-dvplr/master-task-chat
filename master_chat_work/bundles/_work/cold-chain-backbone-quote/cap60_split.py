"""Cap-60 kill table helper: lost points (lever = wide_* checks) and the kinds of failure messages in a
run_local_tests log. stdout and stderr interleave out of order in these logs, so the WRONG / TIMEOUT / CRASH
point split is read from the message kinds: 'timed out' = TIMEOUT, bare 'exit -9:' = CRASH (memory kill),
anything else (documents differ, missing key, bad exit) = WRONG. Each book run is memoised, so every check
reading a book repeats that book's message."""
import collections, re, sys
for path in sys.argv[1:]:
    lines = open(path, errors="replace").read().splitlines()
    lost = collections.Counter()
    kinds = collections.Counter()
    score = ""
    for ln in lines:
        m = re.match(r"^(\S+)\s+w=\s*(-?\d+)\s+(PASS|fail)", ln)
        if m:
            name, w, st = m.group(1), int(m.group(2)), m.group(3)
            if st == "fail" and w > 0:
                lost["lever" if name.startswith("wide_") else "other"] += w
            if st == "PASS" and w < 0:
                lost["negative_fired:" + name] += w
        elif ln.startswith("SCORE"):
            score = ln
        elif ln.startswith("_check"):
            k = "T" if "timed out" in ln else ("C" if re.search(r"exit -9: *$", ln) else "W")
            kinds[k] += 1
    print(path.split("/")[-1], "|", score, "| lost", dict(lost), "| message kinds", dict(kinds))
