# ---- reference rating engine (computes expected documents from input bytes) ----
import configparser as _ref_cp
import csv as _ref_csv
import datetime as _ref_dt
import io as _ref_io
import json as _ref_json
import re as _ref_re
import xml.etree.ElementTree as _ref_et
from bisect import bisect_right as _ref_bisect
from decimal import Decimal as _RD
from fractions import Fraction as _RF

REF_REGIONS = ("central", "east", "north", "south", "west")
REF_SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
REF_PRODUCTS = ("CMP", "EGR", "STO", "SUP")
REF_FILES = {
    "central": "collector_central.csv",
    "east": "collector_east.tsv",
    "north": "collector_north.jsonl",
    "south": "collector_south.txt",
    "west": "collector_west.log",
}
REF_INPUTS = (
    "collector_central.csv", "collector_east.tsv", "collector_north.jsonl",
    "collector_south.txt", "collector_west.log", "accounts.csv",
    "plan_changes.log", "rate_card.json", "commitments.xml", "products.ini",
    "collector_controls.json",
)
REF_REASONS = ("timestamp_outside_month", "unknown_account", "unknown_product", "units_not_integer")
_REF_UTC = _ref_dt.timezone.utc
_REF_DIGITS = _ref_re.compile(r"[0-9]+")


class RefStop(Exception):
    pass


def ref_canon(raw):
    return raw.strip().upper().replace("-", "")


def ref_cents(value):
    """Round a Fraction to 0.01 with ties to the even hundredth; returns int cents."""
    scaled = value * 100
    whole = scaled.numerator // scaled.denominator
    rest = scaled - whole
    if rest > _RF(1, 2) or (rest == _RF(1, 2) and whole % 2 == 1):
        whole += 1
    return whole


def ref_money(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)


def _ref_lines(text):
    return [ln for ln in text.split("\n") if ln.strip() != ""]


