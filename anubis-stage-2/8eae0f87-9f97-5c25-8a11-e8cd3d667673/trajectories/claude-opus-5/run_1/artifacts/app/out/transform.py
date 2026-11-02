#!/usr/bin/env python3
"""Meter one billing period of the query fleet and write its thirteen reports."""

import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta

GIB = 1073741824
EPOCH = datetime(1970, 1, 1)
REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
MAX_OFFSET = 19
MAX_TRANSFER_MS = 4999

LOCAL_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{3})$")
REF_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{3})Z$")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
INT_RE = re.compile(r"^\d+$")


def stamp_to_ms(text, regex):
    match = regex.match(text)
    if not match:
        return None
    year, month, day, hour, minute, second, millis = (int(g) for g in match.groups())
    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    return int((dt - EPOCH).total_seconds()) * 1000 + millis


def ms_to_ref(ms):
    dt = EPOCH + timedelta(milliseconds=ms)
    return "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ" % (
        dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, ms % 1000,
    )


def ms_to_date(ms):
    dt = EPOCH + timedelta(milliseconds=ms)
    return "%04d-%02d-%02d" % (dt.year, dt.month, dt.day)


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            row = {}
            for key, value in raw.items():
                if key is None:
                    continue
                row[key.strip()] = value.strip() if isinstance(value, str) else value
            rows.append(row)
        return rows


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --- clocks -----------------------------------------------------------------

def read_transfers(path):
    transfers = []
    carried = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = [p.strip() for p in text.split("|")]
            if len(parts) != 5:
                continue
            xfer_id, from_node, sent_local, to_node, recv_local = parts
            sent = stamp_to_ms(sent_local, LOCAL_RE)
            recv = stamp_to_ms(recv_local, LOCAL_RE)
            if sent is None or recv is None:
                continue
            carried += 1
            transfers.append((xfer_id, from_node, sent, to_node, recv))
    return transfers, carried


def solve_differences(variables, constraints, root, anchors):
    """Solve low <= x_b - x_a <= high over integers bounded to +-MAX_OFFSET.

    `root` is the variable held at zero; `anchors` maps further variables to a
    fixed value. Returns the pointwise maximal solution together with a flag
    telling whether it is the only one, or None when the system is infeasible.
    """
    index = {var: i for i, var in enumerate(variables)}
    size = len(variables)
    inf = float("inf")
    dist = [[inf] * size for _ in range(size)]
    for i in range(size):
        dist[i][i] = 0

    def edge(a, b, weight):
        i, j = index[a], index[b]
        if weight < dist[i][j]:
            dist[i][j] = weight

    for var in variables:
        if var == root:
            continue
        if var in anchors:
            edge(root, var, anchors[var])
            edge(var, root, -anchors[var])
        else:
            edge(root, var, MAX_OFFSET)
            edge(var, root, MAX_OFFSET)
    for var_a, var_b, low, high in constraints:
        edge(var_a, var_b, high)
        edge(var_b, var_a, -low)

    for k in range(size):
        row_k = dist[k]
        for i in range(size):
            via = dist[i][k]
            if via == inf:
                continue
            row_i = dist[i]
            for j in range(size):
                if row_k[j] == inf:
                    continue
                alt = via + row_k[j]
                if alt < row_i[j]:
                    row_i[j] = alt
    for i in range(size):
        if dist[i][i] < 0:
            return None
    root_index = index[root]
    base = dist[root_index]
    if any(value == inf for value in base):
        return None
    unique = all(dist[i][root_index] == -base[i] for i in range(size))
    return {var: base[index[var]] for var in variables}, unique


