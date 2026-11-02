#!/usr/bin/env python3
"""Create a disposable on-disk DB inside OUT and verify draft DDL/PRAGMAs."""
import sqlite3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
db=root/'schema_dryrun.sqlite'
for p in (db,Path(str(db)+'-wal'),Path(str(db)+'-shm')):
    if p.exists(): p.unlink()
con=sqlite3.connect(db)
try:
    con.executescript((root/'schema.sql').read_text())
    print('journal_mode',con.execute('pragma journal_mode').fetchone()[0])
    print('synchronous',con.execute('pragma synchronous').fetchone()[0])
    print('busy_timeout',con.execute('pragma busy_timeout').fetchone()[0])
    print('integrity_check',con.execute('pragma integrity_check').fetchone()[0])
    print('foreign_key_check',len(con.execute('pragma foreign_key_check').fetchall()))
    print('tables',con.execute("select count(*) from sqlite_master where type='table'").fetchone()[0])
finally:
    con.close()
    for p in (db,Path(str(db)+'-wal'),Path(str(db)+'-shm')):
        if p.exists(): p.unlink()
