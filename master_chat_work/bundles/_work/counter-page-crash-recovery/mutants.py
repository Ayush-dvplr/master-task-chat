"""Real mutants of the oracle deliverable, graded by tests/test_output.py (local stub rewardkit).

Each mutant patches one member of the oracle's /app/out/package.zip (or one /app/out file),
regenerates the four shipped documents with the patched archive, and grades the result.
Usage: mutants.py <oracle out dir> [name ...]
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "counter-page-crash-recovery"
TESTS = BUNDLE / "tests" / "test_output.py"
DATA = BUNDLE / "environment" / "data"
REC = "src/pagerecover/recovery.py"
LOAD = "src/pagerecover/loader.py"
PAGES = "src/pagerecover/pages.py"
REP = "src/pagerecover/reports.py"
CLI = "src/pagerecover/cli.py"
C = "recovery_contract.md"

EAGER_OLD = '''        redone = {change["page"] for change in record["changes"]
                  if change["page"] in dirty and lsn >= dirty[change["page"]]
                  and lsn > pages[change["page"]]["page_lsn"]}
        for change in record["changes"]:
            if change["page"] in redone:
                pages[change["page"]]["slots"][change["slot"]] += change["delta"]
                applied += 1
        for page in redone:
            pages[page]["page_lsn"] = lsn
'''
EAGER_NEW = '''        for change in record["changes"]:
            page = change["page"]
            if page in dirty and lsn >= dirty[page] and lsn > pages[page]["page_lsn"]:
                pages[page]["slots"][change["slot"]] += change["delta"]
                pages[page]["page_lsn"] = lsn
                applied += 1
'''
FIRST_OLD = '''        redone = {change["page"] for change in record["changes"]
                  if change["page"] in dirty and lsn >= dirty[change["page"]]
                  and lsn > pages[change["page"]]["page_lsn"]}
'''
FIRST_NEW = '''        first = record["changes"][0]["page"]
        redone = (set(c["page"] for c in record["changes"])
                  if first in dirty and lsn >= dirty[first] and lsn > pages[first]["page_lsn"] else set())
'''
HOP_OLD = '''        lsn = record["undo_next"] if record["type"] == "clr" else record["prev"]
'''
HOP_NEW = '''        if record["type"] == "clr" and record["undo_next"] is not None \\
                and by_lsn[record["undo_next"]]["type"] == "clr":
            return by_lsn[record["undo_next"]]
        lsn = record["undo_next"] if record["type"] == "clr" else record["prev"]
'''
IDLE_OLD = '''        if point is None:
            end(txn)
        else:
            pending[txn] = point
    while pending:
'''
IDLE_NEW = '''        if point is None:
            idle.append(txn)
        else:
            pending[txn] = point
    while pending:
'''
SCAN_OLD = '''    for record in log:
        if record["lsn"] < master or record["type"] not in TXN_TYPES:
'''
SCAN_NEW = '''    scan = end["lsn"] if master else 0
    for record in log:
        if record["lsn"] < scan or record["type"] not in TXN_TYPES:
'''
SLOW_OLD = '''        results[image_id] = recovery.recover_image(image)
'''
SLOW_NEW = '''        if len(image["pages"]) == 24 and len(image["records"]) > 1100:
            import time
            time.sleep(6)
        results[image_id] = recovery.recover_image(image)
'''


def _out_json(name, change):
    def apply(out):
        path = out / name
        doc = json.loads(path.read_text())
        change(doc)
        path.write_text(json.dumps(doc, indent=2))
    return apply


def _drop_fixed(doc):
    doc["fixed_modules"] = doc["fixed_modules"][1:]


def _bump_run(doc):
    doc["tests_run"] += 1


# name -> (rule, contract ref, lever, [(member, old, new)] or callable on out dir)
MUTANTS = {
    "redo_eager_pagelsn": ("pages a record redoes are decided before any change is applied", C + ":114-119", "LV-WR-1",
                           [(REC, EAGER_OLD, EAGER_NEW)]),
    "redo_first_change_page": ("redo decided per page, not per record", C + ":114-119", "LV-WR-1",
                               [(REC, FIRST_OLD, FIRST_NEW)]),
    "redo_ge_pagelsn": ("record lsn greater than the page's pageLSN", C + ":117-118", "LV-WR-1",
                        [(REC, 'and lsn > pages[change["page"]]["page_lsn"]}', 'and lsn >= pages[change["page"]]["page_lsn"]}')]),
    "redo_start_master": ("redo starts at the smallest recLSN after analysis", C + ":111", "LV-WR-3",
                          [(REC, '    table, dirty = analyse(image, log)\n',
                            '    table, dirty = analyse(image, log)\n'
                            '    dirty = {p: max(r, image["master"]) for p, r in dirty.items()}\n')]),
    "undo_one_hop": ("a CLR moves to the record named by its undo_next", C + ":130-132", "LV-WR-2",
                     [(REC, HOP_OLD, HOP_NEW)]),
    "undo_prev_walk": ("a CLR moves to undo_next, any other record to prev", C + ":130-132", "LV-WR-2",
                       [(REC, HOP_OLD, '        lsn = record["prev"]\n'),
                        (REC, 'point = undo_point(by_lsn, clr["lsn"])', 'point = undo_point(by_lsn, update["prev"])')]),
    "clr_undo_next_field": ("the CLR's undo_next is the undone update's prev", C + ":138", "LV-WR-2",
                            [(REC, '"undo_next": update["prev"]})',
                              '"undo_next": (undo_point(by_lsn, update["prev"]) or {}).get("lsn")})')]),
    "undo_per_txn": ("each undo step takes the loser whose undo point has the largest LSN", C + ":134", "LV-WR-3",
                     [(REC, 'txn = max(pending, key=lambda t: pending[t]["lsn"])', 'txn = max(pending)')]),
    "idle_loser_end_late": ("end for every loser without undo point before the undo steps", C + ":126-128", "LV-WR-3",
                            [(REC, IDLE_OLD, IDLE_NEW),
                             (REC, '    pending = {}\n', '    pending = {}\n    idle = []\n'),
                             (REC, '    fields = {', '    for txn in idle:\n        end(txn)\n    fields = {')]),
    "winner_end_table_order": ("end for every winner in ascending transaction id", C + ":126", "LV-WR-3",
                               [(REC, '    winners = sorted(t for t, e in table.items() if e["state"] == "committed")\n    losers = sorted(t for t, e in table.items() if e["state"] != "committed")\n    for txn in winners:',
                                 '    winners = [t for t, e in table.items() if e["state"] == "committed"]\n    losers = sorted(t for t, e in table.items() if e["state"] != "committed")\n    for txn in winners:')]),
    "clr_keeps_pagelsn": ("appending a CLR sets the pageLSN of every page it names", C + ":139-140", "LV-WR-1",
                          [(REC, '            pages[change["page"]]["page_lsn"] = clr["lsn"]\n', '')]),
    "first_lsn_offset": ("the first appended record takes the largest journal lsn plus 1", C + ":123-124", "LV-WR-3",
                         [(REC, 'max(by_lsn) + 1)', 'max(by_lsn) + 2)')]),
    "analysis_keeps_ended": ("an end removes its transaction from the table", C + ":98-99", "LV-WR-1",
                             [(REC, '            table.pop(txn, None)\n            continue', '            continue')]),
    "analysis_from_ckpt_end": ("analysis reads every record whose lsn is at least master_lsn", C + ":97-98", "LV-WR-1",
                               [(REC, SCAN_OLD, SCAN_NEW)]),
    "dirty_overwrite": ("a page not yet in the dirty page table is added with recLSN", C + ":102-104", "LV-WR-1",
                        [(REC, 'dirty.setdefault(change["page"], record["lsn"])', 'dirty[change["page"]] = record["lsn"]')]),
    "validation_order": ("checks run in the stated order", C + ":71-83", "-",
                         [(REC, '(_check_frames, _check_changes, _check_lsns, _check_chains)',
                           '(_check_frames, _check_lsns, _check_changes, _check_chains)')]),
    "crc_ignored": ("a frame whose CRC-32 does not match rejects the image", C + ":75-77", "-",
                    [(LOAD, 'if not frame["crc_ok"] or frame["page"] in image_pages:', 'if frame["page"] in image_pages:')]),
    "undo_next_unchecked": ("a non-null undo_next names an earlier record of the same txn", C + ":81-83", "-",
                            [(REC, 'if record["type"] == "clr" and record["undo_next"] is not None:',
                              'if False:')]),
    "pagelsn_u32": ("pageLSN is an unsigned 64-bit big endian integer", C + ":2 input files", "-",
                    [(PAGES, '        off += 10\n', '        off += 10\n        page_lsn &= 0xFFFFFFFF\n')]),
    "slots_unsigned": ("slot values are signed 64-bit integers", C + ":2 input files", "-",
                       [(PAGES, '">%dq" % count', '">%dQ" % count')]),
    "page_ids_lowercased": ("page ids are case-sensitive", C + ":2 input files", "-",
                            [(LOAD, '    parser.optionxform = str\n', '')]),
    "sha_noncanonical": ("image_sha256 of pages serialized with sorted keys, no whitespace", C + ":174-177", "-",
                         [(REP, 'json.dumps(pages, sort_keys=True, separators=(",", ":"))', 'json.dumps(pages)')]),
    "compensated_signed": ("compensated is the sum of absolute deltas", C + ":178-180", "-",
                           [(REP, 'sum(abs(c["delta"]) for c', 'sum(c["delta"] for c')]),
    "missing_input_exit0": ("a missing input exits with a nonzero status", C + ":155-157", "-",
                            [(CLI, '        return 2\n', '        return 0\n')]),
    "writes_into_data": ("recovery reads the book; reruns give the same documents", C + ":152-153", "-",
                         [(CLI, '    os.makedirs(args.out, exist_ok=True)\n',
                           '    os.makedirs(args.out, exist_ok=True)\n'
                           '    with open(os.path.join(args.data, "audit_queries.json"), "a") as fh:\n'
                           '        fh.write(" ")\n')]),
    "slow_large_images": ("a book at the stated limits is recovered within 60 seconds", C + ":185", "-",
                          [(CLI, SLOW_OLD, SLOW_NEW)]),
    "pyproject_version": ("pyproject version is required_version", C + ":195-198", "-",
                          [("pyproject.toml", 'version = "2.4.0"', 'version = "2.3.0"')]),
    "extra_member": ("no member other than archive_members and added .py files", C + ":191-194", "-",
                     [("+notes.txt", None, "release notes\n")]),
    "selftest_count": ("tests_run is the unittest count of the archive's tests", C + ":208-209", "-",
                       _out_json("selftest.json", _bump_run)),
    "fixed_modules_short": ("fixed_modules lists every file the repair changed or created", C + ":215-216", "-",
                            _out_json("build_report.json", _drop_fixed)),
    "smoke_test_skipped": ("tests/test_smoke.py keeps every shipped test, none skipped", C + ":198-200", "-",
                           [("tests/test_smoke.py", "    def test_digest_is_hex", "    @unittest.skip('slow')\n    def test_digest_is_hex")]),
    "holds_image_ids": ("the package holds no figure or image id of any book", C + ":185-187", "-",
                        "IDS"),
}


def _runner():
    return ("import runpy, sys; sys.path.insert(0, sys.argv[1]); "
            "sys.argv = ['pagerecover'] + sys.argv[2:]; "
            "runpy.run_module('pagerecover', run_name='__main__', alter_sys=True)")


def run_mutant(name, oracle_out):
    rule, ref, lever, patch = MUTANTS[name]
    tmp = Path(tempfile.mkdtemp(prefix="mut-"))
    try:
        out = tmp / "app" / "out"
        shutil.copytree(oracle_out, out)
        data = tmp / "data"
        shutil.copytree(DATA, data)
        if callable(patch):
            patch(out)
        else:
            if patch == "IDS":
                ids = sorted(json.loads((out / "module_core.json").read_text())["images"])[:3]
                patch = [("+src/pagerecover/known.py", None, "KNOWN = %r\n" % ids)]
            src = zipfile.ZipFile(out / "package.zip")
            infos = src.infolist()
            files = {i.filename: src.read(i) for i in infos}
            template = infos[0]
            for member, old, new in patch:
                if member.startswith("+"):
                    member = member[1:]
                    zi = zipfile.ZipInfo(member, date_time=template.date_time)
                    zi.compress_type = template.compress_type
                    zi.external_attr = template.external_attr
                    infos.append(zi)
                    files[member] = new.encode()
                    continue
                text = files[member].decode()
                assert old in text, (name, member, old[:60])
                files[member] = text.replace(old, new, 1).encode()
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as dst:
                for info in infos:
                    dst.writestr(info, files[info.filename])
            (out / "package.zip").write_bytes(buf.getvalue())
            ext = tmp / "ext"
            zipfile.ZipFile(out / "package.zip").extractall(ext)
            for doc in ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json"):
                (out / doc).unlink()
            subprocess.run([sys.executable, "-I", "-B", "-c", _runner(), str(ext / "src"), "recover",
                            "--data", str(data), "--out", str(out)], capture_output=True, timeout=None)
        done = subprocess.run([sys.executable, "-B", str(HERE / "run_local_tests.py"), str(tmp / "app"), str(TESTS)],
                              capture_output=True, text=True, timeout=3000)
        lines = done.stdout.splitlines()
        results = json.loads(next(l for l in lines if l.startswith("RESULTS "))[8:])
        weights = {}
        for line in lines:
            m = re.match(r"(\w+)\s+w=\s*(-?\d+)", line)
            if m:
                weights[m.group(1)] = int(m.group(2))
        failed = [k for k, w in weights.items() if w > 0 and not results[k]]
        fired = [k for k, w in weights.items() if w < 0 and results[k]]
        lost = sum(weights[k] for k in failed) + sum(-weights[k] for k in fired)
        return name, rule, ref, lever, lost, failed + ["NEG:" + k for k in fired]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    oracle_out = Path(sys.argv[1])
    names = sys.argv[2:] or list(MUTANTS)
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(lambda n: run_mutant(n, oracle_out), names):
            rows.append(row)
            name, rule, ref, lever, lost, failed = row
            print("MUTANT %s | %s | %s | %s | lost %d | failed %s" % (name, rule, ref, lever, lost, " ".join(failed)),
                  flush=True)
    json.dump(rows, open(HERE / "mutants.json", "w"), indent=1)
    print("ALL_DONE")


if __name__ == "__main__":
    main()
