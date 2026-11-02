#!/usr/bin/env python3
"""Meter one billing period of the query fleet.

Usage: python3 transform.py DATA_DIR OUT_DIR
"""
import csv
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

GIB = 1073741824
SPAN = 19
TRANSIT_CAP = 4999
REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
REPORTS = ["normalized.jsonl", "summary.json", "data_quality.json", "product_summary.json"] + \
    ["region_%s.json" % r for r in REGIONS] + ["segment_%s.json" % s for s in SEGMENTS]


class Reject(Exception):
    pass


def stamp(text, zulu):
    """Milliseconds since the epoch for a local or reference stamp."""
    t = text.strip()
    if zulu:
        if not t.endswith("Z"):
            raise Reject(text)
        t = t[:-1]
    elif t.endswith("Z"):
        raise Reject(text)
    if len(t) != 23 or t[10] != "T" or t[19] != "." or not t[20:].isdigit():
        raise Reject(text)
    try:
        moment = datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise Reject(text) from exc
    return int(moment.timestamp()) * 1000 + int(t[20:])


def show(ms):
    moment = datetime.fromtimestamp(ms // 1000, tz=timezone.utc)
    return "%sT%s.%03dZ" % (moment.strftime("%Y-%m-%d"), moment.strftime("%H:%M:%S"), ms % 1000)


def count(text):
    t = text.strip()
    if not t or not all("0" <= ch <= "9" for ch in t):
        raise Reject(text)
    return int(t)


def table(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8", newline="") as handle:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


class Fleet:
    """Clock offsets of every node, per run of mutually consistent transfers."""

    def __init__(self, nodes, reference):
        self.nodes = nodes
        self.reference = reference
        self.runs = []

    def _fresh(self):
        box = {n: [-SPAN, SPAN] for n in self.nodes}
        box[self.reference] = [0, 0]
        return box

    @staticmethod
    def _narrow(box, links, start):
        work = list(start)
        while work:
            a, b, lo, hi = work.pop()
            # b - a within [lo, hi]
            ba, bb = box[a], box[b]
            nb = [max(bb[0], ba[0] + lo), min(bb[1], ba[1] + hi)]
            na = [max(ba[0], bb[0] - hi), min(ba[1], bb[1] - lo)]
            if nb[0] > nb[1] or na[0] > na[1]:
                return False
            changed = []
            if nb != bb:
                box[b] = nb
                changed.append(b)
            if na != ba:
                box[a] = na
                changed.append(a)
            for node in changed:
                work.extend(link for link in links if node in (link[0], link[1]))
        return True

    def build(self, transfers):
        transfers.sort(key=lambda t: (t[2], t[0]))
        box, links, first = self._fresh(), [], None
        for xid, src, sent, dst, recv in transfers:
            gap = recv - sent
            link = (src, dst, -((TRANSIT_CAP - gap) // 1000), gap // 1000)
            trial = {k: v[:] for k, v in box.items()}
            if not self._narrow(trial, links + [link], [link]):
                self.runs.append((first, box))
                box, links = self._fresh(), []
                trial = {k: v[:] for k, v in box.items()}
                if not self._narrow(trial, [link], [link]):
                    raise SystemExit("transfer %s fits no offsets" % xid)
                first = None
            box = trial
            links.append(link)
            if first is None:
                first = sent
        self.runs.append((first, box))
        for _, run in self.runs:
            for node, (lo, hi) in run.items():
                if lo != hi:
                    raise SystemExit("offset of %s is not settled (%d..%d)" % (node, lo, hi))

    def offset(self, node, local_ms):
        chosen = self.runs[0][1]
        for first, run in self.runs:
            if first is not None and first <= local_ms:
                chosen = run
        return chosen[node][0]


@dataclass
class Query:
    qid: str
    node: str
    tenant: str
    product: str
    started: int
    duration: int
    scanned: int
    logged: int
    status: str
    withdrawn: bool = False
    billed: dict = field(default_factory=dict)


class Meter:
    def __init__(self, folder):
        self.folder = folder
        nodes = table(folder, "nodes.csv")
        self.region_of = {r["node_id"]: r["region"].lower() for r in nodes}
        refs = [r["node_id"] for r in nodes if r["role"].lower() == "reference"]
        if len(refs) != 1:
            raise SystemExit("node register needs exactly one reference node")
        self.fleet = Fleet(sorted(self.region_of), refs[0])
        self.tenant = {r["tenant_id"]: (r["segment"].lower(), r["plan"], r["zone"]) for r in table(folder, "tenants.csv")}
        self.merge = {r["absorbed_tenant"]: (stamp(r["effective_at"], True), r["surviving_tenant"])
                      for r in table(folder, "tenant_merges.csv")}
        self.line_of = {r["product_id"]: r["product_line"].lower() for r in table(folder, "products.csv")}
        with open(os.path.join(folder, "plans.json"), encoding="utf-8") as handle:
            raw = json.load(handle)["plans"]
        self.cards = {code: sorted((stamp(v["effective_from"], True), v) for v in vs) for code, vs in raw.items()}
        with open(os.path.join(folder, "zones.json"), encoding="utf-8") as handle:
            self.zone = json.load(handle)["zones"]
        self.daylight = {name: [(stamp(p["start"], True), stamp(p["end"], True)) for p in z["daylight_periods"]]
                         for name, z in self.zone.items()}

    def card(self, plan, at):
        found = None
        for begins, version in self.cards[plan]:
            if begins <= at:
                found = version
        if found is None:
            raise SystemExit("no rate card of %s in force" % plan)
        return found

    def shift(self, zone, at):
        z = self.zone[zone]
        if any(a <= at < b for a, b in self.daylight[zone]):
            return z["daylight_offset_minutes"]
        return z["standard_offset_minutes"]

    def local(self, zone, at):
        return datetime.fromtimestamp((at + self.shift(zone, at) * 60000) / 1000, tz=timezone.utc)

    def midnight(self, zone, day):
        base = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()) * 1000
        z = self.zone[zone]
        for minutes in (z["standard_offset_minutes"], z["daylight_offset_minutes"]):
            guess = base - minutes * 60000
            if self.shift(zone, guess) == minutes:
                return guess
        raise SystemExit("local midnight of %s in %s is undefined" % (day, zone))

    def who(self, tenant, at):
        hops = 0
        while tenant in self.merge and at >= self.merge[tenant][0]:
            tenant = self.merge[tenant][1]
            hops += 1
            if hops > len(self.merge):
                raise SystemExit("merge register loops")
        return tenant

    def load(self):
        self.rows = table(self.folder, "queries.csv")
        self.queries = {}
        self.rejected = 0
        for row in self.rows:
            try:
                for key in ("query_id", "node_id", "tenant_id", "product_id"):
                    if not row.get(key):
                        raise Reject(key)
                status = row.get("status", "").lower()
                if status not in ("ok", "cancelled", "failed"):
                    raise Reject(status)
                if row["node_id"] not in self.region_of or row["tenant_id"] not in self.tenant \
                        or row["product_id"] not in self.line_of:
                    raise Reject(row["query_id"])
                q = Query(row["query_id"], row["node_id"], row["tenant_id"], row["product_id"],
                          stamp(row["started_local"], False), count(row["duration_ms"]),
                          count(row["scanned_bytes"]), 0, status)
            except (Reject, KeyError):
                self.rejected += 1
                continue
            q.logged = q.scanned
            self.queries[q.qid] = q
        fixes = []
        with open(os.path.join(self.folder, "corrections.jsonl"), encoding="utf-8") as handle:
            for text in handle:
                if text.strip():
                    fixes.append(json.loads(text))
        for fix in sorted(fixes, key=lambda f: (stamp(f["recorded_at"], True), f["correction_id"])):
            q = self.queries.get(fix["query_id"])
            if q is None:
                continue
            if fix["action"] == "restate":
                q.scanned = fix["scanned_bytes"]
            elif fix["action"] == "void":
                q.withdrawn = True
            elif fix["action"] == "reinstate":
                q.withdrawn = False
        transfers = []
        with open(os.path.join(self.folder, "transfers.log"), encoding="utf-8") as handle:
            for text in handle:
                text = text.strip()
                if not text or text.startswith("#"):
                    continue
                xid, src, sent, dst, recv = (part.strip() for part in text.split("|"))
                transfers.append((xid, src, stamp(sent, False), dst, stamp(recv, False)))
        self.transfer_lines = len(transfers)
        self.fleet.build(transfers)

    def settle_order(self):
        """The order among queries billed at one instant, from the prior allowance statement.

        Every two-key order over metered bytes, start, query id and node, in
        either direction, is replayed against the statement; exactly one must
        reproduce every free_bytes figure in it.
        """
        rows = table(self.folder, "allowance_statement_prior.csv")
        days = {}
        for r in rows:
            days.setdefault((r["billing_day"], r["tenant_id"]), []).append(r)
        fields = {
            "metered": lambda r: int(r["metered_bytes"]),
            "start": lambda r: stamp(r["started_at"], True),
            "query": lambda r: r["query_id"],
            "node": lambda r: r["node_id"],
        }

        def keyed(name, sign, r):
            v = fields[name](r)
            if sign > 0:
                return v
            return -v if isinstance(v, int) else tuple(-ord(ch) for ch in v)

        fits = []
        names = sorted(fields)
        for first in names:
            for second in names:
                if second == first:
                    continue
                for s1 in (1, -1):
                    for s2 in (1, -1):
                        order = ((first, s1), (second, s2))
                        if all(self._replays(day, tenant, group, order, keyed) for (day, tenant), group in days.items()):
                            fits.append(order)
        if len(fits) != 1:
            raise SystemExit("the allowance statement admits %d orders for equal billing instants" % len(fits))
        self.order = fits[0]

    def _replays(self, day, tenant, group, order, keyed):
        segment, plan, zone = self.tenant[tenant]
        left = self.card(plan, self.midnight(zone, datetime.strptime(day, "%Y-%m-%d").date()))["daily_free_bytes"]
        ranked = sorted(group, key=lambda r: (stamp(r["billed_at"], True),) + tuple(keyed(n, sg, r) for n, sg in order))
        for r in ranked:
            take = min(left, int(r["metered_bytes"]))
            left -= take
            if take != int(r["free_bytes"]):
                return False
        return True

    def tie_key(self, q):
        values = {"metered": q.billed["metered"], "start": q.billed["start"], "query": q.qid, "node": q.node}
        out = []
        for name, sign in self.order:
            v = values[name]
            out.append(v if sign > 0 else (-v if isinstance(v, int) else tuple(-ord(ch) for ch in v)))
        return tuple(out)

    def bill(self):
        billed = [q for q in self.queries.values() if q.status != "failed" and not q.withdrawn]
        days = {}
        for q in billed:
            start = q.started - self.fleet.offset(q.node, q.started) * 1000
            end = start + q.duration
            ident = self.who(q.tenant, end)
            segment, plan, zone = self.tenant[ident]
            version = self.card(plan, end)
            metered = max(q.scanned, version["min_billable_bytes"])
            block = version["block_bytes"]
            metered = (metered + block - 1) // block * block
            when = self.local(zone, end)
            day = when.date()
            minute_of_day = when.hour * 60 + when.minute
            peak = (day.weekday() < 5 and day.isoformat() not in self.zone[zone]["holidays"]
                    and 480 <= minute_of_day < 1200)
            q.billed = {"start": start, "end": end, "ident": ident, "segment": segment, "plan": plan, "zone": zone,
                        "version": version, "metered": metered, "day": day, "peak": peak}
            days.setdefault((ident, day), []).append(q)
        for (ident, day), group in days.items():
            plan, zone = self.tenant[ident][1], self.tenant[ident][2]
            left = self.card(plan, self.midnight(zone, day))["daily_free_bytes"]
            group.sort(key=lambda q: (q.billed["end"],) + self.tie_key(q) + (q.qid,))
            for q in group:
                info = q.billed
                take = min(left, info["metered"])
                left -= take
                info["free"] = take
                info["charge_bytes"] = info["metered"] - take
                rate = info["version"]["peak_micros_per_gib" if info["peak"] else "offpeak_micros_per_gib"]
                numerator = info["charge_bytes"] * rate
                info["micros"] = numerator // GIB + (1 if (numerator % GIB) * 2 >= GIB else 0)
        billed.sort(key=lambda q: (q.billed["end"], q.qid))
        self.ledger = []
        for q in billed:
            info = q.billed
            self.ledger.append({
                "billed_at": show(info["end"]), "billing_day": info["day"].isoformat(),
                "chargeable_bytes": info["charge_bytes"], "charge_micros": info["micros"],
                "corrected": q.scanned != q.logged, "free_bytes": info["free"], "metered_bytes": info["metered"],
                "node_id": q.node, "plan_version": info["version"]["version"], "product_id": q.product,
                "product_line": self.line_of[q.product], "query_id": q.qid, "region": self.region_of[q.node],
                "scanned_bytes": q.scanned, "segment": info["segment"], "source_tenant_id": q.tenant,
                "tenant_id": info["ident"], "window": "peak" if info["peak"] else "offpeak",
            })

    def documents(self):
        rows = self.ledger

        def sums(chosen):
            return {
                "billed_queries": len(chosen),
                "metered_bytes": sum(r["metered_bytes"] for r in chosen),
                "free_bytes": sum(r["free_bytes"] for r in chosen),
                "chargeable_bytes": sum(r["chargeable_bytes"] for r in chosen),
                "charge_micros": sum(r["charge_micros"] for r in chosen),
            }

        def by(chosen, key):
            out = {}
            for r in chosen:
                out[r[key]] = out.get(r[key], 0) + r["charge_micros"]
            return out

        docs = {}
        products = []
        for pid in sorted(self.line_of):
            mine = [r for r in rows if r["product_id"] == pid]
            entry = sums(mine)
            del entry["free_bytes"]
            entry.update(product_id=pid, product_line=self.line_of[pid])
            products.append(entry)
        docs["product_summary.json"] = {"products": products}
        for name in REGIONS:
            mine = [r for r in rows if r["region"] == name]
            entry = sums(mine)
            windows = {"offpeak": 0, "peak": 0}
            windows.update(by(mine, "window"))
            entry.update(region=name, in_scope=name in self.region_of.values(),
                         nodes=sorted(n for n, g in self.region_of.items() if g == name),
                         tenants=sorted({r["tenant_id"] for r in mine}), by_window=windows)
            docs["region_%s.json" % name] = entry
        for name in SEGMENTS:
            mine = [r for r in rows if r["segment"] == name]
            entry = sums(mine)
            entry.update(segment=name, in_scope=bool(mine), tenants=sorted({r["tenant_id"] for r in mine}),
                         by_region=by(mine, "region"))
            docs["segment_%s.json" % name] = entry
        total = sum(r["charge_micros"] for r in rows)
        regional = sum(docs["region_%s.json" % n]["charge_micros"] for n in REGIONS)
        segmental = sum(docs["segment_%s.json" % n]["charge_micros"] for n in SEGMENTS)
        by_product = sum(p["charge_micros"] for p in products)
        summary = sums(rows)
        summary.update(by_region=by(rows, "region"), by_segment=by(rows, "segment"), by_window=by(rows, "window"),
                       by_product_line=by(rows, "product_line"), by_plan_version=by(rows, "plan_version"))
        summary["reconciliation"] = {"ledger_charge_micros": total, "region_charge_micros": regional,
                                     "segment_charge_micros": segmental, "product_charge_micros": by_product,
                                     "residual_micros": 3 * total - regional - segmental - by_product}
        docs["summary.json"] = summary
        failed = sum(1 for q in self.queries.values() if q.status == "failed")
        withdrawn = sum(1 for q in self.queries.values() if q.status != "failed" and q.withdrawn)
        docs["data_quality.json"] = {
            "input_files": sorted(e.name for e in os.scandir(self.folder) if e.is_file()),
            "query_rows": len(self.rows), "rejected_rows": self.rejected, "failed_queries": failed,
            "voided_queries": withdrawn, "billed_queries": len(rows),
            "corrected_queries": sum(1 for r in rows if r["corrected"]),
            "merged_queries": sum(1 for r in rows if r["tenant_id"] != r["source_tenant_id"]),
            "transfer_lines": self.transfer_lines,
        }
        text = {"normalized.jsonl": "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows)}
        for name, body in docs.items():
            text[name] = json.dumps(body, sort_keys=True, indent=2) + "\n"
        return text


def main(argv):
    folder = argv[1] if len(argv) > 1 else "/app/data"
    target = argv[2] if len(argv) > 2 else "/app/out"
    meter = Meter(folder)
    meter.load()
    meter.settle_order()
    meter.bill()
    text = meter.documents()
    os.makedirs(target, exist_ok=True)
    lines = []
    for name in sorted(REPORTS):
        data = text[name].encode("utf-8")
        with open(os.path.join(target, name), "wb") as handle:
            handle.write(data)
        lines.append("%s %d\n" % (name, len(data)))
    sys.stdout.write("".join(lines))


if __name__ == "__main__":
    main(sys.argv)
