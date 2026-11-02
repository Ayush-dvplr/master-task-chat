import json, os, sys

sv, inst, ref, out, rc, sec = sys.argv[1:7]
r = json.load(open(ref))
if rc != "0" or not os.path.exists(out):
    verdict = "TIMEOUT" if rc in ("142", "-14") else "CRASH"
    print("ROW", sv, inst, sec, verdict, "kept 0/%d" % len(r["fam"]), "rc", rc)
    sys.exit(0)
o = json.load(open(out))
same = [k for k in r["fam"] if r["fam"][k] == o["fam"].get(k)]
diff = [k for k in r["fam"] if k not in same]
verdict = "EXACT" if not diff else "WRONG"
print("ROW", sv, inst, sec, verdict, "kept %d/%d" % (len(same), len(r["fam"])),
      "obj", o["obj"], "ref", r["obj"], "firstdiff", diff[:1])
