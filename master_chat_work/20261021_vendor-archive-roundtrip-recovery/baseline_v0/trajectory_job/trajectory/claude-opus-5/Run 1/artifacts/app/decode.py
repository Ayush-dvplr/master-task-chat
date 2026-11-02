"""VARC1 container codec. Reference tables are baked in; no external files
or helper modules are read at run time.
"""
import base64
import json
import sys
import zlib

_MAX_ID = 2100
_ALIAS_STREAMS = 40
_PREFIXES = ['pressure', 'voltage', 'current', 'freq', 'load', 'ticks', 'phase', 'level', 'flow', 'rms', 'peak', 'humid', 'angle', 'speed', 'power', 'temp']
_UNIT_NAMES = ['ampere', 'celsius', 'count', 'hertz', 'meter', 'pascal', 'percent', 'volt']
_REMAP_REVISIONS = frozenset([4, 5, 6, 7])

# One byte per canonical id: bits 0-2 index _UNIT_NAMES, bit 3 set means width 4.
_B_UNITW = (
    'eNodVlkWwyAIFFF25P637aRf7UuswGx0k0i+O72IpU6bGs3eKT5MnmeOeS7z1k7zOXs2ldw3lVsODd+VS8fp6dzxlWNmO0JW'
    'yuYjFHYOi699T+++ptVn3+daXkpeR29K3tlrvfXVfq/DNRRXLan1ldo8p+iwlaSorm7CLW6vmo6wU9Ku47QVp1x5RwlfPpfR'
    '5M3X4lxybNuTE6px512hQv+12PoYawzpXXrmrT5n+156+5Hc9SSnfbvm2hbBtlCWVtvIPDWr0Xvq9cK1wxmyh2WpPgY4vkXv'
    'SALJOX2Z9hvZpGsohd6zXXnVkstVD/k+70xctImjaLTqLA+A2ps9LVCJ0ChFAZqexYcY4NYtT3prq9ig8AvxCxzMBqQSeLWZ'
    'zcCH3Nd7lfnxZbPGMuiqO3N0ysxyqquj++KOB5AaVL6svnOvXWFiwy+lGUT63L77XqoVijPgiC3P4n2SDmH+UvAg8ZKSURg8'
    'DVBlekRQiYafhN7uorWOX58iE4ijX+uth2sNwAcUYIJTmkxosWLZuEOZDlxpHbEEGMs0aXG6iwfQ4F58dbd6BwopPSjPBg9k'
    'sehM1jmAMQRiX71r7xcJ2O28RVSAB7wX1BdZT8EhJAE1f3JpjnsZ1BqOae+Lpsdvoe0jmE8McwTEXFd2kY/0Drz0Z5kYJ7or'
    'AAaNvibJsDiF7m2fgwF2GWZLUOxofCk0ic9iIJj94FSjVLkyOXnX6UqcgjvsQCsD5Hos3GrJZzKIOYzOY5dUAz1SArws0ea1'
    's0GOPXvZweC5jyxUTX/rPA2wthYNzH/6rQdRTyqtOapN/i6s3wVoz40dLgPR0A349uFpn4D3MpcA4+v9WA8zE4pUtEGagBmN'
    't2zZ/cJ0OUqIlsiylQU9QybSmBYyPA1C10UqSNRlgXShRsjm8cnoOPwAhwP0IaTPeTsWNJja8YbPGflcBoYIso27WEElGCw4'
    'm2B9zA1ZEOA4IBNXIQ0svlDShEGZd1UMfAF9Lwg67R+cAFre9YU0kA5kY2EYKAgFGrDcSdhhz8FZNE0H0GGYLiNkiYS8QQdv'
    'HAFwIBJFFZEqZC3MeQzoJV7NxkQBTdt0ObJS+zP8IIHjCdeHF5wskDv8FNAVoAAQ/YoBNsBAf6ATbhDABQlAG2yIcUQHMuhL'
    'si/hEWKSO+AfUBWIgw2oXqlnY3CIZjeiG3rsBnH69CBkO0PrEdAtJDow5WIqBMo2PPruSPzgOASOvl3upklWqBCs3OCzADlS'
    'EBmDZkJ6FQeiD6F89/Z1UbXhjygQS7IgXOVbw0gT8ZSGMV7JwjIK+UoV8hNhtG4pEGbhEIDAYNfrOp2IkwhCI1ak+fPjmUWD'
    'xZEADd7FNWgAfvCPxRDy8PQFx89qeR/9hK1lvG1t7CqkCWBG9vsgsODLsm/lfWh2wgKQiH7yw+2jzshILvgdzxHGfYMAFEIa'
    'yY8MgumQOghXdFFIVmv4B+rsGbgEuwdSwqTXsKrhqYVhGovruSlc4SUOD9tHCs5iv2GyRVAwFIXcwTe6FyZBzl1CjlwYFSjf'
    'bzLIAdVKFXu1BgwiIvBvYL4cF0KA/gA5Hj1p'
)

