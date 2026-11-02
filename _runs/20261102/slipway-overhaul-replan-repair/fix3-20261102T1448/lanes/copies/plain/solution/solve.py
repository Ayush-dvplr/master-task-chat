#!/usr/bin/env python3
"""Reference solution for slipway-overhaul-replan-repair.

The shipped slwopt engine is extracted from the working papers, each
catalogued fault is repaired in place by a targeted edit to the shipped
source, the repaired tree is delivered as an archive, and the repaired engine
is then driven over the same working papers to publish the derived documents.

Nothing here reimplements the replan. The whole derivation lives in the
repaired engine, which is what the contract asks for: the deliverable is an
engine that works, not a script that happens to publish one round.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DATA = Path("/app/data")
WORK = Path("/app/project")
OUT = Path("/app/out")
NL = chr(10)


def _block(*lines):
    """One anchor, written as the lines it spans in the module."""
    return NL.join(lines) + NL


# One entry per fault: the code, the module it sits in, the anchor the shipped
# engine carries, and the anchor the stage papers put in force. DFC-01 to
# DFC-15 are the catalogued faults; DFC-16 onward are faults the stage papers
# show beside them (cycle lodgements, the crosswalk on every job identifier,
# the order of the lodgement tests, exact inverses, inert classification, the
# round weighted resource, the alias count, and declared-input errors).
# Each is asserted to match its file exactly once before it is applied, in
# order, so a later anchor may sit on text an earlier repair wrote.
REPAIRS = (
    ("DFC-01", "src/slwopt/cells.py",
     _block('            out.append(named("demand", name))'),
     _block("            for other in sorted(graph.readers_of(self.accepted, name,",
            "                                                 self.jobs, precinct)):",
            '                out.append(named("demand", other))')),
    ("DFC-02", "src/slwopt/search.py",
     _block("            [],"),
     _block('            [seen["rule|" + r]["digest"] for r in rules],')),
    ("DFC-03", "src/slwopt/cells.py",
     _block('            trail[-1] = (marker, "revalidated")',
            "            return True"),
     _block('            trail[-1] = (marker, "revalidated")',
            "            return False")),
    ("DFC-04", "src/slwopt/charge.py",
     _block("    held = dict(model.meta.get(name, {}))",
            "    held.update({field: job[field] for field in REGISTER_FIELDS})",
            "    return [held,"),
     _block("    return [{field: job[field] for field in REGISTER_FIELDS},")),
    ("DFC-05", "src/slwopt/mutate.py",
     _block('    if kind == "job_note_revision":',
            '        return [cells.named("norm", payload["job_id"])]'),
     _block('    if kind == "job_note_revision":',
            "        return []")),
    ("DFC-06", "src/slwopt/mutate.py",
     _block('    if kind == "capacity_revision":',
            '        return [cells.named("closure", name) for name in sorted(model.jobs)',
            '                if model.jobs[name]["precinct"] == payload["precinct"]] + [',
            '                    cells.named("solve", payload["precinct"])]',
            '    if kind == "carryover_revision":',
            '        return [cells.named("solve", payload["precinct"])]'),
     _block('    if kind in ("capacity_revision", "carryover_revision"):',
            '        return [cells.named("solve", payload["precinct"])]')),
    ("DFC-07", "src/slwopt/mutate.py",
     _block('    if kind == "edge_withdrawn":',
            "        return []",
            '    if kind == "edge_lodged":',
            '        return [cells.named("closure", payload["requiring_job"])]'),
     _block('    if kind in ("edge_lodged", "edge_withdrawn"):',
            '        return [cells.named("closure", payload["requiring_job"])]')),
    ("DFC-08", "src/slwopt/objective.py",
     _block("    return (total,)"),
     _block("    return (total, weighted, optional, tuple(closed))")),
    ("DFC-09", "src/slwopt/objective.py",
     _block("        if usage[pool] >= available[pool]:"),
     _block("        if usage[pool] > available[pool]:")),
    ("DFC-10", "src/slwopt/normalise.py",
     _block('        elif section == "precinct_shift_minutes" and head.startswith("PCT-"):',
            "            shifts[head] = 480"),
     _block('        elif section == "precinct_shift_minutes" and head.startswith("PCT-"):',
            "            shifts[head] = int(row[1])")),
    ("DFC-11", "src/slwopt/normalise.py",
     _block('        elif section == "pool_weights" and head in POOLS:',
            "            weights[head] = (1, 1)"),
     _block('        elif section == "pool_weights" and head in POOLS:',
            "            weights[head] = (int(row[1]), int(row[2]))")),
    ("DFC-12", "src/slwopt/search.py",
     _block("        rebate = objective.rebate_of(closed, rules, closures, base)"),
     _block("        rebate = objective.rebate_of(closed, rules, closures, base + surcharge)")),
    ("DFC-13", "src/slwopt/search.py",
     _block('        penalty = sum(charges[name]["deferral_penalty_mills"]',
            "                      for name in names if name not in closed)"),
     _block('        penalty = sum(charges[name]["deferral_penalty_mills"]',
            "                      for name in charter if name not in closed)")),
    ("DFC-14", "src/slwopt/normalise.py",
     _block('        if "RESCINDED IN FULL" in line:',
            "            holding = True",
            "            continue",
            '        if line.startswith("APPENDIX") or "IN FORCE FOR ROUND" in line:',
            "            holding = False"),
     _block('        if "IN FORCE FOR ROUND" in line:',
            "            holding = True",
            "            continue",
            '        if line.startswith("APPENDIX"):',
            "            holding = False")),
    ("DFC-15", "src/slwopt/normalise.py",
     _block('    source = "berth_job_register_current.csv"'),
     _block('    source = params["header"]["register_in_force"]')),
    ('DFC-16', 'src/slwopt/cells.py',
     _block('        for name in list(self.accepted):',
            '            if name not in self.jobs:',
            '                del self.accepted[name]',
            '            else:',
            '                self.accepted[name] = [step for step in self.accepted[name]',
            '                                       if step in self.jobs]'),
     _block('        accepted, rejected = graph.sift(self.journal, self.jobs)',
            '        self.accepted = accepted',
            '        self.edge_rejected = sorted(rejected)')),
    ('DFC-17', 'src/slwopt/cells.py',
     _block('        self.groups, group_rejected = graph.groups(root, self.jobs)'),
     _block('        self.groups, group_rejected = graph.groups(root, self.jobs, alias)')),
    ('DFC-18', 'src/slwopt/graph.py',
     _block('def groups(root, jobs):',
            '    """Stage p08. Open memberships, with a job standing in two open groups',
            '    kept by the group of the lower precedence number."""',
            '    rows = [row for row in reading.delimited(root / "exclusive_slot_groups.csv")',
            '            if row["state"] == "open" and row["member_job"] in jobs]'),
     _block('def groups(root, jobs, alias):',
            '    """Stage p08. Open memberships, with a job standing in two open groups',
            '    kept by the group of the lower precedence number."""',
            '    rows = []',
            '    for row in reading.delimited(root / "exclusive_slot_groups.csv"):',
            '        row = dict(row)',
            '        row["member_job"] = alias.get(row["member_job"], row["member_job"])',
            '        if row["state"] == "open" and row["member_job"] in jobs:',
            '            rows.append(row)')),
    ('DFC-19', 'src/slwopt/cells.py',
     _block('            if record.get("state") == "in_force":',
            '                self.rules[record["rule_id"]] = dict(record)'),
     _block('            if record.get("state") == "in_force":',
            '                record = dict(record)',
            '                for field in ("first_job", "second_job", "anchor_job"):',
            '                    if record.get(field):',
            '                        record[field] = alias.get(record[field], record[field])',
            '                self.rules[record["rule_id"]] = record')),
    ('DFC-20', 'src/slwopt/mutate.py',
     _block('    out = []',
            '    for record in sorted(rows, key=lambda r: int(r["sequence"])):'),
     _block('    alias = normalise.crosswalk(root)',
            '    out = []',
            '    for record in sorted(rows, key=lambda r: int(r["sequence"])):')),
    ('DFC-21', 'src/slwopt/mutate.py',
     '            payload[field] = value\n'
     '        out.append(',
     '            payload[field] = value\n'
     '        for field in ("job_id", "requiring_job", "required_job",\n'
     '                      "member_job"):\n'
     '            if field in payload:\n'
     '                payload[field] = alias.get(payload[field], payload[field])\n'
     '        out.append('),
    ('DFC-22', 'src/slwopt/mutate.py',
     _block('        if requiring not in model.jobs or required not in model.jobs:',
            '            return kind, payload, "rejected", "EDG-UNKNOWNJOB"',
            '        if requiring == required:',
            '            return kind, payload, "rejected", "EDG-SELF"'),
     _block('        if requiring == required:',
            '            return kind, payload, "rejected", "EDG-SELF"',
            '        if requiring not in model.jobs or required not in model.jobs:',
            '            return kind, payload, "rejected", "EDG-UNKNOWNJOB"')),
    ('DFC-23', 'src/slwopt/mutate.py',
     _block('    if kind == "edge_lodged":',
            '        model.journal[payload["edge_id"]] = {',
            '            "requiring_job": payload["requiring_job"],',
            '            "required_job": payload["required_job"],',
            '            "kind": payload.get("kind", "hard"), "status": "active"}',
            '        model.refresh_edges(model.jobs[payload["requiring_job"]]["precinct"])',
            '        return {"edge_id": payload["edge_id"]}',
            '    if kind == "edge_withdrawn":',
            '        row = model.journal[payload["edge_id"]]',
            '        back = {"edge_id": payload["edge_id"],',
            '                "requiring_job": row["requiring_job"],',
            '                "required_job": row["required_job"], "kind": row["kind"]}',
            '        row["status"] = "withdrawn"'),
     _block('    if kind == "edge_lodged":',
            '        back = {"edge_id": payload["edge_id"],',
            '                "requiring_job": payload["requiring_job"],',
            '                "required_job": payload["required_job"],',
            '                "kind": payload.get("kind", "hard")}',
            '        if payload.get("undo"):',
            '            del model.journal[payload["edge_id"]]',
            '        else:',
            '            model.journal[payload["edge_id"]] = {',
            '                "requiring_job": payload["requiring_job"],',
            '                "required_job": payload["required_job"],',
            '                "kind": payload.get("kind", "hard"), "status": "active"}',
            '            back["undo"] = True',
            '        model.refresh_edges(model.jobs[payload["requiring_job"]]["precinct"])',
            '        return back',
            '    if kind == "edge_withdrawn":',
            '        row = model.journal[payload["edge_id"]]',
            '        back = {"edge_id": payload["edge_id"],',
            '                "requiring_job": row["requiring_job"],',
            '                "required_job": row["required_job"], "kind": row["kind"]}',
            '        if payload.get("undo"):',
            '            row["status"] = payload["undo"]',
            '        else:',
            '            back["undo"] = row["status"]',
            '            row["status"] = "withdrawn"')),
    ('DFC-24', 'src/slwopt/mutate.py',
     _block('    seeds = seeds_for(model, kind, payload)'),
     _block('    seeds = seeds_for(model, kind, payload)',
            '    if not seeds:',
            '        record["classification"] = "inert"')),
    ('DFC-25', 'src/slwopt/publish.py',
     _block('        weighted += Fraction(body["weighted_resource"])'),
     _block('        for pool in body["usage"]:',
            '            top, bottom = model.params["pool_weights"][pool]',
            '            weighted += Fraction(top, bottom) * body["usage"][pool]')),
    ('DFC-26', 'src/slwopt/publish.py',
     _block('        "aliases_active": len(model.alias),'),
     _block('        "aliases_active": sum(',
            '            1 for row in graph.reading.delimited(',
            '                root / "identifier_crosswalk.tsv", graph.reading.TAB)',
            '            if row["status"] == "active"),')),
    ('DFC-27', 'src/slwopt/reading.py',
     _block('                            for cell in row.findall(WORD_NS + "tc")])',
            '    return out'),
     _block('                            for cell in row.findall(WORD_NS + "tc")])',
            '    return out',
            '',
            '',
            'def _declared(reader):',
            '    """Stop the run, naming the file, when a declared input is missing or',
            '    cannot be read in the shape its reader expects."""',
            '    def guarded(path, *rest):',
            '        if not Path(path).is_file():',
            '            raise SystemExit("a declared input is missing: " + str(path))',
            '        try:',
            '            return reader(path, *rest)',
            '        except (OSError, ValueError, KeyError, IndexError,',
            '                zipfile.BadZipFile, sqlite3.Error, ET.ParseError) as error:',
            '            raise SystemExit("a declared input is malformed: " + str(path)',
            '                             + ": " + str(error)) from error',
            '    guarded.__name__ = reader.__name__',
            '    guarded.__doc__ = reader.__doc__',
            '    return guarded',
            '',
            '',
            'text_lines = _declared(text_lines)',
            'delimited = _declared(delimited)',
            'records = _declared(records)',
            'document = _declared(document)',
            'xml_nodes = _declared(xml_nodes)',
            'table = _declared(table)',
            'sheets = _declared(sheets)',
            'pdf_lines = _declared(pdf_lines)',
            'docx_blocks = _declared(docx_blocks)')),
)


def extract():
    """Unpack the shipped engine into the working tree."""
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(DATA / "project.zip") as archive:
        archive.extractall(WORK)


def repair():
    """Apply one targeted edit per catalogued fault."""
    for code, relative, shipped, correct in REPAIRS:
        path = WORK / relative
        text = path.read_text(encoding="utf-8")
        if text.count(shipped) != 1:
            raise SystemExit("repair " + code + " does not match "
                             + relative + " exactly once")
        path.write_text(text.replace(shipped, correct), encoding="utf-8")


def deliver():
    """Write the repaired tree back out as the delivered archive."""
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = (1980, 1, 1, 0, 0, 0)
    names = sorted(str(p.relative_to(WORK)).replace(os.sep, "/")
                   for p in WORK.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(OUT / "patched_engine.zip", "w",
                         zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, (WORK / name).read_bytes())


def publish():
    """Drive the repaired engine over the working papers."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORK / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "slwopt",
                           "--data", str(DATA), "--out", str(OUT)],
                          env=env)
    if proc.returncode != 0:
        raise SystemExit("the repaired engine exited " + str(proc.returncode))


def main():
    extract()
    repair()
    deliver()
    publish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
