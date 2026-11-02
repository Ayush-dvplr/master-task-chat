

# =========================================================================== #
# Seeds (the sample tier regenerates the visible catalog; the eval tier is     #
# built only here). SAMPLE_SEED mirrors the generator SEED.                    #
# =========================================================================== #
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

SAMPLE_SEED = SEED
CHALLENGE_SEED = SEED ^ 0x5EED5EED
EVAL_SEED = 0x5641524345564C31

SCHEMA, _LAYOUTS, _SYMROWS, _REVISIONS = build_schema()
_LONG = {name: cid for (cid, name, unit, width) in _LAYOUTS}


# --------------------------------------------------------------------------- #
# record builders for constructed hidden cases                                #
# --------------------------------------------------------------------------- #
def _r_raw(key, value, wide=True, long_key=False, ext=None):
    rec = {"raw_key": None if long_key else key, "long_key": long_key, "mode": "raw",
           "wide": wide, "raw_value": value, "value": value,
           "ext_present": bool(ext), "extensions": ext or []}
    if long_key:
        rec["key_str"] = key
    return rec


def _r_delta(key, delta, length=None, long_key=False, ext=None):
    rec = {"raw_key": None if long_key else key, "long_key": long_key, "mode": "delta",
           "wide": None, "delta_raw": delta, "value": None,
           "ext_present": bool(ext), "extensions": ext or []}
    if length is not None:
        rec["delta_raw_len"] = length
    if long_key:
        rec["key_str"] = key
    return rec


def _r_dict(key, index, long_key=False, ext=None):
    rec = {"raw_key": None if long_key else key, "long_key": long_key, "mode": "dict",
           "wide": None, "dict_index": index, "value": None,
           "ext_present": bool(ext), "extensions": ext or []}
    if long_key:
        rec["key_str"] = key
    return rec


def _r_reset():
    return {"raw_key": 0, "long_key": False, "mode": "reset", "wide": None,
            "value": None, "ext_present": False, "extensions": []}


def _seg(stream_id, seq_no, revision, records, cont=False):
    return {"stream_id": stream_id, "seq_no": seq_no, "revision": revision,
            "flags": {"stream_continues": cont}, "record_count": len(records),
            "records": records}


# --------------------------------------------------------------------------- #
# subprocess runners (agent code, unprivileged where possible, group killed)   #
# --------------------------------------------------------------------------- #
_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"}


def _wrap(ws, program, extra):
    base = [sys.executable, "-I", str(Path(ws) / program)]
    if os.name == "posix" and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", *base, *extra]
    return [*base, *extra]


def _run(cmd, timeout=60):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=tempfile.gettempdir(), start_new_session=True, env=_ENV)
    except Exception:
        return None, b""
    try:
        out, _err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass
        return None, b""
    return proc.returncode, out


def _decode(ws, buf):
    with tempfile.NamedTemporaryFile(suffix=".varc", delete=False) as fh:
        fh.write(buf)
        path = fh.name
    try:
        rc, out = _run(_wrap(ws, "decode.py", [path]))
        if rc != 0:
            return None
        return json.loads(out.decode("utf-8"))
    except Exception:
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _salvage(ws, buf):
    with tempfile.NamedTemporaryFile(suffix=".varc", delete=False) as fh:
        fh.write(buf)
        path = fh.name
    try:
        rc, out = _run(_wrap(ws, "decode.py", ["--salvage", path]))
        if rc != 0:
            return None
        return json.loads(out.decode("utf-8"))
    except Exception:
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _stream(ws, bufs):
    paths = []
    tmp = tempfile.mkdtemp()
    try:
        for i, buf in enumerate(bufs):
            p = os.path.join(tmp, f"seg_{i}.varc")
            with open(p, "wb") as fh:
                fh.write(buf)
            paths.append(p)
        man = os.path.join(tmp, "manifest.json")
        with open(man, "w") as fh:
            json.dump({"segments": [{"path": p} for p in paths]}, fh)
        rc, out = _run(_wrap(ws, "decode.py", ["--stream", man]))
        if rc != 0:
            return None
        return json.loads(out.decode("utf-8"))
    except Exception:
        return None


def _encode(ws, doc):
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "doc.json")
        dst = os.path.join(tmp, "out.varc")
        with open(src, "w") as fh:
            json.dump(doc, fh)
        rc, _out = _run(_wrap(ws, "encode.py", [src, dst]))
        if rc != 0 or not os.path.isfile(dst):
            return None
        with open(dst, "rb") as fh:
            return fh.read()
    except Exception:
        return None


