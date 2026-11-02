#!/usr/bin/env python3
"""Billing run for one concierge desk cycle extract."""
import csv
import io
import json
import os
import sys

REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
OFFSET_RANGE = range(-19, 20)


def days_from_civil(y, m, d):
    """Days since 1970-01-01 (proleptic Gregorian)."""
    yy = y - (1 if m <= 2 else 0)
    era = (yy if yy >= 0 else yy - 399) // 400
    yoe = yy - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (1 if m <= 2 else 0), m, d)


def parse_day(s):
    return days_from_civil(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def format_day(z):
    y, m, d = civil_from_days(z)
    return "%04d-%02d-%02d" % (y, m, d)


def parse_instant(s):
    """ISO instant YYYY-MM-DDTHH:MM:SS as seconds since epoch."""
    day = days_from_civil(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    return day * 86400 + int(s[11:13]) * 3600 + int(s[14:16]) * 60 + int(s[17:19])


def parse_legacy_instant(s):
    """Legacy instant DD.MM.YYYY HH:MM:SS as seconds since epoch."""
    day = days_from_civil(int(s[6:10]), int(s[3:5]), int(s[0:2]))
    return day * 86400 + int(s[11:13]) * 3600 + int(s[14:16]) * 60 + int(s[17:19])


def format_instant(sec):
    day, rem = divmod(sec, 86400)
    return "%sT%02d:%02d:%02d" % (format_day(day), rem // 3600, (rem % 3600) // 60, rem % 60)


def read_text(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


def read_csv_rows(path):
    reader = csv.DictReader(io.StringIO(read_text(path), newline=""))
    rows = []
    for raw in reader:
        row = {}
        for key, value in raw.items():
            if key is None:
                continue
            row[key.strip()] = value.strip() if isinstance(value, str) else ""
        rows.append(row)
    return rows


def round_half_even(micro, unit=10000):
    q, r = divmod(micro, unit)
    twice = r * 2
    if twice > unit or (twice == unit and q % 2 != 0):
        q += 1
    return q


class Extract(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.input_files = sorted(
            name for name in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, name))
        )
        self.cycle = json.loads(read_text(os.path.join(data_dir, "cycle.json")))
        self.first_day = parse_day(self.cycle["first_day"].strip())
        self.last_day = parse_day(self.cycle["last_day"].strip())
        self.minimum_invoice = int(self.cycle["minimum_invoice_micro"])
        self.cycle_name = self.cycle["cycle"].strip()

        self.clients = {}
        for row in read_csv_rows(os.path.join(data_dir, "clients.csv")):
            self.clients[row["client"]] = row

        self.plans = {}
        for row in read_csv_rows(os.path.join(data_dir, "plans.csv")):
            tiers = row["credit_tiers"]
            self.plans[row["plan"]] = (
                int(row["included_minutes"]),
                frozenset(tiers.split(" ")) if tiers else frozenset(),
            )

        self.catalog = {}
        for row in read_csv_rows(os.path.join(data_dir, "service_catalog.csv")):
            self.catalog[row["service"].upper()] = (row["product_line"], int(row["increment_minutes"]))

        self.aliases = {}
        for row in read_csv_rows(os.path.join(data_dir, "code_aliases.csv")):
            self.aliases[row["alias"].upper()] = row["service"].upper()

        self.holidays = set()
        for row in read_csv_rows(os.path.join(data_dir, "holidays.csv")):
            self.holidays.add((row["region"], parse_day(row["day"])))

        self.zones = {}
        for row in read_csv_rows(os.path.join(data_dir, "zone_rules.csv")):
            self.zones.setdefault(row["zone"], []).append(
                (parse_instant(row["from_utc"]), int(row["utc_offset_minutes"]))
            )
        for rules in self.zones.values():
            rules.sort()

        self.rates = {}
        for row in read_csv_rows(os.path.join(data_dir, self.cycle["rate_card"].strip())):
            end = parse_day(row["effective_to"]) if row["effective_to"] else None
            self.rates.setdefault((row["service"].upper(), row["tier"]), []).append(
                (parse_day(row["effective_from"]), end, int(row["rate_micro_per_minute"]))
            )

        self.register = {}
        for row in read_csv_rows(os.path.join(data_dir, "exchange_register.csv")):
            minute = parse_day(row["day"]) * 1440 + int(row["slot"][0:2]) * 60 + int(row["slot"][3:5])
            key = (row["line"], minute)
            self.register[key] = self.register.get(key, 0) + int(row["calls"])

        self.amendments = []
        for line in read_text(os.path.join(data_dir, "amendments.jsonl")).split("\n"):
            if line.strip():
                self.amendments.append(json.loads(line))

        self.closings, self.duplicates = self._read_closings()

    def _read_closings(self):
        main = []
        for row in read_csv_rows(os.path.join(self.data_dir, "closings.csv")):
            main.append({
                "ref": row["ref"],
                "handset": row["handset"],
                "seq": int(row["seq"]),
                "client": row["client"],
                "service_code": row["service"],
                "stamp": parse_instant(row["stamped_at"]),
                "worked_minutes": int(row["worked_minutes"]),
            })
        identities = set((c["handset"], c["seq"]) for c in main)

        unit = None
        legacy = []
        duplicates = []
        for line in read_text(os.path.join(self.data_dir, "legacy_closings.txt")).split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                body = stripped.lstrip("#").strip()
                if body.lower().startswith("duration unit:"):
                    unit = body.split(":", 1)[1].strip().lower()
                continue
            fields = [f.strip() for f in stripped.split("|")]
            ref, handset, seq, client, service, stamped, duration = fields[:7]
            seq = int(seq)
            if (handset, seq) in identities:
                duplicates.append(ref)
                continue
            value = int(duration)
            legacy.append({
                "ref": ref,
                "handset": handset,
                "seq": seq,
                "client": client,
                "service_code": service,
                "stamp": parse_legacy_instant(stamped),
                "worked_minutes": value if unit == "minutes" else -(-value // 60),
            })
        return main + legacy, duplicates

    def zone_offset(self, zone, instant):
        offset = None
        for start, minutes in self.zones[zone]:
            if start <= instant:
                offset = minutes
            else:
                break
        return offset

    def rate_for(self, service, tier, local_day):
        for start, end, rate in self.rates.get((service, tier), ()):
            if start <= local_day and (end is None or local_day < end):
                return rate
        return None


def infer_offsets(extract):
    """Clock offset of every handset, read off the traffic register.

    Each received closing makes one call on its client's line at its
    completion instant, and a row never counts more calls than the closings
    of that line in that slot, but the exchange may lose a call. The offsets
    kept are those leaving the fewest registered calls unexplained.
    """
    lines = {}
    handsets = set()
    for c in extract.closings:
        line = extract.clients[c["client"]]["line"]
        c["line"] = line
        handsets.add(c["handset"])
        lines.setdefault(line, {}).setdefault(c["handset"], []).append(c["stamp"] // 60)
    needs = {}
    for (line, minute), calls in extract.register.items():
        needs.setdefault(line, {})[minute] = calls
    handsets = sorted(handsets)

    def unexplained(line, assignment, only=None):
        need = needs.get(line)
        if not need:
            return 0
        counts = {}
        for handset, stamps in lines[line].items():
            if only is not None and handset != only:
                continue
            off = assignment[handset]
            for stamp in stamps:
                key = stamp + off
                if key in need:
                    counts[key] = counts.get(key, 0) + 1
        total = 0
        for key, calls in need.items():
            got = counts.get(key, 0)
            if got < calls:
                total += calls - got
        return total

    touched = {}
    exclusive = {}
    for line, by_handset in lines.items():
        for handset in by_handset:
            touched.setdefault(handset, []).append(line)
        if len(by_handset) == 1:
            exclusive.setdefault(next(iter(by_handset)), []).append(line)

    def alone_best(subset):
        """Best offset of each handset taken on its own."""
        assignment = dict((handset, 0) for handset in handsets)
        for handset in handsets:
            best = None
            for off in OFFSET_RANGE:
                assignment[handset] = off
                total = sum(unexplained(line, assignment, handset) for line in subset.get(handset, ()))
                key = (total, abs(off), off)
                if best is None or key < best:
                    best = key
            assignment[handset] = best[2]
        return assignment

    def descend(assignment):
        for _ in range(len(handsets) + 2):
            changed = False
            for handset in handsets:
                best = None
                for off in OFFSET_RANGE:
                    assignment[handset] = off
                    total = sum(unexplained(line, assignment) for line in touched[handset])
                    key = (total, abs(off), off)
                    if best is None or key < best:
                        best = key
                if best[2] != assignment[handset]:
                    changed = True
                assignment[handset] = best[2]
            if not changed:
                break
        total = sum(unexplained(line, assignment) for line in lines)
        return total, [assignment[handset] for handset in handsets], assignment

    starts = [alone_best(touched), alone_best(exclusive), dict((handset, 0) for handset in handsets)]
    return min((descend(start) for start in starts), key=lambda item: (item[0], item[1]))[2]


def apply_amendments(extract, by_identity):
    """Void identities, worked-minute overrides and amendments without effect."""
    by_id = {}
    for am in extract.amendments:
        by_id[am["amendment"]] = am

    cancelled = set()
    no_effect = set()
    for am in extract.amendments:
        if am["action"] != "revert":
            continue
        target = by_id.get(am["reverts"]) if am["reverts"] is not None else None
        if target is None or target["action"] not in ("void", "minutes"):
            no_effect.add(am["amendment"])
        elif parse_instant(am["issued_at"]) <= parse_instant(target["issued_at"]):
            no_effect.add(am["amendment"])
        else:
            cancelled.add(target["amendment"])

    effective = []
    for am in extract.amendments:
        if am["action"] not in ("void", "minutes"):
            continue
        closing = by_identity.get((am["handset"], int(am["seq"])))
        if closing is None or parse_instant(am["issued_at"]) < closing["completed_at"]:
            no_effect.add(am["amendment"])
        elif am["amendment"] not in cancelled:
            effective.append((parse_instant(am["issued_at"]), am["amendment"], am))
    effective.sort(key=lambda item: (item[0], item[1]))

    void_ids = set()
    worked = {}
    for _, _, am in effective:
        ident = (am["handset"], int(am["seq"]))
        if am["action"] == "void":
            void_ids.add(ident)
        else:
            worked[ident] = int(am["minutes"])
    return void_ids, worked, no_effect | cancelled


def build(extract):
    offsets = infer_offsets(extract)
    for c in extract.closings:
        c["completed_at"] = c["stamp"] + offsets[c["handset"]] * 60

    by_identity = {}
    for c in extract.closings:
        by_identity[(c["handset"], c["seq"])] = c

    void_ids, worked_override, amendments_without_effect = apply_amendments(extract, by_identity)

    rejected = {}
    outside_cycle = []
    void_refs = []
    unrated = []
    billed = []

    for c in extract.closings:
        code = c["service_code"].upper()
        if code in extract.catalog:
            service = code
        elif code in extract.aliases:
            service = extract.aliases[code]
        else:
            rejected[c["ref"]] = "unknown_service"
            continue
        c["service"] = service
        client = extract.clients[c["client"]]
        local = c["completed_at"] + extract.zone_offset(client["zone"], c["completed_at"]) * 60
        local_day, rem = divmod(local, 86400)
        c["local_day"] = local_day
        if local_day < extract.first_day or local_day > extract.last_day:
            outside_cycle.append(c["ref"])
            continue
        if (c["handset"], c["seq"]) in void_ids:
            void_refs.append(c["ref"])
            continue
        if (local_day + 3) % 7 >= 5 or (client["region"], local_day) in extract.holidays:
            tier = "weekend_holiday"
        elif 8 * 3600 <= rem < 18 * 3600:
            tier = "standard"
        else:
            tier = "after_hours"
        c["tier"] = tier
        rate = extract.rate_for(service, tier, local_day)
        if rate is None:
            unrated.append(c["ref"])
            continue
        c["rate"] = rate
        product_line, increment = extract.catalog[service]
        c["product_line"] = product_line
        worked = worked_override.get((c["handset"], c["seq"]), c["worked_minutes"])
        c["worked"] = worked
        c["billable"] = -(-worked // increment) * increment
        c["segment"] = client["segment"]
        c["region"] = client["region"]
        c["credited"] = 0
        billed.append(c)

    by_client = {}
    for c in billed:
        by_client.setdefault(c["client"], []).append(c)
    for client_id, items in by_client.items():
        included, credit_tiers = extract.plans[extract.clients[client_id]["plan"]]
        eligible = [c for c in items if c["tier"] in credit_tiers]
        eligible.sort(key=lambda c: (-c["completed_at"], c["ref"]))
        remaining = included
        for c in eligible:
            if remaining <= 0:
                break
            credit = c["billable"] if c["billable"] < remaining else remaining
            c["credited"] = credit
            remaining -= credit
    for c in billed:
        c["charged"] = c["billable"] - c["credited"]
        c["gross_micro"] = c["billable"] * c["rate"]
        c["net_micro"] = c["charged"] * c["rate"]

    billed.sort(key=lambda c: (c["completed_at"], c["ref"]))

    return {
        "billed": billed,
        "rejected": rejected,
        "outside_cycle": sorted(outside_cycle),
        "void": sorted(void_refs),
        "unrated": sorted(unrated),
        "amendments_without_effect": sorted(amendments_without_effect),
    }


def invoice_report(items, name_key, name, in_scope):
    gross = sum(c["gross_micro"] for c in items)
    net = sum(c["net_micro"] for c in items)
    by_tier = {}
    for c in items:
        by_tier[c["tier"]] = by_tier.get(c["tier"], 0) + c["net_micro"]
    return {
        "by_tier": by_tier,
        "clients": sorted(set(c["client"] for c in items)),
        "closings": len(items),
        "credit_micro": gross - net,
        "gross_micro": gross,
        "in_scope": in_scope(gross, net),
        "net_cents": round_half_even(net),
        "net_micro": net,
        name_key: name,
    }


def dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def main(argv):
    data_dir, out_dir = argv[1], argv[2]
    extract = Extract(data_dir)
    result = build(extract)
    billed = result["billed"]
    minimum = extract.minimum_invoice

    files = {}
    files["normalized.jsonl"] = "".join(dumps({
        "billable_minutes": c["billable"],
        "charged_minutes": c["charged"],
        "client": c["client"],
        "completed_at": format_instant(c["completed_at"]),
        "credited_minutes": c["credited"],
        "gross_micro": c["gross_micro"],
        "handset": c["handset"],
        "line": c["line"],
        "local_day": format_day(c["local_day"]),
        "net_micro": c["net_micro"],
        "product_line": c["product_line"],
        "rate_micro_per_minute": c["rate"],
        "ref": c["ref"],
        "region": c["region"],
        "segment": c["segment"],
        "seq": c["seq"],
        "service": c["service"],
        "tier": c["tier"],
        "worked_minutes": c["worked"],
    }) + "\n" for c in billed)

    product_objs = []
    product_net = 0
    for pl in sorted(set(line for line, _ in extract.catalog.values())):
        items = [c for c in billed if c["product_line"] == pl]
        net = sum(c["net_micro"] for c in items)
        product_net += net
        product_objs.append({
            "billable_minutes": sum(c["billable"] for c in items),
            "closings": len(items),
            "gross_micro": sum(c["gross_micro"] for c in items),
            "net_micro": net,
            "product_line": pl,
        })
    files["product_summary.json"] = dumps({"product_lines": product_objs}) + "\n"

    region_net = 0
    for region in REGIONS:
        items = [c for c in billed if c["region"] == region]
        rep = invoice_report(items, "region", region, lambda gross, net: gross >= minimum)
        region_net += rep["net_micro"]
        files["region_%s.json" % region] = dumps(rep) + "\n"

    segment_net = 0
    for segment in SEGMENTS:
        items = [c for c in billed if c["segment"] == segment]
        rep = invoice_report(items, "segment", segment, lambda gross, net: net >= minimum)
        segment_net += rep["net_micro"]
        files["segment_%s.json" % segment] = dumps(rep) + "\n"

    gross_total = sum(c["gross_micro"] for c in billed)
    net_total = sum(c["net_micro"] for c in billed)
    by_tier = {}
    for c in billed:
        by_tier[c["tier"]] = by_tier.get(c["tier"], 0) + c["net_micro"]
    files["summary.json"] = dumps({
        "by_tier": by_tier,
        "closings_billed": len(billed),
        "credit_micro": gross_total - net_total,
        "cycle": extract.cycle_name,
        "gross_micro": gross_total,
        "net_cents": round_half_even(net_total),
        "net_micro": net_total,
        "reconciliation": {
            "normalized_net_micro": net_total,
            "product_net_micro": product_net,
            "region_net_micro": region_net,
            "residual_micro": product_net + region_net + segment_net - 3 * net_total,
            "segment_net_micro": segment_net,
        },
    }) + "\n"

    files["data_quality.json"] = dumps({
        "amendments_without_effect": result["amendments_without_effect"],
        "closings_received": len(extract.closings),
        "duplicates": sorted(extract.duplicates),
        "input_files": extract.input_files,
        "outside_cycle": result["outside_cycle"],
        "rejected": result["rejected"],
        "unrated": result["unrated"],
        "void": result["void"],
    }) + "\n"

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    lines = []
    for name in sorted(files):
        payload = files[name].encode("utf-8")
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(payload)
        lines.append("wrote %s %d\n" % (name, len(payload)))
    sys.stdout.write("".join(lines))


if __name__ == "__main__":
    main(sys.argv)
