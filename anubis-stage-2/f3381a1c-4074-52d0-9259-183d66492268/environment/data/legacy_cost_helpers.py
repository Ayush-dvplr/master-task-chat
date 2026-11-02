"""Cost helpers of the retired release planner.

Kept beside the retired planner for comparison. Nothing here is a
specification; the handbook and its addenda are.
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def rows_of_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def rows_of_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def obj_of_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sheets_of_workbook(path: Path) -> dict[str, list[dict]]:
    sheets: dict[str, list[dict]] = {}
    with zipfile.ZipFile(path) as zf:
        book = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = {rel.get("Id"): rel.get("Target")
                for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))}
        for sheet in book.find(f"{NS_MAIN}sheets"):
            part = "xl/" + str(rels[sheet.get(f"{NS_REL}id")]).lstrip("/")
            grid = []
            data = ET.fromstring(zf.read(part))
            for row in data.find(f"{NS_MAIN}sheetData") or []:
                cells = []
                for cell in row:
                    inline = cell.find(f"{NS_MAIN}is/{NS_MAIN}t")
                    value = cell.find(f"{NS_MAIN}v")
                    cells.append((inline.text or "") if inline is not None
                                 else ((value.text or "") if value is not None else ""))
                grid.append(cells)
            header = grid[0] if grid else []
            sheets[sheet.get("name")] = [dict(zip(header, line))
                                         for line in grid[1:]]
    return sheets


def number(raw: object, fallback: int = 0) -> int:
    """Read a count out of a cell. Decimal points are tolerated by truncation."""
    text = str(raw).strip().replace("_", "")
    if not text:
        return fallback
    match = re.match(r"^-?\d+", text)
    return int(match.group(0)) if match else fallback


def blended_cost(base: int, pairs: list[tuple[int, int]]) -> int:
    """Scale a base cost by every fraction at once and round at the end."""
    value = float(base)
    for num, den in pairs:
        if den:
            value = value * num / den
    return int(value + 0.5)


def pdf_lines(path: Path) -> list[str]:
    raw = path.read_bytes().decode("latin-1")
    return [m.group(1) for m in re.finditer(r"\((.*?)\)\s*Tj", raw, re.S)]


def docx_rows(path: Path) -> list[list[str]]:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    out = []
    for tr in doc.iter(f"{ns}tr"):
        out.append(["".join(t.text or "" for t in tc.iter(f"{ns}t"))
                    for tc in tr.iter(f"{ns}tc")])
    return out
