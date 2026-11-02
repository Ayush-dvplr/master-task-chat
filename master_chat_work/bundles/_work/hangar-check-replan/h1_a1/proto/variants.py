"""h1 lever prototypes: restructure the Word tables of a generated folder without changing any value.

Every variant is valid WordprocessingML per ECMA-376 (data_conventions.md:20-23):
  sdt   rows of one table inside a repeating-section content control (Part 1, 17.5.2 row-level sdt)
  cxml  rows of one table inside custom XML row elements (Part 1, 17.5.1 row-level customXml)
  alt   value cells of one table carry mc:AlternateContent whose Choice and Fallback hold the same run
        (Part 3 markup compatibility; a consumer keeps exactly one branch)
Expected outputs are the reference on the folder before restructuring (values are unchanged).
"""
import re
import zipfile

W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
TABLES = {"allow": ("planning_limits.docx", ("base", "allowance_shifts"), 1),
          "close": ("disruption_notice.docx", ("base", "from"), 2),
          "avail": ("disruption_notice.docx", ("tail", "available_from"), 1)}
RUN = re.compile(r'<w:r><w:t xml:space="preserve">[^<]*</w:t></w:r>')


def _read(path):
    with zipfile.ZipFile(path) as z:
        return [(i, z.read(i.filename)) for i in z.infolist()]


def _write(path, items):
    with zipfile.ZipFile(path, "w") as z:
        for info, data in items:
            z.writestr(info, data)


def _cells(tr):
    return re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)


def _head(tbl):
    tr = re.search(r"<w:tr>.*?</w:tr>", tbl, re.S).group(0)
    return tuple(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", tr)[:2])


def _sdt(rows):
    items = "".join('<w:sdt><w:sdtPr><w:id w:val="%d"/><w15:repeatingSectionItem/></w:sdtPr><w:sdtContent>%s'
                    '</w:sdtContent></w:sdt>' % (900 + k, r) for k, r in enumerate(rows))
    return ('<w:sdt><w:sdtPr><w:alias w:val="rows"/><w:id w:val="899"/><w15:repeatingSection/></w:sdtPr>'
            '<w:sdtContent>%s</w:sdtContent></w:sdt>' % items)


def _cxml(rows):
    return "".join('<w:customXml w:uri="urn:planning" w:element="row">%s</w:customXml>' % r for r in rows)


def _alt(rows, cell):
    out = []
    for r in rows:
        c = _cells(r)[cell]
        run = RUN.search(c).group(0)
        choice = run.replace("<w:r>", '<w:r><w:rPr><w14:ligatures w14:val="standard"/></w:rPr>', 1)
        ac = ('<mc:AlternateContent><mc:Choice Requires="w14">%s</mc:Choice><mc:Fallback>%s</mc:Fallback>'
              '</mc:AlternateContent>' % (choice, run))
        out.append(r.replace(c, c.replace(run, ac, 1), 1))
    return "".join(out)


def restructure(data_dir, table, kind):
    """Rewrite one table of one Word file in data_dir; returns the number of data rows touched."""
    fname, head, cell = TABLES[table]
    path = "%s/%s" % (data_dir, fname)
    items = _read(path)
    k = [i for i, (info, _) in enumerate(items) if info.filename == "word/document.xml"][0]
    doc = items[k][1].decode()
    done = 0
    for m in re.finditer(r"<w:tbl>.*?</w:tbl>", doc, re.S):
        tbl = m.group(0)
        if _head(tbl) != head:
            continue
        rows = re.findall(r"<w:tr>.*?</w:tr>", tbl, re.S)
        data = rows[1:]
        assert data, "table %s has no data rows" % table
        body = {"sdt": _sdt, "cxml": _cxml}.get(kind, lambda rs: _alt(rs, cell))(data)
        new = tbl.replace("".join(data), body, 1)
        doc = doc[:m.start()] + new + doc[m.end():]
        done = len(data)
        break
    assert done, "no table %s" % table
    doc = doc.replace('<w:document xmlns:w="', '<w:document xmlns:mc="%s" xmlns:w14="%s" xmlns:w15="%s" '
                      'mc:Ignorable="w14 w15" xmlns:w="' % (MC, W14, W15), 1)
    items[k] = (items[k][0], doc.encode())
    _write(path, items)
    return done


VARIANTS = {"allow_sdt": ("allow", "sdt"), "allow_alt": ("allow", "alt"), "allow_cxml": ("allow", "cxml"), "close_sdt": ("close", "sdt"),
            "close_cxml": ("close", "cxml"), "close_alt": ("close", "alt"), "avail_sdt": ("avail", "sdt"),
            "avail_cxml": ("avail", "cxml"), "avail_alt": ("avail", "alt")}
