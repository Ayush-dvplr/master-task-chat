"""Author-time builder for the hidden corpora (not shipped in the bundle).

usage: python3 mkhidden.py <shipped_data_dir> <out_root>
Writes <out_root>/H1..H4 (full corpora), <out_root>/H*/../H*.cases.json
"""
import hashlib
import importlib.util
import json
import re
import shutil
import sqlite3
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("oracle", HERE / "oracle.py")
O = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(O)

CORPORA = {"H1": 7101, "H2": 7202, "H3": 7303, "H4": 7404}

# file -> (fmt, governing integer columns to reseed)
RESEED = {
    "dmd_block_a1.csv": ("csv", ["units"]),
    "dmd_block_a2.tsv": ("tsv", ["qty"]),
    "dmd_block_b1.psv": ("psv", ["units_dz"]),
    "dmd_block_b2.jsonl": ("jsonl", ["planned_units"]),
    "dmd_block_c1.ndjson": ("jsonl", ["units_dz"]),
    "dmd_block_c2.txt": ("txt", ["units"]),
    "mesh_dump_01.ndjson": ("jsonl", ["units"]),
    "mesh_dump_02.txt": ("txt", ["units"]),
    "unitcost_ledger_p1.csv": ("csv", ["amount"]),
    "unitcost_ledger_p2.tsv": ("tsv", ["amount"]),
    "setup_charge_even.csv": ("csv", ["amount"]),
    "setup_charge_odd.psv": ("psv", ["amount"]),
    "cap_grid_n.csv": ("csv", ["base_capacity_units"]),
    "cap_grid_s.tsv": ("tsv", ["base_capacity_units"]),
    "handling_rates.psv": ("psv", ["handling_cents_per_unit"]),
    "retrofit_savings.tsv": ("tsv", ["savings_value"]),
}
SEP = {"csv": ",", "tsv": "\t", "psv": "|", "txt": "|"}
CUTOFF = 8140


class Rng:
    def __init__(self, seed):
        self.seed = str(seed)
        self.n = 0

    def unit(self, *salt):
        h = hashlib.sha256(("|".join([self.seed, *map(str, salt)])).encode()).digest()
        return int.from_bytes(h[:8], "big") / 2 ** 64

    def pick(self, seq, *salt):
        return seq[int(self.unit(*salt) * len(seq))]


def scale_int(text, factor):
    core = text.strip()
    if not re.fullmatch(r"-?\d+", core):
        return text
    val = int(core)
    if val == 0:
        return text
    new = max(1, int(round(val * factor)))
    return text.replace(core, str(new), 1)


def reseed_file(path, fmt, cols, rng):
    lines = path.read_text(encoding="utf-8").split("\n")
    out = []
    if fmt == "jsonl":
        for ln in lines:
            if ln.strip():
                uid = re.search(r'"row_uid":"([^"]*)"', ln)
                for col in cols:
                    f = 0.75 + 0.55 * rng.unit(path.name, uid.group(1) if uid else ln, col)
                    ln = re.sub(r'("%s":)(\d+)' % col,
                                lambda m: m.group(1) + scale_int(m.group(2), f), ln)
            out.append(ln)
    else:
        sep = SEP[fmt]
        header = None
        for ln in lines:
            if fmt == "txt" and ln.startswith("# fixed column order:"):
                header = [c.strip() for c in ln.split(":", 1)[1].split("|")]
                out.append(ln)
                continue
            if header is None and fmt != "txt":
                header = [c.strip() for c in ln.split(sep)]
                out.append(ln)
                continue
            if not ln.strip() or ln.startswith("#"):
                out.append(ln)
                continue
            cells = ln.split(sep)
            uid = cells[header.index("row_uid")].strip() if "row_uid" in header else ln
            for col in cols:
                idx = header.index(col)
                f = 0.75 + 0.55 * rng.unit(path.name, uid, col)
                cells[idx] = scale_int(cells[idx], f)
            out.append(sep.join(cells))
    path.write_text("\n".join(out), encoding="utf-8")


def append_line(path, line):
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + line + "\n", encoding="utf-8")


