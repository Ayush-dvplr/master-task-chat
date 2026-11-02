"""Wrong recovery methods (baselines) for the cost table; flags off == bookgen reference."""
import bookgen as bg

VARS = {
    "B1_commit_filter": {"commit_filter"},
    "B2_no_clr_redo": {"no_clr_redo"},
    "B3_redo_ge": {"redo_ge"},
    "B4_per_txn_order": {"per_txn_order"},
    "B5_prev_walk": {"prev_walk"},
    "B6_redo_from_ckpt": {"redo_from_ckpt"},
    "B7_textbook_end": {"textbook_end"},
    "B8_scan_from_end": {"analysis_from_end"},
    "B9_end_no_lsn": {"end_no_lsn"},
    "B10_latest_ckpt": {"latest_ckpt"},
    "B12_one_hop": {"one_hop"},
    "B13_undo_next_resolved": {"undo_next_resolved"},
    "B15_per_record_redo": {"per_record_redo"},
    "B16_eager_pagelsn": {"eager_pagelsn"},
    "TB_textbook": {"textbook_end", "eager_pagelsn"},
}


def undo_point(R, lsn, f):
    while lsn is not None:
        r = R[lsn]
        if r["type"] == "update":
            return r
        if r["type"] == "clr":
            if "one_hop" in f and r["undo_next"] is not None and R[r["undo_next"]]["type"] == "clr":
                return R[r["undo_next"]]
            lsn = r["prev"] if "prev_walk" in f else r["undo_next"]
        else:
            lsn = r["prev"]
    return None


def analysis(img, f):
    R = {r["lsn"]: r for r in img["records"]}
    order = sorted(R)
    master = img["master"]
    if "latest_ckpt" in f:
        ends = [r for r in img["records"] if r["type"] == "checkpoint_end"]
        master = max(e["begin_lsn"] for e in ends) if ends else 0
    T, D = {}, {}
    scan_from = master
    if master:
        end = [r for r in img["records"] if r["type"] == "checkpoint_end" and r["begin_lsn"] == master][0]
        for t in end["txn_table"]:
            T[t["txn"]] = {"state": t["state"], "last": t["last_lsn"]}
        for d in end["dirty_pages"]:
            D[d["page"]] = d["rec_lsn"]
        if "analysis_from_end" in f:
            scan_from = end["lsn"]
    for lsn in order:
        if lsn < scan_from:
            continue
        r = R[lsn]
        if r["type"] not in bg.TXN_KINDS:
            continue
        if r["type"] == "end":
            T.pop(r["txn"], None)
            continue
        e = T.setdefault(r["txn"], {"state": "running", "last": lsn})
        e["last"] = lsn
        if r["type"] == "commit":
            e["state"] = "committed"
        elif r["type"] == "abort":
            e["state"] = "aborting"
        for ch in r.get("changes", ()):
            D.setdefault(ch["page"], lsn)
    return R, order, T, D, master


def redo(R, order, D, pages, master, f):
    start = min(D.values()) if D else None
    if "redo_from_ckpt" in f and master:
        start = master
    examined = applied = 0
    if start is None:
        return start, 0, 0
    for lsn in order:
        r = R[lsn]
        if lsn < start or r["type"] not in ("update", "clr"):
            continue
        examined += 1
        if r["type"] == "clr" and "no_clr_redo" in f:
            continue

        def ok(p):
            if p not in D or lsn < D[p]:
                return False
            return lsn >= pages[p]["page_lsn"] if "redo_ge" in f else lsn > pages[p]["page_lsn"]
        if "eager_pagelsn" in f:
            for ch in r["changes"]:
                if ok(ch["page"]):
                    pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                    pages[ch["page"]]["page_lsn"] = lsn
                    applied += 1
            continue
        if "per_record_redo" in f:
            todo = {ch["page"] for ch in r["changes"]} if ok(r["changes"][0]["page"]) else set()
        else:
            todo = {ch["page"] for ch in r["changes"] if ok(ch["page"])}
        for ch in r["changes"]:
            if ch["page"] in todo:
                pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                pages[ch["page"]]["page_lsn"] = lsn
                applied += 1
    return start, examined, applied


