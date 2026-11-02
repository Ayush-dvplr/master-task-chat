"""Prototype end-to-end solver: rendered files -> 9 JSON outputs.
Usage: solve_proto.py <data_dir> <out_dir> [solver]   (solver = core.SOLVERS key, default ref)"""
import configparser, csv, json, os, re, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

DEPOTS = core.DEPOTS
FMT = "%Y-%m-%dT%H:%M"


def load(data):
    g = configparser.ConfigParser()
    g.read(os.path.join(data, "grid.ini"))
    pd = g["plan"]["plan_date"]
    t0 = datetime.strptime(g["plan"]["first_slot"], FMT)
    S = int(g["plan"]["slots"])

    def slot(t):
        d = datetime.strptime(t, FMT) - t0
        return int(d.total_seconds()) // 900

    def ts(s):
        return (t0 + timedelta(minutes=15 * s)).strftime(FMT)

    feeder = [int(g["feeder"]["feeder_kwh_per_slot"])] * S
    base = t0.hour * 4 + t0.minute // 15

    def tod(hhmm):
        h, mi = hhmm.split(":")
        return (int(h) * 4 + int(mi) // 15 - base) % S

    import xml.etree.ElementTree as ET
    versions = []
    for v in ET.parse(os.path.join(data, "tariff.xml")).getroot().iter("version"):
        arr = [None] * S
        for bd in v.iter("band"):
            a, b2 = tod(bd.get("from")), tod(bd.get("to"))
            n = (b2 - a) % S or S
            for i in range(n):
                arr[(a + i) % S] = int(bd.get("cents_per_kwh"))
        versions.append((v.get("valid_from"), v.get("valid_to"), arr))

    def tariff_on(day):
        hit = [arr for v0, v1, arr in versions if v0 <= day <= v1]
        assert len(hit) == 1, day
        return hit[0]

    price = tariff_on(pd)
    sess = {d: [] for d in DEPOTS}
    for r in csv.DictReader(open(os.path.join(data, "settlements.csv"))):
        st = datetime.strptime(r["start"], FMT)
        en = datetime.strptime(r["end"], FMT)
        L = int((en - st).total_seconds()) // 900
        s0 = tod(st.strftime("%H:%M"))
        sess[r["depot"]].append((tariff_on(r["settled_date"]), s0, L, int(r["kwh"]) // L, int(r["cents"])))
    dprice = {}
    for d in DEPOTS:
        ks = [k for k in range(S) if all(c == sum(rr * arr[(s0 + i + k) % S] for i in range(L)) for arr, s0, L, rr, c in sess[d])]
        assert len(ks) == 1, (d, ks)
        dprice[d] = [price[(s + ks[0]) % S] for s in range(S)]
    dj = json.load(open(os.path.join(data, "depots.json")))
    ck = dj["cabinet_kwh_per_slot"]
    cabs = {d["depot"]: [d["cabinets"]] * S for d in dj["depots"]}
    note = open(os.path.join(data, "disruption_notice.md")).read()
    for m in re.finditer(r"^- (\w+): (\d+) cabinets out of service from (\S+) to (\S+)$", note, re.M):
        for s in range(max(0, slot(m.group(3))), min(S, slot(m.group(4)))):
            cabs[m.group(1)][s] = max(0, cabs[m.group(1)][s] - int(m.group(2)))
    for m in re.finditer(r"^- from (\S+) to (\S+): feeder limit (\d+) kWh per slot$", note, re.M):
        for s in range(max(0, slot(m.group(1))), min(S, slot(m.group(2)))):
            feeder[s] = int(m.group(3))
    nd = (datetime.strptime(pd, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    extra = {}
    for m in re.finditer(r"^- (\w+): extra trip on (\S+), (\d+) kWh$", note, re.M):
        if m.group(2) == nd:
            extra[m.group(1)] = extra.get(m.group(1), 0) + int(m.group(3))
    types = json.load(open(os.path.join(data, "bus_types.json")))
    fleet = {r["vehicle_id"]: r for r in csv.DictReader(open(os.path.join(data, "fleet_register.csv")))}
    ccls = {c["contract_id"]: c["class"] for c in json.load(open(os.path.join(data, "contracts.json")))["contracts"]}
    sc = configparser.ConfigParser()
    sc.read(os.path.join(data, "service_classes.ini"))
    weight = {k: int(sc[k]["weight"]) for k in sc.sections()}
    trips = {}
    for line in open(os.path.join(data, "trips.jsonl")):
        t = json.loads(line)
        if t["service_date"] == nd:
            trips[t["bus_id"]] = trips.get(t["bus_id"], 0) + t["kwh"]
    rej, buses, seen = [], [], set()
    with open(os.path.join(data, "roster.csv")) as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            if r["plan_date"] != pd:
                continue
            bid = r["bus_id"]
            why = None
            if bid not in fleet:
                why = "unknown_vehicle"
            elif fleet[bid]["status"] != "active":
                why = "retired_vehicle"
            elif bid in seen:
                why = "duplicate_roster_row"
            elif not (0 <= slot(r["arrive"]) < slot(r["depart"]) <= S):
                why = "bad_window"
            if why:
                rej.append({"file": "roster.csv", "line": ln, "reason": why})
                continue
            seen.add(bid)
            ty = types[fleet[bid]["type"]]
            need = max(0, trips.get(bid, 0) + extra.get(bid, 0) + ty["reserve_kwh"] - int(r["soc_arrival_kwh"]))
            cls = ccls.get(r["contract_id"], "commercial")
            buses.append({"id": bid, "depot": r["depot"], "a": slot(r["arrive"]), "e": slot(r["depart"]),
                          "need": need, "rate": ty["max_kwh_per_slot"], "w": weight[cls], "cls": cls, "pub": {}})
    byid = {b["id"]: b for b in buses}
    with open(os.path.join(data, "published_plan.csv")) as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            if r["plan_date"] != pd:
                continue
            b = byid.get(r["bus_id"])
            if b is None:
                continue
            s = slot(r["slot_start"])
            if not (b["a"] <= s < b["e"]):
                rej.append({"file": "published_plan.csv", "line": ln, "reason": "published_row_outside_window"})
                continue
            b["pub"][str(s)] = b["pub"].get(str(s), 0) + int(r["kwh"])
    cap = {d: [c * ck for c in cabs[d]] for d in DEPOTS}
    inst = {"S": S, "price": price, "dprice": dprice, "feeder": feeder, "cap": cap, "buses": sorted(buses, key=lambda b: b["id"])}
    return inst, rej, pd, ts


def write(inst, x, rej, pd, ts, out):
    S = inst["S"]
    os.makedirs(out, exist_ok=True)
    load = [0] * S
    for (bid, s), k in x.items():
        load[s] += k
    rows = []
    for b in inst["buses"]:
        ch = sorted((s, k) for (bid, s), k in x.items() if bid == b["id"])
        got = sum(k for _, k in ch)
        un = b["need"] - got
        reason = None
        if un > 0:
            reason = "window" if b["need"] > b["rate"] * (b["e"] - b["a"]) else "supply"
        pubd = {int(s): k for s, k in b["pub"].items()}
        rows.append({"bus_id": b["id"], "depot": b["depot"], "class": b["cls"], "need_kwh": b["need"],
                     "delivered_kwh": got, "unmet_kwh": un, "unmet_reason": reason,
                     "changed": dict(ch) != pubd,
                     "charges": [{"slot": ts(s), "kwh": k} for s, k in ch],
                     "_cost": sum(k * core.dp(inst, b["depot"])[s] for s, k in ch),
                     "_moved": sum(max(0, p - dict(ch).get(s, 0)) for s, p in pubd.items()),
                     "_w": b["w"], "_ch": ch})
    fs = [{"slot": ts(s), "kwh": load[s]} for s in range(S)]

    def dump(name, obj):
        with open(os.path.join(out, name), "w") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")

    def strip(r):
        return {k: v for k, v in r.items() if not k.startswith("_")}

    def group(sel):
        sl = [0] * S
        for r in sel:
            for s, k in r["_ch"]:
                sl[s] += k
        return {"buses": len(sel), "energy_kwh": sum(r["delivered_kwh"] for r in sel),
                "cost_cents": sum(r["_cost"] for r in sel), "unmet_kwh": sum(r["unmet_kwh"] for r in sel),
                "slots": [{"slot": ts(s), "kwh": sl[s], "feeder_kwh": load[s]} for s in range(S)]}

    dump("policy_audit.json", {"plan_date": pd, "buses": [strip(r) for r in rows]})
    for d in DEPOTS:
        dump("region_%s.json" % d, dict({"depot": d}, **group([r for r in rows if r["depot"] == d])))
    for c in ("commercial", "public"):
        sel = [r for r in rows if r["class"] == c]
        dump("segment_%s.json" % c, dict({"class": c}, **group(sel)))
    dump("summary.json", {"plan_date": pd,
                          "weighted_unmet_kwh": sum(r["_w"] * r["unmet_kwh"] for r in rows),
                          "energy_cost_cents": sum(r["_cost"] for r in rows),
                          "moved_kwh": sum(r["_moved"] for r in rows),
                          "feeder_peak_kwh": max(load),
                          "feeder_kwh_by_slot": fs,
                          "buses_planned": len(rows),
                          "buses_short": sum(1 for r in rows if r["unmet_kwh"] > 0),
                          "buses_changed": sum(1 for r in rows if r["changed"]),
                          "records_rejected": len(rej)})
    dump("data_quality.json", {"plan_date": pd, "rejected": sorted(rej, key=lambda r: (r["file"], r["line"]))})


if __name__ == "__main__":
    inst, rej, pd, ts = load(sys.argv[1])
    sv = sys.argv[3] if len(sys.argv) > 3 else "ref"
    x = core.SOLVERS[sv](inst)
    write(inst, x, rej, pd, ts, sys.argv[2])
