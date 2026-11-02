"""helios_close.cli: one-pass Q3 close builder."""
from __future__ import annotations

from .ledger import *  # noqa: F401,F403
import os
import shutil
import sys
import tempfile


def stage1_files(rows):
    files = {}
    for name in P1_FILES:
        if name == 'teams.csv':
            files[name] = teams_bytes(rows[name])
            continue
        if name == 'ledger.jsonl':
            clean = [{k: r[k] for k in LEDGER_KEYS[r['kind']]} for r in rows[name]]
        else:
            clean = [{k: r[k] for k in P1_KEYS[name]} for r in rows[name]]
        files[name] = jsonl_bytes(clean + evidence_rows(name, clean, wide=True))
    return files


def complete_files(data_dir):
    """Compute all shared values in memory and serialise each artifact once."""
    close = Close(data_dir)
    p1 = close.stage1()
    raw1 = stage1_files(p1)
    p2 = stage2(p1, raw1)
    raw2 = {name: rich_doc_bytes(name, p2[name]) for name in P2_FILES}
    p3 = stage3(p1, raw1, p2, raw2)
    raw3 = {name: rich_doc_bytes(name, p3[name]) for name in P3_FILES}
    files = dict(raw1)
    files.update(raw2)
    files.update(raw3)
    files.update(supplemental_bytes(p1, p2, p3))
    return files


def write_complete(out_dir, files):
    """Publish a complete directory only after every byte is ready.

    Entries of an existing output directory that are not artifacts of the close (the program itself, for
    example) are carried over unchanged; the earlier artifacts are replaced as one set.
    """
    out = Path(out_dir)
    parent = out.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='.helios-complete-', dir=str(parent)))
    try:
        for name in sorted(files):
            (tmp / name).write_bytes(files[name])
        if not out.exists():
            os.replace(tmp, out)
            return
        old = Path(tempfile.mkdtemp(prefix='.helios-old-', dir=str(parent)))
        old.rmdir()
        os.replace(out, old)
        kept = []
        try:
            for entry in sorted(old.iterdir()):
                if entry.name not in files:
                    os.replace(entry, tmp / entry.name)
                    kept.append(entry.name)
            os.replace(tmp, out)
        except OSError:
            for name in kept:
                if (tmp / name).exists():
                    os.replace(tmp / name, old / name)
            os.replace(old, out)
            raise
        shutil.rmtree(old)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


USAGE = 'usage: build.py DATA_DIR OUT_DIR'


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print('error: ' + USAGE, file=sys.stderr)
        return 2
    data_dir, out_dir = map(Path, argv)
    if not data_dir.is_dir() or not os.access(data_dir, os.R_OK):
        print(f'error: unreadable input directory {data_dir}', file=sys.stderr)
        return 3
    try:
        files = complete_files(data_dir)
        write_complete(out_dir, files)
    except (InputError, StageError, OSError, ValueError, KeyError, UnicodeDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
