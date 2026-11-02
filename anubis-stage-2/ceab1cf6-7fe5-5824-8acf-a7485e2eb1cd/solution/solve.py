#!/usr/bin/env python3
"""Reference solution for the offline strict-envelope budget-allocation ladder task.

Reads only /app/data, repairs the bundled control tool in place so the tool itself
derives a deterministic allocation ladder from the layered data files using pure
integer arithmetic (round-half-even via integer remainder; no float ever touches a
graded value), drives the repaired CLI to produce, validate and report the flat main
configuration and both deployment profiles, and emits the full set of declared
artifacts under /app/out from the tool-derived values.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_ARCHIVE = Path("/app/data/tool.zip")
DATA = Path("/app/data")
TOOL = Path("/app/tool").resolve()
OUT = Path("/app/out")

FORMAT_TAG = "TASK"

# The 23 declared deliverables, in the task.toml / validation_rules order.
ARTIFACTS = [
    "config.json", "report.json", "tool.zip", "profile_dev.json", "profile_prod.json",
    "validation_report.json", "summary.json", "ladder_solution.yaml", "bitrate_ladder.csv",
    "gop_plan.ini", "vbv_plan.properties", "qp_curve.psv", "color_config.env",
    "framerate_plan.kv", "tiling_plan.toml", "selection_trace.kv", "rounding_audit.yaml",
    "profile_delta_report.json", "convergence_report.txt", "reproducibility_manifest.json",
    "derivation_provenance.xml", "input_manifest.ndjson", "ladder_ordering.tsv",
]

# ---------------------------------------------------------------------------
# The repaired task-ctl tool. The ten shipped defects are corrected in place:
# integer round-half-even, even width, round-on-granularity, scale-before-
# granularity in profiles, integer priority staircase, reserve from the maximum
# allocation, rounded cycle span, active-band canonical-row selection, a required
# subcommand and a flat single-object configuration. The tool reads every rule
# from /app/data; no derived answer is embedded here.
# ---------------------------------------------------------------------------
REPAIRED_CLI = r'''#!/usr/bin/env python3
"""Repaired task-ctl budget-envelope allocation ledger CLI.

Derives one deterministic flat allocation configuration for the active band from
the layered rule files under /app/data, using pure integer arithmetic with
round-half-even (banker's) rounding computed from the division remainder. No
floating-point operation touches a graded value and no derived answer is embedded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get("TASK_CTL_DATA") or "/app/data")


# --- integer helpers (round-half-even via remainder; no floats) ------------
def round_half_even(num: int, den: int) -> int:
    if den < 0:
        num, den = -num, -den
    q, r = divmod(num, den)
    twice = 2 * r
    if twice < den:
        return q
    if twice > den:
        return q + 1
    return q if q % 2 == 0 else q + 1


def quantize_nearest(value: int, step: int) -> int:
    return round_half_even(value, step) * step


# --- config I/O ------------------------------------------------------------
def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def coerce(value: str):
    if value.lstrip("-").isdecimal():
        return int(value)
    if value in {"true", "false"}:
        return value == "true"
    return value


def assert_flat(data: dict) -> None:
    bad = [k for k, v in data.items() if isinstance(v, (dict, list))]
    if bad:
        raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


