#!/usr/bin/env python3
"""Meter one billing period extract of the multi-region SQL query fleet.

Usage: python3 transform.py DATA_DIR OUT_DIR

Writes the thirteen reports defined by report_layout.md into OUT_DIR, one
line per report on standard output giving the file name and its size in bytes.
"""

import json
import os
import sys

MS = 1000
S_PER_DAY = 86400
BUNDLE = 1073741824
REGION_NAMES = ("central", "east", "north", "south", "west")
SEGMENT_NAMES = ("consumer", "corporate", "enterprise", "smb")


# ---------------------------------------------------------------- time types


class Inst:
    """An instant on the reference clock, in whole milliseconds."""

    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __eq__(self, o):
        return self.v == o.v

    def __lt__(self, o):
        return self.v < o.v


class Ldt:
    """A local wall-clock reading, in whole milliseconds since the epoch."""

    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v


def days_from_civil(y, m, d):
    """Days from 1970-01-01 to the given proleptic Gregorian date."""
    y2 = y - (1 if m <= 2 else 0)
    era = (y2 if y2 >= 0 else y2 - 399) // 400
    yoe = y2 - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    """Inverse of days_from_civil."""
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (1 if m <= 2 else 0), m, d


def parse_local(s):
    """Parse `YYYY-MM-DDTHH:MM:SS.mmm` into milliseconds since the epoch."""
    if (
        len(s) != 23
        or s[4] != "-"
        or s[7] != "-"
        or s[10] != "T"
        or s[13] != ":"
        or s[16] != ":"
        or s[19] != "."
    ):
        return None
    for ch in s[0:4] + s[5:7] + s[8:10] + s[11:13] + s[14:16] + s[17:19] + s[20:23]:
        if ch < "0" or ch > "9":
            return None
    y, mo, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    if mo < 1 or mo > 12 or d < 1:
        return None
    k = days_from_civil(y, mo, d)
    if civil_from_days(k) != (y, mo, d):
        return None
    if int(s[11:13]) > 23 or int(s[14:16]) > 59 or int(s[17:19]) > 59:
        return None
    return k * S_PER_DAY * MS + (
        (int(s[11:13]) * 3600 + int(s[14:16]) * 60 + int(s[17:19])) * MS
        + int(s[20:23])
    )


def parse_ref(s):
    """Parse `YYYY-MM-DDTHH:MM:SS.mmmZ` into an Inst, or None."""
    if len(s) != 24 or s[23] != "Z":
        return None
    v = parse_local(s[:23])
    return None if v is None else Inst(v)


def fmt_local(v):
    """Format whole milliseconds since the epoch as `YYYY-MM-DDTHH:MM:SS.mmm`."""
    days, rem = divmod(v, S_PER_DAY * MS)
    y, m, d = civil_from_days(days)
    secs, ms = divmod(rem, MS)
    h, r = divmod(secs, 3600)
    mi, s = divmod(r, 60)
    return "%04d-%02d-%02dT%02d:%02d:%02d.%03d" % (y, m, d, h, mi, s, ms)


def fmt_ref(t):
    return fmt_local(t.v) + "Z"


def parse_int(s):
    if not s or (s[0] != "-" and (s[0] < "0" or s[0] > "9")):
        return None
    for ch in s[1:]:
        if ch < "0" or ch > "9":
            return None
    return int(s)


def parse_date(s):
    """Parse `YYYY-MM-DD` into days since the epoch, or None."""
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        return None
    for ch in s[0:4] + s[5:7] + s[8:10]:
        if ch < "0" or ch > "9":
            return None
    y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    if m < 1 or m > 12 or d < 1:
        return None
    k = days_from_civil(y, m, d)
    if civil_from_days(k) != (y, m, d):
        return None
    return k


def fmt_date(days):
    return "%04d-%02d-%02d" % civil_from_days(days)


# ---------------------------------------------------------------- file reads


