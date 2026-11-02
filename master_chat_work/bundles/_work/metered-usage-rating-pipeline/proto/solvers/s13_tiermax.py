#!/usr/bin/env python3
"""Monthly metered usage rating: collectors in, rated lines and reports out."""
import argparse
import bisect
import collections
import configparser
import csv
import datetime as dt
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_EVEN, Decimal

REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
CODES = ["CMP", "EGR", "STO", "SUP"]
REASONS = ["timestamp_outside_month", "unknown_account", "unknown_product", "units_not_integer"]
COLLECTOR_FILE = {
    "central": "collector_central.csv",
    "east": "collector_east.tsv",
    "north": "collector_north.jsonl",
    "south": "collector_south.txt",
    "west": "collector_west.log",
}
REQUIRED = list(COLLECTOR_FILE.values()) + [
    "accounts.csv", "plan_changes.log", "rate_card.json", "commitments.xml",
    "products.ini", "collector_controls.json",
]
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
FLOOR = Decimal("0.50")
UTC = dt.timezone.utc


class InputError(Exception):
    """A declared input is missing or disagrees with its control."""


def canonical(account):
    return account.strip().upper().replace("-", "")


def to_cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def money(value):
    return f"{value:.2f}"


def nonblank(text):
    return [line for line in text.splitlines() if line.strip()]


def utc(text, fmt):
    return dt.datetime.strptime(text.strip(), fmt).replace(tzinfo=UTC)


def text_units(raw):
    raw = raw.strip()
    if raw and all("0" <= ch <= "9" for ch in raw):
        return int(raw)
    return None


def json_units(raw):
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None


# Each reader returns (record_id, utc timestamp, account, product name, units or None).
def read_central(text):
    rows = list(csv.reader(nonblank(text)))[1:]
    return [(r[0].strip(), utc(r[1], "%Y-%m-%d %H:%M:%S"), r[2].strip(), r[3].strip(), text_units(r[4]))
            for r in rows]


def read_east(text):
    out = []
    for line in nonblank(text)[1:]:
        rid, epoch, acct, prod, qty = line.split("\t")
        when = dt.datetime.fromtimestamp(int(epoch.strip()), UTC)
        out.append((rid.strip(), when, acct.strip(), prod.strip(), text_units(qty)))
    return out


def read_north(text):
    out = []
    for line in nonblank(text):
        obj = json.loads(line)
        out.append((obj["id"].strip(), utc(obj["at"], "%Y-%m-%dT%H:%M:%SZ"), obj["acct"].strip(),
                    obj["sku"].strip(), json_units(obj["units"])))
    return out


def read_south(text):
    return [(line[0:10].strip(), utc(line[10:24], "%Y%m%d%H%M%S"), line[24:34].strip(),
             line[34:46].strip(), text_units(line[46:52]))
            for line in nonblank(text)]


def read_west(text):
    out = []
    for line in nonblank(text):
        stamp, *tokens = line.split()
        fields = dict(tok.split("=", 1) for tok in tokens)
        when = dt.datetime.fromisoformat(stamp).astimezone(UTC)
        out.append((fields["rec"].strip(), when, fields["acct"].strip(), fields["product"].strip(),
                    text_units(fields["qty"])))
    return out


READERS = {"central": read_central, "east": read_east, "north": read_north,
           "south": read_south, "west": read_west}


