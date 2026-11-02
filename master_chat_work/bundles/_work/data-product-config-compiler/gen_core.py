from __future__ import annotations

import datetime as _gdt
import json as _gjson
import random as _grandom

GEN_SCHEMA = {
    "weight": {"type": "integer", "min": 1, "max": 100},
    "retention_days": {"type": "integer", "min": 1, "max": 3650},
    "replicas": {"type": "integer", "min": 1, "max": 7},
    "partitions": {"type": "integer", "min": 1, "max": 256},
    "freshness_sla_min": {"type": "integer", "min": 5, "max": 1440},
    "pii_scan": {"type": "boolean"},
    "alerts_enabled": {"type": "boolean"},
    "encryption": {"type": "enum", "values": ["none", "kms", "hsm"]},
    "notify": {"type": "list"},
    "tags": {"type": "list"},
    "cost_center": {"type": "string", "optional": True},
    "quota_cap": {"type": "integer", "min": 1, "max": 100000, "optional": True},
}
_GFULL = str.maketrans("0123456789", "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19")
GEN_TEAMS = ["ingest", "finance", "growth", "risk", "search", "ml-platform", "billing", "identity", "catalog",
             "logistics", "support", "ads", "security", "media"]
GEN_LABELS = ["pii", "streaming", "batch", "finance", "realtime", "archive", "ml", "shared"]
GEN_SURNAMES = ["morgan", "kline", "okafor", "lindqvist", "tanaka", "reyes", "novak", "haddad", "fischer", "osei",
                "moreau", "kowalski", "silva", "nguyen", "brennan", "larsen", "duarte", "ivanova", "achebe", "park",
                "rossi", "weber", "costa", "mendez", "sato", "kaur", "bauer", "dubois", "jansen", "petrov", "hughes",
                "varga", "nakamura", "oduya", "berg", "castillo", "yilmaz", "sorensen", "abara", "quinn", "ferreira",
                "holm", "ito", "marsh", "rahman", "steiner", "vidal", "wong", "zeller", "amari"]
GEN_CHANNELS = ["data-oncall", "ops", "sre-pager", "platform-leads", "finance-oncall", "privacy-desk", "ml-oncall",
                "search-oncall", "ingest-oncall", "audit-feed"]
GEN_TAGS = ["tier-1", "batch", "streaming", "gdpr", "sox", "feature-store", "experimental", "legacy", "hot", "cold"]
GEN_CENTERS = ["CC-1100", "CC-2040", "CC-3310", "CC-4475", "CC-5120", "CC-6600", "CC-7015", "CC-8890"]


def _gday(text):
    return _gdt.date.fromisoformat(text)


def _gstr(day):
    return day.isoformat()


def _gcheck(key, value):
    spec = GEN_SCHEMA[key]
    if spec["type"] == "integer":
        assert isinstance(value, int) and not isinstance(value, bool) and spec["min"] <= value <= spec["max"], (key, value)
    elif spec["type"] == "boolean":
        assert isinstance(value, bool), (key, value)
    elif spec["type"] == "enum":
        assert value in spec["values"], (key, value)
    elif spec["type"] == "list":
        assert isinstance(value, list) and all(isinstance(v, str) and v == v.strip() and "," not in v for v in value)
    else:
        assert isinstance(value, str) and value == value.strip() and value, (key, value)
    return value


def _gvalue(rng, key):
    pools = {
        "weight": lambda: rng.choice([1, 2, 2, 3, 3, 4, 5, 6, 8]),
        "retention_days": lambda: rng.choice([7, 14, 30, 45, 60, 90, 180, 365, 400, 730, 1095]),
        "replicas": lambda: rng.randint(1, 5),
        "partitions": lambda: rng.choice([1, 2, 4, 8, 12, 16, 24, 32, 64, 128]),
        "freshness_sla_min": lambda: rng.choice([5, 10, 15, 30, 45, 60, 120, 240, 720, 1440]),
        "pii_scan": lambda: rng.random() < 0.5,
        "alerts_enabled": lambda: rng.random() < 0.6,
        "encryption": lambda: rng.choice(["none", "kms", "kms", "hsm"]),
        "notify": lambda: rng.sample(GEN_CHANNELS, rng.randint(0, 3)),
        "tags": lambda: rng.sample(GEN_TAGS, rng.randint(0, 3)),
        "cost_center": lambda: rng.choice(GEN_CENTERS),
    }
    return _gcheck(key, pools[key]())