# Four remap revisions, 255 little endian uint16 canonical ids each (0 = unmapped).
_B_REVMAP = (
    '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'
)


_MODES = ('raw', 'delta', 'dict', 'reset')
SYNC = 0xAA
ESC = 0x1B
MAGIC = b'VARC1'
VERSION = 2
HEADER_SIZE = 16
TRAILER_SIZE = 4
MIN_FRAME_BYTES = 5
KNOWN_EXT_TYPES = {1: 'span', 2: 'quality', 3: 'source'}

_UNITW = None
_REVMAPS = None


class FrameDamage(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def _unitw():
    global _UNITW
    if _UNITW is None:
        _UNITW = zlib.decompress(base64.b64decode(_B_UNITW))
    return _UNITW


def _revmaps():
    global _REVMAPS
    if _REVMAPS is None:
        raw = zlib.decompress(base64.b64decode(_B_REVMAP))
        _REVMAPS = {}
        for slot, revision in enumerate(_REMAP_REVISIONS):
            table = {}
            base = slot * 255 * 2
            for key in range(1, 256):
                off = base + (key - 1) * 2
                cid = raw[off] | (raw[off + 1] << 8)
                if cid:
                    table[key] = cid
            _REVMAPS[revision] = table
    return _REVMAPS


def base_field_name(cid):
    if cid is None or not 1 <= cid <= _MAX_ID:
        return None
    return '%s_%04d' % (_PREFIXES[(cid - 1) % len(_PREFIXES)], cid)


def field_unit(cid):
    if cid is None or not 1 <= cid <= _MAX_ID:
        return None
    return _UNIT_NAMES[_unitw()[cid - 1] & 0x07]


def field_width(cid):
    if cid is None or not 1 <= cid <= _MAX_ID:
        return None
    return 4 if _unitw()[cid - 1] & 0x08 else 2


def id_for_name(name):
    if not name or '_' not in name:
        return None
    prefix, _, digits = name.rpartition('_')
    if len(digits) != 4 or not digits.isdigit():
        return None
    cid = int(digits)
    if not 1 <= cid <= _MAX_ID:
        return None
    if _PREFIXES[(cid - 1) % len(_PREFIXES)] != prefix:
        return None
    return cid


def resolve_short_key(revision, key):
    if revision in _REMAP_REVISIONS:
        return _revmaps()[revision].get(key)
    return key


def display_field_name(stream_id, cid):
    base = base_field_name(cid)
    if base is None:
        return None
    if stream_id == (cid % _ALIAS_STREAMS) + 1:
        return '%s@s%d' % (base, stream_id)
    return base


def new_state():
    return {'cumulator': 0, 'resolved': []}


def enc_uleb(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def dec_uleb(buf, pos):
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise FrameDamage('truncated_uleb128')
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            raise FrameDamage('oversized_uleb128')


def sleb_len(value):
    count = 0
    while True:
        byte = value & 0x7F
        value >>= 7
        count += 1
        if (value == 0 and not byte & 0x40) or (value == -1 and byte & 0x40):
            return count


def enc_sleb(value, width=0):
    count = max(sleb_len(value), width or 0)
    out = bytearray()
    for index in range(count):
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if index < count - 1 else 0))
    return bytes(out)


