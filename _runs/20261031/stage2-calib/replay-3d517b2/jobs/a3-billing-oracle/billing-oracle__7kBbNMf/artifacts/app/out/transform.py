#!/usr/bin/env python3
"""Concierge desk billing cycle run: python3 transform.py DATA_DIR OUT_DIR."""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

BASE = dt.datetime(1970, 1, 1)
TIER_STANDARD, TIER_AFTER, TIER_WEEKEND = "standard", "after_hours", "weekend_holiday"
REGION_NAMES = ("central", "east", "north", "south", "west")
SEGMENT_NAMES = ("consumer", "corporate", "enterprise", "smb")
OFFSET_RANGE = range(-19, 20)


class CycleError(RuntimeError):
    """The extract does not settle a figure the run needs."""


def instant(text: str) -> int:
    return int((dt.datetime.fromisoformat(text) - BASE).total_seconds())


def handset_reading(text: str) -> int:
    day_part, time_part = text.split(" ")
    d, m, y = day_part.split(".")
    return instant(f"{y}-{m}-{d}T{time_part}")


def show_instant(seconds: int) -> str:
    return (BASE + dt.timedelta(seconds=seconds)).isoformat()


def day_number(text: str) -> int:
    return (dt.date.fromisoformat(text) - BASE.date()).days


def show_day(n: int) -> str:
    return (BASE.date() + dt.timedelta(days=n)).isoformat()


def read_rows(path: Path) -> list[dict[str, str]]:
    raw = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(raw.splitlines())
    names = [n.strip() for n in (reader.fieldnames or [])]
    rows = []
    for record in reader:
        values = [(record.get(k) or "").strip() for k in reader.fieldnames or []]
        if any(values):
            rows.append(dict(zip(names, values)))
    return rows


@dataclass
class Closing:
    ref: str
    handset: str
    seq: int
    client: str
    code: str
    stamp: int
    worked: int
    done: int = 0
    offset: int = 0
    service: str = ""
    local_day: int = 0
    tier: str = ""
    rate: int = 0
    billable: int = 0
    credited: int = 0
    flags: set = field(default_factory=set)


