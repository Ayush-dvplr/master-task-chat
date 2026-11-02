from __future__ import annotations

import argparse
import configparser
import json
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# sentinel-ctl: policy bundle compiler.


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(data):
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(dump_json(data), encoding="utf-8")


def coerce(value):
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if value in ("true", "false"):
        return value == "true"
    return value


def assert_flat(data):
    bad = [key for key, value in data.items() if isinstance(value, (dict, list))]
    if bad:
        raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


def round_half_up(numerator, denominator=1):
    return int((Decimal(numerator) / Decimal(denominator)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def read_toml(path):
    import tomllib

    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonc(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", "", text)
    return json.loads(text)


def read_yaml_flat(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ": " not in stripped and not stripped.endswith(":"):
            continue
        key, _, value = stripped.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def read_conf(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    flat = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            flat[key] = value
    return flat


def read_conf_sections(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def read_kv_text(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for sep in ("=", ":"):
            if sep in stripped:
                key, _, value = stripped.partition(sep)
                out.setdefault(key.strip(), value.strip())
                break
    return out


def read_xml_records(path, tag):
    root = ET.parse(path).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


def _col_to_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    idx = 0
    for char in letters:
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


def read_xlsx_rows(path):
    ns = "{" + "http" + "://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.iter(ns + "si"):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
        sroot = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sroot.iter(ns + "row"):
            cells = {}
            for cell in row.iter(ns + "c"):
                ref = cell.get("r", "A1")
                col = _col_to_idx(ref)
                vnode = cell.find(ns + "v")
                kind = cell.get("t")
                if kind == "inlineStr":
                    cells[col] = "".join(t.text or "" for t in cell.iter(ns + "t"))
                elif kind == "s" and vnode is not None:
                    cells[col] = shared[int(vnode.text)]
                else:
                    cells[col] = vnode.text if vnode is not None and vnode.text is not None else ""
            rows.append(cells)
    if not rows:
        return []
    header = {i: rows[0][i] for i in rows[0]}
    records = []
    for cells in rows[1:]:
        records.append({name: cells.get(i, "") for i, name in header.items()})
    return records


# ---------------------------------------------------------------- parquet ---


class _Thrift:
    def __init__(self, buf, pos=0):
        self.buf = buf
        self.pos = pos

    def byte(self):
        b = self.buf[self.pos]
        self.pos += 1
        return b

    def varint(self):
        shift = 0
        result = 0
        while True:
            b = self.byte()
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                return result
            shift += 7

    def zigzag(self):
        n = self.varint()
        return (n >> 1) ^ -(n & 1)

    def value(self, ftype):
        if ftype in (1, 2):
            return ftype == 1
        if ftype == 3:
            return struct.unpack("b", bytes([self.byte()]))[0]
        if ftype in (4, 5, 6):
            return self.zigzag()
        if ftype == 7:
            v = struct.unpack("<d", self.buf[self.pos:self.pos + 8])[0]
            self.pos += 8
            return v
        if ftype == 8:
            n = self.varint()
            v = bytes(self.buf[self.pos:self.pos + n])
            self.pos += n
            return v
        if ftype in (9, 10):
            head = self.byte()
            size = head >> 4
            etype = head & 0x0F
            if size == 15:
                size = self.varint()
            if etype in (1, 2):
                return [self.byte() == 1 for _ in range(size)]
            return [self.value(etype) for _ in range(size)]
        if ftype == 11:
            size = self.varint()
            if size == 0:
                return {}
            kv = self.byte()
            return {self.value(kv >> 4): self.value(kv & 0x0F) for _ in range(size)}
        if ftype == 12:
            return self.struct()
        raise ValueError("unsupported thrift type %d" % ftype)

    def struct(self):
        out = {}
        last = 0
        while True:
            head = self.byte()
            if head == 0:
                return out
            delta = head >> 4
            ftype = head & 0x0F
            fid = last + delta if delta else self.zigzag()
            out[fid] = self.value(ftype)
            last = fid


def _snappy(data):
    pos = 0
    length = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        length |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    out = bytearray()
    while pos < len(data):
        tag = data[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:
            n = tag >> 2
            if n >= 60:
                extra = n - 59
                n = int.from_bytes(data[pos:pos + extra], "little")
                pos += extra
            n += 1
            out += data[pos:pos + n]
            pos += n
            continue
        if kind == 1:
            n = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | data[pos]
            pos += 1
        elif kind == 2:
            n = (tag >> 2) + 1
            off = int.from_bytes(data[pos:pos + 2], "little")
            pos += 2
        else:
            n = (tag >> 2) + 1
            off = int.from_bytes(data[pos:pos + 4], "little")
            pos += 4
        start = len(out) - off
        for i in range(n):
            out.append(out[start + i])
    if len(out) != length:
        raise ValueError("snappy length mismatch")
    return bytes(out)


def _decompress(codec, data):
    if codec == 0:
        return bytes(data)
    if codec == 1:
        return _snappy(bytes(data))
    if codec == 2:
        return zlib.decompress(bytes(data), 47)
    raise ValueError("unsupported parquet codec %d" % codec)


def _hybrid(buf, pos, end, width, count):
    values = []
    byte_width = (width + 7) // 8
    while len(values) < count and pos < end:
        head = 0
        shift = 0
        while True:
            b = buf[pos]
            pos += 1
            head |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
        if head & 1:
            groups = head >> 1
            nbytes = groups * width
            chunk = int.from_bytes(buf[pos:pos + nbytes], "little")
            pos += nbytes
            mask = (1 << width) - 1
            for i in range(groups * 8):
                values.append((chunk >> (i * width)) & mask if width else 0)
        else:
            run = head >> 1
            val = int.from_bytes(buf[pos:pos + byte_width], "little") if byte_width else 0
            pos += byte_width
            values.extend([val] * run)
    return values[:count]


def _plain(ptype, buf, pos, count, type_length=None):
    values = []
    for _ in range(count):
        if ptype == 1:
            values.append(struct.unpack_from("<i", buf, pos)[0])
            pos += 4
        elif ptype == 2:
            values.append(struct.unpack_from("<q", buf, pos)[0])
            pos += 8
        elif ptype == 4:
            values.append(struct.unpack_from("<f", buf, pos)[0])
            pos += 4
        elif ptype == 5:
            values.append(struct.unpack_from("<d", buf, pos)[0])
            pos += 8
        elif ptype == 6:
            n = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
            values.append(bytes(buf[pos:pos + n]))
            pos += n
        elif ptype == 7:
            values.append(bytes(buf[pos:pos + type_length]))
            pos += type_length
        else:
            raise ValueError("unsupported parquet type %d" % ptype)
    return values


def _parquet_fallback(path):
    buf = Path(path).read_bytes()
    if buf[:4] != b"PAR1" or buf[-4:] != b"PAR1":
        raise ValueError("not a parquet file: %s" % path)
    meta_len = struct.unpack("<I", buf[-8:-4])[0]
    meta = _Thrift(buf, len(buf) - 8 - meta_len).struct()
    schema = meta[2]
    leaves = []
    for element in schema[1:]:
        if element.get(5):
            raise ValueError("nested parquet schema unsupported")
        leaves.append(
            {
                "name": element[4].decode("utf-8"),
                "type": element.get(1),
                "optional": element.get(3, 0) == 1,
                "converted": element.get(6),
                "logical": element.get(10),
                "type_length": element.get(2),
            }
        )
    columns = {leaf["name"]: [] for leaf in leaves}
    for rg in meta.get(4, []):
        for idx, chunk in enumerate(rg[1]):
            leaf = leaves[idx]
            cm = chunk[3]
            codec = cm[4]
            total = cm[5]
            offset = cm.get(11) if cm.get(11) is not None else cm[9]
            if cm.get(11) is not None and cm[9] < offset:
                offset = cm[9]
            dictionary = None
            got = []
            while len(got) < total:
                reader = _Thrift(buf, offset)
                header = reader.struct()
                body_start = reader.pos
                csize = header[3]
                usize = header[2]
                body = buf[body_start:body_start + csize]
                offset = body_start + csize
                ptype = header[1]
                if ptype == 2:
                    data = _decompress(codec, body)
                    dictionary = _plain(leaf["type"], data, 0, header[7][1], leaf["type_length"])
                    continue
                if ptype == 0:
                    dh = header[5]
                    n = dh[1]
                    encoding = dh[2]
                    data = _decompress(codec, body)
                    pos = 0
                    defs = [1] * n
                    if leaf["optional"]:
                        dlen = struct.unpack_from("<I", data, pos)[0]
                        pos += 4
                        defs = _hybrid(data, pos, pos + dlen, 1, n)
                        pos += dlen
                elif ptype == 3:
                    dh = header[8]
                    n = dh[1]
                    encoding = dh[4]
                    dl = dh.get(5, 0)
                    rl = dh.get(6, 0)
                    levels = bytes(body[:dl + rl])
                    rest = bytes(body[dl + rl:])
                    if dh.get(7, True):
                        rest = _decompress(codec, rest)
                    data = rest
                    pos = 0
                    defs = _hybrid(levels, rl, rl + dl, 1, n) if leaf["optional"] else [1] * n
                else:
                    continue
                present = sum(1 for d in defs if d)
                if encoding in (2, 8):
                    width = data[pos]
                    idxs = _hybrid(data, pos + 1, len(data), width, present)
                    vals = [dictionary[i] for i in idxs]
                elif encoding == 0:
                    vals = _plain(leaf["type"], data, pos, present, leaf["type_length"])
                else:
                    raise ValueError("unsupported parquet encoding %d" % encoding)
                it = iter(vals)
                got.extend(next(it) if d else None for d in defs)
            columns[leaf["name"]].extend(got)
    for leaf in leaves:
        if leaf["type"] == 6 and (leaf["converted"] == 0 or (leaf["logical"] or {}).get(1) is not None):
            columns[leaf["name"]] = [v.decode("utf-8") if v is not None else None for v in columns[leaf["name"]]]
    names = [leaf["name"] for leaf in leaves]
    count = len(columns[names[0]]) if names else 0
    return [{name: columns[name][i] for name in names} for i in range(count)]


def read_parquet_rows(path):
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return _parquet_fallback(path)
    return pq.read_table(path).to_pylist()


# ------------------------------------------------------------- resolution ---


def _int(value, default=None):
    if value is None or value == "":
        return default
    return int(str(value).strip().strip('"'))


def _first_int(text, key):
    match = re.search(r"^\s*" + re.escape(key) + r"\s*[=:]\s*(-?[0-9]+)", text, flags=re.M)
    return int(match.group(1)) if match else None


class Resolver:
    def __init__(self, data_dir):
        self.data = Path(data_dir)
        self.order = []

    def path(self, name):
        if name not in self.order:
            self.order.append(name)
        return self.data / name

    def run(self):
        manifest = read_toml(self.path("boot_manifest.toml"))["manifest"]
        instant = int(manifest["effective_instant"])
        active_bundle = str(manifest["active_bundle_id"])
        latest_bundle = manifest.get("latest_bundle_id")

        ledger = read_jsonc(self.path("bundle_ledger.jsonc"))
        bundle = ledger[active_bundle]
        role_key = bundle["role_key"]
        index_name = bundle.get("index_file", "principal_role_index.yaml")
        index = read_yaml_flat(self.path(index_name))

        def role_info(role):
            return (
                index[role + ".param_key"],
                index[role + ".tenant"],
                int(index[role + ".role_level"]),
            )

        param_key, tenant, role_level = role_info(role_key)

        vmap = load_json(self.path("policy_version_map.json"))
        version_from = {}
        for entry in vmap["versions"]:
            version_from[str(entry["version"])] = int(entry["effective_from"])
        candidates = [(eff, ver) for ver, eff in version_from.items() if eff <= instant]
        effective_version = max(candidates)[1] if candidates else None

        client_versions = []
        corpus_path = self.data / "request_corpus.json"
        if corpus_path.exists():
            corpus = load_json(self.path("request_corpus.json"))
            client_versions = sorted({str(e.get("claimed_version")) for e in corpus.get("entries", []) if e.get("claimed_version") is not None})

        base_rows = {str(row["param_key"]): row for row in read_parquet_rows(self.path("base_parameters.parquet"))}

        windows = {w["id"]: w for w in read_xml_records(self.path("effective_windows.xml"), "window")}

        doc = load_json(self.path("override_deltas.json"))
        overrides = sorted(doc.get("overrides", []), key=lambda r: int(r["seq"]))
        aliases = doc.get("param_key_aliases") or []
        reports = doc.get("reports") or []

        precedence = read_conf_sections(self.path("override_precedence.conf"))
        units_text = self.path("units_reference.txt").read_text(encoding="utf-8")
        cutover = _first_int(units_text, "timeout_ms_delta cutover")
        if cutover is None:
            cutover = _first_int(units_text, "cutover")
        catalog = {t["id"]: t for t in read_xml_records(self.path("tenant_catalog.xml"), "tenant")}
        quota = read_conf_sections(self.path("quota_limits.cfg"))
        allowance = {k: int(v) for k, v in quota.get("override_allowance", {}).items()}

        def ms_delta(row):
            raw = int(row["timeout_ms_delta"])
            eff = version_from.get(str(row.get("version")))
            if cutover is not None and eff is not None and eff < cutover:
                return raw * 1000
            return raw

        # controls: parse and count control over every stored row
        sums = {}
        for row in overrides:
            entry = sums.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
            entry["rows"] += 1
            entry["max_records_delta_sum"] += int(row["max_records_delta"])
            entry["timeout_ms_delta_sum_ms"] += ms_delta(row)
        ledger_controls = {}
        for name, control in sorted(doc.get("controls", {}).items()):
            got = sums.get(name, {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
            ok = all(int(control[k]) == got.get(k) for k in control if k in got) and all(k in control for k in got)
            ledger_controls[name] = "ok" if ok else "mismatch"

        def principal_of(row):
            key = str(row["param_key"])
            for alias in aliases:
                if str(alias.get("alias")) == key:
                    if int(alias["start"]) <= instant < int(alias["end"]):
                        return str(alias["principal"])
                    return None
            return key

        def window_live(window_id):
            window = windows.get(window_id)
            if window is None:
                return None
            if not (int(window["start"]) <= instant < int(window["end"])):
                return None
            return window

        last_seq = {}
        for row in overrides:
            last_seq[row["override_id"]] = int(row["seq"])

        # selection
        selected = []
        for row in overrides:
            seq = int(row["seq"])
            if last_seq[row["override_id"]] != seq:
                continue
            status = row.get("status")
            source = row
            if status == "reinstated":
                prior = [r for r in overrides if r["override_id"] == row["override_id"] and int(r["seq"]) < seq and r.get("status") == "active"]
                if not prior:
                    continue
                source = prior[-1]
            elif status != "active":
                continue
            window = window_live(row.get("window_id"))
            if window is None:
                continue
            if str(row.get("version")) != effective_version or str(window.get("version")) != effective_version:
                continue
            selected.append((row, source))

        # draw
        admit_left = {wid: int(w.get("admit", 0)) for wid, w in windows.items()}
        allowance_left = dict(allowance)
        applied = []
        applied_ids = set()
        for row, source in selected:
            requires = row.get("requires")
            if requires and requires not in applied_ids:
                continue
            region = catalog.get(row["tenant"], {}).get("region")
            wid = row["window_id"]
            if allowance_left.get(region, 0) <= 0 or admit_left.get(wid, 0) <= 0:
                continue
            allowance_left[region] -= 1
            admit_left[wid] -= 1
            applied.append((row, source))
            applied_ids.add(row["override_id"])

        # timeout pool per window
        added_timeout = {}
        by_window = {}
        for row, source in applied:
            delta = ms_delta(source)
            if delta <= 0:
                added_timeout[int(row["seq"])] = delta
            else:
                by_window.setdefault(row["window_id"], []).append((int(row["seq"]), delta))
        for wid, items in by_window.items():
            pool = int(windows[wid].get("timeout_pool", 0))
            total = sum(d for _, d in items)
            if total <= pool:
                for seq, d in items:
                    added_timeout[seq] = d
                continue
            first = {seq: (pool * d) // total for seq, d in items}
            keep = [(seq, d) for seq, d in items if first[seq] >= 100]
            kept_total = sum(d for _, d in keep)
            for seq, d in items:
                added_timeout[seq] = 0
            for seq, d in keep:
                added_timeout[seq] = (pool * d) // kept_total

        carries = []
        for row in overrides:
            if row.get("status") != "superseded" or not row.get("carry"):
                continue
            window = window_live(row.get("window_id"))
            if window is None:
                continue
            if str(row.get("version")) != effective_version or str(window.get("version")) != effective_version:
                continue
            carries.append(row)

        mult_rows = {}
        mult_name = "tenant_multiplier_table.xlsx"
        for row in read_xlsx_rows(self.path(mult_name)):
            mult_rows[str(row.get("tenant"))] = row
        constants = read_kv_text(self.path("numeric_constants.env")) if (self.data / "numeric_constants.env").exists() else {}
        mult_default = _int(constants.get("MULT_BPS_DEFAULT"), 1000)

        tiers = {int(row["tier"]): row for row in read_parquet_rows(self.path("threshold_tier_curve.parquet"))}
        spec_text = self.path("convergence_spec.txt").read_text(encoding="utf-8")
        epsilon = _first_int(spec_text, "convergence_epsilon") or 0
        max_iterations = _first_int(spec_text, "max_iterations") or 64
        rules = read_conf(self.path("reconciliation_rules.conf"))
        conf_divisor = int(rules["iteration_divisor"])
        rules_text = (self.data / "reconciliation_rules.conf").read_text(encoding="utf-8")
        span = re.search(r"from\s+([0-9]+)\s+to\s+([0-9]+)", rules_text)
        div_lo, div_hi = (int(span.group(1)), int(span.group(2))) if span else (1, 64)

        def principal_numbers(pkey, ptenant):
            base = base_rows[pkey]
            mine = [(row, source) for row, source in applied if principal_of(row) == pkey]
            mult = mult_rows.get(ptenant, {})
            mult_bps = _int(mult.get("mult_bps"), mult_default)
            cap = _int(mult.get("max_records_cap"))
            mr_total = int(base["max_records_base"]) + sum(int(s["max_records_delta"]) for _, s in mine)
            terms = [int(base["risk_weight_base"])] + [int(s["risk_delta"]) for _, s in mine]
            for row in carries:
                if principal_of(row) != pkey:
                    continue
                if row["carry"] == "max_records_delta":
                    mr_total += int(row["max_records_delta"])
                elif row["carry"] == "risk_delta":
                    terms.append(int(row["risk_delta"]))
            scaled = round_half_up(mr_total * mult_bps, 1000)
            max_records = scaled if cap is None else min(cap, scaled)
            retry_limit = int(base["retry_limit_base"]) + sum(int(s["retry_limit_delta"]) for _, s in mine)
            timeout = int(base["timeout_seconds_base"]) * 1000
            for row, _ in mine:
                timeout += added_timeout.get(int(row["seq"]), 0)
                if timeout < 1000:
                    timeout = 1000
            contribution = sum(round_half_up(t * mult_bps, 1000) for t in terms)
            return {
                "max_records": max_records,
                "retry_limit": retry_limit,
                "timeout_ms": timeout,
                "contribution": contribution,
                "applied": [row["override_id"] for row, _ in mine],
            }

        def curve(level, contribution, divisor):
            base_threshold = int(tiers[level]["base_threshold"])
            t = base_threshold
            iterations = [t]
            converged = None
            if divisor is None:
                return base_threshold, iterations, None
            for _ in range(max_iterations):
                nxt = base_threshold + (contribution + t) // divisor
                iterations.append(nxt)
                if abs(nxt - t) <= epsilon:
                    converged = nxt
                    break
                t = nxt
            return base_threshold, iterations, converged

        resets = [int(r["seq"]) for r in reports if r.get("kind") == "reset"]
        standing = [r for r in reports if r.get("kind") == "curve" and not any(s > int(r["seq"]) for s in resets)]
        if not standing:
            divisor = conf_divisor
        else:
            fits = []
            for cand in range(div_lo, div_hi + 1):
                good = True
                for rep in standing:
                    rkey, rtenant, rlevel = role_info(rep["role"])
                    nums = principal_numbers(rkey, rtenant)
                    _, _, conv = curve(rlevel, nums["contribution"], cand)
                    if conv is None or conv != int(rep["converged"]):
                        good = False
                        break
                if good:
                    fits.append(cand)
            divisor = fits[0] if len(fits) == 1 else None

        nums = principal_numbers(param_key, tenant)
        base_threshold, iterations, converged = curve(role_level, nums["contribution"], divisor)

        defaults = load_json(self.path("defaults.json"))
        schema = load_json(self.path("config_schema.json"))
        resolved = {
            "profile": schema["profile"],
            "producer": schema.get("producer", defaults.get("producer")),
            "container": schema.get("container", defaults.get("container")),
            "checksum": schema.get("checksum", defaults.get("checksum")),
            "mode": defaults["mode"],
            "max_records": nums["max_records"],
            "retry_limit": nums["retry_limit"],
            "timeout_ms": nums["timeout_ms"],
            "trailer": str(defaults["base_config"]["trailer"]),
            "param_key": param_key,
            "tenant": tenant,
            "effective_version": effective_version,
            "risk_threshold": converged,
        }

        rejected = []
        if latest_bundle is not None and str(latest_bundle) != active_bundle:
            rejected.append({"id": str(latest_bundle), "reason": "latest_bundle_id in boot_manifest.toml is not the active bundle; active_bundle_id %s is authoritative" % active_bundle})
        for bid in sorted(ledger):
            entry = ledger[bid]
            if bid == active_bundle or not isinstance(entry, dict):
                continue
            status = entry.get("status")
            if status in ("superseded", "retired") and bid != str(latest_bundle):
                rejected.append({"id": bid, "reason": "bundle %s in bundle_ledger.jsonc" % status})
        for name, reason in (
            ("legacy_override_table.ini", "legacy overrides of the superseded bundle; override_deltas.json is authoritative"),
            ("superseded_windows.xml", "superseded effective windows; effective_windows.xml is authoritative"),
            ("principal_alias_table.jsonc", "aliases of a retired bundle conflict with the active role index"),
            ("legacy_policy_memo.pdf", "audit memo of the superseded bundle"),
        ):
            if (self.data / name).exists():
                rejected.append({"file": name, "reason": reason})
        for ver in client_versions:
            if ver != effective_version:
                rejected.append({"id": ver, "reason": "client claimed_version in request_corpus.json ignored; effective version comes from policy_version_map.json"})
        applied_set = {id(row) for row, _ in applied}
        for row in overrides:
            if principal_of(row) == param_key and id(row) not in applied_set:
                rejected.append({"id": row["override_id"], "seq": int(row["seq"]), "reason": "override row not applied (status %s, window %s, version %s)" % (row.get("status"), row.get("window_id"), row.get("version"))})

        trace = {
            "active_bundle": active_bundle,
            "effective_version": effective_version,
            "param_key": param_key,
            "tenant": tenant,
            "client_version_ignored": True,
            "applied_overrides": nums["applied"],
            "ledger_controls": ledger_controls,
            "resolution_order": list(self.order),
            "rejected_branches": rejected,
        }
        threshold_curve = {
            "tier": role_level,
            "base_threshold": base_threshold,
            "contribution": nums["contribution"],
            "iterations": iterations,
            "converged": converged,
        }
        return resolved, trace, threshold_curve


def resolve_policy(data_dir):
    return Resolver(data_dir).run()


# --------------------------------------------------------------- commands ---


def cmd_init(args):
    schema = load_json(args.schema)
    data = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema["checksum"],
        "mode": schema.get("mode", "strict-local"),
    }
    write_json(args.out, data)
    print("initialized")


def cmd_resolve(args):
    resolved, trace, curve = resolve_policy(args.data_dir)
    out = Path(args.out)
    write_json(out / "policy_resolved.json", resolved)
    write_json(out / "dependency_trace.json", trace)
    write_json(out / "threshold_curve.json", curve)
    print(json.dumps(resolved, sort_keys=True))


def cmd_set(args):
    data = load_json(args.config)
    data[args.key] = coerce(args.value)
    assert_flat(data)
    write_json(args.config, data)
    print("set " + args.key)


def cmd_validate(args):
    schema = load_json(args.schema)
    data = load_json(args.config)
    assert_flat(data)
    required = schema["required_keys"]
    if isinstance(required, str):
        required = [key.strip() for key in required.split(",") if key.strip()]
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_report(args):
    data = load_json(args.config)
    commands = json.loads(args.commands)
    report = {
        "ok": all(int(c.get("returncode", 1)) == 0 for c in commands),
        "tool": "sentinel-ctl",
        "config_sha256": args.digest,
        "commands": commands,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def main():
    parser = argparse.ArgumentParser(prog="sentinel-ctl")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--schema", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("resolve")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("set")
    p.add_argument("--config", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("validate")
    p.add_argument("--schema", required=True)
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
