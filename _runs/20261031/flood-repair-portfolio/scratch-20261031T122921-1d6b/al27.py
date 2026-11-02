import sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import test_output as t
for name in ("H1","H2","H3","M","SHIPPED"):
    files = t.book_files(name)
    led = t.ledger(name)
    docs = t.expected(name)
    for fn in ("proposals.csv","permits.csv"):
        lines = files[fn].split("\n")
        empties = [i+1 for i,l in enumerate(lines[:-1]) if l.strip()==""]
        print(name, fn, "physical lines", len(lines)-1, "empty at physical line(s)", empties)
    faults = docs["data_quality.json"]["rejected"]
    after = [f for f in faults if f["file"] in ("proposals.csv","permits.csv") and f["row"] > 50]
    print(name, "faults", len(faults), "in proposals/permits with row>50:", [(f["round"],f["code"],f["file"],f["row"]) for f in after])
