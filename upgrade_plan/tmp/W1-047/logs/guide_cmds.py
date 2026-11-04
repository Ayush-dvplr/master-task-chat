"""guide_cmds.py GUIDE KEY: print the command lines (4 space indent) of one step of the INSTALL guide,
with /Users/mac/Desktop mapped to E2/Desktop and SLUG to cold-chain-backbone-quote. KEY list: prints all keys."""
import re, sys
guide, key = sys.argv[1], sys.argv[2]
E2 = "/tmp/claude-0/-home-user-master-task-chat/f6261faa-e14c-531f-ac91-5ae19865d520/scratchpad/e2e2"
cur, top, out = None, None, {}
for line in open(guide, encoding="utf-8").read().splitlines():
    m = re.match(r"^(\d+)\. ", line)
    if m:
        top = cur = m.group(1); continue
    m = re.match(r"^   (\d+\.\d+) ", line)
    if m:
        cur = m.group(1); continue
    m = re.match(r"^   (\d+)\. ", line)
    if m and top:
        cur = f"{top}.{m.group(1)}" if "." not in (cur or "") or cur.startswith(top + ".") and cur.count(".") == 1 and False else cur
        if "." not in cur:
            cur = f"{top}.{m.group(1)}"
        elif cur.split(".")[0] == top and re.match(r"^   \d+\. ", line) and cur.count(".") == 1 and top in ("7", "12"):
            cur = f"{top}.{m.group(1)}"
        continue
    if line.startswith("    ") and cur:
        cmd = line[4:].replace("/Users/mac/Desktop", E2 + "/Desktop").replace("https://github.com/Ayush-dvplr/master-task-chat.git", E2 + "/github.git")
        cmd = re.sub(r"\bSLUG\b", "cold-chain-backbone-quote", cmd)
        out.setdefault(cur, []).append(cmd)
if key == "list":
    for k, v in out.items():
        print(k, len(v))
else:
    print("\n".join(out.get(key, [])))
