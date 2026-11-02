"""Prototype recovery (contract reading) with switchable wrong readings for the premortem."""
import hashlib
import json

TXN_TYPES = {"begin", "update", "clr", "commit", "abort", "end"}


def validate(img):
    pages = img["pages"]
    disk = img["disk"]
    for pid, n in pages.items():
        if pid not in disk or disk[pid].get("bad") or len(disk[pid]["slots"]) != n:
            return "E_BAD_IMAGE"
    if set(disk) - set(pages):
        return "E_BAD_IMAGE"
    for r in img["records"]:
        if r["type"] in ("update", "clr"):
            for ch in r["changes"]:
                if ch["page"] not in pages or not (0 <= ch["slot"] < pages[ch["page"]]):
                    return "E_UNKNOWN_PAGE"
    seen = set()
    for r in img["records"]:
        if r["lsn"] in seen:
            return "E_DUP_LSN"
        seen.add(r["lsn"])
    R = {r["lsn"]: r for r in img["records"]}
    for r in img["records"]:
        if r["type"] not in TXN_TYPES:
            continue
        for key in ("prev", "undo_next"):
            if key not in r or r[key] is None:
                continue
            t = R.get(r[key])
            if t is None or r[key] >= r["lsn"] or t.get("txn") != r["txn"]:
                return "E_BAD_CHAIN"
        if r["type"] != "begin" and r["prev"] is None:
            return "E_BAD_CHAIN"
    return None


def undo_point(R, lsn, one_hop=False, prev_walk=False):
    via_undo_next = False
    while lsn is not None:
        r = R[lsn]
        t = r["type"]
        if t == "update":
            return r
        if t == "clr":
            if one_hop and via_undo_next:
                return r
            if prev_walk:
                lsn = r["prev"]
                via_undo_next = False
            else:
                lsn = r["undo_next"]
                via_undo_next = True
        else:
            lsn = r["prev"]
            via_undo_next = False
    return None


def analysis(img, f):
    recs = [r for r in img["records"]]
    R = {r["lsn"]: r for r in recs}
    order = sorted(R)
    master = img["master"]
    if f.get("latest_ckpt"):
        ends = [r for r in recs if r["type"] == "ckpt_end"]
        if ends:
            master = max(ends, key=lambda r: r["lsn"])["begin"]
    T, D = {}, {}
    scan_from = None
    if master:
        ce = [r for r in recs if r["type"] == "ckpt_end" and r["begin"] == master][0]
        for t in ce["txns"]:
            T[t["txn"]] = {"state": t["state"], "last": t["last"]}
        for d in ce["dirty"]:
            D[d["page"]] = d["rec"]
        scan_from = ce["lsn"] if f.get("analysis_from_end") else master
    for lsn in order:
        if scan_from is not None and lsn < scan_from:
            continue
        r = R[lsn]
        if r["type"] not in TXN_TYPES:
            continue
        tx = r["txn"]
        if r["type"] == "end":
            T.pop(tx, None)
            continue
        e = T.setdefault(tx, {"state": "running", "last": lsn})
        e["last"] = lsn
        if r["type"] == "commit":
            e["state"] = "committed"
        elif r["type"] == "abort":
            e["state"] = "aborting"
        elif r["type"] in ("update", "clr"):
            for ch in r["changes"]:
                D.setdefault(ch["page"], lsn)
    return R, order, master, T, D


