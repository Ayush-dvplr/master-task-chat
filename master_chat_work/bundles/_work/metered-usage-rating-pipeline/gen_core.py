# ---- seeded month generator (builds one month of collector extracts) ----
import calendar as _gen_cal
import datetime as _gen_dt
import random as _gen_random
from fractions import Fraction as _GF

GEN_REGIONS = ("central", "east", "north", "south", "west")
GEN_SEGMENTS = ("consumer", "smb", "corporate", "enterprise")
GEN_SEG_WEIGHTS = (30, 30, 25, 15)
GEN_PRODUCTS = ("CMP", "STO", "EGR", "SUP")
GEN_UNIT = {"CMP": "hour", "STO": "gb_day", "EGR": "gb", "SUP": "minute"}
GEN_NAMES = {
    "CMP": {"central": ("compute_hours", "vm_hours"), "east": ("vm-hours", "compute-hrs"),
            "north": ("cmp", "compute"), "south": ("COMPUTE", "VMHOURS"), "west": ("compute", "compute.hours")},
    "STO": {"central": ("storage_gb_days", "disk_gb_days"), "east": ("storage-gbd", "volume-gbd"),
            "north": ("sto", "storage"), "south": ("STORAGE", "DISKGBD"), "west": ("storage", "storage.gbd")},
    "EGR": {"central": ("egress_gb", "transfer_out_gb"), "east": ("egress-gb", "net-out-gb"),
            "north": ("egr", "egress"), "south": ("EGRESS", "NETOUT"), "west": ("egress", "egress.gb")},
    "SUP": {"central": ("support_minutes", "support_time"), "east": ("support-min", "helpdesk-min"),
            "north": ("sup", "support"), "south": ("SUPPORT", "HELPDESK"), "west": ("support", "support.min")},
}
GEN_JUNK_PRODUCTS = ("gpu-hours", "backup", "GPU", "snapshots", "dns.queries", "ipv4")
GEN_RATE_RANGE = {"CMP": (300, 900), "STO": (10, 50), "EGR": (500, 1200), "SUP": (4000, 12000)}
GEN_OFFSETS = (330, -240, 60, 540, -420, 0)
GEN_SITES = ("São Paulo", "Zürich", "Malmö", "Kraków", "Göteborg", "Besançon", "Reykjavík",
             "Århus", "Düsseldorf", "A Coruña", "Montréal", "Bogotá")
GEN_BAD_TEXT_UNITS = ("12.5", "n/a", "", "twelve", "3e2", "-4", "7.0")
GEN_NORTH_DECOYS = ("true", "false", "12.5", "null", '"12.0"', "12.0", "1e2", '"n/a"')
GEN_PREFIX = {"central": "CEN", "east": "EAS", "north": "NOR", "south": "SOU", "west": "WES"}
GEN_FILES = {"central": "collector_central.csv", "east": "collector_east.tsv",
             "north": "collector_north.jsonl", "south": "collector_south.txt", "west": "collector_west.log"}
_GEN_UTC = _gen_dt.timezone.utc


def _gen_rate(rng, lo, hi, tie_capable):
    """A rate in units of 0.0001, never a multiple of 25; tie-capable rates end in 5; None after 1000 misses."""
    for _ in range(1000):
        r = rng.randint(lo, hi)
        if tie_capable:
            r = r - r % 10 + 5
        if r % 25 != 0 and r > 0 and (not tie_capable or r % 10 == 5):
            return r
    return None


def _gen_lower_rate(rng, prev, tie_capable):
    lo = max(1, int(prev * 0.80))
    hi = max(lo, int(prev * 0.92))
    for _ in range(200):
        r = _gen_rate(rng, lo, hi, tie_capable)
        if r is not None and r < prev:
            return r
    if prev <= 1:
        return None  # no lower rate exists; the caller draws the segment again
    r = _gen_rate(rng, 1, prev - 1, False)
    assert r is not None, prev
    return r