class Month:
    """Reference data for one billing month."""

    def __init__(self, folder):
        for name in REQUIRED:
            if not (folder / name).is_file():
                raise InputError(f"missing input: {name}")
        self.folder = folder
        controls = json.loads(self.read("collector_controls.json"))
        self.label = controls["month"].strip()
        self.controls = {r: int(controls["collectors"][r]["records"]) for r in REGIONS}
        self.start = dt.datetime.strptime(self.label + "-01", "%Y-%m-%d").replace(tzinfo=UTC)
        self.end = (self.start + dt.timedelta(days=32)).replace(day=1)
        self.load_products()
        self.load_rates()
        self.load_accounts()
        self.load_changes()
        tree = ET.fromstring(self.read("commitments.xml"))
        self.pools = {p.get("region").strip(): Decimal(p.get("amount").strip()) for p in tree.iter("pool")}
        self.minimums = {p.get("region").strip(): Decimal(p.get("minimum").strip()) for p in tree.iter("pool")}

    def read(self, name, encoding="utf-8"):
        return (self.folder / name).read_text(encoding=encoding)

    def load_products(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(self.read("products.ini"))
        self.unit = {}
        self.alias = {r: {} for r in REGIONS}
        for section in parser.sections():
            code = section.strip()
            self.unit[code] = parser[section]["unit"].strip()
            for region in REGIONS:
                self.alias[region][parser[section][region].strip()] = code

    def load_rates(self):
        card = json.loads(self.read("rate_card.json"), parse_float=Decimal)
        self.tiers = {}
        for code, spec in card["products"].items():
            ladder = sorted(spec["tiers"], key=lambda t: int(t["from"]))
            self.tiers[code] = ([int(t["from"]) for t in ladder],
                                [(int(t["tier"]), {s: Decimal(v) for s, v in t["rates"].items()})
                                 for t in ladder])

    def load_accounts(self):
        self.start_state = {}
        parent = {}
        for row in csv.DictReader(nonblank(self.read("accounts.csv"))):
            acct = canonical(row["account_id"])
            self.start_state[acct] = {"segment": row["segment"].strip(), "plan": row["plan"].strip()}
            parent[acct] = canonical(row["parent"] or "")
        self.group = {}
        for acct in parent:
            chain = []
            node = acct
            while node not in self.group and parent[node]:
                chain.append(node)
                node = parent[node]
            top = self.group.get(node, node)
            self.group[node] = top
            for member in chain:
                self.group[member] = top
        self.committed = {a for a, st in self.start_state.items() if st["plan"] == "committed"}

    def load_changes(self):
        self.history = collections.defaultdict(list)
        self.change_lines = 0
        self.change_applied = 0
        for line in nonblank(self.read("plan_changes.log")):
            self.change_lines += 1
            stamp, _verb, *pairs = line.split()
            fields = dict(p.split("=", 1) for p in pairs)
            acct = canonical(fields.pop("account"))
            if acct not in self.start_state:
                continue
            self.change_applied += 1
            update = {k: v.strip() for k, v in fields.items() if k in ("plan", "segment")}
            self.history[acct].append((utc(stamp, "%Y-%m-%dT%H:%M:%SZ"), update))
        for entries in self.history.values():
            entries.sort(key=lambda e: e[0])  # stable sort keeps file order within one timestamp

    def state_at(self, acct, when):
        state = dict(self.start_state[acct])
        for stamp, update in self.history.get(acct, ()):
            if stamp > when:
                break
            state.update(update)
        return state

    def tier_for(self, code, used):
        starts, ladder = self.tiers[code]
        best = max((s for s in starts if s <= used))
        return ladder[starts.index(best)]


def screen(month):
    """Return accepted lines and the data quality document."""
    lines, quarantined = [], []
    collectors = {}
    reasons = dict.fromkeys(REASONS, 0)
    for region in REGIONS:
        name = COLLECTOR_FILE[region]
        encoding = "latin-1" if region == "south" else "utf-8"
        records = READERS[region](month.read(name, encoding))
        if len(records) != month.controls[region]:
            raise InputError(f"control mismatch: {name}")
        seen = set()
        tally = collections.Counter()
        for rid, when, acct, product, units in records:
            if rid in seen:
                tally["duplicates"] += 1
                continue
            seen.add(rid)
            acct = canonical(acct)
            if not month.start <= when < month.end:
                reason = "timestamp_outside_month"
            elif acct not in month.start_state:
                reason = "unknown_account"
            elif product not in month.alias[region]:
                reason = "unknown_product"
            elif units is None:
                reason = "units_not_integer"
            else:
                tally["accepted"] += 1
                lines.append({"record_id": rid, "region": region, "when": when, "account_id": acct,
                              "product": month.alias[region][product], "units": units})
                continue
            tally["quarantined"] += 1
            reasons[reason] += 1
            quarantined.append({"collector": region, "record_id": rid, "reason": reason})
        collectors[region] = {"file": name, "records": len(records), "duplicates": tally["duplicates"],
                              "quarantined": tally["quarantined"], "accepted": tally["accepted"]}
    quarantined.sort(key=lambda q: (q["collector"], q["record_id"]))
    quality = {"month": month.label, "collectors": collectors, "quarantine_reasons": reasons,
               "quarantined_records": quarantined,
               "plan_changes": {"lines": month.change_lines, "applied": month.change_applied,
                                "unmatched": month.change_lines - month.change_applied}}
    return lines, quality


def rate(month, lines):
    """Rate lines in rating order, then share each region's pool over its credit base."""
    lines.sort(key=lambda ln: (ln["when"], ln["record_id"]))
    used = collections.Counter()
    for ln in lines:
        state = month.state_at(ln["account_id"], ln["when"])
        key = (month.group[ln["account_id"]], ln["product"])
        tier_no, rates = month.tier_for(ln["product"], used[key])
        used[key] += ln["units"]
        ln.update(segment=state["segment"], plan=state["plan"], tier=tier_no,
                  rate=rates[state["segment"]])
        ln["charge"] = to_cents(ln["rate"] * ln["units"])
    counted = {region: [] for region in REGIONS}
    for ln in lines:
        ln["credit"] = ln["true_up"] = ZERO
        if ln["account_id"] in month.committed:
            counted[ln["region"]].append(ln)
    base = {region: sum((ln["charge"] for ln in counted[region]), ZERO) for region in REGIONS}
    for region in REGIONS:
        pool, minimum = month.pools[region], month.minimums[region]
        if base[region] <= pool:
            for ln in counted[region]:
                ln["credit"] = ln["charge"]
        else:
            share_with_floor(pool, counted[region], base[region], "credit")
        if base[region] < minimum:
            share_with_floor(minimum - base[region], counted[region], base[region], "true_up")
    for ln in lines:
        ln["net"] = ln["charge"] - ln["credit"] + ln["true_up"]
    return base


def share_with_floor(total, part, denom, field):
    """First pass in proportion to charge; lines under 0.50 get 0.00 and every cent of the total is
    shared again over the lines that held 0.50 or more (denominator: their summed charge)."""
    first = [(ln, to_cents(total * ln["charge"] / denom)) for ln in part]
    held = [ln for ln, share in first if share >= FLOOR]
    kept = sum((ln["charge"] for ln in held), ZERO)
    for ln in part:
        ln[field] = ZERO
    for ln in held:
        ln[field] = to_cents(total * ln["charge"] / kept)


def totals(lines):
    return {"charge": money(sum((ln["charge"] for ln in lines), ZERO)),
            "credit": money(sum((ln["credit"] for ln in lines), ZERO)),
            "true_up": money(sum((ln["true_up"] for ln in lines), ZERO)),
            "net": money(sum((ln["net"] for ln in lines), ZERO))}


def units_by_code(lines):
    return {code: sum(ln["units"] for ln in lines if ln["product"] == code) for code in CODES}


def reports(month, lines, base):
    docs = {"summary.json": {"month": month.label, "lines": len(lines),
                             "accounts_billed": len({ln["account_id"] for ln in lines}),
                             "units": units_by_code(lines), **totals(lines)}}
    products = {}
    for code in CODES:
        part = [ln for ln in lines if ln["product"] == code]
        products[code] = {"unit": month.unit[code], "lines": len(part),
                          "units": sum(ln["units"] for ln in part), **totals(part)}
    docs["product_summary.json"] = {"month": month.label, "products": products}
    for region in REGIONS:
        part = [ln for ln in lines if ln["region"] == region]
        sums = totals(part)
        applied = sum((ln["credit"] for ln in part), ZERO)
        docs[f"region_{region}.json"] = {
            "region": region, "month": month.label, "lines": len(part),
            "accounts": len({ln["account_id"] for ln in part}), "units": units_by_code(part),
            "charge": sums["charge"], "credit_pool": money(month.pools[region]),
            "credit_base": money(base[region]), "credit_applied": money(applied),
            "credit_unallocated": money(month.pools[region] - applied),
            "minimum": money(month.minimums[region]), "true_up": sums["true_up"], "net": sums["net"]}
    for segment in SEGMENTS:
        part = [ln for ln in lines if ln["segment"] == segment]
        by_product = {}
        for code in CODES:
            sub = [ln for ln in part if ln["product"] == code]
            by_product[code] = {"lines": len(sub), "units": sum(ln["units"] for ln in sub),
                                "charge": totals(sub)["charge"]}
        docs[f"segment_{segment}.json"] = {
            "segment": segment, "month": month.label, "lines": len(part),
            "accounts": len({ln["account_id"] for ln in part}), "by_product": by_product, **totals(part)}
    return docs


def normalized_row(ln):
    return {"record_id": ln["record_id"], "region": ln["region"],
            "timestamp": ln["when"].strftime("%Y-%m-%dT%H:%M:%SZ"), "account_id": ln["account_id"],
            "segment": ln["segment"], "plan": ln["plan"], "product": ln["product"], "units": ln["units"],
            "tier": ln["tier"], "unit_rate": f"{ln['rate']:.4f}", "charge": money(ln["charge"]),
            "credit": money(ln["credit"]), "true_up": money(ln["true_up"]), "net": money(ln["net"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        month = Month(args.input)
        lines, quality = screen(month)
    except InputError as exc:
        print(exc, file=sys.stderr)
        return 1
    base = rate(month, lines)
    docs = reports(month, lines, base)
    docs["data_quality.json"] = quality
    args.output.mkdir(parents=True, exist_ok=True)
    with open(args.output / "normalized.jsonl", "w", encoding="utf-8") as handle:
        for ln in lines:
            handle.write(json.dumps(normalized_row(ln)) + "\n")
    for name, doc in docs.items():
        (args.output / name).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
