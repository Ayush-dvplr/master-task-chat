"""h1 fuzz: a1 program vs reference on generator branches and documented mutators.

Run inside Docker only:  python3 -B fuzz.py OUTLOG branch|equiv|sem N [only=name,...]
Each job writes one JSON line: branch, mutator, seed, verdict, first diff, seconds.
"""
import csv
import io
import json
import multiprocessing as mp
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refgen as R  # noqa: E402

A1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a1_program.py")
NAMES = ["summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
         "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json"]
BRANCH = dict(R.HIDDEN)
BRANCH["shipped"] = (None, False, "bind", False)
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class Skip(Exception):
    pass


def make_branch(branch, seed, d):
    if branch == "shipped":
        return R.corpus("shipped", seed, 8, False, "bind", False, d)
    _, empty, stype, x1 = BRANCH[branch]
    return R.corpus("hidden", seed, 8, empty, stype, x1, d)


# ---------- docx helpers ----------
def dz_read(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def dz_write(path, parts):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items():
            z.writestr(n, b)


def tables(doc):
    return [(m.start(), m.end()) for m in re.finditer(r"<w:tbl>.*?</w:tbl>", doc, re.S)]


def header(tbl):
    tr = re.search(r"<w:tr>.*?</w:tr>", tbl, re.S).group(0)
    return re.findall(r"<w:t[^>]*>([^<]*)</w:t>", tr)


def edit_table(path, first_cell, fn, rng):
    parts = dz_read(path)
    doc = parts["word/document.xml"].decode()
    for a, b in tables(doc):
        tbl = doc[a:b]
        if header(tbl)[0] == first_cell:
            new = fn(tbl, rng)
            doc = doc[:a] + new + doc[b:]
            parts["word/document.xml"] = doc.encode()
            dz_write(path, parts)
            return
    raise Skip("no table " + first_cell)


def wrap_row(kind):
    def fn(tbl, rng):
        rows = [(m.start(), m.end()) for m in re.finditer(r"<w:tr>.*?</w:tr>", tbl, re.S)]
        if len(rows) < 2:
            raise Skip("no data row")
        a, b = rows[rng.randrange(1, len(rows))]
        tr = tbl[a:b]
        if kind == "sdt":
            w = "<w:sdt><w:sdtPr><w:id w:val=\"7\"/></w:sdtPr><w:sdtContent>%s</w:sdtContent></w:sdt>" % tr
        elif kind == "customXml":
            w = "<w:customXml w:element=\"row\">%s</w:customXml>" % tr
        elif kind == "cellsdt":
            cells = re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)
            last = cells[-1]
            w = tr.replace(last, "<w:sdt><w:sdtContent>%s</w:sdtContent></w:sdt>" % last)
        return tbl[:a] + w + tbl[b:]
    return fn


def all_rows_wrapped(tbl, rng):
    rows = list(re.finditer(r"<w:tr>.*?</w:tr>", tbl, re.S))
    if len(rows) < 2:
        raise Skip("no data row")
    out = tbl
    for m in reversed(rows[1:]):
        out = out[:m.start()] + "<w:sdt><w:sdtContent>%s</w:sdtContent></w:sdt>" % m.group(0) + out[m.end():]
    return out


def doc_sub(path, fn):
    parts = dz_read(path)
    parts["word/document.xml"] = fn(parts["word/document.xml"].decode()).encode()
    dz_write(path, parts)


def m_docx(kind, which):
    files = {"allow": ("planning_limits.docx", "base", lambda h: h[1] == "allowance_shifts"),
             "item": ("planning_limits.docx", "item", None), "class": ("planning_limits.docx", "class", None),
             "closure": ("disruption_notice.docx", "base", lambda h: h[1] == "from"),
             "avail": ("disruption_notice.docx", "tail", None)}
    fname, first, pred = files[which]

    def mut(d, rng):
        path = os.path.join(d, fname)
        parts = dz_read(path)
        doc = parts["word/document.xml"].decode()
        for a, b in tables(doc):
            h = header(doc[a:b])
            if h[0] == first and (pred is None or pred(h)):
                fn = all_rows_wrapped if kind == "sdt_all" else wrap_row(kind)
                doc = doc[:a] + fn(doc[a:b], rng) + doc[b:]
                parts["word/document.xml"] = doc.encode()
                dz_write(path, parts)
                return True
        raise Skip("table")
    return mut