def _gen_units(rng, hidden):
    roll = rng.random()
    lo, hi = (1, 120) if roll < 0.6 else ((121, 500) if roll < 0.9 else (501, 999))
    if hidden and rng.random() < 0.08:
        u = rng.randint(lo, hi)
        u = u - u % 20 + 10
        return u if lo <= u <= hi else 10 + 20 * rng.randint(0, 49)
    while True:
        u = rng.randint(lo, hi)
        if hidden or u % 5 != 0:
            return u


def _gen_variant(rng, acct):
    digits = acct[2:]
    forms = ("ac" + digits, "AC-" + digits, "ac-" + digits[:3] + "-" + digits[3:],
             "Ac" + digits, "AC" + digits[:1] + "-" + digits[1:3] + "-" + digits[3:])
    return rng.choice(forms)


def _gen_small_groups(grng, normal, heavy, share, parent, parent_text, variant_share):
    """Groups of 2 to 4 accounts, each with a heavy member; returns the free lists left over."""
    free = list(normal)
    grng.shuffle(free)
    free_heavy = [a for a in free if a in heavy]
    free_light = [a for a in free if a not in heavy]
    grouped = 0
    while grouped < len(normal) * share // 100 and len(free_heavy) >= 2 and len(free_light) >= 2:
        size = grng.randint(2, 4)
        n_heavy = grng.randint(1, min(size, 2))
        members = [free_heavy.pop() for _ in range(n_heavy)] + [free_light.pop() for _ in range(size - n_heavy)]
        grng.shuffle(members)
        for i in range(1, size):
            up = members[i - 1] if grng.random() < 0.6 else members[grng.randrange(i)]
            parent[members[i]] = up
            parent_text[members[i]] = _gen_variant(grng, up) if grng.random() < variant_share else up
        grouped += size
    return free_heavy, free_light


def _gen_reseller_tree(trng, subs, customers, n_resellers, parent, parent_text):
    """One reseller over sub-resellers, each with customers; returns the accounts used, top first."""
    used = [subs.pop()]
    line = [used[0]]

    def attach(child, up):
        parent[child] = up
        parent_text[child] = _gen_variant(trng, up) if trng.random() < 0.5 else up
        used.append(child)

    for i in range(1, n_resellers):
        up = line[-1] if trng.random() < 0.9 else line[max(0, len(line) - trng.randint(2, 4))]
        node = subs.pop()
        attach(node, up)
        line.append(node)
        for _ in range(trng.randint(2, 4)):
            attach(customers.pop(), node)
        if trng.random() < 0.1:
            side = node
            for _ in range(trng.randint(2, 3)):
                nxt = subs.pop()
                attach(nxt, side)
                for _ in range(trng.randint(0, 2)):
                    attach(customers.pop(), nxt)
                side = nxt
    return used


def _gen_depths(order, parent):
    depth = {}
    for a in order:
        path, top = [], a
        while top not in depth and parent[top]:
            path.append(top)
            top = parent[top]
        d = depth.setdefault(top, 0)
        for member in reversed(path):
            d += 1
            depth[member] = d
    return depth


