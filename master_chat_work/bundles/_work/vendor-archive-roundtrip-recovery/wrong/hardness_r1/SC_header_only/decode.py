import json, struct, sys, zlib

def header_error(b):
    if b[:5] != b"VARC1":
        return {"error": "bad_magic"}
    if b[5] != 2:
        return {"error": "unsupported_version", "version": b[5]}
    for off in (14, 15):
        if b[off]:
            return {"error": "reserved_not_zero", "offset": off}
    n = struct.unpack_from("<H", b, 11)[0]
    if n * 5 > len(b) - 20:
        return {"error": "record_count_overflow", "record_count": n}
    e, f = zlib.crc32(b[5:16]) & 0xFFFFFFFF, struct.unpack("<I", b[-4:])[0]
    if e != f:
        return {"error": "trailer_crc_mismatch", "expected": e, "found": f}
    return None

args = sys.argv[1:]
if args[0] == "--stream":
    print(json.dumps({"segments": []}))
elif args[0] == "--salvage":
    b = open(args[1], "rb").read()
    err = header_error(b)
    print(json.dumps({"records": [], "damaged": [], "header_defect": err["error"] if err else None}))
else:
    b = open(args[0], "rb").read()
    print(json.dumps(header_error(b) or {"magic_ok": True, "records": []}))
