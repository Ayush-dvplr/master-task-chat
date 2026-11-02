"""Validation and restart recovery of one crash image.

An image is a dict with keys id, pages ({page: slot count}), disk
({page: {page_lsn, slots}}), records (journal records of the image),
master (master checkpoint LSN, 0 when there is none) and, when read from a
book, bad_frames (how many frames were duplicated or failed their CRC).
"""

TXN_TYPES = ("begin", "update", "clr", "commit", "abort", "end")
CHANGE_TYPES = ("update", "clr")


class Rejected(Exception):
    """A crash image failed validation; args[0] is the error code."""


def _check_frames(image):
    pages = image["pages"]
    disk = image["disk"]
    if image.get("bad_frames") or set(disk) != set(pages):
        raise Rejected("E_BAD_IMAGE")
    for page, frame in disk.items():
        if len(frame["slots"]) != pages[page]:
            raise Rejected("E_BAD_IMAGE")


def _check_changes(image):
    pages = image["pages"]
    for record in image["records"]:
        if record["type"] not in CHANGE_TYPES:
            continue
        for change in record["changes"]:
            count = pages.get(change["page"])
            if count is None or not 0 <= change["slot"] < count:
                raise Rejected("E_UNKNOWN_PAGE")


def _check_lsns(image):
    lsns = [record["lsn"] for record in image["records"]]
    if len(set(lsns)) != len(lsns):
        raise Rejected("E_DUP_LSN")


def _check_chains(image):
    by_lsn = {record["lsn"]: record for record in image["records"]}

    def links_back(record, target):
        other = by_lsn.get(target)
        return other is not None and other.get("txn") == record["txn"] and target < record["lsn"]

    for record in image["records"]:
        if record["type"] not in TXN_TYPES:
            continue
        if record["type"] == "begin":
            if record["prev"] is not None:
                raise Rejected("E_BAD_CHAIN")
        elif record["prev"] is None or not links_back(record, record["prev"]):
            raise Rejected("E_BAD_CHAIN")
        if record["type"] == "clr" and record["undo_next"] is not None:
            if not links_back(record, record["undo_next"]):
                raise Rejected("E_BAD_CHAIN")


def validate_image(image):
    """Return the error code of the first failing check, or None."""
    try:
        for check in (_check_frames, _check_changes, _check_lsns, _check_chains):
            check(image)
    except Rejected as exc:
        return exc.args[0]
    return None


def analyse(image, log):
    """Transaction table {txn: {state, last}} and dirty page table {page: recLSN}."""
    table = {}
    dirty = {}
    master = image["master"]
    if master:
        end = next(r for r in log if r["type"] == "checkpoint_end" and r["begin_lsn"] == master)
        for entry in end["txn_table"]:
            table[entry["txn"]] = {"state": entry["state"], "last": entry["last_lsn"]}
        for entry in end["dirty_pages"]:
            dirty[entry["page"]] = entry["rec_lsn"]
    for record in log:
        if record["lsn"] < master or record["type"] not in TXN_TYPES:
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
        if record["type"] in CHANGE_TYPES:
            for change in record["changes"]:
                dirty.setdefault(change["page"], record["lsn"])
    return table, dirty


def redo(log, dirty, pages):
    """Repeat history from the smallest recLSN; returns (start, records read, changes applied)."""
    if not dirty:
        return None, 0, 0
    start = min(dirty.values())
    read = applied = 0
    for record in log:
        if record["lsn"] < start or record["type"] not in CHANGE_TYPES:
            continue
        read += 1
        lsn = record["lsn"]
        redone = {change["page"] for change in record["changes"]
                  if change["page"] in dirty and lsn >= dirty[change["page"]]
                  and lsn > pages[change["page"]]["page_lsn"]}
        for change in record["changes"]:
            if change["page"] in redone:
                pages[change["page"]]["slots"][change["slot"]] += change["delta"]
                applied += 1
        for page in redone:
            pages[page]["page_lsn"] = lsn
    return start, read, applied


def undo_point(by_lsn, lsn):
    """Follow a loser's chain from lsn to the update that is undone next, or None."""
    while lsn is not None:
        record = by_lsn[lsn]
        if record["type"] == "update":
            return record
        lsn = record["undo_next"] if record["type"] == "clr" else record["prev"]
    return None


def undo(by_lsn, table, pages, next_lsn):
    """Append END and CLR records in the stated order; returns (appended, next lsn)."""
    appended = []

    def append(record):
        nonlocal next_lsn
        record["lsn"] = next_lsn
        next_lsn += 1
        by_lsn[record["lsn"]] = record
        appended.append(record)
        return record

    def end(txn):
        append({"type": "end", "txn": txn, "prev": table[txn]["last"]})

    winners = sorted(t for t, e in table.items() if e["state"] == "committed")
    losers = sorted(t for t, e in table.items() if e["state"] != "committed")
    for txn in winners:
        end(txn)
    pending = {}
    for txn in losers:
        point = undo_point(by_lsn, table[txn]["last"])
        if point is None:
            end(txn)
        else:
            pending[txn] = point
    while pending:
        txn = max(pending, key=lambda t: pending[t]["lsn"])
        update = pending[txn]
        clr = append({"type": "clr", "txn": txn, "prev": table[txn]["last"],
                      "changes": [{"page": c["page"], "slot": c["slot"], "delta": -c["delta"]}
                                  for c in update["changes"]],
                      "undo_next": update["prev"]})
        for change in clr["changes"]:
            pages[change["page"]]["slots"][change["slot"]] += change["delta"]
            pages[change["page"]]["page_lsn"] = clr["lsn"]
        table[txn]["last"] = clr["lsn"]
        point = undo_point(by_lsn, clr["lsn"])
        if point is None:
            del pending[txn]
            end(txn)
        else:
            pending[txn] = point
    fields = {"clr": ("lsn", "type", "txn", "prev", "changes", "undo_next"),
              "end": ("lsn", "type", "txn", "prev")}
    ordered = [{key: record[key] for key in fields[record["type"]]} for record in appended]
    return ordered, next_lsn


def recover_image(image):
    error = validate_image(image)
    if error:
        return {"status": "rejected", "error": error}
    log = sorted(image["records"], key=lambda r: r["lsn"])
    pages = {page: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])}
             for page, d in image["disk"].items()}
    table, dirty = analyse(image, log)
    start, read, applied = redo(log, dirty, pages)
    winners = sorted(t for t, e in table.items() if e["state"] == "committed")
    losers = sorted(t for t, e in table.items() if e["state"] != "committed")
    by_lsn = {record["lsn"]: record for record in log}
    appended, next_lsn = undo(by_lsn, table, pages, max(by_lsn) + 1)
    return {"status": "recovered", "pages": pages, "winners": winners, "losers": losers,
            "redo_start": start, "redo_records": read, "redo_changes_applied": applied,
            "appended": appended, "next_lsn": next_lsn}
