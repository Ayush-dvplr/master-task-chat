"""gen_extracts.py <shipped data> <old B dir> <dest>: build hidden extracts A and B.

A: shipped corpus with every claim whose number is a multiple of 5 removed from every
claim-keyed file (a different claim population and scale).
B: shipped corpus with the claim transaction logs of the previous B extract.
Both carry one triggering row per untriggered rule (AL-27): parenthesised amount,
whole-thousands fixed-width amount, byte-identical duplicate row, cycle-window gap,
zero-capacity cell, claim with nothing to cede.
seed_development (DS-6): young accident years carry incurred above paid.
B also carries a retraction notice for a claim whose reinsurer is unresolved (AL-27).
Run with --seed-shipped to seed the shipped corpus in place first (idempotent).
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ADMISSION = "2033-01-15T00:00:00Z"


def drop_claims(d: Path, gone: set) -> None:
    def keep_line(name: str, line: str) -> bool:
        if not line.strip():
            return True
        if name.startswith(("claim_tx_", "claim_master", "retraction_notices")):
            return line.split(",")[0] not in gone
        if name.startswith("cession_q"):
            return line.split("\t")[0] not in gone
        if name.startswith("fixed_width_intake"):
            return line[0:12].strip() not in gone
        if name == "claim_adjustment_log.log":
            parts = line.split()
            return len(parts) < 2 or parts[1] not in gone
        if name.startswith(("reserve_events_", "endorsement_circulars_")):
            return json.loads(line)["claim_ref"] not in gone
        if name.startswith("endorsement_audit.log"):
            m = re.search(r"claim=(\S+)", line)
            return not m or m.group(1) not in gone
        return True

    for p in sorted(d.iterdir()):
        n = p.name
        if not n.startswith(("claim_tx_", "claim_master", "retraction_notices", "cession_q",
                             "fixed_width_intake", "claim_adjustment_log", "reserve_events_",
                             "endorsement_circulars_", "endorsement_audit.log")):
            continue
        lines = p.read_text().split("\n")
        p.write_text("\n".join(l for l in lines if keep_line(n, l)))


def triggers(d: Path, gap_cycle: str, gap_end: str, zero_cell: tuple) -> None:
    # 1 parenthesised amount in the restated column of the first admitted claim tx row
    tx = sorted(d.glob("claim_tx_*.csv"))[0]
    lines = tx.read_text().split("\n")
    for i in range(1, len(lines)):
        f = lines[i].split(",")
        if len(f) >= 8 and f[6] <= ADMISSION:
            f[7] = "(%d)" % int(f[7])
            lines[i] = ",".join(f)
            break
    tx.write_text("\n".join(lines))
    # 2 whole-thousands paid amount on the first admitted fixed-width row
    fw = d / "fixed_width_intake_h1.txt"
    lines = fw.read_text().split("\n")
    for i, line in enumerate(lines):
        if len(line) >= 92 and line[62:92].strip() <= ADMISSION:
            paid = int(line[48:62].strip())
            lines[i] = line[:48] + str(max(1000, paid // 1000 * 1000)).ljust(14) + line[62:]
            break
    fw.write_text("\n".join(lines))
    # 3 byte-identical duplicate row and 6 a claim with nothing to cede (two new claims)
    tx9 = d / "claim_tx_H09_H12.csv"
    text = tx9.read_text()
    if not text.endswith("\n"):
        text += "\n"
    dup = "CLM-00162,RE-0101,wc,AY2028,50000,50100,2032-05-11T10:00:00Z,50000\n"
    text += "CLM-00161,RE-0101,wc,AY2028,0,0,2032-05-10T10:00:00Z,0\n" + dup + dup
    tx9.write_text(text)
    cm = d / "claim_master.csv"
    text = cm.read_text()
    if not text.endswith("\n"):
        text += "\n"
    cm.write_text(text + "CLM-00161,wc,2028,EVT-9161,casualty\nCLM-00162,wc,2028,EVT-9162,casualty\n")
    # 4 cycle-window gap: the named cycle ends early, leaving a gap before the next start
    for name, col in (("cycle_marks.csv", 2),):
        p = d / name
        lines = p.read_text().split("\n")
        for i, line in enumerate(lines):
            f = line.split(",")
            if f[0] == gap_cycle:
                f[col] = gap_end
                lines[i] = ",".join(f)
        p.write_text("\n".join(lines))
    # 5 zero-capacity cell
    p = d / "layer_capacity_declarations.csv"
    lines = p.read_text().split("\n")
    for i, line in enumerate(lines):
        f = line.split(",")
        if (f[0], f[1] if len(f) > 1 else "") == zero_cell:
            f[2] = "0"
            lines[i] = ",".join(f)
    p.write_text("\n".join(lines))


def seed_development(d: Path) -> None:
    """Incurred (column 5) above paid on young development years.

    Deterministic per (claim_ref, paid, recorded_instant) so byte-identical duplicate
    rows stay identical and a second run changes nothing. Development year 0-3 rows
    are picked with probability 0.7; the case-reserve load falls with age."""
    for tx in sorted(d.glob("claim_tx_*.csv")):
        lines = tx.read_text().split("\n")
        for i in range(1, len(lines)):
            f = lines[i].split(",")
            if len(f) < 8 or not f[3].startswith("AY"):
                continue
            paid = int(f[4])
            dev = int(f[6][:4]) - int(f[3][2:])
            if paid <= 0 or dev < 0 or dev > 3:
                continue
            h = hashlib.sha256(("%s|%s|%s" % (f[0], f[4], f[6])).encode()).digest()
            if h[0] >= 179:
                continue
            load = (0.10 + 0.12 * (3 - dev)) * (0.5 + h[1] / 255.0)
            f[5] = str(paid + int(paid * load + 0.5))
            lines[i] = ",".join(f)
        tx.write_text("\n".join(lines))


def retract_unresolved(d: Path, ref: str) -> None:
    p = d / "retraction_notices.csv"
    text = p.read_text()
    if not text.endswith("\n"):
        text += "\n"
    p.write_text(text + "%s,2032-10-21T12:00:00Z,ON_HOLD\n" % ref)


B_UNRESOLVED = "CLM-00014"


def main() -> None:
    if sys.argv[1] == "--seed-shipped":
        seed_development(Path(sys.argv[2]))
        return
    shipped, old_b, dest = (Path(a) for a in sys.argv[1:4])
    a = dest / "A"
    b = dest / "B"
    for t in (a, b):
        if t.exists():
            shutil.rmtree(t)
        shutil.copytree(shipped, t)
    gone = {"CLM-%05d" % n for n in range(5, 200, 5)}
    drop_claims(a, gone)
    seed_development(a)
    triggers(a, "H10", "2032-05-16T23:59:59Z", ("cal", "H05"))
    for p in sorted(old_b.glob("claim_tx_*.csv")):
        shutil.copy(p, b / p.name)
    seed_development(b)
    triggers(b, "H16", "2032-08-16T23:59:59Z", ("gl", "H07"))
    if B_UNRESOLVED:
        retract_unresolved(b, B_UNRESOLVED)


main()
