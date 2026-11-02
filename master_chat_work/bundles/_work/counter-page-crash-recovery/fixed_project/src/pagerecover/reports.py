"""The four recovery documents."""
import hashlib
import json
import os

DOCUMENTS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")


def image_digest(pages):
    canonical = json.dumps(pages, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _client_totals(result, owners):
    clients = {}
    for txn in result["winners"] + result["losers"]:
        entry = clients.setdefault(owners[txn], {"winners": 0, "losers": 0, "compensated": 0})
        entry["winners" if txn in result["winners"] else "losers"] += 1
    for record in result["appended"]:
        if record["type"] == "clr":
            entry = clients[owners[record["txn"]]]
            entry["compensated"] += sum(abs(c["delta"]) for c in record["changes"])
    return clients


def _audits(result, queries):
    answers = {}
    for q in queries:
        total = 0
        for page in q["pages"]:
            slots = result["pages"][page]["slots"]
            total += sum(slots) if q["slot"] == "all" else slots[q["slot"]]
        answers[q["id"]] = total
    return answers


def build_documents(book, results):
    docs = {name: {} for name in DOCUMENTS}
    for image_id, result in results.items():
        if result["status"] != "recovered":
            for name in DOCUMENTS:
                docs[name][image_id] = {"status": "rejected", "error": result["error"]}
            continue
        clrs = [r for r in result["appended"] if r["type"] == "clr"]
        docs["module_core.json"][image_id] = {"status": "recovered", "pages": result["pages"]}
        docs["module_metrics.json"][image_id] = {
            "status": "recovered",
            "winners": len(result["winners"]),
            "losers": len(result["losers"]),
            "redo_start_lsn": result["redo_start"],
            "redo_records": result["redo_records"],
            "redo_changes_applied": result["redo_changes_applied"],
            "clrs_appended": len(clrs),
            "ends_appended": len(result["appended"]) - len(clrs),
            "next_lsn": result["next_lsn"],
        }
        docs["dependency_resolution.json"][image_id] = {
            "status": "recovered", "losers": result["losers"], "appended": result["appended"]}
        docs["summary.json"][image_id] = {
            "status": "recovered",
            "image_sha256": image_digest(result["pages"]),
            "clients": _client_totals(result, book["owners"].get(image_id, {})),
            "audits": _audits(result, book["queries"].get(image_id, [])),
        }
    return {name: {"images": doc} for name, doc in docs.items()}


def write_documents(out_dir, book, results):
    for name, doc in build_documents(book, results).items():
        with open(os.path.join(out_dir, name), "w") as fh:
            json.dump(doc, fh, indent=2)