def _gtext(rng, key, value, quote_rate=0.25):
    kind = GEN_SCHEMA[key]["type"]
    if kind == "boolean":
        text = rng.choice(["true", "True", "TRUE"]) if value else rng.choice(["false", "False", "FALSE"])
    elif kind == "list":
        text = rng.choice([", ", ",", " , "]).join(value)
    else:
        text = str(value)
    if rng.random() < quote_rate or (kind == "list" and text == "" and rng.random() < 0.5):
        text = '"' + text + '"'
    return text


def _gmangle(rng, pid):
    digits = pid[2:]
    cut = rng.randint(1, len(digits) - 1)
    forms = [pid.lower(), "dp-" + digits, "Dp-" + digits, "DP-" + digits[:cut] + "-" + digits[cut:],
             "dP" + digits[:cut] + "-" + digits[cut:], "dp-" + digits[:cut] + "-" + digits[cut:]]
    return rng.choice(forms)


def _godd(rng, key, hidden):
    if GEN_SCHEMA[key]["type"] == "boolean":
        return rng.choice(["yes", "no", "on", "off", "Y", "1", "0"])
    value = str(_gvalue(rng, key))
    forms = ["+" + value, '"+' + value + '"']
    if hidden:
        forms += [value.translate(_GFULL)] * 3
    return rng.choice(forms)


def _gstamp(rng, day):
    return f"{_gstr(day)}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}Z"


