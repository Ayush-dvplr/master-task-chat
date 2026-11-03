#!/usr/bin/env python3
"""Option (b), no AI: flag teammate tasks that look like DEFECT cases.
Signals: (1) dict keys written by the reference solve.py that appear in no shipped text (instruction, environment docs and data text files);
(2) TRUTH.md sentences admitting a rule is undocumented or hidden only. Writes TRIAGE.csv. Validated against verified cards."""
import subprocess, re, csv, os, collections
REF="origin/main"; ROOT="anubis-stage-2"; OUT=os.path.dirname(os.path.abspath(__file__))
SKIP={"337a1262","42e79476","8fbe0e42","b47fd5f7","b5c7b14c"}
TEXT=(".md",".txt",".json",".yaml",".yml",".csv",".toml",".jsonl",".sql",".xml",".html",".ini",".cfg")
def git(*a): return subprocess.run(["git",*a],capture_output=True,text=True).stdout
def show(p):
    r=subprocess.run(["git","show",f"{REF}:{p}"],capture_output=True)
    return r.stdout.decode("utf-8","replace") if r.returncode==0 else ""
files=collections.defaultdict(list)
for line in git("ls-tree","-r","-l",REF,ROOT).splitlines():
    meta,path=line.split("\t",1); sz=meta.split()[3]; parts=path.split("/")
    if len(parts)>=3: files[parts[1]].append((path,int(sz) if sz.isdigit() else 0))
ADMIT=re.compile(r"(undocumented|not documented|no (document|doc|file) (says|states|mentions)|never (says|states|stated)|hidden (lever|rule)|only the hidden|not stated|unstated|does not say)",re.I)
rows=[]
for t,fl in sorted(files.items()):
    if t[:8] in SKIP: continue
    base=f"{ROOT}/{t}"
    shipped=show(f"{base}/instruction.md")
    for p,sz in fl:
        rel=p[len(base)+1:]
        if rel.startswith("environment/") and p.lower().endswith(TEXT) and sz<3_000_000: shipped+="\n"+show(p)
    sol=show(f"{base}/solution/solve.py")
    keys=set(re.findall(r'["\']([a-z][a-z0-9]*(?:_[a-z0-9]+)+)["\']\s*:',sol))
    missing=sorted(k for k in keys if k not in shipped)
    truth=show(f"{base}/solution/TRUTH.md")
    admits=[m.group(0) for m in ADMIT.finditer(truth)]
    rows.append({"task":t[:8],"solution_keys":len(keys),"keys_not_in_shipped_text":len(missing),
                 "missing_share":round(len(missing)/len(keys),2) if keys else "",
                 "missing_examples":" ".join(missing[:6]),"truth_admits":len(admits),"truth_admit_words":" | ".join(sorted(set(a.lower() for a in admits))[:4])})
with open(os.path.join(OUT,"TRIAGE.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows),"tasks")
