"""Minimal WordprocessingML writer (plain + 4 trap families) and readers (reference + kill slips).

Cell value spec: a plain string, or a tuple
  ("alt", stale_choice, current, stale_fallback[, suffix])   F2 mc:AlternateContent (+ plain run after it)
  ("move", current)                                F3 tracked move of the last digit
  ("delins", prefix, old, new)                     F4 w:del/w:delText + w:ins
F1 is document level: write(..., stale=tables_with_old_values) puts the main part at
word/main_document.xml (named by _rels/.rels) and the stale tables at word/document.xml.
"""
import re
import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
R_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
CT_MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def _run(t):
    return '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % escape(t)


def _cell_p(v, ids):
    if isinstance(v, str):
        return "<w:p>%s</w:p>" % _run(v)
    k = v[0]
    if k == "alt":
        return ('<w:p><mc:AlternateContent><mc:Choice Requires="wps">%s</mc:Choice>'
                '<mc:Choice Requires="w">%s</mc:Choice><mc:Fallback>%s</mc:Fallback>'
                '</mc:AlternateContent>%s</w:p>' % (_run(v[1]), _run(v[2]), _run(v[3]),
                                                     _run(v[4]) if len(v) > 4 else ""))
    if k == "move":
        cur = v[1]
        d, rest = cur[-1], cur[:-1]
        i = next(ids)
        a = 'w:author="Maintenance Control" w:date="2026-02-11T09:00:00Z"'
        return ('<w:p><w:moveFromRangeStart w:id="%d" w:name="m%d" %s/><w:moveFrom w:id="%d" %s>%s</w:moveFrom>'
                '<w:moveFromRangeEnd w:id="%d"/>%s<w:moveToRangeStart w:id="%d" w:name="m%d" %s/>'
                '<w:moveTo w:id="%d" %s>%s</w:moveTo><w:moveToRangeEnd w:id="%d"/></w:p>'
                % (i, i, a, i + 1, a, _run(d), i, _run(rest), i + 2, i, a, i + 3, a, _run(d), i + 2))
    if k == "delins":
        i = next(ids)
        a = 'w:author="Maintenance Control" w:date="2026-02-11T09:00:00Z"'
        return ('<w:p>%s<w:del w:id="%d" %s><w:r><w:delText>%s</w:delText></w:r></w:del>'
                '<w:ins w:id="%d" %s>%s</w:ins></w:p>' % (_run(v[1]), i, a, escape(v[2]), i + 1, a, _run(v[3])))
    raise ValueError(k)


def _body(blocks):
    ids = iter(range(10, 100000, 4))
    out = []
    for b in blocks:
        if b[0] == "p":
            out.append("<w:p>%s</w:p>" % _run(b[1]))
        else:
            rows = b[1]
            out.append("<w:tbl><w:tblPr><w:tblStyle w:val=\"TableGrid\"/></w:tblPr>")
            for r in rows:
                out.append("<w:tr>" + "".join("<w:tc>%s</w:tc>" % _cell_p(c, ids) for c in r) + "</w:tr>")
            out.append("</w:tbl>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="%s" xmlns:mc="%s" xmlns:wps="%s" mc:Ignorable="wps"><w:body>%s'
            '<w:sectPr/></w:body></w:document>' % (W, MC, WPS, "".join(out)))


def plain(v):
    """Current value of a cell spec."""
    if isinstance(v, str):
        return v
    return {"alt": lambda: v[2] + (v[4] if len(v) > 4 else ""), "move": lambda: v[1], "delins": lambda: v[1] + v[3]}[v[0]]()


def write(path, blocks, stale=None):
    main = "word/main_document.xml" if stale is not None else "word/document.xml"
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/%s" ContentType="%s"/></Types>' % (main, CT_MAIN))
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="%s" Target="%s"/></Relationships>' % (R_DOC, main))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        if stale is not None:
            z.writestr("word/document.xml", _body(stale))
        z.writestr(main, _body(blocks))


# ---------------- readers ----------------
import xml.etree.ElementTree as ET  # noqa: E402

MODES = ["ref", "join_all", "default_name", "always_fallback", "first_choice", "delete_unaware", "move_unaware",
         "drop_mc", "direct_runs", "naive"]


def _main_name(z, mode):
    if mode in ("default_name", "naive"):
        return "word/document.xml"
    rels = ET.fromstring(z.read("_rels/.rels"))
    for r in rels:
        if r.get("Type") == R_DOC:
            return r.get("Target").lstrip("/")
    raise ValueError("no officeDocument relationship")


def _text(el, mode, nsmap):
    tag = el.tag
    if tag == "{%s}moveFrom" % W and mode not in ("join_all", "move_unaware"):
        return ""
    if tag == "{%s}t" % W or (tag == "{%s}delText" % W and mode == "delete_unaware"):
        return el.text or ""
    if tag == "{%s}AlternateContent" % MC:
        kids = list(el)
        if mode == "drop_mc":
            return ""
        if mode == "join_all":
            return "".join(_text(k, mode, nsmap) for k in kids)
        if mode == "always_fallback":
            fb = [k for k in kids if k.tag == "{%s}Fallback" % MC]
            return _text(fb[0], mode, nsmap) if fb else ""
        for k in kids:
            if k.tag == "{%s}Choice" % MC:
                req = k.get("Requires", "").split()
                if mode == "first_choice" or all(nsmap.get(p) == W for p in req):
                    return "".join(_text(c, mode, nsmap) for c in k)
            elif k.tag == "{%s}Fallback" % MC:
                return "".join(_text(c, mode, nsmap) for c in k)
        return ""
    return "".join(_text(c, mode, nsmap) for c in el)


def _direct(p):
    return "".join(t.text or "" for r in p.findall("{%s}r" % W) for t in r.findall("{%s}t" % W))


def read_tables(path, mode="ref"):
    with zipfile.ZipFile(path) as z:
        raw = z.read(_main_name(z, mode))
    if mode == "naive":
        doc = raw.decode()
        tables = []
        for tb in re.findall(r"<w:tbl>.*?</w:tbl>", doc, re.S):
            rows = []
            for tr in re.findall(r"<w:tr>.*?</w:tr>", tb, re.S):
                rows.append(["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", tc)).strip()
                             for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)])
            tables.append(rows)
        return tables
    nsmap = {}
    import io
    for ev, (pfx, uri) in ET.iterparse(io.BytesIO(raw), events=("start-ns",)):
        nsmap[pfx] = uri
    root = ET.fromstring(raw)
    tables = []
    for tbl in root.iter("{%s}tbl" % W):
        rows = []
        for tr in tbl.findall("{%s}tr" % W):
            row = []
            for tc in tr.findall("{%s}tc" % W):
                ps = tc.findall("{%s}p" % W)
                if mode == "direct_runs":
                    row.append("".join(_direct(p) for p in ps).strip())
                else:
                    row.append("".join(_text(p, mode, nsmap) for p in ps).strip())
            rows.append(row)
        tables.append(rows)
    return tables
