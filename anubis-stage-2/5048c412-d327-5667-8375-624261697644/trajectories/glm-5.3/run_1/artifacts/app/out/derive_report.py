#!/usr/bin/env python3
"""Balance the four closed storage basins of a season extract and write its reports.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import configparser
import csv
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
BASINS = ('East', 'North', 'South', 'West')
SEGMENTS = ('commercial', 'public')
SEASON_FIRST_DAY = date(2026, 7, 1)
SEASON_LAST_DAY = date(2026, 9, 30)
SEASON_DAYS = (SEASON_LAST_DAY - SEASON_FIRST_DAY).days + 1
SENSE_POINTS = {'fwd': (0, 1), 'rev': (1, 0), 'nil': (Fraction(1, 2), Fraction(1, 2))}
DRAWN_BY_SENSE = {'from': 'rev', 'to': 'fwd', 'neither': 'nil'}
DRAWN_UPPER_SENSE = {'1': 'rev', '0': 'fwd', '0.5': 'nil'}
STN_RE = re.compile(r'^RS-(\d{3})$')
CATCHMENT_RE = re.compile(r'^C(\d{2})$')
GAUGE_RE = re.compile(r'^G(\d{4})$')
GAUGING_RE = re.compile(r'^GX(\d{5})$')
SCHEME_RE = re.compile(r'^SC-(\d{2})$')
DATE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')


class RuleError(Exception):
    """An input broke a rule the documents state for it."""


def die(message):
    raise RuleError(message)


def round_half_away(value):
    """Round an exact Fraction to a whole number, halves away from zero."""
    if value < 0:
        return -math.floor(-value + Fraction(1, 2))
    return math.floor(value + Fraction(1, 2))


def drop_fraction(value):
    """Take an exact Fraction to a whole number by dropping its fraction."""
    if value < 0:
        return -math.floor(-value)
    return math.floor(value)


def points_text(points):
    """Write draw points as the gauging_net report writes them."""
    if points == 1:
        return '1'
    if points == 0:
        return '0'
    return '1/2'


def parse_date(text, where):
    match = DATE_RE.match(text)
    if not match:
        die('%s: %r is not an ISO date' % (where, text))
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError as exc:
        die('%s: %r is not a date: %s' % (where, text, exc))


def day_to_date(day, where):
    if not 1 <= day <= SEASON_DAYS:
        die('%s: day %d is outside the season' % (where, day))
    return SEASON_FIRST_DAY + timedelta(days=day - 1)


# ---------------------------------------------------------------- input files


def read_bytes(data_dir, name):
    try:
        with open(os.path.join(data_dir, name), 'rb') as handle:
            return handle.read()
    except OSError as exc:
        raise RuleError('%s: %s' % (name, exc))


def read_text(data_dir, name):
    data = read_bytes(data_dir, name)
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise RuleError('%s: not UTF-8 text: %s' % (name, exc))


def read_table(data_dir, name, delimiter, columns):
    reader = csv.reader(read_text(data_dir, name).splitlines(), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        die('%s: no header line' % name)
    if sorted(header) != sorted(columns):
        die('%s: header %r is not %r' % (name, header, list(columns)))
    rows = []
    for line in reader:
        if not line:
            continue
        if len(line) != len(columns):
            die('%s: %d fields, expected %d' % (name, len(line), len(columns)))
        rows.append(dict(zip(columns, line)))
    return rows


def parse_int(text, where):
    text = text.strip()
    if not re.match(r'^-?\d+$', text):
        die('%s: %r is not an integer' % (where, text))
    return int(text)


def read_config(data_dir):
    parser = configparser.ConfigParser()
    try:
        parser.read_string(read_text(data_dir, 'basin_cfg.ini'))
        label = parser.get('season', 'label').strip()
        cutoff = parser.get('season', 'revision_cutoff')
    except (configparser.Error, KeyError) as exc:
        die('basin_cfg.ini: %s' % exc)
    if not label:
        die('basin_cfg.ini: no season label')
    return label, parse_int(cutoff, 'basin_cfg.ini revision_cutoff')


def read_register(data_dir):
    """Return the station rows of the register authority, unsorted."""
    path = Path(os.path.abspath(os.path.join(data_dir, 'stn_core.sqlite'))).as_uri()
    try:
        connection = sqlite3.connect(path + '?mode=ro', uri=True)
    except sqlite3.Error as exc:
        die('stn_core.sqlite: %s' % exc)
    try:
        rows = list(connection.execute(
            'SELECT stn, station_name, catchment FROM station'))
    except sqlite3.Error as exc:
        die('stn_core.sqlite: %s' % exc)
    finally:
        connection.close()
    seen = set()
    stations = []
    for stn, name, catchment in rows:
        if not STN_RE.match(stn):
            die('stn_core.sqlite: %r is not a station code' % stn)
        if stn in seen:
            die('stn_core.sqlite: station code %s occurs twice' % stn)
        seen.add(stn)
        if not CATCHMENT_RE.match(catchment):
            die('stn_core.sqlite: %r is not a catchment code' % catchment)
        stations.append({'stn': stn, 'station_name': name, 'catchment': catchment})
    if not stations:
        die('stn_core.sqlite: no reservoirs')
    stations.sort(key=lambda row: int(STN_RE.match(row['stn']).group(1)))
    return stations


def read_basin_map(data_dir):
    text = read_bytes(data_dir, 'bs_map.xml')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        die('bs_map.xml: %s' % exc)
    mapping = {}
    for element in root.iter():
        if element.tag.rsplit('}', 1)[-1] != 'catchment':
            continue
        code = element.get('code')
        if code is None:
            die('bs_map.xml: a catchment has no code')
        if code in mapping:
            die('bs_map.xml: catchment %s occurs twice' % code)
        basin = None
        for child in element:
            if child.tag.rsplit('}', 1)[-1] == 'basin':
                basin = (child.text or '').strip()
        if basin not in BASINS:
            die('bs_map.xml: catchment %s has no basin' % code)
        mapping[code] = basin
    if not mapping:
        die('bs_map.xml: no catchments')
    return mapping


def read_crosswalk(data_dir):
    rows = read_table(data_dir, 'xw_codes.csv', ',', ('gauge_no', 'stn'))
    mapping = {}
    for row in rows:
        if not GAUGE_RE.match(row['gauge_no']):
            die('xw_codes.csv: %r is not a gauge number' % row['gauge_no'])
        if not STN_RE.match(row['stn']):
            die('xw_codes.csv: %r is not a station code' % row['stn'])
        mapping[row['stn']] = row['gauge_no']
    return mapping


# ------------------------------------------------------------- meter records


def read_meter(data_dir):
    """Return (reads, corrections, replacements) from the meter container."""
    data = read_bytes(data_dir, 'ob_s3.bin')
    if len(data) < 18:
        die('ob_s3.bin: too short')
    if data[0:4] != b'OBS3':
        die('ob_s3.bin: bad magic')
    if data[4] != 1:
        die('ob_s3.bin: version %d is not 1' % data[4])
    count = int.from_bytes(data[12:14], 'big')
    end = len(data) - 4
    if zlib.crc32(data[4:end]) & 0xFFFFFFFF != int.from_bytes(data[end:], 'big'):
        die('ob_s3.bin: checksum does not match')
    records = meter_records(data, end, count)
    if records is None:
        die('ob_s3.bin: records end before or after the checksum')
    return records


def meter_records(data, end, count):
    """Parse the records of the meter file, or None when they end wrongly."""
    position = 14
    dictionary = []
    running = 0
    reads = {}
    corrections = []
    replacements = []
    for _ in range(count):
        if position >= end:
            die('ob_s3.bin: fewer records than the count says')
        selector = data[position]
        position += 1
        kind = (selector >> 6) & 3
        if kind == 3:
            die('ob_s3.bin: record kind 3 is not allowed')
        gauge, position = meter_gauge(data, end, position, (selector >> 5) & 1, dictionary)
        if kind == 2:
            current, position = meter_gauge(data, end, position, (selector >> 3) & 1,
                                           dictionary)
            replacements.append((gauge, current))
            continue
        if selector & 0x08:
            die('ob_s3.bin: a reading or correction sets bit 3')
        digits, position = meter_varint(data, end, position)
        value = digits // 2 if digits % 2 == 0 else -((digits + 1) // 2)
        if selector & 0x10:
            value = running + value
        running = value
        if kind == 0:
            reads[gauge] = value
            continue
        if position >= end:
            die('ob_s3.bin: a correction has no day')
        corrections.append((gauge, data[position], value))
        position += 1
    if position != end:
        return None
    return reads, corrections, replacements


def meter_gauge(data, end, position, form, dictionary):
    """Read one gauge number of a meter record and keep the dictionary."""
    if form == 0:
        if position + 2 > end:
            die('ob_s3.bin: a gauge number runs past the records')
        number = int.from_bytes(data[position:position + 2], 'big')
        if number not in dictionary:
            dictionary.append(number)
        return number, position + 2
    if position >= end:
        die('ob_s3.bin: a gauge reference runs past the records')
    index = data[position]
    if index >= len(dictionary):
        die('ob_s3.bin: gauge reference %d is not in the dictionary' % index)
    return dictionary[index], position + 1


def meter_varint(data, end, position):
    """Read one variable-length integer of the meter file."""
    digits = 0
    shift = 0
    while True:
        if position >= end:
            die('ob_s3.bin: a value runs past the records')
        byte = data[position]
        position += 1
        digits |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    return digits, position


# ---------------------------------------------------------- office containers


def zip_member(data_dir, name, member):
    """Return the bytes of one member of a container file."""
    try:
        archive = zipfile.ZipFile(os.path.join(data_dir, name))
    except (OSError, zipfile.BadZipFile) as exc:
        die('%s: %s' % (name, exc))
    with archive:
        try:
            return archive.read(member)
        except KeyError as exc:
            die('%s: %s' % (name, exc))


def docx_tables(data_dir, name):
    try:
        root = ET.fromstring(zip_member(data_dir, name, 'word/document.xml'))
    except ET.ParseError as exc:
        die('%s: %s' % (name, exc))
    body = root.find('{%s}body' % WORD_NS)
    if body is None:
        die('%s: no body' % name)
    tables = []
    for table in body.findall('{%s}tbl' % WORD_NS):
        rows = []
        for row in table.findall('{%s}tr' % WORD_NS):
            cells = []
            for cell in row.findall('{%s}tc' % WORD_NS):
                cells.append(''.join(node.text or '' for node in
                                     cell.iter('{%s}t' % WORD_NS)))
            rows.append(cells)
        tables.append(rows)
    return tables


def read_schemes(data_dir):
    tables = docx_tables(data_dir, 'sc_k2.docx')
    if len(tables) < 2:
        die('sc_k2.docx: fewer than two tables')
    scheme_table, param_table = tables[0], tables[1]
    if scheme_table[0] != ['scheme', 'class', 'segment']:
        die('sc_k2.docx: the scheme table header is %r' % scheme_table[0])
    schemes = []
    for row in scheme_table[1:]:
        if len(row) != 3:
            die('sc_k2.docx: a scheme row has %d cells' % len(row))
        if not SCHEME_RE.match(row[0]):
            die('sc_k2.docx: %r is not a scheme code' % row[0])
        if row[2] not in SEGMENTS:
            die('sc_k2.docx: segment %r is neither commercial nor public' % row[2])
        schemes.append({'scheme': row[0], 'class': row[1], 'segment': row[2]})
    if not schemes:
        die('sc_k2.docx: no schemes')
    if param_table[0] != ['basin', 'damping_percent', 'patience', 'round_budget']:
        die('sc_k2.docx: the parameter table header is %r' % param_table[0])
    params = read_params(param_table)
    return schemes, params


def read_params(table):
    params = {}
    for row in table[1:]:
        if len(row) != 4:
            die('sc_k2.docx: a parameter row has %d cells' % len(row))
        basin = row[0]
        if basin not in BASINS:
            die('sc_k2.docx: %r is not a basin' % basin)
        if basin in params:
            die('sc_k2.docx: basin %s occurs twice' % basin)
        where = 'sc_k2.docx row of %s' % basin
        damping = parse_int(row[1], where + ' damping_percent')
        patience = parse_int(row[2], where + ' patience')
        budget = parse_int(row[3], where + ' round_budget')
        if not 1 <= damping <= 100:
            die('%s: damping_percent %d is outside 1 to 100' % (where, damping))
        if patience < 1:
            die('%s: patience %d is not positive' % (where, patience))
        if budget < 1:
            die('%s: round_budget %d is not positive' % (where, budget))
        params[basin] = {'damping_percent': damping, 'patience': patience,
                         'round_budget': budget}
    for basin in BASINS:
        if basin not in params:
            die('sc_k2.docx: no row for basin %s' % basin)
    return params


def xlsx_sheets(data_dir, name):
    """Return the sheets of a workbook as lists of rows of cell values."""
    try:
        archive = zipfile.ZipFile(os.path.join(data_dir, name))
    except (OSError, zipfile.BadZipFile) as exc:
        die('%s: %s' % (name, exc))
    with archive:
        names = archive.namelist()
        shared = []
        if 'xl/sharedStrings.xml' in names:
            shared = shared_strings(archive, name)
        try:
            workbook = ET.fromstring(archive.read('xl/workbook.xml'))
            rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        except (ET.ParseError, KeyError) as exc:
            die('%s: %s' % (name, exc))
        targets = dict((rel.get('Id'), rel.get('Target')) for rel in rels)
        sheets = []
        for element in workbook.iter('{%s}sheet' % MAIN_NS):
            title = element.get('name')
            link = element.get('{http://schemas.openxmlformats.org/'
                              'officeDocument/2006/relationships}id')
            target = targets.get(link)
            if target is None:
                die('%s: sheet %s has no part' % (name, title))
            part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            if part not in names:
                die('%s: %s is missing' % (name, part))
            sheets.append((title, parse_sheet(archive.read(part), shared, name)))
    return sheets


def shared_strings(archive, name):
    try:
        root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    except (ET.ParseError, KeyError) as exc:
        die('%s: %s' % (name, exc))
    strings = []
    for item in root.iter('{%s}si' % MAIN_NS):
        strings.append(''.join(node.text or '' for node in
                               item.iter('{%s}t' % MAIN_NS)))
    return strings


def parse_sheet(xml, shared, name):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        die('%s: %s' % (name, exc))
    rows = []
    order = []
    for element in root.iter('{%s}row' % MAIN_NS):
        order.append(parse_int(element.get('r') or '0', name))
        rows.append(sheet_row(element, shared, name))
    return [row for _, row in sorted(zip(order, rows), key=lambda pair: pair[0])]


def sheet_row(element, shared, name):
    values = []
    for cell in element.iter('{%s}c' % MAIN_NS):
        column = 0
        match = re.match(r'^([A-Z]+)', cell.get('r') or '')
        if match:
            for letter in match.group(1):
                column = column * 26 + ord(letter) - 64
        while len(values) < column - 1:
            values.append(None)
        values.append(cell_value(cell, shared, name))
    return values


def cell_value(cell, shared, name):
    kind = cell.get('t')
    if kind == 'inlineStr':
        inline = cell.find('{%s}is' % MAIN_NS)
        if inline is None:
            return ''
        return ''.join(node.text or '' for node in inline.iter('{%s}t' % MAIN_NS))
    value = cell.find('{%s}v' % MAIN_NS)
    if value is None:
        return ''
    text = value.text or ''
    if kind == 's':
        index = parse_int(text, name)
        if index >= len(shared):
            die('%s: shared string %d is missing' % (name, index))
        return shared[index]
    if re.match(r'^-?\d+$', text):
        return int(text)
    return text


def read_head_offsets(data_dir):
    for title, rows in xlsx_sheets(data_dir, 'tab_h3.xlsx'):
        if title == 'offset':
            return offset_table(rows, 'tab_h3.xlsx')
    die('tab_h3.xlsx: no sheet named offset')


def offset_table(rows, name):
    if not rows:
        die('%s: the offset sheet is empty' % name)
    table = {}
    for row in rows[1:]:
        if len(row) < 2:
            die('%s: an offset row has %d cells' % (name, len(row)))
        share, offset = row[0], row[1]
        if not isinstance(share, str) or not re.match(r'^\d\.\d\d$', share):
            die('%s: %r is not a share with two decimals' % (name, share))
        if not isinstance(offset, int):
            die('%s: the offset of %s is not a whole number' % (name, share))
        table[share] = offset
    if not table:
        die('%s: the offset sheet has no rows' % name)
    return table


def read_loss_rates(data_dir):
    lines = pdf_lines(data_dir, 'mt_loss.pdf')
    header = None
    for index, line in enumerate(lines):
        if line.split() == ['segment', 'revised_on', 'rate_milli']:
            header = index
            break
    if header is None:
        die('mt_loss.pdf: no rate table header line')
    rates = []
    for line in lines[header + 1:]:
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 3:
            die('mt_loss.pdf: %r is not a rate row' % line)
        if fields[0] not in SEGMENTS:
            die('mt_loss.pdf: segment %r is neither commercial nor public' % fields[0])
        parse_date(fields[1], 'mt_loss.pdf')
        rates.append({'segment': fields[0], 'revised_on': fields[1],
                      'rate_milli': parse_int(fields[2], 'mt_loss.pdf rate_milli')})
    if not rates:
        die('mt_loss.pdf: the rate table has no rows')
    return rates


def pdf_lines(data_dir, name):
    """Return the text lines of every content stream of a PDF, in file order."""
    data = read_bytes(data_dir, name)
    lines = []
    for match in re.finditer(rb'obj(.*?)endobj', data, re.S):
        body = match.group(1)
        head = re.search(rb'stream\r?\n', body)
        if not head:
            continue
        raw = stream_bytes(body, head.end())
        if raw is None:
            die('%s: a stream has no end' % name)
        if b'FlateDecode' in body[:head.start()]:
            try:
                raw = zlib.decompress(raw)
            except zlib.error as exc:
                die('%s: %s' % (name, exc))
        lines.extend(content_lines(raw))
    return lines


def stream_bytes(body, start):
    """Return the bytes of one PDF stream, using its length when it has one."""
    head = re.search(rb'/Length\s+(\d+)(\s|>>)', body[:start])
    if head is not None:
        return body[start:start + int(head.group(1))]
    tail = re.search(rb'\r?\nendstream', body[start:])
    if tail is None:
        return None
    return body[start:start + tail.start()]


def content_lines(stream):
    lines = []
    buffer = []
    position = 0
    length = len(stream)
    while position < length:
        char = stream[position:position + 1]
        if char == b'(':
            text, position = pdf_string(stream, position)
            buffer.append(text)
            continue
        if stream.startswith(b'T*', position) or stream.startswith(b'ET', position):
            lines.append(''.join(buffer))
            buffer = []
            position += 2
            continue
        if (stream.startswith(b'Td', position) or stream.startswith(b'TD', position)
                or stream.startswith(b'BT', position) or char in b"'\""):
            lines.append(''.join(buffer))
            buffer = []
            position += 1 if char in b"'\"" else 2
            continue
        position += 1
    lines.append(''.join(buffer))
    return [line for line in lines if line]


def pdf_string(stream, position):
    position += 1
    out = bytearray()
    depth = 1
    while depth:
        if position >= len(stream):
            break
        char = stream[position]
        position += 1
        if char in b'\\':
            if position >= len(stream):
                break
            escape = stream[position]
            position += 1
            simple = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8,
                      ord('f'): 12}
            if escape in simple:
                out.append(simple[escape])
            elif 48 <= escape <= 55:
                digits = chr(escape)
                while len(digits) < 3 and position < len(stream) \
                        and 48 <= stream[position] <= 55:
                    digits += chr(stream[position])
                    position += 1
                out.append(int(digits, 8) & 0xFF)
            else:
                out.append(escape)
        elif char in b'(':
            depth += 1
            out.append(char)
        elif char in b')':
            depth -= 1
            if depth:
                out.append(char)
        else:
            out.append(char)
    return out.decode('latin-1'), position


# ------------------------------------------------------------- gauging inputs


def read_gaugings(data_dir):
    """Return the gauging records of the three exports, in read order."""
    records = []
    seen = set()
    for row in read_table(data_dir, 'gx_a.csv', ',',
                          ('gauging_id', 'licence', 'from_stn', 'to_stn', 'sense')):
        sense = row['sense']
        if sense not in SENSE_POINTS:
            die('gx_a.csv: sense %r is neither fwd, rev nor nil' % sense)
        records.append(check_gauging(row['gauging_id'], row['licence'],
                                     row['from_stn'], row['to_stn'], sense, seen,
                                     'gx_a.csv'))
    for row in read_table(data_dir, 'gx_b.tsv', '\t',
                          ('gid', 'lic', 'upper', 'lower', 'drawn_upper')):
        key = row['drawn_upper']
        if key not in DRAWN_UPPER_SENSE:
            die('gx_b.tsv: drawn_upper %r is neither 1, 0 nor 0.5' % key)
        records.append(check_gauging(row['gid'], row['lic'], row['upper'],
                                     row['lower'], DRAWN_UPPER_SENSE[key], seen,
                                     'gx_b.tsv'))
    for number, line in enumerate(read_text(data_dir, 'gx_c.jsonl').splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            die('gx_c.jsonl line %d: %s' % (number, exc))
        if not isinstance(item, dict):
            die('gx_c.jsonl line %d: not a JSON object' % number)
        ends = item.get('ends')
        if not isinstance(ends, list) or len(ends) != 2:
            die('gx_c.jsonl line %d: ends is not a pair' % number)
        drawn = item.get('drawn_by')
        if drawn not in DRAWN_BY_SENSE:
            die('gx_c.jsonl line %d: drawn_by %r is neither from, to nor neither'
                % (number, drawn))
        records.append(check_gauging(item.get('id'), item.get('licence'), ends[0],
                                     ends[1], DRAWN_BY_SENSE[drawn], seen,
                                     'gx_c.jsonl line %d' % number))
    return records


def check_gauging(gid, licence, from_stn, to_stn, sense, seen, where):
    if not isinstance(gid, str) or not GAUGING_RE.match(gid):
        die('%s: %r is not a gauging id' % (where, gid))
    if gid in seen:
        die('%s: gauging id %s occurs twice' % (where, gid))
    seen.add(gid)
    if not isinstance(licence, str) or not licence:
        die('%s: gauging %s has no licence' % (where, gid))
    for code in (from_stn, to_stn):
        if not isinstance(code, str) or not STN_RE.match(code):
            die('%s: %r is not a station code' % (where, code))
    return {'gauging_id': gid, 'licence': licence, 'from_stn': from_stn,
            'to_stn': to_stn, 'sense': sense}


def read_revisions(data_dir, cutoff, known):
    """Split the revision log into applying and later lines."""
    lines = read_table(data_dir, 'rv_log.psv', '|', ('seq', 'gauging_id', 'action',
                                                     'value'))
    seen = set()
    applying = []
    later = 0
    unmatched = 0
    for row in lines:
        seq = parse_int(row['seq'], 'rv_log.psv seq')
        if seq < 1:
            die('rv_log.psv: seq %d is not positive' % seq)
        if seq in seen:
            die('rv_log.psv: seq %d occurs twice' % seq)
        seen.add(seq)
        action, value = row['action'], row['value']
        gid = row['gauging_id']
        if action == 'void':
            if value:
                die('rv_log.psv: void revision %d has a value' % seq)
        elif action == 'sense':
            if value not in SENSE_POINTS:
                die('rv_log.psv: sense revision %d gives %r' % (seq, value))
        else:
            die('rv_log.psv: action %r is neither sense nor void' % action)
        if seq > cutoff:
            later += 1
            continue
        if gid not in known:
            unmatched += 1
            continue
        applying.append((seq, gid, action, value))
    applying.sort(key=lambda item: item[0])
    return applying, later, unmatched


def net_gaugings(records, applying):
    """Apply the revisions and return the net gaugings, voided ones left out."""
    state = {}
    for seq, gid, action, value in applying:
        state[gid] = (seq, action, value)
    nets = []
    voided = 0
    for record in records:
        gid = record['gauging_id']
        sense = record['sense']
        revision = state.get(gid)
        if revision is not None:
            if revision[1] == 'void':
                voided += 1
                continue
            sense = revision[2]
        nets.append(dict(record, sense=sense))
    nets.sort(key=lambda record: record['gauging_id'])
    return nets, voided


def read_licences(data_dir):
    text = read_text(data_dir, 'lc_register.json')
    try:
        book = json.loads(text)
    except json.JSONDecodeError as exc:
        die('lc_register.json: %s' % exc)
    if not isinstance(book, dict) or not isinstance(book.get('licences'), list):
        die('lc_register.json: no licences list')
    licences = {}
    for item in book['licences']:
        if not isinstance(item, dict):
            die('lc_register.json: a licence is not an object')
        code, scheme = item.get('licence'), item.get('scheme')
        if not isinstance(code, str) or not code:
            die('lc_register.json: a licence has no code')
        if not isinstance(scheme, str) or not SCHEME_RE.match(scheme):
            die('lc_register.json: %r is not a scheme code' % scheme)
        if code in licences:
            die('lc_register.json: licence %s occurs twice' % code)
        parse_date(str(item.get('date')), 'lc_register.json licence %s' % code)
        licences[code] = {'licence': code, 'scheme': scheme,
                          'date': str(item.get('date'))}
    if not licences:
        die('lc_register.json: no licences')
    return licences


def read_prior(data_dir):
    text = read_text(data_dir, 'prior_balance.json')
    try:
        book = json.loads(text)
    except json.JSONDecodeError as exc:
        die('prior_balance.json: %s' % exc)
    if not isinstance(book, dict):
        die('prior_balance.json: not a JSON object')
    return book


# -------------------------------------------------------------- the pipeline


class Season:
    """One extract: its inputs, its balanced storages and its losses."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.label, self.cutoff = read_config(data_dir)
        self.stations = read_register(data_dir)
        self.basin_map = read_basin_map(data_dir)
        self.crosswalk = read_crosswalk(data_dir)
        self.reads, self.corrections, self.replacements = read_meter(data_dir)
        self.schemes, self.params = read_schemes(data_dir)
        self.offsets = read_head_offsets(data_dir)
        self.rates = read_loss_rates(data_dir)
        self.records = read_gaugings(data_dir)
        self.licences = read_licences(data_dir)
        self.prior = read_prior(data_dir)
        self.mirror = read_table(data_dir, 'stn_mirror.csv', ',',
                                 ('stn', 'station_name', 'basin', 'reading_ml'))
        self.name_of = dict((row['stn'], row['station_name']) for row in self.stations)
        self.catchment_of = dict((row['stn'], row['catchment']) for row in self.stations)
        self.code_of = {}
        for row in self.stations:
            self.code_of[row['stn']] = self.station_basin(row['stn'])
        self.reading_of, self.filed = self.readings()
        self.survey, self.survey_date = self.read_survey()
        self.corrected_of = self.corrected_readings()
        self.datum_of = self.datum_offsets()
        self.opening_of = {}
        for stn in self.name_of:
            self.opening_of[stn] = self.corrected_of[stn] + \
                self.datum_of[self.catchment_of[stn]]
        self.applying, self.later, self.unmatched = read_revisions(
            data_dir, self.cutoff, set(record['gauging_id'] for record in self.records))
        self.nets, self.voided = net_gaugings(self.records, self.applying)
        self.check_gaugings()
        self.segment_of = self.segments()
        self.results = self.balance_all()
        self.losses = self.account_losses()

    def station_basin(self, stn):
        catchment = self.catchment_of[stn]
        basin = self.basin_map.get(catchment)
        if basin is None:
            die('bs_map.xml: catchment %s of %s is not mapped'
                % (catchment, stn))
        return basin

    def readings(self):
        """Return the meter readings of every station and its filed corrections."""
        retired = {}
        for old, new in self.replacements:
            if old in retired:
                die('ob_s3.bin: gauge number %d is retired twice' % old)
            retired[old] = new
        reading = {}
        filed = {}
        for stn in self.name_of:
            gauge = self.crosswalk.get(stn)
            if gauge is None:
                die('xw_codes.csv: no gauge number for %s' % stn)
            number = int(GAUGE_RE.match(gauge).group(1))
            if number not in self.reads:
                die('ob_s3.bin: no reading record for %s' % gauge)
            reading[stn] = self.reads[number]
        for gauge, day, value in self.corrections:
            day_to_date(day, 'ob_s3.bin correction of G%04d' % gauge)
            target = retired.get(gauge, gauge)
            filed.setdefault(target, []).append((day, value))
        return reading, filed

    def corrected_readings(self):
        """Apply the corrections filed on or before the survey date."""
        corrected = {}
        for stn in self.name_of:
            number = int(GAUGE_RE.match(self.crosswalk[stn]).group(1))
            value = self.reading_of[stn]
            usable = [item for item in self.filed.get(number, [])
                      if day_to_date(item[0], 'ob_s3.bin') <= self.survey_date]
            if usable:
                latest = max(item[0] for item in usable)
                value = [item[1] for item in usable if item[0] == latest][-1]
            corrected[stn] = value
        return corrected

    def read_survey(self):
        rows = read_table(self.dir, 'sv_survey.csv', ',',
                          ('reach', 'surveyed_on', 'stations', 'total_ml'))
        if not rows:
            die('sv_survey.csv: no rows')
        dates = set(row['surveyed_on'] for row in rows)
        if len(dates) != 1:
            die('sv_survey.csv: the rows carry %d dates' % len(dates))
        survey = []
        for row in rows:
            stations = row['stations'].split(';')
            for stn in stations:
                if stn not in self.name_of:
                    die('sv_survey.csv: %s is not a station code of the register' % stn)
            total = parse_int(row['total_ml'], 'sv_survey.csv total_ml')
            if total % 10:
                die('sv_survey.csv: reach %s total is not a multiple of 10' % row['reach'])
            survey.append((stations, total))
        return survey, parse_date(rows[0]['surveyed_on'], 'sv_survey.csv')

    def datum_offsets(self):
        catchments = sorted(set(self.catchment_of.values()))
        rows = []
        for stations, total in self.survey:
            base = sum(self.corrected_of[stn] for stn in stations)
            rows.append(([self.catchment_of[stn] for stn in stations], total - base))
        return solve_datums(catchments, rows)

    def check_gaugings(self):
        """Check every gauging of the exports against the register rules."""
        for record in self.records:
            for end in ('from_stn', 'to_stn'):
                if record[end] not in self.name_of:
                    die('gauging %s: %s is not a station code of the register'
                        % (record['gauging_id'], record[end]))
            first = self.code_of[record['from_stn']]
            second = self.code_of[record['to_stn']]
            if first != second:
                die('gauging %s: %s and %s belong to different basins'
                    % (record['gauging_id'], record['from_stn'], record['to_stn']))
        for record in self.nets:
            if record['licence'] not in self.licences:
                die('gauging %s: licence %s is not in the register'
                    % (record['gauging_id'], record['licence']))

    def segments(self):
        segment_of = {}
        for code, licence in self.licences.items():
            segment = None
            for scheme in self.schemes:
                if scheme['scheme'] == licence['scheme']:
                    segment = scheme['segment']
            if segment is None:
                die('sc_k2.docx: no scheme %s for licence %s'
                    % (licence['scheme'], code))
            segment_of[code] = segment
        return segment_of

    def account_losses(self):
        """Return the loss in kilolitres of every net gauging."""
        losses = {}
        for record in self.nets:
            licence = self.licences[record['licence']]
            segment = self.segment_of[licence['licence']]
            rate = rate_in_force(self.rates, segment, licence['date'])
            first = self.results[self.code_of[record['from_stn']]]['storage']
            second = self.results[self.code_of[record['to_stn']]]['storage']
            stored = first[record['from_stn']] + second[record['to_stn']]
            losses[record['gauging_id']] = drop_fraction(Fraction(rate * stored, 1000))
        return losses

    def balance_all(self):
        results = {}
        for basin in BASINS:
            stns = [row['stn'] for row in self.stations if self.code_of[row['stn']] == basin]
            opening = dict((stn, self.opening_of[stn]) for stn in stns)
            gaugings = [(record['from_stn'], record['to_stn'], record['sense'])
                        for record in self.nets if self.code_of[record['from_stn']] == basin]
            params = self.params[basin]
            exit_name, rounds, damping, storage = balance_basin(
                stns, opening, gaugings, params, self.offsets)
            results[basin] = {'basin': basin, 'exit': exit_name, 'rounds': rounds,
                              'damping_percent': damping, 'stns': stns,
                              'opening': opening, 'storage': storage}
        return results