def dec_sleb(buf, pos):
    result = 0
    shift = 0
    start = pos
    while True:
        if pos >= len(buf):
            raise FrameDamage('truncated_sleb128')
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            if byte & 0x40:
                result -= 1 << shift
            return result, pos, pos - start
        if shift > 70:
            raise FrameDamage('oversized_sleb128')


def escape_body(raw):
    out = bytearray()
    for byte in raw:
        if byte == SYNC or byte == ESC:
            out.append(ESC)
            out.append(byte ^ 0x20)
        else:
            out.append(byte)
    return bytes(out)


def unescape_window(window):
    out = bytearray()
    pos = 0
    size = len(window)
    while pos < size:
        byte = window[pos]
        pos += 1
        if byte == ESC:
            if pos >= size:
                raise FrameDamage('escape_at_window_end')
            out.append(window[pos] ^ 0x20)
            pos += 1
        else:
            out.append(byte)
    return bytes(out)


def read_u16(buf, offset):
    return int.from_bytes(bytes(buf[offset:offset + 2]).ljust(2, b'\x00'), 'little')


def parse_frame(buf, offset, stream_id, revision, state, limit=None):
    """Parse one frame without mutating state. Returns (record, next, update)."""
    if limit is None:
        limit = len(buf)
    if offset + 2 > limit or buf[offset] != SYNC:
        raise FrameDamage('missing_sync')
    selector = buf[offset + 1]
    if selector & 0xE0:
        raise FrameDamage('selector_reserved_bits')
    mode = selector & 0x03
    wide = bool(selector & 0x04)
    long_key = bool(selector & 0x08)
    has_ext = bool(selector & 0x10)
    if mode != 0 and wide:
        raise FrameDamage('wide_set_on_non_raw')
    pos = offset + 2
    raw_key = None
    key_str = None
    if long_key:
        key_len, pos = dec_uleb(buf, pos)
        if key_len == 0 or pos + key_len > limit:
            raise FrameDamage('truncated_key')
        try:
            key_str = bytes(buf[pos:pos + key_len]).decode('utf-8')
        except UnicodeDecodeError:
            raise FrameDamage('key_not_utf8')
        pos += key_len
    else:
        if pos >= limit:
            raise FrameDamage('truncated_key')
        raw_key = buf[pos]
        pos += 1
    if pos >= limit:
        raise FrameDamage('truncated_fchk')
    fchk = buf[pos]
    pos += 1
    body_len, pos = dec_uleb(buf, pos)
    if pos + body_len > limit:
        raise FrameDamage('truncated_body')
    body = unescape_window(buf[pos:pos + body_len])
    pos += body_len
    if (sum(body) & 0xFF) != fchk:
        raise FrameDamage('fchk_mismatch')

    cursor = 0
    record = {'raw_key': raw_key, 'long_key': long_key, 'mode': _MODES[mode]}
    if long_key:
        record['key_str'] = key_str
    if mode == 0:
        size = 4 if wide else 2
        if len(body) - cursor < size:
            raise FrameDamage('truncated_value')
        value = int.from_bytes(body[cursor:cursor + size], 'little', signed=True)
        cursor += size
        record['wide'] = wide
        record['raw_value'] = value
        resolved = value
    elif mode == 1:
        delta, cursor, delta_len = dec_sleb(body, cursor)
        record['wide'] = None
        record['delta_raw'] = delta
        record['delta_raw_len'] = delta_len
        resolved = state['cumulator'] + delta
    elif mode == 2:
        if len(body) - cursor < 1:
            raise FrameDamage('truncated_value')
        index = body[cursor]
        cursor += 1
        record['wide'] = None
        record['dict_index'] = index
        slot = len(state['resolved']) - 1 - index
        resolved = state['resolved'][slot] if 0 <= slot < len(state['resolved']) else None
    else:
        record['wide'] = None
        resolved = None

    extensions = []
    if has_ext:
        while cursor < len(body):
            ext_type, cursor = dec_uleb(body, cursor)
            ext_len, cursor = dec_uleb(body, cursor)
            if len(body) - cursor < ext_len:
                raise FrameDamage('truncated_extension')
            extensions.append({'type': ext_type, 'hex': body[cursor:cursor + ext_len].hex()})
            cursor += ext_len
    elif cursor != len(body):
        raise FrameDamage('trailing_body_bytes')
    record['ext_present'] = has_ext
    record['extensions'] = extensions

    cid = None
    if mode != 3:
        cid = id_for_name(key_str) if long_key else resolve_short_key(revision, raw_key)
    record['field'] = display_field_name(stream_id, cid)
    record['unit'] = field_unit(cid)
    record['canonical_id'] = cid if cid is not None and 1 <= cid <= _MAX_ID else None
    record['value'] = resolved
    return record, pos, (mode, resolved)