def _gen_ladder(seed, size, records, accounts, parent, names, m_start, m_end):
    """Rate card with size tiers per product whose starts follow the month's own tier counters."""
    top = {}
    for a in accounts:
        path, up = [], a
        while up not in top and parent[up]:
            path.append(up)
            up = parent[up]
        root = top.setdefault(up, up)
        for member in path:
            top[member] = root
    lines = sorted((rec["ts"], rec["acct"], rec["code"], rec["units"]) for region in GEN_REGIONS
                   for rec in records[region]
                   if not rec.get("utoken") and rec["acct"] in accounts and m_start <= rec["ts"] < m_end
                   and rec["pname"] == names[rec["code"]][region])
    used, seen = {}, {c: [] for c in GEN_PRODUCTS}
    for ts, acct, code, units in lines:
        key = (top[acct], code)
        seen[code].append(used.get(key, 0))
        used[key] = used.get(key, 0) + units
    lrng = _gen_random.Random(seed * 6271 + 53)
    card = {}
    for code in GEN_PRODUCTS:
        counts = sorted(seen[code])
        starts = [0]
        for k in range(1, size):
            starts.append(max(counts[k * len(counts) // size] + lrng.randint(1, 3), starts[-1] + 1))
        lo, hi = GEN_RATE_RANGE[code]
        tiers = []
        for tno, frm in enumerate(starts, 1):
            rates = {seg: _gen_rate(lrng, lo, hi, lrng.random() < 0.6) for seg in GEN_SEGMENTS}
            assert all(r is not None for r in rates.values())
            tiers.append([tno, frm, rates])
        assert len(tiers) == size and tiers[0][1] == 0, code
        card[code] = tiers
    return card


def gen_month(seed, month, rows_per_collector, n_accounts, hidden, compute, resellers=0, ladder=0):
    """Return dict file name -> bytes for one month. compute(files) -> documents (reference)."""
    rng = _gen_random.Random(seed)
    year, mon = int(month[:4]), int(month[5:7])
    m_start = _gen_dt.datetime(year, mon, 1, tzinfo=_GEN_UTC)
    days = _gen_cal.monthrange(year, mon)[1]
    m_end = m_start + _gen_dt.timedelta(days=days)
    month_secs = days * 86400

    pool_ids = rng.sample(range(10000, 100000 if resellers else 70000), n_accounts + 5)
    accounts = {}
    order = []
    for num in pool_ids:
        acct = "AC%05d" % num
        seg = rng.choices(GEN_SEGMENTS, GEN_SEG_WEIGHTS)[0]
        plan = "committed" if rng.random() < 0.6 else "payg"
        accounts[acct] = [seg, plan]
        order.append(acct)
    reserved = order[-5:]
    for acct in reserved:
        accounts[acct][1] = "committed"
    normal = order[:-5]
    heavy = set(rng.sample(normal, max(1, n_accounts * 12 // 100)))
    weights = [12 if a in heavy else 1 for a in normal]
    heavy_list = sorted(heavy)

    # billing groups: own rng so the rest of the month does not move
    grng = _gen_random.Random(seed * 7919 + 17)
    parent = {a: "" for a in order}
    parent_text = {a: "" for a in order}
    if hidden:
        free_heavy, free_light = _gen_small_groups(grng, normal, heavy, 10 if resellers else 25,
                                                   parent, parent_text, 0.5)
        if resellers:
            # one reseller tree over the accounts left: own rng so the groups above do not move
            trng = _gen_random.Random(seed * 104729 + 29)
            trng.shuffle(free_light)
            subs = free_light[:resellers * 3 // 2]
            customers = free_heavy + free_light[resellers * 3 // 2:]
            trng.shuffle(customers)
            assert len(subs) >= resellers * 3 // 2 and len(customers) >= resellers * 4, "reseller room"
            tree = _gen_reseller_tree(trng, subs, customers, resellers, parent, parent_text)
        depth = _gen_depths(order, parent)
        assert sum(1 for a in order if depth[a] >= 2) >= len(normal) // 40, "chains"
        if resellers:
            assert max(depth.values()) >= resellers * 3 // 4, "reseller depth"
            assert len(tree) >= resellers * 4, "reseller customers"
    else:
        _gen_small_groups(grng, normal, heavy, 5, parent, parent_text, 0.3)
        depth = _gen_depths(order, parent)
        grouped = [a for a in order if parent[a]]
        assert max(depth.values()) <= 3, "shipped depth"
        assert sum(1 for a in order if depth[a] >= 2) >= 10, "shipped levels"
        assert sum(1 for a in grouped if parent_text[a] != parent[a]) >= 10, "shipped spellings"
    cum_weights, run_total = [], 0
    for w in weights:
        run_total += w
        cum_weights.append(run_total)
    committed_accounts = {a for a in order if accounts[a][1] == "committed"}

    names = {}
    for code in GEN_PRODUCTS:
        names[code] = {r: (GEN_NAMES[code][r][rng.randint(0, 1)] if hidden else GEN_NAMES[code][r][0])
                       for r in GEN_REGIONS}

    card = {}
    for code in GEN_PRODUCTS:
        t2 = rng.randrange(300, 901, 50)
        t3 = rng.randrange(1000, 2001, 50)
        lo, hi = GEN_RATE_RANGE[code]
        tiers = [[1, 0, {}], [2, t2, {}], [3, t3, {}]]
        for seg in GEN_SEGMENTS:
            for _ in range(100):  # bounded; the first draw is kept whenever it yields three rates
                r1 = _gen_rate(rng, lo, hi, True)
                r2 = _gen_lower_rate(rng, r1, rng.random() < 0.6)
                r3 = _gen_lower_rate(rng, r2, rng.random() < 0.6) if r2 is not None else None
                if r3 is not None:
                    break
            for t, r in zip(tiers, (r1, r2, r3)):
                assert r is not None and 0 < r < 100000 and r % 25 != 0
                t[2][seg] = r
        card[code] = tiers

    def unknown_account():
        while True:
            a = "AC9%04d" % rng.randint(0, 9999)
            if a not in accounts:
                return a

    def other_product(region, code):
        if rng.random() < 0.5:
            others = [names[code][r] for r in GEN_REGIONS if names[code][r] != names[code][region]]
            cand = rng.choice(others)
        else:
            cand = rng.choice(GEN_JUNK_PRODUCTS)
        known = {names[c][region] for c in GEN_PRODUCTS}
        if cand in known or len(cand) > 12:
            cand = rng.choice(GEN_JUNK_PRODUCTS)
        return cand if cand not in known else "gpu-hours"

    records = {r: [] for r in GEN_REGIONS}
    for region in GEN_REGIONS:
        for _ in range(rows_per_collector):
            rec = {"acct": rng.choices(normal, cum_weights=cum_weights)[0], "code": rng.choice(GEN_PRODUCTS),
                   "units": _gen_units(rng, hidden), "offset": rng.choice(GEN_OFFSETS),
                   "site": rng.choice(GEN_SITES)}
            rec["ts"] = m_start + _gen_dt.timedelta(seconds=rng.randrange(month_secs))
            roll = rng.random()
            faults = []
            if roll < 0.010:
                faults = ["outside"]
            elif roll < 0.020:
                faults = ["account"]
            elif roll < 0.030:
                faults = ["product"]
            elif roll < 0.045:
                faults = ["units"]
            elif roll < 0.048:
                faults = rng.sample(["outside", "account", "product", "units"], 2)
            elif region == "north" and roll < 0.048 + (0.03 if hidden else 0.015):
                faults = ["quoted"]
            elif region == "west" and roll < 0.078:
                faults = ["edge"]
            for f in faults:
                if f == "outside":
                    if region == "west":
                        if rng.random() < 0.5:
                            rec["ts"] = m_start - _gen_dt.timedelta(seconds=rng.randrange(1, 3 * 3600))
                            rec["offset"] = rng.choice((330, 540, 60))
                        else:
                            rec["ts"] = m_end + _gen_dt.timedelta(seconds=rng.randrange(0, 3 * 3600))
                            rec["offset"] = rng.choice((-240, -420))
                    elif rng.random() < 0.5:
                        rec["ts"] = m_start - _gen_dt.timedelta(seconds=rng.randrange(1, 2 * 86400))
                    else:
                        rec["ts"] = m_end + _gen_dt.timedelta(seconds=rng.randrange(0, 2 * 86400))
                elif f == "account":
                    rec["acct"] = unknown_account()
                elif f == "product":
                    rec["pname"] = other_product(region, rec["code"])
                elif f == "edge":
                    if rng.random() < 0.5:
                        rec["ts"] = m_start + _gen_dt.timedelta(seconds=rng.randrange(0, 3 * 3600))
                        rec["offset"] = rng.choice((-240, -420))
                    else:
                        rec["ts"] = m_end - _gen_dt.timedelta(seconds=rng.randrange(1, 3 * 3600))
                        rec["offset"] = rng.choice((330, 540, 60))
                elif f == "quoted":
                    if hidden:
                        rec["acct"] = rng.choice(heavy_list)
                        rec["ts"] = m_start + _gen_dt.timedelta(seconds=rng.randrange(5 * 86400))
                        rec["units"] = rng.randint(300, 999)
                    rec["utoken"] = ('"%d"' if rng.random() < 0.6 else '" %d"') % rec["units"]
                else:
                    if region == "north":
                        rec["utoken"] = rng.choice(GEN_NORTH_DECOYS)
                    else:
                        rec["utoken"] = rng.choice(GEN_BAD_TEXT_UNITS)
            rec.setdefault("pname", names[rec["code"]][region])
            records[region].append(rec)
        records[region].sort(key=lambda x: x["ts"])
        if hidden:
            rows = records[region]
            for i in range(1, len(rows)):
                a, b = rows[i - 1], rows[i]
                if (rng.random() < 0.03 and not a.get("swap") and not a.get("utoken") and not b.get("utoken")
                        and m_start <= a["ts"] < m_end and m_start <= b["ts"] < m_end):
                    b["ts"] = a["ts"]
                    if region == "west":
                        b["offset"] = a["offset"]
                    b["swap"] = True

    if ladder:
        # long tier ladders: own rng so the rest of the month does not move
        card = _gen_ladder(seed, ladder, records, accounts, parent, names, m_start, m_end)

    changes = []
    usage_valid = [rec for r in GEN_REGIONS for rec in records[r]
                   if not rec.get("utoken") and rec["acct"] in accounts and m_start <= rec["ts"] < m_end]
    n_changes = n_accounts * 92 // 100
    while len(changes) < n_changes:
        roll = rng.random()
        if roll < 0.03:
            acct = unknown_account()
            ts = m_start + _gen_dt.timedelta(seconds=rng.randrange(month_secs))
        elif roll < 0.04:
            src = rng.choice(usage_valid)
            acct, ts = src["acct"], src["ts"]
        else:
            acct = rng.choices(normal, cum_weights=cum_weights)[0]
            ts = m_start + _gen_dt.timedelta(seconds=rng.randrange(month_secs))
        kind = rng.random()
        fields = {}
        if kind < 0.65:
            fields["plan"] = rng.choice(("committed", "payg"))
        if kind >= 0.40:
            fields["segment"] = rng.choice(GEN_SEGMENTS)
        changes.append([ts, acct, fields])
        if rng.random() < 0.02:
            other = {k: (("payg" if v == "committed" else "committed") if k == "plan"
                         else rng.choice([s for s in GEN_SEGMENTS if s != v])) for k, v in fields.items()}
            changes.append([ts, acct, other])
    changes.sort(key=lambda c: c[0])
    for c in changes:
        assert m_start <= c[0] < m_end
    if not hidden:
        # shipped month: a plan change only moves the plan after the account's last usage line
        last_use = {}
        for rec in usage_valid:
            last_use[rec["acct"]] = max(last_use.get(rec["acct"], rec["ts"]), rec["ts"])
        for ts, acct, fields in changes:
            if "plan" in fields and acct in last_use and ts <= last_use[acct]:
                fields["plan"] = accounts[acct][1]

    def render(pools, extra):
        files = {}
        counts = {}
        for region in GEN_REGIONS:
            rows = records[region] + extra.get(region, [])
            lines = []
            numbers = list(range(1, len(rows) + 1))
            for i, rec in enumerate(rows):
                if rec.get("swap"):
                    numbers[i - 1], numbers[i] = numbers[i], numbers[i - 1]
            for i, rec in enumerate(rows):
                rid = "%s-%06d" % (GEN_PREFIX[region], numbers[i])
                u = rec.get("utoken", str(rec["units"]))
                acct, pname = rec["acct"], rec["pname"]
                if not rec.get("utoken"):
                    assert 1 <= rec["units"] <= 999
                pad = rec.get("pad", "")
                if region == "central":
                    ts = rec["ts"].strftime("%Y-%m-%d %H:%M:%S")
                    lines.append(",".join((rid, ts, pad + acct, pname + pad, u)))
                elif region == "east":
                    epoch = int(rec["ts"].timestamp())
                    lines.append("\t".join((rid, str(epoch), acct + pad, pad + pname, pad + u)))
                elif region == "north":
                    ts = rec["ts"].strftime("%Y-%m-%dT%H:%M:%SZ")
                    lines.append('{"id": "%s", "at": "%s", "acct": "%s", "sku": "%s", "units": %s}'
                                 % (rid, ts, pad + acct, pname + pad, u))
                elif region == "south":
                    ts = rec["ts"].strftime("%Y%m%d%H%M%S")
                    line = rid.ljust(10) + ts + acct.ljust(10) + pname.ljust(12) + u.rjust(6) + rec["site"].ljust(20)
                    assert len(line) == 72
                    lines.append(line)
                else:
                    off = _gen_dt.timezone(_gen_dt.timedelta(minutes=rec["offset"]))
                    ts = rec["ts"].astimezone(off).isoformat()
                    lines.append("%s rec=%s acct=%s product=%s qty=%s" % (ts, rid, acct, pname, u))
            dups = []
            for j in range(len(lines) // 100):
                src = rng.randrange(len(lines) - 1)
                dups.append((rng.randrange(src + 1, len(lines) + 1), lines[src]))
            for pos, text in sorted(dups, reverse=True):
                lines.insert(pos, text)
            counts[region] = len(lines)
            if region == "central":
                lines.insert(0, "record_id,timestamp,account,product,units")
            elif region == "east":
                lines.insert(0, "id\tepoch\taccount\tproduct\tqty")
            enc = "latin-1" if region == "south" else "utf-8"
            files[GEN_FILES[region]] = ("\n".join(lines) + "\n").encode(enc)

        acc_lines = ["account_id,segment,plan,parent"]
        for acct in sorted(order, key=lambda a: rng_order[a]):
            acc_lines.append("%s,%s,%s,%s" % (acct, accounts[acct][0], accounts[acct][1], parent_text[acct]))
        files["accounts.csv"] = ("\n".join(acc_lines) + "\n").encode()

        pc = []
        for ts, acct, fields in changes:
            shown = acct
            if hidden and acct in accounts and variant_flag[id(fields)]:
                shown = variant_text[id(fields)]
            text = "%s change account=%s" % (ts.strftime("%Y-%m-%dT%H:%M:%SZ"), shown)
            for k in ("plan", "segment"):
                if k in fields:
                    text += " %s=%s" % (k, fields[k])
            pc.append(text)
        files["plan_changes.log"] = ("\n".join(pc) + "\n").encode()

        out = ['{', '  "currency": "USD",', '  "products": {']
        for ci, code in enumerate(GEN_PRODUCTS):
            out.append('    "%s": {' % code)
            out.append('      "tiers": [')
            for ti, (tno, frm, rates) in enumerate(card[code]):
                rtxt = ", ".join('"%s": %d.%04d' % (s, rates[s] // 10000, rates[s] % 10000) for s in GEN_SEGMENTS)
                out.append('        {"tier": %d, "from": %d, "rates": {%s}}%s'
                           % (tno, frm, rtxt, "," if ti < len(card[code]) - 1 else ""))
            out.append('      ]')
            out.append('    }' + ("," if ci < 3 else ""))
        out += ['  }', '}']
        files["rate_card.json"] = ("\n".join(out) + "\n").encode()

        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<commitments month="%s" currency="USD">' % month]
        for r in GEN_REGIONS:
            xml.append('  <pool region="%s" amount="%d.%02d" minimum="%d.%02d"/>'
                       % (r, pools[r] // 100, pools[r] % 100, minimums[r] // 100, minimums[r] % 100))
        xml.append('</commitments>')
        files["commitments.xml"] = ("\n".join(xml) + "\n").encode()

        ini = []
        for code in GEN_PRODUCTS:
            ini.append("[%s]" % code)
            ini.append("unit = %s" % GEN_UNIT[code])
            for r in GEN_REGIONS:
                ini.append("%s = %s" % (r, names[code][r]))
            ini.append("")
        files["products.ini"] = "\n".join(ini).encode()

        ctl = ['{', '  "month": "%s",' % month, '  "collectors": {']
        for i, r in enumerate(GEN_REGIONS):
            ctl.append('    "%s": {"file": "%s", "records": %d}%s'
                       % (r, GEN_FILES[r], counts[r], "," if i < 4 else ""))
        ctl += ['  }', '}']
        files["collector_controls.json"] = ("\n".join(ctl) + "\n").encode()
        return files

    rng_order = {a: rng.random() for a in order}
    variant_flag = {}
    variant_text = {}
    for ts, acct, fields in changes:
        variant_flag[id(fields)] = rng.random() < 0.6
        variant_text[id(fields)] = _gen_variant(rng, acct)
    for region in GEN_REGIONS:
        for rec in records[region]:
            if region in ("central", "east", "north") and rng.random() < 0.03:
                rec["pad"] = " " * rng.randint(1, 2)

    zero = {r: 0 for r in GEN_REGIONS}
    minimums = dict(zero)
    dup_state = rng.getstate()
    docs = compute(render(zero, {}))

    def counted_charges(docs, region):
        return [int(ln["charge"].replace(".", "")) for ln in docs["normalized.jsonl"]
                if ln["region"] == region and ln["account_id"] in committed_accounts]

    extra = {}
    roles = {}
    tie_k = {}
    if hidden:
        # credit roles: three regions whose pool lies between the summed charge of the lines that
        # hold 0.50 or more and the credit base, one region whose pool covers the base, one region
        # whose second-pass credits carry half-cent ties
        order_roles = ["sep", "sep", "sep", "full", "tie"]
        rng.shuffle(order_roles)
        roles = dict(zip(GEN_REGIONS, order_roles))
        for idx, region in enumerate(GEN_REGIONS):
            charges0 = counted_charges(docs, region)
            base0 = sum(charges0)
            acct = reserved[idx]
            seg = accounts[acct][0]
            rate = card["CMP"][0][2][seg]
            start = rng.randint(1, 999)
            k = rng.randint(1, 3)
            found = None
            for step in range(999):
                u = (start + step) % 999 + 1
                c = _gen_round(_GF(u * rate, 100))
                if roles[region] != "tie":
                    found = u
                    break
                pool = _gen_tie_pool(charges0 + [c], k)
                if pool is not None:
                    found = u
                    tie_k[region] = k
                    break
            assert found is not None, region
            ts = m_end - _gen_dt.timedelta(seconds=rng.randrange(3600 * 4, 3600 * 20))
            extra[region] = [{"acct": acct, "code": "CMP", "units": found, "offset": 0, "site": "Zürich",
                              "ts": ts, "pname": names["CMP"][region]}]
    rng.setstate(dup_state)
    docs = compute(render(zero, extra))
    pools = {}
    short = set()
    if hidden:
        short_roles = ["short", "short", "short", "cover", "cover"]
        rng.shuffle(short_roles)
        short = {r for r, s in zip(GEN_REGIONS, short_roles) if s == "short"}
    for region in GEN_REGIONS:
        base = int(docs["region_%s.json" % region]["credit_base"].replace(".", ""))
        charges = counted_charges(docs, region)
        assert base > 0 and base == sum(charges)
        if hidden:
            role = roles[region]
            if role == "tie":
                pool = _gen_tie_pool(charges, tie_k[region])
                assert pool is not None, region
            elif role == "sep":
                first, held, kept, second = _gen_floor(base - 1, charges, base)
                sub0 = base - kept
                assert sub0 >= 2, region
                pool = base - sub0 // 2
                first, held, kept, second = _gen_floor(pool, charges, base)
                assert 0 < kept <= pool < base, region
            else:
                pool = base + rng.randint(0, base // 10)
            if region in short:
                minimum = base + int(base * rng.uniform(0.30, 0.80))
                first, held, kept, second = _gen_floor(minimum - base, charges, base)
                assert 0 < kept < base, region
            else:
                minimum = int(base * rng.uniform(0.50, 0.95))
        else:
            pool = int(base * rng.uniform(0.20, 0.45))
            while _gen_has_tie(pool, charges, base):
                pool += 1
            assert 0 < pool * 2 < base
            minimum = int(base * rng.uniform(0.50, 0.90))
        pools[region] = pool
        minimums[region] = minimum
    rng.setstate(dup_state)
    files = render(pools, extra)
    if hidden:
        _gen_check_ties(compute(files), card, pools, committed_accounts, [r for r in GEN_REGIONS if roles[r] == "tie"])
    return files


def _gen_round(x):
    """Fraction of cents -> int cents, half-even."""
    n = x.numerator // x.denominator
    rest = x - n
    if rest > _GF(1, 2) or (rest == _GF(1, 2) and n % 2 == 1):
        n += 1
    return n


def _gen_floor(total, charges, denom):
    """First and second pass of a 0.50-floor share of total cents over charges (cents)."""
    first = [_GF(total * c, denom) for c in charges]
    held = [_gen_round(x) >= 50 for x in first]
    kept = sum(c for c, h in zip(charges, held) if h)
    second = [_GF(total * c, kept) if h else None for c, h in zip(charges, held)]
    return first, held, kept, second


def _gen_has_tie(pool, charges, base):
    first, held, kept, second = _gen_floor(pool, charges, base)
    return any(x is not None and x % 1 == _GF(1, 2) for x in first + second)


def _gen_tie_pool(charges, k):
    """Pool = k/8 of the summed charge of the lines that hold 0.50 or more, consistent with that set."""
    base = sum(charges)
    kept = base
    for _ in range(8):
        pool = k * kept // 8
        first, held, new_kept, second = _gen_floor(pool, charges, base)
        if new_kept == kept:
            return pool if kept % 8 == 0 and 0 < pool * 2 < base else None
        kept = new_kept
    return None


def _gen_check_ties(docs, card, pools, committed_accounts, tie_regions):
    """Hidden months must hold at least 3 rounding ties of each kind per region, segment and product."""
    groups = {}
    for ln in docs["normalized.jsonl"]:
        rate = int(ln["unit_rate"].replace(".", ""))
        exact = ln["units"] * rate
        if exact % 100 == 50 and (exact // 100) % 2 == 0:
            for key in ("region", "segment", "product"):
                groups[(key, ln[key])] = groups.get((key, ln[key]), 0) + 1
    for key, values in (("region", GEN_REGIONS), ("segment", GEN_SEGMENTS), ("product", GEN_PRODUCTS)):
        for v in values:
            assert groups.get((key, v), 0) >= 3, (key, v)
    for region in tie_regions:
        charges = [int(ln["charge"].replace(".", "")) for ln in docs["normalized.jsonl"]
                   if ln["region"] == region and ln["account_id"] in committed_accounts]
        first, held, kept, second = _gen_floor(pools[region], charges, sum(charges))
        ties = sum(1 for x in second if x is not None and x % 1 == _GF(1, 2) and int(x) % 2 == 0)
        assert ties >= 3, region
