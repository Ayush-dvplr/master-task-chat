"""Exact arithmetic, canonical serialisation and the parameter layer.

Every published whole quantity is an integer in the unit its stage names and
every published ratio carries twelve decimal places. Rounding is half away
from zero on an exact rational and happens only where a stage paper puts it.
Binary floating point never enters the derivation.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from . import reading

PLACES = 12
SCALE = 10 ** PLACES
POOLS = ["berth_quarter_days", "crane_lifts", "crew_minutes"]
NEWLINE = chr(10)


def half_up(value):
    """Nearest whole number, halves away from zero, on an exact rational."""
    share = Fraction(value)
    top, bottom = share.numerator, share.denominator
    if bottom == 1:
        return top
    if top >= 0:
        return (2 * top + bottom) // (2 * bottom)
    return -((2 * (-top) + bottom) // (2 * bottom))


def ratio(value):
    """Twelve decimal places, half away from zero, never a negative zero."""
    scaled = half_up(Fraction(value) * SCALE)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, part = divmod(scaled, SCALE)
    out = sign + str(whole) + "." + str(part).rjust(PLACES, "0")
    if out == "-0." + "0" * PLACES:
        return "0." + "0" * PLACES
    return out


def ratio_of(top, bottom):
    if int(bottom) == 0:
        return ratio(0)
    return ratio(Fraction(int(top), int(bottom)))


def tight(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def laid_out(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + NEWLINE


def digest(obj):
    return hashlib.sha256(tight(obj).encode("utf-8")).hexdigest()


def digest_of_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_of(value):
    """A cell hands back its own copy, so a stage that walks over the value it
    was given leaves the stored value where it stands."""
    return json.loads(json.dumps(value))


def amount(text):
    """One amount, however the desk wrote it, as whole mills."""
    raw = str(text).strip().replace(",", "")
    if raw == "":
        return 0
    parts = raw.split()
    number = parts[0]
    unit = parts[1].lower() if len(parts) > 1 else "mills"
    if unit == "gbp":
        if "." in number:
            whole, part = number.split(".", 1)
            return int(whole) * 1000 + int((part + "000")[:3])
        return int(number) * 1000
    if "." in number:
        whole, part = number.split(".", 1)
        if int(part) != 0:
            raise ValueError("an amount in mills carries no fraction")
        return int(whole)
    return int(number)


def _live_sheet(root, header):
    """The sheet whose own key cell carries the round header cell. The name
    the sheet goes under and the position it stands at settle nothing."""
    book = reading.sheets(root / "yard_parameter_workbook.xlsx")
    wanted = str(header["workbook_round_cell"])
    for name in sorted(book):
        rows = book[name]
        for row in rows:
            if row and str(row[0]) == "sheet_key":
                if len(row) > 1 and str(row[1]) == wanted:
                    return rows
                break
    raise SystemExit("no workbook sheet carries the round key cell")


def workbook(root, header):
    """The shift lengths and the pool weights, which stand in no other paper."""
    rows = _live_sheet(root, header)
    shifts = {}
    weights = {}
    section = ""
    for row in rows:
        if not row:
            continue
        head = str(row[0])
        if head == "section":
            section = str(row[1]) if len(row) > 1 else ""
        elif section == "precinct_shift_minutes" and head.startswith("PCT-"):
            shifts[head] = int(row[1])
        elif section == "pool_weights" and head in POOLS:
            weights[head] = (int(row[1]), int(row[2]))
    if sorted(weights) != sorted(POOLS):
        raise SystemExit("the live workbook sheet carries no pool weights")
    return shifts, weights


def memo(root, index, classes):
    """The deferral rates, the store retention and the charge ceiling, which
    stand in no other paper. Only the sitting in force is read; a sitting the
    memo marks as rescinded settles nothing."""
    holding = False
    rates = {}
    retention = 0
    ceiling = 0
    for line in reading.pdf_lines(root / "yard_board_memo.pdf"):
        stripped = line.strip()
        if stripped.startswith("SITTING"):
            holding = ("RESCINDED" not in stripped
                       and "IN FORCE FOR ROUND " + str(index) in stripped)
            continue
        if stripped.startswith("APPENDIX"):
            holding = False
        if not holding:
            continue
        words = stripped.split()
        if len(words) >= 3 and words[0] == "class" and words[1] in classes:
            rates[words[1]] = int(words[2])
        if "derived entries" in line:
            retention = int([w for w in words if w.isdigit()][0])
        if "a charge above" in line:
            ceiling = int([w for w in words if w.isdigit()][0])
    if len(rates) != len(classes) or retention <= 0 or ceiling <= 0:
        raise SystemExit("the board memo did not settle the round parameters")
    return rates, retention, ceiling


def vocabulary(root):
    """The closed set of classes this round recognises."""
    return [row["class"] for row
            in reading.delimited(root / "priority_class_vocabulary.csv")
            if row["state"] == "in_force"]


def parameters(root):
    """Stage p01. Every control value the round stands on."""
    header = reading.document(root / "round_header.json")
    index = int(header["round_index"])
    classes = vocabulary(root)
    shifts, weights = workbook(root, header)
    rates, retention, ceiling = memo(root, index, classes)

    multipliers = {}
    for row in reading.delimited(root / "class_rate_register.csv"):
        if row["state"] != "in_force" or int(row["effective_round"]) > index:
            continue
        held = multipliers.get(row["class"])
        if held is None or int(row["effective_round"]) >= held[0]:
            multipliers[row["class"]] = (int(row["effective_round"]),
                                         int(row["multiplier_bp"]))

    licences = {}
    for row in reading.delimited(root / "licence_validity_register.csv"):
        licences[row["licence_code"]] = row

    precincts = [node["code"] for node
                 in reading.xml_nodes(root / "yard_topology.xml", "precinct")]
    return {"header": header, "round_index": index,
            "round_key": header["round_key"],
            "shift_minutes": shifts, "pool_weights": weights,
            "deferral_rate": rates, "retention": retention,
            "ceiling": ceiling,
            "class_bp": {k: v[1] for k, v in multipliers.items()},
            "licences": licences, "precincts": precincts}


def crosswalk(root):
    """The active rows of the crosswalk, and how many of them there are. A
    row whose status is not active maps nothing."""
    out = {}
    active = 0
    for row in reading.delimited(root / "identifier_crosswalk.tsv", reading.TAB):
        if row["status"] == "active":
            out[row["legacy_id"]] = row["canonical_id"]
            active += 1
    return out, active


def register(root, params, alias):
    """Stage p01. The rows in force out of the register the header names."""
    index = params["round_index"]
    held = {}
    source = params["header"]["register_in_force"]
    for row in reading.delimited(root / source):
        name = alias.get(row["job_id"], row["job_id"])
        if row["state"] not in ("sealed", "withdrawn"):
            continue
        if int(row["sealed_round"]) > index:
            continue
        standing = held.get(name)
        if standing is None or int(row["revision"]) > int(standing["revision"]):
            held[name] = dict(row, job_id=name)
    jobs = {}
    aside = []
    for name in sorted(held):
        row = held[name]
        if row["state"] == "withdrawn":
            aside.append((name, "JOB-WITHDRAWN", row["precinct"]))
        elif row["precinct"] not in params["precincts"]:
            aside.append((name, "JOB-NOPRECINCT", row["precinct"]))
        else:
            jobs[name] = row
    drafted = set()
    for row in reading.delimited(root / source):
        name = alias.get(row["job_id"], row["job_id"])
        if name not in held:
            drafted.add(name)
    for name in sorted(drafted):
        aside.append((name, "JOB-DRAFTONLY", ""))
    return jobs, aside