def apply_state(state, mode, resolved):
    if mode == 3:
        state['resolved'] = []
        state['cumulator'] = 0
    else:
        state['resolved'].append(resolved)
        if resolved is not None:
            state['cumulator'] = resolved


def header_check(buf):
    if bytes(buf[0:5]) != MAGIC:
        return {'error': 'bad_magic'}
    version = buf[5] if len(buf) > 5 else 0
    if version != VERSION:
        return {'error': 'unsupported_version', 'version': version}
    for offset in (14, 15):
        if (buf[offset] if len(buf) > offset else 0) != 0:
            return {'error': 'reserved_not_zero', 'offset': offset}
    rec_count = read_u16(buf, 11)
    span = len(buf) - HEADER_SIZE - TRAILER_SIZE
    if rec_count * MIN_FRAME_BYTES > span:
        return {'error': 'record_count_overflow', 'record_count': rec_count}
    expected = zlib.crc32(bytes(buf[5:16])) & 0xFFFFFFFF
    found = int.from_bytes(bytes(buf[-TRAILER_SIZE:]), 'little')
    if expected != found:
        return {'error': 'trailer_crc_mismatch', 'expected': expected, 'found': found}
    return None


def decode_segment(buf, state=None):
    defect = header_check(buf)
    if defect is not None:
        return defect
    stream_id = read_u16(buf, 7)
    revision = buf[13]
    rec_count = read_u16(buf, 11)
    if state is None:
        state = new_state()
    limit = len(buf) - TRAILER_SIZE
    offset = HEADER_SIZE
    records = []
    for _ in range(rec_count):
        try:
            record, offset, update = parse_frame(buf, offset, stream_id, revision, state, limit)
        except FrameDamage as exc:
            return {'error': 'frame_damage', 'offset': offset, 'reason': exc.reason}
        apply_state(state, update[0], update[1])
        records.append(record)
    return {'magic_ok': True, 'version': buf[5], 'stream_id': stream_id,
            'seq_no': read_u16(buf, 9), 'revision': revision,
            'flags': {'stream_continues': bool(buf[6] & 1)},
            'record_count': rec_count, 'records': records}


def salvage_segment(buf, state=None):
    defect = header_check(buf)
    stream_id = read_u16(buf, 7)
    revision = buf[13] if len(buf) > 13 else 0
    if state is None:
        state = new_state()
    limit = max(len(buf) - TRAILER_SIZE, HEADER_SIZE)
    offset = HEADER_SIZE
    records = []
    damaged = []
    while offset < limit:
        try:
            record, nxt, update = parse_frame(buf, offset, stream_id, revision, state, limit)
        except FrameDamage as exc:
            start = offset
            reason = exc.reason
            resync = None
            probe = offset + 1
            while probe < limit:
                if buf[probe] == SYNC:
                    try:
                        parse_frame(buf, probe, stream_id, revision, state, limit)
                    except FrameDamage:
                        probe += 1
                        continue
                    resync = probe
                    break
                probe += 1
            if resync is None:
                damaged.append({'from_offset': start, 'resync_offset': limit, 'reason': reason})
                break
            damaged.append({'from_offset': start, 'resync_offset': resync, 'reason': reason})
            offset = resync
            continue
        apply_state(state, update[0], update[1])
        records.append(record)
        offset = nxt
    return {'records': records, 'damaged': damaged,
            'header_defect': defect['error'] if defect else None}