def quiet_instants(query_spans):
    """Candidate reset instants: moments at which no query runs anywhere."""
    slack = (MAX_OFFSET + 1) * 1000
    spans = sorted((start - slack, start + duration + slack) for start, duration in query_spans)
    gaps = []
    if not spans:
        return gaps
    current_end = spans[0][1]
    for start, end in spans[1:]:
        if start > current_end:
            gaps.append((current_end + start) // 2)
            current_end = end
        elif end > current_end:
            current_end = end
    return gaps


def solve_clocks(transfers, nodes, reference_node, query_spans):
    """Return a function giving the clock offset of a node at a local stamp."""
    node_ids = sorted(nodes)
    gaps = quiet_instants(query_spans)
    usable = [t for t in transfers if t[1] in nodes and t[3] in nodes]

    def attempt(resets):
        def segment_of(node, ms):
            return sum(1 for split in resets.get(node, ()) if ms >= split)

        variables = [
            (node, seg)
            for node in node_ids
            for seg in range(len(resets.get(node, ())) + 1)
        ]
        root = (reference_node, 0)
        anchors = {
            var: 0 for var in variables if var[0] == reference_node and var != root
        }
        constraints = []
        for _xfer, from_node, sent, to_node, recv in usable:
            delta = recv - sent
            low = -((MAX_TRANSFER_MS - delta) // 1000)
            high = delta // 1000
            constraints.append(
                (
                    (from_node, segment_of(from_node, sent)),
                    (to_node, segment_of(to_node, recv)),
                    low,
                    high,
                )
            )
        solved = solve_differences(variables, constraints, root, anchors)
        if solved is None:
            return None
        solution, unique = solved
        return solution, segment_of, unique

    found = attempt({})
    if found is None:
        # A node was reset during the period; the journal is its only record.
        fallback = None
        for node in node_ids:
            if node == reference_node:
                continue
            for gap in gaps:
                candidate = attempt({node: (gap,)})
                if candidate is None:
                    continue
                if candidate[2]:
                    found = candidate
                    break
                if fallback is None:
                    fallback = candidate
            if found is not None:
                break
        if found is None:
            found = fallback
    if found is None:
        raise ValueError("no consistent set of clock offsets")
    solution, segment_of = found[0], found[1]

    def offset(node, ms):
        return solution[(node, segment_of(node, ms))]

    return offset


# --- zones and rate cards ---------------------------------------------------

class Zone:
    def __init__(self, name, spec):
        self.name = name
        self.standard = int(spec["standard_offset_minutes"])
        self.daylight = int(spec["daylight_offset_minutes"])
        self.periods = sorted(
            (
                stamp_to_ms(period["start"].strip(), REF_RE),
                stamp_to_ms(period["end"].strip(), REF_RE),
            )
            for period in spec.get("daylight_periods", [])
        )
        self.holidays = set(holiday.strip() for holiday in spec.get("holidays", []))

    def offset_minutes(self, ms):
        for start, end in self.periods:
            if start <= ms < end:
                return self.daylight
        return self.standard

    def local_ms(self, ms):
        return ms + self.offset_minutes(ms) * 60000

    def utc_of_local(self, local_ms):
        candidates = sorted({self.standard, self.daylight}, reverse=True)
        for offset in candidates:
            instant = local_ms - offset * 60000
            if self.offset_minutes(instant) == offset:
                return instant
        return local_ms - candidates[0] * 60000


class Plan:
    def __init__(self, code, versions):
        self.code = code
        self.versions = sorted(
            (
                {
                    "version": spec["version"].strip(),
                    "effective_from": stamp_to_ms(spec["effective_from"].strip(), REF_RE),
                    "daily_free_bytes": int(spec["daily_free_bytes"]),
                    "min_billable_bytes": int(spec["min_billable_bytes"]),
                    "block_bytes": int(spec["block_bytes"]),
                    "peak_micros_per_gib": int(spec["peak_micros_per_gib"]),
                    "offpeak_micros_per_gib": int(spec["offpeak_micros_per_gib"]),
                }
                for spec in versions
            ),
            key=lambda version: (version["effective_from"], version["version"]),
        )

    def in_force(self, ms):
        chosen = None
        for version in self.versions:
            if version["effective_from"] <= ms:
                chosen = version
            else:
                break
        if chosen is None:
            raise ValueError("no rate card version in force for plan %s" % self.code)
        return chosen


# --- metering ---------------------------------------------------------------

def round_half_up(numerator, denominator):
    return (2 * numerator + denominator) // (2 * denominator)


def load_registers(data_dir):
    nodes = {}
    reference_node = None
    for row in read_csv(os.path.join(data_dir, "nodes.csv")):
        nodes[row["node_id"]] = {
            "region": row["region"].lower(),
            "role": row["role"].lower(),
        }
        if nodes[row["node_id"]]["role"] == "reference":
            reference_node = row["node_id"]
    if reference_node is None:
        raise ValueError("no reference node in the node register")

    tenants = {}
    for row in read_csv(os.path.join(data_dir, "tenants.csv")):
        tenants[row["tenant_id"]] = {
            "segment": row["segment"].lower(),
            "plan": row["plan"],
            "zone": row["zone"],
        }

    products = {
        row["product_id"]: row["product_line"].lower()
        for row in read_csv(os.path.join(data_dir, "products.csv"))
    }

    merges = {
        row["absorbed_tenant"]: (
            row["surviving_tenant"],
            stamp_to_ms(row["effective_at"], REF_RE),
        )
        for row in read_csv(os.path.join(data_dir, "tenant_merges.csv"))
    }

    plans_doc = load_json(os.path.join(data_dir, "plans.json"))
    plans = {code: Plan(code, versions) for code, versions in plans_doc["plans"].items()}
    zones_doc = load_json(os.path.join(data_dir, "zones.json"))
    zones = {name: Zone(name, spec) for name, spec in zones_doc["zones"].items()}
    return nodes, reference_node, tenants, products, merges, plans, zones


QUERY_FIELDS = (
    "query_id", "node_id", "tenant_id", "product_id", "started_local",
    "duration_ms", "scanned_bytes", "status",
)


def accept_queries(rows, nodes, tenants, products):
    accepted = []
    rejected = 0
    for row in rows:
        values = [row.get(field) for field in QUERY_FIELDS]
        if any(value is None or value == "" for value in values):
            rejected += 1
            continue
        started = stamp_to_ms(row["started_local"], LOCAL_RE)
        status = row["status"].lower()
        if (
            started is None
            or not INT_RE.match(row["duration_ms"])
            or not INT_RE.match(row["scanned_bytes"])
            or status not in ("ok", "cancelled", "failed")
            or row["node_id"] not in nodes
            or row["tenant_id"] not in tenants
            or row["product_id"] not in products
        ):
            rejected += 1
            continue
        accepted.append(
            {
                "query_id": row["query_id"],
                "node_id": row["node_id"],
                "tenant_id": row["tenant_id"],
                "product_id": row["product_id"],
                "started_local": started,
                "duration_ms": int(row["duration_ms"]),
                "logged_bytes": int(row["scanned_bytes"]),
                "scanned_bytes": int(row["scanned_bytes"]),
                "status": status,
                "withdrawn": False,
            }
        )
    return accepted, rejected


def apply_corrections(data_dir, accepted):
    by_id = {}
    for query in accepted:
        by_id.setdefault(query["query_id"], query)
    corrections = []
    with open(os.path.join(data_dir, "corrections.jsonl"), "r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if text:
                corrections.append(json.loads(text))
    corrections.sort(
        key=lambda c: (str(c["recorded_at"]).strip(), str(c["correction_id"]).strip())
    )
    for correction in corrections:
        query = by_id.get(str(correction["query_id"]).strip())
        if query is None:
            continue
        action = str(correction["action"]).strip().lower()
        if action == "restate":
            query["scanned_bytes"] = int(correction["scanned_bytes"])
        elif action == "void":
            query["withdrawn"] = True
        elif action == "reinstate":
            query["withdrawn"] = False


def billing_identity(tenant_id, billed_at, merges):
    identity = tenant_id
    seen = {identity}
    while identity in merges:
        survivor, effective_at = merges[identity]
        if billed_at < effective_at or survivor in seen:
            break
        identity = survivor
        seen.add(identity)
    return identity


def billing_order(entry):
    """Rank within one billing identity and billing day (record dictionary)."""
    return (
        entry["_billed_at_ms"],
        entry["metered_bytes"],
        entry["_started_at_ms"],
        entry["query_id"],
    )


def meter(data_dir):
    nodes, reference_node, tenants, products, merges, plans, zones = load_registers(data_dir)
    query_rows = read_csv(os.path.join(data_dir, "queries.csv"))
    transfers, transfer_lines = read_transfers(os.path.join(data_dir, "transfers.log"))

    accepted, rejected = accept_queries(query_rows, nodes, tenants, products)
    offset_of = solve_clocks(
        transfers,
        nodes,
        reference_node,
        [(query["started_local"], query["duration_ms"]) for query in accepted],
    )
    apply_corrections(data_dir, accepted)

    ledger = []
    for query in accepted:
        if query["status"] == "failed" or query["withdrawn"]:
            continue
        started_ref = query["started_local"] - 1000 * offset_of(
            query["node_id"], query["started_local"]
        )
        billed_at = started_ref + query["duration_ms"]
        identity = billing_identity(query["tenant_id"], billed_at, merges)
        tenant = tenants[identity]
        zone = zones[tenant["zone"]]
        plan = plans[tenant["plan"]]

        local_ms = zone.local_ms(billed_at)
        billing_day = ms_to_date(local_ms)
        local_day_ms = (local_ms // 86400000) * 86400000
        time_of_day = local_ms - local_day_ms
        weekday = ((local_ms // 86400000) + 3) % 7
        peak = (
            weekday < 5
            and billing_day not in zone.holidays
            and 28800000 <= time_of_day < 72000000
        )
        version = plan.in_force(billed_at)
        metered = max(query["scanned_bytes"], version["min_billable_bytes"])
        block = version["block_bytes"]
        if block > 0 and metered % block:
            metered += block - metered % block

        ledger.append(
            {
                "billed_at": ms_to_ref(billed_at),
                "billing_day": billing_day,
                "chargeable_bytes": 0,
                "charge_micros": 0,
                "corrected": query["scanned_bytes"] != query["logged_bytes"],
                "free_bytes": 0,
                "metered_bytes": metered,
                "node_id": query["node_id"],
                "plan_version": version["version"],
                "product_id": query["product_id"],
                "product_line": products[query["product_id"]],
                "query_id": query["query_id"],
                "region": nodes[query["node_id"]]["region"],
                "scanned_bytes": query["scanned_bytes"],
                "segment": tenant["segment"],
                "source_tenant_id": query["tenant_id"],
                "tenant_id": identity,
                "window": "peak" if peak else "offpeak",
                "_billed_at_ms": billed_at,
                "_started_at_ms": started_ref,
                "_zone": tenant["zone"],
                "_plan": tenant["plan"],
                "_rate": version["peak_micros_per_gib"] if peak
                else version["offpeak_micros_per_gib"],
            }
        )

    groups = {}
    for entry in ledger:
        groups.setdefault((entry["tenant_id"], entry["billing_day"]), []).append(entry)
    for (_identity, billing_day), entries in groups.items():
        entries.sort(key=billing_order)
        zone = zones[entries[0]["_zone"]]
        year, month, day = (int(part) for part in DATE_RE.match(billing_day).groups())
        local_midnight = int((datetime(year, month, day) - EPOCH).total_seconds()) * 1000
        day_begins = zone.utc_of_local(local_midnight)
        remaining = plans[entries[0]["_plan"]].in_force(day_begins)["daily_free_bytes"]
        for entry in entries:
            free = min(entry["metered_bytes"], max(remaining, 0))
            remaining -= free
            entry["free_bytes"] = free
            entry["chargeable_bytes"] = entry["metered_bytes"] - free
            entry["charge_micros"] = round_half_up(
                entry["chargeable_bytes"] * entry["_rate"], GIB
            )

    ledger.sort(key=lambda entry: (entry["billed_at"], entry["query_id"]))

    stats = {
        "input_files": sorted(
            name for name in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, name))
        ),
        "query_rows": len(query_rows),
        "rejected_rows": rejected,
        "failed_queries": sum(1 for q in accepted if q["status"] == "failed"),
        "voided_queries": sum(
            1 for q in accepted if q["status"] != "failed" and q["withdrawn"]
        ),
        "billed_queries": len(ledger),
        "corrected_queries": sum(1 for entry in ledger if entry["corrected"]),
        "merged_queries": sum(
            1 for entry in ledger if entry["tenant_id"] != entry["source_tenant_id"]
        ),
        "transfer_lines": transfer_lines,
    }
    return ledger, stats, nodes, products


# --- reports ----------------------------------------------------------------

LEDGER_KEYS = (
    "billed_at", "billing_day", "chargeable_bytes", "charge_micros", "corrected",
    "free_bytes", "metered_bytes", "node_id", "plan_version", "product_id",
    "product_line", "query_id", "region", "scanned_bytes", "segment",
    "source_tenant_id", "tenant_id", "window",
)


def build_reports(ledger, stats, nodes, products):
    reports = {}
    reports["normalized.jsonl"] = "".join(
        json.dumps(
            {key: entry[key] for key in LEDGER_KEYS},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
        for entry in ledger
    )

    def sum_by(field):
        totals = {}
        for entry in ledger:
            totals[entry[field]] = totals.get(entry[field], 0) + entry["charge_micros"]
        return totals

    def totals(rows):
        return {
            "billed_queries": len(rows),
            "metered_bytes": sum(entry["metered_bytes"] for entry in rows),
            "free_bytes": sum(entry["free_bytes"] for entry in rows),
            "chargeable_bytes": sum(entry["chargeable_bytes"] for entry in rows),
            "charge_micros": sum(entry["charge_micros"] for entry in rows),
        }

    ledger_charge = sum(entry["charge_micros"] for entry in ledger)

    region_reports = {}
    for region in REGIONS:
        rows = [entry for entry in ledger if entry["region"] == region]
        by_window = {"offpeak": 0, "peak": 0}
        for entry in rows:
            by_window[entry["window"]] += entry["charge_micros"]
        report = {
            "region": region,
            "in_scope": any(node["region"] == region for node in nodes.values()),
            "nodes": sorted(
                node_id for node_id, node in nodes.items() if node["region"] == region
            ),
            "tenants": sorted({entry["tenant_id"] for entry in rows}),
        }
        report.update(totals(rows))
        report["by_window"] = by_window
        region_reports[region] = report

    segment_reports = {}
    for segment in SEGMENTS:
        rows = [entry for entry in ledger if entry["segment"] == segment]
        by_region = {}
        for entry in rows:
            by_region[entry["region"]] = (
                by_region.get(entry["region"], 0) + entry["charge_micros"]
            )
        report = {
            "segment": segment,
            "in_scope": bool(rows),
            "tenants": sorted({entry["tenant_id"] for entry in rows}),
        }
        report.update(totals(rows))
        report["by_region"] = by_region
        segment_reports[segment] = report

    product_entries = []
    for product_id in sorted(products):
        rows = [entry for entry in ledger if entry["product_id"] == product_id]
        product_entries.append(
            {
                "product_id": product_id,
                "product_line": products[product_id],
                "billed_queries": len(rows),
                "metered_bytes": sum(entry["metered_bytes"] for entry in rows),
                "chargeable_bytes": sum(entry["chargeable_bytes"] for entry in rows),
                "charge_micros": sum(entry["charge_micros"] for entry in rows),
            }
        )

    region_charge = sum(report["charge_micros"] for report in region_reports.values())
    segment_charge = sum(report["charge_micros"] for report in segment_reports.values())
    product_charge = sum(report["charge_micros"] for report in product_entries)

    summary = {
        "billed_queries": len(ledger),
        "metered_bytes": sum(entry["metered_bytes"] for entry in ledger),
        "free_bytes": sum(entry["free_bytes"] for entry in ledger),
        "chargeable_bytes": sum(entry["chargeable_bytes"] for entry in ledger),
        "charge_micros": ledger_charge,
        "by_region": sum_by("region"),
        "by_segment": sum_by("segment"),
        "by_window": sum_by("window"),
        "by_product_line": sum_by("product_line"),
        "by_plan_version": sum_by("plan_version"),
        "reconciliation": {
            "ledger_charge_micros": ledger_charge,
            "region_charge_micros": region_charge,
            "segment_charge_micros": segment_charge,
            "product_charge_micros": product_charge,
            "residual_micros": 3 * ledger_charge
            - region_charge
            - segment_charge
            - product_charge,
        },
    }

    def dump(obj):
        return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"

    reports["summary.json"] = dump(summary)
    reports["data_quality.json"] = dump(stats)
    reports["product_summary.json"] = dump({"products": product_entries})
    for region in REGIONS:
        reports["region_%s.json" % region] = dump(region_reports[region])
    for segment in SEGMENTS:
        reports["segment_%s.json" % segment] = dump(segment_reports[segment])
    return reports


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    ledger, stats, nodes, products = meter(data_dir)
    reports = build_reports(ledger, stats, nodes, products)
    os.makedirs(out_dir, exist_ok=True)
    lines = []
    for name in sorted(reports):
        payload = reports[name].encode("utf-8")
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(payload)
        lines.append("%s %d" % (name, len(payload)))
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