def _out_json(ws, name):
    try:
        return json.loads((Path(ws) / "out" / name).read_text(encoding="utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# constructed hidden fixtures (cached)                                         #
# --------------------------------------------------------------------------- #
_FIX = {}


def _fix(name, builder):
    if name not in _FIX:
        _FIX[name] = builder()
    return _FIX[name]


def _ext_opaque(hexbytes):
    return [{"type": 9, "hex": hexbytes}]


def fx_eval_basic():
    cases = {}
    cases["raw_wide"] = _seg(600, 0, 0, [_r_raw(10, 123456, wide=True), _r_raw(11, -654321, wide=True)])
    cases["raw_narrow"] = _seg(600, 0, 0, [_r_raw(12, 777, wide=False), _r_raw(13, -888, wide=False)])
    cases["delta"] = _seg(600, 0, 0, [_r_raw(14, 1000, wide=True), _r_delta(15, 234), _r_delta(16, -99)])
    cases["dict"] = _seg(600, 0, 0, [_r_raw(17, 42, wide=True), _r_raw(18, 43, wide=True), _r_dict(19, 1)])
    cases["reset"] = _seg(600, 0, 0, [_r_raw(20, 5, wide=True), _r_reset(), _r_raw(21, 6, wide=True)])
    cases["longkey"] = _seg(600, 0, 0, [_r_raw("temp_0016", 9, wide=True, long_key=True),
                                        _r_raw("flow_0009", 8, wide=True, long_key=True)])
    out = {}
    for k, doc in cases.items():
        payload = encode_segment(doc)
        out[k] = (payload, decode_segment(payload, SCHEMA))
    return out


def fx_va1():
    out = {}
    segA = encode_segment(_seg(700, 0, 0, [_r_raw(1, 111, wide=True), _r_raw(2, 222, wide=True),
                                           _r_raw(3, 333, wide=True)], cont=True))
    segB_dict = encode_segment(_seg(700, 1, 0, [_r_dict(4, 2)]))
    out["cross_dict"] = ([segA, segB_dict], decode_stream([segA, segB_dict], SCHEMA))
    segB_delta = encode_segment(_seg(700, 1, 0, [_r_delta(5, 7)]))
    out["cross_delta"] = ([segA, segB_delta], decode_stream([segA, segB_delta], SCHEMA))
    segA3 = encode_segment(_seg(701, 0, 0, [_r_raw(1, 10, wide=True)], cont=True))
    segB3 = encode_segment(_seg(701, 1, 0, [_r_raw(2, 20, wide=True)], cont=True))
    segC3 = encode_segment(_seg(701, 2, 0, [_r_dict(3, 1)]))
    out["three_seg"] = ([segA3, segB3, segC3], decode_stream([segA3, segB3, segC3], SCHEMA))
    return out


def fx_va2():
    out = {}
    base = _seg(620, 0, 0, [
        _r_raw(30, 100, wide=True),
        _r_raw(31, 200, wide=True, ext=_ext_opaque("00ff01")),
        _r_raw(32, 300, wide=True),
    ])
    mod = _seg(620, 0, 0, [
        _r_raw(30, 999, wide=True),
        _r_raw(31, 200, wide=True, ext=_ext_opaque("00ff01")),
        _r_raw(32, 300, wide=True),
    ])
    out["mod_bytes"] = (mod, encode_segment(mod))
    out["ext_doc"] = mod
    base2 = _seg(621, 0, 0, [
        _r_raw(40, 11, wide=True),
        _r_delta(41, 5, length=3, ext=_ext_opaque("0102")),
    ])
    mod2 = _seg(621, 0, 0, [
        _r_raw(40, 77, wide=True),
        _r_delta(41, 5, length=3, ext=_ext_opaque("0102")),
    ])
    out["untouched"] = (mod2, encode_segment(mod2))
    return out


def fx_va3():
    out = {}
    doc = _seg(630, 0, 0, [
        _r_raw(50, 0xAABB - 0x10000, wide=False),
        _r_raw(51, 7, wide=True, ext=_ext_opaque("aa1b")),
        _r_raw(52, 9, wide=True),
    ])
    payload = encode_segment(doc)
    out["case"] = (payload, decode_segment(payload, SCHEMA))
    return out


def fx_va4():
    out = {}
    unmod = _seg(640, 0, 0, [_r_raw(60, 1000, wide=True), _r_delta(61, 3, length=4)])
    out["overlong"] = (encode_segment(unmod), decode_segment(encode_segment(unmod), SCHEMA))
    mod = _seg(640, 0, 0, [_r_raw(60, 1000, wide=True), _r_delta(61, 300000)])
    out["modified"] = (mod, encode_segment(mod))
    return out


def _damage(buf, kind):
    b = bytearray(buf)
    if kind in ("bad_magic", "magic_version"):
        b[0] ^= 0xFF
    if kind in ("unsupported_version", "magic_version", "version_reserved"):
        b[5] = 9
    if kind in ("reserved_not_zero", "version_reserved", "reserved_overflow"):
        b[14] = 1
    if kind in ("record_count_overflow", "reserved_overflow", "overflow_crc"):
        struct.pack_into("<H", b, 11, 0xFFFF)
    if kind in ("trailer_crc_mismatch", "overflow_crc"):
        b[-1] ^= 0xFF
    return bytes(b)


def fx_va5():
    base = encode_segment(_seg(650, 0, 0, [_r_raw(70, 5, wide=True), _r_raw(71, 6, wide=True)]))
    pairs = {
        "magic_version": {"error": "bad_magic"},
        "version_reserved": {"error": "unsupported_version", "version": 9},
        "reserved_overflow": {"error": "reserved_not_zero", "offset": 14},
        "overflow_crc": {"error": "record_count_overflow", "record_count": 0xFFFF},
    }
    out = {k: (_damage(base, k), exp) for k, exp in pairs.items()}
    ver = _damage(base, "unsupported_version")
    out["version_fields"] = (ver, {"error": "unsupported_version", "version": 9})
    return out


def _frame_spans(buf):
    st = StreamState()
    sid = struct.unpack_from("<H", buf, 7)[0]
    rev = buf[13]
    pos = HEADER_SIZE
    end = len(buf) - TRAILER_SIZE
    spans = []
    try:
        while pos < end:
            _rec, newpos, start = parse_frame(buf, pos, st, sid, rev, SCHEMA)
            spans.append((start, newpos))
            pos = newpos
    except FrameError:
        pass
    return spans


def _corrupt_frames(buf, ordinals):
    """Flip one body byte in each named frame of the CLEAN buffer to break fchk."""
    spans = _frame_spans(buf)
    b = bytearray(buf)
    for o in ordinals:
        _s, e = spans[o]
        b[e - 2] ^= 0x01
    return bytes(b)


def fx_va6():
    out = {}
    clean = encode_segment(_seg(660, 0, 0, [
        _r_raw(80, 10, wide=True), _r_raw(81, 20, wide=True),
        _r_raw(82, 30, wide=True), _r_raw(83, 40, wide=True)]))
    damaged = _corrupt_frames(clean, [1])
    out["single"] = (damaged, salvage_one_ref(damaged))
    clean2 = encode_segment(_seg(661, 0, 0, [
        _r_raw(84, 1, wide=True), _r_raw(85, 2, wide=True), _r_raw(86, 3, wide=True),
        _r_raw(87, 4, wide=True), _r_raw(88, 5, wide=True)]))
    d2 = _corrupt_frames(clean2, [1, 3])
    out["two"] = (d2, salvage_one_ref(d2))
    clean3 = encode_segment(_seg(662, 0, 0, [
        _r_raw(0xAA, 90, wide=True), _r_raw(91, 91, wide=True), _r_raw(92, 92, wide=True)]))
    d3 = _corrupt_frames(clean3, [0])
    out["nofalse"] = (d3, salvage_one_ref(d3))
    return out


def salvage_one_ref(buf):
    return salvage(buf, SCHEMA)


def fx_heavy():
    clean = encode_segment(_seg(670, 0, 0, [
        _r_raw(95, 11, wide=True), _r_raw(96, 22, wide=True), _r_raw(97, 33, wide=True)]))
    damaged = bytearray(_corrupt_frames(clean, [1]))
    damaged[14] = 1
    damaged = bytes(damaged)
    return {"decode_expected": {"error": "reserved_not_zero", "offset": 14},
            "salvage_expected": salvage_one_ref(damaged), "buf": damaged}


def fx_compA():
    rev = 4
    raw_key = 50
    canon = SCHEMA["remap"][(rev, raw_key)]
    segA = encode_segment(_seg(680, 0, rev, [_r_raw(1, 500, wide=True), _r_raw(2, 600, wide=True)], cont=True))
    segB = encode_segment(_seg(680, 1, rev, [_r_dict(raw_key, 1, ext=_ext_opaque("aa1b"))]))
    value_doc = decode_stream([segA, segB], SCHEMA)
    unmod = _seg(681, 0, rev, [_r_raw(1, 7, wide=True), _r_delta(raw_key, 4, length=3)])
    len_doc = decode_segment(encode_segment(unmod), SCHEMA)
    modbase = _seg(682, 0, 0, [_r_raw(20, 1, wide=True, ext=_ext_opaque("aa1bcc")),
                               _r_raw(21, 2, wide=True)])
    modmod = _seg(682, 0, 0, [_r_raw(20, 999, wide=True, ext=_ext_opaque("aa1bcc")),
                              _r_raw(21, 2, wide=True)])
    allframe = _seg(683, 0, rev, [_r_raw(1, 8, wide=True),
                                  _r_delta(raw_key, 2, length=4, ext=_ext_opaque("aa1b"))])
    return {
        "value": ([segA, segB], value_doc, raw_key),
        "len": (encode_segment(unmod), len_doc, raw_key),
        "ext": (modmod, encode_segment(modmod)),
        "all": (allframe, encode_segment(allframe)),
    }


# --------------------------------------------------------------------------- #
# comparison + expected report helpers                                        #
# --------------------------------------------------------------------------- #
def _docs_equal(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(_docs_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_docs_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    return a == b


def _rec_values(doc):
    return [r.get("value") for r in doc.get("records", [])]


def _expected_catalog():
    def build():
        clean, reject, schema, layouts, symrows, revisions = build_catalog()
        return _interleave(clean, reject)
    return _fix("catalog", build)


def _expected_format_report():
    def build():
        cat = _expected_catalog()
        mode_counts = {m: 0 for m in ("raw", "delta", "dict", "reset")}
        errors = {}
        ok = err = frames = 0
        streams = set()
        names = set()
        canon = set()
        for row in cat:
            doc = decode_segment(bytes.fromhex(row["hex"]), SCHEMA)
            if "error" in doc:
                err += 1
                errors[doc["error"]] = errors.get(doc["error"], 0) + 1
                continue
            ok += 1
            streams.add(doc["stream_id"])
            frames += len(doc["records"])
            for rec in doc["records"]:
                mode_counts[rec["mode"]] += 1
                if rec["field"] is not None:
                    names.add(rec["field"])
                if rec["canonical_id"] is not None:
                    canon.add(rec["canonical_id"])
        pairs = sorted(f"{SCHEMA['id_to_name'][c]}\t{SCHEMA['id_to_unit'][c]}" for c in canon)
        return {
            "format_tag": "VARC", "magic_hex": MAGIC.hex(), "version": 2,
            "header_size": 16, "trailer_size": 4, "sync_byte": "aa", "esc_byte": "1b",
            "crc_coverage": "header", "crc_covers_offsets": [5, 15],
            "mode_ids": {"raw": 0, "delta": 1, "dict": 2, "reset": 3},
            "catalog_count": ok + err, "catalog_ok_count": ok, "catalog_error_count": err,
            "catalog_mode_counts": mode_counts, "stream_count": len(streams),
            "catalog_frame_count": frames, "catalog_errors": dict(sorted(errors.items())),
            "distinct_field_count": len(names),
            "field_name_sha256": hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest(),
            "field_unit_sha256": hashlib.sha256("\n".join(pairs).encode()).hexdigest(),
        }
    return _fix("expected_format", build)


def _holds(fn):
    try:
        return bool(fn())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# checks                                                                       #
# --------------------------------------------------------------------------- #
@criterion(description="decode.py exists at the workspace root and is not empty.")
def decoder_exists(workspace):
    p = Path(workspace) / "decode.py"
    return _holds(lambda: p.is_file() and p.stat().st_size > 0)


@criterion(description="encode.py exists at the workspace root and is not empty.")
def encoder_exists(workspace):
    p = Path(workspace) / "encode.py"
    return _holds(lambda: p.is_file() and p.stat().st_size > 0)


@criterion(description="format_report.json is present and parses as a JSON object.")
def format_report_present(workspace):
    return isinstance(_out_json(workspace, "format_report.json"), dict)


@criterion(description="roundtrip_report.json is present and parses as a JSON object.")
def roundtrip_report_present(workspace):
    return isinstance(_out_json(workspace, "roundtrip_report.json"), dict)


@criterion(description="error_analysis.json is present and parses as a JSON object.")
def error_analysis_present(workspace):
    return isinstance(_out_json(workspace, "error_analysis.json"), dict)


@criterion(description="decoded_examples.jsonl is present with at least four lines.")
def decoded_examples_present(workspace):
    def fn():
        text = (Path(workspace) / "out" / "decoded_examples.jsonl").read_text(encoding="utf-8")
        return len([ln for ln in text.splitlines() if ln.strip()]) >= 4
    return _holds(fn)


def _basic(workspace, key):
    payload, expected = fx_eval_basic()[key]
    got = _decode(workspace, payload)
    return got is not None and _docs_equal(got, expected)


@criterion(description="A wide raw record decodes to the correct signed integer.")
def basic_raw_wide(workspace):
    return _holds(lambda: _basic(workspace, "raw_wide"))


@criterion(description="A narrow raw record decodes to the correct signed integer.")
def basic_raw_narrow(workspace):
    return _holds(lambda: _basic(workspace, "raw_narrow"))


@criterion(description="A delta record decodes to cumulator plus delta.")
def basic_delta(workspace):
    return _holds(lambda: _basic(workspace, "delta"))


@criterion(description="A dict record decodes to the backward indexed prior value.")
def basic_dict(workspace):
    return _holds(lambda: _basic(workspace, "dict"))


@criterion(description="A reset record clears state and carries null value.")
def basic_reset(workspace):
    return _holds(lambda: _basic(workspace, "reset"))


@criterion(description="A long key record resolves its field name from the key text.")
def basic_longkey(workspace):
    return _holds(lambda: _basic(workspace, "longkey"))


@criterion(description="A dict index in a later segment resolves a value defined in an earlier segment of the stream.")
def va1_cross_dict(workspace):
    def fn():
        bufs, exp = fx_va1()["cross_dict"]
        got = _stream(workspace, bufs)
        return got["segments"][1]["records"][0]["value"] == exp["segments"][1]["records"][0]["value"]
    return _holds(fn)


@criterion(description="A delta in a later segment continues the cumulator from the earlier segment of the stream.")
def va1_cross_delta(workspace):
    def fn():
        bufs, exp = fx_va1()["cross_delta"]
        got = _stream(workspace, bufs)
        return got["segments"][1]["records"][0]["value"] == exp["segments"][1]["records"][0]["value"]
    return _holds(fn)


@criterion(description="A dict index in the third segment resolves a value from the first segment of the stream.")
def va1_three_seg(workspace):
    def fn():
        bufs, exp = fx_va1()["three_seg"]
        got = _stream(workspace, bufs)
        return got["segments"][2]["records"][0]["value"] == exp["segments"][2]["records"][0]["value"]
    return _holds(fn)


@criterion(description="A modified raw record re-encodes to the exact bytes with its opaque extension kept.")
def va2_modified_bytes(workspace):
    def fn():
        mod, expected = fx_va2()["mod_bytes"]
        return _encode(workspace, mod) == expected
    return _holds(fn)


@criterion(description="The opaque extension of a modified record keeps its bytes after re-encoding.")
def va2_extensions_kept(workspace):
    def fn():
        mod = fx_va2()["ext_doc"]
        got = _encode(workspace, mod)
        back = decode_segment(got, SCHEMA)
        return back["records"][1]["extensions"] == [{"type": 9, "hex": "00ff01"}]
    return _holds(fn)


@criterion(description="An untouched overlong delta keeps its byte length when another record is modified.")
def va2_untouched_preserved(workspace):
    def fn():
        mod, expected = fx_va2()["untouched"]
        return _encode(workspace, mod) == expected
    return _holds(fn)


@criterion(description="A frame whose extension ends on an escaped sync byte decodes to the correct values.")
def va3_boundary_value(workspace):
    def fn():
        payload, exp = fx_va3()["case"]
        got = _decode(workspace, payload)
        return _rec_values(got) == _rec_values(exp)
    return _holds(fn)


@criterion(description="An opaque extension carrying escaped sync bytes decodes to the correct hex.")
def va3_ext_escaped(workspace):
    def fn():
        payload, exp = fx_va3()["case"]
        got = _decode(workspace, payload)
        return got["records"][1]["extensions"] == exp["records"][1]["extensions"]
    return _holds(fn)


@criterion(description="A frame with escaped body bytes re-encodes to the exact original bytes.")
def va3_reencode(workspace):
    def fn():
        payload, _exp = fx_va3()["case"]
        got = _decode(workspace, payload)
        return _encode(workspace, got) == payload
    return _holds(fn)


@criterion(description="An unmodified non-shortest delta re-encodes to its original overlong bytes.")
def va4_overlong_bytes(workspace):
    def fn():
        payload, decoded = fx_va4()["overlong"]
        return _encode(workspace, decoded) == payload
    return _holds(fn)


@criterion(description="A non-shortest delta reports its captured byte length on decode.")
def va4_len_reported(workspace):
    def fn():
        payload, _decoded = fx_va4()["overlong"]
        got = _decode(workspace, payload)
        return got["records"][1]["delta_raw_len"] == 4
    return _holds(fn)


@criterion(description="A modified delta re-encodes in shortest form to the exact bytes.")
def va4_modified_shortest(workspace):
    def fn():
        mod, expected = fx_va4()["modified"]
        return _encode(workspace, mod) == expected
    return _holds(fn)


def _va5(workspace, key):
    buf, exp = fx_va5()[key]
    got = _decode(workspace, buf)
    return got == exp


@criterion(description="Bad magic together with a bad version reports bad_magic.")
def va5_magic_over_version(workspace):
    return _holds(lambda: _va5(workspace, "magic_version"))


@criterion(description="A bad version together with a non-zero reserved byte reports unsupported_version.")
def va5_version_over_reserved(workspace):
    return _holds(lambda: _va5(workspace, "version_reserved"))


@criterion(description="A non-zero reserved byte together with an impossible record count reports reserved_not_zero at offset 14.")
def va5_reserved_over_overflow(workspace):
    return _holds(lambda: _va5(workspace, "reserved_overflow"))


@criterion(description="An impossible record count together with a bad checksum reports record_count_overflow.")
def va5_overflow_over_crc(workspace):
    return _holds(lambda: _va5(workspace, "overflow_crc"))


@criterion(description="An unsupported version error object carries the version byte value nine.")
def va5_version_field(workspace):
    return _holds(lambda: _va5(workspace, "version_fields"))


@criterion(description="A segment with a bad header and damaged frames rejects with reserved_not_zero at offset 14.")
def heavy_decode_rejects(workspace):
    def fn():
        h = fx_heavy()
        return _decode(workspace, h["buf"]) == h["decode_expected"]
    return _holds(fn)


@criterion(description="Salvaging a segment with a bad header recovers the clean frames and names the header defect.")
def heavy_salvage_recovers(workspace):
    def fn():
        h = fx_heavy()
        got = _salvage(workspace, h["buf"])
        exp = h["salvage_expected"]
        return (got["header_defect"] == exp["header_defect"]
                and _rec_values(got) == _rec_values(exp))
    return _holds(fn)


@criterion(description="Salvage recovers the clean frames around a single damaged frame.")
def va6_single_records(workspace):
    def fn():
        buf, exp = fx_va6()["single"]
        got = _salvage(workspace, buf)
        return _rec_values(got) == _rec_values(exp)
    return _holds(fn)


@criterion(description="Salvage reports one damaged span with the correct start and resume offsets.")
def va6_single_damage(workspace):
    def fn():
        buf, exp = fx_va6()["single"]
        got = _salvage(workspace, buf)
        gp = [(d["from_offset"], d["resync_offset"]) for d in got["damaged"]]
        ep = [(d["from_offset"], d["resync_offset"]) for d in exp["damaged"]]
        return gp == ep
    return _holds(fn)


@criterion(description="Salvage reports two damaged spans and recovers the clean frames between them.")
def va6_two_spans(workspace):
    def fn():
        buf, exp = fx_va6()["two"]
        got = _salvage(workspace, buf)
        return (len(got["damaged"]) == len(exp["damaged"]) == 2
                and _rec_values(got) == _rec_values(exp))
    return _holds(fn)


@criterion(description="Salvage resumes at a real frame boundary rather than a stray sync byte in damaged data.")
def va6_no_false_resync(workspace):
    def fn():
        buf, exp = fx_va6()["nofalse"]
        got = _salvage(workspace, buf)
        gp = [(d["from_offset"], d["resync_offset"]) for d in got["damaged"]]
        ep = [(d["from_offset"], d["resync_offset"]) for d in exp["damaged"]]
        return gp == ep and _rec_values(got) == _rec_values(exp)
    return _holds(fn)


@criterion(description="A cross-segment dict value under a remapped revision resolves both the value and the field name.")
def compA_value(workspace):
    def fn():
        bufs, exp, _rk = fx_compA()["value"]
        got = _stream(workspace, bufs)
        g = got["segments"][1]["records"][0]
        e = exp["segments"][1]["records"][0]
        return g["value"] == e["value"] and g["field"] == e["field"]
    return _holds(fn)


@criterion(description="An overlong delta under a remapped revision reports both its byte length and field name.")
def compA_len(workspace):
    def fn():
        buf, exp, _rk = fx_compA()["len"]
        got = _decode(workspace, buf)
        g = got["records"][1]
        e = exp["records"][1]
        return g["delta_raw_len"] == e["delta_raw_len"] and g["field"] == e["field"]
    return _holds(fn)


@criterion(description="A modified record with an escaped-sync extension re-encodes to the exact bytes.")
def compA_ext(workspace):
    def fn():
        mod, expected = fx_compA()["ext"]
        return _encode(workspace, mod) == expected
    return _holds(fn)


@criterion(description="A frame combining a remap, an overlong delta and an escaped extension re-encodes byte for byte.")
def compA_all(workspace):
    def fn():
        doc, expected = fx_compA()["all"]
        return _encode(workspace, doc) == expected
    return _holds(fn)


@criterion(description="format_report.json matches the recovered grammar and the catalog tallies.")
def report_format(workspace):
    def fn():
        return _out_json(workspace, "format_report.json") == _expected_format_report()
    return _holds(fn)


@criterion(description="error_analysis.json states the precedence, the catalog error counts and the all_defects winner.")
def report_error_analysis(workspace):
    def fn():
        got = _out_json(workspace, "error_analysis.json")
        exp_err = _expected_format_report()["catalog_errors"]
        return (got["precedence"] == ["bad_magic", "unsupported_version", "reserved_not_zero",
                                      "record_count_overflow", "trailer_crc_mismatch"]
                and got["catalog_errors"] == exp_err
                and got["cases"]["all_defects"] == {"error": "bad_magic"})
    return _holds(fn)


@criterion(description="roundtrip_report.json records byte equality for every self-built example.")
def report_roundtrip(workspace):
    def fn():
        got = _out_json(workspace, "roundtrip_report.json")
        if got.get("all_roundtrips_equal") is not True:
            return False
        exs = got["examples"]
        return len(exs) >= 4 and all(
            e["roundtrip_equal"] is True and e["input_sha256"] == e["rebuilt_sha256"] for e in exs)
    return _holds(fn)


@criterion(description="decoded_examples.jsonl holds self-consistent examples covering all four modes with an opaque extension and a long key.")
def report_decoded_examples(workspace):
    def fn():
        text = (Path(workspace) / "out" / "decoded_examples.jsonl").read_text(encoding="utf-8")
        rows = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        if len(rows) < 4:
            return False
        modes = set()
        opaque = longkey = False
        for row in rows:
            if set(row) != {"name", "hex", "decoded"}:
                return False
            if row["name"][:3] in ("cap", "rej", "eva", "sam", "fie"):
                return False
            payload = bytes.fromhex(row["hex"])
            if decode_segment(payload, SCHEMA) != row["decoded"]:
                return False
            for rec in row["decoded"]["records"]:
                modes.add(rec["mode"])
                if rec["extensions"]:
                    opaque = True
                if rec["long_key"]:
                    longkey = True
        return modes >= {"raw", "delta", "dict", "reset"} and opaque and longkey
    return _holds(fn)


# --------------------------------------------------------------------------- #
# negatives (return True when the cheat is present; negative weight punishes)  #
# --------------------------------------------------------------------------- #
@criterion(description="Fires when the programs reproduce the visible captures but fail the fresh captures.")
def negative_hardcoded_sample_answers(workspace):
    def fn():
        cat = _expected_catalog()
        seen_ok = 0
        seen_total = 0
        for row in cat:
            doc = decode_segment(bytes.fromhex(row["hex"]), SCHEMA)
            if "error" in doc:
                continue
            seen_total += 1
            got = _decode(workspace, bytes.fromhex(row["hex"]))
            if got is not None and _docs_equal(got, doc):
                seen_ok += 1
            if seen_total >= 6:
                break
        fresh_ok = 0
        for payload, expected in fx_eval_basic().values():
            got = _decode(workspace, payload)
            if got is not None and _docs_equal(got, expected):
                fresh_ok += 1
        return seen_ok == seen_total and seen_total > 0 and fresh_ok == 0  # cheat: visible only
    return _holds(fn)


@criterion(description="Fires when the decoder returns different output for the same bytes under a different file name.")
def negative_filename_dependent_behaviour(workspace):
    def fn():
        payload, _exp = fx_eval_basic()["delta"]
        a = _decode(workspace, payload)
        b = _decode(workspace, payload)
        if a is None or b is None:
            return False
        return not _docs_equal(a, b)  # cheat: nondeterministic on identical content
    return _holds(fn)


@criterion(description="Fires when the delivered programs name the training corpus directory in their source.")
def negative_reads_training_corpus_at_runtime(workspace):
    def fn():
        needle = "/" + "app" + "/" + "data"
        for name in ("decode.py", "encode.py"):
            src = (Path(workspace) / name).read_text(encoding="utf-8", errors="ignore")
            if needle in src:
                return True
        return False
    return _holds(fn)


@criterion(description="Fires when the delivered programs rebind a standard library function the verifier relies on.")
def negative_rebinds_verifier_dependencies(workspace):
    import ast as _ast

    def targets(node):
        found = []
        tgts = []
        if isinstance(node, _ast.Assign):
            tgts = node.targets
        elif isinstance(node, (_ast.AnnAssign, _ast.AugAssign)):
            tgts = [node.target]
        for t in tgts:
            if isinstance(t, _ast.Name) and t.id == "open":
                found.append("open")
            if isinstance(t, _ast.Attribute) and isinstance(t.value, _ast.Name):
                pair = f"{t.value.id}.{t.attr}"
                if pair in {"zlib.crc32", "struct.unpack"}:
                    found.append(pair)
        return found

    def fn():
        for name in ("decode.py", "encode.py"):
            tree = _ast.parse((Path(workspace) / name).read_text(encoding="utf-8", errors="ignore"))
            for node in _ast.walk(tree):
                if targets(node):
                    return True
        return False
    return _holds(fn)


@criterion(description="Fires when the decoder produces different output across repeated runs on one capture.")
def negative_nondeterministic_output(workspace):
    def fn():
        payload, _exp = fx_eval_basic()["dict"]
        first = _decode(workspace, payload)
        if first is None:
            return False
        for _ in range(3):
            again = _decode(workspace, payload)
            if again is None or not _docs_equal(first, again):
                return True  # cheat: output changed between runs
        return False
    return _holds(fn)


criteria.decoder_exists(weight=1)
criteria.encoder_exists(weight=1)
criteria.format_report_present(weight=1)
criteria.roundtrip_report_present(weight=1)
criteria.error_analysis_present(weight=1)
criteria.decoded_examples_present(weight=1)
criteria.basic_raw_wide(weight=3)
criteria.basic_raw_narrow(weight=3)
criteria.basic_delta(weight=3)
criteria.basic_dict(weight=3)
criteria.basic_reset(weight=3)
criteria.basic_longkey(weight=3)
criteria.va1_cross_dict(weight=5)
criteria.va1_cross_delta(weight=5)
criteria.va1_three_seg(weight=3)
criteria.va2_modified_bytes(weight=5)
criteria.va2_extensions_kept(weight=5)
criteria.va2_untouched_preserved(weight=3)
criteria.va3_boundary_value(weight=5)
criteria.va3_ext_escaped(weight=5)
criteria.va3_reencode(weight=3)
criteria.va4_overlong_bytes(weight=5)
criteria.va4_len_reported(weight=3)
criteria.va4_modified_shortest(weight=5)
criteria.va5_magic_over_version(weight=3)
criteria.va5_version_over_reserved(weight=3)
criteria.va5_reserved_over_overflow(weight=3)
criteria.va5_overflow_over_crc(weight=3)
criteria.va5_version_field(weight=3)
criteria.heavy_decode_rejects(weight=5)
criteria.heavy_salvage_recovers(weight=5)
criteria.va6_single_records(weight=5)
criteria.va6_single_damage(weight=3)
criteria.va6_two_spans(weight=5)
criteria.va6_no_false_resync(weight=3)
criteria.compA_value(weight=5)
criteria.compA_len(weight=3)
criteria.compA_ext(weight=5)
criteria.compA_all(weight=3)
criteria.report_format(weight=3)
criteria.report_error_analysis(weight=3)
criteria.report_roundtrip(weight=3)
criteria.report_decoded_examples(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_rebinds_verifier_dependencies(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)


def _write_corpus(root):
    """Regenerate the agent-visible catalog and tables into <root>/data (parity
    with the shipped generator; used for local checks, not at grade time)."""
    data = Path(root) / "data"
    data.mkdir(parents=True, exist_ok=True)
    clean, reject, schema, layouts, symrows, revisions = build_catalog()
    cat = _interleave(clean, reject)
    with (data / "capture_catalog.jsonl").open("w", encoding="utf-8") as fh:
        for row in cat:
            fh.write(json.dumps({k: row[k] for k in ("capture_id", "stream_id", "seq_no",
                     "revision", "hex")}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 test_output.py <env_root>")
    _write_corpus(Path(sys.argv[1]))
    print(f"[test_output] regenerated catalog under {sys.argv[1]}/data")