# ------------------------------------------------------------- datum offsets


def solve_datums(catchments, rows):
    """Find the one assignment of a datum offset to every catchment."""
    order = order_catchments(catchments, rows)
    slots = dict((name, index) for index, name in enumerate(order))
    constraints = []
    for names, gap in rows:
        counts = {}
        for name in names:
            counts[name] = counts.get(name, 0) + 1
        items = [(slots[name], counts[name]) for name in sorted(counts)]
        items.sort()
        low = -((-gap) // 5)
        high = (gap + 9) // 5
        constraints.append((items, low, high))
    found = []
    assign = [0] * len(order)

    def search(depth):
        if len(found) > 1:
            return
        if not feasible(constraints, assign, depth):
            return
        if depth == len(order):
            found.append(list(assign))
            return
        for value in range(-19, 20):
            assign[depth] = value
            search(depth + 1)
        assign[depth] = 0

    search(0)
    if not found:
        die('sv_survey.csv: no assignment of the datum offsets holds every row')
    if len(found) > 1:
        die('sv_survey.csv: %d assignments of the datum offsets hold every row'
            % len(found))
    return dict((name, 5 * found[0][slots[name]]) for name in catchments)


def order_catchments(catchments, rows):
    weight = dict((name, 0) for name in catchments)
    for names, _ in rows:
        for name in set(names):
            if name in weight:
                weight[name] += 1
    return sorted(catchments, key=lambda name: (-weight[name], name))


def feasible(constraints, assign, depth):
    """Say whether the constraints can still hold with depth slots assigned."""
    for items, low, high in constraints:
        total = 0
        rest = 0
        open_slots = False
        for slot, count in items:
            if slot < depth:
                total += count * assign[slot]
            else:
                rest += count
                open_slots = True
        if open_slots:
            if total + rest * 19 < low or total - rest * 19 > high:
                return False
        elif not low <= total <= high:
            return False
    return True


def rate_in_force(rates, segment, day):
    """Return the rate in force for a segment on a day."""
    best = None
    for row in rates:
        if row['segment'] != segment or row['revised_on'] >= day:
            continue
        if best is None or row['revised_on'] > best['revised_on']:
            best = row
    if best is None:
        die('mt_loss.pdf: no rate of segment %s is in force on %s' % (segment, day))
    return best['rate_milli']


# ------------------------------------------------------------------ balancing


def balance_basin(stns, opening, gaugings, params, offsets):
    """Balance one basin; return (exit, rounds, damping, storages)."""
    points, partners = draw_lists(stns, gaugings)
    keys = {}
    for stn in stns:
        if points[stn]:
            share = Fraction(sum(points[stn]), len(points[stn]))
            hundredths = round_half_away(share * 100)
            keys[stn] = '%d.%02d' % divmod(hundredths, 100)
    storage = dict(opening)
    damping = params['damping_percent']
    tally = 0
    previous = None
    seen = [tuple(storage[stn] for stn in stns)]
    index = 0
    while True:
        residual = {}
        total = 0
        for stn in stns:
            target = storage[stn]
            if partners[stn]:
                mean = Fraction(sum(storage[other] for other in partners[stn]),
                                len(partners[stn]))
                target = round_half_away(mean) + head_offset(offsets, keys[stn])
            residual[stn] = target - storage[stn]
            total += abs(residual[stn])
        if total == 0:
            return 'balanced', index, damping, storage
        if index > 0 and total >= previous:
            tally += 1
            if tally == params['patience']:
                damping = damping // 2
                tally = 0
        transfer = dict((stn, round_half_away(Fraction(residual[stn]) * damping / 100))
                        for stn in stns)
        gap = sum(transfer.values())
        if gap != 0:
            transfer[furthest(stns, residual)] -= gap
        if all(transfer[stn] == 0 for stn in stns):
            return 'stalled', index, damping, storage
        storage = dict((stn, storage[stn] + transfer[stn]) for stn in stns)
        state = tuple(storage[stn] for stn in stns)
        if state in seen:
            cycle = seen[seen.index(state):]
            low = min(cycle)
            return 'cycle', -1, damping, dict(zip(stns, low))
        seen.append(state)
        previous = total
        index += 1
        if index >= params['round_budget']:
            return 'budget', index, damping, storage


def head_offset(offsets, key):
    """Return the head offset the method table gives for a draw share."""
    if key not in offsets:
        die('tab_h3.xlsx: the offset sheet gives no offset for a share of %s' % key)
    return offsets[key]


def draw_lists(stns, gaugings):
    points = dict((stn, []) for stn in stns)
    partners = dict((stn, []) for stn in stns)
    for first, second, sense in gaugings:
        one, two = SENSE_POINTS[sense]
        points[first].append(one)
        points[second].append(two)
        partners[first].append(second)
        partners[second].append(first)
    return points, partners


def furthest(stns, residual):
    """Return the reservoir of the round furthest from its target."""
    chosen = None
    for stn in stns:
        if chosen is None or abs(residual[stn]) >= abs(residual[chosen]):
            chosen = stn
    return chosen


# ------------------------------------------------------------------- reports


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def text_bytes(lines):
    return ''.join(line + '\n' for line in lines).encode('utf-8')


def quote(field):
    return '"%s"' % field.replace('"', '""')


def escape_xml(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def basin_report(season, basin):
    result = season.results[basin]
    reservoirs = []
    transferred = 0
    storage_total = 0
    for stn in result['stns']:
        opening = season.opening_of[stn]
        balanced = result['storage'][stn]
        reservoirs.append({'stn': stn, 'station_name': season.name_of[stn],
                           'opening_ml': opening, 'balanced_ml': balanced,
                           'change': balanced - opening})
        transferred += abs(balanced - opening)
        storage_total += balanced
    return {'basin': basin, 'exit': result['exit'], 'rounds': result['rounds'],
            'damping_percent': result['damping_percent'],
            'reservoirs': reservoirs, 'transferred_ml': transferred,
            'storage_total': storage_total}


def licence_rows(season):
    """One row per licence, ordered by licence code."""
    rows = []
    for code in sorted(season.licences):
        licence = season.licences[code]
        gaugings = [record for record in season.nets if record['licence'] == code]
        loss = sum(season.losses[record['gauging_id']] for record in gaugings)
        rows.append({'licence': code, 'scheme': licence['scheme'],
                     'segment': season.segment_of[code], 'date': licence['date'],
                     'gaugings': len(gaugings), 'loss_kl': loss})
    return rows


def segment_rows(season):
    rows = []
    for segment in SEGMENTS:
        licences = [row for row in licence_rows(season) if row['segment'] == segment]
        rows.append({'segment': segment,
                     'licences': [{'licence': row['licence'], 'date': row['date'],
                                   'gaugings': row['gaugings'],
                                   'loss_kl': row['loss_kl']} for row in licences],
                     'gaugings': sum(row['gaugings'] for row in licences),
                     'loss_kl': sum(row['loss_kl'] for row in licences)})
    return dict((row['segment'], row) for row in rows)


def gauging_rows(season):
    rows = []
    for record in season.nets:
        licence = season.licences[record['licence']]
        rows.append({'gauging_id': record['gauging_id'], 'licence': record['licence'],
                     'segment': season.segment_of[record['licence']],
                     'from_stn': record['from_stn'], 'to_stn': record['to_stn'],
                     'date': licence['date'],
                     'loss_kl': season.losses[record['gauging_id']],
                     'from_points': points_text(
                         SENSE_POINTS[record['sense']][0])})
    return rows


def day_rows(licence_rows_list):
    days = {}
    for row in licence_rows_list:
        day = days.setdefault(row['date'], {'date': row['date'], 'gaugings': 0,
                                           'loss_kl': 0})
        day['gaugings'] += row['gaugings']
        day['loss_kl'] += row['loss_kl']
    return [days[key] for key in sorted(days)]


def scheme_rows(season, licences):
    rows = []
    for scheme in season.schemes:
        code = scheme['scheme']
        holders = [row for row in licences if row['scheme'] == code]
        rows.append({'scheme': code, 'segment': scheme['segment'],
                     'licences': len(holders),
                     'gaugings': sum(row['gaugings'] for row in holders),
                     'loss_kl': sum(row['loss_kl'] for row in holders)})
    rows.sort(key=lambda row: row['scheme'])
    return rows


def catchment_rows(season):
    rows = []
    for code in sorted(season.basin_map):
        members = [row['stn'] for row in season.stations
                   if season.catchment_of[row['stn']] == code]
        rows.append({'catchment': code, 'basin': season.basin_map[code],
                     'reservoirs': len(members),
                     'opening_ml': sum(season.opening_of[stn] for stn in members),
                     'balanced_ml': sum(
                         season.results[season.code_of[stn]]['storage'][stn]
                         for stn in members)})
    return rows


def mirror_mismatches(season):
    by_code = dict((row['stn'], row) for row in season.mirror)
    mismatches = 0
    for stn in season.name_of:
        row = by_code.get(stn)
        if row is None:
            mismatches += 1
            continue
        reading = parse_int(row['reading_ml'], 'stn_mirror.csv reading_ml of %s' % stn)
        if (row['station_name'] != season.name_of[stn] or row['basin'] != season.code_of[stn]
                or reading != season.reading_of[stn]):
            mismatches += 1
    return mismatches


def ledger_stations(season, reports):
    """The station ledger rows, ordered by basin then register order."""
    rows = []
    for basin in BASINS:
        for row in reports[basin]['reservoirs']:
            rows.append((basin, row['stn'], row['station_name'], row['opening_ml'],
                         row['balanced_ml'], row['change']))
    return rows


def band_lines(season, reports):
    lines = []
    for basin in BASINS:
        counts = {}
        for row in reports[basin]['reservoirs']:
            band = row['balanced_ml'] // 250 * 250
            counts[band] = counts.get(band, 0) + 1
        for band in sorted(counts):
            lines.append('%s %d-%d %d' % (basin, band, band + 249, counts[band]))
    return lines


def brief_lines(season, reports):
    lines = ['# Season %s balancing' % season.label, '',
             '| Basin | Exit | Rounds | Damping | Transferred ML |',
             '|---|---|---|---|---|']
    for basin in BASINS:
        row = reports[basin]
        lines.append('| %s | %s | %d | %d | %d |' % (
            basin, row['exit'], row['rounds'], row['damping_percent'],
            row['transferred_ml']))
    return lines


def exit_lines(season, reports):
    lines = ['season: %s' % season.label, 'basins:']
    for basin in BASINS:
        row = reports[basin]
        lines.append('  %s:' % basin)
        lines.append('    exit: %s' % row['exit'])
        lines.append('    rounds: %d' % row['rounds'])
        lines.append('    damping_percent: %d' % row['damping_percent'])
        lines.append('    transferred_ml: %d' % row['transferred_ml'])
    return lines


def index_lines(season):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<stations season="%s">' % escape_xml(season.label)]
    for row in season.stations:
        stn = row['stn']
        lines.append('  <station stn="%s" gauge="%s" catchment="%s" basin="%s">%s</station>'
                     % (escape_xml(stn), escape_xml(season.crosswalk[stn]),
                        escape_xml(row['catchment']),
                        escape_xml(season.code_of[stn]),
                        escape_xml(row['station_name'])))
    lines.append('</stations>')
    return lines


def prior_report(season, summary, reports):
    prior = season.prior
    basins = {}
    for basin in BASINS:
        entry = prior.get('basins', {}).get(basin, {})
        basins[basin] = {'prior_exit': entry.get('exit'),
                         'exit': reports[basin]['exit'],
                         'prior_rounds': entry.get('rounds'),
                         'rounds': reports[basin]['rounds']}
    return {'prior_season': prior.get('season'),
            'transferred_ml_total': delta(prior.get('transferred_ml_total'),
                                          summary['transferred_ml_total']),
            'loss_kl_total': delta(prior.get('loss_kl_total'),
                                   summary['loss_kl_total']),
            'basins': basins}


def delta(prior, current):
    if not isinstance(prior, int) or not isinstance(current, int):
        die('prior_balance.json: a figure is not an integer')
    return {'prior': prior, 'current': current, 'difference': current - prior}


def sqlite_rows(season, reports, ledger):
    basins = []
    for basin in BASINS:
        row = reports[basin]
        basins.append((basin, row['exit'], row['rounds'], row['damping_percent'],
                       row['transferred_ml']))
    reservoirs = [(row[0], row[1], row[3], row[4], row[5]) for row in ledger]
    return basins, reservoirs


def build_reports(season):
    """Return every report of the season as bytes, keyed by file name."""
    reports = dict((basin, basin_report(season, basin)) for basin in BASINS)
    licences = licence_rows(season)
    segments = segment_rows(season)
    gaugings = gauging_rows(season)
    days = day_rows(licences)
    ledger = ledger_stations(season, reports)
    summary = {
        'season': season.label,
        'basins': dict((basin, {'exit': reports[basin]['exit'],
                                'rounds': reports[basin]['rounds']}) for basin in BASINS),
        'transferred_ml_total': sum(reports[b]['transferred_ml'] for b in BASINS),
        'loss_kl_total': sum(segments[s]['loss_kl'] for s in SEGMENTS),
        'gaugings_net': len(gaugings),
        'reservoirs': len(season.stations)}
    out = {'summary.json': json_bytes(summary),
           'policy_audit.json': json_bytes(policy_report(season)),
           'data_quality.json': json_bytes(quality_report(season))}
    for basin in BASINS:
        out['region_%s.json' % basin] = json_bytes(reports[basin])
        out['basin_%s.tsv' % basin] = text_bytes(basin_lines(season, basin, reports))
    for segment in SEGMENTS:
        out['segment_%s.json' % segment] = json_bytes(segments[segment])
        out['segment_%s.tsv' % segment] = text_bytes(
            segment_lines(segments[segment], gaugings))
    out['licence_losses.csv'] = text_bytes(licence_lines(licences))
    out['scheme_losses.json'] = json_bytes(
        {'schemes': scheme_rows(season, licences)})
    out['gauging_net.psv'] = text_bytes(gauging_lines(gaugings))
    out['loss_ledger.tsv'] = text_bytes(loss_lines(gaugings))
    out['loss_by_day.csv'] = text_bytes(day_lines(days))
    out['station_ledger.csv'] = text_bytes(ledger_lines(ledger))
    out['catchment_totals.csv'] = text_bytes(catchment_lines(catchment_rows(season)))
    out['storage_bands.txt'] = text_bytes(band_lines(season, reports))
    out['season_brief.md'] = text_bytes(brief_lines(season, reports))
    out['exits.yaml'] = text_bytes(exit_lines(season, reports))
    out['station_index.xml'] = text_bytes(index_lines(season))
    out['reconciliation.json'] = json_bytes(
        reconciliation(season, reports, licences, segments, gaugings, days))
    out['prior_delta.json'] = json_bytes(prior_report(season, summary, reports))
    return out, summary, ledger, reports


def policy_report(season):
    return {'season': season.label, 'revision_cutoff': season.cutoff,
            'basins': dict((basin, dict(season.params[basin])) for basin in BASINS),
            'loss_rates': sorted(
                [{'segment': row['segment'], 'revised_on': row['revised_on'],
                  'rate_milli': row['rate_milli']} for row in season.rates],
                key=lambda row: (row['segment'], row['revised_on']))}


def quality_report(season):
    return {'gaugings_read': len(season.records),
            'revisions_applied': len(season.applying),
            'revisions_after_cutoff': season.later,
            'revisions_unmatched': season.unmatched,
            'gaugings_voided': season.voided,
            'mirror_mismatches': mirror_mismatches(season)}


def reconciliation(season, reports, licences, segments, gaugings, days):
    return {'storage': dict((basin, {
                'opening_total': sum(row['opening_ml'] for row in
                                     reports[basin]['reservoirs']),
                'balanced_total': reports[basin]['storage_total']}) for basin in BASINS),
            'loss_kl': {'by_gauging': sum(row['loss_kl'] for row in gaugings),
                        'by_licence': sum(row['loss_kl'] for row in licences),
                        'by_segment': sum(segments[s]['loss_kl'] for s in SEGMENTS),
                        'by_day': sum(row['loss_kl'] for row in days)},
            'gaugings': {'net': len(gaugings),
                         'by_licence': sum(row['gaugings'] for row in licences)}}


def basin_lines(season, basin, reports):
    lines = ['stn\tgauge_no\tcatchment\topening_ml\tbalanced_ml\tchange']
    for row in reports[basin]['reservoirs']:
        lines.append('%s\t%s\t%s\t%d\t%d\t%d' % (
            row['stn'], season.crosswalk[row['stn']],
            season.catchment_of[row['stn']], row['opening_ml'], row['balanced_ml'],
            row['change']))
    return lines


def segment_lines(segment, gaugings):
    lines = ['gauging_id\tlicence\tdate\tloss_kl']
    for row in sorted(gaugings, key=lambda row: row['gauging_id']):
        if row['segment'] == segment['segment']:
            lines.append('%s\t%s\t%s\t%d' % (row['gauging_id'], row['licence'],
                                             row['date'], row['loss_kl']))
    return lines


def licence_lines(licences):
    lines = ['licence,scheme,segment,date,gaugings,loss_kl']
    for row in licences:
        lines.append('%s,%s,%s,%s,%d,%d' % (
            row['licence'], row['scheme'], row['segment'], row['date'],
            row['gaugings'], row['loss_kl']))
    return lines


def gauging_lines(gaugings):
    lines = ['gauging_id|licence|from_stn|to_stn|from_points']
    for row in sorted(gaugings, key=lambda row: row['gauging_id']):
        lines.append('%s|%s|%s|%s|%s' % (row['gauging_id'], row['licence'],
                                        row['from_stn'], row['to_stn'],
                                        row['from_points']))
    return lines


def loss_lines(gaugings):
    lines = ['gauging_id\tlicence\tsegment\tfrom_stn\tto_stn\tloss_kl']
    for row in sorted(gaugings, key=lambda row: row['gauging_id']):
        lines.append('%s\t%s\t%s\t%s\t%s\t%d' % (
            row['gauging_id'], row['licence'], row['segment'], row['from_stn'],
            row['to_stn'], row['loss_kl']))
    return lines


def day_lines(days):
    lines = ['date,gaugings,loss_kl']
    for row in days:
        lines.append('%s,%d,%d' % (row['date'], row['gaugings'], row['loss_kl']))
    return lines


def ledger_lines(ledger):
    lines = ['basin,stn,station_name,opening_ml,balanced_ml,change']
    for basin, stn, name, opening, balanced, change in ledger:
        lines.append('%s,%s,%s,%d,%d,%d' % (basin, stn, quote(name), opening,
                                            balanced, change))
    return lines


def catchment_lines(rows):
    lines = ['catchment,basin,reservoirs,opening_ml,balanced_ml']
    for row in rows:
        lines.append('%s,%s,%d,%d,%d' % (row['catchment'], row['basin'],
                                         row['reservoirs'], row['opening_ml'],
                                         row['balanced_ml']))
    return lines


# ------------------------------------------------------------------ containers


def write_bytes(path, data):
    with open(path, 'wb') as handle:
        handle.write(data)


def write_sqlite(path, basins, reservoirs):
    if os.path.exists(path):
        os.remove(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute('CREATE TABLE basin (basin TEXT, exit TEXT, '
                            'rounds INTEGER, damping_percent INTEGER, '
                            'transferred_ml INTEGER)')
        connection.execute('CREATE TABLE reservoir (basin TEXT, stn TEXT, '
                           'opening_ml INTEGER, balanced_ml INTEGER, '
                           'change INTEGER)')
        connection.executemany('INSERT INTO basin VALUES (?,?,?,?,?)', basins)
        connection.executemany('INSERT INTO reservoir VALUES (?,?,?,?,?)', reservoirs)
        connection.commit()
    finally:
        connection.close()


def dump_sqlite(path):
    connection = sqlite3.connect(path)
    try:
        lines = []
        for row in connection.execute(
                'SELECT basin, exit, rounds, damping_percent, transferred_ml '
                'FROM basin ORDER BY rowid'):
            lines.append('|'.join(['basin'] + [str(value) for value in row]))
        for row in connection.execute(
                'SELECT basin, stn, opening_ml, balanced_ml, change '
                'FROM reservoir ORDER BY rowid'):
            lines.append('|'.join(['reservoir'] + [str(value) for value in row]))
    finally:
        connection.close()
    return ''.join(line + '\n' for line in lines)


def xlsx_rows(licences, segments):
    rows = [['licence', 'scheme', 'segment', 'date', 'gaugings', 'loss_kl']]
    for row in licences:
        rows.append([row['licence'], row['scheme'], row['segment'], row['date'],
                     row['gaugings'], row['loss_kl']])
    sheets = [('licences', rows)]
    rows = [['segment', 'gaugings', 'loss_kl']]
    for segment in SEGMENTS:
        rows.append([segment, segments[segment]['gaugings'],
                     segments[segment]['loss_kl']])
    sheets.append(('segments', rows))
    return sheets


def sheet_xml(rows):
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<worksheet xmlns="%s"><sheetData>' % MAIN_NS]
    for number, row in enumerate(rows, 1):
        cells = []
        for index, value in enumerate(row, 1):
            reference = '%s%d' % (chr(64 + index), number)
            if isinstance(value, str):
                cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>'
                             % (reference, escape_xml(value)))
            else:
                cells.append('<c r="%s"><v>%d</v></c>' % (reference, value))
        parts.append('<row r="%d">%s</row>' % (number, ''.join(cells)))
    parts.append('</sheetData></worksheet>')
    return ''.join(parts).encode('utf-8')


def write_xlsx(path, sheets):
    parts = [('xl/worksheets/sheet%d.xml' % index, sheet_xml(rows))
             for index, (_, rows) in enumerate(sheets, 1)]
    entries = [('[Content_Types].xml', content_types_xml(len(sheets))),
               ('_rels/.rels', root_rels_xml()),
               ('xl/workbook.xml', workbook_xml([name for name, _ in sheets])),
               ('xl/_rels/workbook.xml.rels',
                workbook_rels(len(sheets), 'styles.xml')),
               ('xl/styles.xml', styles_xml())] + parts
    try:
        archive = zipfile.ZipFile(path, 'w')
    except (OSError, zipfile.BadZipFile) as exc:
        die('loss_book.xlsx: %s' % exc)
    with archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)


def workbook_xml(names):
    body = ''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>'
                   % (escape_xml(name), index, index)
                   for index, name in enumerate(names, 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="%s" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"><sheets>%s</sheets></workbook>'
            % (MAIN_NS, body)).encode('utf-8')


def workbook_rels(count, styles):
    body = ''.join('<Relationship Id="rId%d" Type="http://schemas.'
                   'openxmlformats.org/officeDocument/2006/relationships/'
                   'worksheet" Target="worksheets/sheet%d.xml"/>'
                   % (index, index) for index in range(1, count + 1))
    body += ('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.'
             'org/officeDocument/2006/relationships/styles" Target="%s"/>'
             % (count + 1, styles))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships">%s</Relationships>' % body).encode('utf-8')


def content_types_xml(count):
    body = ''.join('<Override PartName="/xl/worksheets/sheet%d.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.'
                   'spreadsheetml.worksheet+xml"/>' % index
                   for index in range(1, count + 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="rels" ContentType="application/'
            'vnd.openxmlformats-package.relationships+xml"/><Default '
            'Extension="xml" ContentType="application/xml"/><Override '
            'PartName="/xl/workbook.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '%s</Types>' % body).encode('utf-8')


def styles_xml():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<styleSheet xmlns="%s"><fonts count="1"><font/></fonts>'
            '<fills count="1"><fill/></fills><borders count="1"><border/>'
            '</borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
            '<cellXfs count="1"><xf/></cellXfs></styleSheet>' % MAIN_NS).encode('utf-8')


def root_rels_xml():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
            ' Target="xl/workbook.xml"/></Relationships>').encode('utf-8')


def dump_xlsx(path, sheets):
    titles = dict((name, rows) for name, rows in sheets)
    lines = []
    for title, rows in xlsx_sheets(os.path.dirname(path) or '.', os.path.basename(path)):
        if title not in titles:
            die('loss_book.xlsx: sheet %s is not expected' % title)
        for row in rows:
            lines.append('|'.join([title] + [cell_text(cell) for cell in row]))
    return ''.join(line + '\n' for line in lines)


def cell_text(cell):
    if cell is None:
        return ''
    if isinstance(cell, int):
        return str(cell)
    return cell


# ----------------------------------------------------------------------- main


def write_all(out_dir, season, files, reports, ledger):
    """Write every report of the season into the output directory."""
    os.makedirs(out_dir, exist_ok=True)
    licences = licence_rows(season)
    segments = segment_rows(season)
    for name, data in sorted(files.items()):
        write_bytes(os.path.join(out_dir, name), data)
    basins, reservoirs = sqlite_rows(season, reports, ledger)
    write_sqlite(os.path.join(out_dir, 'balanced.sqlite'), basins, reservoirs)
    sheets = xlsx_rows(licences, segments)
    write_xlsx(os.path.join(out_dir, 'loss_book.xlsx'), sheets)
    dumps = {'balanced.sqlite': dump_sqlite(os.path.join(out_dir, 'balanced.sqlite')),
             'loss_book.xlsx': dump_xlsx(os.path.join(out_dir, 'loss_book.xlsx'), sheets)}
    digest = {}
    for name, data in files.items():
        digest[name] = hashlib.sha256(data).hexdigest()
    for name, dump in dumps.items():
        digest[name] = hashlib.sha256(dump.encode('utf-8')).hexdigest()
    if sorted(digest) != sorted(list(files) + list(dumps)):
        die('manifest: %d reports' % len(digest))
    write_bytes(os.path.join(out_dir, 'manifest.json'),
                json_bytes({'reports': digest}))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: python3 derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    try:
        season = Season(argv[1])
        files, summary, ledger, reports = build_reports(season)
    except RuleError as exc:
        sys.stderr.write('derive_report: %s\n' % exc)
        return 1
    write_all(argv[2], season, files, reports, ledger)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
