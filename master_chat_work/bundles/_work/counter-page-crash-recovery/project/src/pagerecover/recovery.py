"""Validation and restart recovery of one crash image.

An image is a dict with keys id, pages ({page: slot count}), disk
({page: {page_lsn, slots}}), records (journal records of the image) and
master (master checkpoint LSN, 0 when there is none).
"""

TXN_TYPES = ("begin", "update", "clr", "commit", "abort", "end")


def validate_image(image):
    """Return an error code for a damaged image, or None."""
    seen = set()
    for record in image["records"]:
        if record["lsn"] in seen:
            return "E_DUP_LSN"
        seen.add(record["lsn"])
    return None


def transaction_table(image):
    """Final state and last LSN of every transaction without an END."""
    table = {}
    for record in image["records"]:
        if record["type"] not in TXN_TYPES:
            continue
        txn = record["txn"]
        if record["type"] == "end":
            table.pop(txn, None)
            continue
        entry = table.setdefault(txn, {"state": "running", "last": record["lsn"]})
        entry["last"] = record["lsn"]
        if record["type"] == "commit":
            entry["state"] = "committed"
        elif record["type"] == "abort":
            entry["state"] = "aborting"
    return table


def _copy_pages(image):
    return {page: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])}
            for page, d in image["disk"].items()}


def recover_image(image):
    error = validate_image(image)
    if error:
        return {"status": "rejected", "error": error}
    records = image["records"]
    pages = _copy_pages(image)
    table = transaction_table(image)
    committed = {r["txn"] for r in records if r["type"] == "commit"}

    replayed = 0
    applied = 0
    first = None
    for record in records:
        if record["type"] not in ("update", "clr") or record["txn"] not in committed:
            continue
        replayed += 1
        for change in record["changes"]:
            page = pages[change["page"]]
            if record["lsn"] > page["page_lsn"]:
                page["slots"][change["slot"]] += change["delta"]
                page["page_lsn"] = record["lsn"]
                applied += 1
                first = record["lsn"] if first is None else min(first, record["lsn"])

    winners = sorted(t for t, e in table.items() if e["state"] == "committed")
    losers = sorted(t for t, e in table.items() if e["state"] != "committed")
    next_lsn = max(r["lsn"] for r in records) + 1
    appended = []
    for txn in losers:
        updates = [r for r in records if r.get("txn") == txn and r["type"] == "update"]
        for update in reversed(updates):
            clr = {"lsn": next_lsn, "type": "clr", "txn": txn, "prev": next_lsn - 1,
                   "changes": [{"page": c["page"], "slot": c["slot"], "delta": -c["delta"]}
                               for c in update["changes"]],
                   "undo_next": update["prev"]}
            for change in clr["changes"]:
                pages[change["page"]]["slots"][change["slot"]] += change["delta"]
            appended.append(clr)
            next_lsn += 1
    return {"status": "recovered", "pages": pages, "winners": winners, "losers": losers,
            "redo_start": first, "redo_records": replayed, "redo_changes_applied": applied,
            "appended": appended, "next_lsn": next_lsn}
