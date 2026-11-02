"""KVEC November 2025 settlement grader.

The first part regenerates the corpus deterministically from a seed (the
visible tier matches environment/data: byte-identical except the four SQLite
files, whose page bytes vary with the SQLite build while their rows are
identical); the last part holds the
rewardkit criteria."""
# ---------------------------------------------------------------------------
# KVEC settlement corpus generator: part 1 - deterministic utilities and
# raw writers for every container format the corpus uses.
# ---------------------------------------------------------------------------
import io
import json
import math
import sqlite3
import struct
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_FLOOR
from pathlib import Path

MASK64 = (1 << 64) - 1


class Rng:
    """xorshift64* seeded through splitmix64; stable across Python releases."""

    def __init__(self, seed):
        z = (int(seed) + 0x9E3779B97F4A7C15) & MASK64
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        z ^= z >> 31
        self.s = z or 0x1234567

    def u64(self):
        x = self.s
        x ^= (x >> 12)
        x ^= (x << 25) & MASK64
        x ^= (x >> 27)
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & MASK64

    def random(self):
        return (self.u64() >> 11) / float(1 << 53)

    def below(self, n):
        if n <= 0:
            raise ValueError(n)
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            v = self.u64()
            if v < limit:
                return v % n

    def randint(self, a, b):
        return a + self.below(b - a + 1)

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

    def chance(self, p):
        return self.random() < p

    def fork(self, tag):
        h = 1469598103934665603
        for ch in str(tag):
            h = ((h ^ ord(ch)) * 1099511628211) & MASK64
        return Rng(self.u64() ^ h)


def d2(x):
    return Decimal(x)


def q_even(value, exp="1"):
    return Decimal(value).quantize(Decimal(exp), rounding=ROUND_HALF_EVEN)


def int_even(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


# ---------------------------------------------------------------- time ----
# Settlement time zone: America/Chicago.  The only transition inside the
# settlement window is the fall-back at 2025-11-02 07:00:00Z (02:00 CDT ->
# 01:00 CST).  All conversions are explicit so no tz database is needed.
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
FALLBACK_UTC = int(datetime(2025, 11, 2, 7, 0, tzinfo=timezone.utc).timestamp())
MONTH_START = date(2025, 11, 1)
DAYS = [MONTH_START + timedelta(days=i) for i in range(30)]
BOUNDARY_DATES = [MONTH_START + timedelta(days=i) for i in range(31)]  # Nov1..Dec1


def offset_for_utc(ts):
    return -5 * 3600 if ts < FALLBACK_UTC else -6 * 3600


def local_to_utc(d, hh=0, mm=0, ss=0, fold=0):
    """Local wall time -> UTC epoch.  fold=1 selects CST in the repeated hour."""
    naive = int(datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=timezone.utc).timestamp())
    cdt = naive + 5 * 3600
    cst = naive + 6 * 3600
    cdt_valid = cdt < FALLBACK_UTC
    cst_valid = cst >= FALLBACK_UTC
    if cdt_valid and cst_valid:
        return cst if fold else cdt
    if cdt_valid:
        return cdt
    return cst


def utc_to_local(ts):
    off = offset_for_utc(ts)
    dt = datetime.fromtimestamp(ts + off, tz=timezone.utc).replace(tzinfo=None)
    return dt, ("CDT" if off == -5 * 3600 else "CST"), off


def iso_utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_local_offset(ts):
    dt, _abbr, off = utc_to_local(ts)
    sign = "-" if off < 0 else "+"
    h = abs(off) // 3600
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{h:02d}:00"


def excel_serial_local(ts):
    """Excel 1900-system serial of the LOCAL wall time (Lotus compatible)."""
    dt, _a, _o = utc_to_local(ts)
    base = datetime(1899, 12, 30)
    delta = dt - base
    return delta.days + delta.seconds / 86400.0


def date_add(d, n):
    return d + timedelta(days=n)


def drange(a, b):
    """Dates a <= x < b."""
    out = []
    x = a
    while x < b:
        out.append(x)
        x += timedelta(days=1)
    return out


# --------------------------------------------------------------- canon ----
HOMO_IN = {"K": "\u041a", "A": "\u0410", "C": "\u0421"}
FULLWIDTH = {str(i): chr(0xFF10 + i) for i in range(10)}


def id_variant(canon, kind):
    """Render a canonical KVnnnnnnn / ACnnnnnnnn identifier in a messy form."""
    head, num = canon[:2], canon[2:]
    if kind == "lower":
        return canon.lower()
    if kind == "space":
        return f" {head} {num} "
    if kind == "homoglyph":
        return HOMO_IN.get(head[0], head[0]) + head[1:] + num
    if kind == "unpadded":
        stripped = num.lstrip("0") or "0"
        return head + stripped
    if kind == "fullwidth":
        return head + "".join(FULLWIDTH[c] for c in num)
    return canon


def id_variant_kinds(canon):
    kinds = ["lower", "space", "homoglyph", "fullwidth"]
    if canon[2] == "0":
        kinds.append("unpadded")
    return kinds


# ------------------------------------------------------------- writers ----
ZIP_DT = (1980, 1, 1, 0, 0, 0)


def _zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def xml_esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _col_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheets):
    """sheets: list of (name, rows) where rows are lists of str/int/float/None.
    Strings are written as inline strings, numbers as numeric cells."""
    wb_sheets = []
    rels = []
    members = []
    ct_over = []
    for idx, (name, rows) in enumerate(sheets, 1):
        wb_sheets.append(f'<sheet name="{xml_esc(name)}" sheetId="{idx}" r:id="rId{idx}"/>')
        rels.append(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')
        ct_over.append(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, 1):
            cells = []
            for c, val in enumerate(row):
                if val is None or val == "":
                    continue
                ref = f"{_col_letter(c)}{r}"
                if isinstance(val, bool):
                    val = "TRUE" if val else "FALSE"
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    cells.append(f'<c r="{ref}"><v>{repr(val) if isinstance(val, float) else val}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_esc(val)}</t></is></c>')
            parts.append(f'<row r="{r}">' + "".join(cells) + "</row>")
        parts.append("</sheetData></worksheet>")
        members.append((f"xl/worksheets/sheet{idx}.xml", "".join(parts)))
    rels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                     + "".join(ct_over) + "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 "</Relationships>")
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                + "".join(wb_sheets) + "</sheets></workbook>")
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + "".join(rels) + "</Relationships>")
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
              '</styleSheet>')
    allm = [("[Content_Types].xml", content_types), ("_rels/.rels", root_rels),
            ("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", wb_rels),
            ("xl/styles.xml", styles)] + members
    Path(path).write_bytes(_zip_bytes(allm))


def write_docx(path, blocks, footer_text=None):
    """blocks: ("h", level, text) | ("p", text) | ("table", header, rows)."""
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    body = []
    for blk in blocks:
        if blk[0] == "h":
            body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading{blk[1]}"/></w:pPr><w:r><w:t xml:space="preserve">{xml_esc(blk[2])}</w:t></w:r></w:p>')
        elif blk[0] == "p":
            body.append(f'<w:p><w:r><w:t xml:space="preserve">{xml_esc(blk[1])}</w:t></w:r></w:p>')
        elif blk[0] == "table":
            rows = [blk[1]] + blk[2]
            trs = []
            for row in rows:
                tcs = "".join(f'<w:tc><w:p><w:r><w:t xml:space="preserve">{xml_esc(c)}</w:t></w:r></w:p></w:tc>' for c in row)
                trs.append(f"<w:tr>{tcs}</w:tr>")
            body.append('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/></w:tblPr>' + "".join(trs) + "</w:tbl>")
    sect = '<w:sectPr>' + ('<w:footerReference w:type="default" r:id="rId2"/>' if footer_text else "") + '</w:sectPr>'
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {W}><w:body>' + "".join(body) + sect + "</w:body></w:document>"
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles {W}>'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
              + "".join(f'<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/><w:basedOn w:val="Normal"/></w:style>' for i in (1, 2, 3))
              + '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style></w:styles>')
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
    over = ['<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>']
    members = [("word/document.xml", document), ("word/styles.xml", styles)]
    if footer_text:
        rels.append('<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>')
        over.append('<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>')
        members.append(("word/footer1.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:ftr {W}><w:p><w:r><w:t xml:space="preserve">{xml_esc(footer_text)}</w:t></w:r></w:p></w:ftr>'))
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>' + "".join(over) + "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                 "</Relationships>")
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>")
    Path(path).write_bytes(_zip_bytes([("[Content_Types].xml", content_types), ("_rels/.rels", root_rels),
                                       ("word/_rels/document.xml.rels", doc_rels)] + members))


def _pdf_escape(line):
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path, lines, lines_per_page=78):
    """Plain text-layer PDF: Courier 7pt, one text line per row, ASCII only."""
    for ln in lines:
        if any(ord(ch) > 126 for ch in ln):
            raise ValueError("pdf text must be ASCII: " + ln)
    pages = [lines[i:i + lines_per_page] for i in range(0, max(len(lines), 1), lines_per_page)] or [[]]
    objs = []

    def add(data):
        objs.append(data)
        return len(objs)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    pages_id = len(objs) + 1
    objs.append(None)
    page_ids = []
    for pg in pages:
        ops = ["BT", "/F1 7 Tf", "8.4 TL", "28 806 Td"]
        for ln in pg:
            ops.append(f"({_pdf_escape(ln)}) Tj T*")
        ops.append("ET")
        raw = ("\n".join(ops) + "\n").encode("latin-1")
        comp = zlib.compress(raw, 6)
        cid = add(b"<< /Length " + str(len(comp)).encode() + b" /Filter /FlateDecode >>\nstream\n" + comp + b"\nendstream")
        pid = add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {cid} 0 R >>".encode())
        page_ids.append(pid)
    objs[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>".encode()
    cat_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, data in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + data + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root {cat_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    Path(path).write_bytes(out.getvalue())


def write_parquet(path, columns, types):
    import pyarrow as pa
    import pyarrow.parquet as pq
    arrays = {}
    for name, values in columns.items():
        t = types[name]
        if t == "str":
            arrays[name] = pa.array(values, type=pa.string())
        elif t == "int":
            arrays[name] = pa.array(values, type=pa.int64())
        elif t == "float":
            arrays[name] = pa.array(values, type=pa.float64())
    table = pa.table(arrays)
    pq.write_table(table, str(path), compression="snappy", use_dictionary=False,
                   write_statistics=False, row_group_size=4096)


def write_sqlite(path, ddl_rows):
    """ddl_rows: list of (create_sql, insert_sql, rows)."""
    p = Path(path)
    if p.exists():
        p.unlink()
    con = sqlite3.connect(str(p))
    try:
        con.execute("PRAGMA page_size=4096")
        con.execute("PRAGMA journal_mode=DELETE")
        for create, insert, rows in ddl_rows:
            con.execute(create)
            con.executemany(insert, rows)
        con.commit()
        con.execute("VACUUM")
    finally:
        con.close()


def csv_line(fields, sep=","):
    out = []
    for f in fields:
        s = "" if f is None else str(f)
        if sep in s or '"' in s or "\n" in s or "\r" in s:
            s = '"' + s.replace('"', '""') + '"'
        out.append(s)
    return sep.join(out)


# ---------------------------------------------------------------------------
# KVEC settlement corpus generator: part 2 - entities and logical tables.
# Every table here is the canonical (post-parse) content of one or more of the
# 100 shipped files.  Part 3 computes the settlement truth from these tables;
# part 4 renders them, adding representation traps that never change meaning.
# ---------------------------------------------------------------------------
FEEDERS = [f"F{i:02d}" for i in range(1, 13)]
SUBSTATION = {f: ("north" if i < 3 else "east" if i < 6 else "south" if i < 9 else "west")
              for i, f in enumerate(FEEDERS)}
FEEDER_HES = {"F01": "A", "F02": "A", "F03": "B", "F04": "B", "F05": "C", "F06": "C",
              "F07": "D", "F08": "D", "F09": "E", "F10": "F", "F11": "F", "F12": "F"}
DISTRICT_OF = {f: ("north" if SUBSTATION[f] == "north" else "east" if SUBSTATION[f] == "east" else "southwest")
               for f in FEEDERS}
TERRITORIES = ["TN", "TE", "TS", "TW"]
HES_NAME = {"A": "aurora", "B": "borealis", "C": "cirrus", "D": "delta", "E": "cis_legacy", "F": "fjord"}
HES_CODE = {"A": "AUR", "B": "BOR", "C": "CIR", "D": "DLT", "E": "CIS", "F": "FJD"}
PERIODS6 = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 30)]   # boundary indexes (Nov1 = 0, Dec1 = 30)
PERIODS3 = [(1, 10), (11, 20), (21, 30)]
RATE_CODES = {
    "RES": [f"RES-{i:02d}" for i in range(1, 15)],
    "IND": [f"IND-{i:02d}" for i in range(1, 15)],
    "SGS": [f"SGS-{i:02d}" for i in range(1, 8)],
    "LGS": [f"LGS-{i:02d}" for i in range(1, 8)],
    "AGR": [f"AGR-{i:02d}" for i in range(1, 8)],
    "LIT": [f"LIT-{i:02d}" for i in range(1, 8)],
}
CODE_CLASS = {c: k for k, v in RATE_CODES.items() for c in v}
ALL_CODES = [c for v in RATE_CODES.values() for c in v]
DAYTYPES = ["WEEKDAY", "WEEKEND", "HOLIDAY", "CPP"]
RIDERS = ["R-FUEL", "R-ENV", "R-TRANS", "R-DSM", "R-NUC", "R-LIEAP"]
EXPORT_CODES = RATE_CODES["RES"] + RATE_CODES["SGS"]
CUTOFF_UTC = local_to_utc(date(2025, 12, 3), 17, 0, 0)
Q4_DATES = drange(date(2025, 10, 1), date(2026, 1, 1))
YEAR_DATES = drange(date(2025, 1, 1), date(2026, 1, 1))
DEC1 = date(2025, 12, 1)
NOV30 = date(2025, 11, 30)


def nov(d):
    return MONTH_START <= d < DEC1


def legacy_alias(code):
    cls, n = code.split("-")
    return {"RES": "R", "IND": "I", "SGS": "GS", "LGS": "LG", "AGR": "AG", "LIT": "L"}[cls] + str(int(n))


def read_file_name(hes, k):
    if hes == "E":
        return f"cis_legacy_reads_2025-11_{'abc'[k]}.txt"
    ext = {"A": "csv", "B": "xml", "C": "jsonl", "D": "parquet", "F": "tsv"}[hes]
    return f"{HES_NAME[hes]}_reads_2025-11_p{k + 1}.{ext}"


READ_FILES = [read_file_name(h, k) for h in "ABCDF" for k in range(6)] + [read_file_name("E", k) for k in range(3)]
RESEND_FILE = "fjord_reads_2025-11_p4b.tsv"


def hes_file_index(hes, bidx):
    for k, (a, z) in enumerate(PERIODS3 if hes == "E" else PERIODS6):
        if a <= bidx <= z:
            return k
    return None


class L:
    """Namespace of logical tables."""


def _rand_dec(r, lo, hi, places=3):
    scale = 10 ** places
    return Decimal(r.randint(int(lo * scale), int(hi * scale))) / Decimal(scale)


def sched_utc(read_time, bdate):
    if read_time == "23:00":
        return local_to_utc(bdate - timedelta(days=1), 23, 0, 0)
    return local_to_utc(bdate, 0, 0, 0)


def build_logical(seed):
    rng = Rng(seed)
    X = L()
    X.seed = seed
    X.traps = []          # semantic trap registry: dicts with file, key, family, rule, note
    X.used_ids = set()

    def new_id(prefix, digits, r, lead_zero=0.5):
        while True:
            lead = "0" if r.chance(lead_zero) else str(r.randint(1, 9))
            v = prefix + lead + "".join(str(r.randint(0, 9)) for _ in range(digits - 1))
            if v not in X.used_ids:
                X.used_ids.add(v)
                return v
    X.new_id = new_id
    _entities(X, rng.fork("entities"))
    _registry(X, rng.fork("registry"))
    _reads(X, rng.fork("reads"))
    _read_controls(X, rng.fork("controls"))
    _billing_refs(X, rng.fork("billing"))
    _tariffs(X, rng.fork("tariffs"))
    _lighting(X, rng.fork("lighting"))
    _scada(X, rng.fork("scada"))
    return X


def T(X, file, family, rule, key, note=""):
    X.traps.append({"file": file, "family": family, "rule": rule, "key": key, "note": note, "kind": "semantic"})


# ------------------------------------------------------------------ entities
def _entities(X, r):
    X.feeder_territory = {}
    order = TERRITORIES[:]
    r.shuffle(order)
    for i, f in enumerate(FEEDERS):
        X.feeder_territory[f] = order[i // 3] if not r.chance(0.25) else r.choice(TERRITORIES)
    X.feeder_loss_pct = {f: Decimal(r.randint(1850, 6400)) / Decimal(1000) for f in FEEDERS}
    X.meters = {}
    for f in FEEDERS:
        n = r.randint(506, 528)
        for _ in range(n):
            mid = X.new_id("KV", 7, r, 0.55)
            cls = r.choice(["RES"] * 70 + ["SGS"] * 9 + ["LGS"] * 7 + ["IND"] * 5 + ["AGR"] * 9)
            ct = cls in ("IND", "LGS") and r.chance(0.6)
            X.meters[mid] = {
                "id": mid, "feeder": f, "hes": FEEDER_HES[f], "cls": cls,
                "mult": r.choice([40, 80, 120, 200, 400]) if ct else 1,
                "digits": r.choice([5, 6, 6, 6, 7]) if not ct else r.choice([6, 7]),
                "nem": cls in ("RES", "SGS") and r.chance(0.10),
                "res": r.choice([1, 2, 3, 3, 3]),
                "clock": r.choice([0] * 88 + [180, -240, 420, -540, 600, 780, -840, 660, -720, 960, 300, -300]),
                "read_time": "23:00" if r.chance(0.03) else "00:00",
            }
    X.accounts = {}
    by_feeder = {}
    for mid in sorted(X.meters):
        by_feeder.setdefault(X.meters[mid]["feeder"], []).append(mid)
    for f in FEEDERS:
        ms = by_feeder[f]
        i = 0
        while i < len(ms):
            aid = X.new_id("AC", 8, r, 0.5)
            take = 2 if (r.chance(0.07) and i + 1 < len(ms)
                         and X.meters[ms[i]]["cls"] == X.meters[ms[i + 1]]["cls"]
                         and not X.meters[ms[i]]["nem"] and not X.meters[ms[i + 1]]["nem"]) else 1
            cls = X.meters[ms[i]]["cls"]
            X.accounts[aid] = {"id": aid, "cls": cls, "code": r.choice(RATE_CODES[cls]), "status": "ACTIVE",
                               "final": None, "feeder": f, "name": _cust_name(r, cls)}
            for m in ms[i:i + take]:
                X.meters[m]["account"] = aid
            i += take
    X.lit_accounts = []
    for _ in range(r.randint(62, 70)):
        aid = X.new_id("AC", 8, r, 0.5)
        f = r.choice(FEEDERS)
        X.accounts[aid] = {"id": aid, "cls": "LIT", "code": r.choice(RATE_CODES["LIT"]), "status": "ACTIVE",
                           "final": None, "feeder": f, "name": _cust_name(r, "LIT")}
        X.lit_accounts.append(aid)


FIRST = ["Avery", "Blake", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper", "Indy", "Jordan", "Kendall",
         "Logan", "Morgan", "Noel", "Oakley", "Parker", "Quinn", "Reese", "Sawyer", "Taylor"]
LAST = ["Abbott", "Brandt", "Castillo", "Dunmore", "Eklund", "Fairley", "Gutierrez", "Halvorsen", "Iverson",
        "Jaramillo", "Kowalczyk", "Lindqvist", "Mbeki", "Nakamura", "Okonkwo", "Pellegrini", "Quist", "Rasmussen"]
ORG = ["Prairie", "Kestrel", "Cedar", "Bluestem", "Ironwood", "Sandhill", "Willow", "Redtail", "Granite", "Marsh"]
ORG2 = ["Grain Coop", "Dairy", "Fabrication", "Cold Storage", "Clinic", "Hardware", "Bakery", "Feed Mill",
        "Machining", "Elevator", "Water District", "School District", "Township"]


def _cust_name(r, cls):
    if cls == "RES":
        return f"{r.choice(FIRST)} {r.choice(LAST)}"
    return f"{r.choice(ORG)} {r.choice(ORG2)}"


# ------------------------------------------------------------------ registry
def _registry(X, r):
    """SCD2 registry rows, account lifecycle, merges and rate history."""
    X.registry = {"north": [], "east": [], "southwest": []}
    X.master_extra = []
    X.merges = []
    X.late_merges = []
    X.rate_hist = []
    X.restated_reversals = []
    X.restated_rows = []
    X.migrations_2026 = []
    X.early_adopters = []
    X.schedule_rows = []
    meters = sorted(X.meters)
    eid = [100000]

    def entry():
        eid[0] += r.randint(1, 7)
        return eid[0]
    # historical accounts never active in November (move-outs in prior years)
    for m in meters:
        info = X.meters[m]
        dist = DISTRICT_OF[info["feeder"]]
        install = date(r.randint(2004, 2019), r.randint(1, 12), r.randint(1, 28))
        info["install"] = install
        ncut = r.randint(2, 4) if dist in ("north", "east") else r.randint(0, 3)
        cuts = sorted({date(r.randint(install.year + 1, 2024), r.randint(1, 12), r.randint(1, 28))
                       for _ in range(ncut) if install.year < 2024})
        starts = [install] + cuts
        mult_hist = info["mult"]
        for k, s in enumerate(starts):
            e = starts[k + 1] if k + 1 < len(starts) else None
            acct = info["account"] if e is None else None
            if acct is None:
                acct = X.new_id("AC", 8, r, 0.5)
                X.master_extra.append({"id": acct, "cls": info["cls"], "status": "FINAL", "final": e,
                                       "name": _cust_name(r, info["cls"]), "feeder": info["feeder"]})
            mlt = mult_hist if e is None else (mult_hist if r.chance(0.7) else r.choice([1, 40, 80, 120]) if mult_hist > 1 else 1)
            X.registry[dist].append({"meter": m, "account": acct, "mult": mlt, "hes": HES_CODE[info["hes"]],
                                     "from": s, "to": e, "reason": "INSTALL" if k == 0 else "MOVE_IN"})
        X.schedule_rows.append({"meter": m, "read_time": info["read_time"],
                                "from": date(r.randint(2016, 2024), r.randint(1, 12), 1)})
    # November lifecycle events
    pool = [m for m in meters if X.meters[m]["cls"] in ("RES", "SGS") and not X.meters[m]["nem"]]
    r.shuffle(pool)
    X.lifecycle = {"moves": [], "lags": [], "merge_meters": []}
    for m in pool[:34]:                       # move-out + move-in, registry updated
        info = X.meters[m]
        d = date(2025, 11, r.randint(3, 28))
        old = info["account"]
        if sum(1 for x in meters if X.meters[x]["account"] == old) > 1:
            continue
        new = X.new_id("AC", 8, r, 0.5)
        X.accounts[new] = {"id": new, "cls": info["cls"], "code": r.choice(RATE_CODES[info["cls"]]),
                           "status": "ACTIVE", "final": None, "feeder": info["feeder"],
                           "name": _cust_name(r, info["cls"])}
        X.accounts[old]["status"] = "FINAL"
        X.accounts[old]["final"] = d
        dist = DISTRICT_OF[info["feeder"]]
        cur = [x for x in X.registry[dist] if x["meter"] == m and x["to"] is None][0]
        cur["to"] = d
        X.registry[dist].append({"meter": m, "account": new, "mult": cur["mult"], "hes": cur["hes"],
                                 "from": d, "to": None, "reason": "MOVE_IN"})
        X.lifecycle["moves"].append((m, old, new, d))
    for m in pool[40:48]:                     # move-out, registry lag: vacancy days
        info = X.meters[m]
        acct = info["account"]
        if sum(1 for x in meters if X.meters[x]["account"] == acct) > 1:
            continue
        d = date(2025, 11, r.randint(4, 29))
        X.accounts[acct]["status"] = "FINAL"
        X.accounts[acct]["final"] = d
        X.lifecycle["lags"].append((m, acct, d))
        T(X, "cis_account_master.csv", "T13", "R-VACANCY", acct, "registry still links a FINAL account")
    # merges: predecessor account merged into successor (chains of two)
    acct_ids = sorted(a for a in X.accounts if X.accounts[a]["cls"] != "LIT" and X.accounts[a]["status"] == "ACTIVE")
    r.shuffle(acct_ids)
    used = set()
    k = 0
    for i in range(0, 60, 3):
        a, b, c = acct_ids[i], acct_ids[i + 1], acct_ids[i + 2]
        if X.accounts[a]["cls"] != X.accounts[b]["cls"]:
            continue
        d1 = date(2025, 11, r.randint(2, 20))
        X.merges.append({"id": f"MG-25-{9000 + k:05d}", "pred": a, "succ": b, "eff": d1, "status": "COMPLETED"})
        k += 1
        used |= {a, b}
        if i % 9 == 0 and X.accounts[b]["cls"] == X.accounts[c]["cls"]:
            d2 = date(2025, 11, r.randint(d1.day, 28))
            X.merges.append({"id": f"MG-25-{9000 + k:05d}", "pred": b, "succ": c, "eff": d2, "status": "COMPLETED"})
            k += 1
            T(X, "account_merges_2025.json", "T13", "R-MERGE-CHAIN", a, "merge chain resolves transitively")
        if i % 6 == 3:
            X.merges.append({"id": f"MG-25-{9000 + k:05d}", "pred": c, "succ": a, "eff": date(2025, 11, r.randint(2, 25)),
                             "status": "REVERSED"})
            k += 1
            T(X, "account_merges_2025.json", "T6", "R-MERGE-STATUS", c, "reversed merge")
    for i in range(60, 69, 2):                # late-posted merges, only in the December extract
        a, b = acct_ids[i], acct_ids[i + 1]
        if X.accounts[a]["cls"] != X.accounts[b]["cls"]:
            continue
        X.late_merges.append({"pred": a, "succ": b, "eff": date(2025, 11, r.randint(5, 27))})
        T(X, "cis_account_master_2025-12.csv", "T7", "R-LATE-MERGE", a, "late-posted merge inside the window")
    for i in range(70, 76, 2):                # December merges in the same extract: out of window
        a, b = acct_ids[i], acct_ids[i + 1]
        X.late_merges.append({"pred": a, "succ": b, "eff": date(2025, 12, r.randint(1, 15))})
        T(X, "cis_account_master_2025-12.csv", "T11", "R-LATE-MERGE", a, "merge effective in December")
    # historical merges for padding (pre-November)
    for _ in range(5200):
        a = X.new_id("AC", 8, r, 0.5)
        b = X.new_id("AC", 8, r, 0.5)
        X.merges.append({"id": f"MG-{r.randint(18, 25):02d}-{r.randint(10000, 89999):05d}", "pred": a, "succ": b,
                         "eff": date(r.randint(2018, 2025), r.randint(1, 10), r.randint(1, 28)),
                         "status": r.choice(["COMPLETED"] * 8 + ["REVERSED", "PENDING"])})
    for x in X.merges:
        if x["status"] == "PENDING" and x["pred"] in X.accounts:
            x["status"] = "COMPLETED"
    for nm in range(3):
        a = acct_ids[80 + nm]
        b = acct_ids[90 + nm]
        if X.accounts[a]["cls"] == X.accounts[b]["cls"]:
            X.merges.append({"id": f"MG-25-{9500 + nm:05d}", "pred": a, "succ": b, "eff": date(2025, 11, r.randint(5, 25)),
                             "status": "PENDING"})
            T(X, "account_merges_2025.json", "T6", "R-MERGE-STATUS", a, "pending merge not applied")
    # rate history: sheets 2024 and 2025, exactly 5000 rows each
    accts = sorted(X.accounts)
    hist24 = []
    hist25 = []
    no_hist = set(r.sample(accts, 260))
    for a in accts:
        if a in no_hist:
            continue
        acc = X.accounts[a]
        codes = RATE_CODES[acc["cls"]]
        hist24.append({"acct": a, "code": r.choice(codes), "from": date(2024, r.randint(1, 12), r.randint(1, 28))})
    r.shuffle(hist24)
    while len(hist24) > 5000:
        hist24.pop()
    in24 = {x["acct"] for x in hist24}
    for a in accts:
        if a in no_hist:
            continue
        acc = X.accounts[a]
        if a not in in24:
            hist25.append({"acct": a, "code": acc["code"], "from": date(2025, r.randint(1, 10), r.randint(1, 28))})
    for x in hist24:
        if r.chance(0.35):
            acc = X.accounts[x["acct"]]
            hist25.append({"acct": x["acct"], "code": acc["code"], "from": date(2025, r.randint(1, 10), r.randint(1, 28))})
        else:
            x["code"] = X.accounts[x["acct"]]["code"]
    # mid-November rate changes
    movers = [a for a in accts if a not in no_hist and X.accounts[a]["cls"] != "LIT"]
    r.shuffle(movers)
    for a in movers[:4]:
        acc = X.accounts[a]
        nc = r.choice([c for c in RATE_CODES[acc["cls"]] if c != acc["code"]])
        hist25.append({"acct": a, "code": nc, "from": date(2025, 11, r.randint(2, 29)), "tk": ("T11", "rate code change inside November")})
    for a in movers[40:42]:
        acc = X.accounts[a]
        nc = r.choice([c for c in RATE_CODES[acc["cls"]] if c != acc["code"]])
        hist25.append({"acct": a, "code": nc, "from": DEC1, "tk": ("T11", "change effective 2025-12-01")})
    # padding to exactly 5000 rows in 2025 with older historic changes
    while len(hist25) < 5000:
        a = r.choice(accts)
        if a in no_hist:
            continue
        hist25.append({"acct": a, "code": r.choice(RATE_CODES[X.accounts[a]["cls"]]),
                       "from": date(2025, r.randint(1, 3), r.randint(1, 28)), "pad": True})
    while len(hist25) > 5000:
        cand = [i for i, x in enumerate(hist25) if x.get("pad")]
        hist25.pop(cand[-1] if cand else -1)
    for x in hist24 + hist25:
        x["entry"] = entry()
        x["sheet"] = "2024" if x in hist24 else "2025"
    # legacy alias codes in history (resolved through the 2026 crosswalk aliases)
    for x in r.sample([h for h in hist25 if not h.get('pad')], 1):
        x["alias"] = True
        x["tk"] = ("T1", "legacy rate alias")
    # erroneous entries reversed in the restated workbook (decoy DC06)
    bad = r.sample([x for x in hist25 if X.accounts[x["acct"]]["cls"] != "LIT"], 26)
    for x in bad:
        wrong = {"acct": x["acct"], "code": r.choice([c for c in RATE_CODES[X.accounts[x["acct"]]["cls"]] if c != x["code"]]),
                 "from": date(2025, 11, r.randint(2, 26)), "entry": entry(), "sheet": "2025", "erroneous": True}
        hist25.append(wrong)
        X.restated_reversals.append({"entry": wrong["entry"], "acct": x["acct"], "reason": "KEYING_ERROR"})
        T(X, "account_rate_history_restated.xlsx", "T6", "R-RATE-REVERSAL", x["acct"], "entry reversed")
    # keep 2025 sheet at exactly 5000 by trimming padding
    pads = [x for x in hist25 if x.get("pad")]
    while len(hist25) > 5000 and pads:
        hist25.remove(pads.pop())
    X.rate_hist = hist24 + hist25
    for x in X.rate_hist:
        if "tk" in x:
            T(X, "account_rate_history.xlsx", x["tk"][0], "R-RATE-CODE", x["entry"], x["tk"][1])
    for _ in range(5000 - len(X.restated_reversals)):
        X.restated_reversals.append({"entry": r.randint(10000, 99999), "acct": X.new_id("AC", 8, r, 0.5),
                                     "reason": r.choice(["KEYING_ERROR", "DUPLICATE", "BACKDATED"])})
    # restated history (pull trap): cleaner single row per account but codes re-mapped
    for a in accts:
        acc = X.accounts[a]
        code = acc["code"] if r.chance(0.93) else r.choice(RATE_CODES[acc["cls"]])
        X.restated_rows.append({"acct": a, "code": code, "from": date(2025, 1, 1)})
    # 2026 crosswalk (decoy DC07): per-account migrations, early adopters in November
    for a in accts:
        acc = X.accounts[a]
        X.migrations_2026.append({"acct": a, "new_code": r.choice(RATE_CODES[acc["cls"]]), "eff": date(2026, 1, 1)})
    for a in r.sample([a for a in movers[60:] if X.accounts[a]["cls"] != "LIT"], 18):
        acc = X.accounts[a]
        d = date(2025, 11, r.randint(3, 27))
        nc = r.choice([c for c in RATE_CODES[acc["cls"]] if c != acc["code"]])
        X.early_adopters.append({"acct": a, "new_code": nc, "eff": d})
        T(X, "rate_code_crosswalk_2026.json", "T11", "R-EARLY-ADOPTER", a, "migration effective in November")
    # schedule changes inside November (23:00 <-> 00:00)
    for m in r.sample(meters, 6):
        d = date(2025, 11, r.randint(5, 26))
        info = X.meters[m]
        newt = "23:00" if info["read_time"] == "00:00" else "00:00"
        X.schedule_rows.append({"meter": m, "read_time": newt, "from": d})
        T(X, "kvec_settlement_procedures_manual.docx", "T11", "R-SCHEDULE", m, "schedule change in November")


# ------------------------------------------------------------------ reads
def _reads(X, r):
    meters = sorted(X.meters)
    pool = meters[:]
    r.shuffle(pool)
    X.exchanges = []
    X.ct_orders = []
    X.resets = []
    X.syncs = []
    used_special = set()

    def pick(n, cond):
        out = []
        for m in pool:
            if m in used_special or not cond(X.meters[m]):
                continue
            out.append(m)
            used_special.add(m)
            if len(out) == n:
                break
        return out
    exch = pick(30, lambda i: True)
    ctc = pick(6, lambda i: i["mult"] > 1)
    rst = pick(7, lambda i: not i["nem"])
    roll = pick(14, lambda i: i["digits"] == 5 and i["mult"] == 1)
    syncs = pick(7, lambda i: i["clock"] != 0)
    neg = pick(18, lambda i: True)
    X.special = {"exch": exch, "ctc": ctc, "rst": rst, "roll": roll, "sync": syncs, "neg": neg}
    for m in meters:
        info = X.meters[m]
        mod = Decimal(10) ** info["digits"]
        lo, hi = {"RES": (6, 45), "SGS": (20, 160), "LGS": (150, 900), "IND": (900, 9000), "AGR": (3, 220)}[info["cls"]]
        deltas = []
        for i, d in enumerate(DAYS):
            k = _rand_dec(r, lo, hi)
            if d.weekday() >= 5:
                k = (k * Decimal("0.8")).quantize(Decimal("0.001"))
            if info["mult"] > 1:
                k = (k / info["mult"]).quantize(Decimal("0.001"))
            deltas.append(k)
        info["has_exp"] = info["nem"] or (info["cls"] in ("RES", "SGS") and r.chance(0.002))
        info["d_exp"] = [_rand_dec(r, 0, 22) if info["has_exp"] else Decimal(0) for _ in DAYS]
        info["d_imp"] = deltas
        start = Decimal(r.randint(2000, int(mod) - 3000)) + Decimal(r.randint(0, 999)) / 1000
        if m in roll:
            tot = sum(deltas[:r.randint(6, 24)])
            start = mod - tot + Decimal(r.randint(5, 50)) / 10
            T(X, read_file_name(info["hes"], 0), "T15", "R-ROLLOVER", m, "register rolls over")
        info["start_imp"] = start
        info["start_exp"] = _rand_dec(r, 100, 9000) if info["has_exp"] else None
    for h in "ABCDEF":
        big = [m for m in meters if X.meters[m]["hes"] == h and X.meters[m]["cls"] in ("IND", "LGS") and m not in used_special]
        for m in r.sample(big, min(2, len(big))):
            used_special.add(m)
            i = r.randint(3, 27)
            X.meters[m]["d_imp"][i] = (X.meters[m]["d_imp"][i] * 25).quantize(Decimal("0.001"))
            X.meters[m]["spike"] = i
            T(X, read_file_name(h, hes_file_index(h, i + 1)), "T15", "R-OUTLIER", m, "large but valid consumption")
    # exchanges
    for m in exch:
        info = X.meters[m]
        d = r.randint(2, 27)
        t_ex = local_to_utc(DAYS[d], r.randint(9, 16), r.choice([0, 7, 15, 22, 30, 41, 48]), 0)
        new = X.new_id("KV", 7, r, 0.5)
        X.meters[new] = {k: v for k, v in info.items() if k not in ("d_imp", "d_exp", "start_imp", "start_exp")}
        X.meters[new].update({"id": new, "digits": r.choice([6, 7]), "clock": 0, "replaces": m, "install": DAYS[d]})
        X.meters[new]["d_imp"] = info["d_imp"]
        X.meters[new]["d_exp"] = info["d_exp"]
        frac = Decimal(r.randint(20, 80)) / 100
        X.exchanges.append({"old": m, "new": new, "day": d, "t": t_ex, "frac": frac,
                            "new_imp0": _rand_dec(r, 0, 9), "new_exp0": _rand_dec(r, 0, 3) if info["has_exp"] else None})
        info["exchange"] = X.exchanges[-1]
        X.meters[new]["installed"] = X.exchanges[-1]
        dist = DISTRICT_OF[info["feeder"]]
        cur = [x for x in X.registry[dist] if x["meter"] == m and x["to"] is None][0]
        cur["to"] = DAYS[d]
        X.registry[dist].append({"meter": new, "account": cur["account"], "mult": cur["mult"], "hes": cur["hes"],
                                 "from": DAYS[d], "to": None, "reason": "EXCHANGE"})
        X.schedule_rows.append({"meter": new, "read_time": info["read_time"], "from": DAYS[d]})
    for m in ctc:
        info = X.meters[m]
        d = r.randint(3, 27)
        t_c = local_to_utc(DAYS[d], r.randint(9, 15), r.choice([5, 20, 35, 50]), 0)
        nm = r.choice([x for x in (40, 80, 120, 200, 400, 600) if x != info["mult"]])
        X.ct_orders.append({"meter": m, "day": d, "t": t_c, "new": nm, "frac": Decimal(r.randint(25, 75)) / 100})
        info["ct"] = X.ct_orders[-1]
        if r.chance(0.5):        # registry updated the next day (consistent), else lagging
            dist = DISTRICT_OF[info["feeder"]]
            cur = [x for x in X.registry[dist] if x["meter"] == m and x["to"] is None][0]
            nd = DAYS[d] + timedelta(days=1 + r.randint(0, 3))
            cur["to"] = nd
            X.registry[dist].append({"meter": m, "account": cur["account"], "mult": nm, "hes": cur["hes"],
                                     "from": nd, "to": None, "reason": "CT_UPDATE"})
    for m in rst:
        d = r.randint(3, 27)
        X.resets.append({"meter": m, "day": d, "t": local_to_utc(DAYS[d], r.randint(1, 22), r.choice([3, 17, 33, 49]), 0),
                         "frac": Decimal(r.randint(10, 90)) / 100, "post": _rand_dec(r, 0, 5, 1)})
        X.meters[m]["reset"] = X.resets[-1]
    for m in syncs:
        d = r.randint(4, 25)
        X.syncs.append({"meter": m, "t": local_to_utc(DAYS[d], 12, r.randint(0, 59), 0), "corr": -X.meters[m]["clock"]})
        X.meters[m]["sync"] = X.syncs[-1]
    # register trajectories at each boundary (true values)
    for m in sorted(X.meters):
        info = X.meters[m]
        mod = Decimal(10) ** info["digits"]
        info["reg"] = {}
        info["regx"] = {}
        if "installed" in info:
            ex = info["installed"]
            d = ex["day"]
            v = ex["new_imp0"] + (info["d_imp"][d] * (1 - ex["frac"])).quantize(Decimal("0.001"))
            vx = None
            if ex["new_exp0"] is not None:
                vx = ex["new_exp0"] + (info["d_exp"][d] / 2).quantize(Decimal("0.001"))
            info["reg"][d + 1] = v % mod
            info["regx"][d + 1] = vx
            for b in range(d + 2, 31):
                v += info["d_imp"][b - 1]
                info["reg"][b] = v % mod
                if vx is not None:
                    vx += info["d_exp"][b - 1]
                info["regx"][b] = vx
            continue
        last = info["exchange"]["day"] if "exchange" in info else 30
        v = info["start_imp"]
        vx = info["start_exp"]
        info["reg"][0] = v % mod
        info["regx"][0] = vx
        mult = info["mult"]
        for b in range(1, last + 1):
            dlt = info["d_imp"][b - 1]
            ct = info.get("ct")
            if ct and ct["day"] == b - 1:
                part = (dlt * ct["frac"]).quantize(Decimal("0.001"))
                info["ct_read"] = (v + part) % mod
                dlt = part + ((dlt - part) * mult / ct["new"]).quantize(Decimal("0.001"))
            elif ct and b - 1 > ct["day"]:
                dlt = (dlt * mult / ct["new"]).quantize(Decimal("0.001"))
            rs = info.get("reset")
            if rs and rs["day"] == b - 1:
                part = (dlt * rs["frac"]).quantize(Decimal("0.001"))
                info["reset_pre"] = (v + part) % mod
                v = rs["post"] + (dlt - part)
            else:
                v = v + dlt
            info["reg"][b] = v % mod
            if vx is not None:
                vx += info["d_exp"][b - 1]
            info["regx"][b] = vx
        if "exchange" in info:
            ex = info["exchange"]
            d = ex["day"]
            info["final_imp"] = (info["reg"][d] + (info["d_imp"][d] * ex["frac"]).quantize(Decimal("0.001"))) % mod
            info["final_exp"] = None if vx is None else info["regx"][d] + (info["d_exp"][d] / 2).quantize(Decimal("0.001"))
    for m in sorted(X.meters):
        info = X.meters[m]
        q = Decimal(1).scaleb(-info["res"])
        for key in ("reg", "regx"):
            for b in list(info[key]):
                if info[key][b] is not None:
                    info[key][b] = info[key][b].quantize(q, rounding=ROUND_FLOOR)
        for key in ("final_imp", "final_exp", "ct_read", "reset_pre"):
            if info.get(key) is not None:
                info[key] = info[key].quantize(q, rounding=ROUND_FLOOR)
    for e in X.exchanges:
        q = Decimal(1).scaleb(-X.meters[e["new"]]["res"])
        e["new_imp0"] = e["new_imp0"].quantize(q, rounding=ROUND_FLOOR)
        if e["new_exp0"] is not None:
            e["new_exp0"] = e["new_exp0"].quantize(q, rounding=ROUND_FLOOR)
    for x in X.resets:
        x["post"] = x["post"].quantize(Decimal(1).scaleb(-X.meters[x["meter"]]["res"]), rounding=ROUND_FLOOR)
    _hes_rows(X, r.fork("rows"))


def _service_range(info):
    if "installed" in info:
        return range(info["installed"]["day"] + 1, 31)
    if "exchange" in info:
        return range(0, info["exchange"]["day"] + 1)
    return range(0, 31)


def read_time_on(X, m, bdate):
    best = None
    for row in X.schedule_rows:
        if row["meter"] == m and row["from"] <= bdate and (best is None or row["from"] > best["from"]):
            best = row
    return best["read_time"] if best else "00:00"


def _hes_rows(X, r):
    """One logical row per (meter, boundary) for boundaries 1..30, opening reads for 0."""
    X.reads = {fn: [] for fn in READ_FILES}
    X.opening = []
    sched_cache = {}
    for row in X.schedule_rows:
        sched_cache.setdefault(row["meter"], []).append(row)
    for m in sched_cache:
        sched_cache[m].sort(key=lambda x: x["from"])

    def rt(m, bdate):
        cur = "00:00"
        for row in sched_cache.get(m, []):
            if row["from"] <= bdate:
                cur = row["read_time"]
        return cur
    X.read_time_fn = rt
    for m in sorted(X.meters):
        info = X.meters[m]
        for b in _service_range(info):
            bdate = BOUNDARY_DATES[b]
            t_true = sched_utc(rt(m, bdate), bdate)
            jitter = r.choice([0] * 6 + [60, -60, 120, -180, 240, 300, -300, 420, -420])
            clock = info["clock"]
            if info.get("sync") and t_true + jitter >= info["sync"]["t"]:
                clock = 0
            row = {"meter": m, "b": b, "t": t_true + jitter + clock, "imp": info["reg"][b],
                   "exp": info["regx"].get(b) if info["has_exp"] else None, "seq": 0, "hes": info["hes"], "est": 0, "flags": [],
                   "sentinel": False}
            if b == 0:
                X.opening.append({"meter": m, "t": t_true, "imp": row["imp"], "exp": row["exp"],
                                  "status": "ACTUAL" if r.chance(0.97) else "ESTIMATED"})
                continue
            fn = read_file_name(info["hes"], hes_file_index(info["hes"], b))
            X.reads[fn].append(row)
    seq = [r.randint(10 ** 6, 2 * 10 ** 6)]
    for fn in READ_FILES:
        rows = X.reads[fn]
        rows.sort(key=lambda x: (x["b"], x["meter"]))
        for i in range(0, len(rows) - 1, 5):
            if r.chance(0.4):
                rows[i], rows[i + 1] = rows[i + 1], rows[i]
        for x in rows:
            seq[0] += r.randint(1, 3)
            x["seq"] = seq[0]
            x["file"] = fn


# ---------------------------------------------------------------------------
# part 2b - semantic read traps and the registers that resolve them
# ---------------------------------------------------------------------------
def _plain(X, m):
    i = X.meters[m]
    return not any(k in i for k in ("exchange", "installed", "ct", "reset", "spike")) and m not in X.special["roll"] \
        and m not in X.special["neg"]


def _bump(r, v):
    return (v + Decimal(r.randint(4000, 61000)) / Decimal(1000)).quantize(Decimal("0.001"))


def _spread(n_rows, k, r):
    """k distinct row indexes spread over n_rows in equal bands."""
    if n_rows == 0 or k == 0:
        return []
    out = []
    for i in range(k):
        lo = (n_rows * i) // k
        hi = max(lo, (n_rows * (i + 1)) // k - 1)
        out.append(r.randint(lo, hi))
    return sorted(set(out))


def _read_controls(X, r):
    X.voids = []
    X.corrections = []
    X.vee = []
    X.vee_reviews = []
    X.holds = []
    X.quarantine = []
    X.disputes = []
    X.reversals = []
    X.known_issues = []
    X.batch_partial = {}
    X.withdrawn = {}
    X.debug_echo = []
    hes_of_file = {}
    for fn in READ_FILES:
        for x in X.reads[fn]:
            hes_of_file[fn] = x["hes"]
            break
    est_seq = [700000]
    vee_traps = [0]
    corr_seq = [300000]

    def est_id():
        est_seq[0] += r.randint(1, 9)
        return f"VE{est_seq[0]}"

    def corr_id():
        corr_seq[0] += r.randint(1, 9)
        return f"RC{corr_seq[0]}"
    plan = ["VOID"] * 8 + ["CORR"] * 8 + ["HOLD"] * 8 + ["ISSUE"] * 8 + ["QUAR"] * 30 + ["DISP"] * 30
    infile = ["SENT", "EDGE", "DUP", "NEG", "STRAY"]
    while len(plan) < 33 * 8:
        plan.append(infile[len(plan) % 5])
    r.shuffle(plan)
    for fi, fn in enumerate(READ_FILES):
        rows = X.reads[fn]
        hes = hes_of_file[fn]
        picks = _spread(len(rows), 8, r)
        order = plan[fi * 8:(fi + 1) * 8]
        inserts = []
        for j, idx in enumerate(picks):
            row = rows[idx]
            m, b = row["meter"], row["b"]
            kind = order[j % len(order)]
            if not _plain(X, m) or b >= 30:
                kind = "STRAY" if (j % 2 and not _plain(X, m)) else "EDGE"
            bdate = BOUNDARY_DATES[b]
            info = X.meters[m]
            if kind == "VOID":
                row["imp"] = _bump(r, row["imp"])
                row["perturbed"] = True
                X.voids.append({"hes": HES_CODE[hes], "meter": m, "date": bdate, "reason": r.choice(["DUPLICATE_SEND", "METER_FAULT", "ROUTE_ERROR"]),
                                "reinstated": "N"})
                T(X, "mdm_void_register.csv", "T6", "R-VOID", (m, b), fn)
                if r.chance(0.5):
                    X.vee.append({"id": est_id(), "meter": m, "date": bdate, "imp": info["reg"][b], "exp": info["regx"].get(b),
                                  "version": 1, "created": bdate + timedelta(days=1)})
                    X.vee_reviews.append({"est": X.vee[-1]["id"], "status": "APPROVED", "on": bdate + timedelta(days=2)})
            elif kind == "CORR":
                good_imp = row["imp"]
                row["imp"] = _bump(r, row["imp"])
                row["perturbed"] = True
                X.corrections.append({"id": corr_id(), "meter": m, "date": bdate, "imp": _bump(r, good_imp), "exp": row["exp"],
                                      "rev": 1, "status": "REJECTED"})
                X.corrections.append({"id": corr_id(), "meter": m, "date": bdate, "imp": good_imp, "exp": row["exp"],
                                      "rev": 2, "status": "VALIDATED"})
                if r.chance(0.6):
                    X.corrections.append({"id": corr_id(), "meter": m, "date": bdate, "imp": _bump(r, good_imp),
                                          "exp": row["exp"], "rev": 3, "status": "PROVISIONAL"})
                T(X, "mdm_read_corrections.csv", "T7", "R-CORRECTION", (m, b), fn)
            elif kind == "SENT":
                row["sentinel"] = True
                T(X, fn, "T5", "R-SENTINEL", (m, b))
                lo = info["reg"][b - 1]
                hi = info["reg"][b + 1]
                if hi > lo and r.chance(0.75) and vee_traps[0] < 8:
                    vee_traps[0] += 1
                    span = hi - lo
                    e1 = (lo + span * Decimal(r.randint(30, 70)) / 100).quantize(Decimal("0.001"))
                    e2 = (lo + span * Decimal(r.randint(30, 70)) / 100).quantize(Decimal("0.001"))
                    ex = row["exp"]
                    a = {"id": est_id(), "meter": m, "date": bdate, "imp": e1, "exp": ex, "version": 1, "created": bdate + timedelta(days=1)}
                    c = {"id": est_id(), "meter": m, "date": bdate, "imp": e2, "exp": ex, "version": 2, "created": bdate + timedelta(days=2)}
                    X.vee += [a, c]
                    flip = r.chance(0.5)
                    X.vee_reviews.append({"est": a["id"], "status": "APPROVED", "on": bdate + timedelta(days=2)})
                    X.vee_reviews.append({"est": c["id"], "status": "REJECTED" if flip else "APPROVED", "on": bdate + timedelta(days=3)})
                    if flip:
                        X.vee_reviews.append({"est": c["id"], "status": "APPROVED", "on": bdate - timedelta(days=40)})
                    T(X, "vee_estimate_review_2025.xlsx", "T7", "R-VEE", (m, b), "latest review decides")
            elif kind == "EDGE":
                sched = sched_utc(X.read_time_fn(m, bdate), bdate)
                clock = info["clock"] if not (info.get("sync") and row["t"] >= info["sync"]["t"]) else 0
                inside = r.chance(0.5)
                shift = r.choice([900, -900]) if inside else (r.choice([901, -901, 1200, -1500]) if hes != "E" else r.choice([960, -960, 1200, -1500]))
                row["t"] = sched + shift + clock
                if not inside:
                    row["outside"] = True
                    if b >= 30 or not _plain(X, m) or r.chance(0.4):
                        pass
                    else:
                        X.vee.append({"id": est_id(), "meter": m, "date": bdate, "imp": info["reg"][b],
                                      "exp": info["regx"].get(b), "version": 1, "created": bdate + timedelta(days=1)})
                        X.vee_reviews.append({"est": X.vee[-1]["id"], "status": "APPROVED", "on": bdate + timedelta(days=1)})
                T(X, fn, "T11", "R-SNAP", (m, b), "inside" if inside else "outside")
            elif kind == "DUP":
                good = dict(row)
                if r.chance(0.5):
                    row["imp"] = _bump(r, row["imp"])
                    row["perturbed"] = True
                    good["seq"] = row["seq"] + 1
                    inserts.append((idx, good, "after"))
                    T(X, fn, "T7", "R-DUPLICATE", (m, b), "higher sequence wins at equal distance")
                else:
                    far = dict(row)
                    far["imp"] = _bump(r, row["imp"])
                    far["t"] = row["t"] + r.choice([1, -1]) * r.randint(400, 880)
                    if abs(far["t"] - (row["t"])) < 0:
                        pass
                    far["seq"] = row["seq"] + 1
                    far["perturbed"] = True
                    inserts.append((idx, far, "after"))
                    # make sure the original is closer to schedule than the far copy
                    sched = sched_utc(X.read_time_fn(m, bdate), bdate)
                    clock = info["clock"] if not (info.get("sync") and row["t"] >= info["sync"]["t"]) else 0
                    row["t"] = sched + clock + r.choice([0, 60, -60])
                    far["t"] = sched + clock + r.choice([1, -1]) * r.randint(420, 880)
                    T(X, fn, "T1", "R-DUPLICATE", (m, b), "closest to schedule wins")
            elif kind == "HOLD":
                released = r.chance(0.5)
                t_hold = local_to_utc(bdate, 6, r.randint(0, 59), 0)
                X.holds.append({"meter": m, "date": bdate, "type": "HOLD", "t": t_hold})
                if released:
                    X.holds.append({"meter": m, "date": bdate, "type": "RELEASE", "t": t_hold + r.randint(2, 9) * 86400})
                else:
                    if r.chance(0.5):
                        X.holds.append({"meter": m, "date": bdate, "type": "RELEASE", "t": CUTOFF_UTC + r.randint(3600, 86400 * 4)})
                    row["imp"] = _bump(r, row["imp"])
                    row["perturbed"] = True
                T(X, "mdm_ops_mailbox_2025-11.mbox", "T6", "R-HOLD", (m, b), "released" if released else "held")
            elif kind == "QUAR":
                row["imp"] = _bump(r, row["imp"])
                row["perturbed"] = True
                X.quarantine.append({"meter": m, "date": bdate, "hes": HES_CODE[hes], "reason": r.choice(["SPIKE_RULE", "CLOCK_RULE", "CRC"])})
                T(X, "hes_ingest_debug.log", "T6", "R-QUARANTINE", (m, b), fn)
            elif kind == "DISP":
                upheld = r.chance(0.6)
                if upheld:
                    row["imp"] = _bump(r, row["imp"])
                    row["perturbed"] = True
                X.disputes.append({"meter": m, "date": bdate, "outcome": "UPHELD" if upheld else "NOT UPHELD",
                                   "case": f"DSP-{r.randint(10000, 99999)}"})
                T(X, "customer_portal_usage_export.html", "T6", "R-DISPUTE", (m, b), "upheld" if upheld else "not upheld")
            elif kind == "ISSUE":
                code = r.choice((["WH_AS_KWH"] if hes not in ("E",) else []) + ["STUCK_REGISTER"] + (["SWAP_REGISTERS"] if row["exp"] is not None else []))
                if code == "WH_AS_KWH":
                    row["imp"] = row["imp"] * 1000
                    if row["exp"] is not None:
                        row["exp"] = row["exp"] * 1000
                elif code == "STUCK_REGISTER":
                    row["imp"] = info["reg"][b - 1]
                    row["perturbed"] = True
                    if r.chance(0.5):
                        X.vee.append({"id": est_id(), "meter": m, "date": bdate, "imp": info["reg"][b],
                                      "exp": info["regx"].get(b), "version": 1, "created": bdate + timedelta(days=1)})
                        X.vee_reviews.append({"est": X.vee[-1]["id"], "status": "APPROVED", "on": bdate + timedelta(days=1)})
                else:
                    row["imp"], row["exp"] = row["exp"], row["imp"]
                X.known_issues.append({"id": f"KI-{r.randint(100, 999)}", "code": code, "meter": m, "date": bdate,
                                       "hes": HES_CODE[hes], "status": "OPEN"})
                T(X, "hes_known_issues.md", "T14", "R-KNOWN-ISSUE", (m, b), code)
            elif kind == "NEG":
                row["imp"] = (info["reg"][b - 1] - Decimal(r.randint(1, 900)) / 1000).quantize(Decimal("0.001"))
                if row["imp"] < 0:
                    row["imp"] = info["reg"][b]
                else:
                    row["perturbed"] = True
                    T(X, fn, "T15", "R-NEGATIVE", (m, b), "unexplained negative delta invalidates boundary")
            elif kind == "STRAY":
                exm = [e for e in X.exchanges if X.meters[e["old"]]["hes"] == hes] if hes != "D" else []
                if exm:
                    e = r.choice(exm)
                    old = e["old"]
                    bb = min(30, e["day"] + 2 + r.randint(0, 2))
                    bd = BOUNDARY_DATES[bb]
                    stray = {"meter": old, "b": bb, "t": sched_utc(X.read_time_fn(old, bd), bd), "imp": X.meters[old].get("final_imp", Decimal(1)) + Decimal(r.randint(1, 9)),
                             "exp": None, "seq": row["seq"], "hes": hes, "est": 0, "flags": [], "sentinel": False,
                             "stray": True, "file": fn}
                    inserts.append((idx, stray, "after"))
                    T(X, fn, "T13", "R-REMOVED-METER", (old, bb), "read after meter removal")
                else:
                    ghost = dict(row)
                    ghost["meter"] = "GHOST:" + X.new_id("KV", 7, r, 0.5)
                    ghost["stray"] = True
                    inserts.append((idx, ghost, "after"))
                    T(X, fn, "T13", "R-UNKNOWN-METER", ghost["meter"], "unknown meter")
        for idx, new, _pos in sorted(inserts, key=lambda z: -z[0]):
            new = dict(new)
            new["file"] = fn
            rows.insert(idx + 1, new)
    # batch control: partial rejections and vendor withdrawals (row ordinals are 1-based)
    partial_files = set(r.sample(READ_FILES, 7))
    for fn in READ_FILES:
        rows = X.reads[fn]
        n = len(rows)
        if fn in partial_files:
            a = r.randint(n // 5, (4 * n) // 5)
            z = a + r.randint(2, 6)
            ok = all(not rows[i].get("perturbed") and not rows[i].get("stray") and not rows[i].get("sentinel")
                     and not rows[i].get("outside") for i in range(a - 1, z))
            if ok:
                for i in range(a - 1, z):
                    rows[i]["imp"] = _bump(r, rows[i]["imp"])
                    rows[i]["perturbed"] = True
                    rows[i]["batch_reject"] = True
                X.batch_partial[fn] = (a, z)
                T(X, "mdm_batch_control.log", "T6", "R-BATCH", fn, f"rows {a}-{z}")
        if r.chance(0.3):
            a = r.randint(n // 6, (5 * n) // 6)
            z = a + r.randint(1, 4)
            ok = all(not rows[i].get("perturbed") and not rows[i].get("stray") and not rows[i].get("sentinel")
                     and not rows[i].get("outside") for i in range(a - 1, z))
            if ok:
                for i in range(a - 1, z):
                    rows[i]["imp"] = _bump(r, rows[i]["imp"])
                    rows[i]["perturbed"] = True
                    rows[i]["withdrawn"] = True
                X.withdrawn[fn] = (a, z)
                T(X, "hes_batch_manifest_2025-11.json", "T6", "R-WITHDRAWN", fn, f"rows {a}-{z}")
    # voids that were reinstated (do not apply): on unperturbed plain rows
    for fn in READ_FILES[::9]:
        rows = X.reads[fn]
        for idx in _spread(len(rows), 2, r):
            row = rows[idx]
            if row.get("perturbed") or row.get("stray") or row["meter"].startswith("GHOST"):
                continue
            X.voids.append({"hes": HES_CODE[row["hes"]], "meter": row["meter"], "date": BOUNDARY_DATES[row["b"]],
                            "reason": "ROUTE_ERROR", "reinstated": "Y"})
            T(X, "mdm_void_register.csv", "T7", "R-VOID", (row["meter"], row["b"]), "reinstated void")
            break
    # Fjord resend: reversal lines for some P4 reads
    p4 = X.reads[read_file_name("F", 3)]
    for idx in _spread(len(p4), 8, r):
        row = p4[idx]
        if row.get("perturbed") or row.get("stray") or row.get("sentinel") or row.get("outside"):
            continue
        row["imp"] = _bump(r, row["imp"])
        row["perturbed"] = True
        row["reversed"] = True
        X.reversals.append({"meter": row["meter"], "b": row["b"], "seq": row["seq"]})
        T(X, RESEND_FILE, "T6", "R-REVERSAL", (row["meter"], row["b"]), "reversal honoured")
    # opening reads: corrections on the Nov 1 boundary
    for o in r.sample([o for o in X.opening if _plain(X, o["meter"])], 6):
        good = o["imp"]
        o["imp"] = _bump(r, o["imp"])
        X.corrections.append({"id": corr_id(), "meter": o["meter"], "date": MONTH_START, "imp": good, "exp": o["exp"],
                              "rev": 1, "status": "VALIDATED"})
        T(X, "mdm_october_close_reads.csv", "T7", "R-CORRECTION", (o["meter"], 0), "opening corrected")
    # YTD padding for the registers (prior months; boundary 2025-10-31 is outside, 2025-12-01 inside)
    mlist = sorted(m for m in X.meters)
    while len(X.voids) < 5600:
        m = r.choice(mlist)
        d = date(2025, r.randint(1, 10), r.randint(1, 28))
        if r.chance(0.01):
            d = date(2025, 10, 31)
        X.voids.append({"hes": HES_CODE[X.meters[m]["hes"]], "meter": m, "date": d,
                        "reason": r.choice(["DUPLICATE_SEND", "METER_FAULT", "ROUTE_ERROR", "TEST_READ"]),
                        "reinstated": r.choice(["N", "N", "N", "Y"])})
    X.voids.sort(key=lambda v: (v["meter"], v["date"]))
    for i, v in enumerate(X.voids):
        v["id"] = f"VD{400000 + i * 3 + r.randint(0, 2)}"
    while len(X.corrections) < 5400:
        m = r.choice(mlist)
        d = date(2025, r.randint(1, 10), r.randint(1, 28))
        if r.chance(0.01):
            d = date(2025, 10, 31)
        X.corrections.append({"id": corr_id(), "meter": m, "date": d, "imp": _rand_dec(r, 100, 90000),
                              "exp": None, "rev": r.randint(1, 3), "status": r.choice(["VALIDATED", "PROVISIONAL", "REJECTED"])})
    X.corrections.sort(key=lambda c: (c["meter"], c["date"], c["rev"]))
    while len(X.vee) < 5300:
        m = r.choice(mlist)
        d = date(2025, r.randint(1, 10), r.randint(1, 28))
        X.vee.append({"id": est_id(), "meter": m, "date": d, "imp": _rand_dec(r, 100, 90000), "exp": None,
                      "version": r.randint(1, 3), "created": d + timedelta(days=1)})
    ids = [v["id"] for v in X.vee]
    reviewed = {x["est"] for x in X.vee_reviews}
    for v in X.vee:
        if v["id"] not in reviewed and v["date"] < MONTH_START:
            X.vee_reviews.append({"est": v["id"], "status": r.choice(["APPROVED", "APPROVED", "REJECTED"]),
                                  "on": v["date"] + timedelta(days=r.randint(1, 5))})
    old_ids = [v["id"] for v in X.vee if v["date"] < MONTH_START]
    while len(X.vee_reviews) < 10000:
        X.vee_reviews.append({"est": r.choice(old_ids), "status": "REJECTED", "on": date(2025, r.randint(1, 10), r.randint(1, 28))})
    for v in X.vee_reviews:
        if v["on"] >= MONTH_START and v["est"] in reviewed:
            pass
    X.vee.sort(key=lambda v: (v["meter"], v["date"], v["version"]))
    # known issues padding
    while len(X.known_issues) < 5200:
        m = r.choice(mlist)
        X.known_issues.append({"id": f"KI-{r.randint(100, 999)}", "code": r.choice(["WH_AS_KWH", "STUCK_REGISTER", "SWAP_REGISTERS"]),
                               "meter": m, "date": date(2025, r.randint(1, 10), r.randint(1, 28)),
                               "hes": HES_CODE[X.meters[m]["hes"]], "status": r.choice(["OPEN", "CLOSED"])})
    X.known_issues.sort(key=lambda k: (k["meter"], k["date"]))
    # mailbox padding: holds and releases from earlier months
    while len(X.holds) < 5400:
        m = r.choice(mlist)
        d = date(2025, r.randint(1, 10), r.randint(1, 28))
        t = local_to_utc(d, 6, r.randint(0, 59), 0)
        X.holds.append({"meter": m, "date": d, "type": "HOLD", "t": t})
        if r.chance(0.8):
            X.holds.append({"meter": m, "date": d, "type": "RELEASE", "t": t + r.randint(1, 6) * 86400})
    X.holds.sort(key=lambda h: h["t"])
    # quarantine padding (other months) + parse echo lines for the debug log
    while len(X.quarantine) < 300:
        m = r.choice(mlist)
        X.quarantine.append({"meter": m, "date": date(2025, r.randint(1, 10), r.randint(1, 28)),
                             "hes": HES_CODE[X.meters[m]["hes"]], "reason": r.choice(["SPIKE_RULE", "CLOCK_RULE", "CRC"])})
    while len(X.disputes) < 60:
        m = r.choice(mlist)
        X.disputes.append({"meter": m, "date": date(2025, r.randint(1, 10), r.randint(1, 28)),
                           "outcome": r.choice(["UPHELD", "NOT UPHELD"]), "case": f"DSP-{r.randint(10000, 99999)}"})


# ------------------------------------------------------------------ billing references
def _billing_refs(X, r):
    meters = sorted(X.meters)
    accts = sorted(X.accounts)
    # field service orders
    X.orders = []
    oid = [r.randint(5000000, 6000000)]

    def order_id():
        oid[0] += r.randint(1, 40)
        return f"WO{oid[0]}"
    for e in X.exchanges:
        o = X.meters[e["old"]]
        X.orders.append({"id": order_id(), "type": "EXCHANGE", "status": "COMPLETED", "t": e["t"], "old": e["old"], "new": e["new"],
                         "old_imp": o["final_imp"], "old_exp": o.get("final_exp"), "new_imp": e["new_imp0"], "new_exp": e["new_exp0"]})
        if r.chance(0.12):
            X.orders.append({"id": order_id(), "type": "EXCHANGE", "status": "CANCELLED", "t": e["t"] - 86400 * r.randint(1, 4),
                             "old": e["old"], "new": X.new_id("KV", 7, r, 0.5), "old_imp": o["final_imp"] - Decimal(3),
                             "old_exp": None, "new_imp": Decimal(0), "new_exp": None})
            T(X, "field_service_orders.jsonl", "T6", "R-ORDER-STATUS", X.orders[-1]["id"], "cancelled exchange order")
    for c in X.ct_orders:
        info = X.meters[c["meter"]]
        X.orders.append({"id": order_id(), "type": "CT_CHANGE", "status": "COMPLETED", "t": c["t"], "meter": c["meter"],
                         "old_ratio": info["mult"], "new_ratio": c["new"], "read": info["ct_read"]})
        T(X, "field_service_orders.jsonl", "T2", "R-CT-CHANGE", X.orders[-1]["id"], "multiplier changes mid-day")
    while len(X.orders) < 5500:
        m = r.choice(meters)
        d = date(2025, r.randint(1, 11), r.randint(1, 28))
        t = local_to_utc(d, r.randint(8, 17), r.randint(0, 59), 0)
        kind = r.choice(["INSPECTION", "INSPECTION", "SEAL_CHECK", "RECONNECT_VISIT"])
        X.orders.append({"id": order_id(), "type": kind, "status": r.choice(["COMPLETED", "COMPLETED", "CANCELLED"]),
                         "t": t, "meter": m})
    X.orders.sort(key=lambda o: o["t"])
    # CT ratio verifications (2 sheets x 5000)
    X.ct_verif = []
    ctm = [m for m in meters if X.meters[m]["mult"] > 1 and "ct" not in X.meters[m] and "exchange" not in X.meters[m]
           and "installed" not in X.meters[m]]
    corr = r.sample(ctm, min(5, len(ctm)))
    X.ct_fixes = []
    for m in corr:
        d = date(2025, 11, r.randint(3, 26))
        newr = r.choice([X.meters[m]["mult"] * 2, X.meters[m]["mult"] // 2])
        X.ct_verif.append({"id": f"CV{r.randint(10000, 99999)}", "meter": m, "on": d, "reg": X.meters[m]["mult"],
                           "measured": newr, "result": "FAIL", "action": "CORRECT_RATIO", "half": "H2"})
        X.ct_fixes.append((m, d, newr))
        T(X, "ct_ratio_verification_2025.xlsx", "T2", "R-CT-VERIFY", (m, d), "verified ratio replaces registry ratio")
    for m in r.sample(ctm, 2):
        if m in corr:
            continue
        dd = date(2025, 11, r.randint(3, 26))
        X.ct_verif.append({"id": f"CV{r.randint(10000, 99999)}", "meter": m, "on": dd,
                           "reg": X.meters[m]["mult"], "measured": X.meters[m]["mult"] * 2, "result": "FAIL", "action": "REFER_ENGINEERING",
                           "half": "H2"})
        T(X, "ct_ratio_verification_2025.xlsx", "T6", "R-CT-VERIFY", (m, dd), "failed test without correction action")
    for half, months in (("H1", range(1, 7)), ("H2", range(7, 11))):
        while sum(1 for v in X.ct_verif if v["half"] == half) < 5000:
            m = r.choice(meters)
            reg = X.meters[m]["mult"]
            X.ct_verif.append({"id": f"CV{r.randint(10000, 99999)}", "meter": m, "on": date(2025, r.choice(list(months)), r.randint(1, 28)),
                               "reg": reg, "measured": reg, "result": "PASS", "action": "NONE", "half": half})
    # net metering enrollments and export inspections
    X.nem = []
    X.inspections = []
    nem_m = [m for m in meters if X.meters[m]["nem"]]
    for m in nem_m:
        acct = X.meters[m]["account"]
        start = date(r.randint(2016, 2025), r.randint(1, 12), r.randint(1, 28))
        if start >= MONTH_START:
            start = date(2024, start.month, start.day)
        X.nem.append({"app": f"NM{r.randint(100000, 999999)}", "meter": m, "acct": acct, "status": "APPROVED", "from": start, "to": None})
        X.inspections.append({"meter": m, "on": date(2025, r.randint(1, 6), r.randint(1, 28)), "result": "PASS"})
    for m in r.sample(nem_m, 6):
        x = [n for n in X.nem if n["meter"] == m][0]
        x["to"] = date(2025, 11, r.randint(5, 25))
        T(X, "netmetering_enrollments.csv", "T11", "R-NEM", x["app"], "enrollment ends in November")
    for m in r.sample(nem_m, 6):
        dd = date(2025, 11, r.randint(3, 20))
        X.inspections.append({"meter": m, "on": dd, "result": "FAIL"})
        T(X, "export_meter_inspections_2025.xlsx", "T6", "R-INSPECTION", (m, dd), "failed inspection stops export credit")
    late = [m for m in meters if X.meters[m]["has_exp"] and not X.meters[m]["nem"]]
    for m in late:
        # export register present on the meter but the application was denied
        X.nem.append({"app": f"NM{r.randint(100000, 999999)}", "meter": m, "acct": X.meters[m]["account"], "status": "DENIED",
                      "from": date(2025, 11, 10), "to": None})
        T(X, "netmetering_enrollments.csv", "T6", "R-NEM", X.nem[-1]["app"], "denied application")
    while len(X.nem) < 5300:
        m = r.choice(meters)
        X.nem.append({"app": f"NM{r.randint(100000, 999999)}", "meter": m, "acct": X.meters[m].get("account"),
                      "status": r.choice(["DENIED", "WITHDRAWN"]), "from": date(r.randint(2015, 2025), r.randint(1, 10), r.randint(1, 28)), "to": None})
    X.nem.sort(key=lambda n: (n["meter"], n["from"]))
    for half, months in (("H1", range(1, 7)), ("H2", range(7, 11))):
        cnt = sum(1 for i in X.inspections if i["on"].year == 2025 and (i["on"].month <= 6) == (half == "H1"))
        while cnt < 5000:
            m = r.choice(meters)
            X.inspections.append({"meter": m, "on": date(2025, r.choice(list(months)), r.randint(1, 28)), "result": "PASS", "pad": True})
            cnt += 1
    # disconnections
    X.disc = []
    cand = [m for m in meters if _plain(X, m) and not X.meters[m]["nem"]]
    for m in r.sample(cand, 10):
        d1 = date(2025, 11, r.randint(3, 22))
        X.disc.append({"meter": m, "event": "DISCONNECT", "date": d1, "ref": f"SO{r.randint(10000, 99999)}"})
        if r.chance(0.6):
            X.disc.append({"meter": m, "event": "RECONNECT", "date": d1 + timedelta(days=r.randint(2, 7)), "ref": f"SO{r.randint(10000, 99999)}"})
        T(X, "disconnection_register_2025.docx", "T6", "R-DISCONNECT", (m, d1), "de-energised days unbilled")
    for m in r.sample(cand, 4):
        d0 = date(2025, 10, r.randint(10, 30))
        X.disc.append({"meter": m, "event": "DISCONNECT", "date": d0, "ref": f"SO{r.randint(10000, 99999)}"})
        X.disc.append({"meter": m, "event": "RECONNECT", "date": date(2025, 11, r.randint(4, 18)), "ref": f"SO{r.randint(10000, 99999)}"})
        T(X, "disconnection_register_2025.docx", "T11", "R-DISCONNECT", (m, d0), "disconnected entering November")
    for m in r.sample(cand, 3):
        dx = date(2025, 11, r.randint(3, 25))
        X.disc.append({"meter": m, "event": "DISCONNECT", "date": dx, "ref": f"SOX{r.randint(1000, 9999)}"})
        T(X, "disconnection_register_2025.docx", "T14", "R-DISCONNECT", (m, dx), "SOX orders were cancelled after entry")
    while len(X.disc) < 5200:
        m = r.choice(meters)
        d = date(2025, r.randint(1, 9), r.randint(1, 28))
        X.disc.append({"meter": m, "event": "DISCONNECT", "date": d, "ref": f"SO{r.randint(10000, 99999)}"})
        X.disc.append({"meter": m, "event": "RECONNECT", "date": d + timedelta(days=r.randint(1, 20)), "ref": f"SO{r.randint(10000, 99999)}"})
    X.disc.sort(key=lambda e: (e["meter"], e["date"], e["event"]))
    # meter accuracy tests
    X.acc_tests = []
    for m in r.sample(cand, 10):
        e = Decimal(r.randint(-650, 650)) / 100
        if abs(e) < Decimal("2.05"):
            e = Decimal("3.15") if e >= 0 else Decimal("-2.85")
        X.acc_tests.append({"id": f"MT{r.randint(100000, 999999)}", "meter": m, "date": date(2025, 11, r.randint(5, 27)),
                            "error": e, "result": "FAIL"})
        T(X, "meter_accuracy_test_results_2025.docx", "T12", "R-ACCURACY", X.acc_tests[-1]["id"], "registration error correction")
    while len(X.acc_tests) < 5200:
        m = r.choice(meters)
        d = date(2025, r.randint(1, 11), r.randint(1, 28))
        e = Decimal(r.randint(-180, 180)) / 100
        res = "PASS"
        if not nov(d) and r.chance(0.05):
            e = Decimal(r.randint(250, 700)) / 100
            res = "FAIL"
        X.acc_tests.append({"id": f"MT{r.randint(100000, 999999)}", "meter": m, "date": d, "error": e, "result": res})
    X.acc_tests.sort(key=lambda t: (t["meter"], t["date"]))
    # UFE exemptions
    X.exemptions = []
    for a in r.sample([a for a in accts if X.accounts[a]["cls"] in ("IND", "LGS", "AGR")], 24):
        X.exemptions.append({"acct": a, "from": date(2025, r.randint(1, 10), 1), "to": None, "status": "ACTIVE",
                             "basis": r.choice(["COMPETITIVE_SUPPLY", "INTERVAL_SETTLED", "WHOLESALE"])})
    for a in r.sample([a for a in accts if X.accounts[a]["cls"] in ("IND", "LGS")], 6):
        X.exemptions.append({"acct": a, "from": date(2025, 3, 1), "to": date(2025, 11, r.randint(5, 29)), "status": "ACTIVE",
                             "basis": "COMPETITIVE_SUPPLY"})
        T(X, "ufe_allocation_exemptions_register.pdf", "T11", "R-UFE-EXEMPT", (a, date(2025, 3, 1)), "exemption ends before month end")
    for a in r.sample([a for a in accts if X.accounts[a]["cls"] in ("IND", "LGS")], 5):
        X.exemptions.append({"acct": a, "from": date(2025, 1, 1), "to": None, "status": "REVOKED", "basis": "WHOLESALE"})
        T(X, "ufe_allocation_exemptions_register.pdf", "T6", "R-UFE-EXEMPT", (a, date(2025, 1, 1)), "revoked exemption")
    while len(X.exemptions) < 5200:
        fy = r.randint(2015, 2023)
        X.exemptions.append({"acct": X.new_id("AC", 8, r, 0.5), "from": date(fy, r.randint(1, 12), 1),
                             "to": date(r.randint(fy + 1, 2025), r.randint(1, 10), 1), "status": "ACTIVE",
                             "basis": r.choice(["COMPETITIVE_SUPPLY", "INTERVAL_SETTLED", "WHOLESALE"])})
    X.exemptions.sort(key=lambda e: (e["acct"], e["from"]))


# ---------------------------------------------------------------------------
# part 2c - tariffs, calendar, lighting and SCADA logical tables
# ---------------------------------------------------------------------------
BOOKS = {
    "tariff_book_residential_q4.docx": ["RES"],
    "tariff_book_industrial_q4.docx": ["IND"],
    "tariff_book_commercial_q4.pdf": ["SGS", "LGS"],
    "tariff_book_agri_lighting_q4.pdf": ["AGR", "LIT"],
}
PART_NIGHT_LESS = Decimal("6.00")


def _tariffs(X, r):
    X.rates = {}
    X.unit_dollar_codes = {}
    for code in ALL_CODES:
        base = Decimal(r.randint(650000, 1950000)) / Decimal(100000)
        step_day = date(2025, r.choice([10, 11, 11, 12]), r.randint(1, 28))
        step = Decimal(r.randint(-35000, 60000)) / Decimal(100000)
        mult = {"WEEKDAY": Decimal("1"), "WEEKEND": Decimal("0.86"), "HOLIDAY": Decimal("0.81"), "CPP": Decimal("2.35")}
        for d in Q4_DATES:
            b = base + (step if d >= step_day else 0)
            for dt in DAYTYPES:
                X.rates[(code, d, dt)] = (b * mult[dt]).quantize(Decimal("0.00001"), rounding=ROUND_HALF_EVEN)
    for book, classes in BOOKS.items():
        codes = [c for k in classes for c in RATE_CODES[k]]
        X.unit_dollar_codes[book] = sorted(r.sample(codes, 2))
        for c in X.unit_dollar_codes[book]:
            T(X, book, "T14", "R-TARIFF-UNIT", c, "footnote: rows stated in dollars per kWh")
    # tariff errata (2025 dates); November entries carry the supersession logic
    X.tariff_errata = []
    eid = [r.randint(2000, 3000)]

    def nid():
        eid[0] += r.randint(1, 4)
        return f"TE-{eid[0]}"
    used = set()
    for _ in range(14):
        code = r.choice(ALL_CODES)
        d = r.choice(DAYS)
        dt = r.choice(DAYTYPES)
        if (code, d, dt) in used:
            continue
        used.add((code, d, dt))
        good = (X.rates[(code, d, dt)] + Decimal(r.randint(-90000, 90000)) / Decimal(100000)).quantize(Decimal("0.00001"))
        first = {"id": nid(), "code": code, "date": d, "dt": dt, "rate": good, "issued": date(2025, 11, r.randint(1, 20)),
                 "status": "APPROVED", "supersedes": ""}
        X.tariff_errata.append(first)
        roll = r.random()
        if roll < 0.3:
            later = {"id": nid(), "code": code, "date": d, "dt": dt,
                     "rate": (good + Decimal(r.randint(1000, 40000)) / Decimal(100000)).quantize(Decimal("0.00001")),
                     "issued": first["issued"] + timedelta(days=r.randint(1, 9)), "status": "WITHDRAWN", "supersedes": ""}
            X.tariff_errata.append(later)
            T(X, "tariff_errata_register.html", "T6", "R-TARIFF-ERRATA", (code, d, dt), "withdrawn erratum")
        elif roll < 0.6:
            later = {"id": nid(), "code": code, "date": d, "dt": dt,
                     "rate": (good + Decimal(r.randint(1000, 40000)) / Decimal(100000)).quantize(Decimal("0.00001")),
                     "issued": first["issued"] + timedelta(days=r.randint(1, 9)), "status": "APPROVED", "supersedes": ""}
            X.tariff_errata.append(later)
            T(X, "tariff_errata_register.html", "T7", "R-TARIFF-ERRATA", (code, d, dt), "later approved erratum wins")
        elif roll < 0.8:
            later = {"id": nid(), "code": code, "date": d, "dt": dt,
                     "rate": (good - Decimal(r.randint(1000, 30000)) / Decimal(100000)).quantize(Decimal("0.00001")),
                     "issued": first["issued"] - timedelta(days=r.randint(1, 9)), "status": "APPROVED", "supersedes": first["id"]}
            X.tariff_errata.append(later)
            T(X, "tariff_errata_register.html", "T7", "R-TARIFF-ERRATA", (code, d, dt), "supersedes link beats issue date")
    while len(X.tariff_errata) < 5300:
        code = r.choice(ALL_CODES)
        d = r.choice(YEAR_DATES[:302])
        X.tariff_errata.append({"id": nid(), "code": code, "date": d, "dt": r.choice(DAYTYPES),
                                "rate": Decimal(r.randint(500000, 2500000)) / Decimal(100000), "issued": d + timedelta(days=r.randint(1, 30)),
                                "status": r.choice(["APPROVED", "APPROVED", "WITHDRAWN"]), "supersedes": ""})
    for d in (date(2025, 10, 31), DEC1, date(2025, 10, 31)):
        code = r.choice(ALL_CODES)
        e = {"id": nid(), "code": code, "date": d, "dt": r.choice(DAYTYPES), "status": "APPROVED", "supersedes": "",
             "rate": Decimal(r.randint(500000, 2500000)) / Decimal(100000), "issued": date(2025, 11, r.randint(2, 25))}
        X.tariff_errata.append(e)
        T(X, "tariff_errata_register.html", "T11", "R-TARIFF-ERRATA", (e["code"], e["date"], e["dt"]), "outside window")
    X.tariff_errata.sort(key=lambda e: (e["code"], e["date"], e["id"]))
    # riders
    X.rider_rows = []
    for rider in RIDERS:
        for code in ALL_CODES:
            if rider == "R-FUEL":
                starts = [date(2023, m, 1) for m in (1, 4, 7, 10)] + [date(2024, m, 1) for m in range(1, 13)] + \
                         [date(2025, m, 1) for m in range(1, 11)] + [date(2025, 11, r.randint(8, 22)), date(2025, 12, 1), date(2026, 1, 1)]
            else:
                starts = [date(2020, 7, 1), date(2021, 1, 1), date(2021, 7, 1), date(2022, 1, 1), date(2022, 7, 1),
                          date(2023, 1, 1), date(2023, 7, 1), date(2024, 1, 1), date(2024, 7, 1), date(2025, 1, 1),
                          date(2025, 7, 1), date(2025, 10, 1), date(2026, 1, 1)]
                if r.chance(0.12):
                    starts.append(date(2025, 11, r.randint(5, 25)))
            starts = sorted(set(starts))
            for i, s in enumerate(starts):
                e = starts[i + 1] if i + 1 < len(starts) else date(2026, 7, 1)
                X.rider_rows.append({"rider": rider, "code": code, "from": s, "to": e, "status": "ACTIVE",
                                     "adder": (Decimal(r.randint(-30000, 140000)) / Decimal(100000)).quantize(Decimal("0.00001"))})
    nov_rows = [x for x in X.rider_rows if x["from"] <= DAYS[15] < x["to"]]
    for x in r.sample(nov_rows, 8):
        bad = dict(x)
        bad["adder"] = (x["adder"] + Decimal(r.randint(5000, 50000)) / Decimal(100000)).quantize(Decimal("0.00001"))
        bad["status"] = "RESCINDED"
        X.rider_rows.append(bad)
        T(X, "rider_schedule_2025.pdf", "T6", "R-RIDER", (x["rider"], x["code"]), "rescinded duplicate")
    X.rider_rows.sort(key=lambda x: (x["rider"], x["code"], x["from"], x["status"]))
    X.applicability = []
    for code in ALL_CODES:
        for rider in RIDERS:
            for t in TERRITORIES:
                for e in [date(2022, 1, 1), date(2023, 6, 1), date(2024, 7, 1), date(2025, 3, 1)]:
                    X.applicability.append({"code": code, "rider": rider, "territory": t, "from": e,
                                            "flag": "Y" if r.chance(0.7) else "N"})
    for _ in range(6):
        code, rider, t = r.choice(ALL_CODES), r.choice(RIDERS), r.choice(TERRITORIES)
        last = [a for a in X.applicability if (a["code"], a["rider"], a["territory"]) == (code, rider, t)][-1]
        X.applicability.append({"code": code, "rider": rider, "territory": t, "from": date(2025, 11, r.randint(5, 25)),
                                "flag": "N" if last["flag"] == "Y" else "Y"})
        T(X, "rider_applicability_matrix.html", "T11", "R-APPLICABILITY", (code, rider, t), "flag flips in November")
    X.storm_rows = []
    for code in RATE_CODES["RES"]:
        if r.chance(0.55):
            X.storm_rows.append({"code": code, "from": date(2025, 11, r.randint(14, 24)), "status": "APPROVED",
                                 "adder": (Decimal(r.randint(20000, 90000)) / Decimal(100000)).quantize(Decimal("0.00001"))})
        elif r.chance(0.4):
            X.storm_rows.append({"code": code, "from": date(2025, 11, r.randint(14, 24)), "status": "WITHDRAWN",
                                 "adder": (Decimal(r.randint(20000, 90000)) / Decimal(100000)).quantize(Decimal("0.00001"))})
            T(X, "tariff_book_residential_2026.pdf", "T6", "R-STORM", code, "withdrawn storm row")
            T(X, "tariff_book_residential_2026.pdf", "T11", "R-STORM", code, "storm rider inside November")
        X.storm_rows.append({"code": code, "from": date(2026, 1, 1), "status": "APPROVED",
                             "adder": (Decimal(r.randint(20000, 90000)) / Decimal(100000)).quantize(Decimal("0.00001"))})
    X.rates_2026 = {}
    for code in RATE_CODES["RES"]:
        base = Decimal(r.randint(700000, 2000000)) / Decimal(100000)
        for d in drange(date(2026, 1, 1), date(2026, 4, 1)):
            for dt in DAYTYPES:
                X.rates_2026[(code, d, dt)] = base * {"WEEKDAY": 1, "WEEKEND": Decimal("0.86"), "HOLIDAY": Decimal("0.81"), "CPP": Decimal("2.35")}[dt]
    X.export_rates = {}
    for code in EXPORT_CODES:
        base = Decimal(r.randint(250000, 900000)) / Decimal(100000)
        for d in Q4_DATES:
            for dt in DAYTYPES:
                fac = {"WEEKDAY": Decimal("1"), "WEEKEND": Decimal("0.9"), "HOLIDAY": Decimal("0.9"), "CPP": Decimal("1.8")}[dt]
                X.export_rates[(code, d, dt)] = (base * fac).quantize(Decimal("0.00001"))
    # calendar
    X.cal = []
    uid = [r.randint(1000, 5000)]
    hol = [("New Year", 1, 1), ("Martin Luther King Day", 1, 20), ("Presidents Day", 2, 17), ("Memorial Day", 5, 26),
           ("Juneteenth", 6, 19), ("Independence Day", 7, 4), ("Labor Day", 9, 1), ("Veterans Day", 11, 11),
           ("Thanksgiving", 11, 27), ("Day after Thanksgiving", 11, 28), ("Christmas", 12, 25)]
    for t in TERRITORIES:
        observes = {n for n, _m, _d in hol if r.chance(0.8)} | {"Thanksgiving", "New Year", "Christmas"}
        if r.chance(0.5):
            observes.discard("Day after Thanksgiving")
        for year in range(2012, 2033):
            for n, mth, dy in hol:
                if n in observes:
                    uid[0] += 1
                    d = date(year, mth, dy)
                    X.cal.append({"uid": uid[0], "territory": t, "kind": "HOLIDAY", "start": d, "end": d + timedelta(days=1),
                                  "status": "CONFIRMED", "name": n})
            yd = drange(date(year, 1, 1), date(year + 1, 1, 1))
            wk = [d for d in yd if d.weekday() < 5 and not (year == 2025 and nov(d))]
            for d in r.sample(wk, 56):
                uid[0] += 1
                X.cal.append({"uid": uid[0], "territory": t, "kind": "CPP", "start": d, "end": d + timedelta(days=1),
                              "status": "CONFIRMED" if r.chance(0.86) else "CANCELLED", "name": "Critical peak event"})
    hol_nov = {(e["territory"], e["start"]) for e in X.cal if e["kind"] == "HOLIDAY" and nov(e["start"])}
    for t in TERRITORIES:
        wk = [d for d in DAYS if d.weekday() < 5 and (t, d) not in hol_nov]
        picks = r.sample(wk, 5)
        for j, d in enumerate(picks):
            uid[0] += 1
            st = "CANCELLED" if j == 4 else "CONFIRMED"
            X.cal.append({"uid": uid[0], "territory": t, "kind": "CPP", "start": d, "end": d + timedelta(days=1),
                          "status": st, "name": "Critical peak event"})
            if st == "CANCELLED":
                T(X, "territory_rate_calendar.ics", "T6", "R-DAYTYPE", (t, d), "cancelled CPP event")
        # CPP declared on a holiday: holiday wins
        hd = sorted(d for (tt, d) in hol_nov if tt == t)
        if hd:
            uid[0] += 1
            d = r.choice(hd)
            X.cal.append({"uid": uid[0], "territory": t, "kind": "CPP", "start": d, "end": d + timedelta(days=1),
                          "status": "CONFIRMED", "name": "Critical peak event"})
            T(X, "territory_rate_calendar.ics", "T7", "R-DAYTYPE", (t, d), "holiday outranks CPP")
    t2 = r.choice(TERRITORIES)
    wk2 = [d for d in DAYS if d.weekday() < 4 and (t2, d) not in hol_nov and (t2, d + timedelta(days=1)) not in hol_nov]
    d0 = r.choice(wk2)
    uid[0] += 1
    X.cal.append({"uid": uid[0], "territory": t2, "kind": "CPP", "start": d0, "end": d0 + timedelta(days=2),
                  "status": "CONFIRMED", "name": "Critical peak event (two day)"})
    T(X, "territory_rate_calendar.ics", "T11", "R-DAYTYPE", (t2, d0), "two-day event, DTEND exclusive")
    X.cal.sort(key=lambda e: e["uid"])


def _lighting(X, r):
    X.fixtures = {}
    for aid in X.lit_accounts:
        for _ in range(r.randint(70, 82)):
            fid = X.new_id("FX", 6, r, 0.4)
            inst = date(r.randint(2009, 2024), r.randint(1, 12), r.randint(1, 28))
            X.fixtures[fid] = {"id": fid, "acct": aid, "feeder": X.accounts[aid]["feeder"],
                               "watts": r.choice([35, 50, 70, 100, 150, 175, 250, 400]),
                               "profile": r.choice(["DUSK_DAWN"] * 8 + ["PART_NIGHT", "ALL_DAY"]),
                               "install": inst, "removal": None}
    fids = sorted(X.fixtures)
    for fid in r.sample(fids, 6):
        X.fixtures[fid]["install"] = date(2025, 11, r.randint(2, 29))
        T(X, "unmetered_supply_inventory.json", "T11", "R-FIXTURE", fid, "installed in November")
    for fid in r.sample(fids, 6):
        X.fixtures[fid]["removal"] = date(2025, 11, r.randint(2, 30))
        T(X, "unmetered_supply_inventory.json", "T11", "R-FIXTURE", fid, "removed in November")
    X.audit = []
    for fid in fids:
        q = r.choice(["Q3", "Q4"])
        d = date(2025, r.choice([7, 8, 9]) if q == "Q3" else 10, r.randint(1, 28))
        X.audit.append({"fixture": fid, "date": d, "status": "OK", "watts": X.fixtures[fid]["watts"], "eff": d, "q": q})
    for fid in r.sample(fids, 5):
        nw = r.choice([w for w in (35, 50, 70, 100, 150, 175, 250) if w != X.fixtures[fid]["watts"]])
        X.audit.append({"fixture": fid, "date": date(2025, 11, r.randint(3, 20)), "status": "WATTAGE_CHANGE", "watts": nw,
                        "eff": date(2025, 11, r.randint(3, 25)), "q": "Q4"})
        T(X, "unmetered_fixture_audit_2025.xlsx", "T2", "R-FIXTURE-AUDIT", (fid, X.audit[-1]["eff"]), "audited wattage from effective date")
    for fid in r.sample(fids, 4):
        X.audit.append({"fixture": fid, "date": date(2025, 11, r.randint(3, 20)), "status": "REMOVED", "watts": 0,
                        "eff": date(2025, 11, r.randint(3, 28)), "q": "Q4"})
        T(X, "unmetered_fixture_audit_2025.xlsx", "T6", "R-FIXTURE-AUDIT", (fid, X.audit[-1]["eff"]), "audited removal")
    for q in ("Q3", "Q4"):
        while sum(1 for a in X.audit if a["q"] == q) < 5000:
            fid = r.choice(fids)
            d = date(2025, r.choice([7, 8, 9]) if q == "Q3" else 10, r.randint(1, 28))
            X.audit.append({"fixture": fid, "date": d, "status": "OK", "watts": X.fixtures[fid]["watts"], "eff": d, "q": q})
        while sum(1 for a in X.audit if a["q"] == q) > 5000:
            idx = max(i for i, a in enumerate(X.audit) if a["q"] == q and a["status"] == "OK")
            X.audit.pop(idx)
    X.burn = {}
    for f in FEEDERS:
        phase = r.randint(0, 40)
        for d in drange(date(2024, 1, 1), date(2026, 1, 1)):
            doy = d.timetuple().tm_yday
            h = 12 + 2.6 * math.cos(2 * math.pi * (doy + 10 + phase / 10) / 365.25) + r.randint(-6, 6) / 100
            X.burn[(f, d)] = Decimal(str(round(h, 2))).quantize(Decimal("0.01"))
    X.burn_exc = []
    for fid in r.sample(fids, 8):
        d = r.choice(DAYS)
        X.burn_exc.append({"fixture": fid, "date": d, "hours": r.choice([Decimal("24.00"), Decimal("0.00"), Decimal("7.50")]),
                           "reason": r.choice(["PHOTOCELL_FAIL", "CIRCUIT_OUTAGE", "PART_NIGHT_TRIAL"]), "q": "Q4"})
        T(X, "lighting_burn_hour_exceptions_2025.xlsx", "T15", "R-BURN-EXCEPTION", (fid, d), "24h burn is valid")
    for q in ("Q3", "Q4"):
        while sum(1 for a in X.burn_exc if a["q"] == q) < 5000:
            fid = r.choice(fids)
            d = date(2025, r.choice([7, 8, 9]) if q == "Q3" else 10, r.randint(1, 28))
            X.burn_exc.append({"fixture": fid, "date": d, "hours": r.choice([Decimal("24.00"), Decimal("0.00")]),
                               "reason": r.choice(["PHOTOCELL_FAIL", "CIRCUIT_OUTAGE"]), "q": q})
    dedup = {}
    for e in X.burn_exc:
        dedup[(e["fixture"], e["date"])] = e
    X.burn_exc = list(dedup.values())
    for q in ("Q3", "Q4"):
        while sum(1 for a in X.burn_exc if a["q"] == q) < 5000:
            fid = r.choice(fids)
            d = date(2025, r.choice([7, 8, 9]) if q == "Q3" else 10, r.randint(1, 28))
            if (fid, d) in dedup:
                continue
            e = {"fixture": fid, "date": d, "hours": Decimal("0.00"), "reason": "CIRCUIT_OUTAGE", "q": q}
            dedup[(fid, d)] = e
            X.burn_exc.append(e)


def interval_ends():
    start = local_to_utc(MONTH_START, 0, 0, 0)
    end = local_to_utc(DEC1, 0, 0, 0)
    return [start + 900 * k for k in range(1, (end - start) // 900 + 1)]


SCADA_FILES = {"north": "substation_north_scada_2025-11.csv", "east": "substation_east_scada_2025-11.json",
               "south": "substation_south_historian.log", "west": "substation_west_monthly_report.pdf"}


def _scada(X, r):
    ends = interval_ends()
    X.interval_ends = ends
    load = {f: Decimal(0) for f in FEEDERS}
    fixed = {m: (d, nr) for m, d, nr in X.ct_fixes}
    for m, info in X.meters.items():
        if "replaces" in info:
            continue
        mult = info["mult"]
        if m in fixed:
            mult = fixed[m][1]
        load[info["feeder"]] += sum(info["d_imp"]) * mult
    for fx in X.fixtures.values():
        load[fx["feeder"]] += Decimal(fx["watts"]) * 12 * 30 / 1000
    X.scada = {}
    X.alarms = []
    X.scada_errata = []
    X.gapfill = {}
    X.relay = {}
    for f in FEEDERS:
        sub = SUBSTATION[f]
        total_wh = load[f] * 1000 * (1 + X.feeder_loss_pct[f] / 100 + Decimal(r.randint(-5, 30)) / 1000)
        shapes = []
        for t in ends:
            dt, _a, _o = utc_to_local(t)
            hr = dt.hour + dt.minute / 60
            shapes.append(Decimal(str(round(0.72 + 0.45 * math.exp(-((hr - 18.5) ** 2) / 8) + 0.2 * math.exp(-((hr - 8) ** 2) / 6), 4))))
        per = total_wh / sum(shapes)
        for t, shape in zip(ends, shapes):
            v = per * shape * Decimal(r.randint(950, 1050)) / 1000
            if sub == "north":
                kw = (v / 250).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
                rec = {"kw": kw, "wh": int_even(kw * 250), "q": "GOOD"}
            elif sub == "south":
                mwh = (v / 1000000).quantize(Decimal("0.000001"))
                rec = {"mwh": mwh, "wh": int(mwh * 1000000), "q": "GOOD"}
            else:
                kwh = (v / 1000).quantize(Decimal("0.001"))
                rec = {"kwh": kwh, "wh": int(kwh * 1000), "q": "GOOD"}
            X.scada[(f, t)] = rec
            X.gapfill[(f, t)] = int(rec["wh"] * Decimal(r.randint(985, 1015)) / 1000)
    # quality failures and COMM_FAIL alarm windows
    comm_feeders = set(r.sample(FEEDERS, 8))
    for f in FEEDERS:
        for idx in _spread(len(ends), 2, r):
            t = ends[idx]
            X.scada[(f, t)]["q"] = "BAD"
            X.scada[(f, t)]["wh"] = None
            T(X, SCADA_FILES[SUBSTATION[f]], "T5", "R-SCADA", (f, t), "bad quality interval")
        for _ in range(1 if f in comm_feeders else 0):
            k = r.randint(50, len(ends) - 60)
            raised = ends[k] - 900 + r.randint(0, 899)
            cleared = ends[k + r.randint(2, 8)] - r.randint(0, 899)
            X.alarms.append({"feeder": f, "type": "COMM_FAIL", "raised": raised, "cleared": cleared})
            T(X, "scada_alarm_journal.log", "T6", "R-SCADA-ALARM", (f, raised), "intervals overlapped by alarm invalid")
    # in-scope intervals at the DST repeat are a trap on their own
    rep = [t for t in ends if local_to_utc(date(2025, 11, 2), 1, 0, 0) < t <= local_to_utc(date(2025, 11, 2), 1, 0, 0, fold=1) + 3600]
    for sub in ("north", "east", "south", "west"):
        f = [x for x in FEEDERS if SUBSTATION[x] == sub][0]
        T(X, SCADA_FILES[sub], "T3", "R-SCADA-TIME", (f, rep[0] if rep else ends[100]), "repeated hour")
    # errata: approved, withdrawn and superseded corrections
    eid = [r.randint(100, 900)]
    for f in FEEDERS:
        for idx in _spread(len(ends), 1, r):
            t = ends[idx]
            eid[0] += r.randint(1, 5)
            val = int((X.scada[(f, t)]["wh"] or X.gapfill[(f, t)]) * Decimal(r.randint(800, 1200)) / 1000)
            e1 = {"id": f"SE-{eid[0]}", "feeder": f, "t": t, "wh": val, "status": "APPROVED",
                  "issued": date(2025, 12, r.randint(1, 2)), "supersedes": ""}
            X.scada_errata.append(e1)
            if r.chance(0.35):
                eid[0] += 1
                X.scada_errata.append({"id": f"SE-{eid[0]}", "feeder": f, "t": t, "wh": val + r.randint(500, 9000),
                                       "status": "WITHDRAWN", "issued": e1["issued"], "supersedes": ""})
                T(X, "scada_errata_notice.md", "T6", "R-SCADA-ERRATA", (f, t), "withdrawn")
            elif r.chance(0.4):
                eid[0] += 1
                X.scada_errata.append({"id": f"SE-{eid[0]}", "feeder": f, "t": t, "wh": val - r.randint(500, 9000),
                                       "status": "APPROVED", "issued": date(2025, 11, 30), "supersedes": e1["id"]})
                T(X, "scada_errata_notice.md", "T7", "R-SCADA-ERRATA", (f, t), "supersedes link")
    t0 = local_to_utc(date(2025, 1, 1), 0, 0, 0)
    while len(X.scada_errata) < 5200:
        eid[0] += 1
        f = r.choice(FEEDERS)
        t = t0 + 900 * r.randint(1, 29000)
        X.scada_errata.append({"id": f"SE-{eid[0]}", "feeder": f, "t": t, "wh": r.randint(20000, 900000),
                               "status": r.choice(["APPROVED", "WITHDRAWN"]), "issued": date(2025, r.randint(1, 10), r.randint(1, 28)),
                               "supersedes": ""})
    X.scada_errata.sort(key=lambda e: (e["feeder"], e["t"], e["id"]))
    # relay test replacements for east feeders (decoy DC11 section 4)
    for f in [x for x in FEEDERS if SUBSTATION[x] == "east"]:
        for idx in _spread(len(ends), 3, r):
            t = ends[idx]
            X.relay[(f, t)] = int((X.scada[(f, t)]["wh"] or X.gapfill[(f, t)]) * Decimal(r.randint(600, 900)) / 1000)
            T(X, "substation_east_monthly_report.pdf", "T14", "R-RELAY-TEST", (f, t), "relay-test replacement")
    # one east interval per feeder carries both an approved erratum and a DONE relay test, so the manual
    # section 7 order (erratum before relay test) is exercised; no rng draw, so nothing else shifts
    for f in [x for x in FEEDERS if SUBSTATION[x] == "east"]:
        t = min(t_ for (f_, t_) in X.relay if f_ == f)
        eid[0] += 1
        X.scada_errata.append({"id": f"SE-{eid[0]}", "feeder": f, "t": t, "wh": X.relay[(f, t)] + 1000 + eid[0] % 997,
                               "status": "APPROVED", "issued": date(2025, 12, 2), "supersedes": ""})
        T(X, "scada_errata_notice.md", "T7", "R-SCADA-ERRATA", (f, t), "erratum outranks the relay-test value")
    X.scada_errata.sort(key=lambda e: (e["feeder"], e["t"], e["id"]))
    tn = local_to_utc(MONTH_START)
    while len(X.alarms) < 3990:
        f = r.choice(FEEDERS)
        t = tn + 900 * r.randint(1, 2870)
        typ = r.choice(["OVERVOLT", "UNDERVOLT", "BREAKER_OP", "RECLOSE", "TEMP_HIGH"])
        X.alarms.append({"feeder": f, "type": typ, "raised": t, "cleared": t + r.randint(60, 7200)})
    X.alarms.sort(key=lambda a: (a["raised"], a["feeder"]))


# ---------------------------------------------------------------------------
# part 2d - device identities, profiles, events and the decoy tables
# ---------------------------------------------------------------------------
def build_all(seed, hidden=False):
    X = build_logical_base(seed, hidden)
    return X


def build_logical_base(seed, hidden=False):
    rng = Rng(seed)
    X = L()
    X.seed = seed
    X.traps = []
    X.used_ids = set()

    def new_id(prefix, digits, r, lead_zero=0.5):
        while True:
            lead = "0" if r.chance(lead_zero) else str(r.randint(1, 9))
            v = prefix + lead + "".join(str(r.randint(0, 9)) for _ in range(digits - 1))
            if v not in X.used_ids:
                X.used_ids.add(v)
                return v
    X.new_id = new_id
    _entities(X, rng.fork("entities"))
    _registry(X, rng.fork("registry"))
    _reads(X, rng.fork("reads"))
    _devices(X, rng.fork("devices"))
    _read_controls(X, rng.fork("controls"))
    _quantize_rows(X)
    _billing_refs(X, rng.fork("billing"))
    _tariffs(X, rng.fork("tariffs"))
    _lighting(X, rng.fork("lighting"))
    _scada(X, rng.fork("scada"))
    _events_and_decoys(X, rng.fork("decoys"))
    _precedence_fixtures(X, Rng(X.seed ^ 0x5EEDF1C5A27))
    _vendor_count_drift(X, Rng(X.seed ^ 0x1D0C0DE77))
    if hidden:
        _tiebreak_fixtures(X, Rng(X.seed ^ 0x71EB2EA4C))
    return X


def _vendor_count_drift(X, r):
    """Delivered counts that disagree with the data records actually in the file.

    The vendor manifest record_count and the MDM batch log row count are each a sending system's
    claim about a delivery (manual section 4); contract section 9 counts data_rows in the file.
    Letting the two claims drift keeps data_rows a parsing result instead of a field to copy, and
    keeps manifest_rows a report of the vendor's number instead of the parsed count restated.
    Uses its own generator so every earlier stream is unchanged."""
    X.vendor_drift = {}
    X.log_drift = {}
    for fn in READ_FILES + [RESEND_FILE]:
        if r.chance(0.45):
            X.vendor_drift[fn] = r.choice([-1, 1]) * r.randint(2, 40)
        if r.chance(0.45):
            X.log_drift[fn] = r.choice([-1, 1]) * r.randint(2, 40)


def _tiebreak_fixtures(X, r):
    """Hidden tier only: inputs where the stated tie-breaks of three selection rules decide a graded value.
    Uses its own generator and runs last, so every earlier stream is unchanged; the visible tier never calls it.
    The fourth tie-break (largest remainder, contract section 8) needs the settled weights and is planted by
    _ufe_tie_fixture after the truth is known."""
    # (1) contract section 4, meter accuracy: latest November FAIL test date, then highest test id
    nov_fail = sorted((t for t in X.acc_tests if t["result"] == "FAIL" and nov(t["date"])), key=lambda t: t["id"])
    seen_ids = {t["id"] for t in X.acc_tests}
    by_meter = {}
    for t in nov_fail:
        by_meter.setdefault(t["meter"], []).append(t)
    single = [ts[0] for m, ts in sorted(by_meter.items()) if len(ts) == 1 and ts[0]["date"].day >= 3 and ts[0]["id"] < "MT999000"]

    def other_error(e):
        while True:
            v = Decimal(r.randint(205, 650)) / 100 * r.choice([-1, 1])
            if v != e:
                return v

    def fresh_id(lo):
        while True:
            v = f"MT{r.randint(lo, 999999)}"
            if v not in seen_ids:
                seen_ids.add(v)
                return v
    t_date, t_id = r.sample(single, 2)
    X.acc_tests.append({"id": fresh_id(100000), "meter": t_date["meter"], "date": date(2025, 11, r.randint(2, t_date["date"].day - 1)),
                        "error": other_error(t_date["error"]), "result": "FAIL"})
    T(X, "meter_accuracy_test_results_2025.docx", "T12", "R-ACCURACY", X.acc_tests[-1]["id"], "an earlier November FAIL loses to the latest")
    X.acc_tests.append({"id": fresh_id(int(t_id["id"][2:]) + 1), "meter": t_id["meter"], "date": t_id["date"],
                        "error": other_error(t_id["error"]), "result": "FAIL"})
    T(X, "meter_accuracy_test_results_2025.docx", "T12", "R-ACCURACY", X.acc_tests[-1]["id"], "same test date: the higher test id wins")
    X.acc_tests.sort(key=lambda t: (t["meter"], t["date"]))
    # (2) manual section 3: a second VALIDATED revision of an in-window correction, the higher revision wins
    keys = {}
    for c in X.corrections:
        keys.setdefault((c["meter"], c["date"]), []).append(c)
    cands = []
    for (m, d), cs in sorted(keys.items()):
        valid = [c for c in cs if c["status"] == "VALIDATED"]
        if MONTH_START < d < DEC1 and len(valid) == 1:
            b = (d - MONTH_START).days
            gap = X.meters[m]["reg"][b + 1] - valid[0]["imp"]
            if gap >= Decimal("0.010"):
                cands.append((m, d, b, valid[0], gap))
    m, d, b, cur, gap = r.choice(cands)
    corr_n = max(int(c["id"][2:]) for c in X.corrections)
    X.corrections.append({"id": f"RC{corr_n + r.randint(1, 9)}", "meter": m, "date": d,
                          "imp": (cur["imp"] + gap * Decimal(r.randint(25, 75)) / 100).quantize(Decimal("0.001"), rounding=ROUND_FLOOR),
                          "exp": cur["exp"], "rev": max(c["rev"] for c in keys[(m, d)]) + 1, "status": "VALIDATED"})
    X.corrections.sort(key=lambda c: (c["meter"], c["date"], c["rev"]))
    T(X, "mdm_read_corrections.csv", "T7", "R-CORRECTION", (m, b), "two VALIDATED revisions: the highest wins")
    # (3) manual section 6: two APPROVED November errata for one key issued the same day, the higher number wins
    def daytype(terr, d):
        dt = "WEEKEND" if d.weekday() >= 5 else "WEEKDAY"
        for e in X.cal:
            if e["territory"] == terr and e["status"] == "CONFIRMED" and e["start"] <= d < e["end"]:
                if e["kind"] == "HOLIDAY":
                    return "HOLIDAY"
                if e["kind"] == "CPP":
                    dt = "CPP"
        return dt
    held = {}
    for a in sorted(X.accounts):
        if X.accounts[a]["cls"] == "RES" and X.accounts[a]["status"] == "ACTIVE":
            held[X.accounts[a]["code"]] = held.get(X.accounts[a]["code"], 0) + 1
    code = max(sorted(held), key=lambda c: held[c])
    errata_keys = {(e["code"], e["date"], e["dt"]) for e in X.tariff_errata}
    d = r.choice([x for x in DAYS if all(daytype(t, x) == "WEEKDAY" for t in TERRITORIES)
                  and (code, x, "WEEKDAY") not in errata_keys])
    book = X.rates[(code, d, "WEEKDAY")]
    step = Decimal(r.randint(8000, 40000)) / Decimal(100000)
    rates = [(book + step).quantize(Decimal("0.00001")), (book - step).quantize(Decimal("0.00001"))]
    if r.chance(0.5):
        rates.reverse()
    te_n = max(int(e["id"].split("-")[1]) for e in X.tariff_errata) + r.randint(1, 4)
    issued = date(2025, 11, r.randint(1, 20))
    for i, rate in enumerate(rates):
        X.tariff_errata.append({"id": f"TE-{te_n + 3 * i}", "code": code, "date": d, "dt": "WEEKDAY", "rate": rate,
                                "issued": issued, "status": "APPROVED", "supersedes": ""})
    X.tariff_errata.sort(key=lambda e: (e["code"], e["date"], e["id"]))
    T(X, "tariff_errata_register.html", "T7", "R-TARIFF-ERRATA", (code, d, "WEEKDAY"),
      "same issued date: the higher erratum number wins")


def _ufe_tie_fixture(X, R, r):
    """Hidden tier only (contract section 8): move one approved SCADA erratum by a few Wh so the UFE total puts the
    largest-remainder cutoff between two accounts of equal weight, where only the lower-account-id tie-break decides
    which of them gets the extra Wh. Weights are unchanged (injection is not a weight); only the total moves.
    R is the settled truth of X. Returns True when the erratum was moved."""
    exempt = {e["acct"] for e in X.exemptions
              if e["status"] == "ACTIVE" and e["from"] <= NOV30 and (e["to"] is None or NOV30 < e["to"])}
    weights = {x["account_id"]: x["billed_import_wh"] + x["deemed_wh"] for x in R["account_settlement.csv"]
               if x["account_id"] not in exempt and x["billed_import_wh"] + x["deemed_wh"] > 0}
    W = sum(weights.values())
    loss_pct = dict(X.feeder_loss_pct)
    for e in X.draft_errata:
        if e["table"] == "L" and e["cab"] in X.cab_approved:
            loss_pct[e["key"]] = e["value"]
    per_key = {}
    for e in X.scada_errata:
        per_key[(e["feeder"], e["t"])] = per_key.get((e["feeder"], e["t"]), 0) + 1
    sup = {e["supersedes"] for e in X.scada_errata if e["status"] == "APPROVED" and e["supersedes"]}
    ends = set(X.interval_ends)
    cands = sorted((e for e in X.scada_errata if e["status"] == "APPROVED" and e["id"] not in sup and e["t"] in ends
                    and per_key[(e["feeder"], e["t"])] == 1), key=lambda e: e["id"])
    if not cands or not W:
        return False
    e = r.choice(cands)
    fb = R["feeder_balance.json"]["feeders"][e["feeder"]]
    for delta in range(1, 20000):
        ufe = R["settlement_summary.json"]["ufe_wh"] + delta - (
            int_even(Decimal(fb["injection_wh"] + delta) * loss_pct[e["feeder"]] / 100) - fb["loss_wh"])
        amount = abs(ufe)
        rema = sorted((-(amount * w % W), a) for a, w in weights.items())
        left = -sum(x for x, _a in rema) // W
        if 0 < left < len(rema) and rema[left - 1][0] == rema[left][0]:
            e["wh"] += delta
            return True
    return False


def _precedence_fixtures(X, r):
    """Inputs where each adjacent pair of a stated precedence chain disagrees, so the order is graded.
    Uses its own generator so every earlier stream is unchanged."""
    trap_meters = set()
    for t in X.traps:
        for it in (t["key"] if isinstance(t["key"], tuple) else (t["key"],)):
            if isinstance(it, str) and it.startswith("KV"):
                trap_meters.add(it)
    busy = trap_meters | {e["old"] for e in X.exchanges} | {e["new"] for e in X.exchanges} | {c["meter"] for c in X.ct_orders}
    flags = ("perturbed", "stray", "sentinel", "outside", "withdrawn", "batch_reject", "reversed", "wh_issue")
    taken = {(v["meter"], v["date"]) for v in X.vee} | {(c["meter"], c["date"]) for c in X.corrections}
    taken |= {(h["meter"], h["date"]) for h in X.holds} | {(q["meter"], q["date"]) for q in X.quarantine}
    taken |= {(d["meter"], d["date"]) for d in X.disputes} | {(k["meter"], k["date"]) for k in X.known_issues}
    taken |= {(v["meter"], v["date"]) for v in X.voids}
    # (1) manual section 3: a surviving actual read outranks an approved VEE estimate
    cands = []
    for fn in READ_FILES:
        for row in X.reads[fn]:
            m, b = row["meter"], row["b"]
            if m not in X.meters or m in busy or not _plain(X, m) or not 2 <= b <= 28 or any(row.get(f) for f in flags):
                continue
            info = X.meters[m]
            if info["clock"] or (m, BOUNDARY_DATES[b]) in taken or info["reg"][b + 1] <= info["reg"][b - 1]:
                continue
            cands.append((fn, m, b))
    est_n = max(int(v["id"][2:]) for v in X.vee)
    used = set()
    for fn, m, b in r.sample(cands, len(cands)):
        if len(used) == 4:
            break
        if m in used or any(X.meters[m]["hes"] == X.meters[u]["hes"] for u in used):
            continue
        info = X.meters[m]
        lo, hi = info["reg"][b - 1], info["reg"][b + 1]
        est = (lo + (hi - lo) * Decimal(r.randint(30, 70)) / 100).quantize(Decimal("0.001"))
        if est == info["reg"][b]:
            continue
        used.add(m)
        bdate = BOUNDARY_DATES[b]
        est_n += r.randint(1, 9)
        X.vee.append({"id": f"VE{est_n}", "meter": m, "date": bdate, "imp": est, "exp": info["regx"].get(b),
                      "version": 1, "created": bdate + timedelta(days=1)})
        X.vee_reviews.append({"est": f"VE{est_n}", "status": "APPROVED", "on": bdate + timedelta(days=2)})
        T(X, "vee_estimate_review_2025.xlsx", "T7", "R-VEE", (m, b), "surviving actual outranks an approved estimate")
    X.vee.sort(key=lambda v: (v["meter"], v["date"], v["version"]))
    busy |= used
    # (2) contract section 6: HOLIDAY and CPP outrank WEEKEND
    weekend = [d for d in DAYS if d.weekday() >= 5]
    uid = max(e["uid"] for e in X.cal)
    covered = {(e["territory"], d) for e in X.cal if e["status"] == "CONFIRMED" for d in weekend if e["start"] <= d < e["end"]}
    terrs = r.sample(TERRITORIES, 2)
    for terr, kind, name in ((terrs[0], "CPP", "Critical peak event"), (terrs[1], "HOLIDAY", "Cooperative Founders Day")):
        d = r.choice([x for x in weekend if (terr, x) not in covered])
        uid += 1
        X.cal.append({"uid": uid, "territory": terr, "kind": kind, "start": d, "end": d + timedelta(days=1),
                      "status": "CONFIRMED", "name": name})
        T(X, "territory_rate_calendar.ics", "T7", "R-DAYTYPE", (terr, d), f"{kind} outranks WEEKEND")
    # (3) contract section 4: on equal instants order beats verification beats registry
    nov_verif = {v["meter"] for v in X.ct_verif if nov(v["on"])}
    sched = {}
    for row in X.schedule_rows:
        sched.setdefault(row["meter"], []).append((row["from"], 0, row["read_time"]))
    for e in X.draft_errata:
        if e["table"] == "R":
            sched.setdefault(e["key"], []).append((e["from"], 1, e["value"]))
    errata_meters = {e["key"] for e in X.draft_errata if e["table"] == "R"}

    def rt(m, d):
        cur = "00:00"
        for frm, _p, val in sorted(sched.get(m, [])):
            if frm <= d:
                cur = val
        return cur
    ctm = [m for m in sorted(X.meters) if X.meters[m]["mult"] > 1 and m not in busy and m not in nov_verif
           and m not in errata_meters and not any(k in X.meters[m] for k in ("ct", "exchange", "installed", "reset", "spike"))]
    ctm = r.sample(ctm, len(ctm))
    ratios = (40, 80, 120, 200, 400, 600)
    cv_ids = {v["id"] for v in X.ct_verif}

    def cv_id():
        pad = next(i for i, v in enumerate(X.ct_verif) if v["half"] == "H2" and v["result"] == "PASS" and not nov(v["on"]))
        X.ct_verif.pop(pad)
        while True:
            v = f"CV{r.randint(10000, 99999)}"
            if v not in cv_ids:
                cv_ids.add(v)
                return v
    # verification beats registry: a registry row of date D carries a wrong ratio, the same-day verification restores it
    m1 = ctm[0]
    info = X.meters[m1]
    d1 = date(2025, 11, r.randint(4, 24))
    wrong = r.choice([x for x in ratios if x != info["mult"]])
    dist = DISTRICT_OF[info["feeder"]]
    cur = [x for x in X.registry[dist] if x["meter"] == m1 and x["to"] is None][0]
    cur["to"] = d1
    X.registry[dist].append({"meter": m1, "account": cur["account"], "mult": wrong, "hes": cur["hes"],
                             "from": d1, "to": None, "reason": "CT_UPDATE"})
    X.ct_verif.append({"id": cv_id(), "meter": m1, "on": d1, "reg": wrong, "measured": info["mult"], "result": "FAIL",
                       "action": "CORRECT_RATIO", "half": "H2"})
    T(X, "ct_ratio_verification_2025.xlsx", "T2", "R-CT-VERIFY", (m1, d1), "verification outranks a registry row of the same date")
    # order beats verification: a CT_CHANGE completed at local midnight, the same-day verification names another ratio
    clean = {}
    for fn in READ_FILES:
        for row in X.reads[fn]:
            if row["meter"] in X.meters and not any(row.get(f) for f in flags):
                clean.setdefault(row["meter"], set()).add(row["b"])
    for m2 in ctm[1:]:
        bs = [b for b in range(5, 26) if b in clean.get(m2, ()) and rt(m2, BOUNDARY_DATES[b]) == "00:00"
              and (m2, BOUNDARY_DATES[b]) not in taken]
        if bs:
            break
    b2 = r.choice(bs)
    d2 = BOUNDARY_DATES[b2]
    info = X.meters[m2]
    t2 = local_to_utc(d2)
    oid = max(int(o["id"][2:]) for o in X.orders) + r.randint(1, 40)
    X.ct_orders.append({"meter": m2, "day": b2 - 1, "t": t2, "new": info["mult"], "frac": Decimal(0)})
    X.orders.append({"id": f"WO{oid}", "type": "CT_CHANGE", "status": "COMPLETED", "t": t2, "meter": m2,
                     "old_ratio": info["mult"], "new_ratio": info["mult"], "read": info["reg"][b2]})
    X.orders.sort(key=lambda o: o["t"])
    X.ct_verif.append({"id": cv_id(), "meter": m2, "on": d2, "reg": info["mult"],
                       "measured": r.choice([x for x in ratios if x != info["mult"]]), "result": "FAIL",
                       "action": "CORRECT_RATIO", "half": "H2"})
    T(X, "field_service_orders.jsonl", "T2", "R-CT-CHANGE", f"WO{oid}", "order outranks a verification at the same instant")
    # (4) manual section 1: an approved erratum row outranks an Appendix R register row with the same effective date
    appr = sorted((e for e in X.draft_errata if e["table"] == "R" and e["cab"] in X.cab_approved), key=lambda e: e["id"])
    er = r.choice(appr)
    X.schedule_rows.append({"meter": er["key"], "read_time": "23:00" if er["value"] == "00:00" else "00:00", "from": er["from"]})
    T(X, "settlement_procedures_manual_rev4_draft.docx", "T7", "R-DRAFT-ERRATA", er["key"],
      "approved erratum outranks a register row of the same date")
    # (5) manual section 5: an in-window migration outranks a history entry with the same effective date
    merged = {x["pred"] for x in X.merges} | {x["pred"] for x in X.late_merges}
    metered = {info.get("account") for info in X.meters.values()}
    ea = sorted((x for x in X.early_adopters if x.get("status", "ACTIVE") == "ACTIVE" and x["acct"] in X.accounts
                 and X.accounts[x["acct"]]["status"] == "ACTIVE" and x["acct"] not in merged and x["acct"] in metered),
                key=lambda x: x["acct"])
    ad = r.choice(ea)
    cls = X.accounts[ad["acct"]]["cls"]
    later = {}
    for h in X.rate_hist:
        if not h.get("erroneous") and h["from"] <= MONTH_START:
            later[h["acct"]] = max(later.get(h["acct"], h["from"]), h["from"])
    pad = next(h for h in X.rate_hist if h.get("pad") and h["sheet"] == "2025" and later[h["acct"]] > h["from"])
    X.rate_hist.remove(pad)
    X.rate_hist.append({"acct": ad["acct"], "code": r.choice([c for c in RATE_CODES[cls] if c != ad["new_code"]]),
                        "from": ad["eff"], "entry": max(h["entry"] for h in X.rate_hist) + r.randint(1, 7), "sheet": "2025"})
    T(X, "rate_code_crosswalk_2026.json", "T11", "R-EARLY-ADOPTER", ad["acct"],
      "migration outranks a history entry of the same date")
    # (6) contract section 5: a FAIL export inspection outranks a PASS of the same date
    open_nem = {n["meter"] for n in X.nem if n["status"] == "APPROVED" and n["to"] is None}
    fails = sorted((i for i in X.inspections if i["result"] == "FAIL" and nov(i["on"]) and i["meter"] in open_nem
                    and not any(j["meter"] == i["meter"] and j["on"] > i["on"] for j in X.inspections)),
                   key=lambda i: (i["meter"], i["on"]))
    fi = r.choice(fails)
    X.inspections.append({"meter": fi["meter"], "on": fi["on"], "result": "PASS"})
    T(X, "export_meter_inspections_2025.xlsx", "T6", "R-INSPECTION", (fi["meter"], fi["on"]),
      "a FAIL outranks a PASS inspection of the same date")
    # (7) manual section 5: when several merges of one predecessor apply, the latest effective one wins
    applied = {}
    for x in X.merges:
        if x["status"] == "COMPLETED":
            applied.setdefault(x["pred"], []).append(x)
    for x in X.late_merges:
        applied.setdefault(x["pred"], []).append(x)
    involved = {x["pred"] for x in X.merges} | {x["succ"] for x in X.merges} | \
        {x["pred"] for x in X.late_merges} | {x["succ"] for x in X.late_merges}
    mgs = sorted((x for x in X.merges if x["status"] == "COMPLETED" and nov(x["eff"]) and x["pred"] in X.accounts
                  and len(applied[x["pred"]]) == 1), key=lambda x: x["id"])
    mg = r.choice(mgs)
    cls = X.accounts[mg["pred"]]["cls"]
    s2 = r.choice(sorted(a for a, acc in X.accounts.items() if acc["cls"] == cls and acc["status"] == "ACTIVE"
                         and a not in involved))
    X.merges.append({"id": "MG-25-09600", "pred": mg["pred"], "succ": s2, "eff": date(2025, 10, r.randint(1, 28)),
                     "status": "COMPLETED"})
    T(X, "account_merges_2025.json", "T13", "R-MERGE-CHAIN", (mg["pred"], mg["succ"], s2),
      "the latest effective merge of a predecessor wins")
    X.cal.sort(key=lambda e: e["uid"])


def _quantize_rows(X):
    for fn in READ_FILES:
        for row in X.reads[fn]:
            m = row["meter"]
            res = X.meters[m]["res"] if m in X.meters else 3
            q = Decimal(1).scaleb(-res)
            if row.get("imp") is not None and not row.get("wh_issue"):
                row["imp"] = row["imp"].quantize(q, rounding=ROUND_FLOOR)
            if row.get("exp") is not None and not row.get("wh_issue"):
                row["exp"] = row["exp"].quantize(q, rounding=ROUND_FLOOR)


def _devices(X, r):
    """Per-HES device identities and parsing profiles (canonical facts)."""
    def uniq(make):
        while True:
            v = make()
            if v not in X.used_ids:
                X.used_ids.add(v)
                return v
    X.uniq = uniq
    X.eui = {}           # meter -> eui (Cirrus)
    X.spid_of = {}       # meter -> spid (Delta)
    X.legacy_of = {}     # meter -> legacy id (CIS)
    X.xref = []          # (spid, meter, from_t, to_t)
    for m in sorted(X.meters, key=lambda z: ("replaces" in X.meters[z], z)):
        info = X.meters[m]
        if info["hes"] == "C":
            X.eui[m] = uniq(lambda: "".join(r.choice("0123456789ABCDEF") for _ in range(16)))
        elif info["hes"] == "D":
            if "replaces" in info:
                X.spid_of[m] = X.spid_of[info["replaces"]]
            else:
                X.spid_of[m] = uniq(lambda: "SP" + str(r.randint(10 ** 8, 10 ** 9 - 1)))
        elif info["hes"] == "E":
            X.legacy_of[m] = uniq(lambda: "L-" + str(r.randint(100000, 999999)))
    # Delta: xref rows, one per meter service window
    for e in X.exchanges:
        X.meters[e["old"]]["removed_t"] = e["t"]
    for m in sorted(X.spid_of):
        info = X.meters[m]
        frm = local_to_utc(info.get("install") or date(2015, 1, 1)) if "installed" not in info else info["installed"]["t"]
        to = info.get("removed_t")
        X.xref.append({"spid": X.spid_of[m], "meter": m, "from": frm, "to": to})
    # Aurora firmware history (Wh units for AU-2.x)
    X.aur_fw = []
    for m in sorted(X.meters):
        if X.meters[m]["hes"] != "A":
            continue
        hist = []
        d = date(r.randint(2016, 2019), r.randint(1, 12), 1)
        for _ in range(r.randint(5, 6)):
            hist.append({"meter": m, "fw": r.choice(["AU-2.4", "AU-2.7", "AU-3.1", "AU-3.2"]), "from": d})
            d = date(d.year + 1, r.randint(1, 12), 1) if d.year < 2023 else (date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1))
        X.aur_fw += hist
    aur = sorted({x["meter"] for x in X.aur_fw})
    for m in r.sample(aur, 6):
        cur = [x for x in X.aur_fw if x["meter"] == m][-1]["fw"]
        X.aur_fw.append({"meter": m, "fw": "AU-3.2" if cur.startswith("AU-2") else "AU-2.7", "from": date(2025, 11, r.randint(5, 25))})
        T(X, "aurora_hes_profile.yaml", "T2", "R-AURORA-UNIT", m, "firmware changes units mid-month")
    # Cirrus firmware history (decimal comma for CX-4.1.x)
    X.cir_fw = []
    for m in sorted(X.eui):
        d = date(r.randint(2016, 2020), r.randint(1, 12), 1)
        for _ in range(r.randint(4, 6)):
            X.cir_fw.append({"eui": X.eui[m], "fw": r.choice(["CX-3.9.2", "CX-4.1.0", "CX-4.1.3", "CX-4.2.0"]), "from": d})
            d = date(d.year + 1, r.randint(1, 12), 1) if d.year < 2023 else (date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1))
        pass
    for m in r.sample(sorted(X.eui), 6):
        cur = [x for x in X.cir_fw if x["eui"] == X.eui[m]][-1]["fw"]
        X.cir_fw.append({"eui": X.eui[m], "fw": "CX-4.2.0" if cur.startswith("CX-4.1") else "CX-4.1.3", "from": date(2025, 11, r.randint(5, 25))})
        T(X, "cirrus_hes_profile.yaml", "T4", "R-CIRRUS-LOCALE", m, "firmware change switches decimal separator")
    # Borealis channel maps
    X.bor_ch = []
    for m in sorted(X.meters):
        if X.meters[m]["hes"] != "B":
            continue
        d = date(r.randint(2015, 2019), r.randint(1, 12), 1)
        for _ in range(r.randint(4, 6)):
            pair = r.choice([(1, 2), (1, 2), (2, 1), (3, 4), (1, 3)])
            X.bor_ch.append({"meter": m, "imp": pair[0], "exp": pair[1], "from": d})
            d = date(d.year + 1, r.randint(1, 12), 1) if d.year < 2023 else (date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1))
        pass
    for m in r.sample(sorted({x["meter"] for x in X.bor_ch}), 6):
        X.bor_ch.append({"meter": m, "imp": 5, "exp": 6, "from": date(2025, 11, r.randint(5, 25))})
        T(X, "borealis_channel_map.toml", "T8", "R-BOREALIS-CHANNEL", m, "channel map changes mid-month")
    # Fjord multiplier-applied flag
    X.fj_flag = []
    X.fj_flag_2026 = []
    for m in sorted(X.meters):
        if X.meters[m]["hes"] != "F":
            continue
        d = date(r.randint(2015, 2020), r.randint(1, 12), 1)
        for _ in range(r.randint(3, 4)):
            X.fj_flag.append({"meter": m, "applied": X.meters[m]["mult"] > 1 and r.chance(0.5), "from": d})
            d = date(d.year + 1, r.randint(1, 12), 1) if d.year < 2023 else (date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1))
        X.fj_flag_2026.append({"meter": m, "applied": X.meters[m]["mult"] > 1, "from": date(2026, 1, r.randint(5, 28))})
    fmult = [m for m in sorted(X.meters) if X.meters[m]["hes"] == "F" and X.meters[m]["mult"] > 1]
    for m in r.sample(fmult, min(6, len(fmult))):
        cur = [x for x in X.fj_flag if x["meter"] == m][-1]["applied"]
        X.fj_flag_2026.append({"meter": m, "applied": not cur, "from": date(2025, 11, r.randint(6, 24))})
        T(X, "fjord_hes_profile_2026.yaml", "T2", "R-FJORD-MULT", m, "in-window entry of the 2026 profile")
    # CIS dial constants (legacy electromechanical registers)
    X.dial = {}
    for m in sorted(X.legacy_of):
        X.dial[X.legacy_of[m]] = 10 if (X.meters[m]["res"] <= 2 and r.chance(0.25)) else 1
    X.dial_retired = {}
    while len(X.dial) + len(X.dial_retired) < 5200:
        X.dial_retired[uniq(lambda: "L-" + str(r.randint(100000, 999999)))] = r.choice([1, 10, 100])
    # Delta est policy per SPID
    X.delta_policy = {}
    for m, s in sorted(X.spid_of.items()):
        X.delta_policy[s] = "ACCEPT" if r.chance(0.7) else "REJECT"
    while len(X.delta_policy) < 5200:
        X.delta_policy[uniq(lambda: "SP" + str(r.randint(10 ** 8, 10 ** 9 - 1)))] = r.choice(["ACCEPT", "REJECT"])
    # Delta rows flagged as vendor estimates
    for k in range(6):
        rows = X.reads[read_file_name("D", k)]
        for idx in _spread(len(rows), 3, r):
            row = rows[idx]
            m = row["meter"]
            if not _plain(X, m):
                continue
            row["est"] = 1
            if X.delta_policy[X.spid_of[m]] == "REJECT":
                row["imp"] = _bump(r, row["imp"])
                row["perturbed"] = True
            T(X, read_file_name("D", k), "T5", "R-DELTA-EST", (m, row["b"]), X.delta_policy[X.spid_of[m]])


def _events_and_decoys(X, r):
    meters = sorted(X.meters)
    X.conn = [{"meter": m, "feeder": X.meters[m]["feeder"]} for m in meters]
    X.digits = {m: X.meters[m]["digits"] for m in meters}
    X.clock = {m: X.meters[m]["clock"] for m in meters}
    # collector events
    X.collector_events = []
    for x in X.resets:
        info = X.meters[x["meter"]]
        X.collector_events.append({"type": "REGISTER_RESET", "meter": x["meter"], "t": x["t"], "pre": info["reset_pre"], "post": x["post"]})
        T(X, "collector_events_2025-11.log", "T15", "R-RESET", x["meter"], "reset explains negative delta")
    for s in X.syncs:
        X.collector_events.append({"type": "CLOCK_SYNC", "meter": s["meter"], "t": s["t"], "corr": s["corr"]})
        T(X, "collector_events_2025-11.log", "T3", "R-CLOCK", s["meter"], "offset stops applying after sync")
    t0 = local_to_utc(date(2025, 11, 1))
    while len(X.collector_events) < 5300:
        m = r.choice(meters)
        X.collector_events.append({"type": r.choice(["TAMPER", "OUTAGE_START", "OUTAGE_END", "LAST_GASP", "COVER_OPEN"]),
                                   "meter": m, "t": t0 + r.randint(0, 30 * 86400)})
    X.collector_events.sort(key=lambda e: (e["t"], e["meter"]))
    # draft manual errata (decoy DC09) and CAB approvals in the mailbox
    X.draft_errata = []
    X.cab_approved = set()
    X.cab_rejected = set()
    for i, m in enumerate(r.sample(meters, 10)):
        cab = f"CR-{r.randint(1000, 9999)}"
        cur = X.read_time_fn(m, DEC1)
        val = "23:00" if cur == "00:00" else "00:00"
        X.draft_errata.append({"id": f"DE-{100 + i}", "table": "R", "key": m, "value": val,
                               "from": date(2025, 11, r.randint(4, 24)), "cab": cab})
        if i % 2 == 0:
            X.cab_approved.add(cab)
            T(X, "settlement_procedures_manual_rev4_draft.docx", "T7", "R-DRAFT-ERRATA", m, "approved draft erratum")
        else:
            X.cab_rejected.add(cab)
            T(X, "settlement_procedures_manual_rev4_draft.docx", "T6", "R-DRAFT-ERRATA", m, "erratum not approved")
    for i, f in enumerate(r.sample(FEEDERS, 3)):
        cab = f"CR-{r.randint(1000, 9999)}"
        X.draft_errata.append({"id": f"DE-{200 + i}", "table": "L", "key": f,
                               "value": X.feeder_loss_pct[f] + Decimal(r.randint(-400, 400)) / 1000, "from": MONTH_START, "cab": cab})
        if i < 2:
            X.cab_approved.add(cab)
        else:
            X.cab_rejected.add(cab)
        T(X, "settlement_procedures_manual_rev4_draft.docx", "T14", "R-DRAFT-ERRATA", f, "loss factor erratum")
    X.draft_loss = {f: X.feeder_loss_pct[f] + Decimal(r.randint(-900, 900)) / 1000 for f in FEEDERS}
    X.draft_schedule = []
    for row in X.schedule_rows:
        x = dict(row)
        if r.chance(0.02):
            x["read_time"] = "23:00" if x["read_time"] == "00:00" else "00:00"
            x["changed"] = True
        X.draft_schedule.append(x)
    # Fjord resend (decoy DC03)
    p4 = X.reads[read_file_name("F", 3)]
    X.resend_rows = []
    for row in p4:
        if row.get("stray") or row["meter"].startswith("GHOST"):
            continue
        x = dict(row)
        x["seq"] = row["seq"] + 5000000
        if row.get("perturbed") and not row.get("reversed") and r.chance(0.7):
            info = X.meters[row["meter"]]
            x["imp"] = info["reg"].get(row["b"], row["imp"])
            x["fixed"] = True
        elif r.chance(0.01):
            x["imp"] = _bump(r, row["imp"]).quantize(Decimal(1).scaleb(-X.meters[row["meter"]]["res"]), rounding=ROUND_FLOOR)
            x["differs"] = True
        x["sentinel"] = False
        X.resend_rows.append(x)
    for v in X.reversals:
        X.resend_rows.append({"rev": True, "meter": v["meter"], "b": v["b"], "seq": v["seq"]})
    # debug log echo lines (decoy DC12): parsed values mostly agree with the files
    X.debug_echo = []
    for fn in READ_FILES[::3]:
        rows = X.reads[fn]
        for row in rows[::4]:
            if row["meter"].startswith("GHOST"):
                continue
            v = row["imp"]
            if row.get("perturbed") is None and r.chance(0.04):
                v = _bump(r, v)
            X.debug_echo.append({"file": fn, "meter": row["meter"], "b": row["b"], "imp": v})
    # portal usage (decoy DC15): account x period usage, close to but not equal to settlement
    X.portal = []
    for a in sorted(X.accounts):
        if X.accounts[a]["cls"] == "LIT":
            continue
        ms = [m for m in meters if X.meters[m].get("account") == a and "replaces" not in X.meters[m]]
        if not ms:
            continue
        for k, (lo, hi) in enumerate([(0, 10), (10, 20), (20, 30)]):
            tot = sum(sum(X.meters[m]["d_imp"][lo:hi]) * X.meters[m]["mult"] for m in ms)
            if r.chance(0.05):
                tot = tot * Decimal(r.randint(80, 120)) / 100
            X.portal.append({"acct": a, "period": f"2025-11-{lo + 1:02d}/{hi:02d}", "kwh": tot.quantize(Decimal("0.01"))})
    # DW snapshot (decoy DC13): attributes as of 2025-12-03
    X.snapshot = []
    for m in meters:
        info = X.meters[m]
        mult = info["mult"]
        if "ct" in info:
            mult = info["ct"]["new"]
        if r.chance(0.03):
            mult = r.choice([1, 40, 80, 120, 200])
        X.snapshot.append({"meter": m, "account": info.get("account"), "mult": mult, "feeder": info["feeder"],
                           "hes": HES_CODE[info["hes"]], "as_of": date(2025, 12, 3)})
    X.snapshot_log = []
    for i in range(5200):
        X.snapshot_log.append({"seq": i + 1, "meter": r.choice(meters), "change": r.choice(["ATTR_REFRESH", "ACCOUNT_LINK", "MULT_SYNC"]),
                               "at": date(2025, 12, 3) - timedelta(days=r.randint(0, 120))})
    while len(X.xref) < 5300:
        X.xref.append({"spid": X.uniq(lambda: "SP" + str(r.randint(10 ** 8, 10 ** 9 - 1))), "meter": X.new_id("KV", 7, r, 0.5),
                       "from": local_to_utc(date(r.randint(2010, 2020), r.randint(1, 12), 1)),
                       "to": local_to_utc(date(r.randint(2021, 2024), r.randint(1, 12), 1))})
    # Cirrus daily usage (decoy DC04): eui x period, carries the eui -> meter link
    X.cirrus_usage = []
    for m in sorted(X.eui):
        info = X.meters[m]
        for k, (lo, hi) in enumerate(PERIODS6):
            if not any(lo <= b <= hi for b in _service_range(info)):
                continue
            days = [b - 1 for b in range(lo, hi + 1) if b in _service_range(info) and b >= 1]
            kwh = sum(info["d_imp"][d] for d in days) * info["mult"]
            if r.chance(0.05):
                kwh = kwh * Decimal(r.randint(85, 115)) / 100
            X.cirrus_usage.append({"eui": X.eui[m], "meter": m, "period": k + 1, "kwh": kwh.quantize(Decimal("0.001"))})
    # legacy crosswalk & attributes (decoy DC05)
    X.legacy_xwalk = [{"legacy": X.legacy_of[m], "meter": m} for m in sorted(X.legacy_of)]
    for lid in sorted(X.dial_retired):
        X.legacy_xwalk.append({"legacy": lid, "meter": "RETIRED"})
    X.legacy_attr = []
    for m in meters:
        info = X.meters[m]
        mult = info["mult"] if r.chance(0.96) else r.choice([1, 40, 80, 120])
        X.legacy_attr.append({"meter": m, "mult": mult, "digits": info["digits"], "feeder": info["feeder"]})
    # December master (decoy DC01)
    X.master_dec = []
    for a in sorted(X.accounts):
        acc = X.accounts[a]
        code = acc["code"] if r.chance(0.9) else r.choice(RATE_CODES[acc["cls"]])
        st = acc["status"]
        fin = acc["final"]
        if st == "ACTIVE" and r.chance(0.01):
            st, fin = "FINAL", date(2025, 12, r.randint(1, 20))
        X.master_dec.append({"id": a, "cls": acc["cls"], "code": code, "status": st, "final": fin,
                             "merged_into": "", "merge_eff": None, "late": ""})
    by = {x["id"]: x for x in X.master_dec}
    for lm in X.late_merges:
        x = by.get(lm["pred"])
        if x:
            x["merged_into"] = lm["succ"]
            x["merge_eff"] = lm["eff"]
            x["late"] = "Y"
    for mg in X.merges:
        if mg["status"] == "COMPLETED" and mg["pred"] in by and nov(mg["eff"]):
            by[mg["pred"]]["merged_into"] = mg["succ"]
            by[mg["pred"]]["merge_eff"] = mg["eff"]
            by[mg["pred"]]["late"] = "N"
    # vendor manifest (decoy DC08): YTD deliveries + November batches
    X.manifest_days = []
    for h in "ABCDEF":
        for d in drange(date(2025, 1, 1), date(2025, 11, 1)):
            for stream in ("register_reads", "events", "device_status"):
                X.manifest_days.append({"hes": HES_CODE[h], "date": d, "stream": stream, "files": r.randint(1, 3),
                                        "records": r.randint(900, 9000), "status": "DELIVERED" if r.chance(0.98) else "WITHDRAWN"})


# ---------------------------------------------------------------------------
# part 3 - settlement truth.  Applies the documented rules to the logical
# tables.  The reference solution re-derives the same tables from the files.
# ---------------------------------------------------------------------------
def _latest(rows, key):
    best = None
    for x in rows:
        if best is None or key(x) > key(best):
            best = x
    return best


def compute_truth(X):
    R = {}
    meters = sorted(X.meters)
    # ---- schedule (manual appendix R + CAB-approved draft errata)
    sched = {}
    for row in X.schedule_rows:
        sched.setdefault(row["meter"], []).append((row["from"], 0, row["read_time"]))
    for e in X.draft_errata:
        if e["table"] == "R" and e["cab"] in X.cab_approved:
            sched.setdefault(e["key"], []).append((e["from"], 1, e["value"]))
    for m in sched:
        sched[m].sort()

    def read_time(m, bdate):
        cur = "00:00"
        for frm, _p, val in sched.get(m, []):
            if frm <= bdate:
                cur = val
        return cur
    loss_pct = dict(X.feeder_loss_pct)
    for e in X.draft_errata:
        if e["table"] == "L" and e["cab"] in X.cab_approved:
            loss_pct[e["key"]] = e["value"]
    # ---- service windows
    install_t = {}
    removal_t = {}
    for e in X.exchanges:
        removal_t[e["old"]] = e["t"]
        install_t[e["new"]] = e["t"]
    sync_t = {s["meter"]: s["t"] for s in X.syncs}
    # ---- exclusion keys
    void_keys = {(v["hes"], v["meter"], v["date"]) for v in X.voids if v["reinstated"] == "N"}
    disp_last = {}
    for d in sorted(X.disputes, key=lambda d: d.get("decided", date(2025, 1, 1))):
        disp_last[(d["meter"], d["date"])] = d["outcome"]
    disp_keys = {k for k, v in disp_last.items() if v == "UPHELD"}
    rev_keys = {(x["meter"], x["b"]) for x in X.reversals}
    hold_state = {}
    for h in sorted(X.holds, key=lambda h: h["t"]):
        k = (h["meter"], h["date"])
        if h["type"] == "HOLD":
            hold_state[k] = "HELD"
        elif h["type"] == "RELEASE" and h["t"] <= CUTOFF_UTC and hold_state.get(k) == "HELD":
            hold_state[k] = "RELEASED"
    quar_state = {}
    for q in sorted(X.quarantine, key=lambda q: q.get("t", 0)):
        quar_state[(q["meter"], q["date"], q["hes"])] = q.get("action", "QUARANTINE")
    quar_keys = {k for k, v in quar_state.items() if v == "QUARANTINE"}
    issues = {}
    for k in X.known_issues:
        if k["status"] == "OPEN":
            issues[(k["meter"], k["date"], k["hes"])] = k["code"]
    corr = {}
    for c in X.corrections:
        if c["status"] == "VALIDATED":
            k = (c["meter"], c["date"])
            if k not in corr or c["rev"] > corr[k]["rev"]:
                corr[k] = c
    review = {}
    for v in sorted(X.vee_reviews, key=lambda v: v["on"]):
        review[v["est"]] = v["status"]
    vee = {}
    for v in X.vee:
        if review.get(v["id"]) == "APPROVED":
            k = (v["meter"], v["date"])
            if k not in vee or v["version"] > vee[k]["version"]:
                vee[k] = v
    # ---- candidate reads
    cands = {}
    for fn in READ_FILES:
        rows = X.reads[fn]
        part = X.batch_partial.get(fn)
        wd = X.withdrawn.get(fn)
        for ordinal, row in enumerate(rows, 1):
            m = row["meter"]
            if m.startswith("GHOST") or row.get("sentinel") or m not in X.meters:
                continue
            if row["hes"] == "D" and row.get("est") and X.delta_policy.get(X.spid_of[m]) == "REJECT":
                continue
            if row["hes"] == "C" and row.get("stray"):
                continue
            if part and part[0] <= ordinal <= part[1]:
                continue
            if wd and wd[0] <= ordinal <= wd[1]:
                continue
            t = row["t"]
            off = X.meters[m]["clock"]
            corrected = t - off if (m not in sync_t or t - off < sync_t[m]) else t
            if m in install_t and corrected < install_t[m]:
                continue
            if m in removal_t and corrected >= removal_t[m]:
                continue
            b = None
            for bb in range(1, 31):
                bd = BOUNDARY_DATES[bb]
                if abs(corrected - sched_utc(read_time(m, bd), bd)) <= 900:
                    b = bb
                    break
            if b is None:
                continue
            bdate = BOUNDARY_DATES[b]
            hes = HES_CODE[row["hes"]]
            if (hes, m, bdate) in void_keys or (m, bdate) in disp_keys:
                continue
            if fn == read_file_name("F", 3) and (m, b) in rev_keys:
                continue
            if hold_state.get((m, bdate)) == "HELD":
                continue
            if (m, bdate, hes) in quar_keys:
                continue
            imp, exp = row["imp"], row["exp"]
            code = issues.get((m, bdate, hes))
            if code == "STUCK_REGISTER":
                continue
            if code == "WH_AS_KWH":
                imp = imp / 1000
                exp = exp / 1000 if exp is not None else None
            elif code == "SWAP_REGISTERS":
                imp, exp = exp, imp
            dist = abs(corrected - sched_utc(read_time(m, bdate), bdate))
            cands.setdefault((m, b), []).append((dist, -row["seq"], imp, exp))
    # ---- boundary resolution
    bval = {}
    src = {}
    for o in X.opening:
        bval[(o["meter"], 0)] = (o["imp"], o["exp"])
        src[(o["meter"], 0)] = "ACTUAL"
    for (m, b), lst in cands.items():
        lst.sort(key=lambda z: (z[0], z[1]))
        bval[(m, b)] = (lst[0][2], lst[0][3])
        src[(m, b)] = "ACTUAL"
    for m in meters:
        for b in _service_range(X.meters[m]):
            bdate = BOUNDARY_DATES[b]
            if (m, bdate) in corr:
                c = corr[(m, bdate)]
                bval[(m, b)] = (c["imp"], c["exp"])
                src[(m, b)] = "CORRECTION"
            elif (m, b) not in bval and (m, bdate) in vee:
                v = vee[(m, bdate)]
                bval[(m, b)] = (v["imp"], v["exp"])
                src[(m, b)] = "ESTIMATE"
    # ---- multiplier timeline
    mult_events = {}
    for dist_rows in X.registry.values():
        for row in dist_rows:
            mult_events.setdefault(row["meter"], []).append((local_to_utc(row["from"]), 0, row["mult"]))
    for c in X.ct_orders:
        mult_events.setdefault(c["meter"], []).append((c["t"], 2, c["new"]))
    for v in X.ct_verif:
        if v["result"] == "FAIL" and v["action"] == "CORRECT_RATIO":
            mult_events.setdefault(v["meter"], []).append((local_to_utc(v["on"]), 1, v["measured"]))
    for m in mult_events:
        mult_events[m].sort()

    def mult_at(m, t):
        cur = 1
        for tt, _p, val in mult_events.get(m, []):
            if tt <= t:
                cur = val
        return cur
    # ---- segments
    day_index = {d: i for i, d in enumerate(DAYS)}
    m_imp = {}
    m_exp = {}
    resolution = []
    invalid_count = {}
    ex_by_old = {e["old"]: e for e in X.exchanges}
    ex_by_new = {e["new"]: e for e in X.exchanges}
    ct_by = {c["meter"]: c for c in X.ct_orders}
    rs_by = {x["meter"]: x for x in X.resets}
    for m in meters:
        info = X.meters[m]
        mod = Decimal(10) ** info["digits"]
        anchors = []
        for b in _service_range(info):
            bd = BOUNDARY_DATES[b]
            t = sched_utc(read_time(m, bd), bd)
            v = bval.get((m, b))
            anchors.append({"t": t, "kind": "B", "b": b, "imp": v[0] if v else None, "exp": v[1] if v else None})
        if m in ex_by_old:
            e = ex_by_old[m]
            o = [x for x in X.orders if x["type"] == "EXCHANGE" and x["status"] == "COMPLETED" and x["old"] == m][0]
            anchors.append({"t": e["t"], "kind": "EXF", "imp": o["old_imp"], "exp": o["old_exp"]})
        if m in ex_by_new:
            e = ex_by_new[m]
            o = [x for x in X.orders if x["type"] == "EXCHANGE" and x["status"] == "COMPLETED" and x["new"] == m][0]
            anchors.append({"t": e["t"], "kind": "EXI", "imp": o["new_imp"], "exp": o["new_exp"]})
        if m in ct_by:
            o = [x for x in X.orders if x["type"] == "CT_CHANGE" and x["status"] == "COMPLETED" and x.get("meter") == m
                 and nov(utc_to_local(x["t"])[0].date())][0]
            anchors.append({"t": o["t"], "kind": "CT", "imp": o["read"], "exp": None})
        if m in rs_by:
            ev = [x for x in X.collector_events if x["type"] == "REGISTER_RESET" and x["meter"] == m][0]
            anchors.append({"t": ev["t"], "kind": "RS", "imp": ev["pre"], "post": ev["post"], "exp": None})
        anchors.sort(key=lambda a: (a["t"], 0 if a["kind"] == "EXI" else 1))
        for reg, store in (("imp", m_imp), ("exp", m_exp)):
            prev = None
            for a in anchors:
                val = a.get(reg)
                if val is None:
                    continue
                if prev is None:
                    prev = (a["t"], a["post"] if a["kind"] == "RS" else val)
                    continue
                if a["kind"] == "RS":
                    delta = val - prev[1]
                    nxt = (a["t"], a["post"])
                else:
                    delta = val - prev[1]
                    nxt = (a["t"], val)
                    if delta < 0:
                        if prev[1] >= mod * Decimal("0.9") and val < mod * Decimal("0.1"):
                            delta += mod
                        elif a["kind"] == "B":
                            if reg == "imp":
                                invalid_count[m] = invalid_count.get(m, 0) + 1
                                src[(m, a["b"])] = "INVALIDATED:" + str(val)
                            continue
                close = a["t"]
                d = utc_to_local(close - 1)[0].date()
                if d in day_index:
                    wh = int(delta * 1000) * mult_at(m, close - 1)
                    store[(m, d)] = store.get((m, d), 0) + wh
                prev = nxt
    # ---- accuracy correction
    fails = {}
    for t_ in X.acc_tests:
        if t_["result"] == "FAIL" and nov(t_["date"]):
            if t_["meter"] not in fails or (t_["date"], t_["id"]) > (fails[t_["meter"]]["date"], fails[t_["meter"]]["id"]):
                fails[t_["meter"]] = t_
    for m, t_ in fails.items():
        for d in DAYS:
            if d < t_["date"] and (m, d) in m_imp:
                m_imp[(m, d)] = int_even(Decimal(m_imp[(m, d)]) * 100 / (100 + t_["error"]))
    # ---- account mapping
    reg_rows = {}
    for dist_rows in X.registry.values():
        for row in dist_rows:
            reg_rows.setdefault(row["meter"], []).append(row)
    merges = [x for x in X.merges if x["status"] == "COMPLETED"] + \
             [{"pred": x["pred"], "succ": x["succ"], "eff": x["eff"]} for x in X.late_merges if x["eff"] <= NOV30]
    merge_by_pred = {}
    for x in merges:
        merge_by_pred.setdefault(x["pred"], []).append(x)

    def resolve(acct, d):
        seen = set()
        while acct not in seen:
            seen.add(acct)
            cand = [x for x in merge_by_pred.get(acct, []) if x["eff"] <= d]
            if not cand:
                break
            acct = max(cand, key=lambda x: x["eff"])["succ"]
        return acct
    master = {a: X.accounts[a] for a in X.accounts}
    for x in X.master_extra:
        master.setdefault(x["id"], x)

    def acct_on(m, d):
        for row in reg_rows.get(m, []):
            if row["from"] <= d and (row["to"] is None or d < row["to"]):
                return row["account"]
        return None
    disc = {}
    for e in X.disc:
        if e["ref"].startswith("SOX"):
            continue
        disc.setdefault(e["meter"], []).append(e)
    nem = {}
    for n in X.nem:
        if n["status"] == "APPROVED":
            nem.setdefault(n["meter"], []).append(n)
    insp = {}
    for i in X.inspections:
        insp.setdefault(i["meter"], []).append(i)

    def disconnected(m, d):
        last = None
        for e in disc.get(m, []):
            if e["date"] <= d and (last is None or (e["date"], e["event"] == "RECONNECT") > (last["date"], last["event"] == "RECONNECT")):
                last = e
        return last is not None and last["event"] == "DISCONNECT"

    def export_ok(m, d):
        if not any(n["from"] <= d and (n["to"] is None or d < n["to"]) for n in nem.get(m, [])):
            return False
        last = None
        for i in insp.get(m, []):
            # contract section 5: latest inspection on or before d, a FAIL on the same date wins
            if i["on"] <= d and (last is None or (i["on"], i["result"] == "FAIL") >= (last["on"], last["result"] == "FAIL")):
                last = i
        return last is not None and last["result"] == "PASS"
    # ---- rate code
    reversed_entries = {x["entry"] for x in X.restated_reversals}
    alias_map = {legacy_alias(c): c for c in ALL_CODES}
    early = [x for x in X.early_adopters if x.get("status", "ACTIVE") == "ACTIVE"]
    hist = {}
    for x in X.rate_hist:
        if x["entry"] in reversed_entries:
            continue
        code = x["code"]
        hist.setdefault(x["acct"], []).append((x["from"], 0, x["entry"], code))
    for x in early:
        hist.setdefault(x["acct"], []).append((x["eff"], 1, 0, x["new_code"]))
    for a in hist:
        hist[a].sort()

    def code_on(a, d):
        cur = None
        for frm, _p, _e, code in hist.get(a, []):
            if frm <= d:
                cur = code
        return cur or master[a]["code"]
    # ---- daytype
    daytype = {}
    for t in TERRITORIES:
        for d in DAYS:
            dt = "WEEKEND" if d.weekday() >= 5 else "WEEKDAY"
            for e in X.cal:
                if e["territory"] == t and e["status"] == "CONFIRMED" and e["start"] <= d < e["end"]:
                    if e["kind"] == "HOLIDAY":
                        dt = "HOLIDAY"
                        break
                    if e["kind"] == "CPP":
                        dt = "CPP"
            daytype[(t, d)] = dt
    # ---- rates
    err = {}
    superseded = {e["supersedes"] for e in X.tariff_errata if e["status"] == "APPROVED" and e["supersedes"]}
    for e in X.tariff_errata:
        if e["status"] != "APPROVED" or e["id"] in superseded:
            continue
        k = (e["code"], e["date"], e["dt"])
        if k not in err or (e["issued"], int(e["id"].split("-")[1])) > (err[k]["issued"], int(err[k]["id"].split("-")[1])):
            err[k] = e

    def base_rate(code, d, dt):
        k = (code, d, dt)
        return err[k]["rate"] if k in err else X.rates[k]
    riders = {}
    for x in X.rider_rows:
        if x["status"] == "ACTIVE":
            riders.setdefault((x["rider"], x["code"]), []).append(x)
    appl = {}
    for x in X.applicability:
        appl.setdefault((x["code"], x["rider"], x["territory"]), []).append(x)
    storm = [x for x in X.storm_rows if x["from"] <= NOV30 and x["status"] == "APPROVED"]

    def adders(code, d, terr):
        tot = Decimal(0)
        for rd in RIDERS:
            row = None
            for x in riders.get((rd, code), []):
                if x["from"] <= d < x["to"]:
                    row = x
            if row is None:
                continue
            flag = None
            for a in sorted(appl.get((code, rd, terr), []), key=lambda z: z["from"]):
                if a["from"] <= d:
                    flag = a["flag"]
            if flag == "Y":
                tot += row["adder"]
        for x in storm:
            if x["code"] == code and x["from"] <= d:
                tot += x["adder"]
        return tot
    # ---- per account accumulation
    acc = {}

    def A(a):
        if a not in acc:
            acc[a] = {"imp": 0, "exp": 0, "deemed": 0, "energy": Decimal(0), "rider": Decimal(0), "credit": Decimal(0),
                      "last_day": None}
        return acc[a]
    msum = {}
    feeder_tot = {f: {"billed_import_wh": 0, "billed_export_wh": 0, "deemed_wh": 0, "unbilled_wh": 0} for f in FEEDERS}
    conn = {c["meter"]: c["feeder"] for c in X.conn}
    for m in meters:
        info = X.meters[m]
        f = conn[m]
        terr = X.feeder_territory[f]
        rec = {"import_wh": 0, "billed_import_wh": 0, "unbilled_wh": 0, "export_wh": 0}
        for d in DAYS:
            wi = m_imp.get((m, d), 0)
            we = m_exp.get((m, d), 0)
            if (m, d) not in m_imp and (m, d) not in m_exp:
                continue
            rec["import_wh"] += wi
            a0 = acct_on(m, d)
            if a0 is None:
                rec["unbilled_wh"] += wi
                feeder_tot[f]["unbilled_wh"] += wi
                continue
            a = resolve(a0, d)
            vac = master.get(a, {}).get("status") == "FINAL" and master[a]["final"] is not None and master[a]["final"] <= d
            if vac or disconnected(m, d):
                rec["unbilled_wh"] += wi
                feeder_tot[f]["unbilled_wh"] += wi
                continue
            ex = we if (we and export_ok(m, d)) else 0
            rec["billed_import_wh"] += wi
            rec["export_wh"] += ex
            feeder_tot[f]["billed_import_wh"] += wi
            feeder_tot[f]["billed_export_wh"] += ex
            if wi == 0 and ex == 0:
                continue
            s = A(a)
            code = code_on(a, d)
            dt = daytype[(terr, d)]
            s["imp"] += wi
            s["exp"] += ex
            s["energy"] += Decimal(wi) * base_rate(code, d, dt) / 1000
            s["rider"] += Decimal(wi) * adders(code, d, terr) / 1000
            if ex:
                s["credit"] += Decimal(ex) * X.export_rates[(code, d, dt)] / 1000
            s["last_day"] = d
        msum[m] = rec
    # ---- lighting
    audits = {}
    for x in X.audit:
        audits.setdefault(x["fixture"], []).append(x)
    exc = {(x["fixture"], x["date"]): x["hours"] for x in X.burn_exc}
    lighting = []
    for fid in sorted(X.fixtures):
        fx = X.fixtures[fid]
        tot = 0
        days = 0
        terr = X.feeder_territory[fx["feeder"]]
        for d in DAYS:
            if d < fx["install"] or (fx["removal"] is not None and d >= fx["removal"]):
                continue
            watts = fx["watts"]
            removed = False
            for x in sorted(audits.get(fid, []), key=lambda z: z["eff"]):
                if x["eff"] <= d:
                    if x["status"] == "REMOVED":
                        removed = True
                    elif x["status"] == "WATTAGE_CHANGE":
                        watts = x["watts"]
            if removed:
                continue
            if (fid, d) in exc:
                hours = exc[(fid, d)]
            elif fx["profile"] == "ALL_DAY":
                hours = Decimal("24.00")
            elif fx["profile"] == "PART_NIGHT":
                hours = max(Decimal(0), X.burn[(fx["feeder"], d)] - PART_NIGHT_LESS)
            else:
                hours = X.burn[(fx["feeder"], d)]
            wh = int_even(Decimal(watts) * hours)
            if wh <= 0:
                continue
            tot += wh
            days += 1
            a = fx["acct"]
            s = A(a)
            code = code_on(a, d)
            dt = daytype[(terr, d)]
            s["deemed"] += wh
            s["energy"] += Decimal(wh) * base_rate(code, d, dt) / 1000
            s["rider"] += Decimal(wh) * adders(code, d, terr) / 1000
            s["last_day"] = d
            feeder_tot[fx["feeder"]]["deemed_wh"] += wh
        if tot > 0:
            lighting.append({"fixture_id": fid, "account_id": fx["acct"], "burn_days": days, "deemed_wh": tot})
    # ---- SCADA
    alarms = {}
    for a in X.alarms:
        if a["type"] == "COMM_FAIL":
            alarms.setdefault(a["feeder"], []).append(a)
    serr = {}
    sup = {e["supersedes"] for e in X.scada_errata if e["status"] == "APPROVED" and e["supersedes"]}
    for e in X.scada_errata:
        if e["status"] != "APPROVED" or e["id"] in sup:
            continue
        k = (e["feeder"], e["t"])
        if k not in serr or (e["issued"], int(e["id"].split("-")[1])) > (serr[k]["issued"], int(serr[k]["id"].split("-")[1])):
            serr[k] = e
    intervals = []
    inj = {f: 0 for f in FEEDERS}
    for f in FEEDERS:
        for t in X.interval_ends:
            rec = X.scada[(f, t)]
            bad = rec["q"] != "GOOD" or any(a["raised"] < t and a["cleared"] > t - 900 for a in alarms.get(f, []))
            if (f, t) in serr:
                v, s_ = serr[(f, t)]["wh"], "ERRATUM"
            elif (f, t) in X.relay:
                v, s_ = X.relay[(f, t)], "RELAY_TEST"
            elif not bad:
                v, s_ = rec["wh"], "HISTORIAN"
            else:
                v, s_ = X.gapfill[(f, t)], "GAPFILL"
            inj[f] += v
            intervals.append({"feeder": f, "interval_end_utc": iso_utc(t), "injection_wh": v, "source": s_})
    loss = {f: int_even(Decimal(inj[f]) * loss_pct[f] / 100) for f in FEEDERS}
    # ---- UFE
    billed_imp = sum(v["imp"] for v in acc.values())
    deemed = sum(v["deemed"] for v in acc.values())
    billed_exp = sum(v["exp"] for v in acc.values())
    ufe = sum(inj.values()) + billed_exp - sum(loss.values()) - billed_imp - deemed
    exempt = set()
    for e in X.exemptions:
        if e["status"] == "ACTIVE" and e["from"] <= NOV30 and (e["to"] is None or NOV30 < e["to"]):
            exempt.add(e["acct"])
    rows = {}
    for a, v in acc.items():
        rows[a] = {"energy_cents": int_even(v["energy"]), "rider_cents": int_even(v["rider"]),
                   "export_credit_cents": -int_even(v["credit"])}
    weights = {a: v["imp"] + v["deemed"] for a, v in acc.items() if a not in exempt and v["imp"] + v["deemed"] > 0}
    alloc = hamilton(ufe, weights)
    tot_energy = sum(x["energy_cents"] for x in rows.values())
    tot_rider = sum(x["rider_cents"] for x in rows.values())
    price = (Decimal(tot_energy + tot_rider) * 1000 / Decimal(billed_imp + deemed)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    out_acc = []
    for a in sorted(acc):
        v = acc[a]
        if v["imp"] == 0 and v["exp"] == 0 and v["deemed"] == 0:
            continue
        u = alloc.get(a, 0)
        uc = int_even(Decimal(u) * price / 1000)
        row = rows[a]
        out_acc.append({"account_id": a, "rate_code": code_on(a, v["last_day"]), "billed_import_wh": v["imp"],
                        "billed_export_wh": v["exp"], "deemed_wh": v["deemed"], "energy_cents": row["energy_cents"],
                        "rider_cents": row["rider_cents"], "export_credit_cents": row["export_credit_cents"], "ufe_wh": u,
                        "ufe_charge_cents": uc,
                        "total_cents": row["energy_cents"] + row["rider_cents"] + row["export_credit_cents"] + uc})
    out_m = []
    res_rows = []
    for m in meters:
        info = X.meters[m]
        rng_b = list(_service_range(info))
        if not any((m, b) in bval for b in rng_b):
            continue
        cnt = {"CORRECTION": 0, "ESTIMATE": 0, "MISSING": 0, "INVALIDATED": 0}
        for b in rng_b:
            s_ = src.get((m, b), "MISSING")
            kind = s_.split(":")[0]
            if kind == "ACTUAL":
                continue
            cnt[kind] += 1
            val = ""
            if kind in ("CORRECTION", "ESTIMATE"):
                val = f"{bval[(m, b)][0]:.3f}"
            elif kind == "INVALIDATED":
                val = f"{Decimal(s_.split(':')[1]):.3f}"
            res_rows.append({"meter_id": m, "boundary_date": BOUNDARY_DATES[b].isoformat(), "source": kind, "import_kwh": val})
        rec = msum[m]
        out_m.append({"meter_id": m, "feeder": conn[m], "import_wh": rec["import_wh"], "billed_import_wh": rec["billed_import_wh"],
                      "unbilled_wh": rec["unbilled_wh"], "export_wh": rec["export_wh"],
                      "corrected_boundaries": cnt["CORRECTION"], "estimated_boundaries": cnt["ESTIMATE"],
                      "missing_boundaries": cnt["MISSING"], "invalidated_boundaries": cnt["INVALIDATED"]})
    fb = {}
    for f in FEEDERS:
        t_ = feeder_tot[f]
        fb[f] = {"injection_wh": inj[f], "loss_wh": loss[f], "billed_import_wh": t_["billed_import_wh"],
                 "billed_export_wh": t_["billed_export_wh"], "deemed_wh": t_["deemed_wh"], "unbilled_wh": t_["unbilled_wh"],
                 "residual_wh": inj[f] + t_["billed_export_wh"] - loss[f] - t_["billed_import_wh"] - t_["deemed_wh"]}
    summary = {
        "account_count": len(out_acc), "meter_count": len(out_m),
        "injection_wh": sum(inj.values()), "loss_wh": sum(loss.values()), "billed_import_wh": billed_imp,
        "billed_export_wh": billed_exp, "deemed_wh": deemed, "unbilled_wh": sum(r_["unbilled_wh"] for r_ in msum.values()),
        "ufe_wh": ufe, "ufe_price_cents_per_kwh": f"{price:.6f}",
        "energy_cents": tot_energy, "rider_cents": tot_rider,
        "export_credit_cents": sum(x["export_credit_cents"] for x in out_acc),
        "ufe_charge_cents": sum(x["ufe_charge_cents"] for x in out_acc),
        "total_cents": sum(x["total_cents"] for x in out_acc),
    }
    control = []
    for fn in READ_FILES + [RESEND_FILE]:
        n = len(X.reads[fn]) if fn != RESEND_FILE else len(X.resend_rows)
        part = X.batch_partial.get(fn)
        wd = X.withdrawn.get(fn)
        status = "REJECTED" if fn == RESEND_FILE else ("PARTIAL" if part else "ACCEPTED")
        control.append({"file": fn, "data_rows": n, "manifest_rows": n + X.vendor_drift.get(fn, 0),
                        "mdm_status": status,
                        "rejected_rows": n if fn == RESEND_FILE else (part[1] - part[0] + 1 if part else 0),
                        "withdrawn_rows": (wd[1] - wd[0] + 1) if wd else 0})
    cal_rows = [{"territory": t, "date": d.isoformat(), "daytype": daytype[(t, d)]} for t in sorted(TERRITORIES) for d in DAYS]
    control.sort(key=lambda c: c["file"])
    R["account_settlement.csv"] = out_acc
    R["meter_summary.csv"] = out_m
    R["read_resolution.csv"] = res_rows
    R["interval_injection.csv"] = intervals
    R["lighting_deemed.csv"] = lighting
    R["daytype_calendar.csv"] = cal_rows
    R["feeder_balance.json"] = {"feeders": fb}
    R["control_report.json"] = {"batches": control}
    R["settlement_summary.json"] = summary
    return R


def hamilton(total, weights):
    """Largest-remainder allocation of an integer total in proportion to weights."""
    if not weights:
        return {}
    sign = -1 if total < 0 else 1
    amount = abs(total)
    W = sum(weights.values())
    base = {}
    rema = []
    for a, w in weights.items():
        q, rem = divmod(amount * w, W)
        base[a] = q
        rema.append((-rem, a))
    left = amount - sum(base.values())
    rema.sort()
    for _r, a in rema[:left]:
        base[a] += 1
    return {a: sign * v for a, v in base.items()}


OUTPUT_COLUMNS = {
    "account_settlement.csv": ["account_id", "rate_code", "billed_import_wh", "billed_export_wh", "deemed_wh", "energy_cents",
                               "rider_cents", "export_credit_cents", "ufe_wh", "ufe_charge_cents", "total_cents"],
    "meter_summary.csv": ["meter_id", "feeder", "import_wh", "billed_import_wh", "unbilled_wh", "export_wh",
                          "corrected_boundaries", "estimated_boundaries", "missing_boundaries", "invalidated_boundaries"],
    "read_resolution.csv": ["meter_id", "boundary_date", "source", "import_kwh"],
    "interval_injection.csv": ["feeder", "interval_end_utc", "injection_wh", "source"],
    "lighting_deemed.csv": ["fixture_id", "account_id", "burn_days", "deemed_wh"],
    "daytype_calendar.csv": ["territory", "date", "daytype"],
}


def serialize(name, payload):
    if name.endswith(".csv"):
        cols = OUTPUT_COLUMNS[name]
        lines = [",".join(cols)] + [",".join(str(row[c]) for c in cols) for row in payload]
        return ("\n".join(lines) + "\n").encode("utf-8")
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# part 4a - rendering engine: trap planning, value formatting, read files
# ---------------------------------------------------------------------------
DECOYS = [
    "cis_account_master_2025-12.csv", "scada_15min_gapfill_2025-11.csv", "fjord_reads_2025-11_p4b.tsv",
    "cirrus_daily_usage_2025-11.jsonl", "meter_registry_migration_wave3.xlsx", "account_rate_history_restated.xlsx",
    "rate_code_crosswalk_2026.json", "hes_batch_manifest_2025-11.json", "settlement_procedures_manual_rev4_draft.docx",
    "tariff_book_residential_2026.pdf", "substation_east_monthly_report.pdf", "hes_ingest_debug.log",
    "dw_registry_snapshot_2025-12-03.db", "fjord_hes_profile_2026.yaml", "customer_portal_usage_export.html",
]
FAMILY_TEST = {
    "T1": "t01_identifier_canonicalisation", "T2": "t02_unit_and_scale", "T3": "t03_time_and_calendar",
    "T4": "t04_locale_numerics", "T5": "t05_sentinels", "T6": "t06_voided_and_cancelled", "T7": "t07_superseded_revisions",
    "T8": "t08_header_and_schema_drift", "T9": "t09_delimiters_and_quoting", "T10": "t10_encoding_and_line_endings",
    "T11": "t11_window_boundaries", "T12": "t12_precision_and_rounding", "T13": "t13_referential_integrity",
    "T14": "t14_prose_scope_rules", "T15": "t15_valid_outliers", "T16": "t16_decoy_authority",
}
DECOY_TEST = {d: f"dc{i + 1:02d}_" + name for i, (d, name) in enumerate(zip(DECOYS, [
    "december_master", "scada_gapfill", "fjord_resend", "cirrus_usage_crosswalk", "legacy_crosswalk",
    "restated_rate_history", "rate_crosswalk_2026", "vendor_manifest", "draft_manual", "tariff_2026",
    "east_pdf_report", "ingest_debug_log", "dw_snapshot", "fjord_profile_2026", "portal_export"]))}


class Traps:
    def __init__(self, X):
        self.X = X
        self.entries = []

    def semantic(self, fname):
        return [t for t in self.X.traps if t["file"] == fname]

    def plan(self, fname, nrows, sem_rows, families, r):
        """sem_rows: list of (row_index0, family, rule, note).  Returns {row_index0: family} for representation traps."""
        decoy = fname in DECOYS
        bands = max(1, -(-nrows // 500))
        target = 20 if not decoy else max(28, bands + 4)
        if not decoy and bands > 20:
            raise ValueError(f"{fname}: {nrows} rows exceed the 20-band budget")
        sem_rows = list(sem_rows)
        covered = {i // 500 for i, *_ in sem_rows}
        taken = {i for i, *_ in sem_rows}
        rep = {}
        fam_i = [0]

        def nextfam():
            f = families[fam_i[0] % len(families)]
            fam_i[0] += 1
            return f
        for band in range(bands):
            if band in covered:
                continue
            lo, hi = band * 500, min(nrows, band * 500 + 500) - 1
            for _ in range(20):
                i = r.randint(lo, hi)
                if i not in taken:
                    break
            taken.add(i)
            rep[i] = nextfam()
        if decoy:
            have = set(rep.values())
            for fam in families:
                if fam in have:
                    continue
                for _ in range(50):
                    i = r.randint(0, nrows - 1)
                    if i not in taken:
                        taken.add(i)
                        rep[i] = fam
                        break
        guard = 0
        while len(sem_rows) + len(rep) < target and guard < 10000:
            guard += 1
            i = r.randint(0, nrows - 1)
            if i in taken:
                continue
            taken.add(i)
            rep[i] = nextfam()
        for i, fam, rule, note in sem_rows:
            self.entries.append({"file": fname, "row": i + 1, "family": fam, "rule": rule, "kind": "semantic",
                                 "decoy": decoy, "direction": ("pull" if decoy else None), "note": note,
                                 "test": DECOY_TEST.get(fname, FAMILY_TEST[fam])})
        for i, fam in sorted(rep.items()):
            self.entries.append({"file": fname, "row": i + 1, "family": fam, "rule": "R-FORMAT-" + fam, "kind": "representation",
                                 "decoy": decoy, "direction": ("push" if decoy else None), "note": "",
                                 "test": DECOY_TEST.get(fname, FAMILY_TEST[fam])})
        return rep

    def match(self, fname, rows, keyf):
        """Map the semantic traps registered for fname to row indexes using keyf(row) -> key or (key, alt)."""
        wanted = {}
        for t in self.semantic(fname):
            wanted.setdefault(_hkey(t["key"]), []).append(t)
        out = []
        used = set()
        for i, row in enumerate(rows):
            for k in keyf(row):
                hk = _hkey(k)
                if hk in wanted and wanted[hk]:
                    t = wanted[hk].pop()
                    if i in used:
                        continue
                    used.add(i)
                    out.append((i, t["family"], t["rule"], t["note"]))
                    break
        return out


def _hkey(k):
    return repr(k)


def fmt_dec(v, places=None):
    if v is None:
        return ""
    v = Decimal(v)
    if places is not None:
        return f"{v:.{places}f}"
    s = format(v.normalize(), "f") if v != v.to_integral() else format(v.quantize(Decimal(1)), "f")
    return s


def fmt_reg(v, res):
    return f"{Decimal(v):.{res}f}"


def thousands(s):
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "." in s:
        a, b = s.split(".")
    else:
        a, b = s, None
    out = ""
    while len(a) > 3:
        out = "," + a[-3:] + out
        a = a[:-3]
    out = a + out
    return ("-" if neg else "") + out + ("." + b if b is not None else "")


def comma_decimal(s):
    return s.replace(".", ",")


def local_str(ts, fmt="%Y-%m-%d %H:%M:%S"):
    return utc_to_local(ts)[0].strftime(fmt)


def disp_id(canon, kind):
    return id_variant(canon, kind)


def rep_id(r, canon):
    return id_variant(canon, r.choice(id_variant_kinds(canon)))


def rep_id_ascii(r, canon):
    return id_variant(canon, r.choice([k for k in id_variant_kinds(canon) if k in ("lower", "space", "unpadded")]))


# ---------------------------------------------------------------- read files
def keys_read(row):
    return [(row["meter"], row["b"]), row["meter"]]


def _latest_on(rows, d, default, key="from"):
    best = None
    for x in rows:
        if x[key] <= d and (best is None or x[key] >= best[key]):
            best = x
    return best if best is not None else default


def aurora_fw_on(X, m, d):
    x = _latest_on([x for x in X.aur_fw if x["meter"] == m], d, None)
    return x["fw"] if x else "AU-3.1"


def write_aurora(X, TR, out, k, r):
    fn = read_file_name("A", k)
    rows = X.reads[fn]
    sem = TR.match(fn, rows, keys_read)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T8", "T9", "T10", "T1", "T3", "T9", "T4"], r)
    drift_at = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    cols1 = ["meter_id", "read_local", "register_import", "register_export", "quality", "seq", "comment"]
    cols2 = ["seq", "meter_id", "quality", "read_local", "register_export", "register_import", "comment"]
    out_lines = [("\ufeff" + ",".join(cols1)).encode("utf-8") + b"\n"]
    cols = cols1
    comments = ["", "", "", "route 4", "gate locked", "dog on premises", "read via drive-by", ""]
    for i, row in enumerate(rows):
        m = row["meter"]
        fam = rep.get(i)
        if i == drift_at:
            out_lines.append(b"#segment 2: column order changed by HES upgrade\n")
            out_lines.append((",".join(cols2)).encode() + b"\n")
            cols = cols2
        canon = m.split(":")[-1]
        info = X.meters.get(m)
        res = info["res"] if info else 3
        unit_wh = info is not None and aurora_fw_on(X, m, utc_to_local(row["t"])[0].date()).startswith("AU-2")

        def val(v):
            if v is None:
                return ""
            if unit_wh:
                return str(int(Decimal(v) * 1000))
            return fmt_reg(v, res)
        imp = "-1" if row.get("sentinel") else val(row["imp"])
        exp = val(row["exp"])
        ts = local_str(row["t"])
        mid = canon
        comment = r.choice(comments)
        line_end = b"\n"
        enc = "utf-8"
        if fam == "T1":
            mid = rep_id(r, canon)
        elif fam == "T3":
            ts = r.choice([local_str(row["t"], "%Y-%m-%dT%H:%M:%S"), local_str(row["t"], "%m/%d/%Y %H:%M:%S")])
        elif fam == "T4" and imp not in ("", "-1"):
            imp = thousands(imp)
        elif fam == "T9":
            comment = r.choice(["meter behind fence, see note\nsecond line", "access via side gate, key at office",
                                'customer says "estimate"'])
        elif fam == "T10":
            if r.chance(0.5):
                comment = "acc\xe8s refus\xe9 par le client"
                enc = "cp1252"
            else:
                line_end = b"\r\n"
        vals = {"meter_id": mid, "read_local": ts, "register_import": imp, "register_export": exp,
                "quality": "M" if row.get("sentinel") else "A", "seq": str(row["seq"]), "comment": comment}
        line = csv_line([vals[c] for c in cols])
        out_lines.append(line.encode(enc) + line_end)
    (out / fn).write_bytes(b"".join(out_lines))


def bor_channels_on(X, m, d):
    x = _latest_on([x for x in X.bor_ch if x["meter"] == m], d, None)
    return (x["imp"], x["exp"]) if x else (1, 2)


def write_borealis(X, TR, out, k, r):
    fn = read_file_name("B", k)
    rows = X.reads[fn]
    sem = TR.match(fn, rows, keys_read)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T2", "T3", "T8", "T1", "T2", "T3", "T10"], r)
    drift_at = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<ReadBatch system="Borealis" batch="BOR-2025-11-P{k + 1}" schema="1">']
    in_seg2 = False
    for i, row in enumerate(rows):
        m = row["meter"]
        canon = m.split(":")[-1]
        info = X.meters.get(m)
        fam = rep.get(i)
        if i == drift_at:
            lines.append('<Segment schema="2">')
            in_seg2 = True
        d = utc_to_local(row["t"])[0].date()
        ich, ech = bor_channels_on(X, m, d) if info else (1, 2)
        res = info["res"] if info else 3
        mid = rep_id(r, canon) if fam == "T1" else canon
        ts = iso_utc(row["t"])
        if fam == "T3":
            ts = iso_local_offset(row["t"])
        chs = []
        for ch, v in ((ich, row["imp"]), (ech, row["exp"])):
            if v is None:
                continue
            unit = "kWh"
            txt = fmt_reg(v, res) if info else fmt_dec(v, 3)
            if fam == "T2" or (ch == ech and r.chance(0.02)):
                unit = "Wh"
                txt = fmt_dec(Decimal(v) * 1000, 0) if res <= 3 else fmt_dec(Decimal(v) * 1000)
            if row.get("sentinel") and ch == ich:
                chs.append(f'<Ch n="{ch}" unit="{unit}" q="MISSING"/>')
            else:
                chs.append(f'<Ch n="{ch}" unit="{unit}">{txt}</Ch>')
        if r.chance(0.01):
            chs.append(f'<Ch n="9" unit="varh">{r.randint(0, 99999)}</Ch>')
        if in_seg2:
            lines.append(f'<Rd m="{xml_esc(mid)}" t="{ts}" sq="{row["seq"]}">' + "".join(chs) + "</Rd>")
        else:
            lines.append(f'<Read meter="{xml_esc(mid)}" ts="{ts}" seq="{row["seq"]}">' + "".join(chs) + "</Read>")
    if in_seg2:
        lines.append("</Segment>")
    lines.append("</ReadBatch>")
    text = "\n".join(lines) + "\n"
    if any(f == "T10" for f in rep.values()):
        text = text.replace("\n", "\r\n", 40)
    (out / fn).write_text(text, encoding="utf-8", newline="")


def cirrus_fw_on(X, eui, d):
    x = _latest_on([x for x in X.cir_fw if x["eui"] == eui], d, None)
    return x["fw"] if x else "CX-3.9.2"


def write_cirrus(X, TR, out, k, r):
    fn = read_file_name("C", k)
    rows = X.reads[fn]
    sem = TR.match(fn, rows, keys_read)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T4", "T8", "T9", "T10", "T3", "T4", "T1"], r)
    drift_at = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    out_lines = []
    schema2 = False
    for i, row in enumerate(rows):
        m = row["meter"]
        fam = rep.get(i)
        if i == drift_at:
            out_lines.append('{"_schema": 2}\n')
            schema2 = True
        if m in X.eui:
            eui = X.eui[m]
        else:
            eui = X.uniq(lambda: "".join(r.choice("0123456789ABCDEF") for _ in range(16)))
        d = utc_to_local(row["t"])[0].date()
        fw = cirrus_fw_on(X, eui, d)
        info = X.meters.get(m)
        res = info["res"] if info else 3

        def val(v):
            if v is None:
                return "null"
            s_ = fmt_reg(v, res)
            if fw.startswith("CX-4.1"):
                return json.dumps(comma_decimal(s_))
            if fam == "T4":
                return s_
            return json.dumps(s_)
        imp = val(row["imp"])
        exp = val(row["exp"])
        if row.get("sentinel"):
            imp = r.choice(["null", '"ERR"'])
        dev = eui
        if fam == "T1":
            dev = r.choice([eui.lower(), ":".join(eui[j:j + 2] for j in range(0, 16, 2))])
        tsv = json.dumps(str(row["t"])) if fam == "T3" else str(row["t"])
        keys = ("device", "t", "import", "export", "sequence") if schema2 else ("dev", "ts", "imp", "exp", "seq")
        line = "{" + ",".join([f'"{keys[0]}":{json.dumps(dev)}', f'"{keys[1]}":{tsv}', f'"{keys[2]}":{imp}',
                               f'"{keys[3]}":{exp}', f'"{keys[4]}":{row["seq"]}']) + "}"
        end = "\r\n" if fam == "T10" else "\n"
        if fam == "T9":
            out_lines.append("\n")
            line = line + "   "
        out_lines.append(line + end)
    (out / fn).write_text("".join(out_lines), encoding="utf-8", newline="")


class _JsonNum(str):
    pass


def _json_default(z):
    return str(z)


def write_delta(X, TR, out, k, r):
    fn = read_file_name("D", k)
    rows = X.reads[fn]
    sem = TR.match(fn, rows, keys_read)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T12", "T1", "T3"], r)
    cols = {"spid": [], "read_serial": [], "import_raw": [], "export_raw": [], "est_flag": [], "load_id": []}
    for i, row in enumerate(rows):
        m = row["meter"]
        fam = rep.get(i)
        info = X.meters.get(m)
        spid = X.spid_of.get(m) if info else X.uniq(lambda: "SP" + str(r.randint(10 ** 8, 10 ** 9 - 1)))
        if fam == "T1":
            spid = r.choice([spid.lower(), " " + spid + " ", spid[:2] + "-" + spid[2:]])
        res = info["res"] if info else 3
        scale = Decimal(10) ** res
        imp = -1 if row.get("sentinel") else int(Decimal(row["imp"]) * scale)
        exp = None if row["exp"] is None else int(Decimal(row["exp"]) * scale)
        serial = excel_serial_local(row["t"])
        if fam == "T12":
            serial = serial + 0.4 / 86400
        cols["spid"].append(spid)
        cols["read_serial"].append(serial)
        cols["import_raw"].append(imp)
        cols["export_raw"].append(exp)
        cols["est_flag"].append(int(row.get("est", 0)))
        cols["load_id"].append(row["seq"])
    write_parquet(out / fn, cols, {"spid": "str", "read_serial": "float", "import_raw": "int", "export_raw": "int",
                                   "est_flag": "int", "load_id": "int"})


def julian(d):
    return f"{d.year}{d.timetuple().tm_yday:03d}"


def write_cis(X, TR, out, k, r):
    fn = read_file_name("E", k)
    rows = X.reads[fn]
    sem = TR.match(fn, rows, keys_read)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T8", "T3", "T4", "T10", "T8"], r)
    drift = sorted(i for i, f in rep.items() if f == "T8")
    lines = [f"H{'CISLEGACY':<10}{'2025-11':<8}{k + 1:02d}{len(rows):08d}"]
    layout = 1
    for i, row in enumerate(rows):
        m = row["meter"]
        fam = rep.get(i)
        if i in drift:
            layout = 2 if layout == 1 else 1
            lines.append(f"L{layout}")
        info = X.meters.get(m)
        lid = X.legacy_of.get(m) if info else X.uniq(lambda: "L-" + str(r.randint(100000, 999999)))
        dial = X.dial.get(lid, 1)
        dt = utc_to_local(row["t"])[0]
        dstr = julian(dt.date())
        tstr = dt.strftime("%H%M")
        if fam == "T3" and tstr != "0000":
            fam = "T1"
        if fam == "T3":
            dstr = julian(dt.date() - timedelta(days=1))
            tstr = "2400"
        if fam == "T1":
            lid = lid.lower() if r.chance(0.5) else lid.replace("-", "")
        def digits(v, width):
            if v is None:
                return " " * width
            val = Decimal(v) / dial
            n = int(val * 1000)
            return f"{n:0{width}d}"
        imp = "9" * 10 if row.get("sentinel") else digits(row["imp"], 10)
        exp = digits(row["exp"], 10)
        seq = f"{row['seq']:010d}"
        if fam == "T4" and not row.get("sentinel"):
            imp = imp.replace("0", " ", 1) if imp.startswith("0") else imp
        if layout == 1:
            rec = f"D{lid:<9}{dstr}{tstr}{imp}{exp}{seq}"
        else:
            imp2 = ("0" + imp) if imp.strip() != "9" * 10 else "9" * 11
            exp2 = (" " + exp) if exp.strip() == "" else ("0" + exp)
            rec = f"D{dstr}{tstr}{seq}{lid:<9}{imp2}{exp2}"
        lines.append(rec + ("\r" if fam == "T10" else ""))
    lines.append(f"T{len(rows):08d}")
    text = "\n".join(lines) + "\n"
    (out / fn).write_text(text, encoding="ascii", newline="")


def fjord_applied_on(X, m, d):
    rows = [dict(x, pri=0) for x in X.fj_flag if x["meter"] == m] + \
           [dict(x, pri=1) for x in X.fj_flag_2026 if x["meter"] == m and x["from"] <= NOV30]
    best = None
    for x in rows:
        if x["from"] <= d and (best is None or (x["from"], x["pri"]) >= (best["from"], best["pri"])):
            best = x
    return best["applied"] if best else False


def mult_for_render(X, m, t):
    """Multiplier in force at instant t (registry rows, CT orders, CT verification corrections)."""
    ev = []
    for rows in X.registry.values():
        for row in rows:
            if row["meter"] == m:
                ev.append((local_to_utc(row["from"]), 0, row["mult"]))
    for c in X.ct_orders:
        if c["meter"] == m:
            ev.append((c["t"], 2, c["new"]))
    for v in X.ct_verif:
        if v["meter"] == m and v["result"] == "FAIL" and v["action"] == "CORRECT_RATIO":
            ev.append((local_to_utc(v["on"]), 1, v["measured"]))
    cur = 1
    for tt, _p, val in sorted(ev):
        if tt <= t:
            cur = val
    return cur


def write_fjord(X, TR, out, k, r, resend=False):
    fn = RESEND_FILE if resend else read_file_name("F", k)
    rows = X.resend_rows if resend else X.reads[fn]
    sem = TR.match(fn, rows, lambda row: [(row["meter"], row["b"]), row["meter"]])
    fams = ["T1", "T8", "T9", "T10", "T1", "T9"] if not resend else ["T8", "T10", "T1", "T9"]
    rep = TR.plan(fn, len(rows), sem, fams, r)
    drift_at = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    head1 = ["meter", "ts_ms", "import_kwh", "export_kwh", "flags", "seq"]
    head2 = ["SEQ", "METER_ID", "EPOCH_MS", "IMP", "EXP", "FLG"]
    lines = []
    if resend:
        lines.append("#RESEND of FJD-2025-11-P4 generated 2025-12-02T09:14:00Z")
        lines.append("#values in this copy were re-derived by the vendor after the original send")
    lines.append("\t".join(head1))
    cols = head1
    for i, row in enumerate(rows):
        fam = rep.get(i)
        if i == drift_at:
            lines.append("#header change")
            lines.append("\t".join(head2))
            cols = head2
        if row.get("rev"):
            lines.append("\t".join(["REV", row["meter"], str(row["seq"]), BOUNDARY_DATES[row["b"]].isoformat()]))
            continue
        m = row["meter"]
        canon = m.split(":")[-1]
        info = X.meters.get(m)
        res = info["res"] if info else 3
        d = utc_to_local(row["t"])[0].date()
        applied = info is not None and fjord_applied_on(X, m, d)
        tc = row["t"]
        if info is not None:
            off = info["clock"]
            st = info.get("sync", {}).get("t")
            tc = row["t"] - off if (st is None or row["t"] - off < st) else row["t"]
        mult = mult_for_render(X, m, tc) if applied else 1

        def val(v):
            if v is None:
                return ""
            return fmt_dec(Decimal(v) * mult, res) if mult > 1 else fmt_reg(v, res)
        imp = val(row["imp"])
        exp = val(row["exp"])
        if row.get("sentinel"):
            imp = "9999999.999"
        flags = "A"
        mid = rep_id(r, canon) if fam == "T1" else canon
        vals = {"meter": mid, "ts_ms": str(row["t"] * 1000 + r.randint(0, 999)), "import_kwh": imp, "export_kwh": exp,
                "flags": flags, "seq": str(row["seq"])}
        alias = dict(zip(head2, ["seq", "meter", "ts_ms", "import_kwh", "export_kwh", "flags"]))
        parts = [vals[alias[c]] if cols is head2 else vals[c] for c in cols]
        line = "\t".join(parts)
        if fam == "T9":
            line = line + "\t" if r.chance(0.5) else "\t".join(parts[:-1] + [parts[-1] + "\t"])
        if fam == "T10":
            line = line + "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


# ---------------------------------------------------------------------------
# part 4b - registers, profiles, logs, sqlite and spreadsheet writers
# ---------------------------------------------------------------------------
def spread_layout(rows, sem_flags, r):
    """Reorder rows so flagged rows sit one per 500-row band (in band order)."""
    sem = [x for x, f in zip(rows, sem_flags) if f]
    rest = [x for x, f in zip(rows, sem_flags) if not f]
    n = len(rows)
    bands = max(1, -(-n // 500))
    slots = []
    for i in range(len(sem)):
        band = (i * bands) // max(1, len(sem))
        lo = band * 500
        hi = min(n, lo + 500) - 1
        slots.append(r.randint(lo, hi))
    slots = sorted(set(slots))
    while len(slots) < len(sem):
        c = r.randint(0, n - 1)
        if c not in slots:
            slots.append(c)
            slots.sort()
    out = [None] * n
    for s, x in zip(slots, sem):
        out[s] = x
    it = iter(rest)
    for i in range(n):
        if out[i] is None:
            out[i] = next(it)
    return out


def bidx_of(d):
    if MONTH_START <= d <= DEC1:
        return (d - MONTH_START).days
    return None


def xprec(v, places):
    """A longer decimal string that rounds half-even (and only half-even) back to v."""
    v = Decimal(v).quantize(Decimal(1).scaleb(-places))
    ulp = Decimal(1).scaleb(-places)
    last = int(str(v.quantize(ulp)).replace(".", "")[-1])
    if last % 2 == 0:
        w = v + ulp / 2
    else:
        w = v - ulp * Decimal("0.4")
    return format(w.normalize() if w != w.to_integral() else w, "f")


def date_variant(d, r):
    return r.choice([d.strftime("%m/%d/%Y"), d.strftime("%Y%m%d"), d.strftime("%d-%b-%Y")])


def _reorder_sem(TR, fname, rows, keyf, r):
    sem_keys = {_hkey(t["key"]) for t in TR.semantic(fname)}
    flags = [any(_hkey(k) in sem_keys for k in keyf(x)) for x in rows]
    return spread_layout(rows, flags, r)


def _csv_write(path, header, rows_fields, rep, r, crlf_rows=(), enc_rows=(), extra_header=None):
    out = []
    if extra_header:
        out.extend(x.encode("utf-8") + b"\n" for x in extra_header)
    out.append(csv_line(header).encode("utf-8") + b"\n")
    for i, fields in enumerate(rows_fields):
        line = csv_line(fields)
        enc = "cp1252" if i in enc_rows else "utf-8"
        end = b"\r\n" if i in crlf_rows else b"\n"
        out.append(line.encode(enc) + end)
    Path(path).write_bytes(b"".join(out))


def write_opening(X, TR, out, r):
    fn = "mdm_october_close_reads.csv"
    rows = sorted(X.opening, key=lambda o: o["meter"])
    rows = _reorder_sem(TR, fn, rows, lambda o: [(o["meter"], 0), o["meter"]], r)
    sem = TR.match(fn, rows, lambda o: [(o["meter"], 0), o["meter"]])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T12", "T10", "T1", "T3"], r)
    fields = []
    crlf = set()
    for i, o in enumerate(rows):
        m = o["meter"]
        res = X.meters[m]["res"]
        fam = rep.get(i)
        mid = rep_id(r, m) if fam == "T1" else m
        ts = local_str(o["t"], "%Y-%m-%d %H:%M")
        if fam == "T3":
            ts = local_str(o["t"], "%m/%d/%Y %H:%M")
        imp = fmt_reg(o["imp"], res)
        if fam == "T4":
            imp = thousands(imp)
        if fam == "T12":
            imp = xprec(o["imp"], 3)
        if fam == "T10":
            crlf.add(i)
        exp = "" if o["exp"] is None else fmt_reg(o["exp"], res)
        fields.append([mid, ts, imp, exp, o["status"]])
    _csv_write(out / fn, ["meter_id", "boundary_local", "register_import_kwh", "register_export_kwh", "status"], fields, rep, r, crlf_rows=crlf,
               extra_header=["# MDM October 2025 close: validated boundary reads at each meter's scheduled November 1 read time"])


def write_master(X, TR, out, r):
    fn = "cis_account_master.csv"
    rows = [X.accounts[a] for a in sorted(X.accounts)]
    extras = sorted(X.master_extra, key=lambda x: x["id"])[:max(0, 9600 - len(rows))]
    rows = sorted(rows + extras, key=lambda x: x["id"])
    rows = _reorder_sem(TR, fn, rows, lambda x: [x["id"]], r)
    sem = TR.match(fn, rows, lambda x: [x["id"]])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T9", "T10", "T1", "T3", "T9"], r)
    fields = []
    enc = set()
    for i, a in enumerate(rows):
        fam = rep.get(i)
        aid = rep_id(r, a["id"]) if fam == "T1" else a["id"]
        name = a["name"]
        fin = a["final"].isoformat() if a["final"] else ""
        if fam == "T3" and a["final"]:
            fin = a["final"].strftime("%m/%d/%Y")
        elif fam == "T3":
            fam = "T9"
        if fam == "T9":
            name = name + ", Trustee" if r.chance(0.5) else name + ' "Jr"'
        if fam == "T10":
            name = name + " Pe\xf1a"
            enc.add(i)
        fields.append([aid, name, a["cls"], a["status"], fin, a.get("code", "")])
    _csv_write(out / fn, ["account_id", "customer_name", "customer_class", "status", "final_date", "rate_code_snapshot"], fields, rep, r,
               enc_rows=enc, extra_header=["# as_of: 2025-11-30", "# source: CIS month-end extract (settlement extract of record)"])


def write_voids(X, TR, out, r):
    fn = "mdm_void_register.csv"
    key = lambda v: [(v["meter"], bidx_of(v["date"]))]
    rows = _reorder_sem(TR, fn, X.voids, key, r)
    sem = TR.match(fn, rows, key)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T10", "T11", "T1", "T3"], r)
    fields = []
    crlf = set()
    for i, v in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, v["meter"]) if fam == "T1" else v["meter"]
        d = v["date"].isoformat()
        if fam == "T3":
            d = v["date"].strftime("%m/%d/%Y")
        if fam == "T10":
            crlf.add(i)
        fields.append([v["id"], v["hes"], mid, d, v["reason"], v["reinstated"]])
    _csv_write(out / fn, ["void_id", "hes", "meter_id", "read_date", "reason", "reinstated"], fields, rep, r, crlf_rows=crlf)


def write_corrections(X, TR, out, r):
    fn = "mdm_read_corrections.csv"
    key = lambda c: [(c["meter"], bidx_of(c["date"]))]
    rows = _reorder_sem(TR, fn, X.corrections, key, r)
    sem = TR.match(fn, rows, key)
    rep = TR.plan(fn, len(rows), sem, ["T12", "T1", "T3", "T4", "T12", "T1"], r)
    fields = []
    for i, c in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, c["meter"]) if fam == "T1" else c["meter"]
        d = c["date"].isoformat() if fam != "T3" else c["date"].strftime("%m/%d/%Y")
        imp = fmt_dec(c["imp"], 3)
        if fam == "T12":
            imp = xprec(c["imp"], 3)
        if fam == "T4":
            imp = thousands(imp)
        exp = "" if c["exp"] is None else fmt_dec(c["exp"], 3)
        fields.append([c["id"], mid, d, imp, exp, str(c["rev"]), c["status"]])
    _csv_write(out / fn, ["correction_id", "meter_id", "read_date", "corrected_import_kwh", "corrected_export_kwh", "revision", "status"],
               fields, rep, r)


def feeder_variant(f, r):
    return r.choice([f.lower(), "F" + str(int(f[1:])), f" {f} ", "FDR-" + f[1:]])


def scada_rows(X, sub):
    feeders = [f for f in FEEDERS if SUBSTATION[f] == sub]
    return [(f, t) for f in feeders for t in X.interval_ends]


def write_north(X, TR, out, r):
    fn = SCADA_FILES["north"]
    rows = scada_rows(X, "north")
    sem = TR.match(fn, rows, lambda x: [x])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T12", "T1", "T4"], r)
    fields = []
    for i, (f, t) in enumerate(rows):
        rec = X.scada[(f, t)]
        fam = rep.get(i)
        dt, abbr, _o = utc_to_local(t)
        fid = feeder_variant(f, r) if fam == "T1" else f
        ts = dt.strftime("%Y-%m-%d %H:%M")
        if fam == "T3":
            ts = dt.strftime("%m/%d/%Y %H:%M")
        if rec["q"] != "GOOD":
            kw, q = "-9999", "BAD"
        else:
            kw, q = fmt_dec(rec["kw"], 2), "GOOD"
            if fam == "T4":
                kw = thousands(kw) if rec["kw"] >= 1000 else kw + "0"
            if fam == "T12":
                kw = xprec(rec["kw"], 2)
        fields.append([fid, ts, abbr, kw, q])
    _csv_write(out / fn, ["feeder", "interval_end_local", "tz", "kw_avg", "quality"], fields, rep, r,
               extra_header=["# North substation historian export, 15-minute average demand per feeder (interval-ending)"])


def write_nem(X, TR, out, r):
    fn = "netmetering_enrollments.csv"
    rows = _reorder_sem(TR, fn, X.nem, lambda n: [n["app"]], r)
    sem = TR.match(fn, rows, lambda n: [n["app"]])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T9", "T1", "T3"], r)
    fields = []
    for i, n in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, n["meter"]) if fam == "T1" else n["meter"]
        fr = n["from"].isoformat() if fam != "T3" else n["from"].strftime("%m/%d/%Y")
        to = n["to"].isoformat() if n["to"] else ""
        fields.append([n["app"], mid, n["acct"] or "", n["status"], fr, to])
        if fam == "T9":
            fields[-1] = fields[-1] + [""]
    _csv_write(out / fn, ["application_id", "meter_id", "account_id", "status", "effective_from", "effective_to"], fields, rep, r)


def write_vee(X, TR, out, r):
    fn = "mdm_vee_estimates.tsv"
    rows = X.vee
    rep = TR.plan(fn, len(rows), [], ["T12", "T1", "T3", "T9", "T12", "T10"], r)
    lines = ["estimate_id\tmeter_id\tread_date\test_import_kwh\test_export_kwh\tversion\tcreated_on"]
    for i, v in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, v["meter"]) if fam == "T1" else v["meter"]
        d = v["date"].isoformat() if fam != "T3" else v["date"].strftime("%Y%m%d")
        imp = fmt_dec(v["imp"], 3) if fam != "T12" else xprec(v["imp"], 3)
        exp = "" if v["exp"] is None else fmt_dec(v["exp"], 3)
        line = "\t".join([v["id"], mid, d, imp, exp, str(v["version"]), v["created"].isoformat()])
        if fam == "T9":
            line += "\t"
        if fam == "T10":
            line += "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_orders(X, TR, out, r):
    fn = "field_service_orders.jsonl"
    rows = sorted(X.orders, key=lambda o: (o.get("old") or o.get("meter"), o["t"]))
    key = lambda o: [o["id"]]
    rows = _reorder_sem(TR, fn, rows, key, r)
    sem = TR.match(fn, rows, key)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T8", "T10", "T1"], r)
    lines = []
    for i, o in enumerate(rows):
        fam = rep.get(i)
        obj = {"order_id": o["id"], "type": o["type"], "status": o["status"], "completed_at": iso_local_offset(o["t"])}
        if fam == "T3":
            obj["completed_at"] = iso_utc(o["t"])
        def mid(x):
            return rep_id(r, x) if fam == "T1" else x
        if o["type"] == "EXCHANGE":
            obj.update({"old_meter": mid(o["old"]), "new_meter": o["new"], "old_final_import_kwh": fmt_dec(o["old_imp"], 3),
                        "old_final_export_kwh": fmt_dec(o["old_exp"], 3) if o["old_exp"] is not None else None,
                        "new_initial_import_kwh": fmt_dec(o["new_imp"], 3),
                        "new_initial_export_kwh": fmt_dec(o["new_exp"], 3) if o["new_exp"] is not None else None})
            if fam == "T4":
                obj["old_final_import_kwh"] = thousands(obj["old_final_import_kwh"])
        elif o["type"] == "CT_CHANGE":
            obj.update({"meter": mid(o["meter"]), "old_ratio": f"{o['old_ratio']}:5", "new_ratio": f"{o['new_ratio']}:5",
                        "register_at_change_kwh": fmt_dec(o["read"], 3)})
        else:
            obj.update({"meter": mid(o["meter"])})
        if fam == "T8":
            obj = {("ts" if k_ == "completed_at" else k_): v_ for k_, v_ in obj.items()}
        line = json.dumps(obj, separators=(",", ":"))
        lines.append(line + ("\r\n" if fam == "T10" else "\n"))
    (out / fn).write_text("".join(lines), encoding="utf-8", newline="")


def write_east(X, TR, out, r):
    fn = SCADA_FILES["east"]
    rows = scada_rows(X, "east")
    sem = TR.match(fn, rows, lambda x: [x])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T12", "T4", "T1"], r)
    items = []
    for i, (f, t) in enumerate(rows):
        rec = X.scada[(f, t)]
        fam = rep.get(i)
        fid = feeder_variant(f, r) if fam == "T1" else f
        kwh = fmt_dec(rec["kwh"], 3) if rec["q"] == "GOOD" else None
        if fam == "T12" and kwh:
            kwh = xprec(rec["kwh"], 3)
        if fam == "T4" and kwh:
            kwh = comma_decimal(kwh)
        q = "G" if rec["q"] == "GOOD" else "B"
        tval = t if fam != "T3" else iso_utc(t)
        if fam == "T8":
            items.append({"fdr": fid, "t": tval, "value": kwh, "quality": q})
        else:
            items.append({"feeder": fid, "end_utc": tval, "kwh": kwh, "q": q})
    doc = {"substation": "east", "unit": "kWh per interval", "interval_minutes": 15, "timestamps": "interval-ending, UTC epoch seconds",
           "intervals": items}
    (out / fn).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def write_south(X, TR, out, r):
    fn = SCADA_FILES["south"]
    rows = scada_rows(X, "south")
    sem = TR.match(fn, rows, lambda x: [x])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T10", "T12", "T4"], r)
    switch = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines = ["# south substation historian dump", "# format v1: <interval_end local ISO-8601 with offset> HIST <feeder> MWH=<value> Q=<quality>"]
    v2 = False
    for i, (f, t) in enumerate(rows):
        rec = X.scada[(f, t)]
        fam = rep.get(i)
        if i == switch:
            lines.append("FORMAT v2 HIST|<feeder>|<interval_end UTC yyyy-mm-dd hh:mm:ssZ>|<kWh>|<quality>")
            v2 = True
        fid = feeder_variant(f, r) if fam == "T1" else f
        good = rec["q"] == "GOOD"
        if v2:
            val = fmt_dec(rec["mwh"] * 1000, 3) if good else "NaN"
            if fam == "T4" and good:
                val = comma_decimal(val)
            line = f"HIST|{fid}|{datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z|{val}|{'GOOD' if good else 'BAD'}"
        else:
            val = fmt_dec(rec["mwh"], 6) if good else "NaN"
            if fam == "T12" and good:
                val = xprec(rec["mwh"], 6)
            ts = iso_local_offset(t)
            if fam == "T3":
                ts = iso_utc(t)
            line = f"{ts} HIST {fid} MWH={val} Q={'GOOD' if good else 'BAD'}"
        if fam == "T10":
            line += "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_merges(X, TR, out, r):
    fn = "account_merges_2025.json"
    rows = _reorder_sem(TR, fn, X.merges, lambda x: [x["pred"]], r)
    sem = TR.match(fn, rows, lambda x: [x["pred"]])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1", "T3"], r)
    items = []
    for i, x in enumerate(rows):
        fam = rep.get(i)
        pred = rep_id(r, x["pred"]) if fam == "T1" else x["pred"]
        eff = x["eff"].isoformat() if fam != "T3" else x["eff"].strftime("%m/%d/%Y")
        if fam == "T8":
            items.append({"id": x["id"], "from_account": pred, "to_account": x["succ"], "effective": eff, "state": x["status"]})
        else:
            items.append({"merge_id": x["id"], "predecessor": pred, "successor": x["succ"], "effective_date": eff, "status": x["status"]})
    (out / fn).write_text(json.dumps({"generated": "2025-12-02", "merges": items}, indent=1) + "\n", encoding="utf-8")


def write_inventory(X, TR, out, r):
    fn = "unmetered_supply_inventory.json"
    rows = [X.fixtures[f] for f in sorted(X.fixtures)]
    rows = _reorder_sem(TR, fn, rows, lambda x: [x["id"]], r)
    sem = TR.match(fn, rows, lambda x: [x["id"]])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T4", "T1"], r)
    items = []
    for i, x in enumerate(rows):
        fam = rep.get(i)
        fid = x["id"].lower() if fam == "T1" else x["id"]
        inst = x["install"].isoformat() if fam != "T3" else x["install"].strftime("%m/%d/%Y")
        watts = x["watts"] if fam != "T4" else f"{x['watts']} W"
        rec = {"fixture_id": fid, "account_id": x["acct"], "feeder": x["feeder"], "nominal_watts": watts,
               "burn_profile": x["profile"], "installed": inst, "removed": x["removal"].isoformat() if x["removal"] else None}
        if fam == "T8":
            rec = {"fixture": fid, "account": x["acct"], "feeder": x["feeder"], "watts": watts, "profile": x["profile"],
                   "in_service": inst, "out_of_service": rec["removed"]}
        items.append(rec)
    (out / fn).write_text(json.dumps({"fixtures": items}, indent=1) + "\n", encoding="utf-8")


def write_burn(X, TR, out, r):
    fn = "photocell_burn_hours.json"
    rows = sorted(X.burn.items())
    rep = TR.plan(fn, len(rows), [], ["T12", "T1", "T3", "T12", "T4"], r)
    items = []
    for i, ((f, d), h) in enumerate(rows):
        fam = rep.get(i)
        hv = fmt_dec(h, 2)
        if fam == "T12":
            hv = xprec(h, 2)
        if fam == "T4":
            hv = comma_decimal(hv)
        items.append({"feeder": feeder_variant(f, r) if fam == "T1" else f,
                      "date": d.isoformat() if fam != "T3" else d.strftime("%Y%m%d"), "hours": hv})
    (out / fn).write_text(json.dumps({"unit": "hours of darkness per day (dusk-to-dawn)", "rows": items}, indent=1) + "\n", encoding="utf-8")


def _xl_date(d):
    return (d - date(1899, 12, 30)).days


def write_rate_history(X, TR, out, r):
    fn = "account_rate_history.xlsx"
    sheets = []
    key = lambda x: [x["entry"]]
    for sh in ("2024", "2025"):
        rows = [x for x in X.rate_hist if x["sheet"] == sh]
        rows.sort(key=lambda x: x["entry"])
        rows = _reorder_sem(TR, fn, rows, key, r) if sh == "2025" else rows
        sheets.append((sh, rows))
    allrows = sheets[0][1] + sheets[1][1]
    sem = TR.match(fn, allrows, key)
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T3", "T8", "T12", "T1", "T3"], r)
    out_sheets = []
    off = 0
    for sh, rows in sheets:
        hdr = ["entry_id", "account_id", "rate_code", "effective_from", "entered_on"] if sh == "2025" else \
            ["account_id", "entry_id", "effective_from", "rate_code", "entered_on"]
        data = [hdr]
        for j, x in enumerate(rows):
            fam = rep.get(off + j)
            aid = rep_id(r, x["acct"]) if fam == "T1" else x["acct"]
            code = legacy_alias(x["code"]) if x.get("alias") else x["code"]
            eff = _xl_date(x["from"]) if fam != "T3" else x["from"].isoformat()
            entered = x["from"].isoformat()
            vals = {"entry_id": x["entry"], "account_id": aid, "rate_code": code, "effective_from": eff, "entered_on": entered}
            data.append([vals[c] for c in hdr])
        off += len(rows)
        out_sheets.append((sh, data))
    write_xlsx(out / fn, out_sheets)


def write_fixture_audit(X, TR, out, r):
    fn = "unmetered_fixture_audit_2025.xlsx"
    key = lambda x: [(x["fixture"], x["eff"])]
    sheets = []
    for q in ("Q3", "Q4"):
        rows = sorted([a for a in X.audit if a["q"] == q], key=lambda a: (a["date"], a["fixture"]))
        if q == "Q4":
            rows = _reorder_sem(TR, fn, rows, key, r)
        sheets.append((q, rows))
    allrows = sheets[0][1] + sheets[1][1]
    sem = TR.match(fn, allrows, key)
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T3", "T8", "T4", "T1"], r)
    out_sheets = []
    off = 0
    for q, rows in sheets:
        hdr = ["fixture_id", "audit_date", "finding", "audited_watts", "effective_date"]
        if q == "Q4":
            hdr = ["fixture_id", "finding", "effective_date", "audited_watts", "audit_date"]
        data = [hdr]
        for j, a in enumerate(rows):
            fam = rep.get(off + j)
            vals = {"fixture_id": a["fixture"].lower() if fam == "T1" else a["fixture"], "audit_date": _xl_date(a["date"]),
                    "finding": a["status"], "audited_watts": a["watts"] if fam != "T4" else f"{a['watts']} W",
                    "effective_date": _xl_date(a["eff"]) if fam != "T3" else a["eff"].strftime("%m/%d/%Y")}
            data.append([vals[c] for c in hdr])
        off += len(rows)
        out_sheets.append((q, data))
    write_xlsx(out / fn, out_sheets)


def write_vee_review(X, TR, out, r):
    fn = "vee_estimate_review_2025.xlsx"
    est = {v["id"]: v for v in X.vee}
    key = lambda x: [(est[x["est"]]["meter"], bidx_of(est[x["est"]]["date"]))] if x["est"] in est else []
    h1 = [x for x in X.vee_reviews if x["on"] < date(2025, 7, 1)]
    h2 = [x for x in X.vee_reviews if x["on"] >= date(2025, 7, 1)]
    while len(h1) > 5000:
        h2.append(h1.pop())
    while len(h2) > 5000:
        cand = [i for i, x in enumerate(h2) if x["on"] < MONTH_START and x["status"] == "REJECTED"]
        h2.pop(cand[-1])
    while len(h1) < 5000:
        h1.append({"est": r.choice([e for e in est if est[e]["date"] < MONTH_START]), "status": "REJECTED",
                   "on": date(2025, r.randint(1, 6), r.randint(1, 28))})
    while len(h2) < 5000:
        h2.append({"est": r.choice([e for e in est if est[e]["date"] < MONTH_START]), "status": "REJECTED",
                   "on": date(2025, r.randint(7, 10), r.randint(1, 28))})
    X.vee_reviews = h1 + h2
    h2 = _reorder_sem(TR, fn, h2, key, r)
    allrows = h1 + h2
    sem = TR.match(fn, allrows, key)
    rep = TR.plan(fn, len(allrows), sem, ["T3", "T1", "T8", "T3"], r)
    out_sheets = []
    for idx, (nm, rows) in enumerate((("H1", h1), ("H2", h2))):
        hdr = ["estimate_id", "review_status", "reviewed_on"] if nm == "H1" else ["reviewed_on", "estimate_id", "review_status"]
        data = [hdr]
        for j, x in enumerate(rows):
            fam = rep.get(j + (0 if nm == "H1" else len(h1)))
            vals = {"estimate_id": x["est"].lower() if fam == "T1" else x["est"], "review_status": x["status"],
                    "reviewed_on": _xl_date(x["on"]) if fam != "T3" else x["on"].isoformat()}
            data.append([vals[c] for c in hdr])
        out_sheets.append((nm, data))
    write_xlsx(out / fn, out_sheets)


def write_two_sheet(X, TR, out, r, fn, rows_by_sheet, hdrs, render, key):
    sheets = []
    for nm, rows in rows_by_sheet:
        sheets.append((nm, rows))
    allrows = [x for _n, rows in sheets for x in rows]
    sem = TR.match(fn, allrows, key)
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T3", "T8", "T1", "T3"], r)
    out_sheets = []
    off = 0
    for (nm, rows), hdr in zip(sheets, hdrs):
        data = [hdr]
        for j, x in enumerate(rows):
            vals = render(x, rep.get(off + j))
            data.append([vals[c] for c in hdr])
        off += len(rows)
        out_sheets.append((nm, data))
    write_xlsx(out / fn, out_sheets)


def write_ct_verif(X, TR, out, r):
    fn = "ct_ratio_verification_2025.xlsx"
    key = lambda v: [(v["meter"], v["on"])]
    h1 = [v for v in X.ct_verif if v["half"] == "H1"]
    h2 = _reorder_sem(TR, fn, [v for v in X.ct_verif if v["half"] == "H2"], key, r)

    def render(v, fam):
        return {"verification_id": v["id"], "meter_id": rep_id(r, v["meter"]) if fam == "T1" else v["meter"],
                "verified_on": _xl_date(v["on"]) if fam != "T3" else v["on"].strftime("%m/%d/%Y"),
                "registry_ratio": f"{v['reg']}:5", "measured_ratio": f"{v['measured']}:5", "result": v["result"], "action": v["action"]}
    hdr = ["verification_id", "meter_id", "verified_on", "registry_ratio", "measured_ratio", "result", "action"]
    write_two_sheet(X, TR, out, r, fn, [("H1", h1), ("H2", h2)], [hdr, hdr[::-1]], render, key)


def write_inspections(X, TR, out, r):
    fn = "export_meter_inspections_2025.xlsx"
    key = lambda v: [(v["meter"], v["on"])]
    h1 = [i for i in X.inspections if i["on"].month <= 6]
    h2 = [i for i in X.inspections if i["on"].month > 6]
    for h in (h1, h2):
        while len(h) > 5000:
            cand = [k for k, i in enumerate(h) if i.get("pad")]
            h.pop(cand[-1])
        while len(h) < 5000:
            h.append({"meter": r.choice(sorted(X.meters)), "on": date(2025, r.randint(1, 6) if h is h1 else r.randint(7, 10),
                                                                       r.randint(1, 28)), "result": "PASS", "pad": True})
    h2 = sorted(h2, key=lambda i: (i["meter"], i["on"]))
    X.inspections = h1 + h2
    h2 = _reorder_sem(TR, fn, h2, key, r)

    def render(v, fam):
        return {"meter_id": rep_id(r, v["meter"]) if fam == "T1" else v["meter"],
                "inspected_on": _xl_date(v["on"]) if fam != "T3" else v["on"].isoformat(), "result": v["result"]}
    hdr = ["meter_id", "inspected_on", "result"]
    write_two_sheet(X, TR, out, r, fn, [("H1", h1), ("H2", h2)], [hdr, ["result", "meter_id", "inspected_on"]], render, key)


def write_burn_exc(X, TR, out, r):
    fn = "lighting_burn_hour_exceptions_2025.xlsx"
    key = lambda e: [(e["fixture"], e["date"])]
    q3 = sorted([e for e in X.burn_exc if e["q"] == "Q3"], key=lambda e: (e["date"], e["fixture"]))
    q4 = _reorder_sem(TR, fn, sorted([e for e in X.burn_exc if e["q"] == "Q4"], key=lambda e: (e["date"], e["fixture"])), key, r)

    def render(e, fam):
        return {"fixture_id": e["fixture"].lower() if fam == "T1" else e["fixture"],
                "date": _xl_date(e["date"]) if fam != "T3" else e["date"].isoformat(), "hours": fmt_dec(e["hours"], 2),
                "reason": e["reason"]}
    hdr = ["fixture_id", "date", "hours", "reason"]
    write_two_sheet(X, TR, out, r, fn, [("Q3", q3), ("Q4", q4)], [hdr, ["date", "fixture_id", "reason", "hours"]], render, key)


def write_batch_log(X, TR, out, r):
    fn = "mdm_batch_control.log"
    events = []
    t = local_to_utc(date(2025, 1, 2), 3, 0, 0)
    for k in range(1, 4800):
        t += r.randint(3000, 7000)
        if t >= local_to_utc(MONTH_START):
            break
        events.append(("hist", t, f"BATCH HIST-{k:05d} hes={r.choice(list(HES_CODE.values()))} status={r.choice(['ACCEPTED'] * 9 + ['REJECTED'])} rows={r.randint(4000, 8000)}"))
    t = local_to_utc(date(2025, 12, 1), 6, 0, 0)
    files = READ_FILES + [RESEND_FILE]
    for fn_ in files:
        t += r.randint(60, 900)
        n = len(X.reads[fn_]) if fn_ != RESEND_FILE else len(X.resend_rows)
        # the log reports what the sending system said it delivered, which need not be what the file holds
        n = n + X.log_drift.get(fn_, 0)
        if fn_ == RESEND_FILE:
            line = f"BATCH FJD-2025-11-P4B file={fn_} status=REJECTED rows={n} reason=DUPLICATE_RESEND"
        elif fn_ in X.batch_partial:
            a, z = X.batch_partial[fn_]
            line = f"BATCH {fn_.split('.')[0].upper()} file={fn_} status=PARTIAL rows={n} rejected_rows={a}-{z} reason=CRC_MISMATCH"
        else:
            line = f"BATCH {fn_.split('.')[0].upper()} file={fn_} status=ACCEPTED rows={n}"
        events.append((fn_, t, line))
    while len(events) < 5200:
        tt = local_to_utc(date(2025, r.randint(1, 10), r.randint(1, 28)), r.randint(0, 23), 0, 0)
        events.append(("hist", tt, f"CHUNK hes={r.choice(list(HES_CODE.values()))} ok={r.randint(100, 900)} lag_ms={r.randint(5, 900)}"))
    events.sort(key=lambda e: e[1])
    sem_files = {t_["key"] for t_ in TR.semantic(fn)}
    rows = events
    sem = [(i, "T6", "R-BATCH", "") for i, e in enumerate(rows) if e[0] in sem_files]
    rep = TR.plan(fn, len(rows), sem, ["T3", "T10", "T4", "T3"], r)
    lines = []
    for i, (_k, tt, msg) in enumerate(rows):
        fam = rep.get(i)
        ts = iso_utc(tt) if fam != "T3" else iso_local_offset(tt)
        line = f"{ts} mdm-ingest[{1000 + i % 7}]: {msg}"
        if fam == "T10":
            line += "\r"
        if fam == "T4" and "rows=" in msg:
            line = line.replace("rows=", "rows= ")
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_collector(X, TR, out, r):
    fn = "collector_events_2025-11.log"
    rows = X.collector_events
    sem = TR.match(fn, rows, lambda e: [e["meter"]] if e["type"] in ("REGISTER_RESET", "CLOCK_SYNC") else [])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T10", "T1"], r)
    lines = []
    for i, e in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, e["meter"]) if fam == "T1" else e["meter"]
        ts = iso_utc(e["t"]) if fam != "T3" else iso_local_offset(e["t"])
        if e["type"] == "REGISTER_RESET":
            res = X.meters[e["meter"]]["res"]
            pre = fmt_reg(e["pre"], res)
            if fam == "T4":
                pre = thousands(pre)
            msg = f"REGISTER_RESET meter={mid} pre_reset_kwh={pre} post_reset_kwh={fmt_reg(e['post'], res)}"
        elif e["type"] == "CLOCK_SYNC":
            msg = f"CLOCK_SYNC meter={mid} correction_s={e['corr']:+d}"
        else:
            msg = f"{e['type']} meter={mid}"
        line = f"{ts} collector[{r.randint(10, 99)}] {msg}"
        if fam == "T10":
            line += "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_alarms(X, TR, out, r):
    fn = "scada_alarm_journal.log"
    rows = []
    for a in X.alarms:
        rows.append(("RAISED", a["raised"], a))
        rows.append(("CLEARED", a["cleared"], a))
    rows.sort(key=lambda x: (x[1], x[0]))
    sem = TR.match(fn, rows, lambda x: [(x[2]["feeder"], x[2]["raised"])] if x[0] == "RAISED" else [])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T10", "T8", "T1"], r)
    lines = []
    for i, (st, tt, a) in enumerate(rows):
        fam = rep.get(i)
        fid = feeder_variant(a["feeder"], r) if fam == "T1" else a["feeder"]
        ts = iso_utc(tt) if fam != "T3" else iso_local_offset(tt)
        if fam == "T8":
            line = f"{ts};ALARM;{fid};{a['type']};{st}"
        else:
            line = f"{ts} ALARM feeder={fid} type={a['type']} state={st}"
        if fam == "T10":
            line += "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_registry(X, TR, out, dist, r):
    fn = f"mdm_registry_{dist}.db"
    rows = sorted(X.registry[dist], key=lambda x: (x["meter"], x["from"]))
    rep = TR.plan(fn, len(rows), [], ["T1", "T3", "T1", "T3"], r)
    data = []
    for i, x in enumerate(rows):
        fam = rep.get(i)
        mid = x["meter"]
        frm = x["from"].isoformat()
        to = x["to"].isoformat() if x["to"] else None
        if fam == "T1":
            mid = r.choice([mid.lower(), " " + mid])
        if fam == "T3":
            frm = x["from"].strftime("%Y%m%d")
        acct = x["account"]
        data.append((mid, acct, x["mult"], x["hes"], frm, to, x["reason"]))
    write_sqlite(out / fn, [("CREATE TABLE meter_attr_history (meter_id TEXT, account_id TEXT, multiplier INTEGER, hes TEXT, "
                              "valid_from TEXT, valid_to TEXT, change_reason TEXT)",
                              "INSERT INTO meter_attr_history VALUES (?,?,?,?,?,?,?)", data)])


def _yaml_str(s):
    return '"' + str(s).replace('"', '\\"') + '"'


def write_aurora_profile(X, TR, out, r):
    fn = "aurora_hes_profile.yaml"
    rows = sorted(X.aur_fw, key=lambda x: (x["meter"], x["from"]))
    sem = TR.match(fn, rows, lambda x: [x["meter"]] if x["from"] >= MONTH_START else [])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    lines = ["# Aurora head-end export profile (applies to aurora_reads_2025-11_p*.csv)",
             "system: aurora", "hes_code: AUR", "timezone: America/Chicago",
             "timestamp_column: read_local",
             "timestamp_formats: ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%m/%d/%Y %H:%M:%S']",
             "timestamp_basis: 'local wall clock as reported by the meter (meter clock offsets apply)'",
             "encoding: 'utf-8 with BOM; free-text comment fields may contain cp1252 bytes, decode such lines as cp1252'",
             "directives: 'lines starting with # are directives or comments; a header line may be repeated with a new column order'",
             "missing_values: ['-1', '']",
             "thousands_separator: ','",
             "thousands_note: 'values carrying a thousands separator are quoted CSV fields'",
             "units:",
             "  default: kWh",
             "  firmware_rules:",
             "    - match: 'AU-2.*'",
             "      unit: Wh",
             "    - match: 'AU-3.*'",
             "      unit: kWh",
             "matching: 'a firmware entry applies from its effective_from local date; match on the local date of the reported timestamp'",
             "firmware_history:"]
    for i, x in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, x["meter"]) if fam == "T1" else x["meter"]
        frm = x["from"].isoformat() if fam != "T3" else x["from"].strftime("%m/%d/%Y")
        if fam == "T8":
            lines.append(f"  - {{meter: {_yaml_str(mid)}, firmware: {_yaml_str(x['fw'])}, since: {_yaml_str(frm)}}}")
        else:
            lines.append(f"  - {{meter_id: {_yaml_str(mid)}, firmware: {_yaml_str(x['fw'])}, effective_from: {_yaml_str(frm)}}}")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_cirrus_profile(X, TR, out, r):
    fn = "cirrus_hes_profile.yaml"
    rows = sorted(X.cir_fw, key=lambda x: (x["eui"], x["from"]))
    inv = {v: k for k, v in X.eui.items()}
    sem = TR.match(fn, rows, lambda x: [inv.get(x["eui"])] if x["from"] >= MONTH_START else [])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    lines = ["# Cirrus mesh head-end profile (applies to cirrus_reads_2025-11_p*.jsonl)",
             "system: cirrus", "hes_code: CIR",
             "device_key: 'dev (schema 1) or device (schema 2); 16 hex digits, case-insensitive, colon separators allowed'",
             "timestamp: 'ts or t, UTC epoch seconds (integer or string)'",
             "values: 'imp/exp (schema 1) or import/export (schema 2), kWh register readings; JSON numbers or strings'",
             "decimal_separator:",
             "  default: '.'",
             "  firmware_rules:",
             "    - match: 'CX-4.1.*'",
             "      separator: ','",
             "missing_values: [null, 'ERR']",
             "schema_directive: 'a line {\"_schema\": N} switches the key names for all following lines'",
             "blank_lines: ignored",
             "device_identity: 'the device-to-meter link is published in cirrus_daily_usage_2025-11.jsonl (one row per device and period)'",
             "matching: 'a firmware entry applies from its effective_from local date; match on the local date of the reported timestamp'",
             "firmware_history:"]
    for i, x in enumerate(rows):
        fam = rep.get(i)
        eui = x["eui"].lower() if fam == "T1" else x["eui"]
        frm = x["from"].isoformat() if fam != "T3" else x["from"].strftime("%m/%d/%Y")
        key = "since" if fam == "T8" else "effective_from"
        lines.append(f"  - {{device: {_yaml_str(eui)}, firmware: {_yaml_str(x['fw'])}, {key}: {_yaml_str(frm)}}}")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_fjord_profile(X, TR, out, r, y2026=False):
    fn = "fjord_hes_profile_2026.yaml" if y2026 else "fjord_hes_profile.yaml"
    src = X.fj_flag_2026 if y2026 else X.fj_flag
    rows = sorted(src, key=lambda x: (x["meter"], x["from"]))
    if y2026:
        pad = []
        k = 0
        while len(rows) + len(pad) < 5200:
            pad.append({"meter": X.new_id("KV", 7, r, 0.5), "applied": False, "from": date(2026, 2, 1 + k % 27)})
            k += 1
        rows = rows + pad
    sem = TR.match(fn, rows, lambda x: [x["meter"]] if x["from"] <= NOV30 else [])
    if y2026:
        for i, x in enumerate(rows):
            if x["from"] > NOV30 and i % 400 == 7:
                sem.append((i, "T16", "R-FJORD-MULT", "2026 entry agrees with the current flag"))
        sem.append((0, "T13", "R-FJORD-MULT", "planned meters not yet in the registry"))
        sem.append((1, "T6", "R-FJORD-MULT", "planned changes are not in force"))
        sem.append((2, "T7", "R-FJORD-MULT", "newer profile looks like it supersedes the current one"))
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    if y2026:
        lines = ["# Fjord head-end profile 2026 - PLANNED firmware 6.0 rollout. Entries take effect on their effective_from date.",
                 "# status: planned; prepared 2025-12-01 for the January 2026 change window",
                 "system: fjord", "hes_code: FJD", "multiplier_applied_entries:"]
    else:
        lines = ["# Fjord head-end export profile (applies to fjord_reads_2025-11_p*.tsv)",
                 "system: fjord", "hes_code: FJD", "timestamp: 'ts_ms or EPOCH_MS, UTC epoch milliseconds; discard the millisecond part'",
                 "delimiter: 'tab; lines starting with # are comments; a header line may be repeated with renamed columns'",
                 "header_aliases: {SEQ: seq, METER_ID: meter, EPOCH_MS: ts_ms, IMP: import_kwh, EXP: export_kwh, FLG: flags}",
                 "trailing_empty_fields: ignored",
                 "missing_values: ['9999999.999', '']",
                 "matching: 'an entry applies from its effective_from local date; match on the local date of the reported timestamp'",
                 "multiplier_applied: 'when true for a meter on that date, the exported register values have already been multiplied by the multiplier in force at the corrected (true) read instant; divide them back to obtain the register reading'",
                 "multiplier_applied_entries:"]
    for i, x in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, x["meter"]) if fam == "T1" else x["meter"]
        frm = x["from"].isoformat() if fam != "T3" else x["from"].strftime("%m/%d/%Y")
        key = "since" if fam == "T8" else "effective_from"
        lines.append(f"  - {{meter_id: {_yaml_str(mid)}, multiplier_applied: {'true' if x['applied'] else 'false'}, {key}: {_yaml_str(frm)}}}")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_borealis_map(X, TR, out, r):
    fn = "borealis_channel_map.toml"
    rows = sorted(X.bor_ch, key=lambda x: (x["meter"], x["from"]))
    sem = TR.match(fn, rows, lambda x: [x["meter"]] if x["from"] >= MONTH_START else [])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    lines = ["# Borealis channel assignments (applies to borealis_reads_2025-11_p*.xml)",
             "# Each entry assigns the import and export register channels from effective_from (local date) onward.",
             "# Match on the local date of the reported timestamp. Channels not assigned to the meter are ignored. Units come from each Ch element.",
             "[profile]", 'hes_code = "BOR"', 'timestamps = "ISO-8601, UTC (Z) or with an explicit offset"',
             'segments = "a <Segment schema=\\"2\\"> block uses <Rd m= t= sq=> in place of <Read meter= ts= seq=>"',
             'missing = "a Ch element with q=\\"MISSING\\" carries no value"', ""]
    for i, x in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, x["meter"]) if fam == "T1" else x["meter"]
        frm = x["from"].isoformat() if fam != "T3" else x["from"].strftime("%Y%m%d")
        lines.append("[[channel_map]]")
        lines.append(f'meter_id = "{mid}"')
        if fam == "T8":
            lines.append(f"channels = {{ import = {x['imp']}, export = {x['exp']} }}")
        else:
            lines.append(f"import_channel = {x['imp']}")
            lines.append(f"export_channel = {x['exp']}")
        lines.append(f'effective_from = "{frm}"')
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_rollover(X, TR, out, r):
    fn = "register_rollover.toml"
    rows = sorted(X.digits.items())
    rep = TR.plan(fn, len(rows), [], ["T1", "T8", "T1", "T4"], r)
    lines = ["# Register dial capacity: a register with N digits counts modulo 10^N kWh.", "[defaults]", "digits = 6", ""]
    for i, (m, dg) in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, m) if fam == "T1" else m
        if fam == "T8":
            lines.append(f'[[register]]\nmeter = "{mid}"\ndial_digits = {dg}')
        elif fam == "T4":
            lines.append(f'[[register]]\nmeter_id = "{mid}"\ndigits = "{dg}"')
        else:
            lines.append(f'[[register]]\nmeter_id = "{mid}"\ndigits = {dg}')
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_clock(X, TR, out, r):
    fn = "meter_clock_offsets.toml"
    rows = sorted(X.clock.items())
    rep = TR.plan(fn, len(rows), [], ["T1", "T8", "T3", "T1"], r)
    lines = ["# Measured meter clock offsets (seconds the meter clock runs ahead of true time; negative = behind).",
             "# Subtract the offset from a reported timestamp to obtain true time, until the meter's CLOCK_SYNC event.", ""]
    for i, (m, off) in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, m) if fam == "T1" else m
        if fam == "T8":
            lines.append(f'[[offset]]\nmeter = "{mid}"\nahead_s = {off}')
        elif fam == "T3":
            lines.append(f'[[offset]]\nmeter_id = "{mid}"\noffset_s = {off}\nmeasured_on = "2025-10-{r.randint(1, 28):02d}"')
        else:
            lines.append(f'[[offset]]\nmeter_id = "{mid}"\noffset_s = {off}')
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_delta_ini(X, TR, out, r):
    fn = "delta_ingest.ini"
    rows = sorted(X.delta_policy.items())
    rep = TR.plan(fn, len(rows), [], ["T1", "T8", "T1", "T10"], r)
    lines = ["; Delta MDM staging extract settings (delta_reads_2025-11_p*.parquet)", "[settings]",
             "hes_code = DLT", "identity = spid (service point); resolve to a meter through sp_meter_xref valid at the read time",
             "read_serial = Excel 1900 date system serial of the LOCAL wall time (Lotus compatible, day 60 = 1900-02-29); round to the nearest second",
             "raw_scaling = see register_scaling.ini (decimals per meter)",
             "missing_raw = -1",
             "est_flag = 1 marks a vendor estimate; it is a usable actual read only when the service point est_policy is ACCEPT",
             ""]
    for i, (s, p) in enumerate(rows):
        fam = rep.get(i)
        sid = s.lower() if fam == "T1" else s
        if fam == "T8":
            lines.append(f"[spid {sid}]\npolicy = {p}")
        else:
            lines.append(f"[spid:{sid}]\nest_policy = {p}")
        if fam == "T10":
            lines[-1] = lines[-1] + "\r"
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_cis_ini(X, TR, out, r):
    fn = "cis_legacy_layout.ini"
    rows = sorted(list(X.dial.items()) + list(X.dial_retired.items()))
    rep = TR.plan(fn, len(rows), [], ["T1", "T8", "T1"], r)
    lines = ["; CIS legacy fixed-width read export (cis_legacy_reads_2025-11_[abc].txt)",
             "[records]", "H = header", "L = layout switch: the digit after L selects the layout used by following D records",
             "D = data", "T = trailer (data record count)",
             "[layout.1]", "legacy_id = 2-10", "date = 11-17 (YYYYDDD ordinal day)", "time = 18-21 (HHMM local; 2400 means midnight ending that date)",
             "import = 22-31 (implied 3 decimals; leading blanks are zeros; all nines = missing)", "export = 32-41 (blank = no register)", "seq = 42-51",
             "[layout.2]", "date = 2-8", "time = 9-12", "seq = 13-22", "legacy_id = 23-31",
             "import = 32-42 (implied 3 decimals)", "export = 43-53",
             "[identity]", "legacy_id_format = L-nnnnnn (case-insensitive; the hyphen may be missing)",
             "meter_link = ACTIVE rows of the Crosswalk sheet in meter_registry_migration_wave3.xlsx",
             "[dial]", "register_kwh = field value x dial_constant", ""]
    for i, (lid, dial) in enumerate(rows):
        fam = rep.get(i)
        l2 = lid.lower() if fam == "T1" else lid
        if fam == "T8":
            lines.append(f"[legacy {l2}]\nkh = {dial}")
        else:
            lines.append(f"[legacy:{l2}]\ndial_constant = {dial}")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_scaling_ini(X, TR, out, r):
    fn = "register_scaling.ini"
    rows = sorted((m, X.meters[m]["res"]) for m in X.meters)
    rep = TR.plan(fn, len(rows), [], ["T1", "T8", "T1"], r)
    lines = ["; Register resolution (decimal places) per meter.  Raw integer register counts (Delta import_raw/export_raw)",
             "; are divided by 10^decimals to obtain kWh.", ""]
    for i, (m, res) in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, m) if fam == "T1" else m
        if fam == "T8":
            lines.append(f"[meter {mid}]\nresolution = {res}")
        else:
            lines.append(f"[{mid}]\ndecimals = {res}")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_mbox(X, TR, out, r):
    fn = "mdm_ops_mailbox_2025-11.mbox"
    msgs = []
    for h in X.holds:
        msgs.append(("h", h["t"], h))
    t_cab = local_to_utc(date(2025, 11, 20), 10, 0, 0)
    for cab in sorted(X.cab_approved | X.cab_rejected):
        msgs.append(("cab", t_cab + r.randint(0, 9 * 86400), cab))
    msgs.sort(key=lambda m: m[1])
    sem = TR.match(fn, msgs, lambda m: [(m[2]["meter"], bidx_of(m[2]["date"]))] if m[0] == "h" and m[2]["type"] == "HOLD" else [])
    rep = TR.plan(fn, len(msgs), sem, ["T1", "T3", "T10", "T9", "T1"], r)
    parts = []
    for i, (kind, tt, x) in enumerate(msgs):
        fam = rep.get(i)
        dt = datetime.fromtimestamp(tt, tz=timezone.utc)
        date_hdr = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        if fam == "T3":
            loc, _a, off = utc_to_local(tt)
            date_hdr = loc.strftime("%a, %d %b %Y %H:%M:%S ") + ("-0500" if off == -18000 else "-0600")
        if kind == "h":
            mid = rep_id(r, x["meter"]) if fam == "T1" else x["meter"]
            verb = "Read hold" if x["type"] == "HOLD" else "Read release"
            subj = f"MDM notice: {verb} {mid} {x['date'].isoformat()}"
            body = (f"Notice type: {x['type']}\nMeter: {mid}\nRead date: {x['date'].isoformat()}\n"
                    f"Raised by: revenue protection\n")
        else:
            approved = x in X.cab_approved
            subj = f"CAB decision {x}: {'APPROVED' if approved else 'REJECTED'}"
            body = (f"Change advisory board decision for {x}.\nDecision: {'APPROVED' if approved else 'REJECTED'}\n"
                    f"Scope: settlement procedures manual rev4 draft errata index\n")
        if fam == "T10":
            enc_subj = "=?utf-8?q?" + subj.replace(" ", "_").replace(":", "=3A") + "?="
            subj_hdr = enc_subj
        else:
            subj_hdr = subj
        msg = (f"From mdm-notify@kvec.coop {dt.strftime('%a %b %d %H:%M:%S %Y')}\n"
               f"From: MDM Notifications <mdm-notify@kvec.coop>\nTo: settlement-ops@kvec.coop\n"
               f"Date: {date_hdr}\nSubject: {subj_hdr}\nMessage-ID: <{i}.{tt}@kvec.coop>\n")
        if fam == "T9":
            msg += ('MIME-Version: 1.0\nContent-Type: multipart/alternative; boundary="b1"\n\n--b1\n'
                    'Content-Type: text/plain; charset=utf-8\n\n' + body + "\n--b1\nContent-Type: text/html\n\n<p>see text part</p>\n--b1--\n")
        else:
            msg += "Content-Type: text/plain; charset=utf-8\n\n" + body
        parts.append(msg)
    parts.append("From ops-lead@kvec.coop Mon Dec 01 08:00:00 2025\nFrom: Settlement Lead <ops-lead@kvec.coop>\n"
                 "To: settlement-ops@kvec.coop\nDate: Mon, 01 Dec 2025 14:00:00 +0000\nSubject: Reminder: hold and release cutoff\n"
                 "Content-Type: text/plain; charset=utf-8\n\nA RELEASE notice only counts when it is sent at or before the settlement cutoff,\n"
                 "2025-12-03 17:00 America/Chicago. A held read with no qualifying release stays out of the November settlement.\n")
    (out / fn).write_text("\n".join(parts), encoding="utf-8")


def _ics_fold(line):
    out = []
    while len(line.encode("utf-8")) > 74:
        out.append(line[:74])
        line = " " + line[74:]
    out.append(line)
    return "\r\n".join(out)


def write_ics(X, TR, out, r):
    fn = "territory_rate_calendar.ics"
    rows = X.cal
    sem = TR.match(fn, rows, lambda e: [(e["territory"], e["start"])])
    rep = TR.plan(fn, len(rows), sem, ["T3", "T1", "T10", "T8", "T3"], r)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//KVEC//Rate Calendar//EN", "X-WR-CALNAME:KVEC territory rate calendar"]
    crlf_from = set()
    for i, e in enumerate(rows):
        fam = rep.get(i)
        if fam == "T10":
            crlf_from.add(len(lines))
        terr = e["territory"].lower() if fam == "T1" else e["territory"]
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:kvec-cal-{e['uid']}@kvec.coop")
        if fam == "T3":
            lines.append(f"DTSTART;TZID=America/Chicago:{e['start'].strftime('%Y%m%d')}T000000")
            lines.append(f"DTEND;TZID=America/Chicago:{e['end'].strftime('%Y%m%d')}T000000")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{e['start'].strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{e['end'].strftime('%Y%m%d')}")
        summary = f"{e['kind']} {terr} {e['name']}"
        if fam == "T10":
            summary = summary + " - territory-wide observance with extended description for folding test purposes"
        if fam == "T8":
            lines.append(f"STATUS:{e['status']}")
            lines.append(f"CATEGORIES:{e['kind']}")
            lines.append(f"X-KVEC-TERRITORY:{terr}")
        else:
            lines.append(f"CATEGORIES:{e['kind']}")
            lines.append(f"X-KVEC-TERRITORY:{terr}")
            lines.append(f"STATUS:{e['status']}")
        lines.append(f"SUMMARY:{summary}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    parts = []
    for j, x in enumerate(lines):
        crlf = any(s <= j < s + 8 for s in crlf_from)
        parts.append(_ics_fold(x).replace("\r\n", "\r\n" if crlf else "\n") + ("\r\n" if crlf else "\n"))
    (out / fn).write_text("".join(parts), encoding="utf-8", newline="")


# ---------------------------------------------------------------------------
# part 4c - specification documents and document-style data files
# ---------------------------------------------------------------------------
SOURCE_REGISTER = [
    ("settlement_data_contract.md", "this contract (computation rules, output formats, connectivity appendix)"),
    ("kvec_settlement_procedures_manual.docx", "settlement procedures manual revision 3 (authority and precedence, feeder table, read schedule register)"),
    ("settlement_procedures_manual_rev4_draft.docx", "settlement procedures manual revision 4 working draft"),
    ("aurora_reads_2025-11_p1.csv ... _p6.csv", "Aurora head-end register reads, six period files"),
    ("borealis_reads_2025-11_p1.xml ... _p6.xml", "Borealis head-end register reads, six period files"),
    ("cirrus_reads_2025-11_p1.jsonl ... _p6.jsonl", "Cirrus mesh head-end register reads, six period files"),
    ("delta_reads_2025-11_p1.parquet ... _p6.parquet", "Delta MDM staging register reads, six period files"),
    ("cis_legacy_reads_2025-11_a.txt, _b.txt, _c.txt", "CIS legacy fixed-width register reads, three period files"),
    ("fjord_reads_2025-11_p1.tsv ... _p6.tsv", "Fjord head-end register reads, six period files"),
    ("fjord_reads_2025-11_p4b.tsv", "Fjord period 4 batch received 2025-12-02"),
    ("aurora_hes_profile.yaml", "Aurora export profile and firmware history"),
    ("borealis_channel_map.toml", "Borealis channel assignments"),
    ("cirrus_hes_profile.yaml", "Cirrus export profile and device firmware history"),
    ("cirrus_daily_usage_2025-11.jsonl", "Cirrus device usage summary by period"),
    ("delta_ingest.ini", "Delta staging extract settings and service point estimate policy"),
    ("cis_legacy_layout.ini", "CIS legacy record layouts and dial constants"),
    ("fjord_hes_profile.yaml", "Fjord export profile and multiplier flags"),
    ("fjord_hes_profile_2026.yaml", "Fjord export profile for the firmware 6.0 rollout"),
    ("register_scaling.ini", "register resolution per meter"),
    ("register_rollover.toml", "register dial capacity per meter"),
    ("meter_clock_offsets.toml", "meter clock offsets"),
    ("mdm_registry_north.db, mdm_registry_east.db, mdm_registry_southwest.db", "district meter registries (attribute history)"),
    ("dw_registry_snapshot_2025-12-03.db", "data warehouse registry snapshot"),
    ("meter_registry_migration_wave3.xlsx", "AMI migration wave 3 workbook (legacy id crosswalk and attributes)"),
    ("mdm_october_close_reads.csv", "October close boundary reads"),
    ("mdm_void_register.csv", "MDM void register, year to date"),
    ("mdm_read_corrections.csv", "MDM read corrections, year to date"),
    ("mdm_vee_estimates.tsv", "MDM VEE estimates, year to date"),
    ("vee_estimate_review_2025.xlsx", "VEE estimate reviews (H1, H2)"),
    ("mdm_batch_control.log", "MDM batch control log"),
    ("hes_batch_manifest_2025-11.json", "head-end vendor delivery manifest"),
    ("hes_ingest_debug.log", "head-end ingest service log"),
    ("hes_known_issues.md", "head-end known issue register"),
    ("mdm_ops_mailbox_2025-11.mbox", "MDM operations mailbox export"),
    ("collector_events_2025-11.log", "collector event log"),
    ("field_service_orders.jsonl", "field service orders"),
    ("ct_ratio_verification_2025.xlsx", "CT ratio field verifications (H1, H2)"),
    ("meter_accuracy_test_results_2025.docx", "meter accuracy test results"),
    ("disconnection_register_2025.docx", "service disconnection and reconnection register"),
    ("netmetering_enrollments.csv", "net metering applications"),
    ("export_meter_inspections_2025.xlsx", "export meter inspections (H1, H2)"),
    ("cis_account_master.csv", "CIS account master, month-end extract"),
    ("cis_account_master_2025-12.csv", "CIS account master, next-month extract"),
    ("account_merges_2025.json", "account merge register"),
    ("account_rate_history.xlsx", "account rate code history (2024, 2025)"),
    ("account_rate_history_restated.xlsx", "restated rate code history"),
    ("rate_code_crosswalk_2026.json", "rate code consolidation crosswalk"),
    ("tariff_book_residential_q4.docx", "Q4 2025 tariff book, residential"),
    ("tariff_book_industrial_q4.docx", "Q4 2025 tariff book, industrial"),
    ("tariff_book_commercial_q4.pdf", "Q4 2025 tariff book, small and large general service"),
    ("tariff_book_agri_lighting_q4.pdf", "Q4 2025 tariff book, agricultural and lighting"),
    ("tariff_book_residential_2026.pdf", "2026 residential tariff filing"),
    ("tariff_errata_register.html", "tariff errata register"),
    ("rider_schedule_2025.pdf", "rider adder schedule"),
    ("rider_applicability_matrix.html", "rider applicability by rate code and territory"),
    ("net_metering_export_credit_rider.docx", "export credit rates"),
    ("territory_rate_calendar.ics", "territory holiday and critical peak calendar"),
    ("ufe_allocation_exemptions_register.pdf", "UFE allocation exemptions"),
    ("unmetered_supply_inventory.json", "unmetered lighting fixture inventory"),
    ("unmetered_fixture_audit_2025.xlsx", "fixture audit findings (Q3, Q4)"),
    ("photocell_burn_hours.json", "dusk-to-dawn hours by feeder and date"),
    ("lighting_burn_hour_exceptions_2025.xlsx", "fixture burn-hour exceptions (Q3, Q4)"),
    ("customer_portal_usage_export.html", "customer portal usage export and dispute outcomes"),
    ("substation_north_scada_2025-11.csv", "north substation feeder demand (F01-F03)"),
    ("substation_east_scada_2025-11.json", "east substation feeder energy (F04-F06)"),
    ("substation_south_historian.log", "south substation historian dump (F07-F09)"),
    ("substation_west_monthly_report.pdf", "west substation monthly report (F10-F12)"),
    ("substation_east_monthly_report.pdf", "east substation monthly report"),
    ("scada_15min_gapfill_2025-11.csv", "analytics 15-minute feeder series"),
    ("scada_alarm_journal.log", "SCADA alarm journal"),
    ("scada_errata_notice.md", "SCADA interval errata"),
]


def spec_text(X):
    lines = []
    A = lines.append
    A("# KVEC November 2025 Settlement Data Contract")
    A("")
    A("Kestrel Valley Electric Cooperative (KVEC) settles every month from the files in this directory. This contract defines the")
    A("computation and the deliverables. The settlement procedures manual (`kvec_settlement_procedures_manual.docx`, revision 3)")
    A("defines which source is authoritative when sources disagree; each head-end profile defines how its export is parsed. Read")
    A("all three. Nothing in a file name, file date or file size decides authority.")
    A("")
    A("## 1. Scope and time")
    A("")
    A("- Settlement month: November 2025. Settlement days are the local dates 2025-11-01 through 2025-11-30.")
    A("- Local time zone: America/Chicago. Daylight saving time ends 2025-11-02 at 02:00 CDT (07:00Z); the local hour 01:00-02:00")
    A("  occurs twice. Every instant in this contract is an absolute instant; convert local wall times with the offset in force.")
    A("- Boundaries: a meter has one boundary on each local date 2025-11-01 through 2025-12-01 (31 boundaries). The boundary")
    A("  instant is the meter's scheduled read time on that boundary date: 00:00 local on the date, or, for meters scheduled at")
    A("  23:00, 23:00 local on the previous date. The schedule in force on a boundary date comes from Appendix R of the manual")
    A("  (latest effective_from on or before the boundary date) together with approved errata described in the manual.")
    A("- The 2025-11-01 boundary comes from `mdm_october_close_reads.csv` (already validated by MDM at the scheduled instant).")
    A("  The 2025-12-01 boundary belongs to the settlement; 2025-10-31 and 2025-12-02 do not.")
    A("")
    A("## 2. Identifiers")
    A("")
    A("Normalize every identifier before joining: apply Unicode NFKC, map Cyrillic \u041a/\u0410/\u0421 to Latin K/A/C, remove all")
    A("whitespace, upper-case. Meter ids are `KV` + 7 digits, account ids `AC` + 8 digits, fixture ids `FX` + 6 digits: when")
    A("fewer digits are present, left-pad the numeric part with zeros. Feeder ids are F01-F12 (`F1`, `f01`, `FDR-01` and")
    A("`F 01` all mean F01). Service points are `SP` + 9 digits (drop hyphens). Cirrus device EUIs are 16 hexadecimal digits")
    A("(upper-case, drop `:`). Legacy ids are `L-` + 6 digits (the hyphen may be missing). A read whose identifier does not resolve")
    A("to a registered meter, or that resolves only through a link that is not valid at the read time, is ignored.")
    A("")
    A("Text exports are UTF-8 unless a head-end profile says otherwise. Records end with LF or with a bare CR, mixed within one")
    A("file; both terminate a record. Calendar continuation lines start with one space after the terminator.")
    A("")
    A("## 3. Candidate reads")
    A("")
    A("A head-end row is a candidate for meter m only if:")
    A("")
    A("1. its identifier resolves to m (section 2 and the head-end profile);")
    A("2. its register value is present (profile missing-value markers are absent values);")
    A("3. after clock correction its true instant lies inside the meter's service window. Clock correction: subtract the meter's")
    A("   offset from `meter_clock_offsets.toml` when (reported instant - offset) is earlier than the meter's CLOCK_SYNC event in")
    A("   `collector_events_2025-11.log`, or when the meter has no CLOCK_SYNC event; otherwise the reported instant is already true.")
    A("   A meter removed by a completed exchange order has no reads at or after the exchange instant; the replacement meter has")
    A("   no reads before it.")
    A("4. its true instant is within 900 seconds (inclusive) of one of the meter's boundary instants. That boundary is the")
    A("   candidate's boundary. A row more than 900 seconds from every boundary instant is not a boundary read.")
    A("")
    A("The manual lists the exclusions that remove candidates and the precedence that selects one value per boundary. Among")
    A("several surviving actual reads for one boundary, the one closest to the boundary instant wins; on equal distance the higher")
    A("sequence number wins. Register values are kWh; values printed with more than three decimals are rounded half-even to three.")
    A("")
    A("## 4. Register arithmetic")
    A("")
    A("Energy is computed per register (import, export) from an ordered list of anchors: the resolved boundaries, the final")
    A("register of a meter removed by a completed EXCHANGE order, the initial register of its replacement, the register reading")
    A("recorded by a completed CT_CHANGE order, and REGISTER_RESET events (pre-reset and post-reset values). Missing boundaries are")
    A("skipped (a gap). Walk the anchors in time order keeping the previous accepted anchor:")
    A("")
    A("- A REGISTER_RESET contributes (pre_reset - previous) and the post-reset value becomes the previous value.")
    A("- Otherwise delta = value - previous. If delta < 0 and the previous value is at least 90 percent of 10^digits while the new")
    A("  value is below 10 percent of 10^digits (digits from `register_rollover.toml`), the register rolled over: add 10^digits.")
    A("  Any other negative delta at a boundary invalidates that boundary: it is skipped and the previous anchor is kept.")
    A("- Each accepted delta is a segment ending at the anchor instant. Its energy in Wh is delta x 1000 x the multiplier in force")
    A("  one second before the segment end, and it is attributed to the local date of (segment end - 1 second). A gap therefore")
    A("  places all energy since the last accepted anchor on the closing day; gaps are never interpolated. Energy after the last")
    A("  accepted anchor is not settled this month.")
    A("- Multiplier in force at an instant: the latest of (registry row valid_from at 00:00 local, completed CT_CHANGE order at its")
    A("  completion instant, CT ratio verification with action CORRECT_RATIO at 00:00 local of verified_on), on equal instants")
    A("  order beats verification beats registry. Ratios written `N:5` mean multiplier N.")
    A("- Meter accuracy: for a meter with a FAIL accuracy test dated in November (latest test date, then highest test id), each")
    A("  daily import Wh on dates before the test date becomes round_half_even(Wh x 100 / (100 + as_found_error_pct)).")
    A("")
    A("## 5. Billing determinants")
    A("")
    A("For meter m and settlement day d:")
    A("")
    A("- Account: the registry row of m valid on d (valid_from <= d < valid_to; empty valid_to is open), then follow completed")
    A("  merges effective on or before d (predecessor to successor, repeatedly) as the manual defines.")
    A("- Vacant: the resolved account has status FINAL in the account master with final_date <= d. Disconnected: the latest")
    A("  disconnection register event dated on or before d is DISCONNECT. Energy on vacant or disconnected days, or with no")
    A("  registry account, is unbilled.")
    A("- Export credit: export Wh is credited only on billed days when the meter has an APPROVED net metering application with")
    A("  effective_from <= d < effective_to (empty = open) and the latest export inspection dated on or before d is PASS (a FAIL")
    A("  on the same date wins). Uncredited export is ignored everywhere.")
    A("- Territory of a meter day: the territory of the meter's feeder (Appendix T connectivity, manual Table F).")
    A("")
    A("Unmetered lighting fixtures are billed on deemed energy. A fixture is active on d when installed <= d < removed and no")
    A("audit finding REMOVED is effective on or before d. Watts: the latest WATTAGE_CHANGE audit effective on or before d, else")
    A("the inventory nominal watts. Hours: a burn-hour exception for the fixture and date if one exists; else DUSK_DAWN uses the")
    A("feeder's dusk-to-dawn hours for the date, PART_NIGHT uses those hours less 6.00 (never below zero), ALL_DAY uses 24.00.")
    A("Hours are applied at two decimals (round half-even). Deemed Wh per fixture day = round_half_even(watts x hours). Deemed")
    A("energy is billed to the fixture's account like import, with the fixture feeder's territory.")
    A("")
    A("## 6. Day types, rates and charges")
    A("")
    A("Day type of (territory, d): HOLIDAY if a CONFIRMED HOLIDAY event of that territory covers d; else CPP if a CONFIRMED CPP")
    A("event covers d; else WEEKEND on Saturday and Sunday; else WEEKDAY. An event covers DTSTART <= d < DTEND. CANCELLED events")
    A("do not exist. Rate code of an account on d: as the manual defines. Base energy rate (cents per kWh) of (rate code, d, day")
    A("type): the tariff book row, replaced by an erratum where the manual says so. Rider adders: every rider in force for the rate")
    A("code on d whose applicability flag (latest effective_from on or before d for the rate code, rider and territory) is Y, plus")
    A("the storm recovery rider where the manual says so. Export credit rate: `net_metering_export_credit_rider.docx`. All rates")
    A("are applied at five decimals, rounded half-even when printed longer; follow every document note about units.")
    A("")
    A("Charges per account: energy = sum over its billed import and deemed Wh of Wh x base rate / 1000; rider = the same with the")
    A("summed adders; export credit = sum of credited export Wh x credit rate / 1000. Accumulate exactly, then round each of the")
    A("three monthly sums half-even to integer cents once. export_credit_cents is the negated rounded credit.")
    A("")
    A("## 7. Feeder injection and losses")
    A("")
    A("Each feeder has 2884 interval-ending 15-minute intervals: (2025-11-01 00:00, 2025-12-01 00:00] local, including the repeated")
    A("hour. An interval value is invalid when its quality is not good, its value is missing, or a COMM_FAIL alarm in")
    A("`scada_alarm_journal.log` overlaps it (alarm RAISED before the interval end and CLEARED after the interval start). The value")
    A("used per interval follows the manual's SCADA precedence. Demand values are applied at two decimals of kW, energy values at")
    A("three decimals of kWh or six of MWh (round half-even when printed longer). Demand in kW over a 15-minute interval is")
    A("kW x 250 Wh, rounded half-even to whole Wh; kWh and MWh convert exactly.")
    A("Feeder injection = sum of its interval Wh. Feeder losses = round_half_even(injection x loss_pct / 100) with loss_pct from")
    A("manual Table F as amended by approved errata.")
    A("")
    A("## 8. Unaccounted-for energy")
    A("")
    A("System UFE Wh = total injection + total credited export - total losses - total billed import - total deemed. UFE is")
    A("allocated to accounts in proportion to their billed import + deemed Wh, excluding accounts with weight zero and accounts")
    A("exempt on 2025-11-30 (ACTIVE exemption with effective_from <= 2025-11-30 < effective_to, empty = open). Use the largest")
    A("remainder method on whole Wh: allocate floor(|UFE| x w / W), then give one more Wh to the accounts with the largest")
    A("remainders, ties to the lower account id; a negative UFE is allocated as its magnitude and negated.")
    A("UFE price (cents per kWh) = (sum of energy_cents + sum of rider_cents) x 1000 / (total billed import + total deemed Wh),")
    A("rounded half-even to six decimals. ufe_charge_cents = round_half_even(ufe_wh x price / 1000).")
    A("")
    A("## 9. Deliverables")
    A("")
    A("CSV files: UTF-8, no BOM, comma separated, LF line endings, one header row exactly as listed, no quoting, a final newline.")
    A("JSON files: `json.dumps(obj, indent=2, sort_keys=True)` followed by a newline. Integers are JSON integers.")
    A("")
    A("- `account_settlement.csv`: " + ", ".join(OUTPUT_COLUMNS["account_settlement.csv"]) + ". One row per resolved account with")
    A("  non-zero billed import, credited export or deemed Wh; rate_code is the code on the account's last day with any of those;")
    A("  total_cents = energy + rider + export credit + UFE charge. Sorted by account_id.")
    A("- `meter_summary.csv`: " + ", ".join(OUTPUT_COLUMNS["meter_summary.csv"]) + ". One row per meter with at least one resolved")
    A("  boundary in its service range, sorted by meter_id. import_wh is all attributed import (after the accuracy correction),")
    A("  billed_import_wh its billed part, unbilled_wh the rest, export_wh the credited export. The four counts classify the")
    A("  meter's boundaries in its service range (old meter up to its exchange day, replacement meter from the day after).")
    A("- `read_resolution.csv`: " + ", ".join(OUTPUT_COLUMNS["read_resolution.csv"]) + ". One row per boundary in a meter's service")
    A("  range whose import value is not an actual read: CORRECTION, ESTIMATE, MISSING (no value) or INVALIDATED (section 4).")
    A("  import_kwh has three decimals (the rejected value for INVALIDATED, empty for MISSING). Sorted by meter_id, boundary_date.")
    A("- `interval_injection.csv`: " + ", ".join(OUTPUT_COLUMNS["interval_injection.csv"]) + ". interval_end_utc as")
    A("  YYYY-MM-DDTHH:MM:SSZ; source is ERRATUM, RELAY_TEST, HISTORIAN or GAPFILL. Sorted by feeder, then time.")
    A("- `lighting_deemed.csv`: " + ", ".join(OUTPUT_COLUMNS["lighting_deemed.csv"]) + ". Fixtures with deemed_wh > 0; burn_days")
    A("  counts days with deemed Wh > 0. Sorted by fixture_id.")
    A("- `daytype_calendar.csv`: territory, date, daytype for TE, TN, TS, TW (that order) and each settlement day, sorted by territory, then date.")
    A("- `feeder_balance.json`: {\"feeders\": {F01: {...}, ...}} with injection_wh, loss_wh, billed_import_wh, billed_export_wh,")
    A("  deemed_wh, unbilled_wh, residual_wh (= injection + billed export - loss - billed import - deemed) per feeder; meter")
    A("  energy counts on the meter's connectivity feeder, deemed energy on the fixture feeder.")
    A("- `control_report.json`: {\"batches\": [...]} one object per head-end read file including the period 4 resend, sorted by")
    A("  file name: file, data_rows (data records counted in the file itself: reads, plus REV records in the resend), manifest_rows")
    A("  (the record count the vendor manifest reports for the file), mdm_status (from the batch control log), rejected_rows (rows the")
    A("  batch control log excludes; all rows of a REJECTED batch), withdrawn_rows (rows the vendor manifest withdraws).")
    A("- `settlement_summary.json`: account_count, meter_count, injection_wh, loss_wh, billed_import_wh, billed_export_wh,")
    A("  deemed_wh, unbilled_wh, ufe_wh, ufe_price_cents_per_kwh (string with six decimals), energy_cents, rider_cents,")
    A("  export_credit_cents, ufe_charge_cents, total_cents (sums over account_settlement).")
    A("")
    A("## 10. Source register")
    A("")
    A("| file | content |")
    A("|---|---|")
    for f, d in SOURCE_REGISTER:
        A(f"| {f} | {d} |")
    A("")
    A("## Appendix T. Connectivity model extract (normative)")
    A("")
    return lines


def write_spec(X, TR, out, r):
    fn = "settlement_data_contract.md"
    lines = spec_text(X)
    rows = sorted(X.conn, key=lambda c: c["meter"])
    rep = TR.plan(fn, len(rows), [], ["T1", "T8", "T1", "T1"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines.append("| meter_id | feeder |")
    lines.append("|---|---|")
    for i, c in enumerate(rows):
        fam = rep.get(i)
        if i == drift:
            lines.append("")
            lines.append("Continuation (columns swapped):")
            lines.append("")
            lines.append("| feeder | meter_id |")
            lines.append("|---|---|")
        mid = rep_id(r, c["meter"]) if fam == "T1" else c["meter"]
        lines.append(f"| {c['feeder']} | {mid} |" if i >= drift else f"| {mid} | {c['feeder']} |")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


MANUAL_RULES = [
    ("h", 1, "KVEC Settlement Procedures Manual - Revision 3 (in force from 2025-07-01)"),
    ("h", 2, "1. Authority"),
    ("p", "This manual decides authority and precedence between settlement sources. Drafts of later revisions have no effect. "
          "The only exception is the errata index of the revision 4 working draft: an erratum listed there takes effect when the "
          "change advisory board (CAB) decision email for its CR number in the MDM operations mailbox says APPROVED; it then "
          "replaces the Table F loss factor of its feeder, or adds an Appendix R schedule row for its meter from its effective date "
          "(an added row outranks a register row with the same effective date). Every other table and rule of the draft is ignored."),
    ("h", 2, "2. Registry and identity"),
    ("p", "The district registries (mdm_registry_north.db, mdm_registry_east.db, mdm_registry_southwest.db) are the registry of "
          "record for account links, multipliers and service windows. The data warehouse snapshot dw_registry_snapshot_2025-12-03.db "
          "is informational and is not used for attributes; its table sp_meter_xref is the only published link from Delta service "
          "points to meters and is used for that purpose, choosing the non-VOID row valid at the read instant (valid_from <= t < "
          "valid_to, empty valid_to is open). Legacy CIS ids resolve only through the ACTIVE rows of the Crosswalk sheet of "
          "meter_registry_migration_wave3.xlsx; the attribute columns of that workbook are migration staging data and are not used. "
          "Cirrus devices resolve through cirrus_daily_usage_2025-11.jsonl: a device read belongs to the meter listed for that device "
          "and the read file's period number (rows with status VOID link nothing); the usage values in that file are informational."),
    ("h", 2, "3. Boundary value precedence"),
    ("p", "For each meter boundary the value is taken from the first source that has one: (1) a VALIDATED correction in "
          "mdm_read_corrections.csv for the meter and read date, highest revision; PROVISIONAL and REJECTED rows never apply; "
          "(2) the selected actual read (contract section 3) after exclusions; (3) a VEE estimate from mdm_vee_estimates.tsv for "
          "the meter and read date whose latest review in vee_estimate_review_2025.xlsx (latest reviewed_on) is APPROVED, highest "
          "version among those; (4) none (missing). The read date of a boundary is its boundary date. A boundary invalidated by "
          "the register arithmetic is not resolved again."),
    ("h", 2, "4. Exclusions"),
    ("p", "A candidate read is excluded when any of the following applies. Void register rows with reinstated = N whose hes code, "
          "meter and read date match. A dispute for the meter and read date whose latest decision (latest decided date) in the "
          "dispute table of customer_portal_usage_export.html is UPHELD (the usage figures of that export are customer information "
          "only). Rows of a batch the batch control log marks REJECTED, and the rows in the rejected_rows range (1-based data record "
          "ordinals in the file) of a PARTIAL batch. Rows inside the withdrawn range of a batch in hes_batch_manifest_2025-11.json "
          "(same ordinals; entries marked superseded are replaced by the later entry for the same file); the manifest record counts "
          "are the vendor's delivered counts and are reported, not enforced, and the row counts of the batch control log are the same "
          "kind of claim by MDM. Neither is the number of data records a file holds: that number is counted from the file itself, and "
          "where a delivered count disagrees with it the file wins and the vendor's number is still reported as delivered. A read "
          "hold in the MDM operations mailbox for the meter "
          "and read date unless a RELEASE for the same meter and date was sent at or before 2025-12-03 17:00 local. A QUARANTINE "
          "line of hes_ingest_debug.log for the meter, read date and hes code, unless a later UNQUARANTINE line names the same read; "
          "the other lines of that log echo parser state and carry no authority. Known issues with status OPEN in hes_known_issues.md "
          "for the meter, read date and hes code: STUCK_REGISTER excludes the read, WH_AS_KWH divides both registers by 1000, "
          "SWAP_REGISTERS exchanges import and export. Delta rows with est_flag = 1 are excluded unless the service point est_policy "
          "in delta_ingest.ini is ACCEPT."),
    ("p", "The Fjord period 4 batch received 2025-12-02 (fjord_reads_2025-11_p4b.tsv) was rejected by MDM as a duplicate resend; "
          "none of its read rows are used. Its REV records are vendor reversals and are honoured: each one excludes the original "
          "period 4 read (fjord_reads_2025-11_p4.tsv) for that meter and read date."),
    ("h", 2, "5. Accounts"),
    ("p", "The CIS month-end extract cis_account_master.csv (as_of 2025-11-30) is the account master of record. The next-month "
          "extract cis_account_master_2025-12.csv is a forward-billing preview and is not used for status or rate codes, with one "
          "exception: rows flagged late_posted = Y carry merges that CIS posted after the month-end extract was cut, and such a merge "
          "with merge_effective on or before 2025-11-30 is applied exactly like a COMPLETED merge. Merges in account_merges_2025.json "
          "apply only when COMPLETED; REVERSED and PENDING merges never apply. A merge applies from its effective date inclusive and "
          "chains resolve transitively (when several merges of one predecessor apply, the latest effective one wins)."),
    ("p", "Rate code of an account on day d: the entry of account_rate_history.xlsx (either sheet) with the latest effective_from "
          "on or before d, ties to the higher entry_id; entries whose entry_id appears on the Reversals sheet of "
          "account_rate_history_restated.xlsx were keyed in error and do not exist (the restated history itself is pending approval "
          "and is not in force). Legacy rate aliases (for example R7) resolve through the ACTIVE entries of legacy_aliases in "
          "rate_code_crosswalk_2026.json. Account migrations in that crosswalk take effect on their effective date unless WITHDRAWN: "
          "migrations effective inside the settlement month (early adopters) are therefore in force and outrank a history entry with "
          "the same effective date, while 2026 migrations are not. When no entry applies, use rate_code_snapshot of the account master."),
    ("h", 2, "6. Tariffs"),
    ("p", "The Q4 2025 tariff books are authoritative for base rates. An erratum in tariff_errata_register.html replaces the book rate "
          "for its rate code, date and day type when its status is APPROVED and no APPROVED erratum names it in supersedes; among the "
          "remaining errata for the same key the latest issued wins, ties to the higher erratum number. WITHDRAWN errata never apply. "
          "Riders come from rider_schedule_2025.pdf (ACTIVE rows; RESCINDED rows never apply) and rider_applicability_matrix.html. "
          "The storm recovery rider was approved under docket 25-STORM before the 2026 filing: the APPROVED rows of Table S in "
          "tariff_book_residential_2026.pdf with effective_from on or before 2025-11-30 are in force from that date for their rate "
          "code in every territory; the 2026 base rates of that filing are not."),
    ("h", 2, "7. Feeder injection"),
    ("p", "For each feeder interval the value is the first available of: (1) an APPROVED SCADA erratum in scada_errata_notice.md for "
          "the feeder and interval end that no APPROVED erratum supersedes (latest issued, ties to the higher number; WITHDRAWN "
          "never applies); (2) for east feeders, the relay-test replacement value of a DONE row in section 4 of "
          "substation_east_monthly_report.pdf (the rest of that report is a rounded presentation copy); (3) the substation historian "
          "value when valid; (4) the analytics gap-fill value in scada_15min_gapfill_2025-11.csv, PUBLISHED rows of model v3 only. "
          "The analytics series is not revenue grade and is used only in case (4)."),
    ("h", 2, "8. Head-end profile changes"),
    ("p", "fjord_hes_profile_2026.yaml prepares the firmware 6.0 rollout. Its entries with effective_from on or before 2025-11-30 "
          "belong to the November pilot and are in force from their date; later entries are not. Every other head-end setting comes "
          "from the head-end's current profile."),
]


def write_manual(X, TR, out, r):
    fn = "kvec_settlement_procedures_manual.docx"
    blocks = list(MANUAL_RULES)
    blocks.append(("h", 2, "Table F. Feeders"))
    blocks.append(("table", ["feeder", "substation", "territory", "loss_pct"],
                   [[f, SUBSTATION[f], X.feeder_territory[f], f"{X.feeder_loss_pct[f]:.3f}"] for f in FEEDERS]))
    blocks.append(("h", 2, "Appendix R. Read schedule register"))
    blocks.append(("p", "read_time 00:00 means the boundary instant is local midnight of the boundary date; 23:00 means 23:00 local "
                        "on the previous date. effective_from is a local date."))
    rows = sorted(X.schedule_rows, key=lambda x: (x["meter"], x["from"]))
    key = lambda x: [x["meter"]] if x["from"] >= MONTH_START else []
    rows = _reorder_sem(TR, fn, rows, key, r)
    sem = TR.match(fn, rows, key)
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    t1, t2 = [], []
    for i, x in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, x["meter"]) if fam == "T1" else x["meter"]
        frm = x["from"].isoformat() if fam != "T3" else x["from"].strftime("%m/%d/%Y")
        if i < drift:
            t1.append([mid, x["read_time"], frm])
        else:
            t2.append([frm, mid, x["read_time"]])
    blocks.append(("table", ["meter_id", "read_time", "effective_from"], t1))
    if t2:
        blocks.append(("p", "Appendix R (continued)"))
        blocks.append(("table", ["effective_from", "meter_id", "read_time"], t2))
    write_docx(out / fn, blocks, footer_text="KVEC settlement procedures manual rev 3 - controlled copy")


def _tariff_rows(X, classes):
    codes = [c for k in classes for c in RATE_CODES[k]]
    return [(c, d, dt) for c in codes for d in Q4_DATES for dt in DAYTYPES]


def write_tariff_docx(X, TR, out, r, fn, classes, title):
    rows = _tariff_rows(X, classes)
    dollars = X.unit_dollar_codes[fn]
    sem = TR.match(fn, rows, lambda k: [k[0]])
    rep = TR.plan(fn, len(rows), sem, ["T12", "T3", "T8", "T4", "T12", "T1"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    blocks = [("h", 1, title), ("p", "Base energy rates in cents per kWh by rate code, date and day type (WEEKDAY, WEEKEND, HOLIDAY, CPP)."),
              ("p", "Note U: rows for the following rate codes are stated in dollars per kWh (multiply by 100 for cents): " + ", ".join(dollars) + "."),
              ("p", "Rates are applied at five decimals; values printed with more decimals round half-even. Decimal commas may appear.")]
    t1, t2 = [], []
    for i, (c, d, dt) in enumerate(rows):
        fam = rep.get(i)
        v = X.rates[(c, d, dt)]
        s = f"{v:.5f}"
        if c in dollars:
            s = f"{(v / 100):.7f}"
        if fam == "T12" and c not in dollars:
            s = xprec(v, 5)
        if fam == "T4":
            s = comma_decimal(s)
        ds = d.isoformat() if fam != "T3" else d.strftime("%m/%d/%Y")
        code = c.lower() if fam == "T1" else c
        if i < drift:
            t1.append([code, ds, dt, s])
        else:
            t2.append([ds, dt, code, s])
    blocks.append(("table", ["rate_code", "date", "daytype", "rate"], t1))
    if t2:
        blocks.append(("p", "Schedule continued"))
        blocks.append(("table", ["date", "daytype", "rate_code", "rate"], t2))
    write_docx(out / fn, blocks)


def write_tariff_pdf(X, TR, out, r, fn, classes, title):
    rows = _tariff_rows(X, classes)
    dollars = X.unit_dollar_codes[fn]
    sem = TR.match(fn, rows, lambda k: [k[0]])
    rep = TR.plan(fn, len(rows), sem, ["T12", "T3", "T8", "T4", "T12", "T1"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines = [title, "Base energy rates, cents per kWh.", "Note U: rows for the following rate codes are stated in dollars per kWh (multiply by 100 for cents): "
             + ", ".join(dollars) + ".", "Rates are applied at five decimals; values printed with more decimals round half-even.", "",
             "RATE_CODE | DATE | DAYTYPE | RATE"]
    for i, (c, d, dt) in enumerate(rows):
        fam = rep.get(i)
        if i == drift:
            lines.append("")
            lines.append("DATE | DAYTYPE | RATE_CODE | RATE")
        v = X.rates[(c, d, dt)]
        s = f"{v:.5f}" if c not in dollars else f"{(v / 100):.7f}"
        if fam == "T12" and c not in dollars:
            s = xprec(v, 5)
        if fam == "T4":
            s = comma_decimal(s)
        ds = d.isoformat() if fam != "T3" else d.strftime("%m/%d/%Y")
        code = c.lower() if fam == "T1" else c
        lines.append(f"{code} | {ds} | {dt} | {s}" if i < drift else f"{ds} | {dt} | {code} | {s}")
    write_pdf(out / fn, lines)


def write_export_rider(X, TR, out, r):
    fn = "net_metering_export_credit_rider.docx"
    rows = [(c, d, dt) for c in EXPORT_CODES for d in Q4_DATES for dt in DAYTYPES]
    dollars = sorted(r.sample(EXPORT_CODES, 2))
    sem = [(i, "T14", "R-EXPORT-UNIT", "dollar rows") for i, k in enumerate(rows) if k[0] in dollars and k[1] == DAYS[10] and k[2] == "WEEKDAY"]
    rep = TR.plan(fn, len(rows), sem, ["T12", "T3", "T4", "T1"], r)
    blocks = [("h", 1, "Net Metering Export Credit Rider - Q4 2025"),
              ("p", "Credit rates in cents per kWh of credited export, by rate code, date and day type."),
              ("p", "Note C: credit rates for rate codes " + ", ".join(dollars) + " are stated in dollars per kWh."),
              ("p", "Rates apply at five decimals (round half-even); decimal commas may appear.")]
    t = []
    for i, (c, d, dt) in enumerate(rows):
        fam = rep.get(i)
        v = X.export_rates[(c, d, dt)]
        s = f"{v:.5f}" if c not in dollars else f"{(v / 100):.7f}"
        if fam == "T12" and c not in dollars:
            s = xprec(v, 5)
        if fam == "T4":
            s = comma_decimal(s)
        t.append([c.lower() if fam == "T1" else c, d.isoformat() if fam != "T3" else d.strftime("%m/%d/%Y"), dt, s])
    blocks.append(("table", ["rate_code", "date", "daytype", "credit_rate"], t))
    write_docx(out / fn, blocks)


def write_disconnections(X, TR, out, r):
    fn = "disconnection_register_2025.docx"
    rows = _reorder_sem(TR, fn, X.disc, lambda e: [(e["meter"], e["date"])], r)
    sem = TR.match(fn, rows, lambda e: [(e["meter"], e["date"])])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    blocks = [("h", 1, "Service Disconnection and Reconnection Register 2025"),
              ("p", "Each row records a completed field event. Note: service orders whose reference begins with SOX were cancelled after "
                    "entry; their events did not occur.")]
    t1, t2 = [], []
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    for i, e in enumerate(rows):
        fam = rep.get(i)
        mid = rep_id(r, e["meter"]) if fam == "T1" else e["meter"]
        ds = e["date"].isoformat() if fam != "T3" else e["date"].strftime("%m/%d/%Y")
        (t1 if i < drift else t2).append([mid, e["event"], ds, e["ref"]] if i < drift else [ds, mid, e["ref"], e["event"]])
    blocks.append(("table", ["meter_id", "event", "event_date", "order_ref"], t1))
    if t2:
        blocks.append(("table", ["event_date", "meter_id", "order_ref", "event"], t2))
    write_docx(out / fn, blocks)


def write_accuracy(X, TR, out, r):
    fn = "meter_accuracy_test_results_2025.docx"
    rows = _reorder_sem(TR, fn, X.acc_tests, lambda e: [e["id"]], r)
    sem = TR.match(fn, rows, lambda e: [e["id"]])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T1"], r)
    blocks = [("h", 1, "Meter Accuracy Test Results 2025"),
              ("p", "as_found_error_pct is the registration error found (positive = the meter registered fast). Decimal commas may appear.")]
    t = []
    for i, e in enumerate(rows):
        fam = rep.get(i)
        err = f"{e['error']:+.2f}"
        if fam == "T4":
            err = comma_decimal(err)
        t.append([e["id"], rep_id(r, e["meter"]) if fam == "T1" else e["meter"],
                  e["date"].isoformat() if fam != "T3" else e["date"].strftime("%m/%d/%Y"), err, e["result"]])
    blocks.append(("table", ["test_id", "meter_id", "test_date", "as_found_error_pct", "result"], t))
    write_docx(out / fn, blocks)


def write_rider_pdf(X, TR, out, r):
    fn = "rider_schedule_2025.pdf"
    rows = X.rider_rows
    sem = TR.match(fn, rows, lambda x: [(x["rider"], x["code"])] if x["status"] == "RESCINDED" else [])
    sem.append((next(i for i, x in enumerate(rows) if x["rider"] == "R-LIEAP"), "T14", "R-RIDER-UNIT", "mills"))
    rep = TR.plan(fn, len(rows), sem, ["T12", "T3", "T4", "T1"], r)
    lines = ["KVEC Rider Adder Schedule 2025", "Adders in cents per kWh, in force from FROM (inclusive) to TO (exclusive).",
             "Note M: adders for rider R-LIEAP are stated in mills per kWh (divide by 10 for cents).",
             "Adders apply at five decimals; values printed with more decimals round half-even.", "",
             "RIDER | RATE_CODE | FROM | TO | ADDER | STATUS"]
    for i, x in enumerate(rows):
        fam = rep.get(i)
        a = x["adder"]
        s = f"{a:.5f}" if x["rider"] != "R-LIEAP" else f"{a * 10:.4f}"
        if fam == "T12" and x["rider"] != "R-LIEAP":
            s = xprec(a, 5)
        if fam == "T4":
            s = comma_decimal(s)
        fr = x["from"].isoformat() if fam != "T3" else x["from"].strftime("%m/%d/%Y")
        lines.append(f"{x['rider']} | {x['code'].lower() if fam == 'T1' else x['code']} | {fr} | {x['to'].isoformat()} | {s} | {x['status']}")
    write_pdf(out / fn, lines)


def write_exemptions(X, TR, out, r):
    fn = "ufe_allocation_exemptions_register.pdf"
    rows = _reorder_sem(TR, fn, X.exemptions, lambda e: [(e["acct"], e["from"])], r)
    sem = TR.match(fn, rows, lambda e: [(e["acct"], e["from"])])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines = ["KVEC UFE Allocation Exemptions Register", "An account is exempt from UFE allocation while an ACTIVE row covers the date.", "",
             "ACCOUNT | FROM | TO | STATUS | BASIS"]
    for i, e in enumerate(rows):
        fam = rep.get(i)
        if i == drift:
            lines.append("")
            lines.append("STATUS | ACCOUNT | BASIS | FROM | TO")
        aid = rep_id_ascii(r, e["acct"]) if fam == "T1" else e["acct"]
        fr = e["from"].isoformat() if fam != "T3" else e["from"].strftime("%m/%d/%Y")
        to = e["to"].isoformat() if e["to"] else "-"
        lines.append(f"{aid} | {fr} | {to} | {e['status']} | {e['basis']}" if i < drift else f"{e['status']} | {aid} | {e['basis']} | {fr} | {to}")
    write_pdf(out / fn, lines)


def write_west(X, TR, out, r):
    fn = SCADA_FILES["west"]
    rows = scada_rows(X, "west")
    sem = TR.match(fn, rows, lambda x: [x])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T12", "T4"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines = ["West Substation Monthly Report - November 2025", "Feeder energy per 15-minute interval (interval-ending local time and UTC offset).",
             "Values in kWh. '---' marks an interval without a valid historian value.", "", "FEEDER | END_LOCAL | OFFSET | KWH | QUALITY"]
    for i, (f, t) in enumerate(rows):
        fam = rep.get(i)
        rec = X.scada[(f, t)]
        if i == drift:
            lines.append("")
            lines.append("END_LOCAL | OFFSET | FEEDER | KWH | QUALITY")
        dt, _a, off = utc_to_local(t)
        fid = feeder_variant(f, r).strip() if fam == "T1" else f
        good = rec["q"] == "GOOD"
        v = f"{rec['kwh']:.3f}" if good else "---"
        if fam == "T12" and good:
            v = xprec(rec["kwh"], 3)
        if fam == "T4" and good:
            v = comma_decimal(v)
        ts = dt.strftime("%Y-%m-%d %H:%M") if fam != "T3" else dt.strftime("%m/%d/%Y %H:%M")
        o = "-05:00" if off == -18000 else "-06:00"
        q = "GOOD" if good else "BAD"
        lines.append(f"{fid} | {ts} | {o} | {v} | {q}" if i < drift else f"{ts} | {o} | {fid} | {v} | {q}")
    write_pdf(out / fn, lines)


def write_scada_errata(X, TR, out, r):
    fn = "scada_errata_notice.md"
    rows = X.scada_errata
    rows = _reorder_sem(TR, fn, rows, lambda e: [(e["feeder"], e["t"])], r)
    sem = TR.match(fn, rows, lambda e: [(e["feeder"], e["t"])])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T4", "T8"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    lines = ["# SCADA interval errata", "", "Corrected feeder interval energy. interval_end is the UTC interval-ending instant. Values are Wh.",
             "An erratum applies when APPROVED and not superseded by another APPROVED erratum; WITHDRAWN entries never apply.", "",
             "| erratum | feeder | interval_end | wh | status | issued | supersedes |", "|---|---|---|---|---|---|---|"]
    for i, e in enumerate(rows):
        fam = rep.get(i)
        if i == drift:
            lines += ["", "| feeder | erratum | status | interval_end | issued | wh | supersedes |", "|---|---|---|---|---|---|---|"]
        fid = feeder_variant(e["feeder"], r).strip() if fam == "T1" else e["feeder"]
        te = iso_utc(e["t"]) if fam != "T3" else iso_local_offset(e["t"])
        wh = str(e["wh"]) if fam != "T4" else thousands(str(e["wh"]))
        if i < drift:
            lines.append(f"| {e['id']} | {fid} | {te} | {wh} | {e['status']} | {e['issued'].isoformat()} | {e['supersedes']} |")
        else:
            lines.append(f"| {fid} | {e['id']} | {e['status']} | {te} | {e['issued'].isoformat()} | {wh} | {e['supersedes']} |")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_known_issues(X, TR, out, r):
    fn = "hes_known_issues.md"
    rows = _reorder_sem(TR, fn, X.known_issues, lambda k: [(k["meter"], bidx_of(k["date"]))], r)
    sem = TR.match(fn, rows, lambda k: [(k["meter"], bidx_of(k["date"]))])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    lines = ["# Head-end known issue register", "",
             "Each OPEN row affects one read: the read of the meter on read_date delivered by the named head end.",
             "Remedies: STUCK_REGISTER - the register did not advance and the read is unusable; WH_AS_KWH - the head end wrote Wh "
             "into kWh fields, divide both registers by 1000; SWAP_REGISTERS - import and export were exchanged. CLOSED rows "
             "are history and carry no remedy.", "",
             "| issue | code | hes | meter_id | read_date | status |", "|---|---|---|---|---|---|"]
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    for i, k in enumerate(rows):
        fam = rep.get(i)
        if i == drift:
            lines += ["", "| meter_id | read_date | issue | status | code | hes |", "|---|---|---|---|---|---|"]
        mid = rep_id(r, k["meter"]) if fam == "T1" else k["meter"]
        ds = k["date"].isoformat() if fam != "T3" else k["date"].strftime("%m/%d/%Y")
        if i < drift:
            lines.append(f"| {k['id']} | {k['code']} | {k['hes']} | {mid} | {ds} | {k['status']} |")
        else:
            lines.append(f"| {mid} | {ds} | {k['id']} | {k['status']} | {k['code']} | {k['hes']} |")
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _html_table(header, rows):
    out = ["<table>", "<tr>" + "".join(f"<th>{xml_esc(h)}</th>" for h in header) + "</tr>"]
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{xml_esc(c)}</td>" for c in row) + "</tr>")
    out.append("</table>")
    return out


def write_tariff_errata(X, TR, out, r):
    fn = "tariff_errata_register.html"
    rows = _reorder_sem(TR, fn, X.tariff_errata, lambda e: [(e["code"], e["date"], e["dt"])], r)
    sem = TR.match(fn, rows, lambda e: [(e["code"], e["date"], e["dt"])])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T12", "T4", "T8"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    html = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>KVEC tariff errata register</title></head><body>",
            "<h1>Tariff errata register</h1>",
            "<p>Corrected base energy rates (cents per kWh, five decimals, round half-even when longer). An erratum applies when APPROVED "
            "and not named in the supersedes column of another APPROVED erratum; WITHDRAWN errata never apply.</p>"]
    t1, t2 = [], []
    for i, e in enumerate(rows):
        fam = rep.get(i)
        rate = f"{e['rate']:.5f}" if fam != "T12" else xprec(e["rate"], 5)
        if fam == "T4":
            rate = comma_decimal(rate)
        ds = e["date"].isoformat() if fam != "T3" else e["date"].strftime("%m/%d/%Y")
        code = e["code"].lower() if fam == "T1" else e["code"]
        if i < drift:
            t1.append([e["id"], code, ds, e["dt"], rate, e["issued"].isoformat(), e["status"], e["supersedes"]])
        else:
            t2.append([e["status"], e["id"], e["supersedes"], code, ds, e["dt"], e["issued"].isoformat(), rate])
    html += _html_table(["erratum", "rate_code", "date", "daytype", "rate", "issued", "status", "supersedes"], t1)
    if t2:
        html.append("<h2>Register continued</h2>")
        html += _html_table(["status", "erratum", "supersedes", "rate_code", "date", "daytype", "issued", "rate"], t2)
    html.append("</body></html>")
    (out / fn).write_text("\n".join(html) + "\n", encoding="utf-8")


def write_rider_matrix(X, TR, out, r):
    fn = "rider_applicability_matrix.html"
    rows = _reorder_sem(TR, fn, X.applicability, lambda a: [(a["code"], a["rider"], a["territory"])] if a["from"] >= MONTH_START else [], r)
    sem = TR.match(fn, rows, lambda a: [(a["code"], a["rider"], a["territory"])] if a["from"] >= MONTH_START else [])
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8", "T1"], r)
    drift = min([i for i, f in rep.items() if f == "T8"] or [len(rows) + 1])
    html = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>Rider applicability</title></head><body>",
            "<h1>Rider applicability matrix</h1>",
            "<p>Y means the rider applies to the rate code in the territory from effective_from until a later row for the same rate "
            "code, rider and territory.</p>"]
    t1, t2 = [], []
    for i, a in enumerate(rows):
        fam = rep.get(i)
        code = a["code"].lower() if fam == "T1" else a["code"]
        ds = a["from"].isoformat() if fam != "T3" else a["from"].strftime("%m/%d/%Y")
        (t1 if i < drift else t2).append([code, a["rider"], a["territory"], ds, a["flag"]] if i < drift else
                                         [a["territory"], a["flag"], code, a["rider"], ds])
    html += _html_table(["rate_code", "rider", "territory", "effective_from", "applies"], t1)
    if t2:
        html += _html_table(["territory", "applies", "rate_code", "rider", "effective_from"], t2)
    html.append("</body></html>")
    (out / fn).write_text("\n".join(html) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# part 4d - the fifteen decoy files
# ---------------------------------------------------------------------------
def _sem_add(sem, i, fam, rule, note):
    sem.append((i, fam, rule, note))


def write_dc01(X, TR, out, r):
    fn = "cis_account_master_2025-12.csv"
    rows = X.master_dec
    base = {a: X.accounts[a] for a in X.accounts}
    sem = TR.match(fn, rows, lambda x: [x["id"]])
    for i, x in enumerate(rows):
        if x["code"] != base[x["id"]]["code"] and i % 3 == 0:
            _sem_add(sem, i, "T16", "R-MASTER-AUTHORITY", "rate code differs from the month-end extract")
        elif x["status"] == "FINAL" and x["final"] and x["final"] >= DEC1:
            _sem_add(sem, i, "T6", "R-MASTER-AUTHORITY", "closed in December")
        elif x["merged_into"] and x["late"] == "N" and i % 2 == 0:
            _sem_add(sem, i, "T13", "R-MERGE", "merge already in the merge register")
    sem = sem[:60]
    t13 = [i for i, x in enumerate(rows) if x["merged_into"] and x["late"] == "N"]
    if t13 and not any(s[1] == "T13" for s in sem):
        sem.append((t13[0], "T13", "R-MERGE", "merge already carried by the merge register"))
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T9", "T8", "T10"], r)
    hdr = ["account_id", "customer_class", "status", "final_date", "rate_code", "merged_into", "merge_effective", "late_posted"]
    out_rows = []
    crlf = set()
    for i, x in enumerate(rows):
        fam = rep.get(i)
        fd = x["final"].isoformat() if x["final"] else ""
        me = x["merge_eff"].isoformat() if x["merge_eff"] else ""
        aid = rep_id(r, x["id"]) if fam == "T1" else x["id"]
        if fam == "T3" and me:
            me = x["merge_eff"].strftime("%m/%d/%Y")
        if fam == "T10":
            crlf.add(i)
        out_rows.append([aid, x["cls"], x["status"], fd, x["code"], x["merged_into"], me, x["late"]])
    _csv_write(out / fn, hdr, out_rows, rep, r, crlf_rows=crlf,
               extra_header=["# extract: CIS next-month extract cut 2025-12-04 for forward-billing preview - not the settlement extract",
                             "# includes late-posted changes; rate codes reflect the December 1 billing migration"])


def write_dc02(X, TR, out, r):
    fn = "scada_15min_gapfill_2025-11.csv"
    rows = []
    for f in FEEDERS:
        for t in X.interval_ends:
            rows.append({"f": f, "t": t, "wh": X.gapfill[(f, t)], "ver": "v3", "st": "PUBLISHED"})
    extra = []
    for _ in range(60):
        f = r.choice(FEEDERS)
        t = r.choice(X.interval_ends)
        extra.append((f, t, "v2"))
    for _ in range(40):
        f = r.choice(FEEDERS)
        t = r.choice(X.interval_ends)
        extra.append((f, t, "SUP"))
    out_rows = list(rows)
    for f, t, kind in extra:
        idx = next(i for i, x in enumerate(out_rows) if x["f"] == f and x["t"] == t)
        if kind == "v2":
            out_rows.insert(idx, {"f": f, "t": t, "wh": int(X.gapfill[(f, t)] * Decimal(r.randint(900, 1100)) / 1000), "ver": "v2", "st": "PUBLISHED",
                                  "trap": ("T7", "superseded model version")})
        else:
            out_rows.insert(idx + 1, {"f": f, "t": t, "wh": int(X.gapfill[(f, t)] * Decimal(r.randint(900, 1100)) / 1000), "ver": "v3",
                                      "st": "SUPPRESSED", "trap": ("T6", "suppressed duplicate")})
    for k in range(30):
        t = X.interval_ends[k * 90]
        out_rows.append({"f": "F13", "t": t, "wh": r.randint(10000, 90000), "ver": "v3", "st": "PUBLISHED", "trap": ("T13", "decommissioned feeder")})
    used_bad = set()
    for f in FEEDERS:
        for t in X.interval_ends:
            rec = X.scada[(f, t)]
            if rec["q"] != "GOOD":
                used_bad.add((f, t))
    for a in X.alarms:
        if a["type"] == "COMM_FAIL" and a["raised"] >= X.interval_ends[0] - 900 and a["raised"] <= X.interval_ends[-1]:
            for t in X.interval_ends:
                if a["raised"] < t and a["cleared"] > t - 900:
                    used_bad.add((a["feeder"], t))
    sem = []
    for i, x in enumerate(out_rows):
        if "trap" in x:
            sem.append((i, x["trap"][0], "R-GAPFILL", x["trap"][1]))
        elif (x["f"], x["t"]) in used_bad and x["ver"] == "v3" and x["st"] == "PUBLISHED":
            sem.append((i, "T16", "R-GAPFILL", "authoritative only where the historian is invalid"))
    rep = TR.plan(fn, len(out_rows), sem, ["T1", "T3", "T4", "T8", "T10"], r)
    lines = ["# analytics gap-fill model output - modelled 15-minute feeder energy; NOT revenue grade",
             "# rows of the retired v2 model are kept for audit; SUPPRESSED rows were withdrawn by analytics",
             "feeder,interval_end_utc,wh_est,model_version,status"]
    for i, x in enumerate(out_rows):
        fam = rep.get(i)
        fid = feeder_variant(x["f"], r).strip() if fam == "T1" else x["f"]
        te = iso_utc(x["t"]) if fam != "T3" else iso_local_offset(x["t"])
        wh = str(x["wh"]) if fam != "T4" else '"' + thousands(str(x["wh"])) + '"'
        line = f"{fid},{te},{wh},{x['ver']},{x['st']}"
        if fam == "T10":
            line += "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def prep_dc03(X, r):
    for i, x in enumerate(X.resend_rows):
        if x.get("fixed"):
            T(X, RESEND_FILE, "T7", "R-RESEND", (x["meter"], x["b"]), "vendor re-derived value looks corrected")
        elif x.get("differs"):
            T(X, RESEND_FILE, "T16", "R-RESEND", (x["meter"], x["b"]), "value differs from the original send")
    ghosts = 0
    for i in range(0, len(X.resend_rows), 997):
        x = X.resend_rows[i]
        if x.get("rev"):
            continue
        g = dict(x)
        g["meter"] = "GHOST:" + X.new_id("KV", 7, r, 0.5)
        g["seq"] = x["seq"] + 1
        X.resend_rows.insert(i + 1, g)
        T(X, RESEND_FILE, "T13", "R-RESEND", g["meter"], "meter not in the registry")
        ghosts += 1


def write_dc04(X, TR, out, r):
    fn = "cirrus_daily_usage_2025-11.jsonl"
    rows = []
    for u in X.cirrus_usage:
        rows.append(dict(u, status="FINAL"))
    for u in r.sample(X.cirrus_usage, 30):
        other = r.choice(sorted(X.eui))
        rows.append({"eui": u["eui"], "meter": other, "period": u["period"], "kwh": u["kwh"], "status": "VOID", "trap": ("T6", "void link row")})
    for u in r.sample(X.cirrus_usage, 20):
        rows.append(dict(u, status="FINAL", rev=2, trap=("T7", "revised usage, same link")))
    for _ in range(15):
        rows.append({"eui": X.uniq(lambda: "".join(r.choice("0123456789ABCDEF") for _ in range(16))), "meter": X.new_id("KV", 7, r, 0.5), "period": r.randint(1, 6),
                     "kwh": _rand_dec(r, 10, 900), "status": "FINAL", "trap": ("T13", "device of an unregistered meter")})
    rows.sort(key=lambda x: (x["eui"], x["period"], x.get("rev", 1)))
    sem = []
    for i, x in enumerate(rows):
        if "trap" in x:
            sem.append((i, x["trap"][0], "R-CIRRUS-LINK", x["trap"][1]))
    usage_true = {}
    for m in X.eui:
        pass
    for i, x in enumerate(rows):
        if "trap" not in x and i % 211 == 0:
            sem.append((i, "T16", "R-CIRRUS-LINK", "usage figure is informational"))
    rep = TR.plan(fn, len(rows), sem, ["T1", "T4", "T8", "T10", "T1"], r)
    lines = ['{"_comment": "Cirrus device usage by period. Usage figures are vendor-computed and informational; not reconciled to MDM."}']
    for i, x in enumerate(rows):
        fam = rep.get(i)
        dev = x["eui"].lower() if fam == "T1" else x["eui"]
        kwh = fmt_dec(x["kwh"], 3) if fam != "T4" else comma_decimal(fmt_dec(x["kwh"], 3))
        if fam == "T8":
            obj = {"device_eui": dev, "meter": x["meter"], "period_no": x["period"], "usage_kwh": kwh, "state": x["status"]}
        else:
            obj = {"device": dev, "meter_id": x["meter"], "period": x["period"], "kwh": kwh, "status": x["status"]}
        if x.get("rev"):
            obj["revision"] = x["rev"]
        lines.append(json.dumps(obj, separators=(",", ":")) + ("\r" if fam == "T10" else ""))
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_dc05(X, TR, out, r):
    fn = "meter_registry_migration_wave3.xlsx"
    xw = [dict(x, status="ACTIVE") for x in X.legacy_xwalk]
    for x in r.sample([x for x in X.legacy_xwalk if x["meter"] != "RETIRED"], 25):
        xw.append({"legacy": x["legacy"], "meter": r.choice(sorted(X.meters)), "status": "SUPERSEDED", "trap": ("T7", "superseded link")})
    for x in xw:
        if x["meter"] == "RETIRED":
            x["status"] = "RETIRED"
    xw.sort(key=lambda x: (x["legacy"], x["status"]))
    attrs = X.legacy_attr
    allrows = xw + attrs
    sem = []
    for i, x in enumerate(xw):
        if "trap" in x:
            sem.append((i, x["trap"][0], "R-LEGACY-LINK", x["trap"][1]))
        elif x["status"] == "RETIRED" and i % 400 == 0:
            sem.append((i, "T13", "R-LEGACY-LINK", "retired legacy id"))
        elif x["status"] == "RETIRED" and i % 400 == 200:
            sem.append((i, "T6", "R-LEGACY-LINK", "retired legacy id"))
    for j, a in enumerate(attrs):
        if a["mult"] != X.meters[a["meter"]]["mult"] and len(sem) < 70:
            sem.append((len(xw) + j, "T16", "R-LEGACY-ATTR", "staging multiplier differs from the registry"))
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T8", "T3", "T4"], r)
    s1 = [["Staging extract - attribute columns not validated; links are maintained by the migration team"],
          ["legacy_id", "meter_id", "link_status"]]
    for i, x in enumerate(xw):
        fam = rep.get(i)
        lid = x["legacy"].lower() if fam == "T1" else x["legacy"]
        s1.append([lid, x["meter"], x["status"]])
    s2 = [["meter_id", "multiplier", "register_digits", "feeder"]]
    for j, a in enumerate(attrs):
        fam = rep.get(len(xw) + j)
        s2.append([a["meter"], a["mult"] if fam != "T4" else f"{a['mult']}:5", a["digits"], a["feeder"]])
    write_xlsx(out / fn, [("Crosswalk", s1), ("Attributes", s2)])


def write_dc06(X, TR, out, r):
    fn = "account_rate_history_restated.xlsx"
    rest = X.restated_rows
    revs = X.restated_reversals
    allrows = rest + revs
    sem = TR.match(fn, allrows, lambda x: [x["acct"]])
    base = {a: X.accounts[a]["code"] for a in X.accounts}
    for i, x in enumerate(rest):
        if x["code"] != base[x["acct"]] and i % 2 == 0:
            sem.append((i, "T16", "R-RESTATED", "restated code differs"))
    for j, x in enumerate(revs):
        if x["acct"] not in X.accounts and j % 500 == 3:
            sem.append((len(rest) + j, "T13", "R-RESTATED", "reversal of an unknown account"))
    sem.append((0, "T7", "R-RESTATED", "restated history looks newer"))
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T3", "T8", "T1"], r)
    s1 = [["PENDING REGULATORY APPROVAL - restated history is not in force"], ["account_id", "rate_code", "effective_from"]]
    for i, x in enumerate(rest):
        fam = rep.get(i)
        s1.append([rep_id(r, x["acct"]) if fam == "T1" else x["acct"], x["code"],
                   _xl_date(x["from"]) if fam != "T3" else x["from"].isoformat()])
    s2 = [["entry_id", "account_id", "reason"]]
    for j, x in enumerate(revs):
        fam = rep.get(len(rest) + j)
        s2.append([x["entry"], rep_id(r, x["acct"]) if fam == "T1" else x["acct"], x["reason"]])
    write_xlsx(out / fn, [("Restated", s1), ("Reversals", s2)])


def write_dc07(X, TR, out, r):
    fn = "rate_code_crosswalk_2026.json"
    aliases = [{"alias": legacy_alias(c), "rate_code": c, "status": "ACTIVE"} for c in ALL_CODES]
    for c in r.sample(ALL_CODES, 8):
        wrong = r.choice([x for x in RATE_CODES[CODE_CLASS[c]] if x != c])
        aliases.append({"alias": legacy_alias(c), "rate_code": wrong, "status": "RETIRED"})
    r.shuffle(aliases)
    accts = sorted(a for a in X.accounts if X.accounts[a]["cls"] != "LIT")
    for a in r.sample(accts, 5):
        if any(e["acct"] == a for e in X.early_adopters):
            continue
        acc = X.accounts[a]
        X.early_adopters.append({"acct": a, "new_code": r.choice([c for c in RATE_CODES[acc["cls"]] if c != acc["code"]]),
                                 "eff": date(2025, 11, r.randint(3, 27)), "status": "WITHDRAWN"})
        T(X, fn, "T6", "R-EARLY-ADOPTER", a, "withdrawn migration")
    migr = [dict(m, status="ACTIVE") for m in X.migrations_2026] + [dict(e, status=e.get("status", "ACTIVE")) for e in X.early_adopters]
    for _ in range(12):
        migr.append({"acct": X.new_id("AC", 8, r, 0.5), "new_code": r.choice(ALL_CODES), "eff": date(2025, 11, r.randint(3, 27)), "status": "ACTIVE"})
    migr.sort(key=lambda m: m["acct"])
    rows = [("a", x) for x in aliases] + [("m", x) for x in migr]
    sem = TR.match(fn, rows, lambda z: [z[1]["acct"]] if z[0] == "m" else [])
    for i, (k, x) in enumerate(rows):
        if k == "a" and x["status"] == "RETIRED":
            sem.append((i, "T7", "R-RATE-ALIAS", "retired alias mapping"))
        elif k == "m" and x["acct"] not in X.accounts:
            sem.append((i, "T13", "R-EARLY-ADOPTER", "migration for an unknown account"))
        elif k == "m" and x["eff"].year == 2026 and i % 300 == 1:
            sem.append((i, "T16", "R-EARLY-ADOPTER", "2026 migration not in force"))
    rep = TR.plan(fn, len(rows), sem, ["T1", "T3", "T8"], r)
    out_alias, out_mig = [], []
    for i, (k, x) in enumerate(rows):
        fam = rep.get(i)
        if k == "a":
            out_alias.append({"alias": x["alias"], "rate_code": x["rate_code"], "status": x["status"]})
            continue
        aid = rep_id(r, x["acct"]) if fam == "T1" else x["acct"]
        eff = x["eff"].isoformat() if fam != "T3" else x["eff"].strftime("%m/%d/%Y")
        if fam == "T8":
            out_mig.append({"account": aid, "to_rate_code": x["new_code"], "effective": eff, "state": x["status"]})
        else:
            out_mig.append({"account_id": aid, "new_rate_code": x["new_code"], "effective_from": eff, "status": x["status"]})
    recs = [dict(kind="legacy_alias", **a) for a in out_alias] + [dict(kind="migration", **m) for m in out_mig]
    doc = {"title": "KVEC 2026 rate code consolidation crosswalk", "consolidation_effective": "2026-01-01",
           "note": "Prepared for the 2026 tariff filing. Early adopter migrations carry their own effective dates.",
           "records": recs}
    (out / fn).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def write_dc08(X, TR, out, r):
    fn = "hes_batch_manifest_2025-11.json"
    batches = []
    graded_drift = 0
    for fn_ in READ_FILES + [RESEND_FILE]:
        n = len(X.reads[fn_]) if fn_ != RESEND_FILE else len(X.resend_rows)
        wd = X.withdrawn.get(fn_)
        drift = X.vendor_drift.get(fn_, 0)
        if r.chance(0.12) and fn_ != RESEND_FILE:
            batches.append({"file": fn_, "records": n + r.randint(41, 90), "status": "DELIVERED", "withdrawn_rows": None, "superseded": True})
            T(X, fn, "T7", "R-MANIFEST", fn_, "superseded manifest entry")
        if drift and graded_drift < 2:
            graded_drift += 1
            T(X, fn, "T16", "R-MANIFEST", fn_, "vendor count disagrees with the parsed data rows")
        batches.append({"file": fn_, "records": n + drift, "status": "PARTIALLY_WITHDRAWN" if wd else "DELIVERED",
                        "withdrawn_rows": f"{wd[0]}-{wd[1]}" if wd else None, "superseded": False})
    for k in (7, 8):
        batches.append({"file": f"aurora_reads_2025-11_p{k}.csv", "records": r.randint(5000, 5300), "status": "DELIVERED",
                        "withdrawn_rows": None, "superseded": False})
        T(X, fn, "T13", "R-MANIFEST", f"aurora_reads_2025-11_p{k}.csv", "file never delivered")
    days = X.manifest_days
    rows = [("b", b) for b in batches] + [("d", d) for d in days]
    sem = TR.match(fn, rows, lambda z: [z[1]["file"]] if z[0] == "b" else [])
    for i, (k, x) in enumerate(rows):
        if k == "b" and not x["superseded"] and x["status"] == "DELIVERED" and i % 5 == 0 \
                and not X.vendor_drift.get(x["file"]):
            sem.append((i, "T16", "R-MANIFEST", "vendor count agrees with the file"))
    rep = TR.plan(fn, len(rows), sem, ["T3", "T8", "T4"], r)
    ob, od = [], []
    for i, (k, x) in enumerate(rows):
        fam = rep.get(i)
        if k == "b":
            ob.append({"file": x["file"], "record_count": x["records"], "status": x["status"], "withdrawn_rows": x["withdrawn_rows"],
                       "superseded": x["superseded"]})
        else:
            dd = x["date"].isoformat() if fam != "T3" else x["date"].strftime("%m/%d/%Y")
            rec = x["records"] if fam != "T4" else thousands(str(x["records"]))
            if fam == "T8":
                od.append({"system": x["hes"], "day": dd, "feed": x["stream"], "file_count": x["files"], "rows": rec, "state": x["status"]})
            else:
                od.append({"hes": x["hes"], "date": dd, "stream": x["stream"], "files": x["files"], "records": rec, "status": x["status"]})
    doc = {"manifest": "head-end vendor delivery manifest (vendor side)", "period": "2025-11",
           "note": "record_count is the vendor's count of data records delivered in the file; kind=daily rows are year-to-date delivery statistics",
           "records": [dict(kind="batch", **b) for b in ob] + [dict(kind="daily", **d) for d in od]}
    (out / fn).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def write_dc09(X, TR, out, r):
    fn = "settlement_procedures_manual_rev4_draft.docx"
    rows = X.draft_schedule
    sem = []
    for i, x in enumerate(rows):
        if x.get("changed") and len(sem) < 40:
            sem.append((i, "T16", "R-DRAFT", "draft schedule row differs from revision 3"))
    errata_rows = list(X.draft_errata)
    for _ in range(4):
        errata_rows.append({"id": f"DE-{900 + _}", "table": "R", "key": X.new_id("KV", 7, r, 0.5), "value": "23:00",
                            "from": date(2025, 11, 10), "cab": f"CR-{r.randint(1000, 9999)}", "ghost": True})
    off = len(rows)
    sem2 = TR.match(fn, errata_rows, lambda e: [e["key"]])
    sem += [(off + i, f, ru, n) for i, f, ru, n in sem2]
    for i, e in enumerate(errata_rows):
        if e.get("ghost"):
            sem.append((off + i, "T13", "R-DRAFT-ERRATA", "erratum for a meter not in the registry"))
    rep = TR.plan(fn, len(rows) + len(errata_rows), sem, ["T1", "T3", "T8"], r)
    blocks = [("h", 1, "KVEC Settlement Procedures Manual - Revision 4 WORKING DRAFT"),
              ("p", "DRAFT - NOT APPROVED. Circulated to the change advisory board for review. Supersedes revision 3 on approval."),
              ("h", 2, "1. Boundary value precedence (proposed)"),
              ("p", "Approved VEE estimates take precedence over corrections; the most recent read always wins over a closer read."),
              ("h", 2, "2. Proposed feeder table"),
              ("table", ["feeder", "loss_pct"], [[f, f"{X.draft_loss[f]:.3f}"] for f in FEEDERS]),
              ("h", 2, "3. Errata index to revision 3"),
              ("p", "Each erratum takes effect only when the CAB decision for its CR number is APPROVED. Table R adds a read "
                    "schedule row (meter, read_time) from effective_from; table L replaces a feeder loss factor.")]
    et = []
    for i, e in enumerate(errata_rows):
        fam = rep.get(off + i)
        val = e["value"] if e["table"] == "R" else f"{e['value']:.3f}"
        et.append([e["id"], e["table"], rep_id(r, e["key"]) if (fam == "T1" and e["table"] == "R") else e["key"], val,
                   e["from"].isoformat() if fam != "T3" else e["from"].strftime("%m/%d/%Y"), e["cab"]])
    blocks.append(("table", ["erratum", "table", "key", "value", "effective_from", "cr"], et))
    blocks.append(("h", 2, "Appendix R (proposed restatement)"))
    t = []
    for i, x in enumerate(rows):
        fam = rep.get(i)
        t.append([rep_id(r, x["meter"]) if fam == "T1" else x["meter"], x["read_time"],
                  x["from"].isoformat() if fam != "T3" else x["from"].strftime("%m/%d/%Y")])
    blocks.append(("table", ["meter_id", "read_time", "effective_from"], t))
    write_docx(out / fn, blocks, footer_text="DRAFT rev 4 - not for operational use")


def write_dc10(X, TR, out, r):
    fn = "tariff_book_residential_2026.pdf"
    rows = sorted(X.rates_2026.items())
    lines = ["KVEC Residential Tariff Book - 2026 Filing", "Filed 2025-10-15 for rates effective 2026-01-01 (pending commission order).",
             "Section 1. Base energy rates 2026, cents per kWh.", "RATE_CODE | DATE | DAYTYPE | RATE"]
    storm = sorted(X.storm_rows, key=lambda x: (x["code"], x["from"]))
    storm_extra = [{"code": "RES-15", "from": date(2025, 11, 20), "adder": Decimal("0.41000"), "status": "APPROVED", "ghost": True}]
    allrows = [("rate", k, v) for k, v in rows] + [("storm", None, s) for s in storm + storm_extra]
    sem = TR.match(fn, allrows, lambda z: [z[2]["code"]] if z[0] == "storm" else [])
    for i, z in enumerate(allrows):
        if z[0] == "storm" and z[2].get("ghost"):
            sem.append((i, "T13", "R-STORM", "rate code that does not exist"))
        elif z[0] == "rate" and i % 450 == 5:
            sem.append((i, "T16", "R-TARIFF-2026", "2026 base rate, not in force"))
    sem.append((len(rows) // 2, "T7", "R-TARIFF-2026", "newer book looks authoritative"))
    rep = TR.plan(fn, len(allrows), sem, ["T3", "T4", "T12", "T1"], r)
    for i, z in enumerate(allrows):
        fam = rep.get(i)
        if z[0] == "rate":
            (c, d, dt), v = z[1], z[2]
            s = f"{v:.5f}" if fam != "T4" else comma_decimal(f"{v:.5f}")
            lines.append(f"{c} | {d.isoformat() if fam != 'T3' else d.strftime('%m/%d/%Y')} | {dt} | {s}")
        else:
            if i == len(rows):
                lines += ["", "Table S. Storm recovery rider (docket 25-STORM), cents per kWh, in force from EFFECTIVE_FROM.",
                          "RATE_CODE | EFFECTIVE_FROM | ADDER | STATUS"]
            s_ = z[2]
            lines.append(f"{s_['code']} | {s_['from'].isoformat()} | {s_['adder']:.5f} | {s_['status']}")
    write_pdf(out / fn, lines)


def write_dc11(X, TR, out, r):
    fn = "substation_east_monthly_report.pdf"
    rows = scada_rows(X, "east")
    relay = sorted(X.relay.items())
    relay_rows = [(k, v, "DONE") for k, v in relay]
    for k, v in relay[:3]:
        relay_rows.append(((k[0], k[1] + 900), int(v * 0.9), "CANCELLED"))
    relay_rows.sort(key=lambda z: (z[0][0], z[0][1]))
    allrows = [("r", x) for x in rows] + [("s", x) for x in relay_rows]
    sem = TR.match(fn, allrows, lambda z: [z[1][0]] if z[0] == "s" else [])
    for i, z in enumerate(allrows):
        if z[0] == "s" and z[1][2] == "CANCELLED":
            sem.append((i, "T6", "R-RELAY-TEST", "cancelled relay test"))
        elif z[0] == "r" and i % 520 == 11:
            sem.append((i, "T16", "R-EAST-REPORT", "rounded value agrees within 1 kWh"))
    sem.append((5, "T7", "R-EAST-REPORT", "formatted monthly report looks final"))
    sem.append((7, "T13", "R-EAST-REPORT", "report names feeder F06A, not a settlement feeder"))
    rep = TR.plan(fn, len(allrows), sem, ["T3", "T1", "T8", "T12"], r)
    lines = ["East Substation Monthly Report - November 2025", "Presentation copy - values rounded to whole kWh for display.",
             "Includes F06A (station service bus) for information.", "Section 1. Feeder energy per interval",
             "FEEDER | END_LOCAL | OFFSET | KWH"]
    for i, z in enumerate(allrows):
        fam = rep.get(i)
        if z[0] == "r":
            f, t = z[1]
            rec = X.scada[(f, t)]
            dt, _a, off = utc_to_local(t)
            v = str(int(rec["kwh"].quantize(Decimal(1), rounding=ROUND_HALF_EVEN))) if rec["q"] == "GOOD" else "---"
            lines.append(f"{f} | {dt.strftime('%Y-%m-%d %H:%M') if fam != 'T3' else dt.strftime('%m/%d/%Y %H:%M')} | "
                         f"{'-05:00' if off == -18000 else '-06:00'} | {v}")
        else:
            if z is allrows[len(rows)]:
                lines += ["", "Section 4. Relay-test replacement values (protection relay test injections removed)",
                          "FEEDER | INTERVAL_END_UTC | KWH | TEST_STATUS"]
            (f, t), wh, st = z[1]
            lines.append(f"{f} | {iso_utc(t)} | {Decimal(wh) / 1000:.3f} | {st}")
    write_pdf(out / fn, lines)


def write_dc12(X, TR, out, r):
    fn = "hes_ingest_debug.log"
    events = []
    t0 = local_to_utc(date(2025, 12, 1), 5, 0, 0)
    for k, e in enumerate(X.debug_echo):
        events.append(("echo", t0 + k, e))
    for q in X.quarantine:
        events.append(("quar", t0 + r.randint(0, 40000), q))
    nov_q = [q for q in X.quarantine if nov(q["date"]) or q["date"] == DEC1]
    for q in r.sample(nov_q, 4):
        X.meters.get(q["meter"])
    for _ in range(6):
        m = r.choice(sorted(X.meters))
        d = r.choice(BOUNDARY_DATES[1:])
        q = {"meter": m, "date": d, "hes": HES_CODE[X.meters[m]["hes"]], "reason": "SPIKE_RULE"}
        X.quarantine.append(dict(q, t=1))
        X.quarantine.append(dict(q, t=2, action="UNQUARANTINE"))
        events.append(("quar", t0 + 100, q))
        events.append(("unq", t0 + 30000, q))
        T(X, fn, "T7", "R-QUARANTINE", (m, bidx_of(d)), "quarantine lifted")
    for q in X.quarantine:
        q.setdefault("t", 1)
    for _ in range(5):
        q = {"meter": X.new_id("KV", 7, r, 0.5), "date": r.choice(DAYS), "hes": "AUR", "reason": "CRC"}
        events.append(("quar", t0 + r.randint(0, 40000), q))
        T(X, fn, "T13", "R-QUARANTINE", q["meter"], "unknown meter")
    events.sort(key=lambda e: e[1])
    sem = TR.match(fn, events, lambda e: [(e[2]["meter"], bidx_of(e[2]["date"])), e[2]["meter"]] if e[0] != "echo" else [])
    for i, e in enumerate(events):
        if e[0] == "echo" and i % 700 == 3:
            sem.append((i, "T16", "R-DEBUG-ECHO", "echo agrees with the file"))
    rep = TR.plan(fn, len(events), sem, ["T1", "T3", "T10", "T8"], r)
    lines = ["# hes-ingest service log (debug level). Parser echo lines are diagnostics.",
             "# Quarantine decisions are made by the ingest rules engine and are authoritative for MDM."]
    for i, (k, tt, e) in enumerate(events):
        fam = rep.get(i)
        ts = iso_utc(tt) if fam != "T3" else iso_local_offset(tt)
        if k == "echo":
            m = e["meter"]
            mid = rep_id(r, m) if fam == "T1" else m
            line = f"{ts} DEBUG parse file={e['file']} meter={mid} boundary={BOUNDARY_DATES[e['b']].isoformat()} import_kwh={e['imp']}"
        elif k == "quar":
            line = f"{ts} QUARANTINE meter={e['meter']} read_date={e['date'].isoformat()} hes={e['hes']} reason={e['reason']}"
        else:
            line = f"{ts} UNQUARANTINE meter={e['meter']} read_date={e['date'].isoformat()} hes={e['hes']} by=revenue-protection"
        if fam == "T8" and k == "echo":
            line = f"{ts}|DBG|{e['file']}|{e['meter']}|{BOUNDARY_DATES[e['b']].isoformat()}|{e['imp']}"
        if fam == "T10":
            line += "\r"
        lines.append(line)
    (out / fn).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def write_dc13(X, TR, out, r):
    fn = "dw_registry_snapshot_2025-12-03.db"
    snap = X.snapshot
    xref = [dict(x, status="ACTIVE") for x in X.xref]
    for x in r.sample([x for x in X.xref if x["meter"] in X.meters], 20):
        xref.append({"spid": x["spid"], "meter": r.choice(sorted(X.meters)), "from": x["from"], "to": x["to"], "status": "VOID",
                     "trap": ("T6", "void link")})
    xref.sort(key=lambda x: (x["spid"], x["from"]))
    log = X.snapshot_log
    allrows = [("s", x) for x in snap] + [("x", x) for x in xref] + [("l", x) for x in log]
    sem = []
    for i, (k, x) in enumerate(allrows):
        if k == "s" and x["mult"] != X.meters[x["meter"]]["mult"] and len([s for s in sem if s[1] == "T16"]) < 30:
            sem.append((i, "T16", "R-DW-SNAPSHOT", "snapshot multiplier differs"))
        elif k == "x" and "trap" in x:
            sem.append((i, x["trap"][0], "R-SPID-LINK", x["trap"][1]))
        elif k == "x" and x["meter"] not in X.meters and i % 300 == 0:
            sem.append((i, "T13", "R-SPID-LINK", "link to a retired meter"))
        elif k == "x" and x["meter"] in X.meters and "replaces" in X.meters[x["meter"]]:
            sem.append((i, "T7", "R-SPID-LINK", "service point re-pointed at an exchange"))
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T3"], r)
    s_rows, x_rows, l_rows = [], [], []
    for i, (k, x) in enumerate(allrows):
        fam = rep.get(i)
        if k == "s":
            s_rows.append((x["meter"] if fam != "T1" else x["meter"].lower(), x["account"], x["mult"], x["feeder"], x["hes"], x["as_of"].isoformat()))
        elif k == "x":
            fr = iso_utc(x["from"]) if fam != "T3" else iso_local_offset(x["from"])
            x_rows.append((x["spid"] if fam != "T1" else x["spid"].lower(), x["meter"], fr, iso_utc(x["to"]) if x["to"] else None, x["status"]))
        else:
            l_rows.append((x["seq"], x["meter"], x["change"], x["at"].isoformat()))
    l_rows.insert(0, (0, "", "SNAPSHOT_INFO informational copy of registry attributes; not the registry of record", "2025-12-03"))
    write_sqlite(out / fn, [
        ("CREATE TABLE meter_snapshot (meter_id TEXT, account_id TEXT, multiplier INTEGER, feeder TEXT, hes TEXT, as_of TEXT)",
         "INSERT INTO meter_snapshot VALUES (?,?,?,?,?,?)", s_rows),
        ("CREATE TABLE sp_meter_xref (spid TEXT, meter_id TEXT, valid_from_utc TEXT, valid_to_utc TEXT, status TEXT)",
         "INSERT INTO sp_meter_xref VALUES (?,?,?,?,?)", x_rows),
        ("CREATE TABLE snapshot_log (seq INTEGER, meter_id TEXT, change TEXT, at TEXT)",
         "INSERT INTO snapshot_log VALUES (?,?,?,?)", l_rows)])


def write_dc15(X, TR, out, r):
    fn = "customer_portal_usage_export.html"
    for d in X.disputes:
        d.setdefault("decided", d["date"] + timedelta(days=r.randint(3, 12)))
    flips = [d for d in X.disputes if nov(d["date"])][:6]
    for d in flips:
        X.disputes.append({"meter": d["meter"], "date": d["date"], "case": d["case"], "decided": d["decided"] - timedelta(days=2),
                           "outcome": "NOT UPHELD" if d["outcome"] == "UPHELD" else "UPHELD"})
        T(X, fn, "T7", "R-DISPUTE", (d["meter"], bidx_of(d["date"])), "appeal decision supersedes")
    for _ in range(4):
        X.disputes.append({"meter": X.new_id("KV", 7, r, 0.5), "date": r.choice(DAYS), "case": f"DSP-{r.randint(10000, 99999)}",
                           "decided": date(2025, 11, 28), "outcome": "UPHELD"})
        T(X, fn, "T13", "R-DISPUTE", X.disputes[-1]["meter"], "dispute for an unknown meter")
    usage = X.portal
    disp = sorted(X.disputes, key=lambda d: (d["meter"], d["date"], d["decided"]))
    allrows = [("u", u) for u in usage] + [("d", d) for d in disp]
    sem = TR.match(fn, allrows, lambda z: [(z[1]["meter"], bidx_of(z[1]["date"])), z[1]["meter"]] if z[0] == "d" else [])
    for i, (k, x) in enumerate(allrows):
        if k == "u" and i % 600 == 9:
            sem.append((i, "T16", "R-PORTAL", "portal usage close to settlement"))
    rep = TR.plan(fn, len(allrows), sem, ["T1", "T4", "T3", "T8"], r)
    html = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>Customer portal export</title></head><body>",
            "<h1>Customer portal usage export - November 2025</h1>",
            "<p>Usage shown to customers is estimated from interval data and is for customer information only.</p>",
            "<h2>Usage by period</h2>"]
    ut = []
    for i, (k, x) in enumerate(allrows):
        if k != "u":
            continue
        fam = rep.get(i)
        kwh = f"{x['kwh']:.2f}" if fam != "T4" else thousands(f"{x['kwh']:.2f}")
        ut.append([rep_id(r, x["acct"]) if fam == "T1" else x["acct"], x["period"], kwh])
    html += _html_table(["account_id", "period", "kwh"], ut)
    html.append("<h2>Read dispute decisions</h2>")
    dt_rows = []
    for i, (k, x) in enumerate(allrows):
        if k != "d":
            continue
        fam = rep.get(i)
        dt_rows.append([x["case"], rep_id(r, x["meter"]) if fam == "T1" else x["meter"],
                        x["date"].isoformat() if fam != "T3" else x["date"].strftime("%m/%d/%Y"), x["decided"].isoformat(), x["outcome"]])
    html += _html_table(["case", "meter_id", "read_date", "decided", "decision"], dt_rows)
    html.append("</body></html>")
    (out / fn).write_text("\n".join(html) + "\n", encoding="utf-8")


def write_corpus(seed, out, hidden=False):
    """Generate the whole corpus for seed into directory out; returns (X, truth, manifest). hidden=True adds the
    hidden-tier tie-break fixtures; the visible tier and the shipped environment/data use the default."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for p in out.iterdir():
        if p.is_file():
            p.unlink()
    X = build_all(seed, hidden)
    r = Rng(seed).fork("render")
    TR = Traps(X)
    # decoys that add semantic traps to X first
    prep_dc03(X, r.fork("dc03prep"))
    write_dc15(X, TR, out, r.fork("dc15"))
    write_dc12(X, TR, out, r.fork("dc12"))
    write_dc07(X, TR, out, r.fork("dc07"))
    write_dc08(X, TR, out, r.fork("dc08"))
    for k in range(6):
        write_aurora(X, TR, out, k, r.fork(f"a{k}"))
        write_borealis(X, TR, out, k, r.fork(f"b{k}"))
        write_cirrus(X, TR, out, k, r.fork(f"c{k}"))
        write_delta(X, TR, out, k, r.fork(f"d{k}"))
        write_fjord(X, TR, out, k, r.fork(f"f{k}"))
    for k in range(3):
        write_cis(X, TR, out, k, r.fork(f"e{k}"))
    write_opening(X, TR, out, r.fork("open"))
    write_master(X, TR, out, r.fork("master"))
    write_voids(X, TR, out, r.fork("voids"))
    write_corrections(X, TR, out, r.fork("corr"))
    write_north(X, TR, out, r.fork("north"))
    write_nem(X, TR, out, r.fork("nem"))
    write_vee(X, TR, out, r.fork("vee"))
    write_orders(X, TR, out, r.fork("orders"))
    write_east(X, TR, out, r.fork("east"))
    write_south(X, TR, out, r.fork("south"))
    write_west(X, TR, out, r.fork("west"))
    write_merges(X, TR, out, r.fork("merges"))
    write_inventory(X, TR, out, r.fork("inv"))
    write_burn(X, TR, out, r.fork("burn"))
    write_rate_history(X, TR, out, r.fork("rh"))
    write_fixture_audit(X, TR, out, r.fork("audit"))
    write_vee_review(X, TR, out, r.fork("veer"))
    write_ct_verif(X, TR, out, r.fork("ctv"))
    write_inspections(X, TR, out, r.fork("insp"))
    write_burn_exc(X, TR, out, r.fork("bexc"))
    write_manual(X, TR, out, r.fork("manual"))
    write_tariff_docx(X, TR, out, r.fork("tres"), "tariff_book_residential_q4.docx", ["RES"], "KVEC Tariff Book Q4 2025 - Residential")
    write_tariff_docx(X, TR, out, r.fork("tind"), "tariff_book_industrial_q4.docx", ["IND"], "KVEC Tariff Book Q4 2025 - Industrial")
    write_tariff_pdf(X, TR, out, r.fork("tcom"), "tariff_book_commercial_q4.pdf", ["SGS", "LGS"], "KVEC Tariff Book Q4 2025 - General Service")
    write_tariff_pdf(X, TR, out, r.fork("tagr"), "tariff_book_agri_lighting_q4.pdf", ["AGR", "LIT"], "KVEC Tariff Book Q4 2025 - Agricultural and Lighting")
    write_export_rider(X, TR, out, r.fork("exp"))
    write_disconnections(X, TR, out, r.fork("disc"))
    write_accuracy(X, TR, out, r.fork("acc"))
    write_rider_pdf(X, TR, out, r.fork("rider"))
    write_exemptions(X, TR, out, r.fork("exm"))
    write_batch_log(X, TR, out, r.fork("blog"))
    write_collector(X, TR, out, r.fork("coll"))
    write_alarms(X, TR, out, r.fork("alarm"))
    for dist in ("north", "east", "southwest"):
        write_registry(X, TR, out, dist, r.fork("reg" + dist))
    write_aurora_profile(X, TR, out, r.fork("ap"))
    write_cirrus_profile(X, TR, out, r.fork("cp"))
    write_fjord_profile(X, TR, out, r.fork("fp"))
    write_borealis_map(X, TR, out, r.fork("bm"))
    write_rollover(X, TR, out, r.fork("roll"))
    write_clock(X, TR, out, r.fork("clock"))
    write_delta_ini(X, TR, out, r.fork("dini"))
    write_cis_ini(X, TR, out, r.fork("cini"))
    write_scaling_ini(X, TR, out, r.fork("sini"))
    write_spec(X, TR, out, r.fork("spec"))
    serr_r = r.fork("serr")
    serr_state = serr_r.s
    write_scada_errata(X, TR, out, serr_r)
    write_known_issues(X, TR, out, r.fork("ki"))
    write_tariff_errata(X, TR, out, r.fork("terr"))
    write_rider_matrix(X, TR, out, r.fork("rmx"))
    write_mbox(X, TR, out, r.fork("mbox"))
    write_ics(X, TR, out, r.fork("ics"))
    write_dc01(X, TR, out, r.fork("dc01"))
    write_dc02(X, TR, out, r.fork("dc02"))
    write_fjord(X, TR, out, 3, r.fork("dc03"), resend=True)
    write_dc04(X, TR, out, r.fork("dc04"))
    write_dc05(X, TR, out, r.fork("dc05"))
    write_dc06(X, TR, out, r.fork("dc06"))
    write_dc09(X, TR, out, r.fork("dc09"))
    write_dc10(X, TR, out, r.fork("dc10"))
    write_dc11(X, TR, out, r.fork("dc11"))
    write_dc13(X, TR, out, r.fork("dc13"))
    write_fjord_profile(X, TR, out, r.fork("dc14"), y2026=True)
    for p in sorted(out.iterdir()):
        if p.suffix in TEXT_SUFFIXES:
            data = p.read_bytes()
            if b"\r\n" in data:
                p.write_bytes(data.replace(b"\r\n", b"\r"))
    truth = compute_truth(X)
    if hidden and _ufe_tie_fixture(X, truth, Rng(X.seed ^ 0x0FE71EB2EA)):
        again = Rng(0)
        again.s = serr_state
        write_scada_errata(X, Traps(X), out, again)
        p = out / "scada_errata_notice.md"
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\r"))
        truth = compute_truth(X)
    return X, truth, TR.entries


TEXT_SUFFIXES = {".csv", ".tsv", ".jsonl", ".json", ".xml", ".txt", ".log", ".md", ".html", ".yaml", ".toml", ".ini", ".ics", ".mbox"}


# ---------------------------------------------------------------------------
# part 5 - grading.  Both tiers are regenerated here from their seeds: the
# visible tier (SAMPLE_SEED, the shipped /app/data: byte-identical except the
# SQLite page bytes of the four .db files, whose rows are identical) and the
# hidden tier (EVAL_SEED, same file names and documented rules, fresh ids,
# values and trap placements, plus the tie-break fixtures of
# _tiebreak_fixtures and _ufe_tie_fixture, which only the hidden tier
# carries).  /app/data never exists in this container.
# ---------------------------------------------------------------------------
import hashlib
import os
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

from rewardkit import criteria, criterion

SAMPLE_SEED = int("6578686627058557206")
EVAL_SEED = int("1972138169496734964")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
OUTPUTS = ["account_settlement.csv", "meter_summary.csv", "read_resolution.csv", "interval_injection.csv",
           "lighting_deemed.csv", "daytype_calendar.csv", "feeder_balance.json", "control_report.json",
           "settlement_summary.json"]
RUN_TIMEOUT = 1500
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_LOCK = threading.Lock()
_STATE = {}

# Rows no trap family claims are split among these tests so every output byte is graded exactly once. Each share
# goes to the test whose rule decides those rows (Aurora rows to the Aurora unit rules, lighting rows to the locale
# rules and so on); the feeder balance shape has no such rule and is its own check.
OWNED = {
    "t02_unit_and_scale": [("meter_summary.csv", "A"), ("read_resolution.csv", "A")],
    "t04_locale_numerics": [("lighting_deemed.csv", None)],
    "t08_header_and_schema_drift": [("meter_summary.csv", "B"), ("read_resolution.csv", "B")],
    "t09_delimiters_and_quoting": [("control_report.json", None)],
    "feeder_balance_shape": [("feeder_balance.json", None)],
    "t10_encoding_and_line_endings": [("daytype_calendar.csv", None)],
    "t12_precision_and_rounding": [("settlement_summary.json", None)],
    "t16_decoy_authority": [("account_settlement.csv", None)],
    "dc02_scada_gapfill": [("interval_injection.csv", None)],
    "dc04_cirrus_usage_crosswalk": [("meter_summary.csv", "C"), ("read_resolution.csv", "C")],
    "dc05_legacy_crosswalk": [("meter_summary.csv", "E"), ("read_resolution.csv", "E")],
    "dc13_dw_snapshot": [("meter_summary.csv", "D"), ("read_resolution.csv", "D")],
    "dc14_fjord_profile_2026": [("meter_summary.csv", "F"), ("read_resolution.csv", "F")],
}
KEY_COLS = {"account_settlement.csv": 1, "meter_summary.csv": 1, "read_resolution.csv": 2, "interval_injection.csv": 2,
            "lighting_deemed.csv": 1, "daytype_calendar.csv": 2}
# ufe_wh, ufe_charge_cents, total_cents of account_settlement.csv: they carry the system-wide UFE share, so every
# account row check compares the row without them and t12 grades them once for every account.
UFE_COLS = (8, 9, 10)


def _mask(name, line):
    if name != "account_settlement.csv" or not line:
        return line
    return ",".join(c for i, c in enumerate(line.split(",")) if i not in UFE_COLS)


def _ufe_columns(raw):
    rows = []
    for ln in raw.decode("utf-8", errors="replace").split("\n")[1:]:
        if ln:
            cells = ln.split(",")
            rows.append((cells[0], *(cells[i] if i < len(cells) else None for i in UFE_COLS)))
    return rows


def _root_only_tests_present():
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted(command):
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _open_tree(root):
    for p in [root, *root.rglob("*")]:
        try:
            p.chmod(0o777 if p.is_dir() else 0o644)
        except OSError:
            pass


def _focus_resolver(X):
    acct_of_meter = {}
    for rows in X.registry.values():
        for row in rows:
            if row["to"] is None or row["to"] >= MONTH_START:
                acct_of_meter.setdefault(row["meter"], set()).add(row["account"])
    succ = {}
    for x in X.merges:
        succ.setdefault(x["pred"], set()).add(x["succ"])
    for x in X.late_merges:
        succ.setdefault(x["pred"], set()).add(x["succ"])
    entry_acct = {x["entry"]: x["acct"] for x in X.rate_hist}
    app_meter = {n["app"]: n["meter"] for n in X.nem}
    order_meter = {o["id"]: (o.get("old") or o.get("meter")) for o in X.orders}
    test_meter = {t["id"]: t["meter"] for t in X.acc_tests}

    ends = set(interval_ends())
    alarm_clear = {(a["feeder"], a["raised"]): a["cleared"] for a in X.alarms}

    def intervals_of(f, t):
        if t in ends:
            return {(f, iso_utc(t))}
        cleared = alarm_clear.get((f, t))
        if cleared is None:
            return set()
        return {(f, iso_utc(e)) for e in ends if t < e and cleared > e - 900}

    def accounts(m):
        out = set()
        for a in acct_of_meter.get(m, set()):
            out.add(a)
            out |= succ.get(a, set())
            for s in list(succ.get(a, set())):
                out |= succ.get(s, set())
        return out

    def resolve(key):
        out = {"meter": set(), "acct": set(), "fixture": set(), "feeder": set(), "interval": set(), "terr_date": set(),
               "code": set(), "file": set()}
        items = list(key) if isinstance(key, tuple) else [key]
        if isinstance(key, tuple) and len(key) == 2 and isinstance(key[0], str) and key[0] in TERRITORIES:
            out["terr_date"].add((key[0], key[1]))
            return out
        if isinstance(key, tuple) and len(key) == 2 and isinstance(key[0], str) and key[0] in FEEDERS:
            out["feeder"].add(key[0])
            out["interval"] |= intervals_of(key[0], key[1])
            return out
        for it in items:
            if isinstance(it, int) and it in entry_acct:
                out["acct"].add(entry_acct[it])
            if not isinstance(it, str):
                continue
            if it.startswith("KV") and it in X.meters:
                out["meter"].add(it)
                out["acct"] |= accounts(it)
            elif it.startswith("AC"):
                out["acct"].add(it)
            elif it.startswith("FX") and it in X.fixtures:
                out["fixture"].add(it)
                out["acct"].add(X.fixtures[it]["acct"])
            elif it in CODE_CLASS:
                out["code"].add(it)
            elif it in app_meter:
                out["meter"].add(app_meter[it])
                out["acct"] |= accounts(app_meter[it])
            elif it in order_meter and order_meter[it] in X.meters:
                out["meter"].add(order_meter[it])
                out["acct"] |= accounts(order_meter[it])
            elif it in test_meter:
                out["meter"].add(test_meter[it])
                out["acct"] |= accounts(test_meter[it])
            elif it.endswith((".csv", ".xml", ".jsonl", ".parquet", ".tsv", ".txt")):
                out["file"].add(it)
        return out
    return resolve


def _focus(X, truth):
    """test name -> {output name: set of expected exact lines or keys}."""
    resolve = _focus_resolver(X)
    lines = {n: truth_bytes.decode("utf-8").split("\n") for n, truth_bytes in truth.items() if n.endswith(".csv")}
    idx = {}
    for n, ls in lines.items():
        d = {}
        for ln in ls[1:]:
            if ln:
                d.setdefault(ln.split(",")[0], []).append(ln)
        idx[n] = d
    intervals = {}
    for ln in lines["interval_injection.csv"][1:]:
        if ln:
            parts = ln.split(",")
            intervals.setdefault((parts[0], parts[1]), []).append(ln)
    acc_by_code = {}
    for ln in lines["account_settlement.csv"][1:]:
        if ln:
            acc_by_code.setdefault(ln.split(",")[1], []).append(ln)
    out = {}
    for t in X.traps:
        test = DECOY_TEST.get(t["file"], FAMILY_TEST[t["family"]])
        bucket = out.setdefault(test, {})
        f = resolve(t["key"])
        for m in f["meter"]:
            bucket.setdefault("meter_summary.csv", set()).update(idx["meter_summary.csv"].get(m, []))
            bucket.setdefault("read_resolution.csv", set()).update(idx["read_resolution.csv"].get(m, []))
        for a in f["acct"]:
            bucket.setdefault("account_settlement.csv", set()).update(idx["account_settlement.csv"].get(a, []))
        for fx in f["fixture"]:
            bucket.setdefault("lighting_deemed.csv", set()).update(idx["lighting_deemed.csv"].get(fx, []))
        for fd in f["feeder"]:
            bucket.setdefault("feeder_balance.json", set()).add(fd)
        for fd, end in f["interval"]:
            bucket.setdefault("interval_injection.csv", set()).update(intervals.get((fd, end), []))
        for tr, d in f["terr_date"]:
            bucket.setdefault("daytype_calendar.csv", set()).update(x for x in idx["daytype_calendar.csv"].get(tr, []) if f",{d.isoformat()}," in x)
        for c in f["code"]:
            bucket.setdefault("account_settlement.csv", set()).update(acc_by_code.get(c, []))
        for fl in f["file"]:
            bucket.setdefault("control_report.json", set()).add(fl)
    return _disjoint(out)


def _disjoint(focus):
    """Give every focused row or object to exactly one test, the claimant with the smallest focus (ties by name),
    so no observable is paid twice; the other claimants still see it by key through the residual checks."""
    size = {t: sum(len(v) for v in per.values()) for t, per in focus.items()}
    owner = {}
    for t in sorted(focus, key=lambda name: (size[name], name)):
        for n, items in focus[t].items():
            for it in items:
                owner.setdefault((n, it), t)
    return {t: {n: {it for it in items if owner[(n, it)] == t} for n, items in per.items()} for t, per in focus.items()}


def _tier(seed, where, hidden=False):
    X, truth, manifest = write_corpus(seed, where, hidden)
    tb = {n: serialize(n, truth[n]) for n in OUTPUTS}
    ids = set(X.meters) | set(X.accounts)
    return {"dir": where, "truth": tb, "focus": _focus(X, tb), "ids": ids, "summary": truth["settlement_summary.json"],
            "hes": {m: info["hes"] for m, info in X.meters.items()}}


def _visible():
    with _LOCK:
        if "visible" not in _STATE:
            staged = APP_ROOT / "data"
            target = staged if not staged.exists() else Path(tempfile.mkdtemp(prefix="kvec-visible-"))
            _STATE["visible"] = _tier(SAMPLE_SEED, target)
            _open_tree(target)
        return _STATE["visible"]


def _hidden():
    _visible()
    with _LOCK:
        if "hidden" not in _STATE:
            root = Path(tempfile.mkdtemp(prefix="kvec-eval-"))
            _STATE["hidden"] = _tier(EVAL_SEED, root / "corpus", hidden=True)
            _open_tree(root)
        return _STATE["hidden"]


def _read_outputs(d):
    out = {}
    for n in OUTPUTS:
        try:
            out[n] = (d / n).read_bytes()
        except OSError:
            out[n] = None
    return out


def _reap_untrusted():
    """Kill every process left running as the unprivileged grading user, including ones that left our session."""
    if os.name != "posix" or os.geteuid() != 0:
        return
    try:
        uid = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid == uid:
                os.kill(int(entry.name), signal.SIGKILL)
        except (OSError, ValueError):
            continue


def _stage_program():
    """Copy the delivered transform into a root-owned directory the unprivileged user can read. An agent editor
    leaves /app/out/transform.py at mode 0600, which the dropped uid could not open."""
    source = OUT_DIR / "transform.py"
    if not source.is_file():
        return None
    stage_dir = Path(tempfile.mkdtemp(prefix="kvec-program-"))
    staged = stage_dir / "transform.py"
    shutil.copyfile(source, staged)
    staged.chmod(0o644)
    stage_dir.chmod(0o755)
    return staged


def _run(tag, input_dir, out_dir):
    try:
        staged = _stage_program()
    except OSError:
        return None
    if staged is None:
        return None
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    for p in [out_dir.parent, *out_dir.parent.parents]:
        if str(p).startswith(tempfile.gettempdir()) and p != Path(tempfile.gettempdir()):
            try:
                p.chmod(p.stat().st_mode | 0o755)
            except OSError:
                pass
    _open_tree(out_dir.parent)
    try:
        proc = subprocess.Popen(_untrusted([sys.executable, str(staged), str(input_dir), str(out_dir)]),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=str(out_dir.parent), start_new_session=True)
    except (OSError, RuntimeError):
        return None
    timed_out = False
    try:
        proc.communicate(timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        _reap_untrusted()
    if timed_out:
        proc.kill()
        try:
            proc.communicate(timeout=60)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        return None
    if proc.returncode != 0:
        return None
    return _read_outputs(out_dir)


def _snapshot(roots, skip):
    seen = {}
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            dirnames[:] = sorted(d for d in dirnames if here / d not in skip)
            for name in sorted(filenames):
                try:
                    st = (here / name).lstat()
                except OSError:
                    continue
                seen[str(here / name)] = (st.st_uid, st.st_size, st.st_mtime_ns)
            for name in dirnames:
                try:
                    seen[str(here / name)] = ((here / name).lstat().st_uid, None, None)
                except OSError:
                    continue
    return seen


def _untrusted_uid():
    if os.name == "posix" and os.geteuid() == 0:
        try:
            return pwd.getpwnam("nobody").pw_uid
        except KeyError:
            return None
    return os.geteuid()


def _escaped(before, after, protected):
    """True when the run left a file of its own outside OUT_DIR or removed one the grader put in place."""
    uid = _untrusted_uid()
    if any(k not in after and any(k == p or k.startswith(p + os.sep) for p in protected) for k in before):
        return True
    return any(v[0] == uid and before.get(k) != v for k, v in after.items())


def _runs():
    """Three runs of the delivered transform on the hidden tier: two identical, one relocated."""
    h = _hidden()
    visible_dir = _visible()["dir"]
    with _LOCK:
        if "runs" not in _STATE:
            base = Path(tempfile.mkdtemp(prefix="kvec-runs-"))
            base.chmod(0o777)
            first_out = base / "a" / "out"
            first_out.parent.mkdir()
            roots = [APP_ROOT, Path(tempfile.gettempdir()), Path("/var/tmp"), Path("/dev/shm")]
            roots = [x for x in dict.fromkeys(roots) if x.is_dir()]
            before = _snapshot(roots, {first_out})
            protected = [str(APP_ROOT), str(visible_dir), str(h["dir"].parent), str(base)]
            r1 = _run("r1", h["dir"], first_out)
            _STATE["wrote_outside"] = r1 is not None and _escaped(before, _snapshot(roots, {first_out}), protected)
            r2 = _run("r2", h["dir"], base / "b" / "out")
            moved = base / "renamed_input_dir_9"
            shutil.copytree(h["dir"], moved)
            for i, p in enumerate(sorted(moved.iterdir())):
                os.utime(p, (1500000000 + 7919 * i, 1500000000 + 7919 * i))
            _open_tree(base)
            r3 = _run("r3", moved, base / "c" / "different_out_name")
            _STATE["runs"] = (r1, r2, r3)
        return _STATE["runs"]


def _row_key(name, line):
    return tuple(line.split(",")[:KEY_COLS[name]])


def _focused_keys(tier, name):
    cache = tier.setdefault("focused", {})
    if name not in cache:
        keys = set()
        for per_test in tier["focus"].values():
            for item in per_test.get(name, ()):
                keys.add(_row_key(name, item) if name.endswith(".csv") else item)
        cache[name] = keys
    return cache[name]


def _canonical_json(raw):
    obj = json.loads(raw)
    if raw != (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8"):
        return None
    return obj


def _owned_part_ok(outputs, tier, name, hes):
    """Rows or objects another test grades by value are reduced to their key, so this check still sees their
    count and order but never their values."""
    got, want = outputs.get(name), tier["truth"][name]
    if got is None:
        return False
    if name == "settlement_summary.json":
        accounts = outputs.get("account_settlement.csv")
        return accounts is not None and got == want and _ufe_columns(accounts) == _ufe_columns(
            tier["truth"]["account_settlement.csv"])
    keys = _focused_keys(tier, name)
    if name.endswith(".json"):
        try:
            got_obj, want_obj = _canonical_json(got), json.loads(want)
            if got_obj is None:
                return False
            if name == "feeder_balance.json":
                return sorted(got_obj) == sorted(want_obj) and sorted(got_obj["feeders"]) == sorted(want_obj["feeders"])

            def batches(obj):
                return [{"file": b["file"]} if b["file"] in keys else b for b in obj["batches"]]
            return sorted(got_obj) == sorted(want_obj) and batches(got_obj) == batches(want_obj)
        except (ValueError, KeyError, TypeError, AttributeError):
            return False

    def residual(raw):
        lines = raw.decode("utf-8", errors="replace").split("\n")
        body = []
        for ln in lines[1:]:
            k = _row_key(name, ln)
            if hes is None or tier["hes"].get(ln.split(",")[0], "A") == hes:
                body.append(k if k in keys else _mask(name, ln))
        return (lines[:1] if hes in (None, "A") else []) + body
    return residual(got) == residual(want)


def _owned_ok(outputs, tier, test):
    return all(_owned_part_ok(outputs, tier, name, hes) for name, hes in OWNED[test])


def _tier_ok(outputs, tier, test):
    """A check needs only the deliverables it compares, so a missing file costs the checks that grade it; a check
    that compared nothing never passes."""
    if outputs is None:
        return False
    compared = False
    if test in OWNED:
        if not _owned_ok(outputs, tier, test):
            return False
        compared = True
    focus = tier["focus"].get(test, {})
    for n, want in focus.items():
        if not want:
            continue
        if outputs.get(n) is None:
            return False
        compared = True
        if n.endswith(".csv"):
            have = {_mask(n, ln) for ln in outputs[n].decode("utf-8", errors="replace").split("\n")}
            if not {_mask(n, ln) for ln in want} <= have:
                return False
        elif n == "feeder_balance.json":
            try:
                got = json.loads(outputs[n])["feeders"]
                exp = json.loads(tier["truth"][n])["feeders"]
            except (ValueError, KeyError, TypeError):
                return False
            if any(json.dumps(got.get(f), sort_keys=True) != json.dumps(exp.get(f), sort_keys=True) for f in want):
                return False
        elif n == "control_report.json":
            try:
                got = {b["file"]: b for b in json.loads(outputs[n])["batches"]}
                exp = {b["file"]: b for b in json.loads(tier["truth"][n])["batches"]}
            except (ValueError, KeyError, TypeError):
                return False
            if any(json.dumps(got.get(f), sort_keys=True) != json.dumps(exp.get(f), sort_keys=True) for f in want if f in exp):
                return False
    return compared


def _hard(test):
    try:
        visible = _visible()
        if not _tier_ok(_read_outputs(OUT_DIR), visible, test):
            return False
        r1, _r2, _r3 = _runs()
        return _tier_ok(r1, _hidden(), test)
    except Exception:
        return False


def _ids_in(outputs):
    found = set()
    for n in ("account_settlement.csv", "meter_summary.csv"):
        blob = outputs.get(n) or b""
        for ln in blob.decode("utf-8", errors="replace").split("\n")[1:]:
            if ln:
                found.add(ln.split(",")[0])
    return found


def _transform_source():
    try:
        return (OUT_DIR / "transform.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


# ------------------------------------------------------------------ criteria
@criterion(description="Identifier canonicalisation: every meter, account and fixture id variant resolves; visible and hidden tiers exact")
def t01_identifier_canonicalisation(workspace: Path) -> bool:
    return _hard("t01_identifier_canonicalisation")


@criterion(description="Units and scale: Wh versus kWh exports, CT multipliers, Fjord pre-multiplied values and demand conversion are exact on the rows they touch and on every remaining Aurora meter and read resolution row, whose register units follow the Aurora firmware rules")
def t02_unit_and_scale(workspace: Path) -> bool:
    return _hard("t02_unit_and_scale")


@criterion(description="Time handling: DST repeat hour, Excel serial dates, 2400 times, clock offsets and the day-type calendar are exact")
def t03_time_and_calendar(workspace: Path) -> bool:
    return _hard("t03_time_and_calendar")


@criterion(description="Locale numerics: thousands separators, decimal commas and firmware dependent separators parse exactly on the rows they touch and on every remaining lighting row, whose watts and burn hours are printed with locale separators")
def t04_locale_numerics(workspace: Path) -> bool:
    return _hard("t04_locale_numerics")


@criterion(description="Sentinels: missing-value markers per source lead to the documented estimate or gap resolution")
def t05_sentinels(workspace: Path) -> bool:
    return _hard("t05_sentinels")


@criterion(description="Voided and cancelled records: voids, holds, cancelled orders and events, withdrawn errata never apply")
def t06_voided_and_cancelled(workspace: Path) -> bool:
    return _hard("t06_voided_and_cancelled")


@criterion(description="Superseded revisions: corrections, reviews, duplicates, errata supersession and appeal decisions resolve exactly")
def t07_superseded_revisions(workspace: Path) -> bool:
    return _hard("t07_superseded_revisions")


@criterion(description="Header and schema drift: repeated headers, renamed keys, layout switches and swapped table columns are followed on the rows they touch and on every remaining Borealis meter and read resolution row, whose registers follow the channel map")
def t08_header_and_schema_drift(workspace: Path) -> bool:
    return _hard("t08_header_and_schema_drift")


@criterion(description="Delimiters and quoting: owns every control report batch object no other test grades, whose counted data rows depend on quoted newlines, embedded commas and trailing delimiters and disagree with the delivered counts")
def t09_delimiters_and_quoting(workspace: Path) -> bool:
    return _hard("t09_delimiters_and_quoting")


@criterion(description="Feeder balance shape: feeder_balance.json is canonical JSON holding exactly the feeders object with exactly the settled feeders, on the visible and hidden tiers")
def feeder_balance_shape(workspace: Path) -> bool:
    return _hard("feeder_balance_shape")


@criterion(description="Encodings and line endings: owns every day-type row, which depends on folded calendar lines and on CRLF and bare CR record terminators")
def t10_encoding_and_line_endings(workspace: Path) -> bool:
    return _hard("t10_encoding_and_line_endings")


@criterion(description="Window boundaries: snap tolerance, half-open effective windows, month edges and DTEND exclusivity are exact")
def t11_window_boundaries(workspace: Path) -> bool:
    return _hard("t11_window_boundaries")


@criterion(description="Precision and rounding: half-even rounding at the documented steps for rates, hours, energy, charges and UFE is exact on the rows it touches, on the UFE columns of every account row and on the settlement summary")
def t12_precision_and_rounding(workspace: Path) -> bool:
    return _hard("t12_precision_and_rounding")


@criterion(description="Referential integrity: removed meters, unknown devices, merged accounts and vacant premises resolve as documented")
def t13_referential_integrity(workspace: Path) -> bool:
    return _hard("t13_referential_integrity")


@criterion(description="Prose scope rules: document notes on units, cancelled orders, known issues and relay tests override table values")
def t14_prose_scope_rules(workspace: Path) -> bool:
    return _hard("t14_prose_scope_rules")


@criterion(description="Valid outliers: rollovers, resets, consumption spikes and burn-hour exceptions are kept, not cleaned")
def t15_valid_outliers(workspace: Path) -> bool:
    return _hard("t15_valid_outliers")


@criterion(description="Decoy authority: owns every account row no other test grades, each of which holds only when rows of non-authoritative files that disagree with the sources of record are left unused")
def t16_decoy_authority(workspace: Path) -> bool:
    return _hard("t16_decoy_authority")


@criterion(description="December master extract: only late-posted in-window merges are used from it")
def dc01_december_master(workspace: Path) -> bool:
    return _hard("dc01_december_master")


@criterion(description="Analytics gap-fill series: owns every interval row no other test grades, used only for invalid historian intervals and only from v3 published rows")
def dc02_scada_gapfill(workspace: Path) -> bool:
    return _hard("dc02_scada_gapfill")


@criterion(description="Fjord period 4 resend: read rows ignored, reversal records honoured")
def dc03_fjord_resend(workspace: Path) -> bool:
    return _hard("dc03_fjord_resend")


@criterion(description="Cirrus usage summary: owns every remaining Cirrus meter and read resolution row, whose device links come from that file per period while its usage figures are ignored")
def dc04_cirrus_usage_crosswalk(workspace: Path) -> bool:
    return _hard("dc04_cirrus_usage_crosswalk")


@criterion(description="Migration wave 3 workbook: owns every remaining CIS meter and read resolution row, whose legacy links come from the active crosswalk rows while the staging attributes are ignored")
def dc05_legacy_crosswalk(workspace: Path) -> bool:
    return _hard("dc05_legacy_crosswalk")


@criterion(description="Restated rate history: reversal list applied, restated codes ignored")
def dc06_restated_rate_history(workspace: Path) -> bool:
    return _hard("dc06_restated_rate_history")


@criterion(description="2026 rate crosswalk: active aliases and in-window migrations used, 2026 consolidation ignored")
def dc07_rate_crosswalk_2026(workspace: Path) -> bool:
    return _hard("dc07_rate_crosswalk_2026")


@criterion(description="Vendor manifest: the record count reported from the latest entry per file and the data rows counted in the file itself are both exact, superseded entries ignored")
def dc08_vendor_manifest(workspace: Path) -> bool:
    return _hard("dc08_vendor_manifest")


@criterion(description="Revision 4 draft: only CAB-approved errata applied, draft rules and tables ignored")
def dc09_draft_manual(workspace: Path) -> bool:
    return _hard("dc09_draft_manual")


@criterion(description="2026 residential filing: approved in-window storm rider rows applied, 2026 base rates ignored")
def dc10_tariff_2026(workspace: Path) -> bool:
    return _hard("dc10_tariff_2026")


@criterion(description="East substation PDF report: DONE relay-test replacements applied, rounded presentation table ignored")
def dc11_east_pdf_report(workspace: Path) -> bool:
    return _hard("dc11_east_pdf_report")


@criterion(description="Ingest debug log: quarantine decisions applied unless lifted, parser echo lines ignored")
def dc12_ingest_debug_log(workspace: Path) -> bool:
    return _hard("dc12_ingest_debug_log")


@criterion(description="Data warehouse snapshot: owns every remaining Delta meter and read resolution row, whose service point links come from the time-valid xref while the snapshot attributes are ignored")
def dc13_dw_snapshot(workspace: Path) -> bool:
    return _hard("dc13_dw_snapshot")


@criterion(description="Fjord 2026 profile: November pilot entries applied and planned entries ignored on the pilot rows and on every remaining Fjord meter and read resolution row, whose register values depend on the multiplier_applied flags")
def dc14_fjord_profile_2026(workspace: Path) -> bool:
    return _hard("dc14_fjord_profile_2026")


@criterion(description="Customer portal export: latest upheld dispute decisions applied, portal usage ignored")
def dc15_portal_export(workspace: Path) -> bool:
    return _hard("dc15_portal_export")


def _embeds_visible_answers():
    src = _transform_source()
    if src is None:
        return False
    v = _visible()
    hits = sum(1 for i in v["ids"] if i in src)
    s = v["summary"]
    return hits >= 25 or s["ufe_price_cents_per_kwh"] in src or str(s["total_cents"]) in src


@criterion(description="Transform source embeds visible identifiers or visible settlement totals")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened; the negative weight does the punishing.
    try:
        return _embeds_visible_answers()
    except Exception:
        return False


@criterion(description="Transform output changes when only the input or output directory names and file timestamps change")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened; the negative weight does the punishing.
    try:
        r1, r2, r3 = _runs()
        if r1 is None or r2 is None or r3 is None or r1 != r2:
            return False
        return r1 != r3
    except Exception:
        return False


@criterion(description="Transform reads the shipped corpus while settling another directory or leaves files outside its OUT_DIR")
def negative_io_outside_argument_dirs(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened; the negative weight does the punishing.
    # Visible ids carried by embedded answers are priced by negative_hardcoded_sample_answers alone.
    try:
        r1, _r2, _r3 = _runs()
        if _STATE.get("wrote_outside"):
            return True
        if r1 is None or _embeds_visible_answers():
            return False
        only_visible = _visible()["ids"] - _hidden()["ids"]
        return len(_ids_in(r1) & only_visible) >= 10
    except Exception:
        return False


@criterion(description="Two identical runs of the transform on the same input produce different bytes")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened; the negative weight does the punishing.
    try:
        r1, r2, _r3 = _runs()
        if r1 is None or r2 is None:
            return False
        return r1 != r2
    except Exception:
        return False


criteria.t01_identifier_canonicalisation(weight=5)
criteria.t02_unit_and_scale(weight=5)
criteria.t03_time_and_calendar(weight=5)
criteria.t04_locale_numerics(weight=5)
criteria.t05_sentinels(weight=5)
criteria.t06_voided_and_cancelled(weight=5)
criteria.t07_superseded_revisions(weight=5)
criteria.t08_header_and_schema_drift(weight=5)
criteria.t09_delimiters_and_quoting(weight=5)
criteria.feeder_balance_shape(weight=1)
criteria.t10_encoding_and_line_endings(weight=5)
criteria.t11_window_boundaries(weight=5)
criteria.t12_precision_and_rounding(weight=5)
criteria.t13_referential_integrity(weight=5)
criteria.t14_prose_scope_rules(weight=5)
criteria.t15_valid_outliers(weight=5)
criteria.t16_decoy_authority(weight=5)
criteria.dc01_december_master(weight=3)
criteria.dc02_scada_gapfill(weight=5)
criteria.dc03_fjord_resend(weight=5)
criteria.dc04_cirrus_usage_crosswalk(weight=5)
criteria.dc05_legacy_crosswalk(weight=5)
criteria.dc06_restated_rate_history(weight=3)
criteria.dc07_rate_crosswalk_2026(weight=3)
criteria.dc08_vendor_manifest(weight=3)
criteria.dc09_draft_manual(weight=5)
criteria.dc10_tariff_2026(weight=5)
criteria.dc11_east_pdf_report(weight=3)
criteria.dc12_ingest_debug_log(weight=5)
criteria.dc13_dw_snapshot(weight=5)
criteria.dc14_fjord_profile_2026(weight=5)
criteria.dc15_portal_export(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_io_outside_argument_dirs(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)


if __name__ == "__main__":
    write_corpus(SAMPLE_SEED, Path(sys.argv[1]) / "data" if len(sys.argv) > 1 else Path("environment/data"))
