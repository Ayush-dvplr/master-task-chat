"""Readers for every shape the working papers come in.

Nothing here interprets a paper. Each function hands back rows, records or
lines exactly as the file holds them, and the stages above decide what they
mean.
"""
import json
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

TAB = "\t"
PIPE = "|"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def text_lines(path):
    return Path(path).read_text(encoding="utf-8").splitlines()


def delimited(path, sep=","):
    """Rows of a delimited file as dictionaries keyed by the header line."""
    rows = [line for line in text_lines(path) if line.strip() != ""]
    if not rows:
        return []
    header = rows[0].split(sep)
    return [dict(zip(header, line.split(sep))) for line in rows[1:]]


def records(path):
    """One json object per line."""
    out = []
    for line in text_lines(path):
        if line.strip():
            out.append(json.loads(line))
    return out


def document(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def xml_nodes(path, tag):
    root = ET.parse(str(path)).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


def table(path, name):
    connection = sqlite3.connect(str(path))
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM " + name)
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def _column(reference):
    index = 0
    for ch in reference:
        if not ch.isalpha():
            break
        index = index * 26 + (ord(ch.upper()) - 64)
    return index


def sheets(path):
    """Every sheet of a workbook as a mapping of name to row lists."""
    with zipfile.ZipFile(path) as archive:
        pool = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root:
                pool.append("".join(node.text or "" for node in item.iter()
                                    if node.tag.endswith("}t")))
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        names = [node.attrib.get("name") for node in book.iter()
                 if node.tag.endswith("}sheet")]
        out = {}
        for position, name in enumerate(names, start=1):
            member = "xl/worksheets/sheet" + str(position) + ".xml"
            if member not in archive.namelist():
                continue
            grid = ET.fromstring(archive.read(member))
            rows = []
            for row in grid.iter():
                if not row.tag.endswith("}row"):
                    continue
                cells = {}
                width = 0
                for cell in row:
                    if not cell.tag.endswith("}c"):
                        continue
                    index = _column(cell.attrib.get("r", "A1"))
                    held = ""
                    for value in cell:
                        if value.tag.endswith("}v"):
                            held = value.text or ""
                    if cell.attrib.get("t") == "s" and held != "":
                        held = pool[int(held)]
                    cells[index] = held
                    width = max(width, index)
                rows.append([cells.get(i, "") for i in range(1, width + 1)])
            out[name] = rows
        return out


def pdf_lines(path):
    """The text lines of a board minute."""
    raw = Path(path).read_bytes()
    out = []
    depth = 0
    held = []
    escaped = False
    for position in range(len(raw)):
        ch = raw[position:position + 1]
        if depth == 0:
            if ch == b"(":
                depth = 1
                held = []
            continue
        if escaped:
            held.append(ch)
            escaped = False
        elif ch == b"\\":
            escaped = True
        elif ch == b"(":
            depth += 1
            held.append(ch)
        elif ch == b")":
            depth -= 1
            if depth == 0:
                out.append(b"".join(held).decode("latin-1"))
            else:
                held.append(ch)
        else:
            held.append(ch)
    return out


def docx_blocks(path):
    """Paragraphs and table rows of a directive, in document order."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = None
    for node in root:
        if node.tag == WORD_NS + "body":
            body = node
    out = []
    if body is None:
        return out
    for node in body:
        if node.tag == WORD_NS + "p":
            out.append("".join(t.text or "" for t in node.iter(WORD_NS + "t")))
        elif node.tag == WORD_NS + "tbl":
            for row in node.findall(WORD_NS + "tr"):
                out.append(["".join(t.text or "" for t in cell.iter(WORD_NS + "t"))
                            for cell in row.findall(WORD_NS + "tc")])
    return out


def _declared(reader):
    """Stop the run, naming the file, when a declared input is missing or
    cannot be read in the shape its reader expects."""
    def guarded(path, *rest):
        if not Path(path).is_file():
            raise SystemExit("a declared input is missing: " + str(path))
        try:
            return reader(path, *rest)
        except (OSError, ValueError, KeyError, IndexError,
                zipfile.BadZipFile, sqlite3.Error, ET.ParseError) as error:
            raise SystemExit("a declared input is malformed: " + str(path)
                             + ": " + str(error)) from error
    guarded.__name__ = reader.__name__
    guarded.__doc__ = reader.__doc__
    return guarded


text_lines = _declared(text_lines)
delimited = _declared(delimited)
records = _declared(records)
document = _declared(document)
xml_nodes = _declared(xml_nodes)
table = _declared(table)
sheets = _declared(sheets)
pdf_lines = _declared(pdf_lines)
docx_blocks = _declared(docx_blocks)
