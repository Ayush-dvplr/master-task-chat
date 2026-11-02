# (task, Pt, Pj, [(channel, lost_weight, cause, family)]) from tasks/<NN>_*.md steps 4-6
T=[
("01",90,39,[("t",87,"rules withheld, not recovered","NEW-oracle"),("j",33,"rules withheld, not recovered","NEW-oracle"),("j",3,"code-quality criterion","judge-style")]),
("02",96,72,[("t",90,"rules withheld, not recovered","NEW-oracle"),("j",64,"rules withheld, not recovered","NEW-oracle"),("j",3,"stated conduct rule not followed","judge-conduct"),("j",1,"code-quality criterion","judge-style")]),
("03",93,43,[("t",83,"rules withheld, not recovered","NEW-oracle"),("j",36,"rules withheld, not recovered","NEW-oracle"),("j",3,"stated conduct rule not followed","judge-conduct"),("j",3,"code-quality criterion","judge-style")]),
("04",94,78,[("t",67,"two documented rules combined wrongly","A+B"),("t",8,"two documented rules combined wrongly","A+B"),("t",4,"output format (unstated JSON whitespace)","NEW-format"),("j",49,"two documented rules combined wrongly","A+B"),("j",20,"model refusal / omitted figures","other"),("j",3,"code-quality criterion","judge-style")]),
("05",88,69,[("t",74,"documented rule misapplied (missed 1 of 20 defects)","C+B"),("j",61,"documented rule misapplied (missed 1 of 20 defects)","C+B"),("j",1,"noisy zero-mismatch criterion","judge-conduct")]),
("06",94,77,[("t",78,"grader design: bit positions unidentifiable","NEW-design"),("t",10,"rules withheld, not recovered","NEW-oracle"),("j",41,"rules withheld, not recovered","NEW-oracle"),("j",1,"stated conduct rule not followed","judge-conduct"),("j",3,"code-quality criterion","judge-style")]),
("07",51,17,[("t",43,"grader runtime: program unreadable to dropped uid (SUSPECT)","NEW-harness"),("j",6,"judge probes not asked in instruction","judge-narration"),("j",5,"honesty negative (unsupported claim)","judge-honesty")]),
("08",139,19,[("t",55,"grader runtime: program unreadable to dropped uid (SUSPECT)","NEW-harness"),("t",81,"documented rule misapplied (inverted cross-file field)","A+cascade"),("j",9,"stated conduct rule not followed","judge-conduct")]),
("09",85,72,[("t",67,"grader runtime: program unreadable to dropped uid (SUSPECT)","NEW-harness"),("t",5,"grader runtime: program unreadable to dropped uid (SUSPECT)","NEW-harness"),("j",38,"judge probes not asked in instruction","judge-narration"),("j",3,"code-quality criterion","judge-style")]),
("10",62,79,[("t",57,"two documented rules combined wrongly","A+B"),("j",37,"judge probes not asked in instruction","judge-narration"),("j",1,"stated conduct rule not followed","judge-conduct"),("j",1,"code-quality criterion","judge-style")]),
]
overall={"01":5.51,"02":5.90,"03":6.54,"04":11.83,"05":13.03,"06":23.97,"07":25.49,"08":27.40,"09":29.18,"10":29.35}
from collections import defaultdict
C=defaultdict(float);F=defaultdict(float);tot=0
for nn,pt,pj,items in T:
    s=0
    for ch,w,c,f in items:
        pp=50*w/(pt if ch=="t" else pj); s+=pp; C[c]+=pp; F[f]+=pp
    print(nn,"lost",round(s,2),"expected",round(100-overall[nn],2))
    tot+=s
print("total",round(tot,1))
for k,v in sorted(C.items(),key=lambda x:-x[1]): print(f"{v:6.1f}  {k}")
print()
for k,v in sorted(F.items(),key=lambda x:-x[1]): print(f"{v:6.1f}  {k}")
