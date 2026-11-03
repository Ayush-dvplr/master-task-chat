#!/usr/bin/env python3
"""Layer A: feature table for the teammate tasks (no AI). Reads origin/main via git. Writes FEATURES.csv and LOST_CHECKS.csv."""
import subprocess, json, re, csv, os, collections
REF="origin/main"; ROOT="anubis-stage-2"; OUT=os.path.dirname(os.path.abspath(__file__))
SKIP={"337a1262","42e79476","8fbe0e42","b47fd5f7","b5c7b14c"}  # Ayush's own tasks
def git(*a): return subprocess.run(["git",*a],capture_output=True,text=True).stdout
def show(p):
    r=subprocess.run(["git","show",f"{REF}:{p}"],capture_output=True)
    return r.stdout.decode("utf-8","replace") if r.returncode==0 else None
tree=collections.defaultdict(list)
for line in git("ls-tree","-r","-l",REF,ROOT).splitlines():
    meta,path=line.split("\t",1); sz=meta.split()[3]; parts=path.split("/")
    if len(parts)>=3: tree[parts[1]].append((parts[2:],int(sz) if sz.isdigit() else 0))
PHR={"exact_match_bar":r"only an exact match|graded whole|exact(ly)? match",
     "runtime_sentence":r"\b(seconds|minutes|time limit|within \d+|runtime|run time)\b",
     "unseen_data":r"\b(unseen|hidden|held[- ]out|other (inputs|estates|data)|new inputs|any input)\b",
     "standard_named":r"\b(standard|specification|spec|RFC|ISO|format)\b",
     "leave_time_sentence":r"leave enough of that time",
     "program_deliverable":r"\b(program|script|tool|cli)\b.*\b(write|ship|deliver|produce)",
     "honest_report":r"\b(final (reply|response|report)|report (honestly|what))"}
rows=[]; lost_rows=[]
for t in sorted(tree):
    if t[:8] in SKIP: continue
    files=tree[t]; base=f"{ROOT}/{t}"
    ins=show(f"{base}/instruction.md") or ""
    if not ins: continue
    row={"task":t[:8]}
    row["instruction_words"]=len(ins.split())
    for k,p in PHR.items(): row["ins_"+k]=1 if re.search(p,ins,re.I) else 0
    row["ins_output_paths"]=len(set(re.findall(r"/app/out/[\w./-]+",ins)))
    env=[(p,s) for p,s in files if p[0]=="environment"]
    row["env_files"]=len(env); row["env_docs"]=sum(1 for p,_ in env if len(p)>1 and p[1]=="docs")
    row["env_data_kb"]=sum(s for p,s in env if len(p)>1 and p[1]=="data")//1024
    ext=collections.Counter(os.path.splitext(p[-1])[1].lower() or "(none)" for p,_ in env if len(p)>1 and p[1] in("data","docs"))
    row["env_formats"]=len(ext); row["env_top_formats"]=" ".join(f"{e}:{n}" for e,n in ext.most_common(5))
    tst=[(p,s) for p,s in files if p[0]=="tests"]
    row["tests_files"]=len(tst); row["tests_kb"]=sum(s for _,s in tst)//1024
    row["tests_data_files"]=sum(1 for p,_ in tst if len(p)>2)
    judge=show(f"{base}/tests/judge.toml") or ""
    row["judge_trajectory_criteria"]=len(re.findall(r'evaluation_target\s*=\s*"trajectory"',judge))
    row["judge_output_criteria"]=len(re.findall(r'evaluation_target\s*=\s*"(output|artifact|outputs|file)',judge))
    rd=show(f"{base}/trajectories/claude-opus-5/run_1/verifier/reward-details.json")
    ps=show(f"{base}/trajectories/claude-opus-5/pass_summary.json")
    try: s=json.loads(ps); row["opus_tests"]=s["average_test_weights_percentage"]; row["opus_rubric"]=s["average_rubric_weights_percentage"]; row["opus_final"]=s["average_combined_score"]
    except Exception: row["opus_tests"]=row["opus_rubric"]=row["opus_final"]=""
    try: d=json.loads(rd)
    except Exception: d=None
    comps={c["name"]:c for c in d["reward"]["components"]} if d else {}
    for name,key in (("test_output","t"),("judge","j")):
        crit=comps.get(name,{}).get("detail",{}).get("criteria",[]) or []
        pos=[c for c in crit if c.get("weight",0)>0]; neg=[c for c in crit if c.get("weight",0)<0]
        row[f"{key}_checks"]=len(crit); row[f"{key}_pos"]=len(pos); row[f"{key}_neg"]=len(neg)
        row[f"{key}_pos_weight"]=round(sum(c["weight"] for c in pos),2)
        row[f"{key}_pos_lost_weight"]=round(sum(c["weight"]*(1-float(c.get("value") or 0)) for c in pos),2)
        row[f"{key}_neg_fired"]=sum(1 for c in neg if float(c.get("value") or 0)>0)
        row[f"{key}_max_weight"]=max([c["weight"] for c in pos] or [0])
        if key=="t":
            for c in pos:
                lostw=c["weight"]*(1-float(c.get("value") or 0))
                lost_rows.append({"task":t[:8],"check":c.get("name",""),"weight":c["weight"],"value":c.get("value"),"lost_weight":round(lostw,3),"description":(c.get("description") or "")[:200]})
    rows.append(row)
cols=list(rows[0].keys())
for r in rows:
    for c in r:
        if c not in cols: cols.append(c)
with open(os.path.join(OUT,"FEATURES.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
with open(os.path.join(OUT,"LOST_CHECKS.csv"),"w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["task","check","weight","value","lost_weight","description"]); w.writeheader(); w.writerows(lost_rows)
print(len(rows),"tasks;",len(lost_rows),"positive test checks")