def appended(R, T, pages, next_lsn, f):
    step = 0 if "end_no_lsn" in f else 1
    out = []

    def end(tx):
        nonlocal next_lsn
        out.append({"lsn": next_lsn, "type": "end", "txn": tx, "prev": T[tx]["last"]})
        next_lsn += step
        del T[tx]

    def clr(tx, u, nxt_point):
        nonlocal next_lsn
        c = {"lsn": next_lsn, "type": "clr", "txn": tx, "prev": T[tx]["last"],
             "changes": [{"page": x["page"], "slot": x["slot"], "delta": -x["delta"]} for x in u["changes"]],
             "undo_next": u["prev"]}
        if "undo_next_resolved" in f:
            c["undo_next"] = nxt_point["lsn"] if nxt_point else None
        next_lsn += 1
        for x in c["changes"]:
            pages[x["page"]]["slots"][x["slot"]] += x["delta"]
            pages[x["page"]]["page_lsn"] = c["lsn"]
        T[tx]["last"] = c["lsn"]
        R[c["lsn"]] = c
        out.append(c)

    winners = [t for t in T if T[t]["state"] == "committed"]
    for tx in (winners if "textbook_end" in f else sorted(winners)):
        end(tx)
    if "per_txn_order" in f:
        for tx in sorted(T):
            u = undo_point(R, T[tx]["last"], f)
            while u is not None:
                nu = undo_point(R, u["prev"], f)
                clr(tx, u, nu)
                u = nu
            end(tx)
        return out
    if "textbook_end" in f:
        # ToUndo keyed by the next LSN to look at; a loser ends when its chain reaches null.
        key = {}
        for tx in T:
            key[tx] = T[tx]["last"]
        while key:
            tx = max(key, key=lambda t: (key[t], -t))
            r = R[key[tx]]
            if r["type"] == "update":
                nu = undo_point(R, r["prev"], f)
                clr(tx, r, nu)
                nxt = r["prev"]
            elif r["type"] == "clr":
                nxt = r["undo_next"] if "prev_walk" not in f else r["prev"]
            else:
                nxt = r["prev"]
            if nxt is None:
                end(tx)
                del key[tx]
            else:
                key[tx] = nxt
        return out
    up = {tx: undo_point(R, T[tx]["last"], f) for tx in sorted(T)}
    for tx in sorted(t for t in up if up[t] is None):
        end(tx)
        del up[tx]
    while up:
        tx = max(up, key=lambda t: (up[t]["lsn"], -t))
        u = up[tx]
        nu = undo_point(R, u["prev"], f)
        clr(tx, u, nu)
        up[tx] = nu
        if nu is None:
            end(tx)
            del up[tx]
    return out


def commit_filter(img):
    """Shipped method: replay committed transactions, then reverse each loser's updates per transaction."""
    R, order, T, D, _m = analysis(img, set())
    pages = {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in img["disk"].items()}
    committed = {r["txn"] for r in img["records"] if r["type"] == "commit"}
    applied = 0
    for lsn in order:
        r = R[lsn]
        if r["type"] in ("update", "clr") and r["txn"] in committed:
            for ch in r["changes"]:
                if lsn > pages[ch["page"]]["page_lsn"]:
                    pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                    pages[ch["page"]]["page_lsn"] = lsn
                    applied += 1
    winners = sorted(t for t in T if T[t]["state"] == "committed")
    losers = sorted(t for t in T if T[t]["state"] != "committed")
    nxt = max(order) + 1
    app = []
    for tx in losers:
        for r in sorted((r for r in img["records"] if r.get("txn") == tx and r["type"] == "update"),
                        key=lambda r: -r["lsn"]):
            c = {"lsn": nxt, "type": "clr", "txn": tx, "prev": nxt - 1,
                 "changes": [{"page": x["page"], "slot": x["slot"], "delta": -x["delta"]} for x in r["changes"]],
                 "undo_next": r["prev"]}
            for x in c["changes"]:
                pages[x["page"]]["slots"][x["slot"]] += x["delta"]
            app.append(c)
            nxt += 1
    return {"status": "recovered", "pages": pages, "winners": winners, "losers": losers,
            "redo_start": min(D.values()) if D else None, "examined": applied, "applied": applied,
            "appended": app, "next_lsn": nxt}


def recover(img, f):
    err = bg.validate(img)
    if err:
        return {"status": "rejected", "error": err}
    if "commit_filter" in f:
        return commit_filter(img)
    R, order, T, D, master = analysis(img, f)
    pages = {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in img["disk"].items()}
    winners = sorted(t for t, e in T.items() if e["state"] == "committed")
    losers = sorted(t for t, e in T.items() if e["state"] != "committed")
    start, examined, applied = redo(R, order, D, pages, master, f)
    app = appended(R, T, pages, max(order) + 1, f)
    step = 0 if "end_no_lsn" in f else 1
    nl = max(order) + 1 + sum(1 if a["type"] == "clr" else step for a in app)
    return {"status": "recovered", "pages": pages, "winners": winners, "losers": losers,
            "redo_start": start, "examined": examined, "applied": applied, "appended": app, "next_lsn": nl}


def documents(book, flags):
    return bg.documents(book, lambda img: recover(img, flags))