def both_docx(fn):
    def mut(d, rng):
        for f in ("planning_limits.docx", "disruption_notice.docx"):
            fn(os.path.join(d, f), rng)
        return True
    return mut


def d_sdt_tbl(p, rng):
    doc_sub(p, lambda s: re.sub(r"(<w:tbl>.*?</w:tbl>)", r"<w:sdt><w:sdtContent>\1</w:sdtContent></w:sdt>", s,
                                flags=re.S))


def d_sdt_run(p, rng):
    doc_sub(p, lambda s: re.sub(r"(<w:tc><w:p>)(<w:r>.*?</w:r>)(</w:p>)",
                                r"\1<w:sdt><w:sdtContent>\2</w:sdtContent></w:sdt>\3", s, flags=re.S))


def d_split_runs(p, rng):
    def split(m):
        t = m.group(1)
        if len(t) < 2:
            return m.group(0)
        k = rng.randrange(1, len(t))
        return ('<w:r><w:t xml:space="preserve">  %s</w:t></w:r><w:r><w:rPr><w:b/></w:rPr>'
                '<w:t xml:space="preserve">%s </w:t></w:r>' % (t[:k], t[k:]))
    doc_sub(p, lambda s: re.sub(r'<w:r><w:t xml:space="preserve">([^<]*)</w:t></w:r>', split, s))


def d_rename_part(p, rng):
    parts = dz_read(p)
    parts["word/body_main.xml"] = parts.pop("word/document.xml")
    parts["_rels/.rels"] = parts["_rels/.rels"].replace(b"word/document.xml", b"word/body_main.xml")
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(b"/word/document.xml", b"/word/body_main.xml")
    dz_write(p, parts)


def d_target(t):
    def fn(p, rng):
        parts = dz_read(p)
        parts["_rels/.rels"] = parts["_rels/.rels"].replace(b'Target="word/document.xml"', ('Target="%s"' % t).encode())
        dz_write(p, parts)
    return fn


def d_extra_rels(p, rng):
    parts = dz_read(p)
    core = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.'
            b'openxmlformats.org/package/2006/metadata/core-properties"/>')
    parts["docProps/core.xml"] = core
    parts["_rels/.rels"] = parts["_rels/.rels"].replace(
        b'<Relationship Id="rId1"', b'<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/package/2006/'
        b'relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId1"')
    dz_write(p, parts)


def d_decoy(p, rng):
    dec = ('<w:tbl><w:tr><w:tc><w:p><w:r><w:t>note</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>detail</w:t></w:r>'
           '</w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>issued</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>'
           'Maintenance Control</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    doc_sub(p, lambda s: s.replace("<w:body>", "<w:body>" + dec, 1))


def d_tracked(p, rng):
    def tr(m):
        if not re.fullmatch(r"\d+", m.group(1)) or rng.random() < 0.5:
            return m.group(0)
        return ('<w:del w:id="1" w:author="mc"><w:r><w:delText>9%s</w:delText></w:r></w:del>'
                '<w:ins w:id="2" w:author="mc"><w:r><w:t>%s</w:t></w:r></w:ins>' % (m.group(1), m.group(1)))
    doc_sub(p, lambda s: re.sub(r'<w:r><w:t xml:space="preserve">([^<]*)</w:t></w:r>', tr, s))


def d_altcontent(p, rng):
    def ac(m):
        if rng.random() < 0.5:
            return m.group(0)
        return ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
                '<mc:Choice Requires="w">%s</mc:Choice><mc:Fallback>%s</mc:Fallback></mc:AlternateContent>'
                % (m.group(0), m.group(0)))
    doc_sub(p, lambda s: re.sub(r'<w:r><w:t xml:space="preserve">[^<]*</w:t></w:r>', ac, s))