def encode(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def cents_of(micro: int) -> int:
    whole, rest = divmod(micro, 10000)
    if rest > 5000 or (rest == 5000 and whole % 2):
        whole += 1
    return whole


class ClockSolver:
    """Clock offsets of one exchange day: every registered call needs a closing in its slot."""

    def __init__(self, stamps: dict[str, list[tuple[str, int]]], register: dict[tuple[str, int], int]):
        self.stamps = stamps
        self.register = register
        self.handsets = sorted(stamps)
        self.landing: dict[str, dict[int, dict[tuple[str, int], int]]] = {}
        for h in self.handsets:
            per = {}
            for off in OFFSET_RANGE:
                cells: dict[tuple[str, int], int] = {}
                for line, second in stamps[h]:
                    cell = (line, (second + 60 * off) // 60)
                    cells[cell] = cells.get(cell, 0) + 1
                per[off] = cells
            self.landing[h] = per
        self.touch: dict[str, set] = {h: {line for line, _ in stamps[h]} for h in self.handsets}
        self.cells_of_line: dict[str, list] = {}
        for cell in register:
            self.cells_of_line.setdefault(cell[0], []).append(cell)

    def _cover(self, chosen: dict[str, int], domains: dict[str, list[int]], lines) -> bool:
        for line in lines:
            for cell in self.cells_of_line.get(line, ()):
                total = 0
                for h in self.handsets:
                    if line not in self.touch[h]:
                        continue
                    if h in chosen:
                        total += self.landing[h][chosen[h]].get(cell, 0)
                    else:
                        total += max(self.landing[h][o].get(cell, 0) for o in domains[h])
                if total < self.register[cell]:
                    return False
        return True

    def solve(self) -> dict[str, int]:
        served = set().union(*self.touch.values()) if self.touch else set()
        if any(cell[0] not in served for cell in self.register):
            raise CycleError("a registered line has no closing on this day")
        domains = {h: list(OFFSET_RANGE) for h in self.handsets}
        for h in self.handsets:
            domains[h] = [o for o in domains[h] if self._cover({h: o}, domains, self.touch[h])]
        order = sorted(self.handsets, key=lambda h: (len(domains[h]), h))
        found: list[dict[str, int]] = []

        def walk(i: int, chosen: dict[str, int]) -> None:
            if len(found) > 1:
                return
            if i == len(order):
                found.append(dict(chosen))
                return
            h = order[i]
            for o in domains[h]:
                chosen[h] = o
                if self._cover(chosen, domains, self.touch[h]):
                    walk(i + 1, chosen)
                del chosen[h]

        walk(0, {})
        if not found:
            raise CycleError("no clock offsets fit the register")
        if len(found) > 1:
            raise CycleError("more than one set of clock offsets fits the register")
        return found[0]


class CycleRun:
    def __init__(self, data_dir: Path):
        self.data = data_dir
        head = json.loads((data_dir / "cycle.json").read_text(encoding="utf-8-sig"))
        self.cycle = head["cycle"]
        self.first = day_number(head["first_day"])
        self.last = day_number(head["last_day"])
        self.minimum = int(head["minimum_invoice_micro"])
        self.card_name = head["rate_card"]
        self.clients = {r["client"]: r for r in read_rows(data_dir / "clients.csv")}
        self.plans = {r["plan"]: r for r in read_rows(data_dir / "plans.csv")}
        self.zone_steps: dict[str, list[tuple[int, int]]] = {}
        for r in read_rows(data_dir / "zone_rules.csv"):
            self.zone_steps.setdefault(r["zone"], []).append((instant(r["from_utc"]), int(r["utc_offset_minutes"])))
        for steps in self.zone_steps.values():
            steps.sort()
        self.holidays = {(r["region"], day_number(r["day"])) for r in read_rows(data_dir / "holidays.csv")}
        self.catalog = {r["service"].upper(): (r["product_line"], int(r["increment_minutes"])) for r in read_rows(data_dir / "service_catalog.csv")}
        self.alias = {r["alias"].upper(): r["service"].upper() for r in read_rows(data_dir / "code_aliases.csv")}
        self.card: dict[tuple[str, str], list[tuple[int, int | None, int]]] = {}
        for r in read_rows(data_dir / self.card_name):
            end = day_number(r["effective_to"]) if r["effective_to"] else None
            self.card.setdefault((r["service"].upper(), r["tier"]), []).append((day_number(r["effective_from"]), end, int(r["rate_micro_per_minute"])))

    def load_closings(self) -> tuple[dict[tuple[str, int], Closing], list[str]]:
        found: dict[tuple[str, int], Closing] = {}
        for r in read_rows(self.data / "closings.csv"):
            c = Closing(r["ref"], r["handset"], int(r["seq"]), r["client"], r["service"].upper(), instant(r["stamped_at"]), int(r["worked_minutes"]))
            found[(c.handset, c.seq)] = c
        dropped: list[str] = []
        unit = ""
        for text in (self.data / "legacy_closings.txt").read_text(encoding="utf-8-sig").split("\n"):
            if text.startswith("#"):
                if text.startswith("# duration unit:"):
                    unit = text.partition(":")[2].strip()
                continue
            if not text.strip():
                continue
            ref, handset, seq, client, code, stamped, duration = (part.strip() for part in text.split("|"))
            if (handset, int(seq)) in found:
                dropped.append(ref)
                continue
            if unit == "minutes":
                worked = int(duration)
            elif unit == "seconds":
                worked = (int(duration) + 59) // 60
            else:
                raise CycleError(f"legacy duration unit {unit!r}")
            found[(handset, int(seq))] = Closing(ref, handset, int(seq), client, code.upper(), handset_reading(stamped), worked)
        return found, dropped

    def place_on_exchange_clock(self, closings: dict[tuple[str, int], Closing]) -> None:
        register: dict[int, dict[tuple[str, int], int]] = {}
        for r in read_rows(self.data / "exchange_register.csv"):
            hour, minute = r["slot"].split(":")
            day = day_number(r["day"])
            register.setdefault(day, {})[(r["line"], day * 1440 + int(hour) * 60 + int(minute))] = int(r["calls"])
        days: dict[int, dict[str, list]] = {}
        for c in closings.values():
            days.setdefault(c.stamp // 86400, {}).setdefault(c.handset, []).append((self.clients[c.client]["line"], c.stamp))
        per_day: dict[int, dict[str, int]] = {}
        for day in sorted(days):
            per_day[day] = ClockSolver(days[day], register.get(day, {})).solve()
        for c in closings.values():
            c.offset = per_day[c.stamp // 86400][c.handset]
            c.done = c.stamp + 60 * c.offset

    def apply_amendments(self, closings: dict[tuple[str, int], Closing]) -> tuple[set, set]:
        entries = []
        for text in (self.data / "amendments.jsonl").read_text(encoding="utf-8-sig").split("\n"):
            if text.strip():
                entries.append(json.loads(text))
        index = {e["amendment"]: e for e in entries}
        idle: set = set()
        cancelled: set = set()
        for e in entries:
            if e["action"] == "revert":
                target = index.get(e["reverts"])
                if target is None or target["action"] == "revert" or instant(e["issued_at"]) <= instant(target["issued_at"]):
                    idle.add(e["amendment"])
                else:
                    cancelled.add(target["amendment"])
            else:
                c = closings.get((e["handset"], e["seq"]))
                if c is None or instant(e["issued_at"]) < c.done:
                    idle.add(e["amendment"])
        acting = sorted((e for e in entries if e["action"] != "revert" and e["amendment"] not in idle | cancelled),
                        key=lambda e: (instant(e["issued_at"]), e["amendment"]))
        voided = set()
        for e in acting:
            target = closings[(e["handset"], e["seq"])]
            if e["action"] == "void":
                voided.add((target.handset, target.seq))
            else:
                target.worked = int(e["minutes"])
        return idle | cancelled, voided

    def zone_offset(self, zone: str, at: int) -> int:
        current = None
        for start, minutes in self.zone_steps[zone]:
            if start > at:
                break
            current = minutes
        if current is None:
            raise CycleError(f"zone {zone} has no rule in force")
        return current

    def classify(self, c: Closing) -> None:
        client = self.clients[c.client]
        local = c.done + 60 * self.zone_offset(client["zone"], c.done)
        c.local_day, second = divmod(local, 86400)
        weekday = (BASE.date() + dt.timedelta(days=c.local_day)).weekday()
        if weekday in (5, 6) or (client["region"], c.local_day) in self.holidays:
            c.tier = TIER_WEEKEND
        elif 28800 <= second < 64800:
            c.tier = TIER_STANDARD
        else:
            c.tier = TIER_AFTER

    def price(self, c: Closing) -> bool:
        for start, end, rate in self.card.get((c.service, c.tier), ()):
            if start <= c.local_day and (end is None or c.local_day < end):
                c.rate = rate
                return True
        return False

    def run(self, out_dir: Path) -> None:
        closings, duplicates = self.load_closings()
        self.place_on_exchange_clock(closings)
        idle, voided = self.apply_amendments(closings)
        rejected: dict[str, str] = {}
        outside, void, unrated, billed = [], [], [], []
        for key, c in closings.items():
            if c.code in self.catalog:
                c.service = c.code
            elif c.code in self.alias and self.alias[c.code] in self.catalog:
                c.service = self.alias[c.code]
            else:
                rejected[c.ref] = "unknown_service"
                continue
            self.classify(c)
            if not self.first <= c.local_day <= self.last:
                outside.append(c.ref)
            elif key in voided:
                void.append(c.ref)
            elif not self.price(c):
                unrated.append(c.ref)
            else:
                step = self.catalog[c.service][1]
                c.billable = -(-c.worked // step) * step
                billed.append(c)
        self.credit(billed)
        billed.sort(key=lambda c: (c.done, c.ref))
        reports = self.reports(billed)
        reports["data_quality.json"] = encode({
            "amendments_without_effect": sorted(idle), "closings_received": len(closings),
            "duplicates": sorted(duplicates), "input_files": sorted(p.name for p in self.data.iterdir() if p.is_file()),
            "outside_cycle": sorted(outside), "rejected": rejected, "unrated": sorted(unrated), "void": sorted(void)})
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in sorted(reports):
            blob = reports[name].encode("ascii")
            (out_dir / name).write_bytes(blob)
            print(f"wrote {name} {len(blob)}")

    def credit(self, billed: list[Closing]) -> None:
        queues: dict[str, list[Closing]] = {}
        for c in billed:
            plan = self.plans[self.clients[c.client]["plan"]]
            if c.tier in plan["credit_tiers"].split(" "):
                queues.setdefault(c.client, []).append(c)
        for client, queue in queues.items():
            remaining = int(self.plans[self.clients[client]["plan"]]["included_minutes"])
            queue.sort(key=lambda c: (-c.done, c.ref))
            for c in queue:
                c.credited = min(remaining, c.billable)
                remaining -= c.credited

    def reports(self, billed: list[Closing]) -> dict[str, str]:
        def amounts(c: Closing) -> tuple[int, int]:
            return c.billable * c.rate, (c.billable - c.credited) * c.rate

        def roll(items: list[Closing]) -> dict:
            tiers: dict[str, int] = {}
            gross = net = 0
            for c in items:
                g, n = amounts(c)
                gross += g
                net += n
                tiers[c.tier] = tiers.get(c.tier, 0) + n
            return {"by_tier": tiers, "clients": sorted({c.client for c in items}), "closings": len(items),
                    "credit_micro": gross - net, "gross_micro": gross, "net_cents": cents_of(net), "net_micro": net}

        out: dict[str, str] = {}
        rows = []
        for c in billed:
            client = self.clients[c.client]
            gross, net = amounts(c)
            rows.append(encode({
                "billable_minutes": c.billable, "charged_minutes": c.billable - c.credited, "client": c.client,
                "completed_at": show_instant(c.done), "credited_minutes": c.credited, "gross_micro": gross,
                "handset": c.handset, "line": client["line"], "local_day": show_day(c.local_day), "net_micro": net,
                "product_line": self.catalog[c.service][0], "rate_micro_per_minute": c.rate, "ref": c.ref,
                "region": client["region"], "segment": client["segment"], "seq": c.seq, "service": c.service,
                "tier": c.tier, "worked_minutes": c.worked}))
        out["normalized.jsonl"] = "".join(rows)
        totals = {}
        for name in REGION_NAMES:
            part = roll([c for c in billed if self.clients[c.client]["region"] == name])
            part.update(region=name, in_scope=part["gross_micro"] >= self.minimum)
            totals[f"region_{name}.json"] = part
        for name in SEGMENT_NAMES:
            part = roll([c for c in billed if self.clients[c.client]["segment"] == name])
            part.update(segment=name, in_scope=part["net_micro"] >= self.minimum)
            totals[f"segment_{name}.json"] = part
        lines_out = []
        for line in sorted({pl for pl, _ in self.catalog.values()}):
            items = [c for c in billed if self.catalog[c.service][0] == line]
            lines_out.append({"billable_minutes": sum(c.billable for c in items), "closings": len(items),
                              "gross_micro": sum(amounts(c)[0] for c in items), "net_micro": sum(amounts(c)[1] for c in items),
                              "product_line": line})
        everything = roll(billed)
        del everything["clients"]
        stream_net = sum(amounts(c)[1] for c in billed)
        product_net = sum(p["net_micro"] for p in lines_out)
        region_net = sum(v["net_micro"] for k, v in totals.items() if k.startswith("region_"))
        segment_net = sum(v["net_micro"] for k, v in totals.items() if k.startswith("segment_"))
        everything["closings_billed"] = everything.pop("closings")
        everything["cycle"] = self.cycle
        everything["reconciliation"] = {"normalized_net_micro": stream_net, "product_net_micro": product_net,
                                        "region_net_micro": region_net, "segment_net_micro": segment_net,
                                        "residual_micro": product_net + region_net + segment_net - 3 * stream_net}
        out["summary.json"] = encode(everything)
        out["product_summary.json"] = encode({"product_lines": lines_out})
        for name, part in totals.items():
            out[name] = encode(part)
        return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: transform.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    try:
        CycleRun(Path(argv[1])).run(Path(argv[2]))
    except CycleError as exc:
        print(f"cycle run stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
