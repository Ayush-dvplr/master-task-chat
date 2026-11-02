import sys, collections, copy
import gen, rec
VARS = {
 "B1_commit_filter": {"commit_filter":1},
 "B2_no_clr_redo": {"no_clr_redo":1},
 "B3_redo_ge": {"redo_ge":1},
 "B4_per_txn": {"per_txn_order":1},
 "B5_prev_walk": {"prev_walk":1},
 "B6_redo_from_ckpt": {"redo_from_ckpt":1},
 "B7_textbook_end": {"textbook_end":1},
 "B8_scan_from_end": {"analysis_from_end":1},
 "B9_end_no_lsn": {"end_no_lsn":1},
 "B10_latest_ckpt": {"latest_ckpt":1},
 "B12_one_hop": {"one_hop":1},
 "B13_undo_next_resolved": {"undo_next_resolved":1},
 "B15_per_record_redo": {"per_record_redo":1},
 "B16_eager_pagelsn": {"eager_pagelsn":1},
}
def feats(img, res):
    R={r["lsn"]:r for r in img["records"]}
    f=collections.Counter()
    for r in img["records"]:
        if r["type"]=="clr" and r["undo_next"] is not None and R[r["undo_next"]]["type"]=="clr": f["clr_to_clr"]+=1
    return f
prof=sys.argv[1]; nimg=int(sys.argv[2]); seeds=[int(x) for x in sys.argv[3].split(",")]
for seed in seeds:
    b=gen.build_book(seed, prof, nimg)
    ref=rec.docs(copy.deepcopy(b))
    fc=collections.Counter()
    for img in b["images"]:
        fc.update(feats(img,None)); fc["nres"]+=img["nres"]
    row=[]
    for name,f in VARS.items():
        d=rec.docs(copy.deepcopy(b), f)
        lost=[k for k in ("core","metrics","dep","summary") if d[k]!=ref[k]]
        nimg_bad=sum(1 for i in ref["core"] if d["core"][i]!=ref["core"][i])
        row.append(f"{name}:{''.join(k[0] for k in lost) or '-'}({nimg_bad})")
    print(prof, seed, dict(fc), " ".join(row))