def d_altcontent_data(p, rng):
    """mc:AlternateContent around runs of data rows only (header rows stay plain)."""
    def ac(m):
        if rng.random() < 0.5:
            return m.group(0)
        return ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
                '<mc:Choice Requires="w">%s</mc:Choice><mc:Fallback>%s</mc:Fallback></mc:AlternateContent>'
                % (m.group(0), m.group(0)))

    def tbl(mt):
        t = mt.group(0)
        rows = list(re.finditer(r"<w:tr>.*?</w:tr>", t, re.S))
        out = t
        for r in reversed(rows[1:]):
            out = out[:r.start()] + re.sub(r'<w:r><w:t xml:space="preserve">[^<]*</w:t></w:r>', ac, r.group(0)) \
                + out[r.end():]
        return out
    doc_sub(p, lambda s: re.sub(r"<w:tbl>.*?</w:tbl>", tbl, s, flags=re.S))


def m_alt(fname, first, second, cell):
    """mc:AlternateContent (Choice and Fallback carry the same run) around one value cell of one data row."""
    def mut(d, rng):
        path = os.path.join(d, fname)
        parts = dz_read(path)
        doc = parts["word/document.xml"].decode()
        for a, b in tables(doc):
            t = doc[a:b]
            h = header(t)
            if h[0] == first and h[1] == second:
                rows = list(re.finditer(r"<w:tr>.*?</w:tr>", t, re.S))
                if len(rows) < 2:
                    raise Skip("no data row")
                r = rows[rng.randrange(1, len(rows))]
                cells = list(re.finditer(r"<w:tc>.*?</w:tc>", r.group(0), re.S))
                c = cells[cell].group(0)
                run = re.search(r'<w:r><w:t xml:space="preserve">[^<]*</w:t></w:r>', c).group(0)
                ac = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
                      '<mc:Choice Requires="w">%s</mc:Choice><mc:Fallback>%s</mc:Fallback></mc:AlternateContent>'
                      % (run, run))
                nr = r.group(0).replace(c, c.replace(run, ac, 1), 1)
                t = t[:r.start()] + nr + t[r.end():]
                parts["word/document.xml"] = (doc[:a] + t + doc[b:]).encode()
                dz_write(path, parts)
                return True
        raise Skip("table")
    return mut


def d_bookmarks(p, rng):
    doc_sub(p, lambda s: s.replace("</w:tr><w:tr>", '</w:tr><w:bookmarkStart w:id="3" w:name="r"/>'
                                   '<w:bookmarkEnd w:id="3"/><w:tr>'))


def d_prefix(p, rng):
    doc_sub(p, lambda s: s.replace("w:", "q:").replace("xmlns:w=", "xmlns:q="))


def d_header_spaces(p, rng):
    def hs(tbl):
        tr = re.search(r"<w:tr>.*?</w:tr>", tbl, re.S).group(0)
        return tbl.replace(tr, re.sub(r'(<w:t xml:space="preserve">)([^<]*)(</w:t>)', r"\1 \2 \3", tr), 1)
    doc_sub(p, lambda s: re.sub(r"<w:tbl>.*?</w:tbl>", lambda m: hs(m.group(0)), s, flags=re.S))


def d_rowprops(p, rng):
    doc_sub(p, lambda s: s.replace("<w:tr>", '<w:tr w:rsidR="00A1"><w:trPr><w:cantSplit/></w:trPr>')
            .replace("<w:tc>", '<w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr>')
            .replace("<w:tblPr>", "<w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/>"))


