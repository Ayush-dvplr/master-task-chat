#!/usr/bin/env python3
"""Reference solution for 4da82574-5e37-514d-aba2-a86b179fb55a.

The shipped bcrep package is extracted from the working papers, each
catalogued defect is repaired in place by a targeted edit to the shipped
source, the repaired tree is delivered as an archive, and the repaired package
is then driven over the same working papers to publish the derived documents.

Nothing here reimplements the replay. The whole derivation lives in the
repaired package, which is what the contract asks for: the deliverable is a
package that works, not a script that happens to publish one epoch.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

DATA = Path("/app/data")
WORK = Path("/app/project")
OUT = Path("/app/out")
NS_SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

# The stage each catalogued defect sits in, keyed by defect code. The closing
# report names the stage beside every repair.
STAGE_OF_DEFECT = {
    "DFC-01": "r06", "DFC-02": "r09", "DFC-03": "r12", "DFC-04": "r10",
    "DFC-05": "r06", "DFC-06": "r05", "DFC-07": "r03", "DFC-08": "r03",
    "DFC-09": "r07", "DFC-10": "r10", "DFC-11": "r10", "DFC-12": "r11",
    "DFC-13": "r02", "DFC-14": "r12", "DFC-15": "r01", "DFC-16": "r01",
    "DFC-17": "r12", "DFC-18": "r07", "DFC-19": "r04", "DFC-20": "r10",
    "DFC-21": "r04", "DFC-22": "r03",
}

# The paper that puts the correct reading in force for each catalogued defect.
# The report names it beside the repair, so the diagnosis is traceable back to
# the working papers rather than resting on the edit alone.
PAPER_OF_DEFECT = {
    "DFC-01": "spec_stage_r06_replay_window.md",
    "DFC-02": "spec_stage_r09_compensation_targets.md",
    "DFC-03": "custody_board_memo.pdf",
    "DFC-04": "compensation_policy.toml",
    "DFC-05": "spec_stage_r06_replay_window.md",
    "DFC-06": "spec_stage_r05_checkpoint_restoration.md",
    "DFC-07": "event_kind_ranks.csv",
    "DFC-08": "row_provenance_ledger.csv",
    "DFC-09": "precedence_directive.docx",
    "DFC-10": "precedence_directive.docx",
    "DFC-11": "rounding_and_arithmetic_policy.yaml",
    "DFC-12": "custody_parameter_workbook.xlsx",
    "DFC-13": "revision_precedence.toml",
    "DFC-14": "precedence_directive.docx",
    "DFC-15": "spec_stage_r01_unit_normalisation.md",
    "DFC-16": "custody_board_memo.pdf",
    "DFC-17": "eligibility_predicates.csv",
    "DFC-18": "spec_stage_r07_dependency_closure.md",
    "DFC-19": "output_schema_reference.md",
    "DFC-20": "spec_stage_r10_compensation_effects.md",
    "DFC-21": "spec_stage_r04_checkpoint_selection.md",
    "DFC-22": "data_lineage.md",
}
NL = chr(10)
DQ = chr(34)


def _ln(text):
    """One physical line of an anchor, written as it stands in the module."""
    return text


def _block(*lines):
    """One anchor, written as the lines it spans."""
    return NL.join(lines) + NL


# One entry per catalogued defect: the module it sits in, the anchor the
# shipped package carries, and the anchor the stage papers put in force. Each
# is asserted to match its file exactly once before it is applied.
REPAIRS = (
    ("DFC-01", "src/bcrep/window.py",
     _block(_ln("    window_start = max(int(start), int(watermark))")),
     _block(_ln("    window_start = max(int(start), int(watermark) + 1)"))),
    ("DFC-02", "src/bcrep/replay.py",
     _block(_ln("        if str(rec[" + DQ + "kind" + DQ + "]).strip() == " + DQ + "compensate" + DQ + ":"),
            _ln("            link = ctx[" + DQ + "links" + DQ + "][rec[" + DQ + "event_id" + DQ + "]]"),
            _ln("            named = ctx[" + DQ + "by_id" + DQ + "][link[" + DQ + "target_event_id" + DQ + "].strip()]"),
            _ln("            if int(named[" + DQ + "position" + DQ + "]) < window_start:"),
            _ln("                quarantine.append({" + DQ + "event_id" + DQ + ": rec[" + DQ + "event_id" + DQ + "],"),
            _ln("                                   " + DQ + "position" + DQ + ": p,"),
            _ln("                                   " + DQ + "stage" + DQ + ": " + DQ + "r09" + DQ + ","),
            _ln("                                   " + DQ + "reason_code" + DQ + ": " + DQ + "CMP-NOTARGET" + DQ + ","),
            _ln("                                   " + DQ + "detail" + DQ + ": str(rec[" + DQ + "kind" + DQ + "])})"),
            _ln("                continue"),
            _ln("            compensation.apply_compensation(ctx, state, rec, register, order)"),
            _ln("            continue")),
     _block(_ln("        if str(rec[" + DQ + "kind" + DQ + "]).strip() == " + DQ + "compensate" + DQ + ":"),
            _ln("            compensation.apply_compensation(ctx, state, rec, register, order)"),
            _ln("            continue"))),
    ("DFC-03", "src/bcrep/replay.py",
     _block(_ln("        ceiling = 1")),
     _block(_ln("        ceiling = int(ctx[" + DQ + "params" + DQ + "][" + DQ + "round_ceiling" + DQ + "])"))),
    ("DFC-04", "src/bcrep/compensation.py",
     _block(_ln("    state[" + DQ + "counters" + DQ + "][" + DQ + "reversed_cu" + DQ + "] += reversed_cu")),
     _block(_ln("    counter = ctx[" + DQ + "params" + DQ + "][" + DQ + "counter_map" + DQ + "][kind]"),
            _ln("    state[" + DQ + "counters" + DQ + "][counter] -= reversed_cu"),
            _ln("    state[" + DQ + "counters" + DQ + "][kind + " + DQ + "s" + DQ + "] -= 1"),
            _ln("    state[" + DQ + "counters" + DQ + "][" + DQ + "reversed_cu" + DQ + "] += reversed_cu"))),
    ("DFC-05", "src/bcrep/window.py",
     _block(_ln("    positions = [p for p in range(window_start, min(window_end, total) + 1)]")),
     _block(_ln("    positions = [p for p in range(window_start, min(window_end, total + 1))]"))),
    ("DFC-06", "src/bcrep/derived.py",
     _block(_ln("    state[" + DQ + "balances" + DQ + "] = body[" + DQ + "balances" + DQ + "]"),
            _ln("    state[" + DQ + "allotments" + DQ + "] = body[" + DQ + "allotments" + DQ + "]")),
     _block(_ln("    state[" + DQ + "balances" + DQ + "] = dict(body[" + DQ + "balances" + DQ + "])"),
            _ln("    state[" + DQ + "allotments" + DQ + "] = {k: dict(v) for k, v in body[" + DQ + "allotments" + DQ + "].items()}"))),
    ("DFC-07", "src/bcrep/ordering.py",
     _block(_ln("    events.sort(key=lambda r: (int(r[" + DQ + "sequence" + DQ + "]), int(r[" + DQ + "stamp" + DQ + "])))")),
     _block(_ln("    events.sort(key=lambda r: (int(r[" + DQ + "sequence" + DQ + "]), int(r[" + DQ + "stamp" + DQ + "]),"),
            _ln("                               int(r[" + DQ + "rank" + DQ + "]), str(r[" + DQ + "tiebreak" + DQ + "]),"),
            _ln("                               str(r[" + DQ + "event_id" + DQ + "])))"))),
    ("DFC-08", "src/bcrep/ordering.py",
     _block(_ln("        source = str(rec.get(" + DQ + "source" + DQ + ") or " + DQ + DQ + ").strip()")),
     _block(_ln("        source = str(rec.get(" + DQ + "source" + DQ + ") or " + DQ + DQ + ").strip()"),
            _ln("        if source == " + DQ + DQ + ":"),
            _ln("            source = provenance.get(eid, {}).get(rec[" + DQ + "lodged_in" + DQ + "], " + DQ + DQ + ")"))),
    ("DFC-09", "src/bcrep/depends.py",
     _block(_ln("        if pos < window_start:"),
            _ln("            return " + DQ + "DEP-MISSING" + DQ + ", sources")),
     _block(_ln("        if pos < window_start:"),
            _ln("            sources.append((dep, " + DQ + "checkpoint" + DQ + "))"))),
    ("DFC-10", "src/bcrep/compensation.py",
     _block(_ln("    if target_id not in state[" + DQ + "applied" + DQ + "]:")),
     _block(_ln("    if target_id in state[" + DQ + "reversed" + DQ + "]:"),
            _ln("        row[" + DQ + "disposition" + DQ + "] = " + DQ + "void_duplicate" + DQ),
            _ln("        register.append(row)"),
            _ln("        return"),
            _ln("    if target_id not in state[" + DQ + "applied" + DQ + "]:"))),
    ("DFC-11", "src/bcrep/compensation.py",
     _block(_ln("    reversed_cu = round(quantity * factors[" + DQ + "reversal_num" + DQ + "]"),
            _ln("                        / factors[" + DQ + "reversal_den" + DQ + "])")),
     _block(_ln("    reversed_cu = normalise.half_up("),
            _ln("        Fraction(quantity) * Fraction(factors[" + DQ + "reversal_num" + DQ + "],"),
            _ln("                                      factors[" + DQ + "reversal_den" + DQ + "]))"))),
    ("DFC-12", "src/bcrep/derived.py",
     _block(_ln("        quantum = 50")),
     _block(_ln("        quantum = params[" + DQ + "classes" + DQ + "].get(cls, {}).get(" + DQ + "carry_quantum" + DQ + ")"))),
    ("DFC-13", "src/bcrep/normalise.py",
     _block(_ln("    stations = latest_by(reading.read_delim(root / " + DQ + "station_register_current.csv" + DQ + "),")),
     _block(_ln("    stations = latest_by(reading.read_delim(root / " + DQ + "station_register_frozen.csv" + DQ + "),"))),
    ("DFC-14", "src/bcrep/replay.py",
     _block(_ln("            queue = list(state[" + DQ + "pending" + DQ + "])")),
     _block(_ln("            queue = sorted(state[" + DQ + "pending" + DQ + "],"),
            _ln("                           key=lambda eid: precedence_key(ctx, ctx[" + DQ + "by_id" + DQ + "][eid]))"))),
    ("DFC-14", "src/bcrep/replay.py",
     _block(_ln("def run(ctx, start, end, body=None, run_rounds=True):")),
     _block(_ln("def precedence_key(ctx, rec):"),
            _ln("    " + DQ + DQ + DQ
                   + "The five level ladder the directive puts in force: scope, then the"),
            _ln("    region rank on the roster, then the normalised quantity, then the"),
            _ln("    canonical position, then the event identifier." + DQ + DQ + DQ),
            _ln("    scope_rank = 0 if str(rec.get(" + DQ + "scope" + DQ + ", " + DQ
                   + "standard" + DQ + ")) == " + DQ + "mandatory" + DQ + " else 1"),
            _ln("    station = ctx[" + DQ + "stations" + DQ + "].get(str(rec[" + DQ
                   + "station" + DQ + "]).strip())"),
            _ln("    region = str(station[" + DQ + "region" + DQ
                   + "]).strip() if station else " + DQ + DQ),
            _ln("    region_rank = ctx[" + DQ + "params" + DQ + "][" + DQ
                   + "regions" + DQ + "].get(region, 99)"),
            _ln("    quantity = ctx[" + DQ + "norm" + DQ + "].get(rec[" + DQ
                   + "event_id" + DQ + "]) or 0"),
            _ln("    return (scope_rank, region_rank, quantity, int(rec[" + DQ
                   + "position" + DQ + "]),"),
            _ln("            str(rec[" + DQ + "event_id" + DQ + "]))"),
            _ln(""),
            _ln(""),
            _ln("def run(ctx, start, end, body=None, run_rounds=True):"))),
    ("DFC-15", "src/bcrep/reading.py",
     _block(_ln("        wb = ET.fromstring(zf.read(" + DQ + "xl/workbook.xml" + DQ
                   + "))"),
            _ln("        names = []"),
            _ln("        for sh in wb.iter():"),
            _ln("            if sh.tag.endswith(" + DQ + "}sheet" + DQ + "):"),
            _ln("                names.append(sh.attrib.get(" + DQ + "name" + DQ
                   + "))"),
            _ln("        out = {}"),
            _ln("        for idx, name in enumerate(names, start=1):"),
            _ln("            member = " + DQ + "xl/worksheets/sheet" + DQ
                   + " + str(idx) + " + DQ + ".xml" + DQ),
            _ln("            if member not in zf.namelist():"),
            _ln("                continue"),
            _ln("            out[name] = _sheet_rows(zf.read(member), shared)"),
            _ln("        return out")),
     _block(_ln("        wb = ET.fromstring(zf.read(" + DQ + "xl/workbook.xml" + DQ
                   + "))"),
            _ln("        rels = ET.fromstring(zf.read(" + DQ
                   + "xl/_rels/workbook.xml.rels" + DQ + "))"),
            _ln("        targets = {rel.attrib.get(" + DQ + "Id" + DQ
                   + "): rel.attrib.get(" + DQ + "Target" + DQ + ", " + DQ + DQ + ")"),
            _ln("                   for rel in rels.iter() if rel.tag.endswith("
                   + DQ + "}Relationship" + DQ + ")}"),
            _ln("        rid = (" + DQ
                   + "{http://schemas.openxmlformats.org/officeDocument/2006/" + DQ),
            _ln("               " + DQ + "relationships}id" + DQ + ")"),
            _ln("        out = {}"),
            _ln("        for sh in wb.iter():"),
            _ln("            if not sh.tag.endswith(" + DQ + "}sheet" + DQ + "):"),
            _ln("                continue"),
            _ln("            target = targets.get(sh.attrib.get(rid), " + DQ + DQ
                   + ")"),
            _ln("            member = target[1:] if target.startswith(" + DQ + "/"
                   + DQ + ") else " + DQ + "xl/" + DQ + " + target"),
            _ln("            if member not in zf.namelist():"),
            _ln("                continue"),
            _ln("            out[sh.attrib.get(" + DQ + "name" + DQ
                   + ")] = _sheet_rows(zf.read(member), shared)"),
            _ln("        return out"))),
    ("DFC-16", "src/bcrep/reading.py",
     _block(_ln("def _strings(content):"),
            _ln("    " + DQ + DQ + DQ
                   + "The text a content stream shows, one string per line." + DQ + DQ
                   + DQ),
            _ln("    out = []"),
            _ln("    at = 0"),
            _ln("    while at < len(content):"),
            _ln("        if content[at] == " + DQ + "(" + DQ + ":"),
            _ln("            text, at = _pdf_string(content, at)"),
            _ln("            out.append(text)"),
            _ln("        else:"),
            _ln("            at += 1"),
            _ln("    return out"),
            _ln(""),
            _ln(""),
            _ln("def read_pdf_lines(path):"),
            _ln("    out = []"),
            _ln("    for content in _pdf_streams(Path(path).read_bytes()):"),
            _ln("        out.extend(_strings(content))")),
     _block(_ln("def _shown_text(content):"),
            _ln("    " + DQ + DQ + DQ
                   + "One line per text showing operator: the string a Tj shows, and the"),
            _ln("    strings of a TJ array joined in order, its kerning numbers dropped."
                   + DQ + DQ + DQ),
            _ln("    lines = []"),
            _ln("    operands = []"),
            _ln("    array = None"),
            _ln("    at = 0"),
            _ln("    while at < len(content):"),
            _ln("        ch = content[at]"),
            _ln("        if ch == " + DQ + "(" + DQ + ":"),
            _ln("            text, at = _pdf_string(content, at)"),
            _ln("            (operands if array is None else array).append(text)"),
            _ln("        elif ch == " + DQ + "[" + DQ + ":"),
            _ln("            array = []"),
            _ln("            at += 1"),
            _ln("        elif ch == " + DQ + "]" + DQ + ":"),
            _ln("            operands.append(array)"),
            _ln("            array = None"),
            _ln("            at += 1"),
            _ln("        elif ch.isspace():"),
            _ln("            at += 1"),
            _ln("        else:"),
            _ln("            end = at"),
            _ln("            while (end < len(content) and not content[end].isspace()"),
            _ln("                   and content[end] not in " + DQ + "()[]" + DQ
                   + "):"),
            _ln("                end += 1"),
            _ln("            word = content[at:end]"),
            _ln("            at = end"),
            _ln("            if word == " + DQ + "Tj" + DQ
                   + " and operands and isinstance(operands[-1], str):"),
            _ln("                lines.append(operands[-1])"),
            _ln("            elif word == " + DQ + "TJ" + DQ
                   + " and operands and isinstance(operands[-1], list):"),
            _ln("                lines.append(" + DQ + DQ + ".join(operands[-1]))"),
            _ln("            if word[:1].isalpha():"),
            _ln("                operands = []"),
            _ln("    return lines"),
            _ln(""),
            _ln(""),
            _ln("def read_pdf_lines(path):"),
            _ln("    out = []"),
            _ln("    for content in _pdf_streams(Path(path).read_bytes()):"),
            _ln("        out.extend(_shown_text(content))"))),
    ("DFC-17", "src/bcrep/transitions.py",
     _block(_ln("from . import derived"),
            _ln(""),
            _ln(""),
            _ln("def predicate_holds(text, state, stations):"),
            _ln("    " + DQ + DQ + DQ
                   + "The closed predicate vocabulary, read against the state as it stands"),
            _ln("    immediately before the event is offered." + DQ + DQ + DQ),
            _ln("    if not text:"),
            _ln("        return True"),
            _ln("    parts = str(text).split(" + DQ + ":" + DQ + ")"),
            _ln("    head = parts[0]"),
            _ln("    if head == " + DQ + "balance_at_least" + DQ + ":"),
            _ln("        return state[" + DQ + "balances" + DQ
                   + "].get(parts[1], 0) >= int(parts[2])"),
            _ln("    if head == " + DQ + "allotment_below" + DQ + ":"),
            _ln("        inner = state[" + DQ + "allotments" + DQ
                   + "].get(parts[1], {})"),
            _ln("        return inner.get(parts[2], 0) < int(parts[3])"),
            _ln("    if head == " + DQ + "counter_at_least" + DQ + ":"),
            _ln("        return state[" + DQ + "counters" + DQ
                   + "].get(parts[1], 0) >= int(parts[2])"),
            _ln("    if head == " + DQ + "no_pending" + DQ + ":"),
            _ln("        return not state[" + DQ + "pending" + DQ + "]"),
            _ln("    if head == " + DQ + "station_active" + DQ + ":"),
            _ln("        row = stations.get(parts[1])"),
            _ln("        return row is not None and str(row[" + DQ + "status" + DQ
                   + "]).strip() == " + DQ + "active" + DQ),
            _ln("    return False"),
            _ln(""),
            _ln(""),
            _ln("def admissible(ctx, state, rec):"),
            _ln("    return predicate_holds(rec.get(" + DQ + "requires" + DQ
                   + "), state, ctx[" + DQ + "stations" + DQ + "])")),
     _block(_ln("from . import derived, reading"),
            _ln(""),
            _ln("# The vocabulary as first lodged, read when no register is handed over."),
            _ln("DEFAULT_FORMS = {"),
            _ln("    " + DQ + "balance_at_least" + DQ + ": (" + DQ + "active" + DQ
                   + ", [" + DQ + "station" + DQ + ", " + DQ + "amount_cu" + DQ + "]),"),
            _ln("    " + DQ + "allotment_below" + DQ + ": (" + DQ + "active" + DQ
                   + ", [" + DQ + "station" + DQ + ", " + DQ + "programme" + DQ + ", "
                   + DQ + "amount_cu" + DQ + "]),"),
            _ln("    " + DQ + "counter_at_least" + DQ + ": (" + DQ + "active" + DQ
                   + ", [" + DQ + "counter" + DQ + ", " + DQ + "amount" + DQ + "]),"),
            _ln("    " + DQ + "no_pending" + DQ + ": (" + DQ + "active" + DQ
                   + ", []),"),
            _ln("    " + DQ + "station_active" + DQ + ": (" + DQ + "active" + DQ
                   + ", [" + DQ + "station" + DQ + "]),"),
            _ln("}"),
            _ln(""),
            _ln(""),
            _ln("def predicate_forms(root, frozen):"),
            _ln("    " + DQ + DQ + DQ
                   + "The predicate register in force. For each form the row with the"),
            _ln("    greatest revision at or below the frozen revision gives its status and"),
            _ln("    the order its arguments are written in." + DQ + DQ + DQ),
            _ln("    held = {}"),
            _ln("    for row in reading.read_delim(root / " + DQ
                   + "eligibility_predicates.csv" + DQ + "):"),
            _ln("        revision = int(str(row[" + DQ + "revision" + DQ
                   + "]).strip())"),
            _ln("        if revision > frozen:"),
            _ln("            continue"),
            _ln("        name = row[" + DQ + "predicate_id" + DQ + "].strip()"),
            _ln("        if name not in held or revision >= held[name][0]:"),
            _ln("            held[name] = (revision, row)"),
            _ln("    return {name: (row[" + DQ + "status" + DQ + "].strip(), row["
                   + DQ + "form" + DQ + "].strip().split(" + DQ + ":" + DQ + ")[1:])"),
            _ln("            for name, (_revision, row) in held.items()}"),
            _ln(""),
            _ln(""),
            _ln("def predicate_holds(text, state, stations, forms=None):"),
            _ln("    " + DQ + DQ + DQ
                   + "A predicate names its form and then its arguments in the order the"),
            _ln("    form in force lists them, read against the state as it stands immediately"),
            _ln("    before the event is offered. A form the register does not carry as"),
            _ln("    active is false whenever it is read." + DQ + DQ + DQ),
            _ln("    if not text:"),
            _ln("        return True"),
            _ln("    parts = str(text).split(" + DQ + ":" + DQ + ")"),
            _ln("    head = parts[0]"),
            _ln("    status, names = (DEFAULT_FORMS if forms is None else forms).get("),
            _ln("        head, (" + DQ + DQ + ", []))"),
            _ln("    if status != " + DQ + "active" + DQ
                   + " or len(parts) - 1 != len(names):"),
            _ln("        return False"),
            _ln("    args = dict(zip(names, parts[1:]))"),
            _ln("    if head == " + DQ + "balance_at_least" + DQ + ":"),
            _ln("        return (state[" + DQ + "balances" + DQ + "].get(args[" + DQ
                   + "station" + DQ + "], 0)"),
            _ln("                >= int(args[" + DQ + "amount_cu" + DQ + "]))"),
            _ln("    if head == " + DQ + "allotment_below" + DQ + ":"),
            _ln("        inner = state[" + DQ + "allotments" + DQ + "].get(args["
                   + DQ + "station" + DQ + "], {})"),
            _ln("        return inner.get(args[" + DQ + "programme" + DQ
                   + "], 0) < int(args[" + DQ + "amount_cu" + DQ + "])"),
            _ln("    if head == " + DQ + "counter_at_least" + DQ + ":"),
            _ln("        return state[" + DQ + "counters" + DQ + "].get(args[" + DQ
                   + "counter" + DQ + "], 0) >= int(args[" + DQ + "amount" + DQ + "])"),
            _ln("    if head == " + DQ + "no_pending" + DQ + ":"),
            _ln("        return not state[" + DQ + "pending" + DQ + "]"),
            _ln("    if head == " + DQ + "station_active" + DQ + ":"),
            _ln("        row = stations.get(args[" + DQ + "station" + DQ + "])"),
            _ln("        return row is not None and str(row[" + DQ + "status" + DQ
                   + "]).strip() == " + DQ + "active" + DQ),
            _ln("    return False"),
            _ln(""),
            _ln(""),
            _ln("def admissible(ctx, state, rec):"),
            _ln("    if " + DQ + "forms" + DQ + " not in ctx:"),
            _ln("        ctx[" + DQ + "forms" + DQ + "] = predicate_forms(ctx[" + DQ
                   + "root" + DQ + "], ctx[" + DQ + "frozen" + DQ + "])"),
            _ln("    return predicate_holds(rec.get(" + DQ + "requires" + DQ
                   + "), state, ctx[" + DQ + "stations" + DQ + "],"),
            _ln("                           ctx[" + DQ + "forms" + DQ + "])"))),
    ("DFC-18", "src/bcrep/depends.py",
     _block(_ln("def cycle_members(events, edges, by_id):"),
            _ln("    found = set()"),
            _ln("    stack = []"),
            _ln("    seen = {}"),
            _ln(""),
            _ln("    def walk(node):"),
            _ln("        seen[node] = 1"),
            _ln("        stack.append(node)"),
            _ln("        for nxt in edges.get(node, []):"),
            _ln("            if nxt not in by_id:"),
            _ln("                continue"),
            _ln("            if seen.get(nxt) == 1:"),
            _ln("                cut = stack.index(nxt)"),
            _ln("                for member in stack[cut:]:"),
            _ln("                    found.add(member)"),
            _ln("            elif seen.get(nxt) is None:"),
            _ln("                walk(nxt)"),
            _ln("        stack.pop()"),
            _ln("        seen[node] = 2"),
            _ln(""),
            _ln("    for rec in events:"),
            _ln("        if seen.get(rec[" + DQ + "event_id" + DQ + "]) is None:"),
            _ln("            walk(rec[" + DQ + "event_id" + DQ + "])"),
            _ln("    return found")),
     _block(_ln("def cycle_members(events, edges, by_id):"),
            _ln("    " + DQ + DQ + DQ
                   + "Every event some path of edges leads back to: the members of each"),
            _ln("    strongly connected group of two or more, and every event with a self"),
            _ln("    edge. Edges naming an identifier outside the history take no part."
                   + DQ + DQ + DQ),
            _ln("    order = {}"),
            _ln("    low = {}"),
            _ln("    stack = []"),
            _ln("    on_stack = set()"),
            _ln("    found = set()"),
            _ln(""),
            _ln("    def visit(node):"),
            _ln("        order[node] = low[node] = len(order)"),
            _ln("        stack.append(node)"),
            _ln("        on_stack.add(node)"),
            _ln("        for nxt in edges.get(node, []):"),
            _ln("            if nxt not in by_id:"),
            _ln("                continue"),
            _ln("            if nxt not in order:"),
            _ln("                visit(nxt)"),
            _ln("                low[node] = min(low[node], low[nxt])"),
            _ln("            elif nxt in on_stack:"),
            _ln("                low[node] = min(low[node], order[nxt])"),
            _ln("        if low[node] != order[node]:"),
            _ln("            return"),
            _ln("        group = []"),
            _ln("        while True:"),
            _ln("            member = stack.pop()"),
            _ln("            on_stack.discard(member)"),
            _ln("            group.append(member)"),
            _ln("            if member == node:"),
            _ln("                break"),
            _ln("        if len(group) > 1 or node in edges.get(node, []):"),
            _ln("            found.update(group)"),
            _ln(""),
            _ln("    for rec in events:"),
            _ln("        if rec[" + DQ + "event_id" + DQ + "] not in order:"),
            _ln("            visit(rec[" + DQ + "event_id" + DQ + "])"),
            _ln("    return found"))),
    ("DFC-19", "src/bcrep/publish.py",
     _block(_ln("    archive = {}"),
            _ln("    for row in reading.read_sqlite_table(root / " + DQ
                   + "prior_epoch_archive.db" + DQ + ","),
            _ln("                                         " + DQ + "prior_counters"
                   + DQ + "):"),
            _ln("        archive[(row[" + DQ + "checkpoint_id" + DQ + "], row[" + DQ
                   + "counter" + DQ + "])] = int(row[" + DQ + "value" + DQ + "])"),
            _ln("    history = {}"),
            _ln("    for row in reading.read_delim(root / " + DQ
                   + "allotment_ceiling_history.tsv" + DQ + ", TAB):"),
            _ln("        history[(_int(row[" + DQ + "revision" + DQ + "]), row["
                   + DQ + "class" + DQ + "].strip())] = _int("),
            _ln("            row[" + DQ + "ceiling_cu" + DQ + "])"),
            _ln("    deltas = {}"),
            _ln("    historic_total = 0"),
            _ln("    declared = " + DQ + DQ),
            _ln("    recomputed = " + DQ + DQ),
            _ln("    if chosen:"),
            _ln("        for name in derived.COUNTER_NAMES:"),
            _ln("            held = archive.get((chosen[1], name))"),
            _ln("            if held is not None:"),
            _ln("                deltas[name] = held - int(chosen[2][" + DQ
                   + "counters" + DQ + "].get(name, 0))"),
            _ln("        declared = chosen[3][" + DQ + "state_digest" + DQ
                   + "].strip()"),
            _ln("        recomputed = derived.state_digest(chosen[2])"),
            _ln("        checkpoint_revision = _int(chosen[3][" + DQ + "revision"
                   + DQ + "])"),
            _ln("        historic_total = sum(v for (rev, _cls), v in history.items()"),
            _ln("                             if rev == checkpoint_revision)")),
     _block(_ln("    archive = reading.read_sqlite_table(root / " + DQ
                   + "prior_epoch_archive.db" + DQ + ","),
            _ln("                                        " + DQ + "prior_counters"
                   + DQ + ")"),
            _ln("    history = reading.read_delim(root / " + DQ
                   + "allotment_ceiling_history.tsv" + DQ + ", TAB)"),
            _ln("    deltas = {}"),
            _ln("    historic_total = 0"),
            _ln("    declared = " + DQ + DQ),
            _ln("    recomputed = " + DQ + DQ),
            _ln("    if chosen:"),
            _ln("        for name in derived.COUNTER_NAMES:"),
            _ln("            held = [int(row[" + DQ + "value" + DQ
                   + "]) for row in archive"),
            _ln("                    if str(row[" + DQ + "checkpoint_id" + DQ
                   + "]).strip() == chosen[1]"),
            _ln("                    and str(row[" + DQ + "counter" + DQ
                   + "]).strip() == name]"),
            _ln("            if held:"),
            _ln("                deltas[name] = held[-1] - int(chosen[2][" + DQ
                   + "counters" + DQ + "].get(name, 0))"),
            _ln("        declared = chosen[3][" + DQ + "state_digest" + DQ
                   + "].strip()"),
            _ln("        recomputed = derived.state_digest(chosen[2])"),
            _ln("        checkpoint_revision = _int(chosen[3][" + DQ + "revision"
                   + DQ + "])"),
            _ln("        historic_total = sum(_int(row[" + DQ + "ceiling_cu" + DQ
                   + "]) for row in history"),
            _ln("                             if _int(row[" + DQ + "revision" + DQ
                   + "]) == checkpoint_revision)"))),
    ("DFC-20", "src/bcrep/compensation.py",
     _block(_ln("    klass = ctx[" + DQ + "cls" + DQ + "][target_id]")),
     _block(_ln("    lodged = normalise.latest_by("),
            _ln("        reading.read_delim(ctx[" + DQ + "root" + DQ + "] / " + DQ
                   + "station_register_frozen.csv" + DQ + "),"),
            _ln("        " + DQ + "station" + DQ + ", " + DQ + "revision" + DQ
                   + ", int(target[" + DQ + "revision" + DQ + "]))"),
            _ln("    held = lodged.get(str(target[" + DQ + "station" + DQ
                   + "]).strip())"),
            _ln("    klass = str(held[" + DQ + "class" + DQ
                   + "]).strip() if held else ctx[" + DQ + "cls" + DQ + "][target_id]"))),
    ("DFC-21", "src/bcrep/checkpointing.py",
     _block(_ln("        if int(body[" + DQ + "position" + DQ + "]) >= int(end):")),
     _block(_ln("        watermark = int(body[" + DQ + "position" + DQ + "])"),
            _ln("        if any(eid not in ctx[" + DQ + "by_id" + DQ + "]"),
            _ln("               or int(ctx[" + DQ + "by_id" + DQ + "][eid][" + DQ
                   + "position" + DQ + "]) > watermark"),
            _ln("               for eid in body[" + DQ + "applied" + DQ + "]):"),
            _ln("            rejected.append({" + DQ + "checkpoint_id" + DQ
                   + ": cid,"),
            _ln("                             " + DQ + "reason" + DQ + ": " + DQ
                   + "ledger_past_watermark" + DQ + "})"),
            _ln("            continue"),
            _ln("        if int(body[" + DQ + "position" + DQ + "]) >= int(end):"))),
    ("DFC-22", "src/bcrep/ordering.py",
     _block(_ln("def load_events(root, frozen, alias):")),
     _block(_ln("def later_epoch_prefix(root):"),
            _ln("    " + DQ + DQ + DQ
                   + "The identifier prefix data_lineage.md reserves for supplement rows"),
            _ln("    lodged for a later epoch." + DQ + DQ + DQ),
            _ln("    text = " + DQ + " " + DQ + ".join((root / " + DQ
                   + "data_lineage.md" + DQ + ").read_text(encoding=" + DQ + "utf-8"
                   + DQ + ").split())"),
            _ln("    marker = " + DQ + "whose identifier begins `" + DQ),
            _ln("    at = text.find(marker)"),
            _ln("    if at < 0:"),
            _ln("        return None"),
            _ln("    begin = at + len(marker)"),
            _ln("    return text[begin:text.index(" + DQ + "`" + DQ + ", begin)]"),
            _ln(""),
            _ln(""),
            _ln("def load_events(root, frozen, alias):"))),
    ("DFC-22", "src/bcrep/ordering.py",
     _block(_ln("    raw = []"),
            _ln("    for name in (" + DQ + "event_journal.jsonl" + DQ + ", " + DQ
                   + "event_supplement.ndjson" + DQ + "):"),
            _ln("        for rec in reading.read_jsonl(root / name):"),
            _ln("            rec = dict(rec)")),
     _block(_ln("    raw = []"),
            _ln("    later = later_epoch_prefix(root)"),
            _ln("    for name in (" + DQ + "event_journal.jsonl" + DQ + ", " + DQ
                   + "event_supplement.ndjson" + DQ + "):"),
            _ln("        for rec in reading.read_jsonl(root / name):"),
            _ln("            if (name == " + DQ + "event_supplement.ndjson" + DQ
                   + " and later"),
            _ln("                    and str(rec[" + DQ + "event_id" + DQ
                   + "]).strip().startswith(later)):"),
            _ln("                continue"),
            _ln("            rec = dict(rec)"))),
)


def extract():
    """Unpack the shipped package into the working tree."""
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(DATA / "project.zip") as archive:
        archive.extractall(WORK)


def repair():
    """Apply one targeted edit per catalogued defect."""
    for code, relative, broken, correct in REPAIRS:
        path = WORK / relative
        text = path.read_text(encoding="utf-8")
        if text.count(broken) != 1:
            raise SystemExit("repair " + code + " does not match "
                             + relative + " exactly once")
        path.write_text(text.replace(broken, correct), encoding="utf-8",
                        newline=NL)


def deliver():
    """Write the repaired tree back out as the delivered archive."""
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = (1980, 1, 1, 0, 0, 0)
    names = sorted(str(p.relative_to(WORK)).replace(os.sep, "/")
                   for p in WORK.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(OUT / "package.zip", "w",
                         zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, (WORK / name).read_bytes())


def drive(options):
    """Run the repaired package once with the options in the order given."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORK / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "bcrep"] + options, env=env)
    if proc.returncode != 0:
        raise SystemExit("the repaired package exited "
                         + str(proc.returncode))