def jl(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def refresh_manifest(d, touched):
    con = sqlite3.connect(d / "xref_manifest.db")
    for name in sorted(touched):
        fmt = con.execute("select fmt from sources where name=?", (name,)).fetchone()[0]
        con.execute("update sources set record_count=? where name=?",
                    (O.physical_rows(d / name, fmt), name))
    con.commit()
    con.close()


def dp(S, it, prefer_latest=False):
    hz = S["horizon"]
    d = [S["demand"][(it, t)] for t in hz]
    c = [S["unit_cost"][(it, t)] for t in hz]
    k = [S["setup_cost"][(it, t)] for t in hz]
    h = [S["holding_cost"][(it, t)] for t in hz]

    def block(a, b):
        tot = sum(d[a:b])
        if tot == 0:
            return 0
        return k[a] + c[a] * tot + sum(d[u] * sum(h[a:u]) for u in range(a, b))

    n = len(hz)
    best = [0] + [None] * n
    arg = [0] * (n + 1)
    for b in range(1, n + 1):
        for a in range(b):
            cand = best[a] + block(a, b)
            if best[b] is None or cand < best[b] or (prefer_latest and cand == best[b]):
                best[b], arg[b] = cand, a
    cuts, pos = [], n
    while pos > 0:
        cuts.append((arg[pos], pos))
        pos = arg[pos]
    cuts.reverse()
    opens = tuple(a for a, b in cuts if sum(d[a:b]) > 0)
    return best[n], opens, cuts, block


BINARY_SETS = {"H2", "H4"}


def scale_matches(text, pattern, factor):
    return re.sub(pattern, lambda m: m.group(1) + str(max(1, int(round(int(m.group(2)) * factor)))), text)


def rewrite_zip(path, edits):
    src = zipfile.ZipFile(path)
    members = [(info, src.read(info.filename)) for info in src.infolist()]
    src.close()
    with zipfile.ZipFile(path, "w") as dst:
        for info, data in members:
            if info.filename in edits:
                data = edits[info.filename](data.decode("utf-8")).encode("utf-8")
            out = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            out.compress_type = info.compress_type
            out.external_attr = info.external_attr
            dst.writestr(out, data)


def rewrite_pdf(path, edit):
    raw = path.read_bytes()
    objs = list(re.finditer(rb"(\d+) 0 obj\n(.*?)endobj\n", raw, re.S))
    tail = raw[objs[-1].end():]
    trailer = tail[tail.index(b"trailer"):tail.index(b"startxref")]
    body = bytearray(raw[:objs[0].start()])
    offsets = []
    for m in objs:
        inner = m.group(2)
        head = re.match(rb"<< /Length (\d+) /Filter /FlateDecode >>\nstream\n", inner)
        if head:
            stream = inner[head.end():head.end() + int(head.group(1))]
            text = edit(zlib.decompress(stream).decode("latin-1")).encode("latin-1")
            packed = zlib.compress(text, 9)
            inner = (b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(packed)
                     + packed + inner[head.end() + int(head.group(1)):])
        offsets.append(len(body))
        body += m.group(1) + b" 0 obj\n" + inner + b"endobj\n"
    start = len(body)
    body += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    body += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    body += trailer + b"startxref\n%d\n%%%%EOF\n" % start
    path.write_bytes(bytes(body))


def vary_binaries(dst, rng):
    """Re-author the governing figures held in the PDF, DOCX and XLSX sources."""
    f_hold = 0.78 + 0.5 * rng.unit("bin", "holding")
    f_short = 0.78 + 0.5 * rng.unit("bin", "shortfall")
    f_energy = 0.7 + 0.6 * rng.unit("bin", "energy")
    f_budget = 0.85 + 0.35 * rng.unit("bin", "budget")
    f_volume = 0.75 + 0.5 * rng.unit("bin", "volume")

    def pdf_edit(text):
        text = scale_matches(text, r"(R\|PARAM\|holding_rate\|)(\d+)", f_hold)
        return scale_matches(text, r"(R\|PARAM\|shortfall_penalty_per_unit\|)(\d+)", f_short)

    def budget_rows(xml):
        return re.sub(r'<row r="\d+">.*?</row>', lambda m: scale_matches(
            m.group(0), r'(<c r="B\d+"><v>)(\d+)', f_budget)
            if "<t>capital_budget</t>" in m.group(0) else m.group(0), xml)

    def volume_rows(xml):
        return scale_matches(xml, r'(<c r="B(?!1")\d+"><v>)(\d+)', f_volume)

    rewrite_pdf(dst / "penalty_schedule.pdf", pdf_edit)
    rewrite_zip(dst / "amendment_memo.docx", {"word/document.xml": lambda x: scale_matches(
        x, r"(R\|PARAM\|energy_surcharge\|)(\d+)", f_energy)})
    rewrite_zip(dst / "capital_program.xlsx", {"xl/worksheets/sheet1.xml": budget_rows,
                                               "xl/worksheets/sheet2.xml": volume_rows})
    return {"holding_factor": round(f_hold, 4), "shortfall_factor": round(f_short, 4),
            "energy_factor": round(f_energy, 4), "budget_factor": round(f_budget, 4),
            "volume_factor": round(f_volume, 4)}


def build_corpus(src, dst, name, seed):
    rng = Rng(seed)
    sqlite_version_header = (src / "xref_manifest.db").read_bytes()[96:100]
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    touched = set()
    cases = {"corpus": name, "seed": seed}
    uid_n = [0]

    def uid():
        uid_n[0] += 1
        return "U9%s%04d" % (name[1], uid_n[0])

    # M0 reseed governing numeric columns
    for fname, (fmt, cols) in RESEED.items():
        reseed_file(dst / fname, fmt, cols, rng)
    if name in BINARY_SETS:
        cases["binaries"] = vary_binaries(dst, rng)
        touched.update({"penalty_schedule.pdf", "amendment_memo.docx", "capital_program.xlsx"})

    S0 = O.build(dst)
    items, hz = S0["items"], S0["horizon"]

    # C3 amendment identity: first copy voided by the lifecycle log, later copy live;
    # and two live copies where the first one counts.
    amend = []
    for j in range(2):
        it = rng.pick(items, "am", j)
        t = rng.pick(hz, "amp", j)
        aid = "AM9%s%02d" % (name[1], j)
        u1, u2 = uid(), uid()
        a1 = 300 + int(rng.unit("a1", j) * 500)
        a2 = 300 + int(rng.unit("a2", j) * 500)
        append_line(dst / "cost_amendments.jsonl", jl({"amend_id": aid, "amount": a1,
                    "effective_seq": 7990 + j, "item": it.lower(), "period": t,
                    "row_uid": u1, "sign": "charge", "void": 0}))
        append_line(dst / "cost_amendments.jsonl", jl({"amend_id": aid, "amount": a2,
                    "effective_seq": 8010 + j, "item": it, "period": t,
                    "row_uid": u2, "sign": "charge", "void": 0}))
        if j == 0:
            append_line(dst / "adjustment_log.jsonl", jl({"action": "void",
                        "note": "clerical hold", "row_uid": u1, "seq": 8120}))
            touched.add("adjustment_log.jsonl")
        amend.append({"amend_id": aid, "item": it, "period": t, "first": a1,
                      "second": a2, "first_voided_by_log": j == 0})
    touched.add("cost_amendments.jsonl")
    cases["amendments"] = amend

    # C4 rejection rows in demand registers
    rej = []
    retired = sorted(set(O.norm_code(k) for k in ("K07", "K19")))
    rows = [
        ("dmd_block_a1.csv", "k_%s" % retired[0][1:], "retired_item"),
        ("dmd_block_a2.tsv", " K-9%s " % name[1], "unknown_item"),
        ("dmd_block_b1.psv", rng.pick(items, "rs", 0), "sentinel"),
    ]
    for fname, code, reason in rows:
        t = rng.pick(hz, "rj", fname)
        u = uid()
        units = "TBD" if reason == "sentinel" else str(100 + int(rng.unit("ru", fname) * 400))
        if fname.endswith(".csv"):
            line = ",".join([code, t, units, "9", "8100", "0", u, "50"])
        elif fname.endswith(".tsv"):
            line = "\t".join([code, t, units, "9", "8100", "0", u, "50"])
        else:
            line = "|".join([code, t, units, "9", "8100", "0", u, "50"])
        append_line(dst / fname, line)
        touched.add(fname)
        rej.append({"source": fname, "row_uid": u, "code": code, "reason": reason})
    cases["rejections"] = rej

    # C2 setup fallback: void every live setup row of chosen keys through the log
    S1 = O.build(dst)
    setup_rows = {}
    for row in S1["ctx"].by_role.get("setup_cost", []):
        key = (O.norm_code(O.get(row, "item")), O.norm_code(O.get(row, "period")))
        setup_rows.setdefault(key, []).append(str(O.get(row, "row_uid")).strip())
    opened = sorted(S1["opens"])
    chosen = []
    want = ["K22", "K14"]
    for it in want:
        cand = [k for k in opened if k[0] == it]
        if cand:
            chosen.append(cand[int(rng.unit("fb", it) * len(cand))])
    pool = [k for k in opened if k[0] not in want]
    while len(chosen) < 6 and pool:
        k = pool.pop(int(rng.unit("fbp", len(chosen)) * len(pool)))
        if k[0] not in {c[0] for c in chosen}:
            chosen.append(k)
    for key in chosen:
        for u in setup_rows.get(key, []):
            append_line(dst / "adjustment_log.jsonl", jl({"action": "void",
                        "note": "planner rollback", "row_uid": u, "seq": 8138}))
    touched.add("adjustment_log.jsonl")
    refresh_manifest(dst, touched)
    S2 = O.build(dst)
    fb = O.item_fallbacks(S2["ctx"])
    cases["fallback_keys"] = [{"item": k[0], "period": k[1],
                               "setup": S2["setup_cost"][k],
                               "listed": k[0] in fb} for k in chosen]
    for k in chosen:
        assert S2["setup_cost"][k] == fb.get(k[0], 96000), k

    # C5 trigger depth: (a) a log entry above the cutoff, (b) a row whose own
    # void is 1 followed by a log restore, (c) an energy uplift on a negative half
    depth = {}
    used = {(a["item"], a["period"]) for a in amend} | set(chosen)
    dfile = {"H1": "dmd_block_a1.csv", "H2": "dmd_block_a2.tsv",
             "H3": "dmd_block_a2.tsv", "H4": "dmd_block_a1.csv"}[name]
    sep = {"csv": ",", "tsv": "\t", "psv": "|"}[dfile[-3:]]
    kind = "log_above_cutoff" if name in ("H1", "H3") else "own_void_restored"
    keys = sorted(((it, t) for it in items for t in hz
                   if (it, t) not in used and S2["demand"][(it, t)] > 0),
                  key=lambda k: rng.unit("dl", *k))
    key = keys[0]
    units = S2["demand"][key] + 37 + int(rng.unit("du", name) * 200)
    u = uid()
    own_void = "0" if kind == "log_above_cutoff" else "1"
    append_line(dst / dfile, sep.join([key[0], key[1], str(units), "9", "8100",
                                       own_void, u, "50"]))
    if kind == "log_above_cutoff":
        entry = {"action": "void", "note": "planner rollback", "row_uid": u, "seq": 8150}
    else:
        entry = {"action": "restore", "note": "hold released", "row_uid": u, "seq": 8130}
    append_line(dst / "adjustment_log.jsonl", jl(entry))
    touched.update({dfile, "adjustment_log.jsonl"})
    refresh_manifest(dst, touched)
    S5 = O.build(dst)
    expect = units if kind == "log_above_cutoff" else S2["demand"][key]
    assert S5["demand"][key] == expect, (name, key, S5["demand"][key], expect)
    depth[kind] = {"source": dfile, "row_uid": u, "item": key[0], "period": key[1],
                   "units": units, "log": entry, "demand_kept": expect}
    if name in ("H2", "H3", "H4"):
        tab = O.read_cost_tables(S5)
        flat = dict(S5, energy_surcharge=0)
        flat_tab = dict(tab, energy={})
        sur = S5["energy_surcharge"]
        periods = sorted(hz, key=lambda t: rng.unit("en", t))
        found = None
        for total in range(-40, -401, -1):
            for t in periods:
                hits = []
                for it in items:
                    v = O.item_period_cost(flat, flat_tab, (it, t))[0]
                    if v > 0 and (v * -total) % 10000 == 5000:
                        hits.append((it, v))
                if hits:
                    found = (total, t, hits)
                    break
            if found:
                break
        total, t, hits = found
        ue = uid()
        append_line(dst / "energy_index.tsv", "\t".join(
            [t, str(total - sur), "bps", "9", "8100", "0", ue]))
        touched.add("energy_index.tsv")
        refresh_manifest(dst, touched)
        S6 = O.build(dst)
        for it, v in hits:
            n = v * total
            assert S6["energy_applied"][(it, t)] == total, (name, it, t)
            assert S6["unit_cost"][(it, t)] == v + O.rhu(n, 10000), (name, it, t)
            assert O.rhu(n, 10000) != (2 * n + 10000) // 20000, (name, it, t)
        depth["negative_half"] = {"period": t, "row_uid": ue, "index_value": total - sur,
                                  "surcharge": sur, "bps_applied": total,
                                  "items": [{"item": it, "value": v,
                                             "uplift": O.rhu(v * total, 10000)}
                                            for it, v in hits]}
    cases["trigger_depth"] = depth

    # C1 lot ties: lower the setup at a split period so split == merged in cost
    ties = []
    cand_items = sorted(items, key=lambda i: rng.unit("ti", i))
    for it in cand_items:
        if len(ties) >= 2:
            break
        S3 = O.build(dst)
        best, opens, cuts, block = dp(S3, it)
        multi = [(a, b) for a, b in cuts if b - a >= 2 and sum(
            S3["demand"][(it, hz[x])] for x in range(a + 1, b)) > 0]
        done = False
        for a, b in multi:
            for m in range(a + 1, b):
                if S3["demand"][(it, hz[m])] == 0:
                    continue
                delta = block(a, m) + block(m, b) - block(a, b)
                newk = S3["setup_cost"][(it, hz[m])] - delta
                if delta <= 0 or newk < 20000:
                    continue
                trial = dst.parent / (dst.name + ".trial")
                if trial.exists():
                    shutil.rmtree(trial)
                shutil.copytree(dst, trial)
                append_line(trial / "setup_charge_odd.psv", "|".join(
                    [it, hz[m], str(newk), "cents", "9", "8105", "0", "U9%s%04d" % (name[1], 900 + len(ties))]))
                refresh_manifest(trial, {"setup_charge_odd.psv"})
                S4 = O.build(trial)
                b1, o1, _c, _b = dp(S4, it)
                b2, o2, _c, _b = dp(S4, it, prefer_latest=True)
                if b1 == b2 and o1 != o2 and o1 == opens and S4["setup_cost"][(it, hz[m])] == newk:
                    shutil.rmtree(dst)
                    trial.rename(dst)
                    ties.append({"item": it, "merged_start": hz[a], "split_at": hz[m],
                                 "setup": newk, "oracle": [hz[x] for x in o1],
                                 "latest_reading": [hz[x] for x in o2]})
                    done = True
                    break
                shutil.rmtree(trial)
            if done:
                break
    cases["lot_ties"] = ties
    assert len(ties) == 2, (name, ties)
    # SQLite rewrites its library version in the file header on commit. Keep
    # overlays byte-stable across the author's host and the original build.
    with (dst / "xref_manifest.db").open("r+b") as db:
        db.seek(96)
        db.write(sqlite_version_header)
    return cases


def main():
    src, root = Path(sys.argv[1]), Path(sys.argv[2])
    root.mkdir(parents=True, exist_ok=True)
    allc = {}
    for name, seed in CORPORA.items():
        allc[name] = build_corpus(src, root / name, name, seed)
    (root / "cases.json").write_text(json.dumps(allc, indent=1, sort_keys=True) + "\n")
    print(json.dumps(allc, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