def appended_sequence(R, T, pages, next_lsn, f):
    """Yield appended records in contract order; mutates pages and T."""
    f = f or {}
    step = 0 if f.get("end_no_lsn") else 1

    def mk(**kw):
        return kw

    def end_rec(tx):
        nonlocal next_lsn
        r = mk(lsn=next_lsn, txn=tx, type="end", prev=T[tx]["last"])
        next_lsn += step
        return r

    winners = [tx for tx in T if T[tx]["state"] == "committed"]
    if not f.get("textbook_end"):
        winners = sorted(winners)
    for tx in winners:
        yield end_rec(tx)
        del T[tx]
    losers = sorted(T)
    up = {tx: undo_point(R, T[tx]["last"], f.get("one_hop"), f.get("prev_walk")) for tx in losers}

    def clr_for(tx, u):
        nonlocal next_lsn
        chs = [{"page": ch["page"], "slot": ch["slot"], "delta": -ch["delta"]} for ch in u["changes"]]
        if f.get("clr_reverse_changes"):
            chs = chs[::-1]
        c = mk(lsn=next_lsn, txn=tx, type="clr", prev=T[tx]["last"], changes=chs, undo_next=u["prev"])
        next_lsn += 1
        for ch in chs:
            pg = pages[ch["page"]]
            pg["slots"][ch["slot"]] += ch["delta"]
            pg["page_lsn"] = c["lsn"]
        T[tx]["last"] = c["lsn"]
        R[c["lsn"]] = c
        return c

    if f.get("textbook_end"):
        # classical ToUndo keyed by lastLSN; END when chain reaches null
        key = {tx: T[tx]["last"] for tx in losers}
        while key:
            tx = max(key, key=lambda t: (key[t], t))
            r = R[key[tx]]
            if r["type"] == "update":
                c = clr_for(tx, r)
                nxt = r["prev"]
                yield c
            elif r["type"] == "clr":
                nxt = r["undo_next"]
            else:
                nxt = r["prev"]
            if nxt is None:
                e = end_rec(tx)
                yield e
                del key[tx]
                del T[tx]
            else:
                key[tx] = nxt
        return

    for tx in sorted(t for t in losers if up[t] is None):
        yield end_rec(tx)
        del T[tx]
        del up[tx]
    if f.get("per_txn_order"):
        seq = sorted(up)
        for tx in seq:
            while up[tx] is not None:
                u = up[tx]
                c = clr_for(tx, u)
                if f.get("undo_next_resolved"):
                    nu = undo_point(R, u["prev"], f.get("one_hop"), f.get("prev_walk"))
                    c["undo_next"] = nu["lsn"] if nu else None
                yield c
                up[tx] = undo_point(R, u["prev"], f.get("one_hop"), f.get("prev_walk"))
            yield end_rec(tx)
            del T[tx]
        return
    while up:
        tx = max(up, key=lambda t: (up[t]["lsn"], -t))
        u = up[tx]
        c = clr_for(tx, u)
        nu = undo_point(R, u["prev"], f.get("one_hop"), f.get("prev_walk"))
        if f.get("undo_next_resolved"):
            c["undo_next"] = nu["lsn"] if nu else None
        yield c
        if nu is None:
            yield end_rec(tx)
            del T[tx]
            del up[tx]
        else:
            up[tx] = nu


