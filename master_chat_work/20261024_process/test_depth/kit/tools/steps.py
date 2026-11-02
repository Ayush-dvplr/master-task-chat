import json, sys
d = json.load(open(sys.argv[1]))
w = int(sys.argv[2]) if len(sys.argv) > 2 else 220
for s in d["steps"]:
    msg = (s.get("message") or "").replace("\n", " ")[:120]
    calls = []
    for c in s.get("tool_calls") or []:
        a = c.get("arguments", {})
        x = a.get("command") or a.get("path") or json.dumps(a)
        if isinstance(x, str):
            x = x.replace("\n", " \\n ")
        calls.append("%s:%s" % (c["function_name"], str(x)[:w]))
    print(s["step_id"], s["source"], "|", msg, "|", " ;; ".join(calls))
