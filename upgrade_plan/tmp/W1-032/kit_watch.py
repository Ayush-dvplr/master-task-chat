#!/usr/bin/env python3
"""kit_watch.py: watch the PL's QC kit (Input_Bundle_QC) against the saved snapshot (S7, W1-032 draft).

Standard library only. Read only, except two places it is told to write: --out (reports) and, for the
separate save command, --dest (a NEW snapshot folder). It never edits the kit or an existing snapshot.

  kit_watch.py check --kit KIT_DIR [--snapshot qc.json] [--text DIR] [--fixmap FIX_MAP.md]
                     [--rules BUILD_RULES.md ...] [--out OUT_DIR] [--json] [--diff-lines N]
      Hash every file in KIT_DIR and compare with the snapshot. For each changed file:
      a unified diff against the stored text copy (when the snapshot has one and its hash matches),
      the check ids whose lines changed (the id that owns each changed line: the nearest line above it
      that starts with an id such as DS-22, TS-23, F0a, A3), and for each id whether it appears in
      FIX_MAP.md (row numbers; those need a MAJOR or MINOR look) and in BUILD_RULES.md.
      Exit 0 unchanged, 1 changed, 2 usage or snapshot error.

  kit_watch.py save --kit KIT_DIR --dest NEW_SNAPSHOT_DIR --by "Ayush's exact words" [--head SHA]
      Run ONLY on Ayush's word. Writes NEW_SNAPSHOT_DIR/qc.json (same shape as
      knowledge/fingerprints/qc.json plus "text_dir") and NEW_SNAPSHOT_DIR/qc_text/<file> (verbatim
      copies). Refuses when NEW_SNAPSHOT_DIR already holds a qc.json, when --by is empty, or when DEST is
      inside the kit. The master then points knowledge/fingerprints/qc.json at it (moving the old one to
      archive_<head8>/ as today); this script does not do that step.

  kit_watch.py card --kit KIT_DIR [--snapshot qc.json] [--fixmap ...]
      One line for the state card (same wording family as state_card.py kit_line).
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
SKIP = {".git", "__pycache__", ".DS_Store"}
# a line that starts a check: optional list marker, checkbox, bold or table pipe, then the id
ID_START = re.compile(r"^\s*(?:[-*]\s+)?(?:\[[ xX]\]\s+)?(?:\|\s*)?(?:\*\*)?"
                      r"([A-Z]{1,3}-\d{1,3}[a-z]?|[A-Z]\d{1,2}[a-z]?|F0[a-z])(?=[\s:.,)*|]|$)")
ID_ANY = re.compile(r"\b([A-Z]{2,3}-\d{1,3}[a-z]?)\b")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def kit_files(kit):
    out = {}
    for dp, dn, fn in os.walk(kit):
        dn[:] = [d for d in dn if d not in SKIP]
        for n in fn:
            if n in SKIP or n.endswith(".pyc"):
                continue
            p = os.path.join(dp, n)
            out[os.path.relpath(p, kit)] = p
    return out


def read_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return None


def owners(lines):
    """owner[i] = the check id that owns line i (nearest id start at or above), or None."""
    cur, out = None, []
    for line in lines:
        m = ID_START.match(line)
        if m:
            cur = m.group(1)
        elif re.match(r"^#{1,6} ", line):
            cur = None  # a heading ends the previous check
        out.append(cur)
    return out


def changed_ids(old, new):
    """{id: {"old": [line numbers], "new": [line numbers], "mentioned": bool}} from a line diff."""
    res = {}
    oo, no = owners(old), owners(new)

    def add(i, side, ln):
        if i is None:
            return
        res.setdefault(i, {"old": [], "new": [], "mentioned": False})[side].append(ln)

    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for i in range(i1, i2):
            add(oo[i], "old", i + 1)
            for m in ID_ANY.finditer(old[i]):
                res.setdefault(m.group(1), {"old": [], "new": [], "mentioned": True})
        for j in range(j1, j2):
            add(no[j], "new", j + 1)
            for m in ID_ANY.finditer(new[j]):
                res.setdefault(m.group(1), {"old": [], "new": [], "mentioned": True})
    return res


def word_changes(old, new, width=8):
    """Short word level summary of each changed line: 'line N: ...context [old] -> [new] context...'."""
    out = []
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        pairs = list(zip(range(i1, i2), range(j1, j2))) if tag == "replace" else []
        for i, j in pairs:
            a, b = old[i].split(), new[j].split()
            ws = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
            spans = []  # merge word changes that sit 3 words or fewer apart
            for t, x1, x2, y1, y2 in ws.get_opcodes():
                if t == "equal":
                    continue
                if spans and x1 - spans[-1][1] <= 3 and y1 - spans[-1][3] <= 3:
                    spans[-1] = (spans[-1][0], x2, spans[-1][2], y2)
                else:
                    spans.append((x1, x2, y1, y2))
            for x1, x2, y1, y2 in spans:
                pre = " ".join(b[max(0, y1 - width):y1])
                post = " ".join(b[y2:y2 + width])
                out.append(f"line {i + 1}->{j + 1}: ...{pre} [{' '.join(a[x1:x2])}] -> [{' '.join(b[y1:y2])}] {post}...")
        extra_old = range(i1 + len(pairs), i2)
        extra_new = range(j1 + len(pairs), j2)
        for i in extra_old:
            out.append(f"line {i + 1} removed: {old[i][:160]}")
        for j in extra_new:
            out.append(f"line {j + 1} added: {new[j][:160]}")
    return out


def fixmap_rows(path):
    """{id: [row numbers]} from FIX_MAP.md table rows `| n | ID ... |` plus any other mention."""
    rows = {}
    lines = read_lines(path) or []
    for line in lines:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 3 and cells[1].isdigit():
            for m in ID_ANY.finditer(cells[2]):
                rows.setdefault(m.group(1), []).append(int(cells[1]))
    text = "\n".join(lines)
    return rows, text


def load_snapshot(path, text_dir):
    try:
        fp = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"kit_watch: cannot read snapshot {path}: {e}")
    td = text_dir or fp.get("text_dir")
    if td and not os.path.isabs(td):
        td = os.path.join(os.path.dirname(os.path.abspath(path)), td)
    return fp, td


def check(a):
    fp, tdir = load_snapshot(a.snapshot, a.text)
    snap = fp.get("files", {})
    live = kit_files(a.kit)
    fm_rows, fm_text = fixmap_rows(a.fixmap) if a.fixmap else ({}, "")
    rules_text = "\n".join("\n".join(read_lines(r) or []) for r in (a.rules or []))
    if a.out:
        for guard in (a.kit, os.path.dirname(os.path.abspath(a.snapshot)), tdir or ""):
            if guard and os.path.abspath(a.out).startswith(os.path.abspath(guard) + os.sep):
                sys.exit("kit_watch: --out may not be inside the kit or the snapshot folder")
        os.makedirs(os.path.join(a.out, "diffs"), exist_ok=True)

    files, ids = [], {}
    for name in sorted(set(snap) | set(live)):
        old_h, new_p = snap.get(name), live.get(name)
        if old_h and not new_p:
            files.append({"file": name, "status": "MISSING"})
            continue
        new_h = sha(new_p)
        if not old_h:
            new = read_lines(new_p) or []
            files.append({"file": name, "status": "NEW", "sha": new_h[:8],
                          "words": [f"line {k + 1} added: {l[:160]}" for k, l in enumerate(new) if ID_START.match(l)][:20]})
            for i, d in changed_ids([], new).items():
                e = ids.setdefault(i, {"files": set(), "old": [], "new": [], "mentioned": d["mentioned"]})
                e["files"].add(name)
                e["new"] += d["new"]
                e["mentioned"] = e["mentioned"] and d["mentioned"]
            continue
        if old_h == new_h:
            files.append({"file": name, "status": "UNCHANGED"})
            continue
        row = {"file": name, "status": "CHANGED", "old": old_h[:8], "new": new_h[:8]}
        stored = os.path.join(tdir, name) if tdir else None
        if stored and os.path.isfile(stored) and sha(stored) == old_h:
            old, new = read_lines(stored), read_lines(new_p)
            diff = list(difflib.unified_diff(old, new, f"snapshot/{name}", f"live/{name}", n=2, lineterm=""))
            row["plus"] = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            row["minus"] = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            row["diff"] = diff
            row["words"] = word_changes(old, new)
            for i, d in changed_ids(old, new).items():
                e = ids.setdefault(i, {"files": set(), "old": [], "new": [], "mentioned": d["mentioned"]})
                e["files"].add(name)
                e["old"] += d["old"]
                e["new"] += d["new"]
                e["mentioned"] = e["mentioned"] and d["mentioned"]
            if a.out:
                with open(os.path.join(a.out, "diffs", name.replace(os.sep, "__") + ".diff"), "w", encoding="utf-8") as f:
                    f.write("\n".join(diff) + "\n")
        else:
            row["note"] = ("no stored text copy for this snapshot: hash only. Store qc_text/ with each snapshot "
                           "(kit_watch.py save) so the next change gives a diff.")
        files.append(row)

    table, mentions = [], []
    for i in sorted(ids, key=lambda k: (re.sub(r"\d.*", "", k), int(re.search(r"\d+", k).group()), k)):
        e = ids[i]
        in_fm = fm_rows.get(i) or ([] if not re.search(r"\b%s\b" % re.escape(i), fm_text) else ["cited"])
        in_br = bool(re.search(r"\b%s\b" % re.escape(i), rules_text))
        owned = bool(e["old"] or e["new"])
        if not owned:
            mentions.append(i)  # only named inside a changed line of another check: listed apart
            continue
        look = "MAJOR or MINOR look (fix map)" if in_fm else ("rule look (BUILD_RULES)" if in_br else "classify")
        table.append({"id": i, "files": sorted(e["files"]), "lines_old": e["old"][:6], "lines_new": e["new"][:6],
                      "owned_change": owned, "fix_map_rows": in_fm, "build_rules": in_br, "look": look})

    changed = [f for f in files if f["status"] != "UNCHANGED"]
    summary = {"snapshot_head": fp.get("git_head", "?")[:8], "snapshot_time": fp.get("generated_ist", "?"),
               "kit": os.path.abspath(a.kit), "files": len(live), "changed": len(changed),
               "ids_changed": len(table), "ids_in_fix_map": sum(1 for t in table if t["fix_map_rows"]),
               "ids_in_build_rules": sum(1 for t in table if t["build_rules"]), "ids_named_only": mentions}
    if a.out:
        with open(os.path.join(a.out, "kit_watch.json"), "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "files": [{k: v for k, v in r.items() if k != "diff"} for r in files],
                       "ids": table}, f, indent=1)
    if a.json:
        print(json.dumps({"summary": summary, "files": [{k: v for k, v in r.items() if k != "diff"} for r in files],
                          "ids": table}, indent=1))
        return 1 if changed else 0

    print(f"KIT WATCH  {datetime.now(IST):%Y-%m-%d %H:%M} IST")
    print(f"snapshot  {a.snapshot}  head {summary['snapshot_head']}  taken {summary['snapshot_time']}  text copy {'yes' if tdir and os.path.isdir(tdir) else 'none'}")
    print(f"live kit  {summary['kit']}  files {summary['files']}")
    print()
    print("FILES")
    for r in files:
        extra = ""
        if r["status"] == "CHANGED":
            extra = f"  {r['old']} -> {r['new']}"
            extra += f"  +{r['plus']} -{r['minus']} lines" if "diff" in r else "  " + r["note"]
        elif r["status"] == "NEW":
            extra = f"  {r['sha']}"
        print(f"  {r['status']:<9} {r['file']}{extra}")
    print()
    if table:
        print("CHANGED CHECK IDS  (id | files | snapshot lines | live lines | fix map rows | BUILD_RULES | look)")
        for t in table:
            fm = ",".join(str(x) for x in t["fix_map_rows"]) or "-"
            own = ""
            print(f"  {t['id']:<7} | {','.join(t['files'])} | {t['lines_old'] or '-'} | {t['lines_new'] or '-'} | "
                  f"{fm} | {'yes' if t['build_rules'] else 'no'} | {t['look']}{own}")
        if mentions:
            print(f"  also named inside changed lines (not changed themselves): {', '.join(mentions)}")
        print()
    print("WHAT CHANGED (word level; full unified diffs in --out/diffs/)")
    for r in files:
        for w in r.get("words", []):
            print(f"  {r['file']} {w}")
    print()
    for r in files:
        if "diff" in r and a.diff_lines:
            d = r["diff"] if not a.diff_lines else r["diff"][:a.diff_lines]
            print(f"DIFF {r['file']}  ({len(r['diff'])} lines{', first %d shown' % a.diff_lines if len(r['diff']) > a.diff_lines else ''}; long lines cut at 220 characters)")
            print("\n".join(l if len(l) <= 220 else l[:220] + " [...]" for l in d))
            print()
    print(card_text(summary, changed, table))
    if a.out:
        print(f"written: {a.out}/kit_watch.json and {a.out}/diffs/")
    return 1 if changed else 0


def card_text(summary, changed, table):
    if not changed:
        return f"QC KIT: unchanged since snapshot {summary['snapshot_time'][:10]} (head {summary['snapshot_head']})"
    names = ", ".join(sorted({f['file'] for f in changed}))[:120]
    blind = [f["file"] for f in changed if f["status"] == "CHANGED" and "diff" not in f]
    ids = (f"{summary['ids_changed']} check ids, {summary['ids_in_fix_map']} in the fix map, "
           f"{summary['ids_in_build_rules']} in BUILD_RULES")
    if blind:
        ids += f"; ids unknown for {len(blind)} files (snapshot has no text copy)"
    return (f"QC KIT: CHANGED {len(changed)} files ({names}); {ids}. "
            "An agent classifies LENIENT, MINOR or MAJOR (S7); Ayush decides.")


def save(a):
    if not a.by.strip():
        sys.exit("kit_watch save: --by needs Ayush's exact words; a snapshot is saved only on his word")
    dest = os.path.abspath(a.dest)
    if dest.startswith(os.path.abspath(a.kit) + os.sep):
        sys.exit("kit_watch save: --dest may not be inside the kit")
    if os.path.exists(os.path.join(dest, "qc.json")):
        sys.exit(f"kit_watch save: {dest}/qc.json exists; a snapshot is never overwritten, pick a new folder")
    live = kit_files(a.kit)
    os.makedirs(os.path.join(dest, "qc_text"), exist_ok=True)
    files = {}
    for name, p in sorted(live.items()):
        data = open(p, "rb").read()
        files[name] = hashlib.sha256(data).hexdigest()
        out = os.path.join(dest, "qc_text", name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(data)
    fp = {"source": os.path.abspath(a.kit), "git_head": a.head or "", "generated_ist": datetime.now(IST).strftime("%Y-%m-%dT%H:%M+05:30"),
          "file_count": len(files), "files": files, "text_dir": "qc_text", "saved_on_word": a.by}
    with open(os.path.join(dest, "qc.json"), "w", encoding="utf-8") as f:
        json.dump(fp, f, indent=1)
    print(f"saved snapshot {dest}/qc.json ({len(files)} files, text copy qc_text/); on word: {a.by!r}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "card"):
        c = sub.add_parser(name)
        c.add_argument("--kit", required=True)
        c.add_argument("--snapshot", default="/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/fingerprints/qc.json")
        c.add_argument("--text", default=None, help="folder with the snapshot's text copy (default: snapshot text_dir)")
        c.add_argument("--fixmap", default=None)
        c.add_argument("--rules", nargs="*", default=[])
        c.add_argument("--out", default=None)
        c.add_argument("--json", action="store_true")
        c.add_argument("--diff-lines", type=int, default=0, help="print the first N unified diff lines per file (0 = none)")
    s = sub.add_parser("save")
    s.add_argument("--kit", required=True)
    s.add_argument("--dest", required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--head", default="")
    a = ap.parse_args()
    if not os.path.isdir(getattr(a, "kit", "")):
        print(f"kit_watch: kit folder not found: {a.kit}", file=sys.stderr)
        return 2
    if a.cmd == "save":
        return save(a)
    if a.cmd == "card":
        a.out, a.json = None, False
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check(a)
        print(buf.getvalue().strip().splitlines()[-1])
        return rc
    return check(a)


if __name__ == "__main__":
    sys.exit(main())