def read_text(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


def read_csv(path):
    """Rows of a CSV file as lists of trimmed strings; None on any error."""
    try:
        text = read_text(path)
    except OSError:
        return None
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    rows = []
    field = []
    cells = []
    quoted = False
    for ln in lines:
        if ln == "" and not rows:
            continue
        for ch in ln:
            if quoted:
                if ch == '"':
                    quoted = False
                else:
                    field.append(ch)
            elif ch == ",":
                cells.append("".join(field))
                field = []
            elif ch == '"':
                quoted = True
            else:
                field.append(ch)
        if quoted:
            return None
        cells.append("".join(field))
        rows.append([c.strip() for c in cells])
        cells = []
        field = []
    if not rows:
        return None
    return rows


def read_json_file(path):
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- zone logic


class Zone:
    __slots__ = ("std", "dst", "periods", "holidays")

    def __init__(self):
        self.std = 0
        self.dst = 0
        self.periods = []
        self.holidays = set()


def load_zones(doc):
    zones = {}
    if not isinstance(doc, dict) or not isinstance(doc.get("zones"), dict):
        return zones
    for name, z in doc["zones"].items():
        if not isinstance(name, str) or not isinstance(z, dict):
            continue
        std = z.get("standard_offset_minutes")
        dst = z.get("daylight_offset_minutes")
        if not isinstance(std, int) or isinstance(std, bool):
            continue
        if not isinstance(dst, int) or isinstance(dst, bool):
            continue
        zz = Zone()
        zz.std = std * 60 * MS
        zz.dst = dst * 60 * MS
        periods = z.get("daylight_periods")
        if isinstance(periods, list):
            for p in periods:
                if not isinstance(p, dict):
                    continue
                s = p.get("start")
                e = p.get("end")
                if not isinstance(s, str) or not isinstance(e, str):
                    continue
                si = parse_ref(s)
                ei = parse_ref(e)
                if si is None or ei is None:
                    continue
                zz.periods.append((si.v, ei.v))
        holidays = z.get("holidays")
        if isinstance(holidays, list):
            for h in holidays:
                if isinstance(h, str) and parse_date(h) is not None:
                    zz.holidays.add(h)
        zones[name] = zz
    return zones


def zone_offset_ms(z, v):
    for s, e in z.periods:
        if s <= v < e:
            return z.dst
    return z.std


def local_ms(z, v):
    return v + zone_offset_ms(z, v)


def local_day(z, v):
    return (v + zone_offset_ms(z, v)) // (S_PER_DAY * MS)


# ---------------------------------------------------------------- reporting


def write_report(outdir, name, text):
    data = text.encode("utf-8")
    with open(os.path.join(outdir, name), "wb") as f:
        f.write(data)
    return len(data)


def json_dumps(obj):
    """One JSON object with two-space indentation, LF-terminated."""
    return dump_value(obj, 0) + "\n"


def dump_value(v, indent):
    pad = "  " * indent
    pad2 = "  " * (indent + 1)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return quote(v)
    if v is None:
        return "null"
    if isinstance(v, list):
        if not v:
            return "[]"
        items = [pad2 + dump_value(x, indent + 1) for x in v]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    if isinstance(v, dict):
        if not v:
            return "{}"
        parts = [
            pad2 + quote(k) + ": " + dump_value(v[k], indent + 1)
            for k in sorted(v)
        ]
        return "{\n" + ",\n".join(parts) + "\n" + pad + "}"
    raise TypeError(repr(v))


_ESC = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f",
        "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def quote(s):
    out = ['"']
    for ch in s:
        if ch in _ESC:
            out.append(_ESC[ch])
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def compact(obj):
    """An object in one line, no spaces outside string values."""
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, str):
        return quote(obj)
    if obj is None:
        return "null"
    if isinstance(obj, list):
        return "[" + ",".join(compact(x) for x in obj) + "]"
    if isinstance(obj, dict):
        return "{" + ",".join(quote(k) + ":" + compact(obj[k]) for k in sorted(obj)) + "}"
    raise TypeError(repr(obj))


