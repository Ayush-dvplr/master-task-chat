

def plan_rows(data):
    day = ini(data / "grid.ini")["plan"]["plan_date"]
    rows = (data / "roster.csv").read_text(encoding="utf-8").splitlines()
    return day, rows


def check_roster_depot():
    before = {b["bus_id"]: b for b in load(OUT, "policy_audit.json")["buses"]}
    home = {r["vehicle_id"]: r["home_depot"] for r in csv.DictReader((DATA / "fleet_register.csv").open(encoding="utf-8"))}
    data = copy_data("roster_depot")
    day, rows = plan_rows(data)
    names = [d["depot"] for d in json.loads((data / "depots.json").read_text(encoding="utf-8"))["depots"]]
    target = sorted(before)[0]
    for i, line in enumerate(rows[1:], 1):
        f = line.split(",")
        if f[0] == day and f[1] == target:
            f[2] = next(n for n in names if n != home[target])
            rows[i] = ",".join(f)
            moved_to = f[2]
            break
    (data / "roster.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = WORK / "roster_depot" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("roster_depot", res.stderr)
    got = {b["bus_id"]: b for b in load(out, "policy_audit.json")["buses"]}[target]["depot"]
    if got != moved_to:
        fail("roster_depot", "%s roster %s audit %s" % (target, moved_to, got))
    report("roster_depot", "%s home %s, roster row %s: audit depot %s" % (target, home[target], moved_to, got))


def check_tariff_version_change():
    cost = load(OUT, "summary.json")["energy_cost_cents"]
    day = ini(DATA / "grid.ini")["plan"]["plan_date"]
    nxt = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
    data = copy_data("tariff_version")
    tree = ET.parse(data / "tariff.xml")
    root = tree.getroot()
    current = next(v for v in root.iter("version") if v.get("valid_from") <= day <= v.get("valid_to"))
    later = ET.fromstring(ET.tostring(current))
    later.set("valid_from", nxt)
    current.set("valid_to", day)
    for band in later.iter("band"):
        band.set("cents_per_kwh", str(2 * int(band.get("cents_per_kwh"))))
    root.append(later)
    tree.write(data / "tariff.xml", encoding="UTF-8", xml_declaration=True)
    out = WORK / "tariff_version" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("tariff_version_change", res.stderr)
    got = load(out, "summary.json")["energy_cost_cents"]
    if got != cost:
        fail("tariff_version_change", "energy cost %d -> %d" % (cost, got))
    report("tariff_version_change", "version in force on %s ends that day, prices double from %s: energy_cost_cents %d"
           % (day, nxt, got))


def check_overlapping_outage():
    depots = json.loads((DATA / "depots.json").read_text(encoding="utf-8"))
    unit = depots["cabinet_kwh_per_slot"]
    notice = (DATA / "disruption_notice.md").read_text(encoding="utf-8").splitlines()
    line = next(l for l in notice if " cabinets out of service from " in l)
    parts = line.split()
    name, n, start, end = parts[1].rstrip(":"), int(parts[2]), parts[-3], parts[-1]
    cab = next(d["cabinets"] for d in depots["depots"] if d["depot"] == name)
    extra = cab - n - 1
    data = copy_data("overlap")
    lines = (data / "disruption_notice.md").read_text(encoding="utf-8").splitlines()
    k = lines.index(line)
    lines.insert(k + 1, "- %s: %d cabinets out of service from %s to %s" % (name, extra, start, end))
    (data / "disruption_notice.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = WORK / "overlap" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("overlapping_outage", res.stderr)
    slots = [s for s in load(out, "region_%s.json" % name)["slots"] if start <= s["slot"] < end]
    peak = max(s["kwh"] for s in slots)
    if peak > unit:
        fail("overlapping_outage", "%s peak %d above one cabinet %d" % (name, peak, unit))
    report("overlapping_outage", "%s %d + %d of %d cabinets out from %s to %s: slot %s kwh %d (limit %d)"
           % (name, n, extra, cab, start, end, slots[0]["slot"], slots[0]["kwh"], unit))


def check_offgrid_arrival():
    before = {b["bus_id"]: b for b in load(OUT, "policy_audit.json")["buses"]}
    data = copy_data("offgrid")
    day, rows = plan_rows(data)
    target = next(b for b in sorted(before) if before[b]["charges"])
    for i, line in enumerate(rows[1:], 1):
        f = line.split(",")
        if f[0] == day and f[1] == target:
            arrive = (datetime.fromisoformat(f[3]) + timedelta(minutes=7)).strftime("%Y-%m-%dT%H:%M")
            f[3] = arrive
            rows[i] = ",".join(f)
            break
    (data / "roster.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = WORK / "offgrid" / "out"
    res = run(data, out)
    if res.returncode != 0:
        fail("offgrid_arrival", res.stderr)
    charges = {b["bus_id"]: b for b in load(out, "policy_audit.json")["buses"]}[target]["charges"]
    if any(c["slot"] < arrive for c in charges):
        fail("offgrid_arrival", "%s arrives %s charged %s" % (target, arrive, charges[0]["slot"]))
    report("offgrid_arrival", "%s arrives %s: first charge %s, %d charged slots"
           % (target, arrive, charges[0]["slot"] if charges else "none", len(charges)))
