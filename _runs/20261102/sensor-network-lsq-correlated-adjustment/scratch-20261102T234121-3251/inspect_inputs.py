import collections
import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

root = Path(sys.argv[1])
for path in sorted(root.iterdir()):
    data = path.read_bytes()
    print(f"\nFILE {path.name} bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()}")
    if path.suffix in {".db", ".sqlite"}:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for name, sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
            rows = db.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall()
            print("TABLE", sql, "rows", len(rows), "first", rows[:2], "last", rows[-2:])
            print("ALL_TEXT_DOMAINS", [sorted(set(str(r[i]) for r in rows)) if len(set(str(r[i]) for r in rows)) < 15 else f"{len(set(str(r[i]) for r in rows))} distinct" for i in range(len(rows[0]) if rows else 0)])
        db.close()
        continue
    if path.suffix in {".xlsx", ".docx"}:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                text = archive.read(name).decode()
                doc = ET.fromstring(text)
                leaves = [n.text for n in doc.iter() if n.text and n.text.strip()]
                print("MEMBER", name, "nodes", sum(1 for _ in doc.iter()))
                print("TEXT", json.dumps([v for v in leaves if not re.search(r"OB\d{5}", v)] if path.suffix == '.docx' else leaves[:28]))
        continue
    if path.suffix == ".pdf":
        for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
            try:
                stream = zlib.decompress(stream)
            except zlib.error:
                pass
            rendered = stream.decode("latin1")
            print("PDF_STREAM", '\n'.join(x for x in rendered.splitlines() if x != 'T*' and not re.search(r'OB\d{5}', x)))
        continue
    text = data.decode()
    print("LINES", len(text.splitlines()), "DASHES", text.count("\u2013") + text.count("\u2014"))
    lines = text.splitlines()
    comments = [x for x in lines if x.startswith("#")]
    print("COMMENTS", json.dumps(comments))
    body = "\n".join(x for x in lines if not x.startswith("#"))
    rows = None
    if path.suffix in {".csv", ".tsv", ".psv"}:
        reader = csv.DictReader(io.StringIO(body), delimiter={".csv": ",", ".tsv": "\t", ".psv": "|"}[path.suffix])
        rows = list(reader)
    elif path.suffix in {".jsonl", ".ndjson"}:
        rows = [json.loads(x) for x in lines if x and not x.startswith("#")]
    elif path.suffix == ".xml":
        doc = ET.fromstring(text)
        rows = [dict(n.attrib, **({"text": n.text.strip()} if n.text and n.text.strip() else {})) for n in doc.iter()]
    if rows is not None:
        print("RECORDS", len(rows), "FIRST", rows[:2], "LAST", rows[-2:])
        keys = sorted({str(k) for row in rows for k in row})
        for key in keys:
            vals = [str(row[key]) for row in rows if key in row]
            domain = sorted(set(vals))
            print("COLUMN", key, "present", len(vals), "distinct", len(domain), "domain", domain if len(domain) <= 20 else [domain[0], domain[-1]])
    else:
        print("FULL_TEXT_NONREPETITIVE", '\n'.join(x for x in lines if not (re.search(r'OB\d{5}', x) or re.fullmatch(r'\s*(district: \w+|epoch: \d+|kind: \w+|status: \w+|seq: \d+)', x))) if len(lines) > 500 else text)
    print("RULE_OR_PROSE_LINES", json.dumps([x for x in lines if re.search(r"[A-Za-z]{3} [A-Za-z]{3}", x) and not x.startswith("#") and not re.search(r'OB\d{5}', x)]))