# ---------- text file helpers ----------
def rcsv(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def wcsv(path, rows, quoting=csv.QUOTE_MINIMAL, nl="\n"):
    s = io.StringIO()
    csv.writer(s, quoting=quoting, lineterminator=nl).writerows(rows)
    with open(path, "w", newline="") as f:
        f.write(s.getvalue())


CSVS = ["check_requests.csv", "published_plan.csv", "fleet_register.csv"]


def c_crlf(d, rng):
    for f in CSVS:
        wcsv(os.path.join(d, f), rcsv(os.path.join(d, f)), nl="\r\n")
    return True


def c_quoted(d, rng):
    for f in CSVS:
        wcsv(os.path.join(d, f), rcsv(os.path.join(d, f)), quoting=csv.QUOTE_ALL)
    return True


def c_colorder(d, rng):
    for f in CSVS:
        rows = rcsv(os.path.join(d, f))
        idx = list(range(len(rows[0])))
        while idx == sorted(idx):
            rng.shuffle(idx)
        wcsv(os.path.join(d, f), [[r[i] for i in idx] for r in rows])
    return True


def c_extra_col(d, rng):
    for f in CSVS:
        rows = rcsv(os.path.join(d, f))
        wcsv(os.path.join(d, f), [r + (["note"] if i == 0 else ["see, memo %d" % i]) for i, r in enumerate(rows)])
    return True


def c_jsonl(d, rng):
    p = os.path.join(d, "base_calendar.jsonl")
    out = []
    for ln in open(p):
        c = json.loads(ln)
        out.append(json.dumps({"status": c["status"], "date": c["date"], "base": c["base"]}, indent=None,
                              separators=(" , ", " : ")))
    open(p, "w").write("\n".join(out) + "\n")
    return True


def c_toml(d, rng):
    p = os.path.join(d, "fleet_limits.toml")
    kv = dict(re.findall(r'(\w+) = "([^"]*)"', open(p).read()))
    open(p, "w").write("# fleet limits\nseason_end = '%s'  # last day\n\nseason_start   =   \"%s\"\nseason = \"%s\"\n"
                       % (kv["season_end"], kv["season_start"], kv["season"]))
    return True


def c_types(d, rng):
    p = os.path.join(d, "check_types.json")
    t = json.load(open(p))
    t2 = {k: {"overtime_shifts_per_day": v["overtime_shifts_per_day"], "max_compress_days": v["max_compress_days"]}
          for k, v in reversed(list(t.items()))}
    t2["Z"] = {"max_compress_days": 5, "overtime_shifts_per_day": 9}
    json.dump(t2, open(p, "w"))
    return True


def c_blankline(d, rng):
    p = os.path.join(d, "check_requests.csv")
    lines = open(p).read().split("\n")
    k = rng.randrange(2, len(lines) - 1)
    lines.insert(k, "")
    open(p, "w").write("\n".join(lines))
    return ("line_shift", k + 1)


# ---------- semantic mutators (expected = reference on the mutated folder) ----------
def season(d):
    kv = dict(re.findall(r'(\w+) = "([^"]*)"', open(os.path.join(d, "fleet_limits.toml")).read()))
    return kv


def planned_rows(d):
    kv = season(d)
    rows = rcsv(os.path.join(d, "check_requests.csv"))
    h = rows[0]
    return h, [r for r in rows[1:] if r[h.index("season")] == kv["season"] and r[h.index("status")] == "OPEN"], rows


def notice_avail_set(d, rng, datefn):
    """Put a planned tail into the notice tail table with a date from datefn(season kv)."""
    h, pl, _ = planned_rows(d)
    tail = rng.choice(pl)[h.index("tail")]
    kv = season(d)

    def fn(tbl, r2):
        row = ('<w:tr><w:tc><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r>'
               '<w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc></w:tr>' % (tail, datefn(kv, r2)))
        tbl = re.sub(r"<w:tr><w:tc><w:p><w:r><w:t xml:space=\"preserve\">%s</w:t>.*?</w:tr>" % tail, "", tbl,
                     flags=re.S)
        return tbl.replace("</w:tbl>", row + "</w:tbl>")
    edit_table(os.path.join(d, "disruption_notice.docx"), "tail", fn, rng)
    return False


def iso_add(s, n):
    return (R.dt.date.fromisoformat(s) + R.dt.timedelta(days=n)).isoformat()


def s_avail_after(d, rng):
    return notice_avail_set(d, rng, lambda kv, r: iso_add(kv["season_end"], r.randint(1, 20)))


def s_avail_before(d, rng):
    return notice_avail_set(d, rng, lambda kv, r: iso_add(kv["season_start"], -r.randint(1, 40)))


def s_avail_late_in(d, rng):
    return notice_avail_set(d, rng, lambda kv, r: iso_add(kv["season_end"], -r.randint(0, 15)))


def closure_row(datefn, daysfn):
    def mut(d, rng):
        kv = season(d)
        b = rng.choice(R.BASES)

        def fn(tbl, r2):
            row = ('<w:tr>' + "".join('<w:tc><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>' % c
                                      for c in (b, datefn(kv, r2), str(daysfn(r2)))) + '</w:tr>')
            return tbl.replace("</w:tbl>", row + "</w:tbl>")
        parts = dz_read(os.path.join(d, "disruption_notice.docx"))
        doc = parts["word/document.xml"].decode()
        for a, z in tables(doc):
            if header(doc[a:z])[:2] == ["base", "from"]:
                doc = doc[:a] + fn(doc[a:z], rng) + doc[z:]
                break
        parts["word/document.xml"] = doc.encode()
        dz_write(os.path.join(d, "disruption_notice.docx"), parts)
        return False
    return mut


def item_set(item, valfn):
    def mut(d, rng):
        def fn(tbl, r2):
            return re.sub(r"(%s</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t xml:space=\"preserve\">)(\d+)" % item,
                          lambda m: m.group(1) + str(valfn(int(m.group(2)), r2)), tbl)
        edit_table(os.path.join(d, "planning_limits.docx"), "item", fn, rng)
        return False
    return mut


def grants_set(valfn):
    def mut(d, rng):
        def fn(tbl, r2):
            return re.sub(r"(>(?:North|South|West|East)</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t "
                          r"xml:space=\"preserve\">)(\d+)", lambda m: m.group(1) + str(valfn(int(m.group(2)), r2)), tbl)
        parts = dz_read(os.path.join(d, "planning_limits.docx"))
        doc = parts["word/document.xml"].decode()
        for a, z in tables(doc):
            if header(doc[a:z])[:2] == ["base", "allowance_shifts"]:
                doc = doc[:a] + fn(doc[a:z], rng) + doc[z:]
        parts["word/document.xml"] = doc.encode()
        dz_write(os.path.join(d, "planning_limits.docx"), parts)
        return False
    return mut


def rows_edit(fn):
    def mut(d, rng):
        h, pl, rows = planned_rows(d)
        kv = season(d)
        fn(h, [r for r in rows[1:] if r in pl], rows, kv, rng, d)
        wcsv(os.path.join(d, "check_requests.csv"), rows)
        return False
    return mut


def e_dur1(h, pl, rows, kv, rng, d):
    for r in rng.sample(pl, min(4, len(pl))):
        r[h.index("duration_days")] = "1"


def e_due_far(h, pl, rows, kv, rng, d):
    for r in rng.sample(pl, min(4, len(pl))):
        r[h.index("due_date")] = iso_add(kv["season_start"], rng.choice([-60, -5, 200, 400]))


def e_avail_own_out(h, pl, rows, kv, rng, d):
    for r in rng.sample(pl, min(4, len(pl))):
        r[h.index("available_from")] = iso_add(kv["season_start"], rng.choice([-30, -1, 140, 300]))


def e_status_case(h, pl, rows, kv, rng, d):
    for r in rng.sample(pl, min(2, len(pl))):
        r[h.index("status")] = "Open"


def e_empty(h, pl, rows, kv, rng, d):
    del rows[1:]


def s_pub_outside(d, rng):
    h, pl, _ = planned_rows(d)
    ids = {r[0] for r in rng.sample(pl, min(4, len(pl)))}
    kv = season(d)
    rows = rcsv(os.path.join(d, "published_plan.csv"))
    for r in rows[1:]:
        if r[0] in ids:
            r[1] = iso_add(kv["season_start"], rng.choice([-20, -1, 140, 250]))
    wcsv(os.path.join(d, "published_plan.csv"), rows)
    return False


def s_ids_varlen(d, rng):
    h, pl, rows = planned_rows(d)
    ids = sorted({r[0] for r in pl})
    new = {}
    for i, old in enumerate(ids):
        new[old] = rng.choice(["Q", "Q-", "Qa"]) + str(rng.randint(1, 10 ** rng.randint(1, 5)))
    if len(set(new.values())) != len(new):
        raise Skip("collide")
    for r in rows[1:]:
        if r[0] in new and r in pl:
            r[0] = new[r[0]]
    wcsv(os.path.join(d, "check_requests.csv"), rows)
    pr = rcsv(os.path.join(d, "published_plan.csv"))
    for r in pr[1:]:
        if r[0] in new:
            r[0] = new[r[0]]
    wcsv(os.path.join(d, "published_plan.csv"), pr)
    return False


def s_calendar_random(d, rng):
    kv = season(d)
    a, z = kv["season_start"], kv["season_end"]
    p = os.path.join(d, "base_calendar.jsonl")
    out = []
    for ln in open(p):
        c = json.loads(ln)
        if a <= c["date"] <= z and rng.random() < 0.08:
            c["status"] = rng.choice(["OPEN", "NO_START", "CLOSED"])
        out.append(json.dumps(c))
    open(p, "w").write("\n".join(out) + "\n")
    return False


def s_rates(d, rng):
    def fn(tbl, r2):
        return re.sub(r'(<w:t xml:space="preserve">)(\d+)(</w:t>)',
                      lambda m: m.group(1) + str(r2.randint(1, 500)) + m.group(3), tbl)
    edit_table(os.path.join(d, "planning_limits.docx"), "class", fn, rng)
    p = os.path.join(d, "check_types.json")
    t = json.load(open(p))
    for v in t.values():
        v["max_compress_days"] = rng.randint(0, 4)
        v["overtime_shifts_per_day"] = rng.randint(1, 6)
    json.dump(t, open(p, "w"), indent=2)
    return False


MUT = {
    # Word package structure (data_conventions.md:20-23); expected = reference on the unmutated folder
    "D_sdt_row_allow": m_docx("sdt", "allow"), "D_sdt_row_closure": m_docx("sdt", "closure"),
    "D_sdt_row_avail": m_docx("sdt", "avail"), "D_sdt_row_item": m_docx("sdt", "item"),
    "D_sdt_row_class": m_docx("sdt", "class"), "D_sdt_allrows_allow": m_docx("sdt_all", "allow"),
    "D_cxml_row_allow": m_docx("customXml", "allow"), "D_cxml_row_closure": m_docx("customXml", "closure"),
    "D_cxml_row_avail": m_docx("customXml", "avail"), "D_cellsdt_allow": m_docx("cellsdt", "allow"),
    "D_sdt_tbl": both_docx(d_sdt_tbl), "D_sdt_run": both_docx(d_sdt_run), "D_split_runs": both_docx(d_split_runs),
    "D_rename_part": both_docx(d_rename_part), "D_abs_target": both_docx(d_target("/word/document.xml")),
    "D_dot_target": both_docx(d_target("./word/document.xml")), "D_extra_rels": both_docx(d_extra_rels),
    "D_decoy_table": both_docx(d_decoy), "D_tracked": both_docx(d_tracked), "D_altcontent": both_docx(d_altcontent),
    "D_altcontent_data": both_docx(d_altcontent_data),
    "D_alt_allow": m_alt("planning_limits.docx", "base", "allowance_shifts", 1),
    "D_alt_closure_days": m_alt("disruption_notice.docx", "base", "from", 2),
    "D_alt_avail": m_alt("disruption_notice.docx", "tail", "available_from", 1),
    "D_bookmarks": both_docx(d_bookmarks), "D_prefix": both_docx(d_prefix),
    "D_header_spaces": both_docx(d_header_spaces), "D_rowprops": both_docx(d_rowprops),
    # text formats (data_conventions.md:9-16, 31-46)
    "C_crlf": c_crlf, "C_quoted": c_quoted, "C_colorder": c_colorder, "C_extra_col": c_extra_col,
    "C_jsonl_style": c_jsonl, "C_toml_style": c_toml, "C_types_extra": c_types, "C_blankline": c_blankline,
    # semantic branches (planning/overtime/deferral/data_conventions); expected = reference on mutated folder
    "S_avail_after_end": s_avail_after, "S_avail_before_start": s_avail_before, "S_avail_late_in": s_avail_late_in,
    "S_closure_from_before": closure_row(lambda kv, r: iso_add(kv["season_start"], -r.randint(1, 10)),
                                         lambda r: r.randint(5, 20)),
    "S_closure_past_end": closure_row(lambda kv, r: iso_add(kv["season_end"], -r.randint(0, 10)),
                                      lambda r: r.randint(15, 60)),
    "S_closure_outside": closure_row(lambda kv, r: iso_add(kv["season_end"], r.randint(1, 30)),
                                     lambda r: r.randint(1, 9)),
    "S_pool0": item_set("overtime_pool_shifts", lambda v, r: 0),
    "S_pool_big": item_set("overtime_pool_shifts", lambda v, r: 999),
    "S_pool_small": item_set("overtime_pool_shifts", lambda v, r: r.randint(1, max(1, v // 3))),
    "S_shift_cost": item_set("shift_cost", lambda v, r: r.randint(1, 200)),
    "S_grants0": grants_set(lambda v, r: 0), "S_grants_big": grants_set(lambda v, r: v + r.randint(50, 500)),
    "S_grants_rand": grants_set(lambda v, r: r.randint(0, 40)),
    "S_dur1": rows_edit(e_dur1), "S_due_far": rows_edit(e_due_far), "S_avail_own_out": rows_edit(e_avail_own_out),
    "S_status_case": rows_edit(e_status_case), "S_empty_requests": rows_edit(e_empty),
    "S_pub_outside": s_pub_outside, "S_ids_varlen": s_ids_varlen, "S_calendar_random": s_calendar_random,
    "S_rates_types": s_rates,
}


def first_diff(got, want, path=""):
    if type(got) is not type(want) and not (isinstance(got, (int, float)) and isinstance(want, (int, float))):
        return "%s: %r vs %r" % (path, str(got)[:60], str(want)[:60])
    if isinstance(want, dict):
        for k in want:
            if k not in got:
                return "%s.%s missing" % (path, k)
            r = first_diff(got[k], want[k], "%s.%s" % (path, k))
            if r:
                return r
        extra = set(got) - set(want)
        return "%s extra %s" % (path, sorted(extra)[:3]) if extra else None
    if isinstance(want, list):
        if len(got) != len(want):
            return "%s len %d vs %d" % (path, len(got), len(want))
        for i, (g, w) in enumerate(zip(got, want)):
            r = first_diff(g, w, "%s[%d]" % (path, i))
            if r:
                return r
        return None
    return None if got == want else "%s: %r vs %r" % (path, got, want)


def run_a1(data, out, want, rec):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", A1, data, out], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        rec["verdict"] = "TIMEOUT"
        return rec
    rec["a1_s"] = round(time.time() - t0, 2)
    if p.returncode != 0:
        rec["verdict"] = "CRASH"
        rec["why"] = p.stderr.decode(errors="replace").strip().splitlines()[-1][:160] if p.stderr else ""
        return rec
    for n in NAMES:
        try:
            got = json.load(open(os.path.join(out, n)))
        except Exception as e:  # noqa: BLE001
            rec["verdict"] = "WRONG"
            rec["diff"] = "%s unreadable %r" % (n, e)
            return rec
        d = first_diff(got, want[n], n)
        if d:
            rec["verdict"] = "WRONG"
            rec["diff"] = d[:200]
            return rec
    rec["verdict"] = "EXACT"
    return rec


def ref(path, rec):
    t0 = time.time()
    try:
        w = json.loads(json.dumps(R.derive(path)))
    except Exception as e:  # noqa: BLE001
        rec["verdict"] = "REFCRASH"
        rec["why"] = repr(e)[:160]
        return None
    rec["ref_s"] = round(time.time() - t0, 2)
    return w


def job(args):
    """One generated folder; muts = list of mutator names (None = the branch folder itself)."""
    branch, seed, muts = args
    recs = []
    tmp = tempfile.mkdtemp(prefix="fz")
    try:
        orig = os.path.join(tmp, "orig")
        make_branch(branch, seed, orig)
        base = None
        for k, mut in enumerate(muts):
            rec = {"branch": branch, "mut": mut, "seed": seed}
            recs.append(rec)
            try:
                data, out = os.path.join(tmp, "d%d" % k), os.path.join(tmp, "o%d" % k)
                shutil.copytree(orig, data)
                os.makedirs(out)
                equiv, shift = True, None
                if mut:
                    rng = random.Random(seed * 101 + 7 + k)
                    try:
                        res = MUT[mut](data, rng)
                    except Skip as e:
                        rec["verdict"] = "SKIP"
                        rec["why"] = str(e)
                        continue
                    if isinstance(res, tuple):
                        shift = res[1]
                    elif res is False:
                        equiv = False
                if equiv:
                    if base is None:
                        base = ref(orig, rec)
                        if base is None:
                            break
                    want = json.loads(json.dumps(base))
                else:
                    want = ref(data, rec)
                    if want is None:
                        continue
                if shift:
                    for r in want["data_quality.json"]["rejected"]:
                        if r["line"] >= shift:
                            r["line"] += 1
                run_a1(data, out, want, rec)
            except Exception:  # noqa: BLE001
                rec["verdict"] = "HARNESS"
                rec["why"] = traceback.format_exc().strip().splitlines()[-1][:200]
            finally:
                shutil.rmtree(os.path.join(tmp, "d%d" % k), ignore_errors=True)
                shutil.rmtree(os.path.join(tmp, "o%d" % k), ignore_errors=True)
        return recs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    """mode branch: SEEDS branch folders per branch, each also gets one rotating equivalence mutator.
    mode equiv: N seeds, every D_/C_ mutator applied to each (reference computed once per seed).
    mode sem: N folders per S_ mutator."""
    log, mode, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else None
    eq = [m for m in MUT if m[0] in "DC" and (not only or m in only)]
    sem = [m for m in MUT if m[0] == "S" and (not only or m in only)]
    bl = list(BRANCH)
    jobs = []
    if mode == "branch":
        for j, b in enumerate(bl):
            jobs += [(b, 500000 + i * 13 + j, [None, eq[(i + j) % len(eq)]]) for i in range(n)]
    elif mode == "equiv":
        jobs = [(bl[i % len(bl)], 600000 + i * 19, eq) for i in range(n)]
    else:
        for m in sem:
            jobs += [(bl[i % len(bl)], 700000 + i * 17, [m]) for i in range(n)]
    shard = os.environ.get("SHARD")
    if shard:
        k, kk = map(int, shard.split("/"))
        jobs = [jb for x, jb in enumerate(jobs) if x % kk == k]
    skip = os.environ.get("SKIP")
    if skip:
        done = set()
        for line in open(skip):
            if line.startswith("{"):
                r = json.loads(line)
                done.add((r["branch"], r["seed"]))
        jobs = [jb for jb in jobs if (jb[0], jb[1]) not in done]
    total = 0
    with open(log, "a") as f, mp.Pool(2) as pool:
        for recs in pool.imap_unordered(job, jobs):
            for r in recs:
                f.write(json.dumps(r) + "\n")
                total += 1
            f.flush()
        f.write("ALL_DONE %d\n" % total)


if __name__ == "__main__":
    main()