def publish():
    """Drive the repaired package over the working papers."""
    drive(["--data", str(DATA), "--out", str(OUT)])


def digests(folder):
    """One digest per published document, keyed by file name."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(folder).iterdir()) if path.is_file()}


def verify():
    """Run the checks the contract names and print what each one showed.

    The contract asks for three properties the published bytes alone cannot
    show: the entry point takes its two options in either order, two runs over
    one paper directory agree, and the same epoch under another directory name
    agrees again. Each is driven here and the comparison is printed.
    """
    scratch = Path(tempfile.mkdtemp(prefix="bcrep-check-"))
    papers_before = digests(DATA)
    out_first = scratch / "out_first"
    data_first = scratch / "data_first"
    drive(["--out", str(out_first), "--data", str(DATA)])
    drive(["--data", str(DATA), "--out", str(data_first)])
    print("[check] the entry point accepted both option orders")

    first, second = digests(out_first), digests(data_first)
    print("[check] two runs over one paper directory, "
          + str(len(first)) + " documents compared by digest: "
          + ("identical" if first == second else "DIFFER"))
    if first != second:
        raise SystemExit("the repaired package is not reproducible")

    moved = scratch / "papers_under_another_name"
    shutil.copytree(DATA, moved)
    renamed = scratch / "renamed_run"
    drive(["--data", str(moved), "--out", str(renamed)])
    third = digests(renamed)
    print("[check] the same epoch under another directory name: "
          + ("identical" if third == first else "DIFFER"))
    if third != first:
        raise SystemExit("the repaired package keys on the directory name")

    print("[check] the paper directory after every run: "
          + ("untouched" if papers_before == digests(DATA) else "WRITTEN TO"))
    shutil.rmtree(scratch, ignore_errors=True)


def workbook_epoch_cells():
    """The epoch key cell of each workbook sheet, read with the standard
    library, so the live sheet is picked by the cell and not by the name.
    Each sheet name reaches its worksheet part through its relationship."""
    found = []
    with zipfile.ZipFile(DATA / "custody_parameter_workbook.xlsx") as book:
        book_xml = ET.fromstring(book.read("xl/workbook.xml"))
        targets = {rel.get("Id"): rel.get("Target") for rel in ET.fromstring(
            book.read("xl/_rels/workbook.xml.rels")).iter(NS_PKGREL + "Relationship")}
        shared = ["".join(node.text or "" for node in item.iter(NS_SHEET + "t"))
                  for item in ET.fromstring(
                      book.read("xl/sharedStrings.xml")).iter(NS_SHEET + "si")]
        for entry in book_xml.iter(NS_SHEET + "sheet"):
            sheet = ET.fromstring(book.read("xl/" + targets[entry.get(R_ID)]))
            for row in sheet.iter(NS_SHEET + "row"):
                cells = {}
                for cell in row.iter(NS_SHEET + "c"):
                    value = cell.find(NS_SHEET + "v")
                    text = value.text if value is not None else ""
                    if cell.get("t") == "s":
                        text = shared[int(text)]
                    cells[cell.get("r")] = text
                if cells.get("A" + row.get("r")) == "epoch_key":
                    ref = "B" + row.get("r")
                    found.append((entry.get("name"), ref, cells.get(ref, "")))
                    break
    return found


def memo_resolutions():
    """Every resolution line of the board memo, in the order it carries them:
    each FlateDecode content stream inflated, a Tj string read as it stands
    and a kerned TJ array read with its strings joined."""
    raw = (DATA / "custody_board_memo.pdf").read_bytes()
    lines = []
    for match in re.finditer(rb"/Length (\d+) /Filter /FlateDecode >>\nstream\n", raw):
        begin = match.end()
        content = zlib.decompress(raw[begin:begin + int(match.group(1))])
        for shown in re.finditer(r"\((.*?)\) Tj|\[(.*?)\] TJ", content.decode("latin-1")):
            if shown.group(1) is not None:
                lines.append(shown.group(1))
            else:
                lines.append("".join(re.findall(r"\((.*?)\)", shown.group(2))))
    return [line for line in lines if "RESOLUTION" in line]


def directive_ladder():
    """The re offer ladder rows of the precedence directive."""
    with zipfile.ZipFile(DATA / "precedence_directive.docx") as document:
        body = ET.fromstring(document.read("word/document.xml"))
    rows = []
    for row in body.iter(NS_WORD + "tr"):
        cells = ["".join(node.text or "" for node in cell.iter(NS_WORD + "t"))
                 for cell in row.findall(NS_WORD + "tc")]
        if cells and cells[0] == "level":
            rows.append(cells)
    return rows


def frozen_station_classes():
    """The station class in force, one row per station, drafts dropped."""
    header = json.loads((DATA / "epoch_header.json").read_text(encoding="utf-8"))
    frozen = int(header["frozen_register_revision"])
    lines = (DATA / "station_register_frozen.csv").read_text(
        encoding="utf-8").splitlines()
    columns = lines[0].split(",")
    latest = {}
    for line in lines[1:]:
        row = dict(zip(columns, line.split(",")))
        revision = int(row["revision"])
        if revision > frozen:
            continue
        station = row["station"].strip()
        if station not in latest or revision >= latest[station][0]:
            latest[station] = (revision, row["class"].strip())
    return {name: value[1] for name, value in latest.items()}


def report():
    """Close with the report the contract asks for, subject by subject."""
    def read(name):
        return json.loads((OUT / name).read_text(encoding="utf-8"))

    params = read("unit_normalisation.json")
    selection = read("checkpoint_selection.json")
    passes = read("eligibility_passes.json")
    final = read("final_state.json")

    expectations = (DATA / "package_expectations.toml").read_text(
        encoding="utf-8")
    names = re.search(r"names = \[(.*?)\]", expectations, re.S).group(1)
    modules = re.findall(r'"([^"]+)"', names)
    print("[report] package_expectations.toml fixes the module list at "
          + str(len(modules)) + " modules and the standard library at the "
          + "3.12 series: " + ", ".join(modules))
    carried = sorted(path.stem for path
                     in (WORK / "src" / "bcrep").glob("*.py"))
    print("[report] the delivered tree carries exactly that list: "
          + str(carried == sorted(modules)))

    print("")
    print("[report] the three papers that are not plain text")
    cells = workbook_epoch_cells()
    for name, ref, key in cells:
        print("  workbook sheet " + repr(name) + " epoch_key cell " + ref
              + ": " + key)
    for line in memo_resolutions():
        print("  memo: " + line)
    for row in directive_ladder():
        print("  directive ladder: " + " | ".join(row))

    print("")
    live_ref = next(ref for name, ref, _key in cells
                    if name == params["live_sheet"])
    print("[report] live workbook sheet: " + str(params["live_sheet"])
          + ", matched on its epoch key cell " + live_ref + " = "
          + str(params["workbook_epoch_key"]))
    print("[report] selected checkpoint: " + str(selection["selected"])
          + " at watermark position " + str(selection["watermark_position"]))

    reasons = {}
    rows = (OUT / "quarantine_ledger.csv").read_text(
        encoding="utf-8").splitlines()[1:]
    for row in rows:
        code = row.split(",")[3]
        reasons[code] = reasons.get(code, 0) + 1
    for code in sorted(reasons):
        print("[report] set aside under " + code + ": " + str(reasons[code]))

    rejected = {}
    for entry in selection["rejected"]:
        rejected[entry["reason"]] = rejected.get(entry["reason"], 0) + 1
    for reason in sorted(rejected):
        print("[report] checkpoint rows rejected as " + reason + ": "
              + str(rejected[reason]))

    classes = frozen_station_classes()
    if final["balances"]:
        station = max(final["balances"], key=lambda k: final["balances"][k])
        held = classes.get(station, "")
        quantum = params["classes"].get(held, {}).get("carry_quantum")
        print("[report] largest settled balance: " + station + " holding "
              + str(final["balances"][station]) + " cu in class " + str(held)
              + ", carry quantum " + str(quantum))

    print("[report] re offer rounds run: " + str(passes["round_count"])
          + ", the run settled: " + ("yes" if passes["stable"] else "no"))

    register = (OUT / "compensation_register.csv").read_text(
        encoding="utf-8").splitlines()[1:]
    for row in register:
        cells = row.split(",")
        if cells[3] != "applied":
            print("[report] compensation " + cells[0] + " recorded void, "
                  + "reason " + cells[3] + ", target " + cells[1])

    print("[report] the quiet branch at stage r04, taken from "
          + "spec_stage_r04_checkpoint_selection.md rather than from this "
          + "epoch: when no checkpoint is usable the replay opens from an "
          + "empty state at watermark zero, which this epoch never reaches "
          + "because " + str(len(selection["usable"])) + " are usable.")

    reported = set()
    for code, relative, _broken, _correct in REPAIRS:
        if code in reported:
            continue
        reported.add(code)
        print("[report] repaired " + code + " at stage "
              + STAGE_OF_DEFECT[code] + " in " + relative
              + ", on the authority of " + PAPER_OF_DEFECT[code])


def main():
    extract()
    repair()
    deliver()
    publish()
    verify()
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