def _ref_records(region, raw):
    """Yield (record_id, utc datetime, account, product, units value, units kind)."""
    out = []
    if region == "central":
        lines = _ref_lines(raw.decode("utf-8"))
        for row in _ref_csv.reader(lines[1:]):
            f = [x.strip() for x in row]
            ts = _ref_dt.datetime.strptime(f[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=_REF_UTC)
            out.append((f[0], ts, f[2], f[3], f[4], "text"))
    elif region == "east":
        lines = _ref_lines(raw.decode("utf-8"))
        for ln in lines[1:]:
            f = [x.strip() for x in ln.split("\t")]
            ts = _ref_dt.datetime.fromtimestamp(int(f[1]), _REF_UTC)
            out.append((f[0], ts, f[2], f[3], f[4], "text"))
    elif region == "north":
        for ln in _ref_lines(raw.decode("utf-8")):
            obj = _ref_json.loads(ln)
            ts = _ref_dt.datetime.strptime(obj["at"].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_REF_UTC)
            out.append((obj["id"].strip(), ts, obj["acct"].strip(), obj["sku"].strip(), obj["units"], "json"))
    elif region == "south":
        for ln in _ref_lines(raw.decode("latin-1")):
            ts = _ref_dt.datetime.strptime(ln[10:24].strip(), "%Y%m%d%H%M%S").replace(tzinfo=_REF_UTC)
            out.append((ln[0:10].strip(), ts, ln[24:34].strip(), ln[34:46].strip(), ln[46:52].strip(), "text"))
    else:
        for ln in _ref_lines(raw.decode("utf-8")):
            parts = ln.strip().split(" ")
            ts = _ref_dt.datetime.fromisoformat(parts[0]).astimezone(_REF_UTC)
            kv = {}
            for p in parts[1:]:
                k, _, v = p.partition("=")
                kv[k] = v.strip()
            out.append((kv["rec"], ts, kv["acct"], kv["product"], kv["qty"], "text"))
    return out


def _ref_units_ok(value, kind):
    if kind == "json":
        return type(value) is int
    return isinstance(value, str) and _REF_DIGITS.fullmatch(value) is not None


def _ref_floor_share(total, lines, denom):
    """Share total cents over lines in proportion to charge (half-even 0.01); a share below 0.50
    becomes 0.00 and the whole total is shared again over only the lines that held 0.50 or more."""
    first = [(line, ref_cents(_RF(total * line["charge"], 100 * denom))) for line in lines]
    held = [line for line, share in first if share >= 50]
    kept = sum(line["charge"] for line in held)
    out = []
    for line, share in first:
        out.append((line, ref_cents(_RF(total * line["charge"], 100 * kept)) if share >= 50 else 0))
    return out


def ref_compute(files):
    """files: dict file name -> bytes. Returns dict document name -> parsed document."""
    for name in REF_INPUTS:
        if name not in files:
            raise RefStop("missing input: " + name)
    controls = _ref_json.loads(files["collector_controls.json"].decode("utf-8"))
    month = controls["month"].strip()
    year, mon = int(month[:4]), int(month[5:7])
    m_start = _ref_dt.datetime(year, mon, 1, tzinfo=_REF_UTC)
    m_end = _ref_dt.datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=_REF_UTC)

    ini = _ref_cp.ConfigParser(interpolation=None)
    ini.optionxform = str
    ini.read_string(files["products.ini"].decode("utf-8"))
    names = {r: {} for r in REF_REGIONS}
    units_of = {}
    for code in ini.sections():
        units_of[code.strip()] = ini[code]["unit"].strip()
        for r in REF_REGIONS:
            names[r][ini[code][r].strip()] = code.strip()

    card = _ref_json.loads(files["rate_card.json"].decode("utf-8"), parse_float=_RD)
    tiers = {}
    for code, spec in card["products"].items():
        rows = sorted(spec["tiers"], key=lambda t: t["from"])
        tiers[code] = [(int(t["from"]), int(t["tier"]), {s: _RD(t["rates"][s]) for s in REF_SEGMENTS}) for t in rows]
    starts = {code: [t[0] for t in ladder] for code, ladder in tiers.items()}

    accounts = {}
    group_of = {}
    acc_lines = _ref_lines(files["accounts.csv"].decode("utf-8"))
    parent_of = {}
    for row in _ref_csv.DictReader(acc_lines):
        accounts[ref_canon(row["account_id"])] = (row["segment"].strip(), row["plan"].strip())
        parent_of[ref_canon(row["account_id"])] = ref_canon(row["parent"] or "")
    for acct in parent_of:
        path = []
        top = acct
        while top not in group_of and parent_of[top]:
            path.append(top)
            top = parent_of[top]
        top = group_of.get(top, top)
        for member in path:
            group_of[member] = top
        group_of[acct] = top

    changes = {}
    pc_total = pc_applied = 0
    for idx, ln in enumerate(_ref_lines(files["plan_changes.log"].decode("utf-8"))):
        pc_total += 1
        parts = ln.strip().split()
        ts = _ref_dt.datetime.strptime(parts[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_REF_UTC)
        kv = dict(p.split("=", 1) for p in parts[2:])
        acct = ref_canon(kv["account"])
        if acct not in accounts:
            continue
        pc_applied += 1
        changes.setdefault(acct, []).append((ts, idx, {k: v.strip() for k, v in kv.items() if k in ("plan", "segment")}))

    root = _ref_et.fromstring(files["commitments.xml"].decode("utf-8"))
    pools = {p.get("region").strip(): int(_RD(p.get("amount").strip()) * 100) for p in root.iter("pool")}
    minimums = {p.get("region").strip(): int(_RD(p.get("minimum").strip()) * 100) for p in root.iter("pool")}

    collectors = {}
    quarantined = []
    reasons = {k: 0 for k in REF_REASONS}
    accepted = []
    for region in REF_REGIONS:
        fname = REF_FILES[region]
        recs = _ref_records(region, files[fname])
        expected = int(controls["collectors"][region]["records"])
        if len(recs) != expected:
            raise RefStop("control mismatch: " + fname)
        seen = set()
        dup = bad = good = 0
        for rid, ts, acct, prod, units, kind in recs:
            if rid in seen:
                dup += 1
                continue
            seen.add(rid)
            canon = ref_canon(acct)
            if not (m_start <= ts < m_end):
                reason = "timestamp_outside_month"
            elif canon not in accounts:
                reason = "unknown_account"
            elif prod not in names[region]:
                reason = "unknown_product"
            elif not _ref_units_ok(units, kind):
                reason = "units_not_integer"
            else:
                reason = None
            if reason:
                bad += 1
                reasons[reason] += 1
                quarantined.append({"collector": region, "record_id": rid, "reason": reason})
                continue
            good += 1
            accepted.append({"record_id": rid, "region": region, "ts": ts, "account_id": canon,
                             "product": names[region][prod], "units": int(units)})
        collectors[region] = {"file": fname, "records": len(recs), "duplicates": dup,
                              "quarantined": bad, "accepted": good}

    for lst in changes.values():
        lst.sort(key=lambda c: (c[0], c[1]))

    accepted.sort(key=lambda a: (a["ts"], a["record_id"]))
    cumulative = {}
    for line in accepted:
        seg, plan = accounts[line["account_id"]]
        for ts, _idx, fields in changes.get(line["account_id"], ()):
            if ts > line["ts"]:
                break
            seg = fields.get("segment", seg)
            plan = fields.get("plan", plan)
        key = (group_of[line["account_id"]], line["product"])
        before = cumulative.get(key, 0)
        ladder = tiers[line["product"]]
        frm, tier_no, rates = ladder[_ref_bisect(starts[line["product"]], before) - 1]
        chosen = (tier_no, rates[seg])
        cumulative[key] = before + line["units"]
        rate = chosen[1]
        line.update(segment=seg, plan=plan, tier=chosen[0], rate=rate,
                    charge=ref_cents(_RF(rate) * line["units"]))

    base = {r: 0 for r in REF_REGIONS}
    counted = {r: [] for r in REF_REGIONS}
    for line in accepted:
        line["credit"] = line["true_up"] = 0
        if accounts[line["account_id"]][1] == "committed":
            base[line["region"]] += line["charge"]
            counted[line["region"]].append(line)
    for r in REF_REGIONS:
        if base[r] <= pools[r]:
            for line in counted[r]:
                line["credit"] = line["charge"]
        else:
            for line, share in _ref_floor_share(pools[r], counted[r], base[r]):
                line["credit"] = share
        if base[r] < minimums[r]:
            for line, share in _ref_floor_share(minimums[r] - base[r], counted[r], base[r]):
                line["true_up"] = share
    for line in accepted:
        line["net"] = line["charge"] - line["credit"] + line["true_up"]

    docs = {}
    docs["normalized.jsonl"] = [
        {"record_id": a["record_id"], "region": a["region"],
         "timestamp": a["ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), "account_id": a["account_id"],
         "segment": a["segment"], "plan": a["plan"], "product": a["product"], "units": a["units"],
         "tier": a["tier"], "unit_rate": "%s" % a["rate"].quantize(_RD("0.0001")),
         "charge": ref_money(a["charge"]), "credit": ref_money(a["credit"]),
         "true_up": ref_money(a["true_up"]), "net": ref_money(a["net"])}
        for a in accepted]

    def totals(lines):
        return (sum(a["charge"] for a in lines), sum(a["credit"] for a in lines),
                sum(a["true_up"] for a in lines), sum(a["net"] for a in lines))

    def unit_map(lines):
        return {p: sum(a["units"] for a in lines if a["product"] == p) for p in REF_PRODUCTS}

    ch, cr, tu, nt = totals(accepted)
    docs["summary.json"] = {"month": month, "lines": len(accepted),
                            "accounts_billed": len({a["account_id"] for a in accepted}),
                            "units": unit_map(accepted), "charge": ref_money(ch),
                            "credit": ref_money(cr), "true_up": ref_money(tu), "net": ref_money(nt)}
    prods = {}
    for p in REF_PRODUCTS:
        sub = [a for a in accepted if a["product"] == p]
        c1, c2, c4, c3 = totals(sub)
        prods[p] = {"unit": units_of[p], "lines": len(sub), "units": sum(a["units"] for a in sub),
                    "charge": ref_money(c1), "credit": ref_money(c2), "true_up": ref_money(c4),
                    "net": ref_money(c3)}
    docs["product_summary.json"] = {"month": month, "products": prods}
    for r in REF_REGIONS:
        sub = [a for a in accepted if a["region"] == r]
        c1, c2, c4, c3 = totals(sub)
        pool_cents = pools[r]
        docs["region_%s.json" % r] = {
            "region": r, "month": month, "lines": len(sub),
            "accounts": len({a["account_id"] for a in sub}), "units": unit_map(sub),
            "charge": ref_money(c1), "credit_pool": ref_money(pool_cents),
            "credit_base": ref_money(base[r]), "credit_applied": ref_money(c2),
            "credit_unallocated": ref_money(pool_cents - c2), "minimum": ref_money(minimums[r]),
            "true_up": ref_money(c4), "net": ref_money(c3)}
    for s in REF_SEGMENTS:
        sub = [a for a in accepted if a["segment"] == s]
        c1, c2, c4, c3 = totals(sub)
        by = {}
        for p in REF_PRODUCTS:
            ps = [a for a in sub if a["product"] == p]
            by[p] = {"lines": len(ps), "units": sum(a["units"] for a in ps),
                     "charge": ref_money(sum(a["charge"] for a in ps))}
        docs["segment_%s.json" % s] = {
            "segment": s, "month": month, "lines": len(sub),
            "accounts": len({a["account_id"] for a in sub}), "by_product": by,
            "charge": ref_money(c1), "credit": ref_money(c2), "true_up": ref_money(c4),
            "net": ref_money(c3)}
    quarantined.sort(key=lambda q: (q["collector"], q["record_id"]))
    docs["data_quality.json"] = {
        "month": month, "collectors": collectors, "quarantine_reasons": reasons,
        "quarantined_records": quarantined,
        "plan_changes": {"lines": pc_total, "applied": pc_applied, "unmatched": pc_total - pc_applied}}
    return docs