def _implied_cumulator(records):
    """The starting cumulator the document itself pins down, or None when free.

    Only a leading delta record constrains it: every other mode either carries
    its own value or anchors on the record before it.
    """
    if not records or records[0].get('mode') != 'delta':
        return None
    delta = records[0].get('delta_raw')
    value = records[0].get('value')
    if delta is None or value is None:
        return None
    return value - delta


def _document_consistent(records, cumulator, pool):
    """True when every record's resolved value follows from its captured form.

    Used only to pick the starting cumulator a standalone document was decoded
    against, since a later segment may have inherited a non zero one.
    """
    pool = list(pool)
    for record in records:
        mode = record.get('mode')
        value = record.get('value')
        if mode == 'reset':
            pool = []
            cumulator = 0
            continue
        if value is None:
            return False
        if mode == 'raw':
            if record.get('raw_value') != value:
                return False
        elif mode == 'delta':
            delta = record.get('delta_raw')
            if delta is None or cumulator + delta != value:
                return False
        elif mode == 'dict':
            index = record.get('dict_index')
            if index is None:
                return False
            slot = len(pool) - 1 - index
            # An index reaching behind this segment cannot be checked here.
            if 0 <= slot < len(pool) and pool[slot] != value:
                return False
        else:
            return False
        pool.append(value)
        cumulator = value
    return True


def _fit_signed(value, size):
    limit = 1 << (size * 8 - 1)
    return -limit <= value < limit


def encode_frame(record, state, revision):
    mode = _MODES.index(record.get('mode') or 'raw')
    extensions = record.get('extensions') or []
    has_ext = bool(record.get('ext_present')) or bool(extensions)
    long_key = bool(record.get('long_key'))
    raw_key = record.get('raw_key')
    key_str = record.get('key_str')
    value = record.get('value')
    wide = bool(record.get('wide'))
    body = bytearray()

    if mode == 0:
        raw_value = record.get('raw_value')
        if raw_value is None or raw_value != value:
            # New or changed: canonical shortest form is the narrowest that fits.
            raw_value = int(value if value is not None else 0)
            wide = not _fit_signed(raw_value, 2)
        raw_value = int(raw_value)
        size = 4 if wide else 2
        if not _fit_signed(raw_value, size):
            size = 4
            wide = True
        if not _fit_signed(raw_value, 4):
            raw_value = ((raw_value + (1 << 31)) % (1 << 32)) - (1 << 31)
        body += raw_value.to_bytes(size, 'little', signed=True)
        resolved = raw_value
    elif mode == 1:
        cumulator = state['cumulator']
        delta = record.get('delta_raw')
        width = record.get('delta_raw_len') or 0
        if delta is None or (value is not None and cumulator + delta != value):
            delta = int(value if value is not None else cumulator) - cumulator
            width = 0  # shortest form for a new or changed delta
        body += enc_sleb(int(delta), int(width))
        resolved = cumulator + int(delta)
    elif mode == 2:
        pool = state['resolved']
        index = record.get('dict_index')
        slot = len(pool) - 1 - index if index is not None else -1
        verifiable = 0 <= slot < len(pool)
        if index is None or (verifiable and value is not None
                             and pool[slot] != value):
            index = next((back for back in range(len(pool))
                          if pool[len(pool) - 1 - back] == value), index or 0)
        body.append(int(index) & 0xFF)
        slot = len(pool) - 1 - index
        resolved = pool[slot] if 0 <= slot < len(pool) else value
    else:
        resolved = None

    for ext in extensions:
        payload = bytes.fromhex(ext.get('hex') or '')
        body += enc_uleb(int(ext['type']))
        body += enc_uleb(len(payload))
        body += payload

    if not long_key and raw_key is None:
        cid = record.get('canonical_id')
        if cid is None:
            cid = id_for_name(record.get('field'))
        if cid is not None and revision not in _REMAP_REVISIONS and cid <= 0xFF:
            raw_key = cid
        else:
            long_key = True
            key_str = key_str or base_field_name(cid) or ''

    frame = bytearray()
    frame.append(SYNC)
    selector = mode
    if mode == 0 and wide:
        selector |= 0x04
    if long_key:
        selector |= 0x08
    if has_ext:
        selector |= 0x10
    frame.append(selector)
    if long_key:
        text = (key_str or '').encode('utf-8')
        frame += enc_uleb(len(text))
        frame += text
    else:
        frame.append(int(raw_key) & 0xFF)
    escaped = escape_body(bytes(body))
    frame.append(sum(body) & 0xFF)
    frame += enc_uleb(len(escaped))
    frame += escaped
    apply_state(state, mode, resolved)
    return bytes(frame)