# --- data readers: one active band, canonical rows only, decoys ignored ----
def _text(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8", errors="replace")


def _content_lines(name: str, prefixes: tuple = ("#", ";")) -> list:
    out = []
    for raw in _text(name).splitlines():
        s = raw.strip()
        if not s or s.lstrip().startswith(prefixes):
            continue
        out.append(raw)
    return out


def _rows(name: str, sep: str) -> list:
    lines = _content_lines(name)
    header = [c.strip() for c in lines[0].split(sep)]
    rows = []
    for line in lines[1:]:
        parts = [c.strip() for c in line.split(sep)]
        if len(parts) == len(header):
            rows.append(dict(zip(header, parts)))
    return rows


def _canon_row(rows: list, tier: int, key: str = "tier_id") -> dict:
    for row in rows:
        if row.get("status") != "CANONICAL":
            continue
        raw = row.get(key)
        if raw is None:
            continue
        try:
            if int(raw) == tier:
                return row
        except ValueError:
            continue
    raise SystemExit("no canonical row for tier " + str(tier) + " in " + key)


def _json_rows(name: str) -> list:
    rows = []
    for line in _text(name).splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if "_doc" in obj:
            continue
        rows.append(obj)
    return rows


def _canon_json(rows: list, tier: int, field: str):
    for row in rows:
        if row.get("status") == "CANONICAL" and int(row.get("tier", -1)) == tier:
            return row[field]
    raise SystemExit("no canonical json row for tier " + str(tier) + " field " + field)


def base_inputs() -> tuple:
    base = json.loads(_text("defaults.json"))["base_config"]
    return int(base["max_records"]), int(base["retry_limit"]), int(base["timeout_ms"]), str(base["trailer"])


def target_tier(b: int) -> int:
    return (b // 13) % 7


def read_min_kbps(tier: int) -> int:
    section = "tier." + str(tier)
    current = None
    val = None
    status = None
    for line in _content_lines("min_kbps.ini"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            current = s[1:-1]
            continue
        if current != section:
            continue
        if "=" in s:
            k, _, v = s.partition("=")
            k = k.strip()
            if k == "min_kbps":
                val = int(v.strip())
            elif k == "status":
                status = v.strip()
    if status != "CANONICAL" or val is None:
        raise SystemExit("no canonical min_kbps for tier " + str(tier))
    return val


def read_max_kbps(tier: int) -> int:
    kv = {}
    for line in _content_lines("max_kbps.properties"):
        if "=" in line:
            k, _, v = line.partition("=")
            kv[k.strip()] = v.strip()
    if kv.get("tier." + str(tier) + ".status") != "CANONICAL":
        raise SystemExit("no canonical max_kbps for tier " + str(tier))
    return int(kv["tier." + str(tier) + ".max_kbps"])


def read_eff_permille() -> int:
    for line in _content_lines("eff_permille.conf"):
        p = line.split()
        if len(p) >= 6 and p[0] == "codec" and p[1] == "ledger-core" and p[-1] == "CANONICAL":
            return int(p[3])
    raise SystemExit("no canonical eff_permille")


def read_granularity() -> int:
    for line in _content_lines("granularity.kv"):
        fields = dict(part.split("=", 1) for part in line.split("|") if "=" in part)
        if fields.get("status") == "CANONICAL" and "granularity_kbps" in fields:
            return int(fields["granularity_kbps"])
    raise SystemExit("no canonical granularity")


def read_maxrate_ratio() -> int:
    section = None
    ratio = None
    status = None
    for line in _content_lines("maxrate_ratio.toml"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1]
            ratio = None
            status = None
            continue
        if section != "active":
            continue
        if "=" in s:
            k, _, v = s.partition("=")
            k = k.strip()
            v = v.strip().strip('"')
            if k == "ratio_permille":
                ratio = int(v)
            elif k == "status":
                status = v
        if section == "active" and ratio is not None and status == "CANONICAL":
            return ratio
    raise SystemExit("no canonical maxrate ratio")


def read_bpp(tier: int) -> int:
    kv = {}
    for line in _content_lines("bpp.env"):
        if "=" in line:
            k, _, v = line.partition("=")
            kv[k.strip()] = v.strip()
    if kv.get("BPP_TIER_" + str(tier) + "_STATUS") != "CANONICAL":
        raise SystemExit("no canonical bpp for tier " + str(tier))
    return int(kv["BPP_TIER_" + str(tier)])


def read_tier_table(name: str, sep: str, field: str, tier: int) -> int:
    return int(_canon_row(_rows(name, sep), tier)[field])


def read_threads(tier: int) -> int:
    for line in _content_lines("threads.fixed"):
        p = line.split()
        if len(p) >= 3 and p[-1] == "CANONICAL":
            try:
                if int(p[0]) == tier:
                    return int(p[1])
            except ValueError:
                continue
    raise SystemExit("no canonical threads for tier " + str(tier))


def read_stair() -> list:
    stair = []
    for line in _content_lines("qp_stair.psv"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[2] == "CANONICAL":
            try:
                stair.append((int(parts[0]), int(parts[1])))
            except ValueError:
                continue
    if not stair:
        raise SystemExit("no canonical staircase")
    return stair


def band_offset(avg: int, stair: list) -> int:
    off = 0
    for thr, delta in stair:
        if avg >= thr:
            off = delta
    return off


def read_qp_base() -> int:
    for line in _content_lines("qp_base.txt"):
        p = line.split()
        if len(p) >= 3 and p[0] == "qp_base" and p[2] == "CANONICAL":
            return int(p[1])
    raise SystemExit("no canonical qp_base")


def read_qp_bounds() -> tuple:
    text = _text("qp_floor_ceil.edn")
    fl = re.search(r"\(qp_floor\s+(\d+)\s+CANONICAL\)", text)
    ce = re.search(r"\(qp_ceil\s+(\d+)\s+CANONICAL\)", text)
    if not fl or not ce:
        raise SystemExit("no canonical qp bounds")
    return int(fl.group(1)), int(ce.group(1))


def read_double_colon(name: str, key: str) -> int:
    for line in _content_lines(name):
        parts = [p.strip() for p in line.split("::")]
        if len(parts) >= 3 and parts[0] == key and parts[2] == "CANONICAL":
            try:
                return int(parts[1])
            except ValueError:
                continue
    raise SystemExit("no canonical " + key + " in " + name)


def read_colors(tier: int) -> tuple:
    prim = re.search(r":band-" + str(tier) + r":\s+(\S+)\s+status=CANONICAL", _text("color_primaries.rst"))
    trans = re.search(r"\(band\s+" + str(tier) + r"\)\s*\(class\s+(\S+)\)\s*\(status\s+CANONICAL\)", _text("color_transfer.sexp"))
    matr = re.search(r'<tr class="CANONICAL"><td>' + str(tier) + r"</td><td>(\w+)</td>", _text("color_matrix.html"))
    if not (prim and trans and matr):
        raise SystemExit("no canonical colors for tier " + str(tier))
    return prim.group(1), trans.group(1), matr.group(1)


def _clamp(value: int, floor: int, ceil: int) -> int:
    return max(floor, min(ceil, value))


# --- core derivation (pure integer, active band only) ----------------------
def band_inputs() -> dict:
    """Base numbers plus every active-band value the allocation chain needs."""
    b, r, t, trailer = base_inputs()
    tier = target_tier(b)
    height = int(_canon_row(_rows("precision_ladder.tsv", "\t"), tier)["height"])
    dar = _canon_row(_rows("aspect_table.csv", ","), tier)
    width = round_half_even(height * int(dar["dar_num"]), int(dar["dar_den"]))
    if width % 2 == 1:
        width += 1
    fps_num = int(_canon_json(_json_rows("fps_num.ndjson"), tier, "fps_num"))
    fps_den = int(_canon_json(_json_rows("fps_den.jsonl"), tier, "fps_den"))
    luma = width * height
    qp_floor, qp_ceil = read_qp_bounds()
    return {
        "b": b, "r": r, "t": t, "trailer": trailer, "tier": tier,
        "height": height, "width": width, "luma": luma,
        "fps_num": fps_num, "fps_den": fps_den,
        "min_kbps": read_min_kbps(tier), "max_kbps": read_max_kbps(tier),
        "gran": read_granularity(), "maxrate": read_maxrate_ratio(),
        "eff": read_eff_permille(), "stair": read_stair(), "qp_base": read_qp_base(),
        "qp_floor": qp_floor, "qp_ceil": qp_ceil,
        "avg_pre": round_half_even(
            luma * read_bpp(tier) * read_eff_permille() * fps_num, 1000 * 1000 * 1000 * fps_den
        ),
    }


def allocation_chain(inp: dict, scale_permille: int, vbv_delta: int, keyint: int) -> dict:
    """Scale, clamp, quantize, then ceiling, reserve, cycle span and priority."""
    scaled = round_half_even(inp["avg_pre"] * scale_permille, 1000)
    avg = quantize_nearest(_clamp(scaled, inp["min_kbps"], inp["max_kbps"]), inp["gran"])
    maxb = round_half_even(avg * inp["maxrate"], 1000)
    vbv_sec = 1000 + (inp["t"] % 4000) + vbv_delta * 1000
    offset = band_offset(avg, inp["stair"])
    return {
        "avg": avg,
        "maxb": maxb,
        "vbv_sec": vbv_sec,
        "vbv": round_half_even(maxb * vbv_sec, 1000),
        "gop": round_half_even(inp["fps_num"] * keyint, inp["fps_den"]),
        "offset": offset,
        "qp": _clamp(inp["qp_base"] - offset, inp["qp_floor"], inp["qp_ceil"]),
    }


def derive(schema: dict) -> tuple:
    inp = band_inputs()
    b, r, t, trailer, tier = inp["b"], inp["r"], inp["t"], inp["trailer"], inp["tier"]
    height, width, luma = inp["height"], inp["width"], inp["luma"]
    fps_num, fps_den = inp["fps_num"], inp["fps_den"]
    chain = allocation_chain(inp, 1000, 0, r)
    avg, maxb, vbv, gop, qp = chain["avg"], chain["maxb"], chain["vbv"], chain["gop"], chain["qp"]
    min_keyint = round_half_even(fps_num * max(1, r - 1), fps_den)
    bframes = read_tier_table("batch_frames.scsv", ";", "bframes", tier)

    tile_columns = read_tier_table("shard_cols.tsv2", "\t\t", "tile_columns", tier)
    tile_rows = read_tier_table("shard_rows.csv2", ";;", "tile_rows", tier)
    film_grain = read_tier_table("dither_scale.caret", "^", "film_grain", tier)
    vmaf_target = read_tier_table("fidelity_target.tilde", "~", "vmaf_target", tier)
    threads = read_threads(tier)
    lookahead = round_half_even(fps_num * read_double_colon("lookahead_seconds.conf2", "lookahead_seconds"), fps_den)
    pass_count = read_double_colon("pass_count.env2", "PASS_COUNT")
    temporal_layers = read_tier_table("temporal_layers.tsv3", "\t", "temporal_layers", tier)
    primaries, transfer, matrix = read_colors(tier)

    config = {
        "avg_bitrate_kbps": avg,
        "bframes": bframes,
        "checksum": schema["checksum"],
        "codec": schema["codec"],
        "color_matrix": matrix,
        "color_primaries": primaries,
        "color_transfer": transfer,
        "container": schema["container"],
        "film_grain": film_grain,
        "fps_den": fps_den,
        "fps_num": fps_num,
        "gop_size_frames": gop,
        "height": height,
        "lookahead_frames": lookahead,
        "luma_pixels": luma,
        "max_bitrate_kbps": maxb,
        "min_keyint_frames": min_keyint,
        "mode": schema["mode"],
        "pass_count": pass_count,
        "pixel_format": schema["pixel_format"],
        "profile": schema["profile"],
        "qp": qp,
        "temporal_layers": temporal_layers,
        "threads": threads,
        "tile_columns": tile_columns,
        "tile_rows": tile_rows,
        "tiles": tile_columns * tile_rows,
        "trailer": trailer,
        "vbv_buffer_kbits": vbv,
        "vmaf_target": vmaf_target,
        "width": width,
    }
    audit = {
        "max_records": b,
        "retry_limit": r,
        "timeout_ms": t,
        "target_tier": tier,
        "trailer": trailer,
        "granularity_kbps": inp["gran"],
        "maxrate_ratio_permille": inp["maxrate"],
        "eff_permille": inp["eff"],
        "band_offset": chain["offset"],
        "vbv_seconds_milli": chain["vbv_sec"],
        "keyint_seconds": r,
        "min_keyint_seconds": max(1, r - 1),
    }
    return config, audit


def derive_profile(name: str, schema: dict) -> dict:
    inp = band_inputs()
    overrides = json.loads(_text("env_overrides.json"))[name]
    chain = allocation_chain(
        inp,
        int(overrides["avg_scale_permille"]),
        int(overrides["vbv_delta_seconds"]),
        inp["r"] + int(overrides["gop_delta_seconds"]),
    )
    qp = _clamp(chain["qp"] + int(overrides["qp_delta"]), inp["qp_floor"], inp["qp_ceil"])
    return {
        "profile": schema["profile"] + "-" + name,
        "avg_bitrate_kbps": chain["avg"],
        "max_bitrate_kbps": chain["maxb"],
        "vbv_buffer_kbits": chain["vbv"],
        "gop_size_frames": chain["gop"],
        "qp": qp,
        "trailer": inp["trailer"] + ":" + name,
    }


# --- subcommands -----------------------------------------------------------
def cmd_derive(args) -> None:
    schema = load_json(args.schema)
    config, audit = derive(schema)
    assert_flat(config)
    write_json(args.out, {"config": config, "audit": audit})
    print("derived")


def cmd_profile(args) -> None:
    schema = load_json(args.schema)
    profile = derive_profile(args.name, schema)
    assert_flat(profile)
    write_json(args.out, profile)
    print("profiled " + args.name)


def cmd_init(args) -> None:
    schema = load_json(args.schema)
    data = {
        "profile": schema["profile"],
        "codec": schema["codec"],
        "container": schema["container"],
        "pixel_format": schema["pixel_format"],
        "checksum": schema["checksum"],
        "mode": schema.get("mode", "strict-local"),
    }
    assert_flat(data)
    write_json(args.out, data)
    print("initialized")


def cmd_set(args) -> None:
    data = load_json(args.config)
    data[args.key] = coerce(args.value)
    assert_flat(data)
    write_json(args.config, data)
    print("set " + args.key)


def cmd_validate(args) -> None:
    schema = load_json(args.schema)
    data = load_json(args.config)
    assert_flat(data)
    required = [k for k in schema["required_keys"].split(",") if k]
    missing = [k for k in required if k not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_report(args) -> None:
    data = load_json(args.config)
    assert_flat(data)
    commands = json.loads(args.commands)
    commands.append({
        "argv": ["python3", "cli.py", "export-report", "--config", args.config, "--out", args.out],
        "returncode": 0,
        "stdout": "reported",
    })
    report = {
        "ok": True,
        "tool": "task-ctl",
        "config_path": args.config,
        "config_sha256": args.digest,
        "commands": commands,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def main() -> None:
    parser = argparse.ArgumentParser(prog="task-ctl")
    sub = parser.add_subparsers(dest="command", required=True)

    p_der = sub.add_parser("derive")
    p_der.add_argument("--schema", required=True)
    p_der.add_argument("--out", required=True)
    p_der.set_defaults(func=cmd_derive)

    p_prof = sub.add_parser("profile")
    p_prof.add_argument("--schema", required=True)
    p_prof.add_argument("--name", required=True)
    p_prof.add_argument("--out", required=True)
    p_prof.set_defaults(func=cmd_profile)

    p_init = sub.add_parser("init")
    p_init.add_argument("--schema", required=True)
    p_init.add_argument("--out", required=True)
    p_init.set_defaults(func=cmd_init)

    p_set = sub.add_parser("set")
    p_set.add_argument("--config", required=True)
    p_set.add_argument("--key", required=True)
    p_set.add_argument("--value", required=True)
    p_set.set_defaults(func=cmd_set)

    p_val = sub.add_parser("validate")
    p_val.add_argument("--schema", required=True)
    p_val.add_argument("--config", required=True)
    p_val.set_defaults(func=cmd_validate)

    p_rep = sub.add_parser("export-report")
    p_rep.add_argument("--config", required=True)
    p_rep.add_argument("--out", required=True)
    p_rep.add_argument("--digest", required=True)
    p_rep.add_argument("--commands", required=True)
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------------------
# Oracle orchestration: extract, repair the tool in place, drive it to derive.
# ---------------------------------------------------------------------------
def extract() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ARCHIVE) as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit(f"unsafe source member: {info.filename!r}")
            dest = (TOOL / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(TOOL):
                raise SystemExit(f"escaping source member: {info.filename!r}")
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


# What the shipped cli.py does wrong, recognised from its own source text.
SHIPPED_DEFECTS = (
    ("math.floor(num / den + 0.5)", "rounds half-up on floats instead of integer round-half-even"),
    ("width = round_half_up(height * dar_num, dar_den)", "never evens the column width"),
    ("return (value // step) * step", "floors onto the granularity step instead of rounding"),
    ("quantize_floor(round_half_up(avg * scale, 1000), 50)", "scales profiles after granularity"),
    ("math.log2", "takes the priority step from a float logarithm instead of the staircase"),
    ("round_half_up(avg * vbv_seconds_milli, 1000)", "builds the reserve from the average allocation"),
    ("math.ceil(fps_num * R / fps_den)", "ceils the cycle span instead of rounding it"),
    ("return rows[0][field]", "reads the first row of every table instead of the active canonical row"),
    ('add_subparsers(dest="command")', "leaves the subcommand optional"),
    ('config = {"ladder": ladder', "nests the configuration under a ladder object"),
)


def inspect_shipped_tool() -> None:
    """Run the shipped tool and read its source before anything is edited."""
    bare = subprocess.run([sys.executable, str(TOOL / "cli.py")], cwd=TOOL, text=True,
                          capture_output=True, timeout=60, check=False)
    tail = (bare.stderr.strip().splitlines() or [""])[-1]
    print(f"[oracle] shipped task-ctl with no subcommand exits {bare.returncode}: {tail}")
    source = (TOOL / "cli.py").read_text(encoding="utf-8")
    found = [why for marker, why in SHIPPED_DEFECTS if marker in source]
    if len(found) != len(SHIPPED_DEFECTS):
        raise SystemExit("the shipped tool no longer carries every known defect")
    for why in found:
        print(f"[oracle] shipped cli.py {why}")


def repair_cli() -> None:
    (TOOL / "cli.py").write_text(REPAIRED_CLI, encoding="utf-8")


def run_cli(*args: str) -> dict:
    cmd = [sys.executable, str(TOOL / "cli.py"), *args]
    result = subprocess.run(cmd, cwd=TOOL, text=True, capture_output=True, timeout=60, check=False)
    return {
        "argv": ["python3", "cli.py", *args],
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
    }


def package_tool() -> None:
    archive = OUT / "tool.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def input_census() -> list:
    census = []
    for path in sorted(p for p in DATA.iterdir() if p.is_file()):
        try:
            rows = path.read_text(encoding="utf-8").count("\n")
        except UnicodeDecodeError:
            rows = 0
        census.append({
            "name": path.name,
            "format": path.suffix.lstrip("."),
            "bytes": path.stat().st_size,
            "rows": rows,
        })
    return census


# ---------------------------------------------------------------------------
# Artifact writers (all values come from the tool-derived config/profiles/audit)
# ---------------------------------------------------------------------------
def write_artifacts(config: dict, dev: dict, prod: dict, audit: dict, commands: list, digest: str,
                    runs_compared: int, reproduced: bool) -> None:
    tier = audit["target_tier"]
    r = audit["retry_limit"]

    dump_json(OUT / "profile_dev.json", dev)
    dump_json(OUT / "profile_prod.json", prod)

    def _yaml_block(mapping: dict, indent: int) -> list:
        pad = "  " * indent
        rows = []
        for key in sorted(mapping):
            value = mapping[key]
            if isinstance(value, bool):
                rows.append(f"{pad}{key}: {'true' if value else 'false'}")
            else:
                rows.append(f"{pad}{key}: {value}")
        return rows

    ladder_yaml = [f"tier: {tier}", "config:"]
    ladder_yaml.extend(_yaml_block(config, 1))
    ladder_yaml.append("profiles:")
    ladder_yaml.append("  dev:")
    ladder_yaml.extend(_yaml_block(dev, 2))
    ladder_yaml.append("  prod:")
    ladder_yaml.extend(_yaml_block(prod, 2))
    (OUT / "ladder_solution.yaml").write_text("\n".join(ladder_yaml) + "\n", encoding="utf-8")

    (OUT / "bitrate_ladder.csv").write_text(
        "profile,avg_bitrate_kbps,max_bitrate_kbps,vbv_buffer_kbits\n"
        f"main,{config['avg_bitrate_kbps']},{config['max_bitrate_kbps']},{config['vbv_buffer_kbits']}\n"
        f"dev,{dev['avg_bitrate_kbps']},{dev['max_bitrate_kbps']},{dev['vbv_buffer_kbits']}\n"
        f"prod,{prod['avg_bitrate_kbps']},{prod['max_bitrate_kbps']},{prod['vbv_buffer_kbits']}\n",
        encoding="utf-8",
    )

    (OUT / "gop_plan.ini").write_text(
        "[gop]\n"
        f"gop_size_frames={config['gop_size_frames']}\n"
        f"min_keyint_frames={config['min_keyint_frames']}\n"
        f"keyint_seconds={audit['keyint_seconds']}\n"
        f"min_keyint_seconds={audit['min_keyint_seconds']}\n",
        encoding="utf-8",
    )
    (OUT / "vbv_plan.properties").write_text(
        f"vbv_buffer_kbits={config['vbv_buffer_kbits']}\n"
        f"max_bitrate_kbps={config['max_bitrate_kbps']}\n"
        f"vbv_seconds_milli={audit['vbv_seconds_milli']}\n",
        encoding="utf-8",
    )
    (OUT / "qp_curve.psv").write_text(
        "qp|band_offset|avg_bitrate_kbps\n"
        f"{config['qp']}|{audit['band_offset']}|{config['avg_bitrate_kbps']}\n",
        encoding="utf-8",
    )
    (OUT / "color_config.env").write_text(
        f"color_primaries={config['color_primaries']}\n"
        f"color_transfer={config['color_transfer']}\n"
        f"color_matrix={config['color_matrix']}\n",
        encoding="utf-8",
    )
    (OUT / "framerate_plan.kv").write_text(
        f"fps_num={config['fps_num']}\n"
        f"fps_den={config['fps_den']}\n"
        f"lookahead_frames={config['lookahead_frames']}\n",
        encoding="utf-8",
    )
    (OUT / "tiling_plan.toml").write_text(
        f"tile_columns = {config['tile_columns']}\n"
        f"tile_rows = {config['tile_rows']}\n"
        f"tiles = {config['tiles']}\n"
        f"threads = {config['threads']}\n",
        encoding="utf-8",
    )
    (OUT / "selection_trace.kv").write_text(
        f"max_records={audit['max_records']}\n"
        f"retry_limit={audit['retry_limit']}\n"
        f"timeout_ms={audit['timeout_ms']}\n"
        f"target_tier={tier}\n"
        f"height={config['height']}\n"
        "rule=active_band = (max_records // 13) % 7\n",
        encoding="utf-8",
    )
    (OUT / "rounding_audit.yaml").write_text(
        "policy: round_half_even\n"
        f"granularity_kbps: {audit['granularity_kbps']}\n"
        f"maxrate_ratio_permille: {audit['maxrate_ratio_permille']}\n"
        f"eff_permille: {audit['eff_permille']}\n",
        encoding="utf-8",
    )
    dump_json(OUT / "profile_delta_report.json", {
        "dev": {
            "avg_bitrate_kbps": dev["avg_bitrate_kbps"] - config["avg_bitrate_kbps"],
            "max_bitrate_kbps": dev["max_bitrate_kbps"] - config["max_bitrate_kbps"],
            "vbv_buffer_kbits": dev["vbv_buffer_kbits"] - config["vbv_buffer_kbits"],
            "gop_size_frames": dev["gop_size_frames"] - config["gop_size_frames"],
            "qp": dev["qp"] - config["qp"],
        },
        "prod": {
            "avg_bitrate_kbps": prod["avg_bitrate_kbps"] - config["avg_bitrate_kbps"],
            "max_bitrate_kbps": prod["max_bitrate_kbps"] - config["max_bitrate_kbps"],
            "vbv_buffer_kbits": prod["vbv_buffer_kbits"] - config["vbv_buffer_kbits"],
            "gop_size_frames": prod["gop_size_frames"] - config["gop_size_frames"],
            "qp": prod["qp"] - config["qp"],
        },
    })
    (OUT / "convergence_report.txt").write_text(
        f"config_sha256: {digest}\n"
        f"reproduced: {'true' if reproduced else 'false'}\n"
        f"iterations: {runs_compared}\n",
        encoding="utf-8",
    )
    dump_json(OUT / "reproducibility_manifest.json", {
        "base": {"max_records": audit["max_records"], "retry_limit": audit["retry_limit"], "timeout_ms": audit["timeout_ms"]},
        "config_sha256": digest,
        "spine_keys": sorted(config.keys()),
    })
    provenance_sources = {
        "height": "precision_ladder.tsv",
        "dar": "aspect_table.csv",
        "min_kbps": "min_kbps.ini",
        "max_kbps": "max_kbps.properties",
        "fps_num": "fps_num.ndjson",
        "fps_den": "fps_den.jsonl",
        "bpp_milli": "bpp.env",
        "eff_permille": "eff_permille.conf",
        "granularity_kbps": "granularity.kv",
        "maxrate_ratio_permille": "maxrate_ratio.toml",
        "qp_stair": "qp_stair.psv",
    }
    prov_lines = ["<derivation_provenance>", "  <field_sources>"]
    for field, src in provenance_sources.items():
        prov_lines.append(f'    <source field="{field}">{src}</source>')
    prov_lines.append("  </field_sources>")
    prov_lines.append("  <registry_keys>")
    for key in sorted(config.keys()):
        prov_lines.append(f"    <key>{key}</key>")
    prov_lines.append("  </registry_keys>")
    prov_lines.append("</derivation_provenance>")
    (OUT / "derivation_provenance.xml").write_text("\n".join(prov_lines) + "\n", encoding="utf-8")
    (OUT / "input_manifest.ndjson").write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in input_census()),
        encoding="utf-8",
    )

    ladder = [
        ("main", config["avg_bitrate_kbps"], config["max_bitrate_kbps"]),
        ("dev", dev["avg_bitrate_kbps"], dev["max_bitrate_kbps"]),
        ("prod", prod["avg_bitrate_kbps"], prod["max_bitrate_kbps"]),
    ]
    ladder_sorted = sorted(ladder, key=lambda row: row[1])
    lines = ["profile\tavg_bitrate_kbps\tmax_bitrate_kbps\trank"]
    for rank, (name, avg, mx) in enumerate(ladder_sorted):
        lines.append(f"{name}\t{avg}\t{mx}\t{rank}")
    (OUT / "ladder_ordering.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    inputs = sorted(entry["name"] for entry in input_census())
    lazy = {"validation_report.json", "summary.json"}
    all_present = all((OUT / name).exists() or name in lazy for name in ARTIFACTS)
    command_failures = [c for c in commands if c["returncode"] != 0]
    scalar_flat = all(not isinstance(v, (dict, list)) for v in config.values())
    profiles_check = {
        "dev": {"scalar_flat": all(not isinstance(v, (dict, list)) for v in dev.values()), "trailer": dev["trailer"]},
        "prod": {"scalar_flat": all(not isinstance(v, (dict, list)) for v in prod.values()), "trailer": prod["trailer"]},
    }
    checks = {
        "all_artifacts_present": all_present,
        "command_failures": command_failures,
        "config_matches_policy": json.loads((OUT / "config.json").read_text(encoding="utf-8")) == config,
        "config_scalar_flat": scalar_flat,
        "profiles": profiles_check,
        "required_artifacts": list(ARTIFACTS),
    }
    validation_report = {
        "ok": bool(all_present and scalar_flat and not command_failures and checks["config_matches_policy"]),
        "checks": checks,
    }
    dump_json(OUT / "validation_report.json", validation_report)

    dump_json(OUT / "summary.json", {
        "artifact_count": len(ARTIFACTS),
        "artifacts": list(ARTIFACTS),
        "format_tag": FORMAT_TAG,
        "input_count": len(inputs),
        "inputs": inputs,
        "profiles": ["dev", "prod"],
        "target_tier": tier,
        "tool": "task-ctl",
        "trailer": config["trailer"],
    })


def main() -> None:
    extract()
    inspect_shipped_tool()
    repair_cli()
    OUT.mkdir(parents=True, exist_ok=True)
    scratch = TOOL.parent / ".taskctl"
    scratch.mkdir(parents=True, exist_ok=True)

    schema_path = TOOL / "schema.json"
    config_path = OUT / "config.json"

    # 1. The repaired tool derives the configuration from /app/data.
    derived_path = scratch / "derived.json"
    commands = [run_cli("derive", "--schema", str(schema_path), "--out", str(derived_path))]
    if commands[-1]["returncode"] != 0:
        raise SystemExit("derive failed: " + json.dumps(commands[-1]))
    derived_bytes = derived_path.read_bytes()
    derived = json.loads(derived_bytes)
    config = derived["config"]
    audit = derived["audit"]

    # A second derive run from the same inputs must reproduce the first byte for byte.
    repeat_path = scratch / "derived_repeat.json"
    commands.append(run_cli("derive", "--schema", str(schema_path), "--out", str(repeat_path)))
    if commands[-1]["returncode"] != 0:
        raise SystemExit("repeat derive failed: " + json.dumps(commands[-1]))
    reproduced = repeat_path.read_bytes() == derived_bytes
    if not reproduced:
        raise SystemExit("the repaired tool is not stable across a repeat run")

    # 2. Assemble and validate config.json through the repaired tool.
    commands.append(run_cli("init", "--schema", str(schema_path), "--out", str(config_path)))
    for key in sorted(config):
        commands.append(run_cli("set", "--config", str(config_path), "--key", key, "--value", str(config[key])))
    commands.append(run_cli("validate", "--schema", str(schema_path), "--config", str(config_path)))

    failures = [c for c in commands if c["returncode"] != 0]
    if failures:
        raise SystemExit("cli command failed: " + json.dumps(failures))

    digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    commands.append(run_cli(
        "export-report",
        "--config", str(config_path),
        "--out", str(OUT / "report.json"),
        "--digest", digest,
        "--commands", json.dumps(commands, sort_keys=True),
    ))
    if commands[-1]["returncode"] != 0:
        raise SystemExit("export-report failed: " + json.dumps(commands[-1]))

    # 3. The repaired tool derives both deployment profiles.
    dev_path = scratch / "profile_dev.json"
    prod_path = scratch / "profile_prod.json"
    pdev = run_cli("profile", "--schema", str(schema_path), "--name", "dev", "--out", str(dev_path))
    pprod = run_cli("profile", "--schema", str(schema_path), "--name", "prod", "--out", str(prod_path))
    if pdev["returncode"] != 0 or pprod["returncode"] != 0:
        raise SystemExit("profile derivation failed: " + json.dumps([pdev, pprod]))
    dev = json.loads(dev_path.read_text(encoding="utf-8"))
    prod = json.loads(prod_path.read_text(encoding="utf-8"))

    package_tool()
    write_artifacts(config, dev, prod, audit, commands, digest, runs_compared=2, reproduced=reproduced)
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