def recover(img, f=None):
    f = f or {}
    err = validate(img)
    if err:
        return {"status": "rejected", "error": err}
    R, order, master, T, D = analysis(img, f)
    pages = {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in img["disk"].items()}
    T0 = {k: dict(v) for k, v in T.items()}
    if f.get("redo_from_ckpt") and master:
        start = master
    else:
        start = min(D.values()) if D else None
    examined = applied = 0
    if f.get("commit_filter"):
        committed = {tx for tx, e in T.items() if e["state"] == "committed"}
        for lsn in order:
            r = R[lsn]
            if r["type"] in ("update", "clr") and r["txn"] in committed:
                for ch in r["changes"]:
                    if lsn > pages[ch["page"]]["page_lsn"]:
                        pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                        pages[ch["page"]]["page_lsn"] = lsn
                        applied += 1
    elif start is not None:
        for lsn in order:
            if lsn < start:
                continue
            r = R[lsn]
            if r["type"] not in ("update", "clr"):
                continue
            examined += 1
            if f.get("no_clr_redo") and r["type"] == "clr":
                continue
            def ok(p):
                pg = pages[p]
                cmp = (lsn >= pg["page_lsn"]) if f.get("redo_ge") else (lsn > pg["page_lsn"])
                return p in D and lsn >= D[p] and cmp
            if f.get("per_record_redo"):
                if ok(r["changes"][0]["page"]):
                    for ch in r["changes"]:
                        pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                        pages[ch["page"]]["page_lsn"] = lsn
                        applied += 1
                continue
            if f.get("eager_pagelsn"):
                for ch in r["changes"]:
                    if ok(ch["page"]):
                        pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                        pages[ch["page"]]["page_lsn"] = lsn
                        applied += 1
                continue
            todo = {ch["page"] for ch in r["changes"] if ok(ch["page"])}
            for ch in r["changes"]:
                if ch["page"] in todo:
                    pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                    pages[ch["page"]]["page_lsn"] = lsn
                    applied += 1
    next_lsn = max(order) + 1
    losers = sorted(tx for tx, e in T.items() if e["state"] != "committed")
    winners = sorted(tx for tx, e in T.items() if e["state"] == "committed")
    if f.get("commit_filter"):
        # shipped: per loser, reverse its updates, CLRs ignored
        app = []
        for tx in winners:
            app.append({"lsn": next_lsn, "txn": tx, "type": "end", "prev": T[tx]["last"]})
            next_lsn += 1
        for tx in losers:
            ups = sorted((r for r in R.values() if r.get("txn") == tx and r["type"] == "update"),
                         key=lambda r: -r["lsn"])
            for u in ups:
                chs = [{"page": ch["page"], "slot": ch["slot"], "delta": -ch["delta"]} for ch in u["changes"]]
                c = {"lsn": next_lsn, "txn": tx, "type": "clr", "prev": T[tx]["last"], "changes": chs,
                     "undo_next": u["prev"]}
                next_lsn += 1
                for ch in chs:
                    pages[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                    pages[ch["page"]]["page_lsn"] = c["lsn"]
                T[tx]["last"] = c["lsn"]
                app.append(c)
            app.append({"lsn": next_lsn, "txn": tx, "type": "end", "prev": T[tx]["last"]})
            next_lsn += 1
    else:
        app = list(appended_sequence(R, T, pages, next_lsn, f))
    nxt = (max(a["lsn"] for a in app) + 1) if app else next_lsn
    return {"status": "recovered", "pages": pages, "winners": winners, "losers": losers,
            "redo_start": start, "examined": examined, "applied": applied, "appended": app,
            "next_lsn": nxt, "T0": T0}


def canon(pages):
    return json.dumps(pages, sort_keys=True, separators=(",", ":"))


def docs(book, f=None):
    core, metrics, dep, summ = {}, {}, {}, {}
    for img in book["images"]:
        iid = img["id"]
        res = recover(img, f)
        if res["status"] == "rejected":
            for d in (core, metrics, dep, summ):
                d[iid] = {"status": "rejected", "error": res["error"]}
            continue
        core[iid] = {"status": "recovered", "pages": res["pages"]}
        clr = [a for a in res["appended"] if a["type"] == "clr"]
        metrics[iid] = {"status": "recovered", "winners": len(res["winners"]), "losers": len(res["losers"]),
                        "redo_start": res["redo_start"], "redo_examined": res["examined"],
                        "redo_applied": res["applied"], "clrs_written": len(clr),
                        "ends_written": len(res["appended"]) - len(clr), "next_lsn": res["next_lsn"]}
        dep[iid] = {"status": "recovered", "losers": res["losers"], "appended": res["appended"]}
        cat = book["catalog"].get(iid, {})
        clients = {}
        for tx in res["winners"] + res["losers"]:
            c = clients.setdefault(cat[tx], {"committed": 0, "losers": 0, "compensated": 0})
            c["committed" if tx in res["winners"] else "losers"] += 1
        for a in clr:
            clients[cat[a["txn"]]]["compensated"] += sum(abs(ch["delta"]) for ch in a["changes"])
        audits = {}
        for q in book["queries"].get(iid, []):
            s = 0
            for p in q["pages"]:
                sl = res["pages"][p]["slots"]
                s += sum(sl) if q["slot"] is None else sl[q["slot"]]
            audits[q["id"]] = s
        summ[iid] = {"status": "recovered",
                     "image_sha256": hashlib.sha256(canon(res["pages"]).encode()).hexdigest(),
                     "clients": dict(sorted(clients.items())), "audits": audits}
    return {"core": core, "metrics": metrics, "dep": dep, "summary": summ}
