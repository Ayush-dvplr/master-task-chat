"""Rebuild the shipped environment/data/tool.zip with the ledger control readout.

The shipped cli keeps every original defect; the new readout reads
timeout_ms_delta raw, so the t-atlas control reports mismatch.
"""
import hashlib
import zipfile
from pathlib import Path

SRC = Path("/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/sentinel-policy-recompute/environment/data/tool.zip")
DST = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute/environment/data/tool.zip")

OLD_LOAD = '    overrides = load_json(data / "override_deltas.json")["overrides"]\n'
NEW_LOAD = '''    ledger_doc = load_json(data / "override_deltas.json")
    overrides = ledger_doc["overrides"]
    sums = {}
    for ov in overrides:
        entry = sums.setdefault(ov["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(ov["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += int(ov["timeout_ms_delta"])
    ledger_controls = {}
    for name, control in ledger_doc["controls"].items():
        ledger_controls[name] = "ok" if sums.get(name) == control else "mismatch"
'''
OLD_TRACE = '    trace = {"active_bundle": active_bundle, "resolution_order": [], "rejected_branches": []}\n'
NEW_TRACE = '''    trace = {
        "active_bundle": active_bundle,
        "applied_overrides": [selected["override_id"]],
        "ledger_controls": ledger_controls,
        "resolution_order": [],
        "rejected_branches": [],
    }
'''


def main():
    with zipfile.ZipFile(SRC) as z:
        members = {n: z.read(n) for n in z.namelist()}
    cli = members["cli.py"].decode()
    assert cli.count(OLD_LOAD) == 1 and cli.count(OLD_TRACE) == 1
    cli = cli.replace(OLD_LOAD, NEW_LOAD).replace(OLD_TRACE, NEW_TRACE)
    members["cli.py"] = cli.encode()
    with zipfile.ZipFile(DST, "w", compression=zipfile.ZIP_STORED) as z:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            z.writestr(info, members[name])
    print("cli.py sha256", hashlib.sha256(members["cli.py"]).hexdigest())
    print("tool.zip sha256", hashlib.sha256(DST.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