def gen_corpus(seed, n_products, hidden, compile_date, release, ref_compute=None, shift_days=45):
    rng = _grandom.Random(seed)
    day = _gday(compile_date)
    later = day + _gdt.timedelta(days=shift_days)
    start_span = day - _gdt.timedelta(days=6 * 365)

    # owners.csv: non-overlapping assignments per owner
    names, seen = [], set()
    while len(names) < int(n_products * 2.4):
        name = f"{rng.choice('abcdefghijklmnoprstvwz')}.{rng.choice(GEN_SURNAMES)}"
        if name in seen:
            name = f"{name}{rng.randint(2, 9)}"
        if name not in seen:
            seen.add(name)
            names.append(name)
    rows, team_at = [], {}
    for name in names:
        cursor = start_span + _gdt.timedelta(days=rng.randint(0, 4 * 365))
        team = rng.choice(GEN_TEAMS)
        count = rng.choice([1, 2, 2, 3, 3, 4])
        spans = []
        for i in range(count):
            begin = cursor
            if i == count - 1 and rng.random() < 0.65:
                end = None
            else:
                end = begin + _gdt.timedelta(days=rng.randint(60, 700))
            spans.append((name, team, begin, end))
            if end is None:
                break
            cursor = end + _gdt.timedelta(days=rng.randint(1, 90))
            team = rng.choice([t for t in GEN_TEAMS if t != team]) if rng.random() < 0.7 else team
        for owner, t, begin, end in spans:
            rows.append((owner, t, begin, end))
            for probe in (day, later):
                if begin <= probe and (end is None or end >= probe):
                    team_at[(owner, probe)] = t
    live = [n for n in names if (n, day) in team_at]
    dead = [n for n in names if (n, day) not in team_at]
    assert len(live) > n_products and len(dead) > 20

    # products
    pids = sorted(rng.sample(range(10000, 99999), n_products + 400))
    legacy = ["DP%05d" % p for p in pids[n_products:]]
    catalog = sorted("DP%05d" % p for p in rng.sample(pids[:n_products], n_products))
    products = {}
    for pid in catalog:
        owner = rng.choice(dead) if rng.random() < 0.07 else rng.choice(live)
        tier = rng.choices(["bronze", "silver", "gold"], [5, 3, 2])[0]
        labels = rng.sample(GEN_LABELS, rng.choice([0, 1, 1, 2, 2, 3]))
        lines = []
        for key in rng.sample(["retention_days", "partitions", "freshness_sla_min", "encryption", "tags",
                               "cost_center", "notify", "replicas"], rng.choice([0, 1, 1, 2, 3])):
            lines.append((key, _gtext(rng, key, _gvalue(rng, key))))
        products[pid] = {"owner": owner, "tier": tier, "labels": labels, "lines": lines}

    # teams with weight selectors (used to place log-retired owners in the hidden tier)
    weight_teams = rng.sample(GEN_TEAMS, 8)

    # retirements
    shuffled = catalog[:]
    rng.shuffle(shuffled)
    n_ret = max(8, n_products * 7 // 100)
    retired_before = shuffled[:n_ret]
    retired_between = shuffled[n_ret:n_ret + max(4, n_products * 3 // 100)]
    retired_after = shuffled[n_ret + len(retired_between):n_ret + len(retired_between) + max(3, n_products // 50)]
    retired_owner_events = []
    if hidden:
        pool = [n for n in live if team_at[(n, day)] in weight_teams and (n, later) in team_at]
        chosen = rng.sample(pool, 10)
        candidates = [pid for pid in shuffled[n_ret + 60:] if products[pid]["owner"] in live]
        for i, owner in enumerate(chosen):
            for pid in candidates[3 * i:3 * i + rng.choice([2, 3])]:
                products[pid]["owner"] = owner
            when = day - _gdt.timedelta(days=rng.randint(0, 200))
            retired_owner_events.append((when, owner))
        pool2 = [n for n in live if n not in chosen and (n, later) in team_at]
        for owner in rng.sample(pool2, 3):
            pid = rng.choice(candidates[40:])
            products[pid]["owner"] = owner
            retired_owner_events.append((day + _gdt.timedelta(days=rng.randint(1, shift_days)), owner))
        for owner in rng.sample([n for n in names if n not in chosen], 6):
            retired_owner_events.append((day - _gdt.timedelta(days=rng.randint(0, 400)), owner))
        # owners whose only assignment starts on the compile date itself
        for i in range(3):
            fresh = f"{rng.choice('abcdefghijklmnoprstvwz')}.{rng.choice(GEN_SURNAMES)}{11 + i}"
            fresh_team = rng.choice(weight_teams)
            rows.append((fresh, fresh_team, day, None))
            team_at[(fresh, day)] = team_at[(fresh, later)] = fresh_team
            for pid in candidates[32 + 2 * i:34 + 2 * i]:
                products[pid]["owner"] = fresh

    # text values that do not read as their key's type (separate stream, so the rest of the corpus is unchanged)
    prng = _grandom.Random(seed * 7 + 3)
    odd_rate = 0.08 if hidden else 0.03
    for pid in catalog:
        lines = products[pid]["lines"]
        for i, (key, text) in enumerate(lines):
            if GEN_SCHEMA[key]["type"] == "integer" and prng.random() < odd_rate:
                lines[i] = (key, _godd(prng, key, hidden))
        if prng.random() < odd_rate / 2:
            lines.append((prng.choice(["alerts_enabled", "pii_scan"]), _godd(prng, "pii_scan", hidden)))

    # owners with a second, later-started assignment that covers the compile date (hidden tier only)
    planted_rows = []
    if hidden:
        plain = [t for t in GEN_TEAMS if t not in weight_teams]
        gone = {o for _, o in retired_owner_events}
        owning = {products[pid]["owner"] for pid in catalog if pid not in retired_before}
        def covering(name):
            return next(r for r in rows if r[0] == name and r[2] <= day and (r[3] is None or r[3] >= day))

        pool3 = sorted(n for n in live if n in owning and n not in gone and team_at[(n, day)] in plain
                       and (day - covering(n)[2]).days >= 2)
        for i, owner in enumerate(prng.sample(pool3, 14)):
            old = covering(owner)
            starts = {r[2] for r in rows if r[0] == owner}
            begin = old[2] + _gdt.timedelta(days=prng.randint(1, max(1, (day - old[2]).days)))
            while begin in starts:
                begin -= _gdt.timedelta(days=1)
            assert old[2] < begin <= day
            pick = prng.random()
            if pick < 0.4:
                end = None
            elif pick < 0.75:
                end = day + _gdt.timedelta(days=prng.randint(1, shift_days - 1))
            else:
                end = day + _gdt.timedelta(days=prng.randint(shift_days, 400))
            new = (owner, prng.choice([t for t in plain if t != old[1]]), begin, end)
            rows.append(new)
            planted_rows.append((old, new, i % 2 == 0))

    def log_id(pid):
        return _gmangle(rng, pid) if hidden and rng.random() < 0.6 else pid

    events = []
    for pid in retired_before:
        events.append((_gstamp(rng, day - _gdt.timedelta(days=rng.randint(0, 700))), f"RETIRE product={log_id(pid)}"))
    if retired_before:
        events.append((_gstamp(rng, day), f"RETIRE product={log_id(retired_before[0])}"))
    if hidden:
        # a second, later event for products already retired: the earliest event counts
        for pid in retired_before[1:7]:
            events.append((_gstamp(rng, day + _gdt.timedelta(days=rng.randint(1, shift_days))), f"RETIRE product={log_id(pid)}"))
    for pid in retired_between:
        events.append((_gstamp(rng, day + _gdt.timedelta(days=rng.randint(1, shift_days))), f"RETIRE product={log_id(pid)}"))
    for pid in retired_after:
        events.append((_gstamp(rng, later + _gdt.timedelta(days=rng.randint(1, 200))), f"RETIRE product={log_id(pid)}"))
    for when, owner in retired_owner_events:
        events.append((_gstamp(rng, when), f"RETIRE owner={owner}"))
    n_noise = max(0, int(n_products * 5.6) - len(events))
    for _ in range(n_noise):
        when = day - _gdt.timedelta(days=rng.randint(-120, 1100))
        r = rng.random()
        if r < 0.38:
            line = f"RETIRE product={log_id(rng.choice(legacy))}"
        elif r < 0.72:
            line = f"NOTICE product={rng.choice(catalog)} note={rng.choice(['review-scheduled', 'owner-ping', 'cost-review', 'schema-drift'])}"
        elif r < 0.86:
            line = f"NOTICE owner={rng.choice(names)} note={rng.choice(['handover', 'leave', 'reorg'])}"
        else:
            line = f"INFO {rng.choice(['rotation=weekly', 'sync=ok', 'catalog=refreshed', 'audit=passed'])}"
        events.append((_gstamp(rng, when), line))
    rng.shuffle(events)
    ticket = iter(range(rng.randint(1000, 5000), 10 ** 7))
    log_text = "".join(f"{ts} {body} ticket=DEP-{next(ticket)}\n" for ts, body in events)

    # selectors.rules
    rules = [("tier", "gold", "replicas", 3), ("tier", "silver", "replicas", 2), ("tier", "gold", "partitions", 32),
             ("tier", "bronze", "freshness_sla_min", 240), ("label", "pii", "pii_scan", True),
             ("label", "streaming", "freshness_sla_min", 15), ("label", "archive", "retention_days", 1825),
             ("label", "finance", "encryption", "hsm"), ("label", "realtime", "alerts_enabled", True),
             ("label", "ml", "tags", ["ml", "feature-store"]), ("label", "shared", "notify", []),
             ("label", "batch", "partitions", 4)]
    for t in weight_teams:
        rules.append(("team", t, "weight", rng.choice([3, 4, 5, 6, 7])))
    for t in rng.sample(GEN_TEAMS, 6):
        rules.append(("team", t, rng.choice(["retention_days", "replicas", "freshness_sla_min"]), None))
    for t in rng.sample(GEN_TEAMS, 4):
        rules.append(("team", t, "notify", rng.sample(GEN_CHANNELS, 2)))
    rng.shuffle(rules)
    rule_lines = ["# selector rules: applied in file order, later rules win", ""]
    for field, name, key, value in rules:
        if value is None:
            value = _gvalue(rng, key)
        rule_lines.append(f"match {field}:{name} set {key} {_gtext(rng, key, _gcheck(key, value))}")
        if rng.random() < 0.25:
            rule_lines.append("")
    rule_lines.append("")

    # team_overrides.json
    teams = {}
    for t in GEN_TEAMS:
        entries = {}
        for key in rng.sample(["retention_days", "notify", "freshness_sla_min", "alerts_enabled", "cost_center",
                               "replicas", "tags"], rng.randint(2, 4)):
            entries[key] = _gvalue(rng, key)
        teams[t] = entries
    bad_teams = rng.sample(GEN_TEAMS, 8)
    teams[bad_teams[0]]["weight"] = str(rng.choice([4, 5, 6]))
    teams[bad_teams[1]]["retention_days"] = str(rng.choice([45, 120]))
    teams[bad_teams[2]]["cost_center"] = None
    teams[bad_teams[3]]["notify"] = []
    teams[bad_teams[4]]["replicas"] = 9
    teams[bad_teams[5]]["retention"] = 30
    teams[bad_teams[6]]["partitions"] = None
    teams[bad_teams[7]]["weight"] = True
    if hidden:
        teams[weight_teams[0]]["alerts_enabled"] = "false"
        teams[weight_teams[1]]["weight"] = str(rng.choice([2, 7]))
    team_text = _gjson.dumps(teams, indent=2) + "\n"

    # product_overrides.jsonl
    keys = ["retention_days", "freshness_sla_min", "partitions", "notify", "tags", "encryption", "cost_center",
            "replicas", "alerts_enabled", "pii_scan", "weight"]
    key_w = [20, 15, 12, 10, 10, 8, 8, 6, 4, 3, 4]
    records, taken = [], set()

    def pid_form(pid):
        return _gmangle(rng, pid) if rng.random() < 0.3 else pid

    for _ in range(n_products * 15):
        pid = rng.choice(catalog)
        key = rng.choices(keys, key_w)[0]
        if key == "cost_center" and rng.random() < 0.25:
            value = None
        elif key in ("notify", "tags") and rng.random() < 0.15:
            value = []
        else:
            value = _gvalue(rng, key)
        records.append([pid_form(pid), key, value])
        taken.add((pid, key))
    active_ish = [pid for pid in catalog if products[pid]["owner"] in live and pid not in retired_before
                  and not any(products[pid]["owner"] == o for _, o in retired_owner_events)]
    planted = []

    def fresh_pair(key):
        for _ in range(4000):
            pid = rng.choice(active_ish)
            if (pid, key) not in taken:
                taken.add((pid, key))
                return pid
        free = [pid for pid in active_ish if (pid, key) not in taken] or active_ish
        taken.add((free[0], key))
        return free[0]

    scale = 1 if not hidden else 1
    for key, maker, count in [
        ("weight", lambda: str(rng.choice([7, 8, 9, 12])), 5 * scale),
        ("replicas", lambda: str(rng.choice([4, 5])), 3),
        ("retention_days", lambda: str(rng.choice([21, 500, 1000])), 6),
        ("partitions", lambda: str(rng.choice([48, 96])), 4),
        ("freshness_sla_min", lambda: str(rng.choice([25, 90])), 4),
        ("alerts_enabled", lambda: rng.choice(["true", "false"]), 4),
        ("pii_scan", lambda: rng.choice(["true", "false"]), 4),
        ("weight", lambda: True, 2), ("partitions", lambda: False, 2),
        ("retention_days", lambda: 30.0, 3), ("partitions", lambda: 1e2, 2),
        ("replicas", lambda: None, 2), ("encryption", lambda: None, 2),
        ("replicas", lambda: rng.choice([0, 8, 12]), 4), ("freshness_sla_min", lambda: rng.choice([2, 3000]), 4),
        ("encryption", lambda: rng.choice(["aes", "KMS"]), 4),
    ]:
        for _ in range(count):
            planted.append([pid_form(fresh_pair(key)), key, maker()])
    for _ in range(8):
        planted.append([pid_form(rng.choice(catalog)), rng.choice(["retention", "replica", "sla_minutes"]), 30])
    for _ in range(12):
        planted.append([pid_form(rng.choice(legacy)), rng.choice(keys), 3])
    seqs = rng.sample(range(100, n_products * 60), len(records) + len(planted))
    normal_seqs = sorted(seqs)[:len(records)]
    top_seqs = sorted(seqs)[len(records):]
    rng.shuffle(normal_seqs)
    lines = []
    for (form, key, value), seq in zip(records, normal_seqs):
        lines.append({"seq": seq, "product": form, "key": key, "value": value, "ticket": f"CHG-{seq * 7 % 99991:05d}"})
    for (form, key, value), seq in zip(planted, top_seqs):
        lines.append({"seq": seq, "product": form, "key": key, "value": value, "ticket": f"CHG-{seq * 7 % 99991:05d}"})
    rng.shuffle(lines)
    over_text = "".join(_gjson.dumps(o) + "\n" for o in lines)

    # products.ini
    ini = ["# data product catalog", ""]
    for pid in catalog:
        p = products[pid]
        head = _gmangle(rng, pid) if hidden and rng.random() < 0.2 else pid
        ini.append(f"[product {head}]")
        ini.append(f"owner = {p['owner']}")
        ini.append(f"tier = {p['tier']}")
        ini.append("labels = " + ", ".join(p["labels"]))
        for key, text in p["lines"]:
            ini.append(f"{key} = {text}")
        ini.append("")

    base = ["# base layer: a value for every required key", "weight: 2", "retention_days: 90", "replicas: 2",
            "partitions: \"8\"", "freshness_sla_min: 60", "pii_scan: false", "alerts_enabled: True",
            "encryption: kms", "notify: \"data-oncall\"", "tags: \"\"", ""]
    env_dev = ["# dev overlay", "", "[defaults]", "alerts_enabled = false", "replicas = 1", "retention_days = \"14\"",
               "pii_scan = \"FALSE\"", "", "[tier.gold]", "replicas = 2", "alerts_enabled = true", "alerts_enabled = on", "",
               "[tier.silver]", "partitions = 4", "replicas = +3", "weight = +4", ""]
    env_prod = ["# prod overlay", "", "[defaults]", "alerts_enabled = true", "replicas = \"3\"", "pii_scan = true", "",
                "[tier.gold]", "replicas = 5", "weight = \"+6\"", "", "[tier.silver]", "replicas = 4", "alerts_enabled = TRUE",
                "", "[tier.bronze]", "alerts_enabled = false", "replicas = +2", ""]
    if hidden:
        env_dev[env_dev.index("alerts_enabled = true")] += "\nweight = " + str(prng.choice([6, 7, 9])).translate(_GFULL)
        env_prod[env_prod.index("alerts_enabled = TRUE")] += "\npii_scan = on"
    csv_lines = ["owner,team,active_from,active_to"]
    order = rows[:]
    rng.shuffle(order)
    for old, new, new_first in planted_rows:
        a, b = order.index(old), order.index(new)
        if (b < a) != new_first:
            order[a], order[b] = order[b], order[a]
    for owner, t, begin, end in order:
        csv_lines.append(f"{owner},{t},{_gstr(begin)},{'' if end is None else _gstr(end)}")
    manifest = {"release": release, "compile_date": compile_date, "catalog": catalog}
    quotas = {"shared": rng.randint(40000, 60000), "dev": rng.randint(4000, 8000), "prod": rng.randint(20000, 40000)}

    files = {
        "release_manifest.json": (_gjson.dumps(manifest, indent=2) + "\n").encode(),
        "schema_registry.json": (_gjson.dumps({"keys": GEN_SCHEMA}, indent=2) + "\n").encode(),
        "base_layer.yaml": "\n".join(base).encode(),
        "products.ini": "\n".join(ini).encode(),
        "owners.csv": ("\n".join(csv_lines) + "\n").encode(),
        "deprecation.log": log_text.encode(),
        "selectors.rules": "\n".join(rule_lines).encode(),
        "team_overrides.json": team_text.encode(),
        "product_overrides.jsonl": over_text.encode(),
        "env_dev.toml": "\n".join(env_dev).encode(),
        "env_prod.toml": "\n".join(env_prod).encode(),
        "cluster_quota.json": b"",
    }
    if ref_compute is not None:
        quotas = gen_tune_quotas(files, quotas, ref_compute)
    files["cluster_quota.json"] = (_gjson.dumps(quotas, indent=2) + "\n").encode()
    if ref_compute is not None:
        files = gen_caps(files, prng, ref_compute, 0.10 if hidden else 0.0, hidden, n_products * 60)
    return files


def _gshares(files, ref_compute):
    out = ref_compute(files)
    return {doc: {pid: p["quota"] for pid, p in out[doc]["products"].items() if doc != "config.json" or p["status"] == "active"}
            for doc in ("config.json", "profile_dev.json", "profile_prod.json")}


def _gcap_records(files, records, first_seq):
    lines = files["product_overrides.jsonl"].decode().splitlines(keepends=True)
    used = {_gjson.loads(line)["seq"] for line in lines}
    seq = first_seq
    for pid, cap in records:
        while seq in used:
            seq += 1
        used.add(seq)
        lines.insert((seq * 7919) % (len(lines) + 1), _gjson.dumps(
            {"seq": seq, "product": pid, "key": "quota_cap", "value": cap, "ticket": f"CHG-{seq * 7 % 99991:05d}"}) + "\n")
    return dict(files, **{"product_overrides.jsonl": "".join(lines).encode()})


def gen_caps(files, rng, ref_compute, rate, separate, first_seq):
    shares = _gshares(files, ref_compute)["config.json"]
    ranked = sorted(shares, key=lambda pid: (-shares[pid], pid))
    if not separate:
        # round-one shares without remainders, and caps that bind in config.json only, so every reading of the re-share agrees
        quotas = _gjson.loads(files["cluster_quota.json"])
        weights = {pid: p["settings"]["weight"] for pid, p in ref_compute(files)["config.json"]["products"].items()
                   if p["status"] == "active"}
        total = sum(weights.values())
        quotas["shared"] = max(1, round(quotas["shared"] / total)) * total
        files = dict(files, **{"cluster_quota.json": (_gjson.dumps(quotas, indent=2) + "\n").encode()})
        every = _gshares(files, ref_compute)
        shares = every["config.json"]
        fits = [pid for pid in sorted(shares) if max(every["profile_dev.json"][pid], every["profile_prod.json"][pid]) < shares[pid] - 1]
        records = [(pid, rng.randint(max(every["profile_dev.json"][pid], every["profile_prod.json"][pid]), shares[pid] - 1))
                   for pid in rng.sample(fits, 4)]
        trial = _gcap_records(files, records, first_seq)
        mine = ref_compute(trial)
        assert all(mine[d] == ref_compute(trial, cap="restart")[d] for d in ("config.json", "profile_dev.json", "profile_prod.json"))
        assert mine["config.json"] != ref_compute(trial, cap="off")["config.json"]
        return trial
    dev = _gshares(files, ref_compute)["profile_dev.json"]
    for attempt in range(40):
        records = []
        for j, pid in enumerate(rng.sample(ranked, max(6, int(len(ranked) * rate)))):
            if j % 6 < 2:
                records.append((pid, max(1, shares[pid] * rng.randint(40, 97) // 100)))
            elif j % 6 == 2 and dev.get(pid, 0) > 1:
                records.append((pid, max(1, dev[pid] * rng.randint(30, 90) // 100)))
            elif j % 6 == 3 and pid in dev:
                records.append((pid, dev[pid] + 1))
            else:
                records.append((pid, shares[pid] + rng.randint(1, 3)))
        trial = _gcap_records(files, records, first_seq)
        env = trial["env_dev.toml"].decode()
        out = ref_compute(trial)
        gold = sorted(q["quota"] for pid, q in out["profile_dev.json"]["products"].items()
                      if out["config.json"]["products"][pid]["tier"] == "gold")
        cap_text = str(max(1, gold[len(gold) // 2] * 85 // 100)) if gold else "5"
        if "quota_cap" not in env:
            trial["env_dev.toml"] = env.replace("[tier.gold]\n", "[tier.gold]\nquota_cap = " + cap_text + "\n", 1).encode()
        mine = ref_compute(trial)
        other = ref_compute(trial, cap="restart")
        if all(mine[d] != other[d] for d in ("config.json", "profile_dev.json", "profile_prod.json")):
            return trial
    raise AssertionError("caps never separated the re-share readings")


def gen_capped(files, seed, ref_compute):
    records = [_gjson.loads(line) for line in files["product_overrides.jsonl"].decode().splitlines()]
    return gen_caps(files, _grandom.Random(seed), ref_compute, 0.3, True, max(r["seq"] for r in records) + 1)


def gen_tie_ok(quota, weights):
    total = sum(weights.values())
    left = quota - sum(quota * w // total for w in weights.values())
    order = sorted(weights, key=lambda pid: (-(quota * weights[pid] % total), pid))
    if left <= 0 or left >= len(order):
        return False
    rem = lambda pid: quota * weights[pid] % total
    return rem(order[left - 1]) == rem(order[left])


def gen_tune_quotas(files, quotas, ref_compute):
    files = dict(files, **{"cluster_quota.json": (_gjson.dumps(quotas) + "\n").encode()})
    config = ref_compute(files)["config.json"]
    weights = {pid: p["settings"]["weight"] for pid, p in config["products"].items() if p["status"] == "active"}
    tuned = {}
    for name, q in quotas.items():
        for step in range(400):
            if gen_tie_ok(q + step, weights):
                tuned[name] = q + step
                break
        assert name in tuned, name
    return tuned


def gen_shifted(files, shift_days=45):
    manifest = _gjson.loads(files["release_manifest.json"])
    return _gstr(_gday(manifest["compile_date"]) + _gdt.timedelta(days=shift_days))


def gen_rescaled(files, seed):
    rng = _grandom.Random(seed)
    quotas = _gjson.loads(files["cluster_quota.json"])
    cap = max(1, quotas["prod"] * 2 // len(_gjson.loads(files["release_manifest.json"])["catalog"]))
    quotas = {k: v * 3 + rng.randint(1, 97) for k, v in quotas.items()}
    env = files["env_prod.toml"].decode().replace("[defaults]\n", "[defaults]\nquota_cap = %d\n" % cap, 1)
    return dict(files, **{"cluster_quota.json": (_gjson.dumps(quotas, indent=2) + "\n").encode(),
                          "env_prod.toml": env.encode()})


def gen_shuffled(files, seed):
    rng = _grandom.Random(seed)
    lines = files["product_overrides.jsonl"].decode().splitlines(keepends=True)
    rng.shuffle(lines)
    rows = files["owners.csv"].decode().splitlines(keepends=True)
    body = rows[1:]
    rng.shuffle(body)
    return dict(files, **{"product_overrides.jsonl": "".join(lines).encode(),
                          "owners.csv": (rows[0] + "".join(body)).encode()})