def encode_segment(document, state=None):
    records = document.get('records') or []
    revision = int(document.get('revision') or 0)
    seq_no = int(document.get('seq_no') or 0)
    header = bytearray(MAGIC)
    header.append(int(document.get('version') or VERSION) & 0xFF)
    header.append(1 if (document.get('flags') or {}).get('stream_continues') else 0)
    header += (int(document.get('stream_id') or 0) & 0xFFFF).to_bytes(2, 'little')
    header += (seq_no & 0xFFFF).to_bytes(2, 'little')
    header += (len(records) & 0xFFFF).to_bytes(2, 'little')
    header.append(revision & 0xFF)
    header += b'\x00\x00'
    if state is None:
        # A fresh decode anchors at zero; a streamed later segment may have
        # inherited a non zero cumulator, which its leading delta pins down.
        #
        # When a later segment opens with a delta and nothing downstream
        # depends on it, "unmodified segment that inherited cumulator V-D" and
        # "segment whose leading value was edited, anchored at zero" produce an
        # identical document. Byte for byte reproduction is the stronger
        # contract, so the inherited reading wins: zero is tried first, and the
        # implied anchor is used only when zero contradicts the document.
        candidates = [0]
        if seq_no:
            implied = _implied_cumulator(records)
            if implied:
                candidates.append(implied)
        cumulator = next((c for c in candidates
                          if _document_consistent(records, c, [])), 0)
        work = {'cumulator': cumulator, 'resolved': []}
    else:
        work = {'cumulator': state['cumulator'],
                'resolved': list(state['resolved'])}
    out = bytearray(header)
    for record in records:
        out += encode_frame(record, work, revision)
    out += (zlib.crc32(bytes(header[5:16])) & 0xFFFFFFFF).to_bytes(4, 'little')
    return bytes(out)


def _read_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read()


def _segment_paths(manifest):
    paths = []
    for entry in manifest.get('segments') or []:
        paths.append(entry if isinstance(entry, str) else entry['path'])
    return paths


def main(argv):
    try:
        if len(argv) == 3 and argv[1] == '--stream':
            with open(argv[2], 'r', encoding='utf-8') as handle:
                manifest = json.load(handle)
            states = {}
            documents = []
            for path in _segment_paths(manifest):
                buf = _read_bytes(path)
                stream_id = read_u16(buf, 7)
                state = states.get(stream_id)
                if state is None:
                    state = new_state()
                    states[stream_id] = state
                documents.append(decode_segment(buf, state))
            print(json.dumps({'segments': documents}))
        elif len(argv) == 3 and argv[1] == '--salvage':
            print(json.dumps(salvage_segment(_read_bytes(argv[2]))))
        elif len(argv) == 2:
            print(json.dumps(decode_segment(_read_bytes(argv[1]))))
        else:
            print(json.dumps({'error': 'usage'}))
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'error': 'unreadable_input', 'detail': str(exc)}))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