def div_round_half_up(num, den):
    """num/den rounded to a whole number, halves rounded up (num, den > 0)."""
    return (2 * num + den) // (2 * den)


# ---------------------------------------------------------------- clock work


def node_offsets(nodes, transfers):
    """Offsets, in seconds, of every node clock ahead of the reference clock.

    Returns None when no assignment satisfies the transfer constraints.
    """
    off = {}
    for node_id, info in nodes.items():
        off[node_id] = 0 if info[1] == "reference" else None
    unknown = sorted(n for n in off if off[n] is None)
    cons = []
    for from_node, sent, to_node, recv in transfers:
        if from_node not in off or to_node not in off:
            continue
        d = recv.v - sent.v  # local-stamp difference, in milliseconds
        # transfer_ms = d - 1000*(off_to - off_from) must lie in [0, 4999]
        cons.append((from_node, to_node, d - 4999, d))
    for f, t, lo, hi in cons:
        if off[f] is not None and off[t] is not None:
            if not (lo <= (off[t] - off[f]) * MS <= hi):
                return None
    if not unknown:
        return off
    idx = {n: i for i, n in enumerate(unknown)}
    cand = {n: list(range(-19, 20)) for n in unknown}
    for _ in range(len(unknown) + 1):
        changed = False
        for f, t, lo, hi in cons:
            a = off.get(f)
            b = off.get(t)
            if a is not None and b is not None:
                continue
            if a is not None:
                cur = cand[t]
                nv = [x for x in cur if lo <= (x - a) * MS <= hi]
                if nv != cur:
                    cand[t] = nv
                    changed = True
            elif b is not None:
                cur = cand[f]
                nv = [x for x in cur if lo <= (b - x) * MS <= hi]
                if nv != cur:
                    cand[f] = nv
                    changed = True
            else:
                ca, cb = cand[f], cand[t]
                na = [x for x in ca if any(lo <= (y - x) * MS <= hi for y in cb)]
                nb = [y for y in cb if any(lo <= (y - x) * MS <= hi for x in ca)]
                if na != ca:
                    cand[f] = na
                    changed = True
                if nb != cb:
                    cand[t] = nb
                    changed = True
        if not changed:
            break
    if any(len(cand[n]) != 1 for n in unknown):
        return None
    for n in unknown:
        off[n] = cand[n][0]
    return off


