"""Parse kill_l1 logs into lever / non-lever loss with failure kinds."""
import json, re, sys
LEVER = {"wide_1_core", "wide_2_core", "wide_3_core", "wide_books_report", "wide_books_summary", "wide_networks_feasible"}
rows = {}
for path in sys.argv[1:]:
    cur = None
    for line in open(path):
        m = re.match(r"=== (\S+) ", line)
        if m:
            cur = m.group(1); rows[cur] = {"fails": [], "msgs": []}; continue
        if cur is None: continue
        m = re.match(r"(\S+)\s+w=\s*(-?\d+) (PASS|fail)", line)
        if m and int(m.group(2)) > 0 and m.group(3) == "fail":
            rows[cur]["fails"].append((m.group(1), int(m.group(2))))
        elif line.startswith("SCORE"):
            rows[cur]["score"] = line.split()[1]
        elif re.search(r"exit|Error|differs|No such|missing|rejected", line):
            rows[cur]["msgs"].append(line.strip()[:150])
out = {}
for v, r in rows.items():
    lev = sum(w for n, w in r["fails"] if n in LEVER)
    non = sum(w for n, w in r["fails"] if n not in LEVER)
    kinds = set()
    for m in r["msgs"]:
        kinds.add("TIMEOUT" if "timed out" in m else "CRASH" if ("No such" in m or "Error" in m and "Assertion" not in m) else "WRONG")
    out[v] = {"score": r.get("score"), "lever_lost": lev, "nonlever_lost": non,
              "nonlever_checks": [n for n, w in r["fails"] if n not in LEVER], "kinds": sorted(kinds)}
    print(v, out[v]["score"], "lever", lev, "non", non, out[v]["kinds"], out[v]["nonlever_checks"])
json.dump(out, open("runs/kill_l1_parsed.json", "w"), indent=1)