# ---------------------------------------------------------------- metering


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = argv[1]
    out_dir = argv[2]

    # ---- registers -----------------------------------------------------
    nodes_rows = read_csv(os.path.join(data_dir, "nodes.csv"))
    nodes = {}
    if nodes_rows and nodes_rows[0] == ["node_id", "region", "role"]:
        for r in nodes_rows[1:]:
            if len(r) != 3 or not r[0]:
                continue
            role = r[2].lower()
            region = r[1].lower()
            nodes[r[0]] = (
                region,
                role if role in ("reference", "member") else "member",
            )
    regions_by_node = {n: nodes[n][0] for n in nodes}
    region_scope = set(regions_by_node.values())

    tenants_rows = read_csv(os.path.join(data_dir, "tenants.csv"))
    tenants = {}
    if tenants_rows and tenants_rows[0] == [
        "tenant_id", "display_name", "segment", "plan", "zone"
    ]:
        for r in tenants_rows[1:]:
            if len(r) != 5 or not r[0]:
                continue
            tenants[r[0]] = (r[2].lower(), r[3], r[4])

    products_rows = read_csv(os.path.join(data_dir, "products.csv"))
    products = {}
    if products_rows and products_rows[0] == ["product_id", "product_line", "name"]:
        for r in products_rows[1:]:
            if len(r) != 3 or not r[0]:
                continue
            products[r[0]] = r[1].lower()

    plans_doc = read_json_file(os.path.join(data_dir, "plans.json"))
    plans = {}
    if isinstance(plans_doc, dict) and isinstance(plans_doc.get("plans"), dict):
        for code, versions in plans_doc["plans"].items():
            if not isinstance(code, str) or not isinstance(versions, list):
                continue
            lst = []
            for v in versions:
                if not isinstance(v, dict):
                    continue
                ef = v.get("effective_from")
                if not isinstance(ef, str):
                    continue
                efi = parse_ref(ef)
                if efi is None:
                    continue
                if not isinstance(v.get("version"), str):
                    continue
                ints = (
                    "daily_free_bytes",
                    "min_billable_bytes",
                    "block_bytes",
                    "peak_micros_per_gib",
                    "offpeak_micros_per_gib",
                )
                vals = []
                ok = True
                for k in ints:
                    x = v.get(k)
                    if not isinstance(x, int) or isinstance(x, bool):
                        ok = False
                        break
                    vals.append(x)
                if not ok:
                    continue
                lst.append((efi.v, v["version"], vals[0], vals[1], vals[2], vals[3], vals[4]))
            lst.sort(key=lambda t: (t[0], t[1]))
            plans[code] = lst

    zones = load_zones(read_json_file(os.path.join(data_dir, "zones.json")))

    merges_rows = read_csv(os.path.join(data_dir, "tenant_merges.csv"))
    merge_by_absorbed = {}
    if merges_rows and merges_rows[0] == [
        "absorbed_tenant", "surviving_tenant", "effective_at"
    ]:
        for r in merges_rows[1:]:
            if len(r) != 3:
                continue
            at = parse_ref(r[2])
            if at is None:
                continue
            merge_by_absorbed.setdefault(r[0], []).append((at.v, r[1]))

    # ---- transfers -----------------------------------------------------
    transfer_lines = 0
    transfers = []
    path = os.path.join(data_dir, "transfers.log")
    if os.path.isfile(path):
        for line in read_text(path).split("\n"):
            if line == "" or line[0] == "#":
                continue
            parts = line.split("|")
            if len(parts) != 5:
                continue
            f = [p.strip() for p in parts]
            sent = parse_local(f[2])
            recv = parse_local(f[4])
            if sent is None or recv is None:
                continue
            transfers.append((f[1], Ldt(sent), f[3], Ldt(recv)))
            transfer_lines += 1
    offsets = node_offsets(nodes, transfers)
    if offsets is None:
        offsets = {n: 0 for n in nodes}

    # ---- queries -------------------------------------------------------
    rows = read_csv(os.path.join(data_dir, "queries.csv"))
    query_rows = len(rows) - 1 if rows else 0
    queries = []
    if rows and rows[0] == [
        "query_id", "node_id", "tenant_id", "product_id",
        "started_local", "duration_ms", "scanned_bytes", "status",
    ]:
        for r in rows[1:]:
            if len(r) != 8:
                continue
            started = parse_local(r[4])
            dur = parse_int(r[5])
            scanned = parse_int(r[6])
            status = r[7].lower()
            if (
                started is None
                or dur is None
                or scanned is None
                or dur < 0
                or scanned < 0
                or status not in ("ok", "cancelled", "failed")
                or not r[0]
                or r[1] not in nodes
                or r[2] not in tenants
                or r[3] not in products
            ):
                continue
            queries.append(
                {
                    "query_id": r[0],
                    "node_id": r[1],
                    "source_tenant_id": r[2],
                    "product_id": r[3],
                    "started_local": started,
                    "duration_ms": dur,
                    "logged_scanned_bytes": scanned,
                    "scanned_bytes": scanned,
                    "status": status,
                }
            )
    rejected = query_rows - len(queries)

    # ---- corrections ---------------------------------------------------
    corrections = []
    path = os.path.join(data_dir, "corrections.jsonl")
    if os.path.isfile(path):
        for line in read_text(path).split("\n"):
            if line == "":
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            cid = obj.get("correction_id")
            qid = obj.get("query_id")
            at = obj.get("recorded_at")
            action = obj.get("action")
            if not isinstance(cid, str) or not isinstance(qid, str):
                continue
            if not isinstance(at, str) or action not in ("restate", "void", "reinstate"):
                continue
            ati = parse_ref(at)
            if ati is None:
                continue
            sb = obj.get("scanned_bytes")
            if action == "restate":
                if not isinstance(sb, int) or isinstance(sb, bool) or sb < 0:
                    continue
            elif sb is not None and (not isinstance(sb, int) or isinstance(sb, bool) or sb < 0):
                continue
            corrections.append((ati.v, cid, qid, action, sb))
    corrections.sort(key=lambda c: (c[0], c[1]))
    by_id = {}
    for q in queries:
        by_id.setdefault(q["query_id"], []).append(q)
    voided = set()
    for _at, _cid, qid, action, sb in corrections:
        hits = by_id.get(qid)
        if not hits:
            continue
        if action == "restate":
            for q in hits:
                q["scanned_bytes"] = sb
        elif action == "void":
            voided.add(qid)
        else:
            voided.discard(qid)
    for q in queries:
        q["corrected"] = q["scanned_bytes"] != q["logged_scanned_bytes"]

    # ---- billing identity and window -----------------------------------
    def identity(tenant_id, at_ms):
        cur = tenant_id
        seen = set()
        while True:
            best = None
            for at, su in merge_by_absorbed.get(cur, ()):
                if at <= at_ms and (best is None or su < best):
                    best = su
            if best is None or best in seen:
                return cur
            seen.add(cur)
            cur = best

    failed = 0
    metered = []
    for q in queries:
        node_id = q["node_id"]
        at_ms = q["started_local"] - offsets[node_id] * MS + q["duration_ms"]
        q["start_ms"] = q["started_local"] - offsets[node_id] * MS
        tenant_id = identity(q["source_tenant_id"], at_ms)
        info = tenants.get(tenant_id)
        if info is None:
            continue
        q["billed_at"] = at_ms
        q["tenant_id"] = tenant_id
        q["segment"] = info[0]
        q["plan"] = info[1]
        q["zone"] = info[2]
        q["region"] = regions_by_node[node_id]
        if q["status"] == "failed":
            failed += 1
            continue
        if q["query_id"] in voided:
            continue
        metered.append(q)
    voided_count = sum(
        1 for q in queries if q["status"] != "failed" and q["query_id"] in voided
    )

    def rate_card(plan, at_ms):
        chosen = None
        for v in plans.get(plan, ()):
            if v[0] <= at_ms:
                chosen = v
        return chosen

    billed = []
    for q in metered:
        rc = rate_card(q["plan"], q["billed_at"])
        if rc is None:
            continue
        z = zones.get(q["zone"])
        if z is None:
            continue
        q["rc"] = rc
        q["z"] = z
        day = local_day(z, q["billed_at"])
        q["billing_day"] = day
        tod = local_ms(z, q["billed_at"]) - day * S_PER_DAY * MS
        wd = (day + 3) % 7  # 1970-01-01 was a Thursday: 0 = Monday
        hol = fmt_date(day) in z.holidays
        q["window"] = (
            "peak"
            if 0 <= wd <= 4 and not hol and 28800000 <= tod < 72000000
            else "offpeak"
        )
        mbb, bb = rc[3], rc[4]
        base = q["scanned_bytes"]
        if base < mbb:
            base = mbb
        q["metered_bytes"] = ((base + bb - 1) // bb) * bb if bb > 0 else base
        billed.append(q)

    billed.sort(key=lambda q: (q["billed_at"], q["query_id"]))

    # ---- allowance ------------------------------------------------------
    def day_start_ms(z, day):
        """Reference instant at which a local calendar day begins."""
        best = None
        for off in (z.std, z.dst):
            v = day * S_PER_DAY * MS - off
            if local_day(z, v) == day and (best is None or v < best):
                best = v
        return best

    groups = {}
    for q in billed:
        groups.setdefault((q["tenant_id"], q["billing_day"]), []).append(q)
    for (tid, day), qs in groups.items():
        z = qs[0]["z"]
        plan = qs[0]["plan"]
        v0 = day_start_ms(z, day)
        allowance = 0
        if v0 is not None:
            rc0 = rate_card(plan, v0)
            if rc0 is not None:
                allowance = rc0[2]
        # Billing order: ascending billing instant, then the smaller metered
        # bytes, then the earlier start, then the query id.  The three trailing
        # keys carry the ranking past equal billing instants; the shipped
        # allowance statement of the previous period fixes them.
        for q in sorted(
            qs,
            key=lambda x: (
                x["billed_at"],
                x["metered_bytes"],
                x["start_ms"],
                x["query_id"],
            ),
        ):
            take = q["metered_bytes"]
            if take > allowance:
                take = allowance
            if take < 0:
                take = 0
            q["free_bytes"] = take
            q["chargeable_bytes"] = q["metered_bytes"] - take
            allowance -= take
    for q in billed:
        rate = q["rc"][5] if q["window"] == "peak" else q["rc"][6]
        q["charge_micros"] = div_round_half_up(q["chargeable_bytes"] * rate, BUNDLE)

    # ---- normalized.jsonl ----------------------------------------------
    ledger = []
    for q in billed:
        ledger.append(
            {
                "billed_at": fmt_ref(Inst(q["billed_at"])),
                "billing_day": fmt_date(q["billing_day"]),
                "chargeable_bytes": q["chargeable_bytes"],
                "charge_micros": q["charge_micros"],
                "corrected": q["corrected"],
                "free_bytes": q["free_bytes"],
                "metered_bytes": q["metered_bytes"],
                "node_id": q["node_id"],
                "plan_version": q["rc"][1],
                "product_id": q["product_id"],
                "product_line": products[q["product_id"]],
                "query_id": q["query_id"],
                "region": q["region"],
                "scanned_bytes": q["scanned_bytes"],
                "segment": q["segment"],
                "source_tenant_id": q["source_tenant_id"],
                "tenant_id": q["tenant_id"],
                "window": q["window"],
            }
        )
    normalized = "".join(compact(rec) + "\n" for rec in ledger)

    # ---- aggregates -----------------------------------------------------
    def agg(items):
        return (
            len(items),
            sum(i["metered_bytes"] for i in items),
            sum(i["free_bytes"] for i in items),
            sum(i["chargeable_bytes"] for i in items),
            sum(i["charge_micros"] for i in items),
        )

    n_all, mb_all, fb_all, cb_all, cm_all = agg(billed)

    def group_sums(field):
        out = {}
        for q in billed:
            out[q[field]] = out.get(q[field], 0) + q["charge_micros"]
        return out

    by_region = group_sums("region")
    by_segment = group_sums("segment")
    by_window = group_sums("window")
    by_product_line = {}
    for q in billed:
        pl = products[q["product_id"]]
        by_product_line[pl] = by_product_line.get(pl, 0) + q["charge_micros"]
    by_plan_version = {}
    for q in billed:
        by_plan_version[q["rc"][1]] = by_plan_version.get(q["rc"][1], 0) + q["charge_micros"]

    region_reports = {}
    for name in REGION_NAMES:
        items = [q for q in billed if q["region"] == name]
        n, mb, fb, cb, cm = agg(items)
        by_w = {"offpeak": 0, "peak": 0}
        for q in items:
            by_w[q["window"]] += q["charge_micros"]
        region_reports[name] = {
            "region": name,
            "in_scope": name in region_scope,
            "nodes": sorted(n for n in nodes if nodes[n][0] == name),
            "tenants": sorted({q["tenant_id"] for q in items}),
            "billed_queries": n,
            "metered_bytes": mb,
            "free_bytes": fb,
            "chargeable_bytes": cb,
            "charge_micros": cm,
            "by_window": by_w,
        }

    segment_reports = {}
    for name in SEGMENT_NAMES:
        items = [q for q in billed if q["segment"] == name]
        n, mb, fb, cb, cm = agg(items)
        by_r = {}
        for q in items:
            by_r[q["region"]] = by_r.get(q["region"], 0) + q["charge_micros"]
        segment_reports[name] = {
            "segment": name,
            "in_scope": n > 0,
            "tenants": sorted({q["tenant_id"] for q in items}),
            "billed_queries": n,
            "metered_bytes": mb,
            "free_bytes": fb,
            "chargeable_bytes": cb,
            "charge_micros": cm,
            "by_region": by_r,
        }

    product_entries = []
    for pid in sorted(products):
        items = [q for q in billed if q["product_id"] == pid]
        product_entries.append(
            {
                "product_id": pid,
                "product_line": products[pid],
                "billed_queries": len(items),
                "metered_bytes": sum(i["metered_bytes"] for i in items),
                "chargeable_bytes": sum(i["chargeable_bytes"] for i in items),
                "charge_micros": sum(i["charge_micros"] for i in items),
            }
        )

    ledger_total = cm_all
    region_total = sum(r["charge_micros"] for r in region_reports.values())
    segment_total = sum(r["charge_micros"] for r in segment_reports.values())
    product_total = sum(p["charge_micros"] for p in product_entries)
    residual = 3 * ledger_total - region_total - segment_total - product_total

    summary = {
        "billed_queries": n_all,
        "metered_bytes": mb_all,
        "free_bytes": fb_all,
        "chargeable_bytes": cb_all,
        "charge_micros": cm_all,
        "by_region": by_region,
        "by_segment": by_segment,
        "by_window": by_window,
        "by_product_line": by_product_line,
        "by_plan_version": by_plan_version,
        "reconciliation": {
            "ledger_charge_micros": ledger_total,
            "region_charge_micros": region_total,
            "segment_charge_micros": segment_total,
            "product_charge_micros": product_total,
            "residual_micros": residual,
        },
    }

    try:
        input_files = sorted(
            e for e in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, e))
        )
    except OSError:
        input_files = []

    data_quality = {
        "input_files": input_files,
        "query_rows": query_rows,
        "rejected_rows": rejected,
        "failed_queries": failed,
        "voided_queries": voided_count,
        "billed_queries": n_all,
        "corrected_queries": sum(1 for q in billed if q["corrected"]),
        "merged_queries": sum(
            1 for q in billed if q["tenant_id"] != q["source_tenant_id"]
        ),
        "transfer_lines": transfer_lines,
    }

    # ---- write ----------------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    sizes = {}
    sizes["normalized.jsonl"] = write_report(out_dir, "normalized.jsonl", normalized)
    sizes["summary.json"] = write_report(out_dir, "summary.json", json_dumps(summary))
    sizes["data_quality.json"] = write_report(
        out_dir, "data_quality.json", json_dumps(data_quality)
    )
    sizes["product_summary.json"] = write_report(
        out_dir, "product_summary.json", json_dumps({"products": product_entries})
    )
    for name in REGION_NAMES:
        sizes["region_%s.json" % name] = write_report(
            out_dir, "region_%s.json" % name, json_dumps(region_reports[name])
        )
    for name in SEGMENT_NAMES:
        sizes["segment_%s.json" % name] = write_report(
            out_dir, "segment_%s.json" % name, json_dumps(segment_reports[name])
        )
    for name in sorted(sizes):
        sys.stdout.write("%s %d\n" % (name, sizes[name]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
