"""Verifier for the Quillfen settlement repair task.

The first part regenerates settlement extracts from fixed seeds and settles them with an
independent reference implementation of the settlement contract. The second part runs the
delivered repository on those extracts and grades the delivered repair records.
"""
import bisect
import datetime as _dt
import gzip
import hashlib
import io
import json
import os
import random
import re
import sqlite3
import tempfile
import zipfile
from urllib.parse import quote

# ============================================================================ time, zones, schedules
# Verifier-side core: time arithmetic, zone table, cron expansion, recurrence.
# Written independently of the repository engine.

_EPOCH = _dt.datetime(1970, 1, 1)
DAY = 86400
INF = 1 << 62


def iso(t):
    return (_EPOCH + _dt.timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")


def civil(y, mo, d, h=0, mi=0, s=0):
    return int((_dt.datetime(y, mo, d, h, mi, s) - _EPOCH).total_seconds())


def parse_iso(s):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1]
    d = _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    return int((d - _EPOCH).total_seconds())


def ymd(t):
    d = _EPOCH + _dt.timedelta(seconds=t)
    return d.year, d.month, d.day


def fields(t):
    d = _EPOCH + _dt.timedelta(seconds=t)
    return d.year, d.month, d.day, d.hour, d.minute, d.second, d.weekday()


def weekday_of(y, m, d):
    # Monday=0 .. Sunday=6
    return _dt.date(y, m, d).weekday()


def nth_sunday(y, m, n):
    first = _dt.date(y, m, 1)
    off = (6 - first.weekday()) % 7
    return 1 + off + 7 * (n - 1)


def last_sunday(y, m):
    nxt = _dt.date(y + (m == 12), m % 12 + 1, 1)
    last = nxt - _dt.timedelta(days=1)
    return last.day - ((last.weekday() - 6) % 7)


def fmt_offset(minutes):
    sign = "+" if minutes >= 0 else "-"
    m = abs(minutes)
    return "%s%02d:%02d" % (sign, m // 60, m % 60)


# ---------------------------------------------------------------- zones
ZONE_SPECS = {
    "America/New_York": ("us", -300, -240),
    "America/Chicago": ("us", -360, -300),
    "America/Denver": ("us", -420, -360),
    "America/Los_Angeles": ("us", -480, -420),
    "Europe/London": ("eu", 0, 60),
    "Europe/Berlin": ("eu", 60, 120),
    "Europe/Paris": ("eu", 60, 120),
    "Australia/Sydney": ("au", 600, 660),
    "Pacific/Auckland": ("nz", 720, 780),
    "Asia/Kolkata": ("fixed", 330, 330),
    "Asia/Tokyo": ("fixed", 540, 540),
    "UTC": ("fixed", 0, 0),
}
ZONE_LINKS = {
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Pacific": "America/Los_Angeles",
    "Asia/Calcutta": "Asia/Kolkata",
    "GB": "Europe/London",
    "Etc/UTC": "UTC",
}


def zone_rows(y0=2019, y1=2029):
    rows = []
    for zone, (kind, std, dst) in ZONE_SPECS.items():
        rows.append((zone, 0, std if kind != "au" and kind != "nz" else dst))
        if kind == "fixed":
            continue
        for y in range(y0, y1 + 1):
            if kind == "us":
                a = civil(y, 3, nth_sunday(y, 3, 2), 2) - std * 60
                b = civil(y, 11, nth_sunday(y, 11, 1), 2) - dst * 60
                rows.append((zone, a, dst))
                rows.append((zone, b, std))
            elif kind == "eu":
                rows.append((zone, civil(y, 3, last_sunday(y, 3), 1), dst))
                rows.append((zone, civil(y, 10, last_sunday(y, 10), 1), std))
            elif kind == "au":
                rows.append((zone, civil(y, 4, nth_sunday(y, 4, 1), 3) - dst * 60, std))
                rows.append((zone, civil(y, 10, nth_sunday(y, 10, 1), 2) - std * 60, dst))
            elif kind == "nz":
                rows.append((zone, civil(y, 4, nth_sunday(y, 4, 1), 3) - dst * 60, std))
                rows.append((zone, civil(y, 9, last_sunday(y, 9), 2) - std * 60, dst))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


class ZoneTable:
    def __init__(self, rows, links):
        self.rows = {}
        for zone, frm, off in rows:
            self.rows.setdefault(zone, []).append((frm, off))
        for z in self.rows:
            self.rows[z].sort()
        self.links = dict(links)

    def canon(self, zone):
        seen = 0
        while zone in self.links and seen < 8:
            zone = self.links[zone]
            seen += 1
        return zone

    def offset(self, zone, t):
        rows = self.rows[self.canon(zone)]
        best = rows[0][1]
        for frm, off in rows:
            if frm <= t:
                best = off
            else:
                break
        return best

    def to_local(self, zone, t):
        return t + self.offset(zone, t) * 60

    def local_candidates(self, zone, local):
        rows = self.rows[self.canon(zone)]
        offs = sorted(set(o for _, o in rows))
        out = []
        for o in offs:
            t = local - o * 60
            if self.offset(zone, t) == o:
                out.append(t)
        return sorted(set(out))

    def gap_transition(self, zone, local):
        # instant at which the wall clock jumped over `local`
        rows = self.rows[self.canon(zone)]
        for i in range(1, len(rows)):
            frm, off = rows[i]
            prev = rows[i - 1][1]
            if off > prev and frm + prev * 60 <= local < frm + off * 60:
                return frm
        return None


def resolve_wall(zt, zone, local, gap="clamp", fold="second"):
    """Map a wall time to fire instants under a DST reading."""
    cands = zt.local_candidates(zone, local)
    if len(cands) == 1:
        return cands
    if not cands:
        if gap == "skip":
            return []
        if gap == "clamp":
            return [zt.gap_transition(zone, local)]
        if gap == "shift":
            rows = zt.rows[zt.canon(zone)]
            T = zt.gap_transition(zone, local)
            before = [o for f, o in rows if f < T][-1]
            return [local - before * 60]
        raise ValueError(gap)
    if fold == "first":
        return [cands[0]]
    if fold == "second":
        return [cands[-1]]
    if fold == "both":
        return cands
    raise ValueError(fold)


# ---------------------------------------------------------------- cron
_MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
_DOWS = {d: i for i, d in enumerate("SUN MON TUE WED THU FRI SAT".split())}


def _cron_field(text, lo, hi, names):
    vals = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, st = part.split("/")
            step = int(st)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            x, y = part.split("-")
            a = names.get(x.upper(), None) if names else None
            a = int(x) if a is None else a
            b = names.get(y.upper(), None) if names else None
            b = int(y) if b is None else b
        else:
            a = names.get(part.upper(), None) if names else None
            a = int(part) if a is None else a
            b = a if step == 1 else hi
        for v in range(a, b + 1, step):
            vals.add(v)
    return vals


class Cron:
    def __init__(self, expr):
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError(expr)
        self.expr = expr
        self.minutes = _cron_field(parts[0], 0, 59, None)
        self.hours = _cron_field(parts[1], 0, 23, None)
        self.doms = _cron_field(parts[2], 1, 31, None)
        self.months = _cron_field(parts[3], 1, 12, _MONTHS)
        dows = _cron_field(parts[4], 0, 7, _DOWS)
        self.dows = set(0 if d == 7 else d for d in dows)
        self.dom_star = parts[2].startswith("*")
        self.dow_star = parts[4].startswith("*")

    def day_matches(self, y, m, d, rule="or"):
        if m not in self.months:
            return False
        cron_dow = (weekday_of(y, m, d) + 1) % 7  # Sunday=0
        dom_ok = d in self.doms
        dow_ok = cron_dow in self.dows
        if rule == "or" and not self.dom_star and not self.dow_star:
            return dom_ok or dow_ok
        return dom_ok and dow_ok


def cron_fires(zt, cron, zone, lo, hi, gap="clamp", fold="second", rule="or"):
    """Fire instants in [lo, hi) for a cron expression in a zone."""
    out = set()
    y, m, d = ymd(lo - 2 * DAY)
    day = civil(y, m, d)
    end = hi + 2 * DAY
    while day < end:
        yy, mm, dd = ymd(day)
        if cron.day_matches(yy, mm, dd, rule):
            for h in sorted(cron.hours):
                for mi in sorted(cron.minutes):
                    local = day + h * 3600 + mi * 60
                    for t in resolve_wall(zt, zone, local, gap, fold):
                        if lo <= t < hi:
                            out.add(t)
        day += DAY
    return sorted(out)


# ---------------------------------------------------------------- recurrence
_BYDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def parse_rrule(text):
    out = {}
    for part in text.split(";"):
        k, v = part.split("=", 1)
        out[k.upper()] = v
    return out


def parse_until(text):
    t = text.strip().rstrip("Z")
    return civil(int(t[0:4]), int(t[4:6]), int(t[6:8]), int(t[9:11] or 0), int(t[11:13] or 0), int(t[13:15] or 0))


def expand_rrule(start_local, rule, hard_stop_local, zt=None, zone=None):
    """Occurrence start wall times for FREQ=DAILY|WEEKLY subsets (UNTIL is a UTC instant)."""
    freq = rule.get("FREQ", "DAILY")
    interval = int(rule.get("INTERVAL", "1"))
    count = int(rule["COUNT"]) if "COUNT" in rule else None
    until = parse_until(rule["UNTIL"]) if "UNTIL" in rule else None
    out = []
    y, m, d, hh, mi, ss, wd = fields(start_local)
    tod = hh * 3600 + mi * 60 + ss
    day0 = civil(y, m, d)

    def over(s):
        return until is not None and _local_to_utc_simple(zt, zone, s) > until

    if freq == "DAILY":
        k = 0
        while True:
            s = day0 + k * interval * DAY + tod
            if s > hard_stop_local or over(s):
                break
            out.append(s)
            if count is not None and len(out) >= count:
                break
            k += 1
    elif freq == "WEEKLY":
        days = sorted(_BYDAY[x] for x in rule["BYDAY"].split(",")) if "BYDAY" in rule else [wd]
        week0 = day0 - wd * DAY
        k = 0
        done = False
        while not done:
            for dw in days:
                s = week0 + k * interval * 7 * DAY + dw * DAY + tod
                if s < start_local:
                    continue
                if s > hard_stop_local or over(s):
                    done = True
                    break
                out.append(s)
                if count is not None and len(out) >= count:
                    done = True
                    break
            k += 1
    else:
        raise ValueError(freq)
    return out


def _local_to_utc_simple(zt, zone, local):
    if zt is None or zone is None:
        return local
    c = zt.local_candidates(zone, local)
    return c[0] if c else local


def ceil_div(a, b):
    return -((-a) // b)


def to_minor(text):
    text = text.strip()
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    if "." in text:
        whole, frac = text.split(".")
    else:
        whole, frac = text, ""
    frac = (frac + "00")[:2]
    v = int(whole or "0") * 100 + int(frac)
    return -v if neg else v


def largest_remainder(total, parts):
    """Split `total` evenly over sorted `parts`; remainder to ascending ids."""
    n = len(parts)
    base = total // n
    rem = total - base * n
    order = sorted(parts)
    return {p: base + (1 if i < rem else 0) for i, p in enumerate(order)}

# ============================================================================ reference settlement
# Verifier-side reference settlement over structured records.

STATUSES = ["SUSPENDED", "UNRESOLVABLE", "MET", "EXCUSED_OUTAGE", "EXCUSED_UPSTREAM", "LATE", "MISSED"]
REJECT_CODES = ["MALFORMED_RECORD", "UNKNOWN_JOB", "UNMAPPED_DATASET", "ORPHAN_TRANSITION", "UNAPPROVED_MARK"]
LEGAL = {("none", "queued"), ("queued", "running"), ("queued", "removed"), ("running", "success"),
         ("running", "failed"), ("failed", "up_for_retry"), ("up_for_retry", "queued"),
         ("success", "cleared"), ("failed", "cleared"), ("cleared", "queued")}

_NORM = re.compile(r"[-_./ ]+")


def norm(key):
    return _NORM.sub(".", key.strip().lower()).strip(".")


class Rules:
    """The readings a settlement run applies; defaults are the settled practice."""

    def __init__(self, **kw):
        self.gap = kw.get("gap", "clamp")
        self.fold = kw.get("fold", "second")
        self.reland = kw.get("reland", "after_retract")      # first | last | after_retract
        self.marks = kw.get("marks", "before_other")          # always | never | exists | before | before_other
        self.upstream = kw.get("upstream", "lt")              # lt | le
        self.dom_dow = kw.get("dom_dow", "or")
        self.skew_sign = kw.get("skew_sign", -1)
        self.sla_zero = kw.get("sla_zero", "keep")            # keep | cancel
        self.rename = kw.get("rename", "dated")               # dated | onehop
        self.outage_first = kw.get("outage_first", True)
        self.blame_root = kw.get("blame_root", True)
        self.lateness = kw.get("lateness", "ceil")
        self.bucket_edge = kw.get("bucket_edge", "halfopen")
        self.decimal = kw.get("decimal", "exact")
        self.split_tie = kw.get("split_tie", "asc")
        self.order = kw.get("order", "deadline")


class Identity:
    def __init__(self, rename_rows, spec_keys, period_end):
        self.holds = {}   # job index -> list of [name, frm, to]
        self.by_name = {}
        holder = {}
        jobs = []

        def new_job(name, frm):
            j = len(jobs)
            jobs.append([[name, frm, INF]])
            return j

        for r in sorted(rename_rows, key=lambda r: (r["at"], r["ord"])):
            old, new, at = r["old"], r["new"], r["at"]
            if not old:
                j = new_job(new, at)
                holder[new] = j
            else:
                j = holder.get(old)
                if j is None:
                    j = new_job(old, -INF)
                jobs[j][-1][2] = at
                holder.pop(old, None)
                jobs[j].append([new, at, INF])
                holder[new] = j
        held = set()
        for h in jobs:
            for name, _, _ in h:
                held.add(name)
        for k in sorted(set(spec_keys)):
            if k not in held:
                jobs.append([[k, -INF, INF]])
                held.add(k)
        self.jobs = jobs
        for j, h in enumerate(jobs):
            for name, frm, to in h:
                self.by_name.setdefault(name, []).append((frm, to, j))
        for name in self.by_name:
            self.by_name[name].sort()
        last = period_end - 1
        self.canon = []
        for h in jobs:
            cid = None
            for name, frm, to in h:
                if frm <= last < to:
                    cid = name
            if cid is None:
                cid = h[0][0] if h[0][1] > last else h[-1][0]
            self.canon.append("job:" + cid)

    def resolve(self, key, t):
        lst = self.by_name.get(key)
        if not lst:
            return None
        for frm, to, j in lst:
            if frm <= t < to:
                return j
        before = [(to, j) for frm, to, j in lst if to <= t]
        if before:
            return max(before)[1]
        after = [(frm, j) for frm, to, j in lst if frm > t]
        return min(after)[1]

    def name_at(self, j, t):
        for name, frm, to in self.jobs[j]:
            if frm <= t < to:
                return name
        return self.jobs[j][-1][0] if t >= self.jobs[j][-1][1] else self.jobs[j][0][0]


class OneHopIdentity(Identity):
    def __init__(self, rename_rows, spec_keys, period_end):
        super().__init__(rename_rows, spec_keys, period_end)
        self._map = {}
        for r in sorted(rename_rows, key=lambda r: (r["at"], r["ord"])):
            if r["old"]:
                self._map[r["old"]] = r["new"]

    def resolve(self, key, t):
        k = self._map.get(key, key)
        lst = self.by_name.get(k)
        if not lst:
            return None
        return lst[-1][2]


_GLOBS = {}


def glob_match(pattern, path):
    rx = _GLOBS.get(pattern)
    if rx is None:
        rx = _GLOBS[pattern] = re.compile("^" + "".join("[^/]*" if ch == "*" else re.escape(ch) for ch in pattern) + "$")
    return rx.match(path) is not None


def settle(D, rules=None):
    """D: dict of structured, valid record lists; returns output tables."""
    R = rules or Rules()
    P0, P1 = D["period"]
    zt = ZoneTable(D["tz_rows"], D["tz_links"])
    rejects = list(D.get("malformed", []))

    def reject(rec, code):
        rejects.append((rec["src"], rec["ord"], code))

    spec_keys = [s["key"] for s in D["specs"]]
    IdCls = Identity if R.rename == "dated" else OneHopIdentity
    ident = IdCls(D["renames"], spec_keys, P1)
    canon = ident.canon

    # ---- job specs
    specs = {}
    for s in D["specs"]:
        j = ident.resolve(s["key"], s["rev_at"])
        specs.setdefault(j, []).append(s)
    for j in specs:
        specs[j].sort(key=lambda s: s["rev_at"])

    def spec_at(j, t):
        best = None
        for s in specs.get(j, []):
            if s["rev_at"] <= t:
                best = s
        return best

    # ---- sla overrides
    sla_ovr = {}
    for o in D["sla_overrides"]:
        j = ident.resolve(o["key"], o["at"])
        if j is None:
            reject(o, "UNKNOWN_JOB")
            continue
        sla_ovr.setdefault(j, []).append(o)
    for j in sla_ovr:
        sla_ovr[j].sort(key=lambda o: (o["at"], o["ord"]))

    def sla_at(j, t, base):
        cur = None
        for o in sla_ovr.get(j, []):
            if o["at"] <= t:
                v = o["value"]
                if v is None or (R.sla_zero == "cancel" and v == 0):
                    cur = None
                else:
                    cur = v
        return base if cur is None else cur

    # ---- commitments
    lo = P0 - 8 * DAY
    commits = {}
    for j in sorted(specs):
        revs = specs[j]
        for i, s in enumerate(revs):
            a = s["rev_at"]
            b = revs[i + 1]["rev_at"] if i + 1 < len(revs) else INF
            if not s["enabled"]:
                continue
            a2, b2 = max(a, lo), min(b, P1)
            if a2 >= b2:
                continue
            cron = Cron(s["cron"])
            for t in cron_fires(zt, cron, s["zone"], a2, b2, R.gap, R.fold, R.dom_dow):
                sla = sla_at(j, t, s["sla_minutes"])
                dl = t + sla * 60
                if P0 <= dl < P1:
                    commits[(j, t)] = {"job": j, "nominal": t, "deadline": dl, "tier": s["tier"],
                                       "sla": sla, "zone": s["zone"]}

    # ---- team handles / ownership
    handles = D["team_handles"]

    def team_of_handle(h, t):
        h = h.lower().lstrip("@")
        for r in handles:
            if r["handle"] == h and r["frm"] <= t < r["to"]:
                return r["team"]
        return None

    own_commits = sorted(D["ownership"], key=lambda c: (c["at"], -c["ord"]))

    snapshots = []
    state = []
    for c in own_commits:
        for op, pat, hs in c["changes"]:
            if op == "+":
                state.append((pat, tuple(hs)))
            else:
                for k in range(len(state)):
                    if state[k][0] == pat:
                        del state[k]
                        break
        snapshots.append((c["at"], tuple(state)))
    snap_times = [s[0] for s in snapshots]

    def owners_at(j, t):
        import bisect as _b
        i = _b.bisect_right(snap_times, t) - 1
        lines = snapshots[i][1] if i >= 0 else ()
        path = "jobs/" + ident.name_at(j, t)
        match = None
        for pat, hs in lines:
            if glob_match(pat, path):
                match = hs
        if not match:
            return []
        teams = set()
        for h in match:
            tm = team_of_handle(h, t)
            if tm:
                teams.add(tm)
        return sorted(teams)

    own_cache = {}

    def owners(j, t):
        k = (j, t)
        if k not in own_cache:
            own_cache[k] = owners_at(j, t)
        return own_cache[k]

    # ---- suspensions
    freeze_occ = []  # (a, b, tiers)
    for series in D["freeze"]:
        ov = {o["rid_local"]: o for o in D["freeze_overrides"] if o["uid"] == series["uid"]}
        rule = parse_rrule(series["rrule"]) if series["rrule"] else None
        starts = [series["start_local"]] if rule is None else expand_rrule(
            series["start_local"], rule, min(series["start_local"] + 3650 * DAY, P1 + 400 * DAY), zt, series["zone"])
        dur = series["end_local"] - series["start_local"]
        ex = set(series["exdates_local"])
        for s in starts:
            if s in ex:
                continue
            if s in ov:
                o = ov[s]
                if o["cancelled"]:
                    continue
                sa, sb = o["start_local"], o["end_local"]
            else:
                sa, sb = s, s + dur
            ua = zt.local_candidates(series["zone"], sa)[0]
            ub = zt.local_candidates(series["zone"], sb)[0]
            freeze_occ.append((ua, ub, set(series["tiers"])))

    holidays = {}
    for h in D["holidays"]:
        holidays.setdefault(h["team"], set()).add(h["date"])

    pause_windows = {}
    ev = []
    for p in D["pauses"]:
        j = ident.resolve(p["key"], p["at"])
        if j is None:
            reject(p, "UNKNOWN_JOB")
            continue
        ev.append((p["at"], p["ord"], j, p))
    open_p = {}
    for at, _, j, p in sorted(ev):
        if p["action"] == "pause":
            if j not in open_p:
                open_p[j] = at
        else:
            if j in open_p:
                pause_windows.setdefault(j, []).append((open_p.pop(j), at))
            else:
                reject(p, "ORPHAN_TRANSITION")
    for j, at in open_p.items():
        pause_windows.setdefault(j, []).append((at, INF))

    def suspension(c):
        t, j = c["nominal"], c["job"]
        for a, b, tiers in freeze_occ:
            if a <= t < b and c["tier"] in tiers:
                return "FREEZE"
        for a, b in pause_windows.get(j, []):
            if a <= t < b:
                return "PAUSE"
        if c["tier"] == 3:
            loc = zt.to_local(c["zone"], t)
            dkey = ymd(loc)
            for tm in owners(j, c["deadline"]):
                if dkey in holidays.get(tm, ()):
                    return "HOLIDAY"
        return ""

    for c in commits.values():
        c["suspension"] = suspension(c)

    # ---- producers / datasets
    producers = {}
    for p in D["producers"]:
        producers.setdefault(p["dataset"], []).append(p)

    def producers_at(ds, t, rec=None):
        out = set()
        known_rows = False
        for p in producers.get(ds, []):
            if p["frm"] <= t < p["to"]:
                j = ident.resolve(p["key"], t)
                if j is not None:
                    out.add(j)
                known_rows = True
        return out

    for p in D["producers"]:
        if ident.resolve(p["key"], 0) is None:
            reject(p, "UNKNOWN_JOB")

    job_datasets = {}
    for ds, rows in producers.items():
        for p in rows:
            job_datasets.setdefault(ds, None)

    prod_by_key = {}
    for p in D["producers"]:
        if ident.resolve(p["key"], 0) is not None:
            prod_by_key.setdefault(p["key"], []).append(p)

    def datasets_of(j, t):
        out = set()
        for name, _, _ in ident.jobs[j]:
            for p in prod_by_key.get(name, []):
                if p["frm"] <= t < p["to"] and ident.resolve(p["key"], t) == j:
                    out.add(p["dataset"])
        return out

    # ---- backfills
    backfill_runs = set()
    for b in D["backfills"]:
        if ident.resolve(b["key"], b["nominal"]) is None:
            reject(b, "UNKNOWN_JOB")
            continue
        backfill_runs.add(b["run_id"])

    # ---- landing evidence
    part_events = {}
    for e in D["landings"]:
        js = producers_at(e["dataset"], e["nominal"])
        if not js:
            reject(e, "UNMAPPED_DATASET")
            continue
        part_events.setdefault((e["dataset"], e["nominal"]), []).append((e["at"], 0, e["ord"], e["src"], "land"))
    for e in D["retracts"]:
        js = producers_at(e["dataset"], e["nominal"])
        if not js:
            reject(e, "UNMAPPED_DATASET")
            continue
        part_events.setdefault((e["dataset"], e["nominal"]), []).append((e["at"], 1, e["ord"], e["src"], "retract"))
    governing_land = {}
    for key, evs in part_events.items():
        evs.sort()
        lands = [e for e in evs if e[4] == "land"]
        seen_land = False
        last_retract_idx = None
        for i, e in enumerate(evs):
            if e[4] == "land":
                seen_land = True
            else:
                if not seen_land:
                    rejects.append((e[3], e[2], "ORPHAN_TRANSITION"))
                else:
                    last_retract_idx = i
        valid_evs = evs
        if not lands:
            continue
        if R.reland == "first":
            g = lands[0][0]
        elif R.reland == "last":
            g = lands[-1][0]
        else:
            if last_retract_idx is None:
                g = lands[0][0]
            else:
                after = [e for e in evs[last_retract_idx + 1:] if e[4] == "land"]
                g = after[0][0] if after else None
        governing_land[key] = (g, len(lands))

    # ---- clock calibration
    samples = {}
    for s in D["clock_samples"]:
        samples.setdefault(s["host"], []).append((s["t_ms"], s["offset_ms"]))
    for h in D["heartbeats"]:
        samples.setdefault(h["host"], []).append((h["recv_ms"], h["sent_ms"] - h["recv_ms"]))
    for h in samples:
        samples[h].sort()

    def correct(host, local_ms):
        best = None
        for t_ms, off in samples.get(host, []):
            if t_ms <= local_ms:
                if local_ms - t_ms <= 86400 * 1000:
                    best = off
                else:
                    best = None
            else:
                break
        if best is None:
            return None
        return (local_ms + R.skew_sign * best) // 1000

    # ---- worker commits
    worker = {}
    worker_rows = []
    for e in D["workers"]:
        j = ident.resolve(e["key"], e["nominal"])
        if j is None:
            reject(e, "UNKNOWN_JOB")
            continue
        if e["event"] != "commit" or e["run_id"] in backfill_runs:
            continue
        corrected = correct(e["host"], e["local_ms"])
        worker.setdefault((j, e["nominal"]), []).append(corrected)
        worker_rows.append((j, e["nominal"], e["host"], e["local_ms"], corrected))

    # ---- scheduler transitions
    sched = {}
    audit_inst = {}
    for e in D["sched"]:
        j = ident.resolve(e["key"], e["nominal"])
        if j is None:
            reject(e, "UNKNOWN_JOB")
            continue
        audit_inst.setdefault((j, e["nominal"], e["run_id"]), []).append(e)
        if e["state"] == "success" and e["run_id"] not in backfill_runs:
            sched.setdefault((j, e["nominal"]), []).append(e["at"])
    state_audit = []
    for (j, nom, run), evs in audit_inst.items():
        evs.sort(key=lambda e: (e["at"], e["src"], e["ord"]))
        cur = "none"
        for e in evs:
            if (cur, e["state"]) not in LEGAL:
                state_audit.append((canon[j], iso(nom), run, cur, e["state"], iso(e["at"])))
            cur = e["state"]

    # ---- people
    person_of_mail = {}
    people = {}
    for p in D["ldif_people"]:
        people.setdefault(p["eid"], {"emails": set(), "handles": set()})
        for m in p["mails"]:
            people[p["eid"]]["emails"].add(m.lower())
    uid_eid = {p["uid"]: p["eid"] for p in D["ldif_people"]}
    for m in D["ldif_mods"]:
        eid = uid_eid.get(m["uid"])
        if eid is not None and m["op"] == "add":
            people[eid]["emails"].add(m["mail"].lower())
    for eid, rec in people.items():
        for m in rec["emails"]:
            person_of_mail[m] = eid
    person_of_handle = {}
    for v in D["vcards"]:
        eid = None
        for m in v["emails"]:
            if m.lower() in person_of_mail:
                eid = person_of_mail[m.lower()]
        if eid is None:
            continue
        for h in v["handles"]:
            person_of_handle[h.lower()] = eid
            people[eid]["handles"].add(h.lower())

    # ---- operator marks
    approvals = {}
    for a in D["approvals"]:
        j = ident.resolve(a["key"], a["nominal"])
        if j is None:
            reject(a, "UNKNOWN_JOB")
            continue
        approvals.setdefault((j, a["nominal"]), []).append(a)
    marks = {}
    for m in D["operator"]:
        j = ident.resolve(m["key"], m["nominal"])
        if j is None:
            reject(m, "UNKNOWN_JOB")
            continue
        if m["action"] != "mark_success":
            continue
        marks.setdefault((j, m["nominal"]), []).append(m)

    def mark_accepted(m, k):
        aps = approvals.get(k, [])
        if R.marks == "always":
            return True
        if R.marks == "never":
            return False
        if R.marks == "exists":
            return bool(aps)
        actor = person_of_handle.get(m["actor"].lower())
        for a in aps:
            if a["at"] > m["at"]:
                continue
            if R.marks == "before":
                return True
            ap = person_of_mail.get(a["from"].lower())
            if ap is not None and actor is not None and ap != actor:
                return True
        return False

    for k, ms in marks.items():
        for m in ms:
            if not mark_accepted(m, k):
                reject(m, "UNAPPROVED_MARK")

    # ---- evidence resolution per interval
    evidence = {}
    for k, c in commits.items():
        j, t = k
        dss = datasets_of(j, t)
        ds = next(iter(dss)) if len(dss) == 1 else None
        info = {"landed_at": None, "tier": "none", "candidates": 0, "reason": ""}
        if len(dss) > 1 or any(len(producers_at(x, t)) > 1 for x in dss):
            info["reason"] = "AMBIGUOUS_PRODUCER"
        else:
            gl = governing_land.get((ds, t)) if ds is not None else None
            if gl is not None:
                info["tier"] = "physical"
                info["candidates"] = gl[1]
                info["landed_at"] = gl[0]
            elif k in worker:
                vals = worker[k]
                info["tier"] = "worker"
                info["candidates"] = len(vals)
                good = [v for v in vals if v is not None]
                if good:
                    info["landed_at"] = min(good)
                else:
                    info["reason"] = "UNCALIBRATED_CLOCK"
            elif k in sched:
                info["tier"] = "scheduler"
                info["candidates"] = len(sched[k])
                info["landed_at"] = min(sched[k])
            elif k in marks:
                acc = [m["at"] for m in marks[k] if mark_accepted(m, k)]
                if acc:
                    info["tier"] = "operator"
                    info["candidates"] = len(acc)
                    info["landed_at"] = min(acc)
        info["datasets"] = dss
        evidence[k] = info

    # ---- outages
    outage_rev = {}
    for o in D["outages"]:
        cur = outage_rev.get(o["guid"])
        if cur is None or (o["pub_at"], o["ord"]) > (cur["pub_at"], cur["ord"]):
            outage_rev[o["guid"]] = o
    outage_scope = {}
    for r in D["incidents"]:
        outage_scope.setdefault(r["outage"], set()).add(r["dataset"])
    outages = [(o["a"], o["b"], outage_scope.get(g, set())) for g, o in outage_rev.items() if o["status"] == "active"]

    # ---- dependencies
    edges = []
    for e in D["deps"]:
        if ident.resolve(e["down"], 0) is None or ident.resolve(e["up"], 0) is None:
            reject(e, "UNKNOWN_JOB")
            continue
        edges.append(e)
    job_nominals = {}
    for (j, t) in commits:
        job_nominals.setdefault(j, []).append(t)
    for j in job_nominals:
        job_nominals[j].sort()

    import bisect
    status = {}
    upstream_of = {}
    order_keys = sorted(commits, key=lambda k: (commits[k]["deadline"], canon[k[0]], k[1]))
    # upstream graph evaluated per interval
    dep_rows = []
    waits = []
    for k in order_keys:
        c = commits[k]
        j, t = k
        ups = []
        seen_waits = set()
        for e in edges:
            if not (e["frm"] <= t < e["to"]):
                continue
            if ident.resolve(e["down"], t) != j:
                continue
            u = ident.resolve(e["up"], t)
            if u is None:
                continue
            noms = job_nominals.get(u, [])
            if R.upstream == "lt":
                idx = bisect.bisect_left(noms, t)
            else:
                idx = bisect.bisect_right(noms, t)
            idx = idx - 1 - e["lag"]
            waited = noms[idx] if idx >= 0 else None
            if (u, e["lag"], waited) not in seen_waits:
                seen_waits.add((u, e["lag"], waited))
                waits.append((k, u, e["lag"], waited))
            if idx < 0:
                continue
            ups.append((u, noms[idx], e["lag"]))
        upstream_of[k] = sorted(set(ups))

    # status in dependency order: upstream nominal < downstream nominal always
    def classify(k, memo):
        if k in memo:
            return memo[k]
        c = commits[k]
        ev_ = evidence[k]
        if c["suspension"]:
            memo[k] = ("SUSPENDED", "")
            return memo[k]
        if ev_["reason"]:
            memo[k] = ("UNRESOLVABLE", ev_["reason"])
            return memo[k]
        la = ev_["landed_at"]
        if la is not None and la < c["deadline"]:
            memo[k] = ("MET", "")
            return memo[k]
        out_ex = False
        for a, b, scope in outages:
            if a <= c["deadline"] < b and (ev_["datasets"] & scope):
                out_ex = True
        up_ex = False
        for (u, un, lag) in upstream_of.get(k, []):
            uk = (u, un)
            if uk not in commits:
                continue
            st = classify(uk, memo)[0]
            if st not in ("MET", "SUSPENDED"):
                up_ex = True
        if R.outage_first:
            if out_ex:
                memo[k] = ("EXCUSED_OUTAGE", "")
                return memo[k]
            if up_ex:
                memo[k] = ("EXCUSED_UPSTREAM", "")
                return memo[k]
        else:
            if up_ex:
                memo[k] = ("EXCUSED_UPSTREAM", "")
                return memo[k]
            if out_ex:
                memo[k] = ("EXCUSED_OUTAGE", "")
                return memo[k]
        if la is not None and la < P1:
            memo[k] = ("LATE", "")
        else:
            memo[k] = ("MISSED", "")
        return memo[k]

    memo = {}
    for k in sorted(commits, key=lambda k: k[1]):
        classify(k, memo)

    # ---- money
    rates = {}
    for r in D["ratecard"]:
        rates.setdefault((r["tier"], r["bucket"]), []).append(r)
    for key in rates:
        rates[key].sort(key=lambda r: (r["frm"], r["ord"]))

    def minor(text):
        if R.decimal == "exact":
            return to_minor(text)
        return int(float(text) * 100)

    def bucket(minutes):
        if R.bucket_edge == "halfopen":
            return "B0" if minutes < 30 else ("B30" if minutes < 120 else "B120")
        return "B0" if minutes <= 30 else ("B30" if minutes <= 120 else "B120")

    ledger = []
    for k in order_keys:
        c = commits[k]
        st, reason = memo[k]
        ev_ = evidence[k]
        la = ev_["landed_at"]
        mins = bk = pen = None
        if st in ("LATE", "MISSED"):
            end = la if st == "LATE" else P1
            secs = end - c["deadline"]
            mins = ceil_div(secs, 60) if R.lateness == "ceil" else round(secs / 60)
            bk = bucket(mins)
            row = None
            for r in rates.get((c["tier"], bk), []):
                if r["frm"] <= c["deadline"]:
                    row = r
            pen = minor(row["base"]) + minor(row["per_min"]) * mins if row else 0
        ledger.append({"key": k, "status": st, "reason": reason, "landed_at": la if st in ("MET", "LATE", "EXCUSED_OUTAGE", "EXCUSED_UPSTREAM", "MISSED") and la is not None else None,
                       "minutes": mins, "bucket": bk, "penalty": pen})

    # ---- blame
    blame = []
    parents = {}
    for k in order_keys:
        if memo[k][0] != "EXCUSED_UPSTREAM":
            continue
        cands = []
        for (u, un, lag) in upstream_of.get(k, []):
            uk = (u, un)
            if uk in commits and memo[uk][0] not in ("MET", "SUSPENDED"):
                la = evidence[uk]["landed_at"]
                cands.append((-(la if la is not None else INF), canon[u], uk))
        cands.sort()
        parents[k] = cands[0][2]
    for k in order_keys:
        if k not in parents:
            continue
        cur, depth = parents[k], 1
        if R.blame_root:
            while cur in parents:
                cur = parents[cur]
                depth += 1
        blame.append({"key": k, "parent": parents[k], "root": cur, "depth": depth,
                      "root_teams": owners(cur[0], commits[cur]["deadline"])})

    # ---- chargeback & accountability
    teams = sorted(set(r["team"] for r in handles))
    cb = {tm: {"penalty": 0, "late": 0, "missed": 0, "blamed": 0} for tm in teams}
    unowned = {"penalty": 0, "late": 0, "missed": 0}
    tier_charge = {"teams": {}, "unowned": {}}
    rota_occ = build_rota(D, zt)
    accountability = []
    for row in ledger:
        if row["status"] not in ("LATE", "MISSED"):
            continue
        k = row["key"]
        c = commits[k]
        ts = owners(k[0], c["deadline"])
        fld = "late" if row["status"] == "LATE" else "missed"
        if not ts:
            unowned["penalty"] += row["penalty"]
            unowned[fld] += 1
            cell = tier_charge["unowned"].setdefault(c["tier"], {"penalty": 0, "late": 0, "missed": 0})
            cell["penalty"] += row["penalty"]
            cell[fld] += 1
        if ts:
            share = largest_remainder(row["penalty"], ts) if R.split_tie == "asc" else _split_first(row["penalty"], ts)
            for tm in ts:
                cb.setdefault(tm, {"penalty": 0, "late": 0, "missed": 0, "blamed": 0})
                cb[tm]["penalty"] += share[tm]
                cb[tm][fld] += 1
                cell = tier_charge["teams"].setdefault(tm, {}).setdefault(c["tier"], {"penalty": 0, "late": 0, "missed": 0})
                cell["penalty"] += share[tm]
                cell[fld] += 1
        for tm in ts:
            accountability.append((canon[k[0]] + "@" + iso(k[1]), tm, oncall(rota_occ, person_of_mail, tm, c["deadline"])))
    for b in blame:
        for tm in b["root_teams"]:
            cb.setdefault(tm, {"penalty": 0, "late": 0, "missed": 0, "blamed": 0})
            cb[tm]["blamed"] += 1

    return {
        "ident": ident, "commits": commits, "evidence": evidence, "status": memo, "ledger": ledger,
        "blame": blame, "chargeback": cb, "accountability": accountability, "rejects": rejects,
        "state_audit": state_audit, "unowned": unowned, "datasets_of": datasets_of, "upstream_of": upstream_of, "people": people, "order": order_keys,
        "canon": canon, "owners": owners, "governing_land": governing_land, "marks": marks,
        "mark_accepted": mark_accepted, "part_events": part_events,
        "zt": zt, "freeze_occ": freeze_occ, "rota_occ": rota_occ, "person_of_mail": person_of_mail,
        "person_of_handle": person_of_handle, "worker_rows": worker_rows, "waits": waits, "tier_charge": tier_charge,
    }


def _split_first(total, parts):
    n = len(parts)
    base = total // n
    rem = total - base * n
    return {p: base + (rem if i == 0 else 0) for i, p in enumerate(parts)}


def build_rota(D, zt):
    occ = []
    for s in D["rota"]:
        ov = {o["rid_local"]: o for o in D["rota_overrides"] if o["uid"] == s["uid"]}
        rule = parse_rrule(s["rrule"])
        starts = expand_rrule(s["start_local"], rule, D["period"][1] + 60 * DAY, zt, s["zone"])
        for st in starts:
            att = s["attendee"]
            if st in ov:
                if ov[st]["cancelled"]:
                    continue
                att = ov[st]["attendee"]
            a = zt.local_candidates(s["zone"], st)[0]
            b = zt.local_candidates(s["zone"], st + s["length_days"] * DAY)[0]
            occ.append((s["team"], a, b, att))
    return occ


def oncall(occ, person_of_mail, team, t):
    best = None
    for tm, a, b, att in occ:
        if tm == team and a <= t < b:
            pid = person_of_mail.get(att.lower())
            key = (-a, pid or "~")
            if pid is not None and (best is None or key < best[0]):
                best = (key, pid)
    return "emp:" + best[1] if best else "UNASSIGNED"

# ============================================================================ extract generator
# Verifier-side world generator: seeded platform month with conflicting evidence.

FAMILIES = ["platform", "analytics", "finance", "legacy"]
FAMILY_ZONES = {
    "platform": ["America/New_York", "America/Chicago", "UTC", "US/Eastern", "America/New_York"],
    "analytics": ["Asia/Kolkata", "Australia/Sydney", "Asia/Tokyo", "Pacific/Auckland", "Asia/Calcutta"],
    "finance": ["Europe/Berlin", "Europe/London", "Europe/Paris", "GB", "Europe/Berlin"],
    "legacy": ["America/Los_Angeles", "America/Denver", "US/Pacific", "America/Los_Angeles"],
}
FAMILY_REGION = {"platform": "us", "analytics": "apac", "finance": "eu", "legacy": "legacy"}
FAMILY_PREFIX = {"platform": "lake", "analytics": "ana", "finance": "fin", "legacy": "leg"}
DST_HOURS = {  # wall hours inside a transition for the zone family
    "America/New_York": [1, 2], "America/Chicago": [1, 2], "US/Eastern": [1, 2],
    "America/Los_Angeles": [1, 2], "America/Denver": [1, 2], "US/Pacific": [1, 2],
    "Europe/Berlin": [2], "Europe/Paris": [2], "Europe/London": [1], "GB": [1],
    "Australia/Sydney": [2], "Pacific/Auckland": [2],
}
DOMAINS = ["orders", "payments", "ledger", "sessions", "clicks", "inventory", "shipments", "refunds", "invoices",
           "accounts", "events", "catalog", "pricing", "returns", "vendors", "rates", "tickets", "claims",
           "fraud", "loyalty", "reviews", "search", "ads", "budgets", "payroll", "tax", "fx", "cohorts",
           "churn", "forecast", "stock", "leads", "quotes", "renewals", "usage", "alerts", "exports",
           "snapshots", "audits", "limits"]
STAGES = ["ingest", "stage", "merge", "publish", "rollup", "extract", "sync", "compact", "score", "close"]
CADENCES = ["hourly", "four.hourly", "daily", "weekday", "twice.monthly", "weekly"]
TEAMS = ["ingest-core", "lake-platform", "analytics-eng", "growth-analytics", "finance-data",
         "revenue-ops", "legacy-batch", "billing-systems", "ml-features", "data-quality"]
FAMILY_TEAMS = {"platform": ["ingest-core", "lake-platform", "data-quality"],
                "analytics": ["analytics-eng", "growth-analytics", "ml-features"],
                "finance": ["finance-data", "revenue-ops"],
                "legacy": ["legacy-batch", "billing-systems"]}
TEAM_ZONE = {"ingest-core": "America/New_York", "lake-platform": "America/Chicago", "data-quality": "UTC",
             "analytics-eng": "Asia/Kolkata", "growth-analytics": "Australia/Sydney", "ml-features": "Asia/Tokyo",
             "finance-data": "Europe/Berlin", "revenue-ops": "Europe/London", "legacy-batch": "America/Los_Angeles",
             "billing-systems": "America/Denver"}
FIRST = ["Asha", "Bruno", "Chen", "Dara", "Emeka", "Farah", "Gus", "Hana", "Ines", "Jonas", "Kavya", "Lior",
         "Mira", "Nikhil", "Oona", "Pavel", "Qiu", "Rosa", "Sanjay", "Tove", "Umar", "Vera", "Wen", "Ximena",
         "Yusuf", "Zoe", "Arjun", "Beatriz", "Colm", "Divya", "Elif", "Femi", "Greta", "Hugo", "Ishaan", "Jana"]
LAST = ["Rao", "Silva", "Okafor", "Lindqvist", "Mehta", "Novak", "Hughes", "Tanaka", "Moreau", "Ivers",
        "Kapoor", "Haddad", "Brandt", "Costa", "Dubois", "Eriksen", "Fischer", "Garcia", "Iyer", "Jansen"]
POOLS = ["a", "b", "c", "d", "e", "f"]
LANDING_SYSTEMS = ["objectstore", "hdfs", "warehouse", "catalog", "partner"]


def _h(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


class World:
    pass


def default_params(seed, p0, p1, scale=1.0, features=None):
    return {
        "seed": seed, "period": (p0, p1), "scale": scale,
        "jobs": {f: max(4, int(26 * scale)) for f in FAMILIES},
        "features": set(features) if features is not None else set(ALL_FEATURES),
    }


ALL_FEATURES = ["dst", "reland", "marks", "upstream", "rename_chain", "key_reuse", "skew", "eu_local",
                "syslog_rollover", "ics_fold", "logfmt_escape", "ldif_multi", "dom_dow", "sla_zero",
                "outage_upstream", "blame_chain", "decimal", "bucket_edge", "split_tie", "ordering",
                "backfill", "uncalibrated", "ambiguous", "orphans", "state_audit", "holiday", "pause",
                "freeze", "outage", "handles"]


def build(params):
    rng = random.Random(params["seed"])
    w = World()
    w.P = params
    w.F = params["features"]
    w.p0, w.p1 = params["period"]
    y0 = ymd(w.p0)[0]
    w.zt = ZoneTable(zone_rows(y0 - 7, y0 + 3), ZONE_LINKS)
    w.tz_rows = zone_rows(y0 - 7, y0 + 3)
    w.tz_links = dict(ZONE_LINKS)
    w.hist0 = civil(y0 - 4, 1, 1)
    _teams(w, rng)
    _people(w, rng)
    _hosts(w, rng)
    _jobs(w, rng)
    _datasets(w, rng)
    _deps(w, rng)
    _ownership(w, rng)
    _calendars(w, rng)
    _pauses(w, rng)
    _sla_overrides(w, rng)
    _ratecard(w, rng)
    _simulate(w, rng)
    _outages(w, rng)
    _journals(w, rng)
    return w


# ------------------------------------------------------------------ teams/people
def _teams(w, rng):
    w.teams = list(TEAMS)
    w.team_handles = []
    for tm in TEAMS:
        w.team_handles.append({"handle": "quillfen/" + tm, "team": tm, "frm": -INF, "to": INF})
    # historical and moving handles
    moves = []
    for i in range(22):
        base = rng.choice(DOMAINS)
        h = "quillfen/%s-%s" % (base, rng.choice(["owners", "oncall", "stewards", "maint"]))
        if any(x["handle"] == h for x in w.team_handles):
            continue
        a, b = rng.sample(TEAMS, 2)
        cut = w.p0 + rng.randrange(3 * DAY, 25 * DAY) if ("handles" in w.F and i % 3 == 0) else w.hist0 + rng.randrange(0, 900) * DAY
        w.team_handles.append({"handle": h, "team": a, "frm": -INF, "to": cut})
        w.team_handles.append({"handle": h, "team": b, "frm": cut, "to": INF})
        moves.append(h)
    # padding: retired handles
    k = 0
    while len(w.team_handles) < 210:
        tm = rng.choice(TEAMS)
        h = "quillfen/%s-%s-%d" % (tm, rng.choice(["archive", "old", "v1", "legacy"]), k)
        a = w.hist0 + rng.randrange(0, 400) * DAY
        w.team_handles.append({"handle": h, "team": tm, "frm": a, "to": a + rng.randrange(30, 500) * DAY})
        k += 1
    w.moving_handles = moves


def _people(w, rng):
    w.people = []
    used = set()
    eid = 1001
    for tm in TEAMS:
        for _ in range(4):
            while True:
                fn, ln = rng.choice(FIRST), rng.choice(LAST)
                if (fn, ln) not in used:
                    used.add((fn, ln))
                    break
            uid = (fn[0] + ln).lower()
            p = {"eid": "E%d" % eid, "uid": uid, "cn": fn + " " + ln, "team": tm,
                 "primary": "%s.%s@quillfen.example" % (fn.lower(), ln.lower()),
                 "aliases": ["%s@quillfen.example" % uid],
                 "handles": ["pg-" + uid]}
            if rng.random() < 0.5:
                p["aliases"].append("%s@qf-legacy.example" % uid)
            if rng.random() < 0.3:
                p["late_alias"] = "%s.%s@corp.quillfen.example" % (fn[0].lower(), ln.lower())
            w.people.append(p)
            eid += 1
    w.person_by_eid = {p["eid"]: p for p in w.people}
    w.team_people = {tm: [p for p in w.people if p["team"] == tm] for tm in TEAMS}


def _hosts(w, rng):
    w.hosts = []
    w.host_zone = {}
    for pool in POOLS:
        for i in range(1, 6):
            h = "wk-%s-%02d" % (pool, i)
            z = rng.choice(["UTC", "America/New_York", "Europe/Berlin", "Asia/Kolkata"])
            w.hosts.append({"host": h, "pool": pool, "zone": z, "frm": -INF, "to": INF})
            w.host_zone[h] = [(-INF, INF, z)]
    for i in range(1, 5):
        h = "cronhost-%d" % i
        w.hosts.append({"host": h, "pool": "legacy", "zone": "America/Los_Angeles", "frm": -INF, "to": INF})
        w.host_zone[h] = [(-INF, INF, "America/Los_Angeles")]
    for i in range(1, 4):
        h = "nn-%d" % i
        z = ["Europe/Berlin", "America/Chicago", "Asia/Tokyo"][i - 1]
        w.hosts.append({"host": h, "pool": "namenode", "zone": z, "frm": -INF, "to": INF})
        w.host_zone[h] = [(-INF, INF, z)]
    for i in range(1, 3):
        h = "partner-sftp-%d" % i
        w.hosts.append({"host": h, "pool": "partner", "zone": "Asia/Kolkata", "frm": -INF, "to": INF})
        w.host_zone[h] = [(-INF, INF, "Asia/Kolkata")]
    # a host that moved zones inside the period (namenode relocation)
    cut = w.p0 + 11 * DAY + 3 * 3600
    w.hosts = [h for h in w.hosts if h["host"] != "nn-2"]
    w.hosts.append({"host": "nn-2", "pool": "namenode", "zone": "America/Chicago", "frm": -INF, "to": cut})
    w.hosts.append({"host": "nn-2", "pool": "namenode", "zone": "America/New_York", "frm": cut, "to": INF})
    w.host_zone["nn-2"] = [(-INF, cut, "America/Chicago"), (cut, INF, "America/New_York")]
    # padding: retired hosts
    k = 0
    while len(w.hosts) < 215:
        pool = rng.choice(POOLS)
        a = w.hist0 + rng.randrange(0, 700) * DAY
        w.hosts.append({"host": "wk-%s-r%03d" % (pool, k), "pool": pool, "zone": rng.choice(["UTC", "Europe/Berlin"]),
                        "frm": a, "to": a + rng.randrange(40, 300) * DAY})
        k += 1


def zone_of_host(w, host, t):
    for a, b, z in w.host_zone.get(host, [(-INF, INF, "UTC")]):
        if a <= t < b:
            return z
    return "UTC"


# ------------------------------------------------------------------ jobs
def _cron_for(w, rng, cadence, zone, dst_bias):
    dst = DST_HOURS.get(zone)
    m = rng.choice([0, 5, 10, 15, 20, 30, 45])
    if cadence == "hourly":
        return "%d * * * *" % rng.choice([0, 7, 30, 45])
    if cadence == "four.hourly":
        return "%d %s * * *" % (m, rng.choice(["*/4", "1-23/4", "2-22/4"]))
    hour = rng.choice(dst) if (dst and dst_bias) else rng.choice([0, 3, 4, 5, 6, 7, 9, 11, 13, 17, 19, 22])
    if cadence == "daily":
        return "%d %d * * *" % (m, hour)
    if cadence == "weekday":
        return "%d %d * * %s" % (m, hour, rng.choice(["1-5", "MON-FRI", "1,2,3,4,5"]))
    if cadence == "twice.monthly":
        if "dom_dow" in w.F:
            return "%d %d %s * %s" % (m, hour, rng.choice(["1,15", "1-7", "10,20"]), rng.choice(["1", "SUN", "5", "0"]))
        return "%d %d 1,15 * *" % (m, hour)
    return "%d %d * * %s" % (m, hour, rng.choice(["0", "7", "SUN", "6"]))


def _jobs(w, rng):
    w.jobs = []       # list of dict: family, names [(name, frm)], specs
    w.renames = []    # {old,new,at}
    names_used = set()
    n = 0
    for fam in FAMILIES:
        count = w.P["jobs"][fam]
        cad_pool = ["hourly"] * 1 + ["four.hourly"] * 3 + ["daily"] * 7 + ["weekday"] * 3 + ["twice.monthly"] * 2 + ["weekly"] * 2
        for i in range(count):
            while True:
                name = "%s.%s.%s" % (rng.choice(STAGES), rng.choice(DOMAINS), rng.choice(cad_pool))
                if name not in names_used:
                    break
            names_used.add(name)
            cadence = name.split(".", 2)[2]
            zone = rng.choice(FAMILY_ZONES[fam])
            created = w.hist0 + rng.randrange(0, 1000) * DAY + rng.randrange(0, 86400)
            job = {"id": n, "family": fam, "names": [[name, -INF]], "created": created, "cadence": cadence,
                   "zone": zone, "specs": [], "team": rng.choice(FAMILY_TEAMS[fam])}
            n += 1
            # spec revisions: history then maybe in-period change
            revs = []
            t = created
            dst_bias = ("dst" in w.F) and rng.random() < 0.45 and cadence in ("daily", "weekday", "weekly", "twice.monthly")
            cron = _cron_for(w, rng, cadence, zone, dst_bias)
            sla = rng.choice([30, 45, 60, 90, 120, 180, 240]) if cadence != "hourly" else rng.choice([20, 30, 40])
            tier = rng.choice([1, 2, 2, 3, 3])
            enabled = True
            nrev = rng.randrange(6, 10)
            for r in range(nrev):
                revs.append({"rev_at": t, "cron": cron, "zone": zone, "sla_minutes": sla, "tier": tier, "enabled": enabled})
                t = t + rng.randrange(20, 160) * DAY + rng.randrange(0, 86400)
                if t >= w.p0 - 5 * DAY:
                    break
                ch = rng.random()
                if ch < 0.3:
                    sla = rng.choice([30, 45, 60, 90, 120, 180]) if cadence != "hourly" else rng.choice([20, 30, 40])
                elif ch < 0.5:
                    tier = rng.choice([1, 2, 3])
                elif ch < 0.65:
                    cron = _cron_for(w, rng, cadence, zone, dst_bias)
                elif ch < 0.72:
                    enabled = False
                else:
                    enabled = True
            revs[-1]["enabled"] = True if rng.random() < 0.95 else False
            if rng.random() < 0.22:
                # in-period revision exactly on a would-be fire boundary
                mid = w.p0 + rng.randrange(4, 26) * DAY
                zone2 = zone
                c2 = _cron_for(w, rng, cadence, zone2, dst_bias)
                fires = cron_fires(w.zt, Cron(revs[-1]["cron"]), zone, mid, mid + 2 * DAY)
                at = fires[0] if fires else mid
                revs.append({"rev_at": at, "cron": c2, "zone": zone2, "sla_minutes": revs[-1]["sla_minutes"],
                             "tier": revs[-1]["tier"], "enabled": True})
            job["specs"] = revs
            w.jobs.append(job)
    # renames
    period_rename = []
    for job in w.jobs:
        r = rng.random()
        hops = 0
        if r < 0.30:
            hops = 1
        elif r < 0.42 and "rename_chain" in w.F:
            hops = 2
        t = job["created"] + rng.randrange(30, 400) * DAY
        for hnum in range(hops):
            if hnum == hops - 1 and rng.random() < 0.35:
                t = w.p0 + rng.randrange(2, 27) * DAY + rng.randrange(0, 86400)
            elif t > w.p0:
                t = w.p0 - rng.randrange(10, 60) * DAY
            old = job["names"][-1][0]
            parts = old.split(".")
            while True:
                new = "%s.%s.%s" % (rng.choice(STAGES), parts[1] if rng.random() < 0.6 else rng.choice(DOMAINS), ".".join(parts[2:]))
                if new not in names_used:
                    break
            names_used.add(new)
            if job["names"][-1][1] >= t:
                t = job["names"][-1][1] + DAY
            job["names"].append([new, t])
            w.renames.append({"old": old, "new": new, "at": t, "job": job["id"]})
            if w.p0 <= t < w.p1:
                period_rename.append(job)
            t = t + rng.randrange(60, 300) * DAY
            if t > w.p1:
                break
    # future-dated rename (after period end)
    for job in rng.sample(w.jobs, 3):
        old = job["names"][-1][0]
        new = old + ".v2"
        if new in names_used:
            continue
        at = w.p1 + rng.randrange(2, 20) * DAY
        names_used.add(new)
        job["names"].append([new, at])
        w.renames.append({"old": old, "new": new, "at": at, "job": job["id"]})
    # key reuse: a new job introduced under a name another job left
    w.reused = []
    if "key_reuse" in w.F:
        cands = [j for j in w.jobs if len(j["names"]) > 1 and j["names"][1][1] < w.p0 - 20 * DAY]
        for src in rng.sample(cands, min(3, len(cands))):
            old_name = src["names"][0][0]
            at = w.p0 + rng.randrange(5, 20) * DAY + rng.randrange(0, 86400)
            fam = src["family"]
            job = {"id": len(w.jobs), "family": fam, "names": [[old_name, at]], "created": at,
                   "cadence": src["cadence"], "zone": src["zone"], "team": src["team"],
                   "specs": [{"rev_at": at, "cron": _cron_for(w, rng, src["cadence"], src["zone"], False),
                              "zone": src["zone"], "sla_minutes": 60, "tier": 2, "enabled": True}], "introduced": True}
            w.jobs.append(job)
            w.renames.append({"old": "", "new": old_name, "at": at, "job": job["id"]})
            w.reused.append((src["id"], job["id"], old_name, at))
    # retired padding jobs so each spec file carries history
    for fam in FAMILIES:
        for i in range(max(2, int(4 * w.P["scale"]))):
            name = "retired.%s.%s%d.daily" % (FAMILY_PREFIX[fam], rng.choice(DOMAINS), i)
            if name in names_used:
                continue
            names_used.add(name)
            created = w.hist0 + rng.randrange(0, 300) * DAY
            specs = []
            t = created
            for r in range(8):
                specs.append({"rev_at": t, "cron": "0 4 * * *", "zone": FAMILY_ZONES[fam][0], "sla_minutes": 60,
                              "tier": 3, "enabled": r < 7})
                t += rng.randrange(20, 60) * DAY
            w.jobs.append({"id": len(w.jobs), "family": fam, "names": [[name, -INF]], "created": created,
                           "cadence": "daily", "zone": FAMILY_ZONES[fam][0], "team": FAMILY_TEAMS[fam][0],
                           "specs": specs, "retired": True})
    w.job_by_id = {j["id"]: j for j in w.jobs}


def name_at(job, t):
    cur = job["names"][0][0]
    for name, frm in job["names"]:
        if frm <= t:
            cur = name
    return cur


def _datasets(w, rng):
    w.producers = []
    w.job_dataset = {}
    used = set()
    for job in w.jobs:
        base = job["names"][0][0].split(".")
        ds = "%s.%s_%s" % (FAMILY_PREFIX[job["family"]], base[1], "_".join(base[2:]).replace(".", "_"))
        k = 1
        while ds in used:
            ds = ds + str(k)
            k += 1
        used.add(ds)
        w.job_dataset[job["id"]] = [(-INF, INF, ds)]
        w.producers.append({"dataset": ds, "job": job["id"], "frm": job["created"] - DAY, "to": INF})
    # historical rows for datasets replaced long ago
    k = 0
    while len(w.producers) < 205:
        job = rng.choice(w.jobs)
        ds = "hist.%s_%d" % (rng.choice(DOMAINS), k)
        a = w.hist0 + rng.randrange(0, 600) * DAY
        w.producers.append({"dataset": ds, "job": job["id"], "frm": a, "to": a + rng.randrange(30, 200) * DAY})
        k += 1
    if "orphans" in w.F:
        for i in range(12):
            w.producers.append({"dataset": "lake.shadow_%d" % i, "job": None, "unknown_key": unknown_name(w, rng, i),
                                "frm": w.p0 - 100 * DAY, "to": INF})
    # ambiguous overlap inside the period
    w.ambiguous = []
    if "ambiguous" in w.F:
        live = [j for j in w.jobs if not j.get("retired") and not j.get("introduced") and j["cadence"] in ("daily", "four.hourly")]
        for a_job, b_job in [tuple(rng.sample(live, 2)) for _ in range(2)]:
            ds = w.job_dataset[a_job["id"]][0][2]
            s = w.p0 + rng.randrange(6, 22) * DAY
            e = s + rng.randrange(1, 3) * DAY
            w.producers.append({"dataset": ds, "job": b_job["id"], "frm": s, "to": e})
            w.ambiguous.append((ds, a_job["id"], b_job["id"], s, e))


def _deps(w, rng):
    live = [j for j in w.jobs if not j.get("retired")]
    order = list(live)
    rng.shuffle(order)
    rank = {j["id"]: i for i, j in enumerate(order)}
    w.rank = rank
    w.deps = []
    for j in order:
        r = rank[j["id"]]
        if r == 0:
            continue
        k = rng.choice([0, 1, 1, 2, 2, 3])
        ups = rng.sample(order[:r], min(k, r))
        for u in ups:
            lag = rng.choice([0] * 8 + [1] * 3 + [2])
            frm, to = -INF, INF
            x = rng.random()
            if x < 0.08:
                frm = w.p0 + rng.randrange(3, 20) * DAY
            elif x < 0.14:
                to = w.p0 + rng.randrange(5, 25) * DAY
            w.deps.append({"down": j["id"], "up": u["id"], "lag": lag, "frm": frm, "to": to})
    if "orphans" in w.F:
        for i in range(12):
            j = rng.choice(order)
            w.deps.append({"down": j["id"], "up": None, "unknown_key": unknown_name(w, rng, i), "lag": 0, "frm": -INF, "to": INF})
    if "upstream" in w.F:
        pairs = [e for e in w.deps if e.get("up") is not None and e["lag"] == 0 and e["frm"] == -INF and e["to"] == INF]
        rng.shuffle(pairs)
        done = 0
        for e in pairs:
            d, u = w.job_by_id[e["down"]], w.job_by_id[e["up"]]
            if d["cadence"] == u["cadence"] and d["cadence"] in ("daily", "four.hourly", "hourly", "weekday"):
                d["specs"][-1]["cron"] = u["specs"][-1]["cron"]
                d["specs"][-1]["zone"] = u["specs"][-1]["zone"]
                done += 1
            if done >= max(3, int(10 * w.P["scale"])):
                break
    k = 0
    while len(w.deps) < 210:
        a, b = rng.sample(order, 2)
        if rank[a["id"]] < rank[b["id"]]:
            a, b = b, a
        s = w.hist0 + rng.randrange(0, 700) * DAY
        w.deps.append({"down": a["id"], "up": b["id"], "lag": 0, "frm": s, "to": s + rng.randrange(20, 200) * DAY})
        k += 1


def _ownership(w, rng):
    w.own_commits = []
    t = w.hist0 + 5 * DAY
    lines = []
    changes = []
    for fam in FAMILIES:
        for tm in FAMILY_TEAMS[fam]:
            pass
    # initial file: family globs owned by first team
    stage_globs = sorted(set(j["names"][0][0].split(".")[0] for j in w.jobs))
    for st in stage_globs:
        tm = rng.choice(TEAMS)
        changes.append(("+", "jobs/%s.*" % st, ["@quillfen/" + tm]))
    w.own_commits.append({"at": t, "author": "E1001", "changes": changes, "msg": "Initial CODEOWNERS"})
    live = [j for j in w.jobs if not j.get("retired")]
    handles_all = sorted(set(h["handle"] for h in w.team_handles if h["frm"] == -INF))
    for i in range(230):
        t += rng.randrange(1, 6) * DAY + rng.randrange(0, 86400)
        if i > 200:
            t = w.p0 + (i - 200) * (26 * DAY // 30) + rng.randrange(0, 3600)
        job = rng.choice(live)
        nm = name_at(job, t)
        r = rng.random()
        ch = []
        if r < 0.55:
            hs = ["@" + h for h in rng.sample(handles_all, rng.choice([1, 1, 1, 2, 3]))]
            ch.append(("+", "jobs/" + nm, hs))
        elif r < 0.75:
            dom = nm.split(".")[1]
            ch.append(("+", "jobs/*.%s.*" % dom, ["@quillfen/" + rng.choice(TEAMS)]))
        else:
            # remove a previously added exact line
            prior = [c for cm in w.own_commits for c in cm["changes"] if c[0] == "+"]
            if prior:
                p = rng.choice(prior)
                ch.append(("-", p[1], p[2]))
            else:
                ch.append(("+", "jobs/" + nm, ["@quillfen/" + job["team"]]))
        w.own_commits.append({"at": t, "author": rng.choice(w.people)["eid"], "changes": ch,
                              "msg": "Update ownership for %s" % nm})
    # decoy: identical re-adds are appended as distinct lines (last match wins still applies)


def _calendars(w, rng):
    zt = w.zt
    w.freeze = []
    w.freeze_overrides = []
    uid = 0
    # weekend freeze series for tier 3 (Berlin wall clock)
    y0 = ymd(w.p0)[0]
    for year in range(y0 - 3, y0 + 1):
        for zone, tiers, dow, hh, dur_h in [("Europe/Berlin", [3], "SA", 22, 30), ("America/New_York", [2, 3], "FR", 23, 6),
                                             ("Asia/Tokyo", [1, 2, 3], "WE", 4, 2)]:
            uid += 1
            cur_start = w.p0 - 120 * DAY - (w.p0 - 120 * DAY) % DAY + hh * 3600
            start = civil(year, 1, 2, hh) if year < y0 else cur_start
            # align to weekday
            while fields(start)[6] != {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}[dow]:
                start += DAY
            until = min(civil(year, 12, 31, 23, 59, 59), cur_start - DAY) if year < y0 else None
            if until is not None and until <= start:
                continue
            rule = "FREQ=WEEKLY;BYDAY=%s" % dow + (";UNTIL=%s" % iso(until).replace("-", "").replace(":", "") if until else "")
            s = {"uid": "freeze-%04d@quillfen" % uid, "zone": zone, "start_local": start, "end_local": start + dur_h * 3600,
                 "rrule": rule, "exdates_local": [], "tiers": tiers, "summary": "Change freeze %s" % zone,
                 "until": until}
            if year == y0 and "freeze" in w.F:
                occ = expand_rrule(start, parse_rrule("FREQ=WEEKLY;BYDAY=%s" % dow), w.p1 + 10 * DAY)
                inp = [o for o in occ if w.p0 - DAY <= o < w.p1]
                if inp:
                    ex = rng.sample(inp, min(len(inp), 2))
                    hist = [o for o in occ if o < w.p0 - 7 * DAY]
                    picked = sorted(rng.sample(hist, min(7, len(hist))))
                    s["exdates_local"] = sorted(ex) + (picked if "ics_fold" in w.F else [])
                    rest = [o for o in inp if o not in ex]
                    if rest:
                        o = rng.choice(rest)
                        w.freeze_overrides.append({"uid": s["uid"], "rid_local": o, "cancelled": False,
                                                   "start_local": o + 2 * 3600, "end_local": o + (dur_h + 3) * 3600,
                                                   "zone": zone})
                        rest2 = [x for x in rest if x != o]
                        if rest2:
                            w.freeze_overrides.append({"uid": s["uid"], "rid_local": rng.choice(rest2), "cancelled": True,
                                                       "start_local": None, "end_local": None, "zone": zone})
            w.freeze.append(s)
    # one-off freezes history + period
    while len(w.freeze) + len(w.freeze_overrides) < 215:
        uid += 1
        zone = rng.choice(["UTC", "Europe/Berlin", "America/Chicago"])
        if len(w.freeze) % 25 == 0 and "freeze" in w.F:
            start = w.p0 + rng.randrange(3, 26) * DAY + rng.choice([9, 13, 18]) * 3600
        else:
            start = w.hist0 + rng.randrange(0, 1100) * DAY + rng.choice([9, 13, 18]) * 3600
        w.freeze.append({"uid": "freeze-%04d@quillfen" % uid, "zone": zone, "start_local": start,
                         "end_local": start + rng.choice([2, 3, 4]) * 3600, "rrule": "", "exdates_local": [],
                         "tiers": rng.choice([[1], [2], [1, 2], [3], [2, 3]]), "summary": "Release freeze", "until": None})
    # holidays
    w.holidays = []
    for year in range(y0 - 3, y0 + 1):
        for tm in TEAMS:
            dates = set()
            while len(dates) < 5:
                dates.add((year, rng.randrange(1, 13), rng.randrange(1, 28)))
            if year == y0 and "holiday" in w.F:
                py, pm, _ = ymd(w.p0)
                dates.add((py, pm, rng.randrange(2, 27)))
            for d in sorted(dates):
                w.holidays.append({"team": tm, "date": d, "summary": "Team holiday"})
    # rota
    w.rota = []
    w.rota_overrides = []
    for tm in TEAMS:
        zone = TEAM_ZONE[tm]
        ppl = w.team_people[tm]
        # historic series (ended) and current series
        for era in range(2):
            n = len(ppl)
            base_day = civil(y0 - 1, 1, 5, 9) if era == 0 else civil(y0 - 1, 9, 1, 9)
            while fields(base_day)[6] != 0:
                base_day += DAY
            for i, p in enumerate(ppl):
                start = base_day + i * 7 * DAY
                until = civil(y0 - 1, 8, 25) if era == 0 else None
                rule = "FREQ=WEEKLY;INTERVAL=%d;BYDAY=MO" % n
                if until:
                    rule += ";UNTIL=%s" % iso(until).replace("-", "").replace(":", "")
                email = rng.choice([p["primary"]] + p["aliases"])
                w.rota.append({"uid": "rota-%s-%d-%d@quillfen" % (tm, era, i), "team": tm, "zone": zone,
                               "start_local": start, "rrule": rule, "attendee": email, "length_days": 7,
                               "until": until})
                if era == 1:
                    occ = expand_rrule(start, parse_rrule(rule), w.p1 + 14 * DAY)
                    inp = [o for o in occ if w.p0 - 7 * DAY <= o < w.p1]
                    hist = [o for o in occ if o < w.p0 - 7 * DAY]
                    for o in rng.sample(hist, min(len(hist), 3)):
                        other = rng.choice([q for q in ppl if q is not p])
                        w.rota_overrides.append({"uid": w.rota[-1]["uid"], "rid_local": o, "cancelled": False,
                                                 "attendee": other.get("late_alias") or other["aliases"][0]})
                    for o in inp:
                        x = rng.random()
                        if x < 0.35:
                            other = rng.choice([q for q in ppl if q is not p])
                            w.rota_overrides.append({"uid": w.rota[-1]["uid"], "rid_local": o, "cancelled": False,
                                                     "attendee": other.get("late_alias") or other["aliases"][0]})
                        elif x < 0.45:
                            w.rota_overrides.append({"uid": w.rota[-1]["uid"], "rid_local": o, "cancelled": True,
                                                     "attendee": None})
    while len(w.rota) + len(w.rota_overrides) < 210:
        tm = rng.choice(TEAMS)
        p = rng.choice(w.team_people[tm])
        start = civil(y0 - 3, 1, 1, 9) + rng.randrange(0, 500) * DAY
        while fields(start)[6] != 0:
            start += DAY
        until = start + 70 * DAY
        w.rota.append({"uid": "rota-archive-%d@quillfen" % len(w.rota), "team": tm, "zone": TEAM_ZONE[tm],
                       "start_local": start, "rrule": "FREQ=WEEKLY;COUNT=%d;BYDAY=MO" % rng.randrange(2, 9),
                       "attendee": p["primary"], "length_days": 7, "until": None})


def _pauses(w, rng):
    w.pauses = []
    live = [j for j in w.jobs if not j.get("retired")]
    for i in range(70):
        job = rng.choice(live)
        a = w.hist0 + rng.randrange(0, 1100) * DAY + rng.randrange(0, 86400)
        b = a + rng.randrange(3600, 5 * DAY)
        who = rng.choice(w.people)["handles"][0]
        w.pauses.append({"job": job["id"], "at": a, "action": "pause", "actor": who})
        w.pauses.append({"job": job["id"], "at": b, "action": "unpause", "actor": who})
    if "pause" in w.F:
        for i in range(22):
            job = rng.choice(live)
            a = w.p0 + rng.randrange(1, 27) * DAY + rng.randrange(0, 86400)
            b = a + rng.randrange(2 * 3600, 3 * DAY)
            who = rng.choice(w.people)["handles"][0]
            w.pauses.append({"job": job["id"], "at": a, "action": "pause", "actor": who})
            if i % 4 == 0:
                w.pauses.append({"job": job["id"], "at": a + 1800, "action": "pause", "actor": who})
            w.pauses.append({"job": job["id"], "at": b, "action": "unpause", "actor": who})
    if "orphans" in w.F:
        for i in range(12):
            a = w.p0 + rng.randrange(1, 27) * DAY + rng.randrange(0, 86400)
            w.pauses.append({"job": None, "unknown_key": unknown_name(w, rng, i), "at": a, "action": "pause",
                             "actor": rng.choice(w.people)["handles"][0]})
        for i in range(14):
            job = rng.choice(live)
            a = w.p0 + rng.randrange(1, 27) * DAY + rng.randrange(0, 86400)
            w.pauses.append({"job": job["id"], "at": a, "action": "unpause", "actor": rng.choice(w.people)["handles"][0],
                             "orphan_candidate": True})


def _sla_overrides(w, rng):
    w.sla_overrides = []
    live = [j for j in w.jobs if not j.get("retired")]
    for i in range(170):
        job = rng.choice(live)
        at = w.hist0 + rng.randrange(0, 1100) * DAY
        w.sla_overrides.append({"job": job["id"], "at": at, "value": rng.choice([15, 30, 60, 90, 120, None])})
    if "orphans" in w.F:
        for i in range(12):
            w.sla_overrides.append({"job": None, "unknown_key": unknown_name(w, rng, i), "at": w.p0 - rng.randrange(1, 90) * DAY, "value": 30})
    for i in range(45):
        job = rng.choice([j for j in live if j["cadence"] != "hourly"])
        at = w.p0 - rng.randrange(1, 40) * DAY if i % 3 else w.p0 + rng.randrange(1, 25) * DAY
        v = rng.choice([0, 0, None, 45, 120]) if "sla_zero" in w.F else rng.choice([None, 45, 120])
        w.sla_overrides.append({"job": job["id"], "at": at, "value": v})


def _ratecard(w, rng):
    w.ratecard = []
    y0 = ymd(w.p0)[0]
    tricky = ["0.29", "0.57", "1.15", "2.01", "4.35", "0.58", "1.13", "8.2", "12.5", "3.07", "0.07", "19.99"]
    plain = ["0.25", "0.5", "1", "2", "5", "10", "12", "20", "0.75", "1.5"]
    for year in range(y0 - 2, y0 + 1):
        for month in range(1, 13):
            frm = civil(year, month, 1)
            if frm > w.p1:
                break
            for tier in (1, 2, 3):
                for bucket in ("B0", "B30", "B120"):
                    pool = tricky if "decimal" in w.F else plain
                    small = ["0.07", "0.29", "0.57", "0.58", "1.13", "1.15", "0.2"] if "decimal" in w.F else ["0.25", "0.5", "1", "0.75"]
                    w.ratecard.append({"tier": tier, "bucket": bucket, "frm": frm,
                                       "base": rng.choice(pool) if bucket != "B0" else rng.choice(["0", "1", "2.5", "0.57"] if "decimal" in w.F else ["0", "1", "2.5"]),
                                       "per_min": rng.choice(small)})
    mid = w.p0 + rng.randrange(8, 20) * DAY + rng.randrange(0, 86400)
    for tier in (1, 2, 3):
        for bucket in ("B0", "B30", "B120"):
            w.ratecard.append({"tier": tier, "bucket": bucket, "frm": mid,
                               "base": rng.choice(tricky if "decimal" in w.F else plain),
                               "per_min": rng.choice(["0.29", "0.57", "1.15"] if "decimal" in w.F else ["0.5", "1"])})
    w.rate_change = mid


# ------------------------------------------------------------------ simulation
def _structured_config(w):
    """Build the structured config part used by the reference to derive commitments."""
    D = {"period": (w.p0, w.p1), "tz_rows": w.tz_rows, "tz_links": w.tz_links, "malformed": []}
    D["renames"] = [dict(r, old=r["old"], new=r["new"], ord=i, src="job_renames.csv") for i, r in enumerate(w.renames)]
    specs = []
    for job in w.jobs:
        for s in job["specs"]:
            specs.append({"key": name_at(job, s["rev_at"]), "rev_at": s["rev_at"], "cron": s["cron"], "zone": s["zone"],
                          "sla_minutes": s["sla_minutes"], "tier": s["tier"], "enabled": s["enabled"],
                          "family": job["family"], "job": job["id"]})
    D["specs"] = specs
    return D


def _simulate(w, rng):
    zt = w.zt
    D = _structured_config(w)
    ident = Identity(D["renames"], [s["key"] for s in D["specs"]], w.p1)
    w.ident = ident
    # map world job id -> identity index
    w.jidx = {}
    for s in D["specs"]:
        w.jidx[s["job"]] = ident.resolve(s["key"], s["rev_at"])
    # expand fires: the prior month feeds the sensor wait record, the rest the settlement evidence
    lo, hi = w.p0 - 35 * DAY, w.p1 + 2 * DAY
    fires = []
    for job in w.jobs:
        if job.get("retired"):
            continue
        revs = job["specs"]
        for i, s in enumerate(revs):
            a = s["rev_at"]
            b = revs[i + 1]["rev_at"] if i + 1 < len(revs) else INF
            if not s["enabled"]:
                continue
            a2, b2 = max(a, lo), min(b, hi)
            if a2 >= b2:
                continue
            for t in cron_fires(zt, Cron(s["cron"]), s["zone"], a2, b2, "clamp", "second", "or"):
                sla = _sla_true(w, job, t, s["sla_minutes"])
                fires.append((t, job["id"], sla, s["tier"]))
    fires.sort()
    w.fires = fires
    fires_by_job = {}
    for t, jid, sla, tier in fires:
        fires_by_job.setdefault(jid, []).append(t)
    w.fires_by_job = fires_by_job

    # dependency waits (true reading: strictly earlier, lag counts back)
    dep_by_down = {}
    for e in w.deps:
        if e.get("up") is not None:
            dep_by_down.setdefault(e["down"], []).append(e)

    def governing_ups(jid, t):
        out = []
        for e in dep_by_down.get(jid, []):
            if not (e["frm"] <= t < e["to"]):
                continue
            noms = fires_by_job.get(e["up"], [])
            idx = bisect.bisect_left(noms, t) - 1 - e["lag"]
            if idx >= 0:
                out.append((e["up"], noms[idx], e["lag"]))
        return out

    w.governing_ups = governing_ups
    w.sensor = []
    for t, jid, sla, tier in fires:
        if not (w.p0 - 28 * DAY <= t < w.p0):
            continue
        wroll = random.Random(_h("wait", w.P["seed"], jid, t))
        job = w.job_by_id[jid]
        for u, un, lag in governing_ups(jid, t):
            if wroll.random() < 0.6:
                w.sensor.append({"down": name_at(job, t), "down_nominal": t, "up": name_at(w.job_by_id[u], t),
                                 "up_nominal": un, "lag": lag, "at": t + wroll.randrange(30, 3000)})
    landed = {}
    w.sched = []
    w.workers = []
    w.landings = []
    w.retracts = []
    w.operator = []
    w.approvals = []
    w.backfills = []
    run_seq = 0
    host_by_pool = {p: ["wk-%s-%02d" % (p, i) for i in range(1, 6)] for p in POOLS}
    systems_by_ds = {}
    for job in w.jobs:
        ds = w.job_dataset[job["id"]][0][2]
        r = _h(ds, w.P["seed"])
        systems_by_ds[ds] = [LANDING_SYSTEMS[int(r[:4], 16) % 5]]
        if int(r[4:6], 16) % 7 == 0:
            systems_by_ds[ds].append(LANDING_SYSTEMS[(int(r[:4], 16) + 1) % 5])
    w.systems_by_ds = systems_by_ds
    feat = w.F
    for t, jid, sla, tier in fires:
        if t < w.p0 - 9 * DAY:
            continue
        job = w.job_by_id[jid]
        fam = job["family"]
        ds = w.job_dataset[jid][0][2]
        key = name_at(job, t)
        deadline = t + sla * 60
        in_focus = w.p0 + DAY <= t < w.p1 - DAY
        roll = random.Random(_h("fire", w.P["seed"], jid, t))
        run_seq += 1
        run_id = "sch-%s" % _h(jid, t)[:10]
        # upstream wait
        start = t + roll.randrange(5, 90)
        for u, un, lag in governing_ups(jid, t):
            la = landed.get((u, un))
            if la is not None and la > start and la < t + 6 * 3600:
                start = la + roll.randrange(20, 200)
        down = roll.random() < 0.015
        outcome = roll.random()
        late = roll.random() < 0.14
        duration = int(sla * 60 * (roll.uniform(1.05, 2.4) if late else roll.uniform(0.15, 0.85)))
        pool = POOLS[int(_h(jid)[:2], 16) % 6]
        host = host_by_pool[pool][roll.randrange(0, 5)]
        region = FAMILY_REGION[fam]
        transitions = []
        if down:
            pass
        else:
            q = start
            transitions.append(("queued", q))
            r1 = q + roll.randrange(2, 60)
            transitions.append(("running", r1))
            w.workers.append({"pool": pool, "host": host, "run_id": run_id, "key": key, "nominal": t, "event": "start", "at": r1 + 1})
            fail_first = roll.random() < 0.08
            cur = r1
            if fail_first:
                f = cur + roll.randrange(60, 900)
                transitions.append(("failed", f))
                w.workers.append({"pool": pool, "host": host, "run_id": run_id, "key": key, "nominal": t, "event": "fail", "at": f - 1})
                transitions.append(("up_for_retry", f + 1))
                transitions.append(("queued", f + roll.randrange(30, 300)))
                cur = transitions[-1][1] + roll.randrange(2, 40)
                transitions.append(("running", cur))
            end = cur + duration
            hard_fail = roll.random() < 0.035
            if hard_fail:
                transitions.append(("failed", end))
                w.workers.append({"pool": pool, "host": host, "run_id": run_id, "key": key, "nominal": t, "event": "fail", "at": end - 2})
            else:
                commit = end - roll.randrange(1, 20)
                transitions.append(("success", end))
                w.workers.append({"pool": pool, "host": host, "run_id": run_id, "key": key, "nominal": t, "event": "commit", "at": commit})
                x = roll.random()
                if fam == "finance" and "eu_local" not in feat and 0.93 <= x < 0.97:
                    x = 0.5
                if "bucket_edge" in feat and in_focus and late and roll.random() < 0.1:
                    x = 0.5
                    edge_land = deadline + roll.choice([1800, 7200])
                else:
                    edge_land = None
                if x < 0.84:
                    la = commit + roll.randrange(5, 120) if edge_land is None else edge_land
                    for sys_ in systems_by_ds[ds]:
                        w.landings.append({"system": sys_, "dataset": ds, "nominal": t, "at": la + (0 if sys_ == systems_by_ds[ds][0] else roll.randrange(0, 40))})
                    landed[(jid, t)] = la
                    y = roll.random()
                    if "reland" in feat and in_focus:
                        if y < 0.06:
                            w.landings.append({"system": systems_by_ds[ds][0], "dataset": ds, "nominal": t, "at": la + roll.randrange(1800, 20000)})
                        elif y < 0.10:
                            rt = la + roll.randrange(600, 9000)
                            w.retracts.append({"dataset": ds, "nominal": t, "at": rt})
                            if roll.random() < 0.8:
                                bf = "bf-%s" % _h("bf", jid, t)[:10]
                                re = rt + roll.randrange(600, 12000)
                                w.landings.append({"system": systems_by_ds[ds][0], "dataset": ds, "nominal": t, "at": re})
                                w.backfills.append({"run_id": bf, "key": key, "nominal": t, "requested_at": rt + 60,
                                                    "by": rng.choice(w.people)["handles"][0]})
                                w.workers.append({"pool": pool, "host": host, "run_id": bf, "key": key, "nominal": t, "event": "commit", "at": re - 30})
                                if not (fam == "finance" and "eu_local" not in feat):
                                    w.sched.append({"region": region, "run_id": bf, "key": key, "nominal": t, "state": "queued", "at": rt + 90, "host": "cronhost-1"})
                                    w.sched.append({"region": region, "run_id": bf, "key": key, "nominal": t, "state": "running", "at": rt + 100, "host": "cronhost-1"})
                                    w.sched.append({"region": region, "run_id": bf, "key": key, "nominal": t, "state": "success", "at": re - 10, "host": "cronhost-1"})
                                landed[(jid, t)] = re
                        elif y < 0.11:
                            w.landings.append({"system": systems_by_ds[ds][0], "dataset": ds, "nominal": t, "at": la + roll.randrange(60, 5000)})
                    if "skew" in feat and in_focus and roll.random() < 0.03:
                        pass
                elif x < 0.93:
                    landed[(jid, t)] = commit
                    if "skew" in feat and in_focus and roll.random() < 0.5:
                        # commit near the deadline so the clock correction decides MET or LATE
                        shift = deadline + roll.randrange(-70, 70) - commit
                        w.workers[-1]["at"] += shift
                        landed[(jid, t)] = w.workers[-1]["at"]
                elif x < 0.97:
                    w.workers.pop()
                    landed[(jid, t)] = end
                else:
                    w.workers.pop()
                    transitions.pop()
                    transitions.append(("failed", end))
        if not down and "state_audit" in feat and in_focus and roll.random() < 0.012 and len(transitions) > 2                 and not (fam == "finance" and "eu_local" not in feat):
            dup = transitions[1]
            transitions.append((dup[0], transitions[-1][1] + 5))
        for st, at in transitions:
            w.sched.append({"region": region, "run_id": run_id, "key": key, "nominal": t, "state": st, "at": at,
                            "host": "cronhost-%d" % (1 + int(_h(jid)[2:4], 16) % 4)})
        # operator marks when no success
        succeeded = any(st == "success" for st, _ in transitions)
        if (down or not succeeded) and in_focus and "marks" in feat and roll.random() < 0.7:
            actor = rng.choice(w.people)
            mat = deadline + roll.randrange(-3000, 3000)
            w.operator.append({"at": mat, "actor": actor["handles"][0], "action": "mark_success", "key": key, "nominal": t})
            kind = roll.random()
            approver = rng.choice([p for p in w.people if p is not actor])
            if kind < 0.35:
                w.approvals.append({"from": approver["primary"], "at": mat - roll.randrange(60, 3000), "key": key, "nominal": t})
            elif kind < 0.55:
                w.approvals.append({"from": approver["aliases"][0], "at": mat + roll.randrange(60, 3000), "key": key, "nominal": t})
            elif kind < 0.75:
                w.approvals.append({"from": actor.get("late_alias") or actor["aliases"][-1], "at": mat - roll.randrange(60, 3000), "key": key, "nominal": t})
        if in_focus and roll.random() < 0.004:
            actor = rng.choice(w.people)
            w.operator.append({"at": t + roll.randrange(3600, 7200), "actor": actor["handles"][0], "action": "clear", "key": key, "nominal": t})
    _inject_unknown(w, rng)
    # history rows for rulings (prior month) and padding
    _history_evidence(w, rng)
    _clock(w, rng)


def unknown_name(w, rng, k):
    held = set()
    for j in w.jobs:
        for n, _ in j["names"]:
            held.add(n)
    while True:
        n = "%s.%s%s.%s" % (rng.choice(STAGES), rng.choice(DOMAINS), rng.choice(["x", "2", "tmp", "old"]), rng.choice(["daily", "hourly"]))
        if n not in held:
            return n


def _inject_unknown(w, rng):
    """Records naming jobs no source defines, and partitions of datasets nobody produces."""
    if "orphans" not in w.F:
        return
    lo = w.p0 + 2 * DAY
    for region in ("us", "eu", "apac", "legacy"):
        for i in range(4):
            t = lo + rng.randrange(0, 25) * DAY + 3600 * rng.randrange(0, 24)
            key = unknown_name(w, rng, i)
            run = "sch-%s" % _h("unk", region, i, t)[:10]
            for st, dt_ in (("queued", 10), ("running", 40), ("success", 900)):
                w.sched.append({"region": region, "run_id": run, "key": key, "nominal": t, "state": st, "at": t + dt_,
                                "host": "cronhost-%d" % (1 + i % 4)})
    for pool in POOLS:
        for i in range(3):
            t = lo + rng.randrange(0, 25) * DAY + 3600 * rng.randrange(0, 24)
            w.workers.append({"pool": pool, "host": "wk-%s-%02d" % (pool, 1 + i), "run_id": "sch-%s" % _h("unkw", pool, i)[:10],
                              "key": unknown_name(w, rng, i), "nominal": t, "event": "commit", "at": t + 1200})
    for i in range(12):
        t = lo + rng.randrange(0, 25) * DAY + 5 * 3600
        key = unknown_name(w, rng, i)
        w.operator.append({"at": t + 7200, "actor": rng.choice(w.people)["handles"][0], "action": "mark_success", "key": key, "nominal": t})
        w.approvals.append({"from": rng.choice(w.people)["primary"], "at": t + 3600, "key": key, "nominal": t})
        w.backfills.append({"run_id": "bf-%s" % _h("unkb", i)[:10], "key": key, "nominal": t, "requested_at": t + 86400,
                            "by": rng.choice(w.people)["handles"][0]})
    systems = ["objectstore", "hdfs", "warehouse", "catalog", "partner"]
    for i in range(15):
        t = lo + rng.randrange(0, 25) * DAY + 6 * 3600
        ds = "scratch.tmp_%s_%d" % (rng.choice(DOMAINS), i)
        w.landings.append({"system": systems[i % 5], "dataset": ds, "nominal": t, "at": t + 1500})
    for i in range(3):
        t = lo + rng.randrange(0, 25) * DAY + 6 * 3600
        w.retracts.append({"dataset": "scratch.tmp_orphan_%d" % i, "nominal": t, "at": t + 4000})


def _sla_true(w, job, t, base):
    cur = None
    for o in sorted(w.sla_overrides, key=lambda o: o["at"]):
        if o.get("job") != job["id"] or o["at"] > t:
            continue
        cur = o["value"]
    return base if cur is None else cur


def _history_evidence(w, rng):
    """Prior-month disputes that the review board ruled on; their raw records ship too."""
    w.rulings = []
    pm0 = w.p0 - 40 * DAY
    live = [j for j in w.jobs if not j.get("retired") and not j.get("introduced")]
    rid = 0
    used = set()

    def fresh(hour):
        while True:
            job = rng.choice(live)
            t = pm0 + rng.randrange(0, 30) * DAY + hour * 3600
            if (job["id"], t) not in used:
                used.add((job["id"], t))
                return job, t
    # re-land disputes
    for i in range(64):
        job, t = fresh(4)
        ds = w.job_dataset[job["id"]][0][2]
        la = t + rng.randrange(600, 5000)
        sys_ = w.systems_by_ds[ds][0]
        w.landings.append({"system": sys_, "dataset": ds, "nominal": t, "at": la})
        kind = i % 4
        accepted = None
        if kind == 0:
            w.landings.append({"system": sys_, "dataset": ds, "nominal": t, "at": la + rng.randrange(3000, 9000)})
            outcome, accepted = "original_landing_upheld", la
        elif kind == 1:
            rt = la + rng.randrange(1000, 4000)
            re_ = rt + rng.randrange(1000, 8000)
            w.retracts.append({"dataset": ds, "nominal": t, "at": rt})
            w.landings.append({"system": sys_, "dataset": ds, "nominal": t, "at": re_})
            outcome, accepted = "relanding_upheld", re_
        elif kind == 2:
            rt = la + rng.randrange(1000, 4000)
            re1 = rt + rng.randrange(1000, 8000)
            w.retracts.append({"dataset": ds, "nominal": t, "at": rt})
            w.landings.append({"system": sys_, "dataset": ds, "nominal": t, "at": re1})
            w.landings.append({"system": sys_, "dataset": ds, "nominal": t, "at": rt + rng.randrange(9000, 15000)})
            outcome, accepted = "relanding_upheld", re1
        else:
            rt = la + rng.randrange(1000, 4000)
            w.retracts.append({"dataset": ds, "nominal": t, "at": rt})
            outcome = "partition_voided"
        rid += 1
        w.rulings.append({"id": "RB-%04d" % rid, "type": "re_land", "ref": "%s@%s" % (ds, iso(t)), "token": outcome,
                          "accepted_at": accepted})
    # operator mark disputes
    for i in range(60):
        job, t = fresh(7)
        key = name_at(job, t)
        actor = rng.choice(w.people)
        mat = t + rng.randrange(3600, 9000)
        w.operator.append({"at": mat, "actor": actor["handles"][0], "action": "mark_success", "key": key, "nominal": t})
        other = rng.choice([p for p in w.people if p is not actor])
        kind = i % 5
        if kind == 0:
            w.approvals.append({"from": other["primary"], "at": mat - rng.randrange(300, 3000), "key": key, "nominal": t})
            outcome = "mark_upheld"
        elif kind == 1:
            w.approvals.append({"from": other["aliases"][0], "at": mat + rng.randrange(300, 3000), "key": key, "nominal": t})
            outcome = "mark_overturned"
        elif kind == 2:
            w.approvals.append({"from": actor.get("late_alias") or actor["aliases"][-1], "at": mat - rng.randrange(300, 3000), "key": key, "nominal": t})
            outcome = "mark_overturned"
        elif kind == 3:
            outcome = "mark_overturned"
        else:
            w.approvals.append({"from": other.get("late_alias") or other["aliases"][-1], "at": mat - rng.randrange(300, 3000), "key": key, "nominal": t})
            outcome = "mark_upheld"
        rid += 1
        w.rulings.append({"id": "RB-%04d" % rid, "type": "operator_mark", "ref": "%s@%s" % (key, iso(t)), "token": outcome,
                          "accepted_at": mat if outcome == "mark_upheld" else None})
    # unrelated ruling kinds (context)
    while len(w.rulings) < 230:
        job = rng.choice(live)
        t = pm0 + rng.randrange(0, 30) * DAY
        rid += 1
        w.rulings.append({"id": "RB-%04d" % rid, "type": rng.choice(["outage_scope", "ownership", "sla_waiver"]),
                          "ref": "%s@%s" % (name_at(job, t), iso(t)),
                          "token": rng.choice(["upheld", "dismissed", "withdrawn"]), "accepted_at": None})


def _clock(w, rng):
    w.clock_samples = []
    w.heartbeats = []
    lo, hi = w.p0 - 9 * DAY, w.p1 + 2 * DAY
    w.host_offset = {}
    prom_pools = {"a", "b", "c", "d"}
    for pool in POOLS:
        for i in range(1, 6):
            host = "wk-%s-%02d" % (pool, i)
            hr = random.Random(_h("clock", w.P["seed"], host))
            gap = None
            if "uncalibrated" in w.F and host in ("wk-b-03", "wk-e-02"):
                g0 = w.p0 + hr.randrange(5, 20) * DAY
                gap = (g0, g0 + hr.randrange(2, 4) * DAY)
            skewed = "skew" in w.F
            off = hr.randrange(-4000, 4000) if skewed else 0
            hour = lo - lo % 3600
            offs = {}
            while hour < hi:
                if hr.random() < 0.04:
                    off = hr.choice([-1, 1]) * hr.randrange(40000, 95000) if skewed else 0
                elif hr.random() < 0.2:
                    off = hr.randrange(-4000, 4000) if skewed else 0
                offs[hour] = off
                if not (gap and gap[0] <= hour < gap[1]):
                    if pool in prom_pools:
                        w.clock_samples.append({"host": host, "t_ms": hour * 1000, "offset_ms": off})
                    else:
                        w.heartbeats.append({"host": host, "recv_ms": hour * 1000 + 250, "sent_ms": hour * 1000 + 250 + off})
                hour += 3600
            w.host_offset[host] = offs
    for e in w.workers:
        offs = w.host_offset.get(e["host"], {})
        hour = e["at"] - e["at"] % 3600
        off = offs.get(hour, 0)
        e["local_ms"] = e["at"] * 1000 + off


def _outages(w, rng):
    w.outages = []
    w.incidents = []
    y0 = ymd(w.p0)[0]
    gid = 0
    all_ds = sorted(set(v[0][2] for v in w.job_dataset.values()))
    for i in range(192):
        gid += 1
        a = w.hist0 + rng.randrange(0, 1100) * DAY + rng.randrange(0, 86400)
        b = a + rng.randrange(1800, 4 * 3600)
        g = "OUT-%d-%03d" % (ymd(a)[0], gid)
        w.outages.append({"guid": g, "rev": 1, "pub_at": a + 300, "a": a, "b": b, "status": "active", "title": "Degraded storage"})
        for ds in rng.sample(all_ds, 2):
            w.incidents.append({"outage": g, "dataset": ds})
    if "outage" in w.F:
        for i in range(12):
            gid += 1
            a = w.p0 + rng.randrange(2, 27) * DAY + rng.randrange(0, 86400)
            b = a + rng.randrange(2 * 3600, 8 * 3600)
            g = "OUT-%d-%03d" % (y0, gid)
            w.outages.append({"guid": g, "rev": 1, "pub_at": a + 600, "a": a, "b": b, "status": "active", "title": "Object store latency"})
            if i % 3 == 0:
                w.outages.append({"guid": g, "rev": 2, "pub_at": b + 3600, "a": a - 3600, "b": b + 2 * 3600, "status": "active", "title": "Object store latency (window corrected)"})
            if i % 5 == 4:
                w.outages.append({"guid": g, "rev": 2, "pub_at": b + 7200, "a": a, "b": b, "status": "retracted", "title": "Object store latency (retracted)"})
            # scope: datasets of jobs with deadlines in window, plus chosen downstreams
            cands = []
            for t, jid, sla, tier in w.fires:
                dl = t + sla * 60
                if a - 3600 <= dl < b + 2 * 3600:
                    cands.append(w.job_dataset[jid][0][2])
            if "outage_upstream" not in w.F:
                has_up = set(e["down"] for e in w.deps if e.get("up") is not None)
                cands = [c for c in cands if not any(w.job_dataset[j][0][2] == c for j in has_up)]
            cands = sorted(set(cands))
            for ds in rng.sample(cands, min(len(cands), 18)):
                w.incidents.append({"outage": g, "dataset": ds})


def _journals(w, rng):
    """Tick journal of past zone-transition days (practice record for wall-time handling)."""
    zt = w.zt
    w.ticks = []
    y0 = ymd(w.p0)[0]
    zones = ["America/New_York", "America/Los_Angeles", "Europe/Berlin", "Europe/London", "Australia/Sydney", "Pacific/Auckland"]
    rows = [r for r in w.tz_rows if r[0] in zones and civil(y0 - 1, 1, 1) <= r[1] < civil(y0, 1, 1)]
    live = [j for j in w.jobs if not j.get("retired")]
    for zone, frm, off in rows:
        for hour_pick in range(3):
            job = rng.choice(live)
            loc = frm + zt.offset(zone, frm - 1) * 60
            y, m, d = ymd(loc)
            hours = [1, 2] if zone.startswith("America") else ([1] if zone == "Europe/London" else [2])
            hh = hours[hour_pick % len(hours)]
            mm = rng.choice([0, 15, 30, 45])
            cron = "%d %d * * *" % (mm, hh)
            for dd in (-1, 0, 1):
                day = civil(y, m, d) + dd * DAY
                local = day + hh * 3600 + mm * 60
                fired = resolve_wall(zt, zone, local, "clamp", "second")
                yy, mo, da = ymd(day)
                w.ticks.append({"key": name_at(job, local), "zone": zone, "cron": cron,
                                "wall": "%04d-%02d-%02d %02d:%02d" % (yy, mo, da, hh, mm),
                                "fired": [iso(x) for x in fired]})
    while len(w.ticks) < 220:
        job = rng.choice(live)
        zone = rng.choice(zones)
        day = civil(y0 - 1, rng.randrange(1, 13), rng.randrange(1, 28))
        hh, mm = rng.choice([3, 6, 9, 14]), rng.choice([0, 30])
        local = day + hh * 3600 + mm * 60
        fired = resolve_wall(zt, zone, local, "clamp", "second")
        yy, mo, da = ymd(day)
        w.ticks.append({"key": name_at(job, local), "zone": zone, "cron": "%d %d * * *" % (mm, hh),
                        "wall": "%04d-%02d-%02d %02d:%02d" % (yy, mo, da, hh, mm), "fired": [iso(x) for x in fired]})

# ============================================================================ source file rendering
# Verifier-side renderer: world -> source files, plus the records a correct reading yields.

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
WDAYS = "Mon Tue Wed Thu Fri Sat Sun".split()


class Out:
    def __init__(self, w):
        self.w = w
        self.files = {}
        self.traps = {}
        self.D = {"period": (w.p0, w.p1), "tz_rows": [], "tz_links": {}, "malformed": []}
        for k in ["renames", "specs", "sla_overrides", "deps", "producers", "team_handles", "ownership",
                  "ldif_people", "ldif_mods", "vcards", "freeze", "freeze_overrides", "holidays", "rota",
                  "rota_overrides", "pauses", "sched", "workers", "clock_samples", "heartbeats", "landings",
                  "retracts", "operator", "approvals", "outages", "incidents", "backfills"]:
            self.D[k] = []

    def trap(self, f, n=1):
        self.traps[f] = self.traps.get(f, 0) + n

    def bad(self, f, ordinal):
        self.D["malformed"].append((f, ordinal, "MALFORMED_RECORD"))
        self.trap(f)


def _rng(w, name):
    return random.Random(_h("render", w.P["seed"], name))


def variant(rng, name, allow_space=True, p=0.5):
    if rng.random() > p:
        return name, False
    parts = name.split(".")
    r = rng.random()
    if r < 0.3:
        v = "-".join(parts)
    elif r < 0.55:
        v = "_".join(x.capitalize() for x in parts)
    elif r < 0.75:
        v = name.upper()
    elif r < 0.9 or not allow_space:
        v = parts[0] + "/" + ".".join(parts[1:])
    else:
        v = " " + "-".join(parts).title() + " "
    return v, v != name


def ds_variant(rng, ds, p=0.4):
    if rng.random() > p:
        return ds, False
    r = rng.random()
    if r < 0.4:
        v = ds.replace("_", "-")
    elif r < 0.7:
        v = ds.upper()
    else:
        v = ds.replace(".", "/")
    return v, v != ds


def bad_positions(rng, n, k, start=60):
    """Record ordinals (1-based, counted with the injected records) that carry malformed content."""
    start = min(start, max(2, n // 3))
    return set(rng.sample(range(start, n + k), k))


def clean_first(items, is_trap, n=50):
    head, rest = [], []
    for it in items:
        if len(head) < n and not is_trap(it):
            head.append(it)
        else:
            rest.append(it)
    return head + rest


def local_parts(zt, zone, t):
    return fields(zt.to_local(zone, t))


def wall_to_instant(zt, zone, local):
    c = zt.local_candidates(zone, local)
    return c[0] if c else None


def iso_offset(zt, zone, t, sep="T"):
    off = zt.offset(zone, t)
    y, mo, d, h, mi, s, _ = fields(t + off * 60)
    return "%04d-%02d-%02d%s%02d:%02d:%02d%s" % (y, mo, d, sep, h, mi, s, fmt_offset(off))


def compact(t):
    return iso(t).replace("-", "").replace(":", "")


# ====================================================================== render
def render(w):
    o = Out(w)
    zt = w.zt
    _tz(o, w)
    _specs(o, w)
    _renames(o, w)
    _render_deps(o, w)
    _producers(o, w)
    _sla(o, w)
    _render_ratecard(o, w)
    _render_ownership(o, w)
    _registry(o, w)
    _ldif(o, w)
    _vcf(o, w)
    _freeze(o, w)
    _holidays(o, w)
    _rota(o, w)
    _render_pauses(o, w)
    _render_hosts(o, w)
    _sched(o, w)
    _workers(o, w)
    _render_clock(o, w)
    _landing(o, w)
    _operator(o, w)
    _render_outages(o, w)
    _backfills(o, w)
    _evidence(o, w)
    return o


# ---------------------------------------------------------------------- tz
def _tz(o, w):
    f = "tz_transitions.csv"
    rng = _rng(w, f)
    lines = ["zone,effective_from,utc_offset"]
    recs = []
    for zone, frm, off in w.tz_rows:
        recs.append(("row", zone, frm, off))
    for a, b in sorted(w.tz_links.items()):
        recs.append(("link", a, b, None))
    rng.shuffle(recs)
    junk = [("junk", "Asia/Kolkata", civil(2020, 1, 1), "+5:30"), ("junk", "Mars/Olympus", None, "+01:00"),
            ("junk", "Europe/Berlin", None, "UTC+2")] * 5
    recs = clean_first(recs, lambda r: r[0] != "row")
    for i, j in enumerate(junk):
        recs.insert(60 + i * 11, j)
    o.D["tz_rows"] = []
    for idx, r in enumerate(recs, start=1):
        kind, zone, frm, off = r
        if kind == "row":
            lines.append("%s,%s,%s" % (zone, iso(frm), fmt_offset(off)))
            o.D["tz_rows"].append((zone, frm, off))
        elif kind == "link":
            lines.append("%s,,=>%s" % (zone, frm))
            o.D["tz_links"][zone] = frm
            o.trap(f)
        else:
            lines.append("%s,%s,%s" % (zone, iso(frm) if frm else "", off))
            o.bad(f, idx)
    o.files[f] = ("\n".join(lines) + "\n").encode()


# ---------------------------------------------------------------------- specs
def _spec_records(w, fam):
    out = []
    for job in w.jobs:
        if job["family"] != fam:
            continue
        for s in job["specs"]:
            out.append((job, s))
    return out


def _specs(o, w):
    zt = w.zt
    # platform TOML
    f = "jobs_platform.toml"
    rng = _rng(w, f)
    recs = sorted(_spec_records(w, "platform"), key=lambda js: (js[1]["rev_at"], js[0]["id"]))
    trapf = lambda js: js[1]["rev_at"] >= w.p0 - 40 * DAY or len(js[0]["names"]) > 1 or js[1]["zone"] in w.tz_links
    recs = clean_first(recs, trapf)
    parts = ["# Quillfen platform scheduler export", "[settlement]", "period_start = %s" % iso(w.p0),
             "period_end = %s" % iso(w.p1), ""]
    idx = 0
    bad_at = bad_positions(rng, len(recs), 12, 70)
    ri = 0
    while ri < len(recs) or idx < len(recs) + 12:
        idx += 1
        if idx in bad_at:
            parts += ["[[revision]]", 'job = "%s"' % rng.choice(recs)[0]["names"][0][0], 'effective = "soon"',
                      'schedule = "0 3 * * *"', 'zone = "UTC"', "sla_minutes = 60", "tier = 2", "enabled = true", ""]
            o.bad(f, idx)
            continue
        if ri >= len(recs):
            break
        job, s = recs[ri]
        ri += 1
        name = name_at(job, s["rev_at"])
        key, tv = variant(rng, name, p=0.3 if idx > 50 else 0)
        if tv:
            o.trap(f)
        if s["zone"] in w.tz_links or len(job["names"]) > 1:
            o.trap(f)
        parts += ["[[revision]]", 'job = "%s"' % key, "effective = %s" % iso(s["rev_at"]),
                  'schedule = "%s"' % s["cron"], 'zone = "%s"' % s["zone"], "sla_minutes = %d" % s["sla_minutes"],
                  "tier = %d" % s["tier"], "enabled = %s" % ("true" if s["enabled"] else "false"), ""]
        o.D["specs"].append({"key": norm(key), "rev_at": s["rev_at"], "cron": s["cron"], "zone": s["zone"],
                             "sla_minutes": s["sla_minutes"], "tier": s["tier"], "enabled": s["enabled"],
                             "ord": idx, "src": f})
    o.files[f] = ("\n".join(parts) + "\n").encode()

    # analytics JSON
    f = "jobs_analytics.json"
    rng = _rng(w, f)
    recs = clean_first(sorted(_spec_records(w, "analytics"), key=lambda js: (js[0]["id"], js[1]["rev_at"])), trapf)
    arr = []
    idx = 0
    bad_at = bad_positions(rng, len(recs), 12, 60)
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            arr.append({"job": rng.choice(recs)[0]["names"][0][0], "effective_ms": None, "cron": "0 1 * * *",
                        "tz": "UTC", "sla_seconds": 3600, "tier": "T2", "state": "active"})
            o.bad(f, idx)
            continue
        if ri >= len(recs):
            break
        job, s = recs[ri]
        ri += 1
        name = name_at(job, s["rev_at"])
        key, tv = variant(rng, name, p=0.3 if idx > 50 else 0)
        if tv:
            o.trap(f)
        if s["zone"] in w.tz_links or s["sla_minutes"] % 60:
            o.trap(f)
        arr.append({"job": key, "effective_ms": s["rev_at"] * 1000 + (rng.randrange(0, 999) if idx > 50 else 0),
                    "cron": s["cron"], "tz": s["zone"], "sla_seconds": s["sla_minutes"] * 60,
                    "tier": "T%d" % s["tier"], "state": "active" if s["enabled"] else "disabled"})
        o.D["specs"].append({"key": norm(key), "rev_at": s["rev_at"], "cron": s["cron"], "zone": s["zone"],
                             "sla_minutes": s["sla_minutes"], "tier": s["tier"], "enabled": s["enabled"],
                             "ord": idx, "src": f})
    o.files[f] = json.dumps({"exporter": "quillfen-analytics-scheduler", "revisions": arr}, indent=1).encode()

    # finance XML
    f = "jobs_finance.xml"
    rng = _rng(w, f)
    recs = clean_first(sorted(_spec_records(w, "finance"), key=lambda js: (js[1]["rev_at"], js[0]["id"])), trapf)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<revisions system=\"finance-scheduler\">"]
    idx = 0
    bad_at = bad_positions(rng, len(recs), 12, 60)
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            lines.append('  <revision job="%s" effective="2025-02-30T10:00:00+01:00"><schedule>0 6 * * *</schedule>'
                         "<zone>Europe/Berlin</zone><sla>PT1H</sla><tier>2</tier><enabled>yes</enabled></revision>"
                         % rng.choice(recs)[0]["names"][0][0])
            o.bad(f, idx)
            continue
        if ri >= len(recs):
            break
        job, s = recs[ri]
        ri += 1
        name = name_at(job, s["rev_at"])
        key, tv = variant(rng, name, p=0.3 if idx > 50 else 0)
        if tv:
            o.trap(f)
        zone_for_stamp = "Europe/Berlin"
        eff = iso_offset(zt, zone_for_stamp, s["rev_at"])
        if s["zone"] in w.tz_links:
            o.trap(f)
        m = s["sla_minutes"]
        dur = "PT%s%s" % (("%dH" % (m // 60)) if m >= 60 else "", ("%dM" % (m % 60)) if m % 60 else "")
        lines.append('  <revision job="%s" effective="%s"><schedule>%s</schedule><zone>%s</zone><sla>%s</sla>'
                     "<tier>%d</tier><enabled>%s</enabled></revision>"
                     % (key, eff, s["cron"], s["zone"], dur, s["tier"], "yes" if s["enabled"] else "no"))
        o.D["specs"].append({"key": norm(key), "rev_at": s["rev_at"], "cron": s["cron"], "zone": s["zone"],
                             "sla_minutes": s["sla_minutes"], "tier": s["tier"], "enabled": s["enabled"],
                             "ord": idx, "src": f})
    lines.append("</revisions>")
    o.files[f] = ("\n".join(lines) + "\n").encode()

    # legacy INI + crontab
    f = "jobs_legacy.ini"
    fc = "crontab_legacy.cron"
    rng = _rng(w, f)
    recs = clean_first(sorted(_spec_records(w, "legacy"), key=lambda js: (js[0]["id"], js[1]["rev_at"])), trapf)
    ini = ["; legacy batch scheduler job definitions", ""]
    cron_lines = ["# crontab for legacy batch hosts", "SHELL=/bin/sh", "MAILTO=\"\"", ""]
    idx = 0
    cidx = 0
    bad_at = bad_positions(rng, len(recs), 12, 60)
    ri = 0
    cron_entries = []
    while True:
        idx += 1
        if idx in bad_at:
            ini += ["[%s @ 2025-13-01 %02d:%02d:00 -0800]" % (rng.choice(recs)[0]["names"][0][0], idx // 60 % 24, idx % 60), "zone = US/Pacific",
                    "sla = 1h", "tier = 3", "disabled = no", ""]
            o.bad(f, idx)
            continue
        if ri >= len(recs):
            break
        job, s = recs[ri]
        ri += 1
        name = name_at(job, s["rev_at"])
        key, tv = variant(rng, name, allow_space=False, p=0.3 if idx > 50 else 0)
        if tv:
            o.trap(f)
        stamp = iso_offset(zt, "America/Los_Angeles", s["rev_at"], sep=" ").replace("T", " ")
        stamp = stamp[:19] + " " + stamp[19:].replace(":", "")
        m = s["sla_minutes"]
        sla = ("%dh%dm" % (m // 60, m % 60) if m % 60 else "%dh" % (m // 60)) if m >= 60 else "%dm" % m
        ini += ["[%s @ %s]" % (key, stamp), "zone = %s" % s["zone"], "sla = %s" % sla, "tier = %d" % s["tier"],
                "disabled = %s" % ("no" if s["enabled"] else "yes")]
        if idx > 50 and rng.random() < 0.25:
            ini.append("schedule_hint = %s" % rng.choice(["0 5 * * *", "15 */6 * * *", s["cron"]]))
            o.trap(f)
        ini.append("")
        cron_entries.append((s["rev_at"], name, s["cron"], idx))
        o.D["specs"].append({"key": norm(key), "rev_at": s["rev_at"], "cron": s["cron"], "zone": s["zone"],
                             "sla_minutes": s["sla_minutes"], "tier": s["tier"], "enabled": s["enabled"],
                             "ord": idx, "src": f})
    o.files[f] = ("\n".join(ini) + "\n").encode()
    rngc = _rng(w, fc)
    rngc.shuffle(cron_entries)
    cron_entries = clean_first(cron_entries, lambda e: False)
    junk_at = bad_positions(rngc, len(cron_entries), 14, 60)
    k = 0
    for cidx in range(1, len(cron_entries) + 15):
        if cidx in junk_at:
            cron_lines += ["# rev %s %s" % ("retired.job.%d" % cidx, iso(w.hist0 + cidx * DAY)),
                           "61 4 * * * /opt/qf/bin/run retired.job.%d" % cidx]
            o.bad(fc, cidx)
            continue
        if k >= len(cron_entries):
            break
        rev_at, name, cron, sidx = cron_entries[k]
        k += 1
        key, tv = variant(rngc, name, allow_space=False, p=0.35 if cidx > 50 else 0)
        if tv:
            o.trap(fc)
        cron_lines += ["# rev %s %s" % (key, iso(rev_at)), "%s /opt/qf/bin/run %s" % (cron, key)]
    o.files[fc] = ("\n".join(cron_lines) + "\n").encode()


# ---------------------------------------------------------------------- renames
def _renames(o, w):
    f = "job_renames.csv"
    rng = _rng(w, f)
    rows = sorted(w.renames, key=lambda r: (r["at"], r["new"]))
    rows = clean_first(rows, lambda r: not r["old"] or r["at"] >= w.p0 - 30 * DAY)
    out = ["old_key,new_key,effective_at"]
    zones = ["UTC", "Asia/Kolkata", "America/New_York", "Europe/Berlin"]
    idx = 0
    ri = 0
    pad = []
    # padding: historical renames of retired jobs chained among themselves
    live_names = set()
    for j in w.jobs:
        for n, _ in j["names"]:
            live_names.add(n)
    k = 0
    while len(rows) + len(pad) < 205:
        a = "archived.%s.%d" % (rng.choice(["orders", "rates", "claims", "tax"]), k)
        b = a + ".old"
        pad.append({"old": b, "new": a + ".gone", "at": w.hist0 + rng.randrange(0, 300) * DAY})
        k += 1
    allrows = rows[:50] + sorted(rows[50:] + pad, key=lambda r: (r["at"], r["new"]))
    bad_at = bad_positions(rng, len(allrows), 12, 55)
    while True:
        idx += 1
        if idx in bad_at:
            out.append("%s,%s,%s" % ("stage.orders.daily", "stage.orders.daily2", "yesterday"))
            o.bad(f, idx)
            continue
        if ri >= len(allrows):
            break
        r = allrows[ri]
        ri += 1
        z = zones[0] if idx <= 50 else rng.choice(zones)
        old_v, t1 = variant(rng, r["old"], allow_space=False, p=0.25 if idx > 50 else 0) if r["old"] else ("", False)
        new_v, t2 = variant(rng, r["new"], allow_space=False, p=0.25 if idx > 50 else 0)
        if t1 or t2 or z != "UTC" or not r["old"] or r["at"] >= w.p0 - 30 * DAY:
            o.trap(f)
        out.append("%s,%s,%s" % (old_v, new_v, iso_offset(w.zt, z, r["at"], sep=" ")))
        o.D["renames"].append({"old": norm(old_v) if old_v else "", "new": norm(new_v), "at": r["at"], "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- deps
def _render_deps(o, w):
    f = "dependencies.dot"
    rng = _rng(w, f)
    lines = ["digraph quillfen_dependencies {", "  rankdir=LR;", "  node [shape=box];"]
    edges = list(w.deps)
    rng.shuffle(edges)
    edges = clean_first(edges, lambda e: e["lag"] or e["frm"] != -INF or e["to"] != INF or e.get("up") is None)
    bad_at = bad_positions(rng, len(edges), 12, 60)
    idx = 0
    ei = 0
    while True:
        idx += 1
        if idx in bad_at:
            e = rng.choice(edges)
            lines.append('  "%s" -> "%s" [lag=soon];' % (w.job_by_id[e["down"]]["names"][0][0], w.job_by_id[e["down"]]["names"][0][0]))
            o.bad(f, idx)
            continue
        if ei >= len(edges):
            break
        e = edges[ei]
        ei += 1
        ref_t = e["frm"] if e["frm"] != -INF else w.p0 - 60 * DAY
        up = e["unknown_key"] if e.get("up") is None else name_at(w.job_by_id[e["up"]], ref_t)
        down = name_at(w.job_by_id[e["down"]], ref_t)
        upv, t1 = variant(rng, up, p=0.2 if idx > 50 else 0)
        dnv, t2 = variant(rng, down, p=0.2 if idx > 50 else 0)
        attrs = ["lag=%d" % e["lag"]]
        if e["frm"] != -INF:
            attrs.append('valid_from="%s"' % iso(e["frm"]))
        if e["to"] != INF:
            attrs.append('valid_to="%s"' % iso(e["to"]))
        if t1 or t2 or e["lag"] or len(attrs) > 1 or e.get("up") is None:
            o.trap(f)
        lines.append('  "%s" -> "%s" [%s];' % (upv, dnv, ", ".join(attrs)))
        o.D["deps"].append({"down": norm(dnv), "up": norm(upv), "lag": e["lag"], "frm": e["frm"], "to": e["to"],
                            "ord": idx, "src": f})
    lines.append("}")
    o.files[f] = ("\n".join(lines) + "\n").encode()


# ---------------------------------------------------------------------- producers
def _producers(o, w):
    f = "dataset_producers.psv"
    rng = _rng(w, f)
    rows = sorted(w.producers, key=lambda p: (p["frm"], p["dataset"]))
    rows = clean_first(rows, lambda p: p["to"] != INF or p.get("job") is None)
    out = ["dataset|producer_job|valid_from|valid_to"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("lake.unknown_feed|%s|2025-01-01T00:00Z" % rng.choice(w.jobs)["names"][0][0])
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        p = rows[ri]
        ri += 1
        if p.get("job") is None:
            nm = p["unknown_key"]
        else:
            job = w.job_by_id[p["job"]]
            ref = max(p["frm"], job["created"])
            nm = name_at(job, ref)
        kv, t1 = variant(rng, nm, allow_space=False, p=0.25 if idx > 50 else 0)
        dv, t2 = ds_variant(rng, p["dataset"], p=0.3 if idx > 50 else 0)
        if t1 or t2 or p["to"] != INF or p.get("job") is None:
            o.trap(f)
        frm = iso(p["frm"])[:16] + "Z"
        to = "" if p["to"] == INF else iso(p["to"])[:16] + "Z"
        out.append("%s|%s|%s|%s" % (dv, kv, frm, to))
        o.D["producers"].append({"dataset": norm(dv), "key": norm(kv), "frm": p["frm"] - p["frm"] % 60,
                                 "to": INF if p["to"] == INF else p["to"] - p["to"] % 60, "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- sla
def _sla(o, w):
    f = "sla_overrides.properties"
    rng = _rng(w, f)
    rows = sorted(w.sla_overrides, key=lambda r: (r["at"], r["job"] if r["job"] is not None else -1))
    rows = clean_first(rows, lambda r: r["value"] in (0, None) or r.get("job") is None)
    out = ["# SLA overrides (minutes). Key: sla.<job>.<instant>", "# generated by ops-config"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("sla.%s.%s = ninety" % (rng.choice(w.jobs)["names"][0][0], iso(w.p0).replace(":", "\\:")))
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        r = rows[ri]
        ri += 1
        nm = r["unknown_key"] if r.get("job") is None else name_at(w.job_by_id[r["job"]], r["at"])
        kv, tv = variant(rng, nm, allow_space=False, p=0.2 if idx > 50 else 0)
        if tv or r["value"] in (0, None) or r.get("job") is None:
            o.trap(f)
        val = "" if r["value"] is None else str(r["value"])
        sep = rng.choice([" = ", "=", ": "]) if idx > 50 else " = "
        out.append("sla.%s.%s%s%s" % (kv, iso(r["at"]).replace(":", "\\:"), sep, val))
        o.D["sla_overrides"].append({"key": norm(kv), "at": r["at"], "value": r["value"], "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- ratecard
def _render_ratecard(o, w):
    f = "ratecard.fwf"
    rng = _rng(w, f)
    rows = sorted(w.ratecard, key=lambda r: (r["frm"], r["tier"], r["bucket"]))
    hdr = "TIER BUCKET EFFECTIVE_FROM          BASE      PER_MINUTE CUR"
    out = [hdr]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    o.D["ratecard"] = []
    while True:
        idx += 1
        if idx in bad_at:
            out.append("%-4s %-6s %-20s %-9s %-10s %-3s" % ("2", "B30", iso(w.hist0), "12,50", "0.3", "EUR"))
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        r = rows[ri]
        ri += 1
        if "." in r["base"] or "." in r["per_min"] or r["frm"] == w.rate_change:
            o.trap(f)
        out.append("%-4d %-6s %-20s %-9s %-10s %-3s" % (r["tier"], r["bucket"], iso(r["frm"]), r["base"], r["per_min"], "EUR"))
        o.D["ratecard"].append(dict(r, ord=idx, src=f))
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- ownership
def _render_ownership(o, w):
    f = "ownership_history.gitlog"
    rng = _rng(w, f)
    commits = list(w.own_commits)
    order = sorted(range(len(commits)), key=lambda i: commits[i]["at"], reverse=True)
    out = []
    bad_ids = set(rng.sample(range(0, len(commits) - 60), 12))
    idx = 0
    pos = 0
    for i in order:
        c = commits[i]
        pos += 1
        if pos in bad_ids:
            idx += 1
            out += ["commit %s" % _h("bad", i)[:40], "Author: Ops Bot <ops-bot@quillfen.example>",
                    "Date:   sometime last week", "", "    Reformat", "", " CODEOWNERS", ""]
            o.bad(f, idx)
        idx += 1
        p = w.person_by_eid.get(c["author"], w.people[0])
        zone = rng.choice(["UTC", "Europe/Berlin", "Asia/Kolkata", "America/Los_Angeles"])
        off = w.zt.offset(zone, c["at"])
        y, mo, d, h, mi, s, wd = fields(c["at"] + off * 60)
        date = "%s %s %d %02d:%02d:%02d %d %s" % (WDAYS[wd], MONTHS[mo - 1], d, h, mi, s, y, fmt_offset(off).replace(":", ""))
        out += ["commit %s" % _h("commit", i)[:40], "Author: %s <%s>" % (p["cn"], p["primary"]), "Date:   %s" % date,
                "", "    %s" % c["msg"], "", " CODEOWNERS"]
        for op, pat, hs in c["changes"]:
            out.append("%s%s %s" % (op, pat, " ".join(hs)))
            if op == "-" or "*" in pat:
                o.trap(f)
        out.append("")
        o.D["ownership"].append({"at": c["at"], "changes": [(op, pat, [h.lower() for h in hs]) for op, pat, hs in c["changes"]],
                                 "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


def _registry(o, w):
    f = "team_registry.hcl"
    rng = _rng(w, f)
    rows = sorted(w.team_handles, key=lambda r: (r["handle"], r["frm"]))
    rows = clean_first(rows, lambda r: r["frm"] != -INF or r["to"] != INF)
    out = ["# Team handle bindings", ""]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out += ['handle "quillfen/orphan-%d" {' % idx, '  valid_from = ""', "}", ""]
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        r = rows[ri]
        ri += 1
        if r["frm"] != -INF or r["to"] != INF:
            o.trap(f)
        out += ['handle "%s" {' % r["handle"], '  team       = "%s"' % r["team"],
                '  valid_from = "%s"' % ("" if r["frm"] == -INF else iso(r["frm"])),
                '  valid_to   = "%s"' % ("" if r["to"] == INF else iso(r["to"])), "}", ""]
        o.D["team_handles"].append({"handle": r["handle"].lower(), "team": "team:" + r["team"], "frm": r["frm"], "to": r["to"]})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- people
def _fold_ldif(line):
    if len(line) <= 76:
        return [line]
    out = [line[:76]]
    rest = line[76:]
    while rest:
        out.append(" " + rest[:75])
        rest = rest[75:]
    return out


def _ldif(o, w):
    f = "directory.ldif"
    rng = _rng(w, f)
    out = ["version: 1", ""]
    idx = 0
    entries = []
    for p in w.people:
        entries.append(("person", p))
    multi = "ldif_multi" in w.F
    for p in w.people:
        if not multi:
            for a in p["aliases"]:
                entries.append(("mod_add_alias", (p, a)))
        if p.get("late_alias"):
            entries.append(("mod_add", p))
        if rng.random() < 0.5:
            entries.append(("mod_del", p))
    k = 0
    while len(entries) < 215:
        entries.append(("former", k))
        k += 1
    entries = clean_first(entries, lambda e: e[0] != "person" or len(e[1]["aliases"]) > 1)

    bad_at = bad_positions(rng, len(entries), 12, 60)
    ei = 0
    while True:
        idx += 1
        if idx in bad_at:
            out += ["dn: uid=tmp%d,ou=people,dc=quillfen,dc=example" % idx, "objectClass: inetOrgPerson",
                    "uid: tmp%d" % idx, "cn: Temp Account", ""]
            o.bad(f, idx)
            continue
        if ei >= len(entries):
            break
        kind, p = entries[ei]
        ei += 1
        if kind == "person":
            lines = ["dn: uid=%s,ou=people,dc=quillfen,dc=example" % p["uid"], "objectClass: inetOrgPerson",
                     "uid: %s" % p["uid"], "cn: %s" % p["cn"], "employeeNumber: %s" % p["eid"],
                     "description: %s" % ("Member of the %s team, reachable through the paging rota and the team channel during business hours" % p["team"])]
            mails = [p["primary"]] + (p["aliases"] if multi else [])
            for m in mails:
                lines.append("mail: %s" % m)
            if len(mails) > 1:
                o.trap(f)
            for ln in lines:
                out += _fold_ldif(ln)
            out.append("")
            o.D["ldif_people"].append({"eid": p["eid"], "uid": p["uid"], "mails": [m.lower() for m in mails]})
        elif kind == "mod_add":
            at = w.p0 - rng.randrange(5, 200) * DAY
            out += ["dn: uid=%s,ou=people,dc=quillfen,dc=example" % p["uid"], "changetype: modify", "add: mail",
                    "mail: %s" % p["late_alias"], "-", "replace: modifyTimestamp",
                    "modifyTimestamp: %s" % compact(at).replace("T", ""), "-", ""]
            o.D["ldif_mods"].append({"uid": p["uid"], "op": "add", "mail": p["late_alias"].lower(), "at": at})
            o.trap(f)
        elif kind == "mod_add_alias":
            p, a = p
            at = w.p0 - rng.randrange(200, 900) * DAY
            out += ["dn: uid=%s,ou=people,dc=quillfen,dc=example" % p["uid"], "changetype: modify", "add: mail",
                    "mail: %s" % a, "-", "replace: modifyTimestamp",
                    "modifyTimestamp: %s" % compact(at).replace("T", ""), "-", ""]
            o.D["ldif_mods"].append({"uid": p["uid"], "op": "add", "mail": a.lower(), "at": at})
        elif kind == "mod_del":
            at = w.p0 - rng.randrange(5, 200) * DAY
            m = p["aliases"][-1]
            out += ["dn: uid=%s,ou=people,dc=quillfen,dc=example" % p["uid"], "changetype: modify", "delete: mail",
                    "mail: %s" % m, "-", "replace: modifyTimestamp",
                    "modifyTimestamp: %s" % compact(at).replace("T", ""), "-", ""]
            o.D["ldif_mods"].append({"uid": p["uid"], "op": "delete", "mail": m.lower(), "at": at})
            o.trap(f)
        else:
            uid = "former%03d" % p
            out += ["dn: uid=%s,ou=alumni,dc=quillfen,dc=example" % uid, "objectClass: inetOrgPerson", "uid: %s" % uid,
                    "cn: Former Staff %d" % p, "employeeNumber: X%04d" % p, "mail: %s@qf-legacy.example" % uid, ""]
            o.D["ldif_people"].append({"eid": "X%04d" % p, "uid": uid, "mails": ["%s@qf-legacy.example" % uid]})
    o.files[f] = ("\n".join(out) + "\n").encode()


def _vcf(o, w):
    f = "pager_contacts.vcf"
    rng = _rng(w, f)
    cards = []
    for p in w.people:
        cards.append(("p", p))
    k = 0
    while len(cards) < 210:
        cards.append(("contractor", k))
        k += 1
    rng.shuffle(cards)
    cards = clean_first(cards, lambda c: c[0] != "p")
    out = []
    bad_at = bad_positions(rng, len(cards), 12, 60)
    idx = 0
    ci = 0
    while True:
        idx += 1
        if idx in bad_at:
            out += ["BEGIN:VCARD", "VERSION:4.0", "FN:Unknown", "X-PAGER-HANDLE:", "END:VCARD"]
            o.bad(f, idx)
            continue
        if ci >= len(cards):
            break
        kind, p = cards[ci]
        ci += 1
        if kind == "p":
            emails = [rng.choice(p["aliases"])] if idx > 50 else [p["primary"]]
            handles = list(p["handles"])
            if idx > 50 and rng.random() < 0.3:
                handles = [h.upper() for h in handles]
                o.trap(f)
            if emails[0] != p["primary"]:
                o.trap(f)
            out += ["BEGIN:VCARD", "VERSION:4.0", "FN:%s" % p["cn"]]
            for e in emails:
                out.append("EMAIL;TYPE=work:%s" % e)
            for h in handles:
                out.append("X-PAGER-HANDLE:%s" % h)
            out.append("END:VCARD")
            o.D["vcards"].append({"emails": [e.lower() for e in emails], "handles": [h.lower() for h in handles]})
        else:
            out += ["BEGIN:VCARD", "VERSION:4.0", "FN:Contractor %d" % p, "EMAIL:ext%d@vendor.example" % p,
                    "X-PAGER-HANDLE:pg-ext%d" % p, "END:VCARD"]
            o.D["vcards"].append({"emails": ["ext%d@vendor.example" % p], "handles": ["pg-ext%d" % p]})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- calendars
def _ics_fold(line):
    out = []
    b = line
    while len(b) > 75:
        out.append(b[:75])
        b = " " + b[75:]
    out.append(b)
    return out


def _local_stamp(t):
    return compact(t).replace("Z", "")


def _freeze(o, w):
    f = "freeze_windows.ics"
    rng = _rng(w, f)
    comps = [("s", s) for s in w.freeze] + [("o", x) for x in w.freeze_overrides]
    comps = clean_first(comps, lambda c: c[0] == "o" or bool(c[1].get("exdates_local")) or bool(c[1].get("rrule")))
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Quillfen//Freeze Calendar//EN"]
    bad_at = bad_positions(rng, len(comps), 12, 60)
    idx = 0
    ci = 0
    while True:
        idx += 1
        if idx in bad_at:
            out += ["BEGIN:VEVENT", "UID:broken-%d@quillfen" % idx, "SUMMARY:Freeze placeholder", "END:VEVENT"]
            o.bad(f, idx)
            continue
        if ci >= len(comps):
            break
        kind, c = comps[ci]
        ci += 1
        if kind == "s":
            lines = ["BEGIN:VEVENT", "UID:%s" % c["uid"], "SUMMARY:%s" % c["summary"],
                     "DTSTART;TZID=%s:%s" % (c["zone"], _local_stamp(c["start_local"])),
                     "DTEND;TZID=%s:%s" % (c["zone"], _local_stamp(c["end_local"])),
                     "CATEGORIES:%s" % ",".join("TIER%d" % t for t in c["tiers"])]
            if c["rrule"]:
                lines.append("RRULE:%s" % c["rrule"])
                o.trap(f)
            if c["exdates_local"]:
                inside = [x for x in c["exdates_local"] if w.p0 - DAY <= x < w.p1 + DAY]
                others = [x for x in c["exdates_local"] if x not in inside]
                prefix = "EXDATE;TZID=%s:" % c["zone"]
                bounds = [75 + 74 * k for k in range(12)]
                order = list(c["exdates_local"])
                for k in range(len(others) + 1):
                    cand = others[:k] + inside + others[k:]
                    pos = len(prefix)
                    split_inside = False
                    for x in cand:
                        a, b = pos, pos + 15
                        if x in inside and any(a < bd < b for bd in bounds):
                            split_inside = True
                        pos = b + 1
                    if split_inside:
                        order = cand
                        break
                lines.append(prefix + ",".join(_local_stamp(x) for x in order))
                o.trap(f, 2)
            lines.append("END:VEVENT")
            for ln in lines:
                out += _ics_fold(ln)
            o.D["freeze"].append({"uid": c["uid"], "zone": c["zone"], "start_local": c["start_local"],
                                  "end_local": c["end_local"], "rrule": c["rrule"], "exdates_local": list(c["exdates_local"]),
                                  "tiers": list(c["tiers"])})
        else:
            lines = ["BEGIN:VEVENT", "UID:%s" % c["uid"],
                     "RECURRENCE-ID;TZID=%s:%s" % (c["zone"], _local_stamp(c["rid_local"]))]
            if c["cancelled"]:
                lines.append("STATUS:CANCELLED")
            else:
                lines += ["DTSTART;TZID=%s:%s" % (c["zone"], _local_stamp(c["start_local"])),
                          "DTEND;TZID=%s:%s" % (c["zone"], _local_stamp(c["end_local"]))]
            lines.append("END:VEVENT")
            out += lines
            o.trap(f)
            o.D["freeze_overrides"].append({"uid": c["uid"], "rid_local": c["rid_local"], "cancelled": c["cancelled"],
                                            "start_local": c["start_local"], "end_local": c["end_local"]})
    out.append("END:VCALENDAR")
    o.files[f] = ("\n".join(out) + "\n").encode()


def _holidays(o, w):
    f = "team_holidays.xcs"
    rng = _rng(w, f)
    rows = sorted(w.holidays, key=lambda h: (h["date"], h["team"]))
    rows = clean_first(rows, lambda h: h["date"][:2] == ymd(w.p0)[:2])
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<icalendar xmlns="urn:ietf:params:xml:ns:icalendar-2.0">',
           "<vcalendar><properties><prodid><text>-//Quillfen//Holidays//EN</text></prodid></properties><components>"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("<vevent><properties><dtstart><date>2025-02-31</date></dtstart><summary><text>Bad</text></summary>"
                       "<x-team><text>%s</text></x-team></properties></vevent>" % rng.choice(w.teams))
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        h = rows[ri]
        ri += 1
        if h["date"][:2] == ymd(w.p0)[:2]:
            o.trap(f)
        out.append("<vevent><properties><dtstart><date>%04d-%02d-%02d</date></dtstart><summary><text>%s</text></summary>"
                   "<x-team><text>%s</text></x-team></properties></vevent>" % (h["date"] + (h["summary"], h["team"])))
        o.D["holidays"].append({"team": "team:" + h["team"], "date": h["date"]})
    out += ["</components></vcalendar>", "</icalendar>"]
    o.files[f] = ("\n".join(out) + "\n").encode()


def _rota(o, w):
    f = "oncall_rota.jcal"
    rng = _rng(w, f)
    comps = [("s", s) for s in w.rota] + [("o", x) for x in w.rota_overrides]
    comps = clean_first(comps, lambda c: c[0] == "o")
    series_zone = {s["uid"]: s["zone"] for s in w.rota}
    vevents = []
    bad_at = bad_positions(rng, len(comps), 12, 60)
    idx = 0
    ci = 0
    while True:
        idx += 1
        if idx in bad_at:
            vevents.append(["vevent", [["uid", {}, "text", "rota-bad-%d@quillfen" % idx],
                                       ["dtstart", {"tzid": "UTC"}, "date-time", "2025-99-01T09:00:00"]], []])
            o.bad(f, idx)
            continue
        if ci >= len(comps):
            break
        kind, c = comps[ci]
        ci += 1
        if kind == "s":
            y, mo, d, h, mi, s, _ = fields(c["start_local"])
            rr = {}
            for part in c["rrule"].split(";"):
                k, v = part.split("=")
                rr[k.lower()] = int(v) if k in ("INTERVAL", "COUNT") else v
            if "until" in rr:
                u = rr["until"]
                rr["until"] = "%s-%s-%sT%s:%s:%sZ" % (u[:4], u[4:6], u[6:8], u[9:11], u[11:13], u[13:15])
            props = [["uid", {}, "text", c["uid"]],
                     ["dtstart", {"tzid": c["zone"]}, "date-time", "%04d-%02d-%02dT%02d:%02d:%02d" % (y, mo, d, h, mi, s)],
                     ["duration", {}, "duration", "P%dD" % c["length_days"]],
                     ["rrule", {}, "recur", rr],
                     ["attendee", {}, "cal-address", "mailto:%s" % c["attendee"]],
                     ["x-team", {}, "text", c["team"]]]
            vevents.append(["vevent", props, []])
            o.D["rota"].append({"uid": c["uid"], "team": "team:" + c["team"], "zone": c["zone"],
                                "start_local": c["start_local"], "rrule": c["rrule"], "attendee": c["attendee"].lower(),
                                "length_days": c["length_days"]})
            if c["attendee"] not in [p["primary"] for p in w.people]:
                o.trap(f)
        else:
            y, mo, d, h, mi, s, _ = fields(c["rid_local"])
            props = [["uid", {}, "text", c["uid"]],
                     ["recurrence-id", {"tzid": series_zone[c["uid"]]}, "date-time", "%04d-%02d-%02dT%02d:%02d:%02d" % (y, mo, d, h, mi, s)]]
            if c["cancelled"]:
                props.append(["status", {}, "text", "CANCELLED"])
            else:
                props.append(["attendee", {}, "cal-address", "mailto:%s" % c["attendee"]])
            vevents.append(["vevent", props, []])
            o.trap(f)
            o.D["rota_overrides"].append({"uid": c["uid"], "rid_local": c["rid_local"], "cancelled": c["cancelled"],
                                          "attendee": (c["attendee"] or "").lower()})
    cal = ["vcalendar", [["prodid", {}, "text", "-//Quillfen//Rota//EN"], ["version", {}, "text", "2.0"]], vevents]
    o.files[f] = json.dumps(cal, indent=1).encode()


def _render_pauses(o, w):
    f = "job_pauses.ltsv"
    rng = _rng(w, f)
    rows = sorted(w.pauses, key=lambda p: (p["at"], p["job"] if p["job"] is not None else -1))
    rows = clean_first(rows, lambda p: p["at"] >= w.p0 - 10 * DAY or p.get("job") is None)
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    zones = ["UTC", "Asia/Kolkata", "Europe/Berlin", "America/Chicago"]
    while True:
        idx += 1
        if idx in bad_at:
            out.append("time:\tjob:%s\taction:pause\tactor:pg-ops" % rng.choice(w.jobs)["names"][0][0])
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        p = rows[ri]
        ri += 1
        nm = p["unknown_key"] if p.get("job") is None else name_at(w.job_by_id[p["job"]], p["at"])
        kv, tv = variant(rng, nm, allow_space=False, p=0.25 if idx > 50 else 0)
        z = "UTC" if idx <= 50 else rng.choice(zones)
        if tv or z != "UTC" or p.get("orphan_candidate") or p.get("job") is None:
            o.trap(f)
        out.append("time:%s\tjob:%s\taction:%s\tactor:%s\tticket:OPS-%d" % (iso_offset(w.zt, z, p["at"]), kv, p["action"], p["actor"], 1000 + idx))
        o.D["pauses"].append({"key": norm(kv), "at": p["at"], "action": p["action"], "actor": p["actor"], "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


def _render_hosts(o, w):
    f = "host_inventory.csv"
    rng = _rng(w, f)
    rows = list(w.hosts)
    rows = clean_first(rows, lambda h: h["frm"] != -INF or h["to"] != INF)
    out = ["host,pool,zone,valid_from,valid_to"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    o.D["hosts"] = []
    while True:
        idx += 1
        if idx in bad_at:
            out.append("wk-z-%02d,z,Moon/Base,," % idx)
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        h = rows[ri]
        ri += 1
        if h["frm"] != -INF or h["to"] != INF or h["zone"] != "UTC":
            o.trap(f)
        out.append("%s,%s,%s,%s,%s" % (h["host"], h["pool"], h["zone"], "" if h["frm"] == -INF else iso(h["frm"]),
                                       "" if h["to"] == INF else iso(h["to"])))
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- scheduler
def _sched(o, w):
    zt = w.zt
    by_region = {}
    for e in w.sched:
        by_region.setdefault(e["region"], []).append(e)
    for region, lst in by_region.items():
        lst.sort(key=lambda e: (e["at"], e["run_id"]))
    backfill_ids = set(b["run_id"] for b in w.backfills)

    def is_trap(e):
        return e["run_id"] in backfill_ids or e["nominal"] >= w.p0

    # US sqlite
    f = "sched_us.sqlite"
    rng = _rng(w, f)
    rows = clean_first(by_region.get("us", []), is_trap)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "s.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE task_transitions (run_id TEXT NOT NULL, job TEXT NOT NULL, nominal_utc TEXT NOT NULL, state TEXT NOT NULL, at_utc TEXT NOT NULL)")
    con.execute("CREATE TABLE exporter_meta (k TEXT, v TEXT)")
    con.execute("INSERT INTO exporter_meta VALUES ('region','us-east'), ('format','v3')")
    bad_at = bad_positions(rng, len(rows), 14, 60)
    idx = 0
    ri = 0
    batch = []
    while True:
        idx += 1
        if idx in bad_at:
            batch.append(("sch-broken", "unknown", "N/A", "running", "N/A"))
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.15 if idx > 50 else 0)
        if tv or is_trap(e):
            o.trap(f)
        batch.append((e["run_id"], kv, iso(e["nominal"]), e["state"], iso(e["at"]).replace("T", " ").replace("Z", "")))
        o.D["sched"].append({"run_id": e["run_id"], "key": norm(kv), "nominal": e["nominal"], "state": e["state"],
                             "at": e["at"], "ord": idx, "src": f})
    con.executemany("INSERT INTO task_transitions VALUES (?,?,?,?,?)", batch)
    con.commit()
    con.execute("VACUUM")
    con.close()
    with open(path, "rb") as fh:
        o.files[f] = fh.read()
    os.remove(path)
    os.rmdir(tmp)

    # EU semicolon CSV, Berlin wall time
    f = "sched_eu.ssv"
    rng = _rng(w, f)
    rows = clean_first(by_region.get("eu", []), is_trap)
    out = ["run_id;job;nominal_utc;state;at_local"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("sch-broken;%s;%s;running;31.02.2026 25:61:00" % (rng.choice(w.jobs)["names"][0][0], iso(w.p0)))
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], allow_space=False, p=0.15 if idx > 50 else 0)
        y, mo, d, h, mi, s, _ = local_parts(zt, "Europe/Berlin", e["at"])
        loc = civil(y, mo, d, h, mi, s)
        at = wall_to_instant(zt, "Europe/Berlin", loc)
        o.trap(f) if (tv or is_trap(e)) else None
        out.append("%s;%s;%s;%s;%02d.%02d.%04d %02d:%02d:%02d" % (e["run_id"], kv, iso(e["nominal"]), e["state"], d, mo, y, h, mi, s))
        o.D["sched"].append({"run_id": e["run_id"], "key": norm(kv), "nominal": e["nominal"], "state": e["state"],
                             "at": at, "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()

    # APAC JSON lines, epoch millis
    f = "sched_apac.jsonl"
    rng = _rng(w, f)
    rows = clean_first(by_region.get("apac", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append('{"run": "sch-broken", "job": "x", "nominal_ms": 17, "state": "running", "ts_ms": }')
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.15 if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e)) else None
        ms = e["at"] * 1000 + (rng.randrange(0, 1000) if idx > 50 else 0)
        out.append(json.dumps({"run": e["run_id"], "job": kv, "nominal_ms": e["nominal"] * 1000, "state": e["state"], "ts_ms": ms}))
        o.D["sched"].append({"run_id": e["run_id"], "key": norm(kv), "nominal": e["nominal"], "state": e["state"],
                             "at": ms // 1000, "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()

    # legacy syslog, host wall time, no year
    f = "sched_legacy.syslog"
    rng = _rng(w, f)
    rows = clean_first(by_region.get("legacy", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = 0
    ri = 0
    py0 = ymd(w.p0)
    while True:
        idx += 1
        if idx in bad_at:
            out.append("Foo 99 99:99:99 cronhost-1 qf-sched[1]: run=sch-broken job=x nominal=bad state=running")
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        host = e["host"]
        zone = zone_of_host(w, host, e["at"])
        y, mo, d, h, mi, s, _ = local_parts(zt, zone, e["at"])
        # year inference: the year that places the stamp nearest the period start
        cands = []
        for yy in (py0[0] - 1, py0[0], py0[0] + 1):
            try:
                loc = civil(yy, mo, d, h, mi, s)
            except ValueError:
                continue
            cands.append((abs(loc - w.p0), yy, loc))
        loc = civil(y, mo, d, h, mi, s)
        at = wall_to_instant(zt, zone, loc)
        if y != py0[0]:
            o.trap(f)
        kv, tv = variant(rng, e["key"], allow_space=False, p=0.15 if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e)) else None
        out.append("%s %2d %02d:%02d:%02d %s qf-sched[%d]: run=%s job=%s nominal=%s state=%s" % (
            MONTHS[mo - 1], d, h, mi, s, host, 2000 + idx % 7000, e["run_id"], kv, iso(e["nominal"]), e["state"]))
        o.D["sched"].append({"run_id": e["run_id"], "key": norm(kv), "nominal": e["nominal"], "state": e["state"],
                             "at": at, "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- workers
def _workers(o, w):
    zt = w.zt
    by_pool = {}
    for e in w.workers:
        by_pool.setdefault(e["pool"], []).append(e)
    for p in by_pool:
        by_pool[p].sort(key=lambda e: (e["local_ms"], e["run_id"], e["event"]))
    backfill_ids = set(b["run_id"] for b in w.backfills)

    def is_trap(e):
        return e["run_id"] in backfill_ids or e["nominal"] >= w.p0

    def add(f, e, key, local_ms, idx):
        o.D["workers"].append({"host": e["host"], "run_id": e["run_id"], "key": norm(key), "nominal": e["nominal"],
                               "event": e["event"], "local_ms": local_ms, "ord": idx, "src": f})

    def sec_iso(ms):
        return iso(ms // 1000)

    # a: logfmt
    f = "workers_a.logfmt"
    rng = _rng(w, f)
    rows = clean_first(by_pool.get("a", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append('ts=2026-13-45T99:00:00Z level=info host=wk-a-01 event=commit')
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.2 if idx > 50 else 0)
        ms = e["local_ms"] - e["local_ms"] % 1000
        msg = 'run %s finished' % e["event"]
        tricky = "logfmt_escape" in w.F and idx > 50 and e["event"] in ("commit", "fail") and rng.random() < 0.35
        if tricky:
            msg = 'replayed \\" event=start \\" marker'
            o.trap(f)
        jobv = '"%s"' % kv if (" " in kv or tricky) else kv
        o.trap(f) if (tv or is_trap(e)) else None
        line = 'ts=%s level=info host=%s run=%s job=%s nominal=%s event=%s msg="%s"' % (sec_iso(ms), e["host"], e["run_id"], jobv, iso(e["nominal"]), e["event"], msg)
        out.append(line)
        add(f, e, kv, ms, idx)
    o.files[f] = ("\n".join(out) + "\n").encode()

    # b: CEF
    f = "workers_b.cef"
    rng = _rng(w, f)
    rows = clean_first(by_pool.get("b", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    names = {"start": ("4100", "Run started"), "commit": ("4101", "Run committed"), "fail": ("4102", "Run failed")}
    while True:
        idx += 1
        if idx in bad_at:
            out.append("CEF:0|Quillfen|worker|3.2|4101|Run committed|3|rt=notanumber dhost=wk-b-01")
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.2 if idx > 50 else 0)
        sig, nm = names[e["event"]]
        note = "attempt=1"
        if idx > 50 and rng.random() < 0.25:
            note = "a\\=b path\\=/tmp/x"
            o.trap(f)
        o.trap(f) if (tv or is_trap(e)) else None
        out.append("CEF:0|Quillfen|worker|3.2|%s|%s|3|rt=%d dhost=%s cs1Label=run cs1=%s cs2Label=job cs2=%s cs3Label=nominal cs3=%s msg=%s" % (
            sig, nm, e["local_ms"], e["host"], e["run_id"], kv.replace("=", "\\="), iso(e["nominal"]), note))
        add(f, e, kv, e["local_ms"], idx)
    o.files[f] = ("\n".join(out) + "\n").encode()

    # c: W3C extended log (UTC by directive), field order changes mid file
    f = "workers_c.w3c.log"
    rng = _rng(w, f)
    rows = clean_first(by_pool.get("c", []), is_trap)
    fa = ["date", "time", "s-computername", "cs-run", "cs-job", "cs-nominal", "x-event"]
    fb = ["x-event", "cs-run", "date", "time", "cs-nominal", "cs-job", "s-computername"]
    out = ["#Software: Quillfen Worker 3.2", "#Version: 1.0", "#Fields: " + " ".join(fa)]
    cur = fa
    bad_at = bad_positions(rng, len(rows), 12, 60)
    switch_at = set(range(400, len(rows), 700))
    idx = ri = 0
    while True:
        idx += 1
        if idx in switch_at:
            cur = fb if cur is fa else fa
            out.append("#Fields: " + " ".join(cur))
            o.trap(f)
        if idx in bad_at:
            out.append("2026-03-04 notatime wk-c-01 sch-x y z commit")
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], allow_space=False, p=0.2 if idx > 50 else 0)
        ms = e["local_ms"] - e["local_ms"] % 1000
        y, mo, d, h, mi, s, _ = fields(ms // 1000)
        vals = {"date": "%04d-%02d-%02d" % (y, mo, d), "time": "%02d:%02d:%02d" % (h, mi, s), "s-computername": e["host"],
                "cs-run": e["run_id"], "cs-job": kv, "cs-nominal": iso(e["nominal"]), "x-event": e["event"]}
        o.trap(f) if (tv or is_trap(e)) else None
        out.append(" ".join(vals[k] for k in cur))
        add(f, e, kv, ms, idx)
    o.files[f] = ("\n".join(out) + "\n").encode()

    # d: Windows event XML
    f = "workers_d.evtx.xml"
    rng = _rng(w, f)
    rows = clean_first(by_pool.get("d", []), is_trap)
    out = ['<?xml version="1.0" encoding="utf-8"?>', "<Events>"]
    ids = {"start": 4100, "commit": 4101, "fail": 4102}
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append('<Event><System><EventID>4101</EventID><TimeCreated SystemTime="yesterday"/><Computer>wk-d-01</Computer></System><EventData/></Event>')
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.2 if idx > 50 else 0)
        ms = e["local_ms"]
        frac = "%03d%04d" % (ms % 1000, rng.randrange(0, 10000) if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e) or frac[3:] != "0000") else None
        out.append('<Event><System><Provider Name="QuillfenWorker"/><EventID>%d</EventID><TimeCreated SystemTime="%s.%sZ"/>'
                   "<Computer>%s</Computer></System><EventData><Data Name=\"run\">%s</Data><Data Name=\"job\">%s</Data>"
                   "<Data Name=\"nominal\">%s</Data></EventData></Event>" % (ids[e["event"]], iso(ms // 1000)[:-1], frac, e["host"], e["run_id"], kv, iso(e["nominal"])))
        add(f, e, kv, ms, idx)
    out.append("</Events>")
    o.files[f] = ("\n".join(out) + "\n").encode()

    # e: combined access log (host wall time with offset)
    f = "workers_e.access.log"
    rng = _rng(w, f)
    rows = clean_first(by_pool.get("e", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append('10.2.0.9 - wk-e-01 [32/Foo/2026:25:00:00 +0000] "POST /runs/sch-x/commit HTTP/1.1" 204 0')
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.2 if idx > 50 else 0)
        ms = e["local_ms"] - e["local_ms"] % 1000
        zone = zone_of_host(w, e["host"], ms // 1000)
        off = zt.offset(zone, ms // 1000)
        y, mo, d, h, mi, s, _ = fields(ms // 1000 + off * 60)
        stamp = "%02d/%s/%04d:%02d:%02d:%02d %s" % (d, MONTHS[mo - 1], y, h, mi, s, fmt_offset(off).replace(":", ""))
        o.trap(f) if (tv or is_trap(e) or off != 0) else None
        url = "/runs/%s/%s?job=%s&nominal=%s" % (e["run_id"], e["event"], quote(kv, safe=""), quote(iso(e["nominal"]), safe=""))
        out.append('10.2.%d.%d - %s [%s] "POST %s HTTP/1.1" 204 0 "-" "qf-worker/3.2"' % (idx % 250, idx % 199, e["host"], stamp, url))
        add(f, e, kv, ms, idx)
    o.files[f] = ("\n".join(out) + "\n").encode()

    # f: protobuf text format
    f = "workers_f.pbtxt"
    rng = _rng(w, f)
    rows = clean_first(by_pool.get("f", []), is_trap)
    out = ["# proto-file: quillfen/worker_event.proto", "# proto-message: WorkerEventLog", ""]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    kinds = {"start": "START", "commit": "COMMIT", "fail": "FAIL"}
    while True:
        idx += 1
        if idx in bad_at:
            out += ["event {", '  host: "wk-f-01"', "  kind: COMMIT", "  local_time { seconds: -1 }", "}"]
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        kv, tv = variant(rng, e["key"], p=0.2 if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e)) else None
        out += ["event {", '  host: "%s"' % e["host"], '  run_id: "%s"' % e["run_id"], '  job: "%s"' % kv.replace('"', '\\"'),
                '  nominal: "%s"' % iso(e["nominal"]), "  kind: %s" % kinds[e["event"]],
                "  local_time { seconds: %d nanos: %d }" % (e["local_ms"] // 1000, (e["local_ms"] % 1000) * 1000000), "}"]
        add(f, e, kv, e["local_ms"], idx)
    o.files[f] = ("\n".join(out) + "\n").encode()


def _render_clock(o, w):
    f = "clock_offsets.prom"
    rng = _rng(w, f)
    out = ["# HELP node_timex_offset_seconds Estimated offset of the local clock from true time (local minus true).",
           "# TYPE node_timex_offset_seconds gauge"]
    rows = sorted(w.clock_samples, key=lambda s: (s["t_ms"], s["host"]))
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append('node_timex_offset_seconds{host="wk-a-01"} NaN')
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        s = rows[ri]
        ri += 1
        off = s["offset_ms"]
        sign = "-" if off < 0 else ""
        txt = "%s%d.%03d" % (sign, abs(off) // 1000, abs(off) % 1000)
        if idx > 50 and abs(off) < 1000 and rng.random() < 0.2:
            txt = "%se-3" % (("-" if off < 0 else "") + str(abs(off))) if off else "0"
            o.trap(f)
        if abs(off) > 30000:
            o.trap(f)
        out.append('node_timex_offset_seconds{host="%s",pool="%s"} %s %d' % (s["host"], s["host"][3], txt, s["t_ms"]))
        o.D["clock_samples"].append({"host": s["host"], "t_ms": s["t_ms"], "offset_ms": off})
    o.files[f] = ("\n".join(out) + "\n").encode()

    f = "heartbeats.txt"
    rng = _rng(w, f)
    rows = sorted(w.heartbeats, key=lambda s: (s["recv_ms"], s["host"]))
    out = []
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out += ["host: wk-e-01", "sent: never", "received: 2026-03-01T00:00:00.000Z", ""]
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        s = rows[ri]
        ri += 1
        if abs(s["sent_ms"] - s["recv_ms"]) > 30000:
            o.trap(f)
        sm, rm = s["sent_ms"], s["recv_ms"]
        out += ["host: %s" % s["host"], "sent: %s.%03dZ" % (iso(sm // 1000)[:-1], sm % 1000),
                "received: %s.%03dZ" % (iso(rm // 1000)[:-1], rm % 1000), ""]
        o.D["heartbeats"].append({"host": s["host"], "sent_ms": sm, "recv_ms": rm})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- landing
def _landing(o, w):
    zt = w.zt
    by_sys = {}
    for e in w.landings:
        by_sys.setdefault(e["system"], []).append(e)
    for s in by_sys:
        by_sys[s].sort(key=lambda e: (e["at"], e["dataset"]))
    def is_trap(e):
        return e["nominal"] >= w.p0 or e["nominal"] < w.p0 - 20 * DAY

    def add(f, e, ds, at, idx, kind="landings"):
        o.D[kind].append({"dataset": norm(ds), "nominal": e["nominal"], "at": at, "ord": idx, "src": f})

    # object store inventory, gzip CSV
    f = "landing_objectstore.csv.gz"
    rng = _rng(w, f)
    rows = clean_first(by_sys.get("objectstore", []), is_trap)
    out = ["bucket,key,size_bytes,last_modified_utc,storage_class"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("qf-lake,lake/unknown/ts=20260304T0500Z/part-0.parquet,10,2026-03-04 25:00:00,STANDARD")
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        dv, tv = ds_variant(rng, e["dataset"], p=0.25 if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e)) else None
        keyp = "%s/ts=%s/_SUCCESS" % (dv.replace(".", "/", 1), compact(e["nominal"])[:13] + "Z")
        out.append("qf-lake,%s,0,%s,STANDARD" % (keyp, iso(e["at"]).replace("T", " ").replace("Z", "")))
        add(f, e, dv, e["at"], idx)
    raw = ("\n".join(out) + "\n").encode()
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as gz:
        gz.write(raw)
    o.files[f] = bio.getvalue()

    # HDFS audit log (namenode wall time)
    f = "landing_hdfs_audit.log"
    rng = _rng(w, f)
    rows = clean_first(by_sys.get("hdfs", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 24, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            if idx % 2:
                out.append("2026-03-04 99:00:00,000 INFO FSNamesystem.audit: allowed=true ugi=etl cmd=create src=/warehouse/x/2026/03/04/0500/_SUCCESS dst=null host=nn-1")
                o.bad(f, idx)
            else:
                e = rng.choice(rows)
                y, mo, d, h, mi, s, _ = local_parts(zt, "Europe/Berlin", e["at"])
                out.append("%04d-%02d-%02d %02d:%02d:%02d,%03d INFO FSNamesystem.audit: allowed=true ugi=etl ip=/10.0.0.7 cmd=delete src=/warehouse/%s/_tmp_%d dst=null perm=null proto=rpc host=nn-1" % (y, mo, d, h, mi, s, idx % 1000, e["dataset"], idx))
                o.trap(f)
                o.D.setdefault("ignored", []).append((f, idx))
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        host = "nn-%d" % (1 + int(_h(e["dataset"])[:2], 16) % 3)
        zone = zone_of_host(w, host, e["at"])
        y, mo, d, h, mi, s, _ = local_parts(zt, zone, e["at"])
        at = wall_to_instant(zt, zone, civil(y, mo, d, h, mi, s))
        dv, tv = ds_variant(rng, e["dataset"], p=0.2 if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e) or host == "nn-2") else None
        yy, mm, dd, hh, mi2, _, _ = fields(e["nominal"])
        out.append("%04d-%02d-%02d %02d:%02d:%02d,%03d INFO FSNamesystem.audit: allowed=true ugi=etl ip=/10.0.0.5 cmd=create src=/warehouse/%s/%04d/%02d/%02d/%02d%02d/_SUCCESS dst=null perm=etl:hdfs:rw-r--r-- proto=rpc host=%s" % (
            y, mo, d, h, mi, s, idx % 1000, dv, yy, mm, dd, hh, mi2, host))
        add(f, e, dv, at, idx)
    o.files[f] = ("\n".join(out) + "\n").encode()

    # warehouse SQL dump
    f = "landing_warehouse.sql"
    rng = _rng(w, f)
    rows = clean_first(by_sys.get("warehouse", []), is_trap)
    out = ["-- partition registry dump", "SET TIME ZONE 'UTC';", ""]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    pending = []

    def flush():
        if pending:
            out.append("INSERT INTO partition_registry (dataset, partition_ts, registered_at) VALUES\n  " + ",\n  ".join(pending) + ";")
            pending.clear()
    while True:
        idx += 1
        if idx in bad_at:
            pending.append("('lake.broken', 'not a time', '2026-03-04 05:00:00')")
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        dv, tv = ds_variant(rng, e["dataset"], p=0.2 if idx > 50 else 0)
        o.trap(f) if (tv or is_trap(e)) else None
        pending.append("('%s', '%s', '%s')" % (dv.replace("'", "''"), iso(e["nominal"]).replace("T", " ")[:-1], iso(e["at"]).replace("T", " ")[:-1]))
        if len(pending) >= rng.choice([1, 3, 5]):
            flush()
        add(f, e, dv, e["at"], idx)
    flush()
    o.files[f] = ("\n".join(out) + "\n").encode()

    # catalog Atom feed
    f = "landing_catalog.atom"
    rng = _rng(w, f)
    rows = clean_first(by_sys.get("catalog", []), is_trap)
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom">',
           "<title>Quillfen data catalog partition notices</title>", "<id>urn:quillfen:catalog</id>"]
    bad_at = bad_positions(rng, len(rows), 24, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            if idx % 2:
                out.append("<entry><id>urn:qf:bad:%d</id><title>lake.broken 2026-03-04T05:00:00Z</title><updated>soon</updated><category term=\"published\"/></entry>" % idx)
                o.bad(f, idx)
            else:
                e = rng.choice(rows)
                out.append("<entry><id>urn:qf:wd:%d</id><title>%s %s</title><updated>%s</updated><category term=\"withdrawn\"/></entry>" % (idx, e["dataset"], iso(e["nominal"]), iso(e["at"] + 900)))
                o.trap(f)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        dv, tv = ds_variant(rng, e["dataset"], p=0.2 if idx > 50 else 0)
        zone = "UTC" if idx <= 50 else rng.choice(["UTC", "Europe/Berlin", "Asia/Tokyo"])
        o.trap(f) if (tv or is_trap(e) or zone != "UTC") else None
        out.append("<entry><id>urn:qf:part:%s</id><title>%s %s</title><updated>%s</updated><category term=\"published\"/></entry>" % (
            _h(e["dataset"], e["nominal"], e["at"])[:16], dv, iso(e["nominal"]), iso_offset(zt, zone, e["at"])))
        add(f, e, dv, e["at"], idx)
    out.append("</feed>")
    o.files[f] = ("\n".join(out) + "\n").encode()

    # partner xferlog (host wall time, Asia/Kolkata)
    f = "landing_partner.xferlog"
    rng = _rng(w, f)
    rows = clean_first(by_sys.get("partner", []), is_trap)
    out = []
    bad_at = bad_positions(rng, len(rows), 24, 60)
    idx = ri = 0
    while True:
        idx += 1
        host = "partner-sftp-%d" % (1 + idx % 2)
        if idx in bad_at:
            e = rng.choice(rows)
            y, mo, d, h, mi, s, wd = local_parts(zt, "Asia/Kolkata", e["at"] + 300)
            yy, mm, dd, hh, mi2, _, _ = fields(e["nominal"])
            if idx % 2:
                out.append("%s %s %2d %02d:%02d:%02d %04d 3 %s 1024 /incoming/%s_%04d%02d%02d%02d%02d.csv.gz b _ i r partner sftp 0 * i" % (
                    WDAYS[wd], MONTHS[mo - 1], d, h, mi, s, y, host, e["dataset"], yy, mm, dd, hh, mi2))
                o.trap(f)
            else:
                out.append("%s %s %2d %02d:%02d:%02d %04d x %s oops" % (WDAYS[wd], MONTHS[mo - 1], d, h, mi, s, y, host))
                o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        e = rows[ri]
        ri += 1
        y, mo, d, h, mi, s, wd = local_parts(zt, "Asia/Kolkata", e["at"])
        yy, mm, dd, hh, mi2, _, _ = fields(e["nominal"])
        dv, tv = ds_variant(rng, e["dataset"], p=0.2 if idx > 50 else 0)
        dv = dv.replace("/", ".")
        o.trap(f) if (tv or is_trap(e)) else None
        out.append("%s %s %2d %02d:%02d:%02d %04d 2 %s 20480 /incoming/%s_%04d%02d%02d%02d%02d.csv.gz b _ i r partner sftp 0 * c" % (
            WDAYS[wd], MONTHS[mo - 1], d, h, mi, s, y, host, dv, yy, mm, dd, hh, mi2))
        add(f, e, dv, e["at"], idx)
    o.files[f] = ("\n".join(out) + "\n").encode()

    # deletions report (HTML)
    f = "partition_deletions.html"
    rng = _rng(w, f)
    rows = sorted(w.retracts, key=lambda e: (e["at"], e["dataset"]))
    # pad with deletions of historic partitions that were never registered (orphans) and old ones
    pads = []
    k = 0
    while len(rows) + len(pads) < 205:
        job = rng.choice([j for j in w.jobs if not j.get("retired")])
        ds = w.job_dataset[job["id"]][0][2]
        t = w.p0 - rng.randrange(60, 400) * DAY + 3 * 3600
        pads.append({"dataset": ds, "nominal": t, "at": t + 7200, "pad": True})
        k += 1
    orphans = []
    if "orphans" in w.F:
        for i in range(12):
            job = rng.choice([j for j in w.jobs if not j.get("retired")])
            ds = w.job_dataset[job["id"]][0][2]
            t = w.p0 + rng.randrange(2, 25) * DAY + 13 * 3600 + 17 * 60
            orphans.append({"dataset": ds, "nominal": t, "at": t + 3600, "orphan": True})
    allrows = sorted(rows + pads + orphans, key=lambda e: (e["at"], e["dataset"]))
    allrows = clean_first(allrows, lambda e: not e.get("pad"))
    out = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>Partition deletions</title></head><body>",
           "<h1>Partition deletions report</h1>", "<table id=\"deletions\">",
           "<tr><th>dataset</th><th>partition</th><th>deleted at</th><th>requested by</th></tr>"]
    bad_at = bad_positions(rng, len(allrows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("<tr><td>lake.broken</td><td>2026-03-04T05:00:00Z</td><td>n/a</td><td>ops</td></tr>")
            o.bad(f, idx)
            continue
        if ri >= len(allrows):
            break
        e = allrows[ri]
        ri += 1
        if not e.get("pad"):
            o.trap(f)
        out.append("<tr><td>%s</td><td>%s</td><td>%s UTC</td><td>%s</td></tr>" % (
            e["dataset"], iso(e["nominal"]), iso(e["at"]).replace("T", " ")[:-4], rng.choice(w.people)["handles"][0]))
        at = e["at"] - e["at"] % 60
        o.D["retracts"].append({"dataset": norm(e["dataset"]), "nominal": e["nominal"], "at": at, "ord": idx, "src": f})
    out += ["</table>", "</body></html>"]
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- operator
def _xlsx(rows):
    def cell(ref, v):
        if isinstance(v, (int, float)):
            return '<c r="%s"><v>%s</v></c>' % (ref, v)
        return '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, v.replace("&", "&amp;").replace("<", "&lt;"))
    cols = "ABCDEFGH"
    sheet_rows = []
    for i, r in enumerate(rows, start=1):
        sheet_rows.append('<row r="%d">%s</row>' % (i, "".join(cell("%s%d" % (cols[j], i), v) for j, v in enumerate(r))))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>%s</sheetData></worksheet>' % "".join(sheet_rows))
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="audit" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(info, files[name])
    return bio.getvalue()


EXCEL_EPOCH = civil(1899, 12, 30)


def _operator(o, w):
    f = "operator_audit.xlsx"
    rng = _rng(w, f)
    rows = sorted(w.operator, key=lambda r: (r["at"], r["key"]))
    pads = []
    while len(rows) + len(pads) < 210:
        job = rng.choice([j for j in w.jobs if not j.get("retired")])
        t = w.hist0 + rng.randrange(0, 900) * DAY + 5 * 3600
        pads.append({"at": t + 3600, "actor": rng.choice(w.people)["handles"][0], "action": "note", "key": name_at(job, t), "nominal": t})
    allrows = sorted(rows + pads, key=lambda r: (r["at"], r["key"]))
    allrows = clean_first(allrows, lambda r: r["action"] != "note")
    sheet = [["timestamp", "actor", "action", "target", "ticket"]]
    bad_at = bad_positions(rng, len(allrows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            sheet.append(["n/a", "pg-ops", "mark_success", "nothing", "OPS-0"])
            o.bad(f, idx)
            continue
        if ri >= len(allrows):
            break
        r = allrows[ri]
        ri += 1
        kv, tv = variant(rng, r["key"], allow_space=False, p=0.2 if idx > 50 else 0)
        serial = "%.8f" % ((r["at"] - EXCEL_EPOCH) / 86400.0)
        back = EXCEL_EPOCH + int(round(float(serial) * 86400))
        if r["action"] != "note" or tv:
            o.trap(f)
        actor = r["actor"].upper() if (idx > 50 and rng.random() < 0.2) else r["actor"]
        sheet.append([float(serial), actor, r["action"], "%s@%s" % (kv, iso(r["nominal"])), "OPS-%d" % (5000 + idx)])
        o.D["operator"].append({"at": back, "actor": actor.lower(), "action": r["action"], "key": norm(kv),
                                "nominal": r["nominal"], "ord": idx, "src": f})
    o.files[f] = _xlsx(sheet)

    f = "approvals.mbox"
    rng = _rng(w, f)
    rows = sorted(w.approvals, key=lambda r: (r["at"], r["key"]))
    pads = []
    while len(rows) + len(pads) < 205:
        job = rng.choice([j for j in w.jobs if not j.get("retired")])
        t = w.hist0 + rng.randrange(0, 900) * DAY + 5 * 3600
        pads.append({"from": rng.choice(w.people)["primary"], "at": t + 1800, "key": name_at(job, t), "nominal": t})
    allrows = clean_first(sorted(rows + pads, key=lambda r: (r["at"], r["key"])), lambda r: r["nominal"] >= w.p0 - 45 * DAY)
    out = []
    bad_at = bad_positions(rng, len(allrows), 12, 60)
    idx = ri = 0
    zones = ["UTC", "Europe/Berlin", "Asia/Kolkata", "America/New_York"]
    while True:
        idx += 1
        if idx in bad_at:
            out += ["From MAILER-DAEMON Thu Jan  1 00:00:00 1970", "From: postmaster@quillfen.example",
                    "Date: not a date", "Subject: Undeliverable", "", "Delivery failed.", ""]
            o.bad(f, idx)
            continue
        if ri >= len(allrows):
            break
        r = allrows[ri]
        ri += 1
        z = "UTC" if idx <= 50 else rng.choice(zones)
        off = w.zt.offset(z, r["at"])
        y, mo, d, h, mi, s, wd = fields(r["at"] + off * 60)
        date = "%s, %02d %s %04d %02d:%02d:%02d %s" % (WDAYS[wd], d, MONTHS[mo - 1], y, h, mi, s, fmt_offset(off).replace(":", ""))
        kv, tv = variant(rng, r["key"], allow_space=False, p=0.2 if idx > 50 else 0)
        if tv or z != "UTC" or r["nominal"] >= w.p0 - 45 * DAY:
            o.trap(f)
        body = ["Approved. Please mark the interval as complete.", ""]
        if idx > 50 and rng.random() < 0.2:
            body = ["From the runbook: approvals must precede the mark.", ">From earlier thread: ok", ""]
            o.trap(f)
        out += ["From %s %s %s %2d %02d:%02d:%02d %04d" % (r["from"], WDAYS[wd], MONTHS[mo - 1], d, h, mi, s, y),
                "From: %s" % r["from"], "Date: %s" % date, "Subject: Approve mark_success %s" % kv,
                "Message-ID: <%s@quillfen.example>" % _h("m", idx)[:20], "X-Quillfen-Interval: %s@%s" % (kv, iso(r["nominal"])), ""] + \
               [(">" + b if b.startswith("From ") else b) for b in body]
        o.D["approvals"].append({"from": r["from"].lower(), "at": r["at"], "key": norm(kv), "nominal": r["nominal"], "ord": idx, "src": f})
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- outages
def _rfc822(t):
    y, mo, d, h, mi, s, wd = fields(t)
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (WDAYS[wd], d, MONTHS[mo - 1], y, h, mi, s)


def _render_outages(o, w):
    f = "outages.rss"
    rng = _rng(w, f)
    items = sorted(w.outages, key=lambda x: (x["pub_at"], x["guid"]))
    items = clean_first(items, lambda x: x["rev"] > 1 or x["pub_at"] >= w.p0 - DAY)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>', "<title>Quillfen status</title>",
           "<link>https://status.quillfen.example/</link>", "<description>Platform incidents</description>"]
    bad_at = bad_positions(rng, len(items), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("<item><title>Maintenance</title><guid isPermaLink=\"false\">OUT-BAD-%d</guid><pubDate>soon</pubDate>"
                       "<description>window=?;status=active</description></item>" % idx)
            o.bad(f, idx)
            continue
        if ri >= len(items):
            break
        x = items[ri]
        ri += 1
        guid = x["guid"] if x["rev"] == 1 else "%s/r%d" % (x["guid"], x["rev"])
        if x["rev"] > 1 or x["status"] != "active" or x["pub_at"] >= w.p0 - DAY:
            o.trap(f)
        out.append("<item><title>%s</title><guid isPermaLink=\"false\">%s</guid><pubDate>%s</pubDate>"
                   "<description>window=%s/%s;status=%s</description></item>" % (x["title"], guid, _rfc822(x["pub_at"]), iso(x["a"]), iso(x["b"]), x["status"]))
        o.D["outages"].append({"guid": x["guid"], "pub_at": x["pub_at"], "a": x["a"], "b": x["b"], "status": x["status"], "ord": idx, "src": f})
    out.append("</channel></rss>")
    o.files[f] = ("\n".join(out) + "\n").encode()

    f = "incident_register.md"
    rng = _rng(w, f)
    rows = list(w.incidents)
    rows = clean_first(rows, lambda r: r["outage"].startswith("OUT-%d" % ymd(w.p0)[0]))
    out = ["# Incident register", "", "Datasets recorded against each published outage.", "",
           "| outage | dataset | noted by |", "|---|---|---|"]
    bad_at = bad_positions(rng, len(rows), 12, 60)
    idx = ri = 0
    while True:
        idx += 1
        if idx in bad_at:
            out.append("| | lake.orders_daily |")
            o.bad(f, idx)
            continue
        if ri >= len(rows):
            break
        r = rows[ri]
        ri += 1
        dv, tv = ds_variant(rng, r["dataset"], p=0.25 if idx > 50 else 0)
        if tv or r["outage"].startswith("OUT-%d" % ymd(w.p0)[0]):
            o.trap(f)
        out.append("| %s | %s | %s |" % (r["outage"], dv, rng.choice(w.people)["handles"][0]))
        o.D["incidents"].append({"outage": r["outage"], "dataset": norm(dv)})
    o.files[f] = ("\n".join(out) + "\n").encode()


def _backfills(o, w):
    f = "backfills.edn"
    rng = _rng(w, f)
    rows = sorted(w.backfills, key=lambda b: (b["requested_at"], b["run_id"]))
    pads = []
    k = 0
    while len(rows) + len(pads) < 205:
        job = rng.choice([j for j in w.jobs if not j.get("retired")])
        t = w.hist0 + rng.randrange(0, 900) * DAY + 5 * 3600
        pads.append({"run_id": "bf-hist%05d" % k, "key": name_at(job, t), "nominal": t, "requested_at": t + 86400,
                     "by": rng.choice(w.people)["handles"][0]})
        k += 1
    allrows = clean_first(sorted(rows + pads, key=lambda b: (b["requested_at"], b["run_id"])), lambda b: not b["run_id"].startswith("bf-hist"))
    out = [";; backfill requests exported from the orchestration console", "["]
    bad_at = bad_positions(rng, len(allrows), 12, 60)
    idx = ri = 0

    def inst(t):
        return '#inst "%s.000-00:00"' % iso(t)[:-1]
    while True:
        idx += 1
        if idx in bad_at:
            out.append(' {:run-id "bf-broken%d" :job "x" :nominal #inst "never"}' % idx)
            o.bad(f, idx)
            continue
        if ri >= len(allrows):
            break
        b = allrows[ri]
        ri += 1
        kv, tv = variant(rng, b["key"], p=0.2 if idx > 50 else 0)
        if tv or not b["run_id"].startswith("bf-hist"):
            o.trap(f)
        out.append(' {:run-id "%s" :job "%s" :nominal %s :requested-by "%s" :requested-at %s}' % (
            b["run_id"], kv, inst(b["nominal"]), b["by"], inst(b["requested_at"])))
        o.D["backfills"].append({"run_id": b["run_id"], "key": norm(kv), "nominal": b["nominal"], "ord": idx, "src": f})
    out.append("]")
    o.files[f] = ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------- evidence (not settlement inputs)
def _ods(rows):
    def cell(v):
        return '<table:table-cell office:value-type="string"><text:p>%s</text:p></table:table-cell>' % str(v).replace("&", "&amp;").replace("<", "&lt;")
    body = "".join("<table:table-row>%s</table:table-row>" % "".join(cell(v) for v in r) for r in rows)
    content = ('<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">'
               '<office:body><office:spreadsheet><table:table table:name="rulings">%s</table:table></office:spreadsheet></office:body></office:document-content>' % body)
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        info = zipfile.ZipInfo("mimetype", date_time=(1980, 1, 1, 0, 0, 0))
        z.writestr(info, "application/vnd.oasis.opendocument.spreadsheet", compress_type=zipfile.ZIP_STORED)
        for name, data in [("META-INF/manifest.xml", manifest), ("content.xml", content)]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    return bio.getvalue()


def _evidence(o, w):
    f = "scheduler_ticks.tsv"
    out = ["job\tzone\tschedule\twall_time\tfired_at_utc"]
    for t in w.ticks:
        out.append("%s\t%s\t%s\t%s\t%s" % (t["key"], t["zone"], t["cron"], t["wall"], ",".join(t["fired"]) if t["fired"] else "-"))
        if len(t["fired"]) != 1 or True:
            pass
    o.files[f] = ("\n".join(out) + "\n").encode()
    o.traps[f] = sum(1 for t in w.ticks if len(t["fired"]) == 1 and t["wall"][11:13] in ("01", "02"))

    f = "sensor_waits.xml"
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<sensorWaits retained_from="%s" retained_to="%s">' % (iso(w.p0 - 28 * DAY), iso(w.p0))]
    for s in sorted(w.sensor, key=lambda s: (s["down_nominal"], s["down"], s["up"])):
        out.append('  <wait downstream="%s" downstream_nominal="%s" upstream="%s" waited_on="%s" edge_lag="%d" released_at="%s"/>' % (
            s["down"], iso(s["down_nominal"]), s["up"], iso(s["up_nominal"]), s["lag"], iso(s["at"])))
    out.append("</sensorWaits>")
    o.files[f] = ("\n".join(out) + "\n").encode()
    o.traps[f] = sum(1 for s in w.sensor if s["lag"] or s["up_nominal"] < s["down_nominal"])

    f = "review_rulings.ods"
    rows = [["ruling", "dispute", "subject", "outcome", "accepted_event_at"]]
    for r in w.rulings:
        rows.append([r["id"], r["type"], r["ref"], r["token"], iso(r["accepted_at"]) if r.get("accepted_at") else ""])
    o.files[f] = _ods(rows)
    o.traps[f] = sum(1 for r in w.rulings if r["type"] in ("re_land", "operator_mark"))

# ============================================================================ repaired reference repository
# The repaired repository, one source file per line, used to build single-defect variants.
REFERENCE_TREE = {
    "README.md": "# quillfen-settle\n\nSettlement engine for the Quillfen data platform's scheduled commitments. It reads one settlement extract (the\nexports of the schedulers, worker pools, landing systems, calendars, directory and ownership history) and writes the\nsettled output set described by the settlement contract.\n\n## Running\n\n```\nPYTHONPATH=src python3 -m quillfen settle /path/to/extract /path/to/output\n```\n\n## Layout\n\n- `src/quillfen/parsers` reads each export into normalised records\n- `src/quillfen/core` identity, schedules, calendars, evidence, dependencies and status\n- `src/quillfen/report` money, blame, chargeback and the output writers\n\n## Tests\n\n```\nPYTHONPATH=src python3 -m unittest discover -s tests -t .\n```\n\nThe engine uses the Python standard library only.\n",
    "pyproject.toml": "[project]\nname = \"quillfen-settle\"\nversion = \"7.0.3\"\ndescription = \"Scheduled commitment settlement engine for the Quillfen data platform\"\nrequires-python = \">=3.11\"\ndependencies = []\n\n[project.scripts]\nquillfen = \"quillfen.cli:main\"\n\n[tool.setuptools.packages.find]\nwhere = [\"src\"]\n",
    "src/quillfen/__init__.py": "\"\"\"Quillfen scheduled commitment settlement engine.\"\"\"\n\n__version__ = \"7.0.3\"\n",
    "src/quillfen/__main__.py": "import sys\n\nfrom .cli import main\n\nsys.exit(main())\n",
    "src/quillfen/cli.py": "\"\"\"Command line entry point: python -m quillfen settle <input_dir> <output_dir>.\"\"\"\nfrom __future__ import annotations\n\nimport argparse\nimport sys\n\n\ndef main(argv=None) -> int:\n    parser = argparse.ArgumentParser(prog=\"quillfen\")\n    sub = parser.add_subparsers(dest=\"command\", required=True)\n    s = sub.add_parser(\"settle\", help=\"settle one extract directory\")\n    s.add_argument(\"input_dir\")\n    s.add_argument(\"output_dir\")\n    args = parser.parse_args(argv)\n    if args.command == \"settle\":\n        from .pipeline import settle\n        from .report.writers import write\n        write(settle(args.input_dir), args.output_dir)\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
    "src/quillfen/core/__init__.py": "",
    "src/quillfen/core/audit.py": "\"\"\"Scheduler state machine audit.\"\"\"\nfrom __future__ import annotations\n\nLEGAL = {\n    (\"none\", \"queued\"), (\"queued\", \"running\"), (\"queued\", \"removed\"), (\"running\", \"success\"),\n    (\"running\", \"failed\"), (\"failed\", \"up_for_retry\"), (\"up_for_retry\", \"queued\"),\n    (\"success\", \"cleared\"), (\"failed\", \"cleared\"), (\"cleared\", \"queued\"),\n}\n\n\ndef illegal_transitions(transitions_by_interval: dict) -> list:\n    \"\"\"(job index, nominal, run id, from state, to state, instant) for every illegal step.\"\"\"\n    runs = {}\n    for (idx, nominal), rows in transitions_by_interval.items():\n        for t in rows:\n            runs.setdefault((idx, nominal, t.run_id), []).append(t)\n    out = []\n    for (idx, nominal, run_id), rows in runs.items():\n        rows.sort(key=lambda t: (t.at, t.origin.source, t.origin.ordinal))\n        state = \"none\"\n        for t in rows:\n            if (state, t.state) not in LEGAL:\n                out.append((idx, nominal, run_id, state, t.state, t.at))\n            state = t.state\n    return out\n",
    "src/quillfen/core/calendars.py": "\"\"\"Recurring calendar windows: change freezes, holidays and the on-call rota.\"\"\"\nfrom __future__ import annotations\n\nfrom ..timebase import DAY, ZoneTable, civil, instant\n\nWEEKDAYS = {\"MO\": 0, \"TU\": 1, \"WE\": 2, \"TH\": 3, \"FR\": 4, \"SA\": 5, \"SU\": 6}\n\n\ndef _until(text: str) -> int:\n    t = text.rstrip(\"Z\")\n    return instant(int(t[0:4]), int(t[4:6]), int(t[6:8]), int(t[9:11]), int(t[11:13]), int(t[13:15]))\n\n\ndef occurrence_walls(start_wall: int, rule: dict, zones: ZoneTable, zone: str, horizon_wall: int) -> list:\n    \"\"\"Occurrence start wall times of a DAILY or WEEKLY rule; UNTIL is compared as an instant.\"\"\"\n    if not rule:\n        return [start_wall]\n    freq = rule.get(\"FREQ\", \"DAILY\")\n    interval = int(rule.get(\"INTERVAL\", \"1\"))\n    count = int(rule[\"COUNT\"]) if \"COUNT\" in rule else None\n    until = _until(rule[\"UNTIL\"]) if \"UNTIL\" in rule else None\n    y, mo, d, h, mi, s, wd = civil(start_wall)\n    time_of_day = h * 3600 + mi * 60 + s\n    first_day = start_wall - time_of_day\n    out = []\n\n    def stop(w):\n        if w > horizon_wall:\n            return True\n        return until is not None and zones.instants_for_wall(zone, w)[:1] and zones.instants_for_wall(zone, w)[0] > until\n\n    if freq == \"DAILY\":\n        k = 0\n        while True:\n            w = first_day + k * interval * DAY + time_of_day\n            if stop(w):\n                break\n            out.append(w)\n            if count is not None and len(out) >= count:\n                break\n            k += 1\n        return out\n    if freq != \"WEEKLY\":\n        raise ValueError(\"unsupported FREQ %s\" % freq)\n    days = sorted(WEEKDAYS[x] for x in rule[\"BYDAY\"].split(\",\")) if \"BYDAY\" in rule else [wd]\n    week = first_day - wd * DAY\n    k = 0\n    while True:\n        for dw in days:\n            w = week + k * interval * 7 * DAY + dw * DAY + time_of_day\n            if w < start_wall:\n                continue\n            if stop(w):\n                return out\n            out.append(w)\n            if count is not None and len(out) >= count:\n                return out\n        k += 1\n\n\ndef freeze_windows(events: list, zones: ZoneTable, horizon: int) -> list:\n    \"\"\"(start instant, end instant, tiers) for every occurrence after exceptions and overrides.\"\"\"\n    overrides = {}\n    for ev in events:\n        if ev.recurrence_id is not None:\n            overrides[(ev.uid, ev.recurrence_id)] = ev\n    windows = []\n    for ev in events:\n        if ev.recurrence_id is not None:\n            continue\n        length = ev.end_wall - ev.start_wall\n        excluded = set(ev.exdates)\n        for w in occurrence_walls(ev.start_wall, ev.rrule, zones, ev.zone, horizon):\n            if w in excluded:\n                continue\n            o = overrides.get((ev.uid, w))\n            if o is not None:\n                if o.cancelled:\n                    continue\n                a, b = o.start_wall, o.end_wall\n            else:\n                a, b = w, w + length\n            windows.append((zones.wall_to_instant(ev.zone, a), zones.wall_to_instant(ev.zone, b), set(ev.categories)))\n    return windows\n\n\ndef rota_shifts(events: list, zones: ZoneTable, horizon: int) -> list:\n    \"\"\"(team, start instant, end instant, attendee address) for every rota occurrence.\"\"\"\n    overrides = {}\n    for ev in events:\n        if ev.recurrence_id is not None:\n            overrides[(ev.uid, ev.recurrence_id)] = ev\n    shifts = []\n    for ev in events:\n        if ev.recurrence_id is not None or ev.start_wall is None:\n            continue\n        length = ev.end_wall - ev.start_wall\n        for w in occurrence_walls(ev.start_wall, ev.rrule, zones, ev.zone, horizon):\n            attendee = ev.attendee\n            o = overrides.get((ev.uid, w))\n            if o is not None:\n                if o.cancelled:\n                    continue\n                attendee = o.attendee or attendee\n            shifts.append((ev.team, zones.wall_to_instant(ev.zone, w), zones.wall_to_instant(ev.zone, w + length), attendee))\n    return shifts\n",
    "src/quillfen/core/clock.py": "\"\"\"Host clock correction.\"\"\"\nfrom __future__ import annotations\n\nimport bisect\n\nWINDOW_MS = 86_400_000\n\n\nclass ClockBook:\n    def __init__(self, samples: list):\n        self.by_host = {}\n        for s in samples:\n            self.by_host.setdefault(s.host, []).append((s.at_ms, s.offset_ms))\n        for lst in self.by_host.values():\n            lst.sort()\n        self.keys = {h: [t for t, _ in lst] for h, lst in self.by_host.items()}\n\n    def correct(self, host: str, local_ms: int):\n        \"\"\"Corrected instant in whole seconds, or None when no usable calibration sample exists.\n\n        The governing sample is the latest one stamped at or before the uncorrected reading and no\n        more than a day older than it. Offsets are local clock minus true time.\"\"\"\n        lst = self.by_host.get(host)\n        if not lst:\n            return None\n        i = bisect.bisect_right(self.keys[host], local_ms) - 1\n        if i < 0:\n            return None\n        at_ms, offset_ms = lst[i]\n        if local_ms - at_ms > WINDOW_MS:\n            return None\n        return (local_ms - offset_ms) // 1000\n",
    "src/quillfen/core/commitments.py": "\"\"\"Scheduled commitments: spec timelines, SLA overrides and interval expansion.\"\"\"\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass\n\nfrom ..timebase import DAY, MINUTE\nfrom .cron import Schedule, fires_between\nfrom .identity import Identity, Job\n\nLOOKBACK = 8 * DAY\n\n\n@dataclass\nclass Interval:\n    job: Job\n    nominal: int\n    deadline: int\n    tier: int\n    sla_minutes: int\n    zone: str\n    suspension: str = \"\"\n\n    @property\n    def key(self):\n        return (self.job.index, self.nominal)\n\n\nclass SpecTimeline:\n    def __init__(self, identity: Identity, specs: list):\n        self.by_job = {}\n        for s in specs:\n            job = identity.resolve_key(s.key, s.effective)\n            self.by_job.setdefault(job.index, []).append(s)\n        for revs in self.by_job.values():\n            revs.sort(key=lambda s: s.effective)\n\n    def windows(self, job: Job):\n        revs = self.by_job.get(job.index, [])\n        for i, s in enumerate(revs):\n            end = revs[i + 1].effective if i + 1 < len(revs) else None\n            yield s, s.effective, end\n\n\nclass SlaBook:\n    def __init__(self, identity: Identity, overrides: list, corpus):\n        self.by_job = {}\n        for o in overrides:\n            if not identity.known(o.key):\n                corpus.reject(o.origin, \"UNKNOWN_JOB\")\n                continue\n            job = identity.resolve_key(o.key, o.effective)\n            self.by_job.setdefault(job.index, []).append(o)\n        for lst in self.by_job.values():\n            lst.sort(key=lambda o: (o.effective, o.origin.ordinal))\n\n    def effective_sla(self, job: Job, nominal: int, base_minutes: int) -> int:\n        \"\"\"Latest override at or before the nominal instant; an empty override cancels back to the base.\"\"\"\n        current = None\n        for o in self.by_job.get(job.index, []):\n            if o.effective > nominal:\n                break\n            current = o.minutes\n        return base_minutes if current is None else current\n\n\ndef expand(identity: Identity, timeline: SpecTimeline, sla: SlaBook, zones, period_start: int, period_end: int) -> dict:\n    intervals = {}\n    lo = period_start - LOOKBACK\n    for job in identity.jobs:\n        for spec, start, end in timeline.windows(job):\n            if not spec.enabled or not spec.schedule:\n                continue\n            a = max(start, lo)\n            b = period_end if end is None else min(end, period_end)\n            if a >= b:\n                continue\n            for t in fires_between(Schedule(spec.schedule), zones, spec.zone, a, b):\n                minutes = sla.effective_sla(job, t, spec.sla_minutes)\n                deadline = t + minutes * MINUTE\n                if period_start <= deadline < period_end:\n                    iv = Interval(job=job, nominal=t, deadline=deadline, tier=spec.tier, sla_minutes=minutes, zone=spec.zone)\n                    intervals[iv.key] = iv\n    return intervals\n",
    "src/quillfen/core/cron.py": "\"\"\"Five-field cron schedules evaluated on a zone's wall clock.\"\"\"\nfrom __future__ import annotations\n\nimport calendar\n\nfrom ..timebase import DAY, HOUR, MINUTE, ZoneTable, civil, instant\n\n_MONTH_NAMES = {n: i + 1 for i, n in enumerate(\"JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC\".split())}\n_DAY_NAMES = {n: i for i, n in enumerate(\"SUN MON TUE WED THU FRI SAT\".split())}\n\n\ndef _value(token: str, names: dict | None) -> int:\n    if names and token.upper() in names:\n        return names[token.upper()]\n    if not token.isdigit():\n        raise ValueError(\"cron value %r\" % token)\n    return int(token)\n\n\ndef _field(text: str, lo: int, hi: int, names: dict | None = None) -> frozenset:\n    values = set()\n    for part in text.split(\",\"):\n        if not part:\n            raise ValueError(\"empty cron list item\")\n        step = 1\n        if \"/\" in part:\n            part, step_text = part.split(\"/\", 1)\n            if not step_text.isdigit() or int(step_text) == 0:\n                raise ValueError(\"cron step\")\n            step = int(step_text)\n        if part == \"*\":\n            first, last = lo, hi\n        elif \"-\" in part:\n            a, b = part.split(\"-\", 1)\n            first, last = _value(a, names), _value(b, names)\n        else:\n            first = _value(part, names)\n            last = hi if step > 1 else first\n        if first < lo or last > hi or first > last:\n            raise ValueError(\"cron range\")\n        values.update(range(first, last + 1, step))\n    return frozenset(values)\n\n\nclass Schedule:\n    def __init__(self, expression: str):\n        parts = expression.split()\n        if len(parts) != 5:\n            raise ValueError(\"cron needs five fields\")\n        self.expression = expression\n        self.minutes = _field(parts[0], 0, 59)\n        self.hours = _field(parts[1], 0, 23)\n        self.days_of_month = _field(parts[2], 1, 31)\n        self.months = _field(parts[3], 1, 12, _MONTH_NAMES)\n        self.days_of_week = frozenset(0 if d == 7 else d for d in _field(parts[4], 0, 7, _DAY_NAMES))\n        self.dom_restricted = not parts[2].startswith(\"*\")\n        self.dow_restricted = not parts[4].startswith(\"*\")\n\n    def day_matches(self, year: int, month: int, day: int) -> bool:\n        \"\"\"Standard cron: when both day fields are restricted, a day matching either one qualifies.\"\"\"\n        if month not in self.months:\n            return False\n        weekday = (calendar.weekday(year, month, day) + 1) % 7\n        by_dom = day in self.days_of_month\n        by_dow = weekday in self.days_of_week\n        if self.dom_restricted and self.dow_restricted:\n            return by_dom or by_dow\n        return by_dom and by_dow\n\n    def wall_times(self, first_day_wall: int, last_day_wall: int):\n        day = first_day_wall - first_day_wall % DAY\n        while day <= last_day_wall:\n            y, mo, d = civil(day)[:3]\n            if self.day_matches(y, mo, d):\n                for h in sorted(self.hours):\n                    for mi in sorted(self.minutes):\n                        yield day + h * HOUR + mi * MINUTE\n            day += DAY\n\n\ndef wall_to_fires(zones: ZoneTable, zone: str, wall: int) -> list:\n    \"\"\"Instants at which the scheduler fires for one scheduled wall time.\"\"\"\n    found = zones.instants_for_wall(zone, wall)\n    if len(found) == 1:\n        return found\n    if not found:\n        jump = zones.transition_before(zone, wall)\n        return [jump[0]] if jump else []\n    return [found[-1]]\n\n\ndef fires_between(schedule: Schedule, zones: ZoneTable, zone: str, lo: int, hi: int) -> list:\n    \"\"\"Distinct fire instants in [lo, hi).\"\"\"\n    out = set()\n    for wall in schedule.wall_times(lo - 2 * DAY, hi + 2 * DAY):\n        for t in wall_to_fires(zones, zone, wall):\n            if lo <= t < hi:\n                out.add(t)\n    return sorted(out)\n",
    "src/quillfen/core/deps.py": "\"\"\"Dependency edges and the upstream interval a downstream interval waits on.\"\"\"\nfrom __future__ import annotations\n\nimport bisect\n\nfrom .identity import Identity\n\n\nclass DependencyGraph:\n    def __init__(self, edges: list, identity: Identity, corpus):\n        self.identity = identity\n        self.edges = []\n        self.by_name = {}\n        for e in edges:\n            if not identity.known(e.upstream) or not identity.known(e.downstream):\n                corpus.reject(e.origin, \"UNKNOWN_JOB\")\n                continue\n            self.edges.append(e)\n            self.by_name.setdefault(e.downstream, []).append(e)\n\n    def edges_into(self, job, nominal: int) -> list:\n        out = []\n        for name in self.identity.names_of(job):\n            for e in self.by_name.get(name, []):\n                if e.valid_from is not None and nominal < e.valid_from:\n                    continue\n                if e.valid_to is not None and nominal >= e.valid_to:\n                    continue\n                if self.identity.resolve_key(e.downstream, nominal) is job:\n                    out.append(e)\n        return out\n\n\ndef governing_upstream(nominals: list, nominal: int, lag: int):\n    \"\"\"Position in the upstream job's sorted interval nominals that a downstream interval waits on.\"\"\"\n    i = bisect.bisect_left(nominals, nominal) - 1 - lag\n    return nominals[i] if i >= 0 else None\n\n\ndef upstream_intervals(graph: DependencyGraph, interval, nominals_by_job: dict) -> list:\n    found = set()\n    for e in graph.edges_into(interval.job, interval.nominal):\n        up = graph.identity.resolve_key(e.upstream, interval.nominal)\n        n = governing_upstream(nominals_by_job.get(up.index, []), interval.nominal, e.lag)\n        if n is not None:\n            found.add((up.index, n, e.lag))\n    return sorted(found)\n",
    "src/quillfen/core/evidence.py": "\"\"\"Evidence tiers and the instant an interval's data landed.\"\"\"\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, field\nfrom typing import Optional\n\nfrom .clock import ClockBook\nfrom .identity import Identity\nfrom .landing import governing_land\nfrom .people import People\n\nTIERS = (\"physical\", \"worker\", \"scheduler\", \"operator\", \"none\")\n\n\n@dataclass\nclass Evidence:\n    tier: str = \"none\"\n    landed_at: Optional[int] = None\n    candidates: int = 0\n    unresolvable: str = \"\"\n    datasets: set = field(default_factory=set)\n\n\ndef index_by_interval(records: list, identity: Identity, corpus) -> dict:\n    \"\"\"Group interval-referencing records by (job index, nominal); unknown keys are rejected.\"\"\"\n    out = {}\n    for r in records:\n        if not identity.known(r.key):\n            corpus.reject(r.origin, \"UNKNOWN_JOB\")\n            continue\n        job = identity.resolve_key(r.key, r.nominal)\n        out.setdefault((job.index, r.nominal), []).append(r)\n    return out\n\n\ndef mark_accepted(mark, approvals: list, people: People) -> bool:\n    \"\"\"An operator mark counts only when an approval that precedes it was sent by someone other than the actor.\"\"\"\n    actor = people.person_of_handle.get(mark.actor.lower())\n    for a in approvals:\n        if a.at > mark.at:\n            continue\n        approver = people.by_mail(a.sender)\n        if approver is not None and actor is not None and approver != actor:\n            return True\n    return False\n\n\ndef resolve(interval, producers, streams, workers, backfill_runs, clock: ClockBook, transitions, marks, approvals,\n            people: People) -> Evidence:\n    ev = Evidence()\n    key = interval.key\n    datasets = producers.datasets_for(interval.job, interval.nominal)\n    ev.datasets = datasets\n    if len(datasets) > 1 or any(len(producers.jobs_for(ds, interval.nominal)) > 1 for ds in datasets):\n        ev.unresolvable = \"AMBIGUOUS_PRODUCER\"\n        return ev\n    stream = None\n    if datasets:\n        ds = next(iter(datasets))\n        stream = streams.get((ds, interval.nominal))\n    if stream:\n        at, lands = governing_land(stream)\n        if lands:\n            ev.tier, ev.landed_at, ev.candidates = \"physical\", at, lands\n            return ev\n    commits = [w for w in workers.get(key, []) if w.event == \"commit\" and w.run_id not in backfill_runs]\n    if commits:\n        corrected = [clock.correct(w.host, w.local_ms) for w in commits]\n        usable = [c for c in corrected if c is not None]\n        ev.tier, ev.candidates = \"worker\", len(commits)\n        if usable:\n            ev.landed_at = min(usable)\n        else:\n            ev.unresolvable = \"UNCALIBRATED_CLOCK\"\n        return ev\n    successes = [t.at for t in transitions.get(key, []) if t.state == \"success\" and t.run_id not in backfill_runs]\n    if successes:\n        ev.tier, ev.landed_at, ev.candidates = \"scheduler\", min(successes), len(successes)\n        return ev\n    accepted = [m.at for m in marks.get(key, []) if m.action == \"mark_success\" and mark_accepted(m, approvals.get(key, []), people)]\n    if accepted:\n        ev.tier, ev.landed_at, ev.candidates = \"operator\", min(accepted), len(accepted)\n    return ev\n",
    "src/quillfen/core/identity.py": "\"\"\"Job identity across renames and reused names.\"\"\"\nfrom __future__ import annotations\n\nimport bisect\nfrom dataclasses import dataclass, field\n\nNEVER = -(10 ** 15)\nALWAYS = 10 ** 15\n\n\n@dataclass\nclass Job:\n    index: int\n    names: list = field(default_factory=list)   # [name, held_from, held_to]\n    canonical: str = \"\"\n\n\nclass Identity:\n    def __init__(self, renames: list, spec_keys: list, period_end: int):\n        self.jobs: list = []\n        holder = {}\n        for r in sorted(renames, key=lambda r: (r.effective, r.origin.ordinal)):\n            if not r.old_key:\n                job = self._new(r.new_key, r.effective)\n            else:\n                job = holder.get(r.old_key)\n                if job is None:\n                    job = self._new(r.old_key, NEVER)\n                job.names[-1][2] = r.effective\n                job.names.append([r.new_key, r.effective, ALWAYS])\n                holder.pop(r.old_key, None)\n            holder[r.new_key] = job\n        known = {n[0] for j in self.jobs for n in j.names}\n        for key in sorted(set(spec_keys)):\n            if key not in known:\n                self._new(key, NEVER)\n                known.add(key)\n        self.holders = {}\n        for job in self.jobs:\n            for name, frm, to in job.names:\n                self.holders.setdefault(name, []).append((frm, to, job.index))\n        for name in self.holders:\n            self.holders[name].sort()\n        closing = period_end - 1\n        for job in self.jobs:\n            held = [n for n in job.names if n[1] <= closing < n[2]]\n            if held:\n                job.canonical = \"job:\" + held[0][0]\n            elif job.names[0][1] > closing:\n                job.canonical = \"job:\" + job.names[0][0]\n            else:\n                job.canonical = \"job:\" + job.names[-1][0]\n\n    def _new(self, name: str, frm: int) -> Job:\n        job = Job(index=len(self.jobs), names=[[name, frm, ALWAYS]])\n        self.jobs.append(job)\n        return job\n\n    def known(self, key: str) -> bool:\n        return key in self.holders\n\n    def resolve_key(self, key: str, at: int):\n        \"\"\"The job holding `key` at `at`; else its most recent holder before `at`; else its first holder after.\"\"\"\n        spans = self.holders.get(key)\n        if not spans:\n            return None\n        for frm, to, idx in spans:\n            if frm <= at < to:\n                return self.jobs[idx]\n        before = [(to, idx) for frm, to, idx in spans if to <= at]\n        if before:\n            return self.jobs[max(before)[1]]\n        return self.jobs[min((frm, idx) for frm, to, idx in spans if frm > at)[1]]\n\n    def name_at(self, job: Job, at: int) -> str:\n        for name, frm, to in job.names:\n            if frm <= at < to:\n                return name\n        if at < job.names[0][1]:\n            return job.names[0][0]\n        return job.names[-1][0]\n\n    def names_of(self, job: Job) -> set:\n        return {n[0] for n in job.names}\n",
    "src/quillfen/core/landing.py": "\"\"\"Physical partition events and the land event that governs a partition.\"\"\"\nfrom __future__ import annotations\n\nfrom .identity import Identity\n\n\nclass Producers:\n    def __init__(self, rows: list, identity: Identity, corpus):\n        self.identity = identity\n        self.by_dataset = {}\n        self.by_name = {}\n        for r in rows:\n            if not identity.known(r.key):\n                corpus.reject(r.origin, \"UNKNOWN_JOB\")\n                continue\n            self.by_dataset.setdefault(r.dataset, []).append(r)\n            self.by_name.setdefault(r.key, []).append(r)\n\n    @staticmethod\n    def _live(r, at):\n        return r.valid_from <= at and (r.valid_to is None or at < r.valid_to)\n\n    def jobs_for(self, dataset: str, at: int) -> set:\n        out = set()\n        for r in self.by_dataset.get(dataset, []):\n            if self._live(r, at):\n                out.add(self.identity.resolve_key(r.key, at).index)\n        return out\n\n    def datasets_for(self, job, at: int) -> set:\n        out = set()\n        for name in self.identity.names_of(job):\n            for r in self.by_name.get(name, []):\n                if self._live(r, at) and self.identity.resolve_key(r.key, at) is job:\n                    out.add(r.dataset)\n        return out\n\n\ndef partition_streams(events: list, producers: Producers, corpus) -> dict:\n    \"\"\"Per (dataset, nominal): merged land and retract events ordered by instant, lands first on ties.\"\"\"\n    streams = {}\n    for e in events:\n        if not producers.jobs_for(e.dataset, e.nominal):\n            corpus.reject(e.origin, \"UNMAPPED_DATASET\")\n            continue\n        streams.setdefault((e.dataset, e.nominal), []).append(e)\n    for key, evs in streams.items():\n        evs.sort(key=lambda e: (e.at, 0 if e.kind == \"land\" else 1, e.origin.source, e.origin.ordinal))\n        landed = False\n        kept = []\n        for e in evs:\n            if e.kind == \"land\":\n                landed = True\n            elif not landed:\n                corpus.reject(e.origin, \"ORPHAN_TRANSITION\")\n                continue\n            kept.append(e)\n        streams[key] = kept\n    return streams\n\n\ndef governing_land(stream: list):\n    \"\"\"(instant of the governing land event or None, number of land events).\"\"\"\n    lands = [e for e in stream if e.kind == \"land\"]\n    if not lands:\n        return None, 0\n    last_retract = None\n    for i, e in enumerate(stream):\n        if e.kind == \"retract\":\n            last_retract = i\n    if last_retract is None:\n        return lands[0].at, len(lands)\n    after = [e for e in stream[last_retract + 1:] if e.kind == \"land\"]\n    return (after[0].at if after else None), len(lands)\n",
    "src/quillfen/core/ownership.py": "\"\"\"Owning teams from the CODEOWNERS history and the team handle registry.\"\"\"\nfrom __future__ import annotations\n\nimport bisect\nimport re\nfrom functools import lru_cache\n\nfrom .identity import Identity, Job\n\n\ndef _pattern(glob: str):\n    return re.compile(\"^\" + \"\".join(\"[^/]*\" if ch == \"*\" else re.escape(ch) for ch in glob) + \"$\")\n\n\nclass Ownership:\n    def __init__(self, commits: list, handles: list, identity: Identity):\n        self.identity = identity\n        ordered = sorted(commits, key=lambda c: (c.committed, -c.origin.ordinal))\n        self.times = []\n        self.snapshots = []\n        lines = []\n        for c in ordered:\n            for op, glob, hs in c.changes:\n                if op == \"+\":\n                    lines.append((glob, _pattern(glob), tuple(hs)))\n                else:\n                    for i, existing in enumerate(lines):\n                        if existing[0] == glob:\n                            del lines[i]\n                            break\n            self.times.append(c.committed)\n            self.snapshots.append(list(lines))\n        self.handles = {}\n        for h in handles:\n            self.handles.setdefault(h.handle, []).append(h)\n        self._cache = {}\n\n    def team_for_handle(self, handle: str, at: int):\n        for b in self.handles.get(handle, []):\n            lo = b.valid_from if b.valid_from is not None else -(10 ** 15)\n            hi = b.valid_to if b.valid_to is not None else 10 ** 15\n            if lo <= at < hi:\n                return b.team\n        return None\n\n    def teams(self, job: Job, at: int) -> list:\n        key = (job.index, at)\n        if key in self._cache:\n            return self._cache[key]\n        i = bisect.bisect_right(self.times, at) - 1\n        result = []\n        if i >= 0:\n            path = \"jobs/\" + self.identity.name_at(job, at)\n            winner = None\n            # CODEOWNERS semantics: the last matching line takes precedence.\n            for glob, rx, hs in self.snapshots[i]:\n                if rx.match(path):\n                    winner = hs\n            if winner:\n                result = sorted({t for t in (self.team_for_handle(h, at) for h in winner) if t})\n        self._cache[key] = result\n        return result\n",
    "src/quillfen/core/people.py": "\"\"\"People from the directory and pager contacts.\"\"\"\nfrom __future__ import annotations\n\n\nclass People:\n    def __init__(self, directory: list, changes: list, contacts: list):\n        self.mails = {}\n        self.handles = {}\n        self.person_of_mail = {}\n        by_uid = {}\n        for p in directory:\n            pid = \"emp:\" + p.employee\n            by_uid[p.uid] = pid\n            self.mails.setdefault(pid, set()).update(p.mails)\n            self.handles.setdefault(pid, set())\n        for c in changes:\n            pid = by_uid.get(c.uid)\n            if pid is not None and c.op == \"add\":\n                self.mails[pid].add(c.mail)\n        for pid, mails in self.mails.items():\n            for m in mails:\n                self.person_of_mail[m] = pid\n        self.person_of_handle = {}\n        for card in contacts:\n            pid = None\n            for m in card.mails:\n                if m in self.person_of_mail:\n                    pid = self.person_of_mail[m]\n            if pid is None:\n                continue\n            for h in card.handles:\n                self.person_of_handle[h] = pid\n                self.handles[pid].add(h)\n\n    def by_mail(self, mail: str):\n        return self.person_of_mail.get(mail)\n",
    "src/quillfen/core/status.py": "\"\"\"Suspensions, outages and the settled status of every interval.\"\"\"\nfrom __future__ import annotations\n\nfrom ..timebase import civil\n\nSETTLED = (\"SUSPENDED\", \"UNRESOLVABLE\", \"MET\", \"EXCUSED_OUTAGE\", \"EXCUSED_UPSTREAM\", \"LATE\", \"MISSED\")\n\n\ndef pause_windows(pauses: list, identity, corpus) -> dict:\n    \"\"\"Pause state machine per job: a pause while paused is ignored, an unpause while running is an orphan.\"\"\"\n    events = []\n    for p in pauses:\n        if not identity.known(p.key):\n            corpus.reject(p.origin, \"UNKNOWN_JOB\")\n            continue\n        job = identity.resolve_key(p.key, p.at)\n        events.append((p.at, p.origin.ordinal, job.index, p))\n    windows = {}\n    open_since = {}\n    for at, _, idx, p in sorted(events, key=lambda e: (e[0], e[1])):\n        if p.action == \"pause\":\n            open_since.setdefault(idx, at)\n        elif idx in open_since:\n            windows.setdefault(idx, []).append((open_since.pop(idx), at))\n        else:\n            corpus.reject(p.origin, \"ORPHAN_TRANSITION\")\n    for idx, at in open_since.items():\n        windows.setdefault(idx, []).append((at, None))\n    return windows\n\n\ndef suspension_of(interval, freezes: list, pauses: dict, holidays: dict, owners, zones) -> str:\n    t = interval.nominal\n    for a, b, tiers in freezes:\n        if a <= t < b and interval.tier in tiers:\n            return \"FREEZE\"\n    for a, b in pauses.get(interval.job.index, []):\n        if a <= t and (b is None or t < b):\n            return \"PAUSE\"\n    if interval.tier == 3:\n        y, mo, d = civil(zones.wall(interval.zone, t))[:3]\n        for team in owners(interval.job, interval.deadline):\n            if (y, mo, d) in holidays.get(team, ()):\n                return \"HOLIDAY\"\n    return \"\"\n\n\ndef active_outages(notices: list, incidents: list) -> list:\n    \"\"\"Latest published revision of each outage governs; a retracted outage excuses nothing.\"\"\"\n    latest = {}\n    for n in notices:\n        cur = latest.get(n.guid)\n        if cur is None or (n.published, n.origin.ordinal) > (cur.published, cur.origin.ordinal):\n            latest[n.guid] = n\n    scope = {}\n    for i in incidents:\n        scope.setdefault(i.outage, set()).add(i.dataset)\n    return [(n.window_start, n.window_end, scope.get(guid, set())) for guid, n in sorted(latest.items()) if n.status == \"active\"]\n\n\ndef classify(interval, evidence, outages: list, upstream_statuses: list, period_end: int) -> str:\n    if interval.suspension:\n        return \"SUSPENDED\"\n    if evidence.unresolvable:\n        return \"UNRESOLVABLE\"\n    if evidence.landed_at is not None and evidence.landed_at < interval.deadline:\n        return \"MET\"\n    if any(a <= interval.deadline < b and (evidence.datasets & scope) for a, b, scope in outages):\n        return \"EXCUSED_OUTAGE\"\n    if any(s not in (\"MET\", \"SUSPENDED\") for s in upstream_statuses):\n        return \"EXCUSED_UPSTREAM\"\n    if evidence.landed_at is not None and evidence.landed_at < period_end:\n        return \"LATE\"\n    return \"MISSED\"\n",
    "src/quillfen/keys.py": "\"\"\"Key normalisation.\"\"\"\nfrom __future__ import annotations\n\nimport re\n\n_SEPARATORS = re.compile(r\"[-_./ ]+\")\n\n\ndef normalize_key(raw: str) -> str:\n    \"\"\"Job keys and dataset names compare only after this normalisation.\"\"\"\n    return _SEPARATORS.sub(\".\", raw.strip().lower()).strip(\".\")\n\n\ndef normalize_handle(raw: str) -> str:\n    return raw.strip().lower().lstrip(\"@\")\n\n\ndef normalize_mail(raw: str) -> str:\n    raw = raw.strip()\n    if raw.lower().startswith(\"mailto:\"):\n        raw = raw[7:]\n    return raw.lower()\n\n\ndef interval_id(canonical_job: str, nominal_text: str) -> str:\n    return \"%s@%s\" % (canonical_job, nominal_text)\n",
    "src/quillfen/parsers/__init__.py": "\"\"\"Reads a settlement extract directory into a Corpus.\"\"\"\nfrom __future__ import annotations\n\nfrom pathlib import Path\n\nfrom ..records import Corpus\nfrom . import graph, ical, landing, ops, org, scheduler, specs, workers\n\n# Files the engine never reads.\nNOT_INPUTS = (\"scheduler_ticks.tsv\", \"sensor_waits.xml\", \"review_rulings.ods\", \"operations-runbook.md\",\n              \"settlement-contract.md\", \"output-contract.md\", \"repo.zip\")\n\nREADERS = [\n    (\"host_inventory.csv\", org.read_hosts),\n    (\"job_renames.csv\", graph.read_renames),\n    (\"jobs_platform.toml\", specs.read_platform),\n    (\"jobs_analytics.json\", specs.read_analytics),\n    (\"jobs_finance.xml\", specs.read_finance),\n    (\"dependencies.dot\", graph.read_dependencies),\n    (\"dataset_producers.psv\", graph.read_producers),\n    (\"sla_overrides.properties\", graph.read_sla_overrides),\n    (\"ratecard.fwf\", graph.read_rates),\n    (\"ownership_history.gitlog\", org.read_ownership),\n    (\"team_registry.hcl\", org.read_handles),\n    (\"directory.ldif\", org.read_directory),\n    (\"pager_contacts.vcf\", org.read_contacts),\n    (\"freeze_windows.ics\", ical.read_freezes),\n    (\"team_holidays.xcs\", ical.read_holidays),\n    (\"oncall_rota.jcal\", ical.read_rota),\n    (\"job_pauses.ltsv\", ops.read_pauses),\n    (\"operator_audit.xlsx\", ops.read_operator),\n    (\"approvals.mbox\", ops.read_approvals),\n    (\"backfills.edn\", ops.read_backfills),\n    (\"outages.rss\", ops.read_outages),\n    (\"incident_register.md\", ops.read_incidents),\n    (\"sched_us.sqlite\", scheduler.read_us),\n    (\"sched_eu.ssv\", scheduler.read_eu),\n    (\"sched_apac.jsonl\", scheduler.read_apac),\n    (\"sched_legacy.syslog\", scheduler.read_legacy),\n    (\"workers_a.logfmt\", workers.read_logfmt),\n    (\"workers_b.cef\", workers.read_cef),\n    (\"workers_c.w3c.log\", workers.read_w3c),\n    (\"workers_d.evtx.xml\", workers.read_evtx),\n    (\"workers_e.access.log\", workers.read_access),\n    (\"workers_f.pbtxt\", workers.read_pbtxt),\n    (\"clock_offsets.prom\", workers.read_prometheus),\n    (\"heartbeats.txt\", workers.read_heartbeats),\n    (\"landing_objectstore.csv.gz\", landing.read_objectstore),\n    (\"landing_hdfs_audit.log\", landing.read_hdfs),\n    (\"landing_warehouse.sql\", landing.read_warehouse),\n    (\"landing_catalog.atom\", landing.read_catalog),\n    (\"landing_partner.xferlog\", landing.read_partner),\n    (\"partition_deletions.html\", landing.read_deletions),\n]\n\n\ndef read_corpus(directory: Path) -> Corpus:\n    directory = Path(directory)\n    corpus = Corpus()\n    graph.read_zones(directory / \"tz_transitions.csv\", corpus)\n    specs.read_period(directory / \"jobs_platform.toml\", corpus)\n    for name, fn in READERS:\n        fn(directory / name, corpus)\n    specs.read_legacy(directory / \"jobs_legacy.ini\", directory / \"crontab_legacy.cron\", corpus)\n    return corpus\n",
    "src/quillfen/parsers/common.py": "\"\"\"Helpers shared by the source readers.\"\"\"\nfrom __future__ import annotations\n\nimport re\nfrom pathlib import Path\n\nfrom ..records import Corpus, Origin\n\nMALFORMED = \"MALFORMED_RECORD\"\nMONTHS = {m: i + 1 for i, m in enumerate(\"Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec\".split())}\n\n\nclass Reader:\n    \"\"\"Iterates records of one source and turns any read failure into a MALFORMED_RECORD reject.\"\"\"\n\n    def __init__(self, corpus: Corpus, source: str):\n        self.corpus = corpus\n        self.source = source\n        self.ordinal = 0\n\n    def next(self) -> Origin:\n        self.ordinal += 1\n        return Origin(self.source, self.ordinal)\n\n    def malformed(self, origin: Origin) -> None:\n        self.corpus.reject(origin, MALFORMED)\n\n\ndef read_text(path: Path) -> str:\n    return path.read_text(encoding=\"utf-8\")\n\n\ndef require(value, message=\"missing field\"):\n    if value is None or (isinstance(value, str) and value.strip() == \"\"):\n        raise ValueError(message)\n    return value\n\n\ndef to_int(text, lo=None, hi=None) -> int:\n    if isinstance(text, bool):\n        raise ValueError(\"boolean is not an integer\")\n    if isinstance(text, int):\n        v = text\n    else:\n        if not re.fullmatch(r\"-?\\d+\", str(text).strip()):\n            raise ValueError(\"not an integer: %r\" % (text,))\n        v = int(str(text).strip())\n    if lo is not None and v < lo:\n        raise ValueError(\"below range\")\n    if hi is not None and v > hi:\n        raise ValueError(\"above range\")\n    return v\n\n\ndef host_instant(corpus: Corpus, host: str, wall: int) -> int:\n    \"\"\"A host wall-clock reading denotes the instant it reads in the zone of the host binding\n    whose validity window contains that instant; the latest-starting such binding wins.\"\"\"\n    zones = corpus.zones\n    best = None\n    for b in corpus.hosts:\n        if b.host != host:\n            continue\n        try:\n            t = zones.wall_to_instant(b.zone, wall)\n        except ValueError:\n            continue\n        lo = b.valid_from if b.valid_from is not None else -(10 ** 15)\n        hi = b.valid_to if b.valid_to is not None else 10 ** 15\n        if lo <= t < hi:\n            if best is None or lo > best[0]:\n                best = (lo, t)\n    if best is None:\n        raise ValueError(\"no host binding for %s\" % host)\n    return best[1]\n",
    "src/quillfen/parsers/graph.py": "\"\"\"Reference and relationship sources: zones, renames, dependencies, producers, SLA overrides, rates.\"\"\"\nfrom __future__ import annotations\n\nimport csv\nimport io\nimport re\nfrom pathlib import Path\n\nfrom ..keys import normalize_key\nfrom ..records import Corpus, Dependency, Producer, RateRow, Rename, SlaOverride\nfrom ..timebase import ZoneTable, parse_offset, parse_stamp\nfrom .common import Reader, read_text, require, to_int\n\n\ndef read_zones(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    table = ZoneTable()\n    rows = list(csv.reader(io.StringIO(read_text(path))))\n    for row in rows[1:]:\n        if not row:\n            continue\n        origin = reader.next()\n        try:\n            if len(row) != 3:\n                raise ValueError(\"columns\")\n            zone, effective, offset = (c.strip() for c in row)\n            require(zone)\n            if offset.startswith(\"=>\"):\n                if effective:\n                    raise ValueError(\"link rows carry no effective instant\")\n                table.links[zone] = require(offset[2:].strip())\n                continue\n            if not re.fullmatch(r\"[+-]\\d{2}:\\d{2}\", offset):\n                raise ValueError(\"offset\")\n            table.add(zone, parse_stamp(require(effective), default_offset=None), parse_offset(offset))\n        except ValueError:\n            reader.malformed(origin)\n    table.seal()\n    corpus.zones = table\n\n\ndef read_renames(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    rows = list(csv.reader(io.StringIO(read_text(path))))\n    for row in rows[1:]:\n        if not row:\n            continue\n        origin = reader.next()\n        try:\n            if len(row) != 3:\n                raise ValueError(\"columns\")\n            old, new, effective = row\n            corpus.renames.append(Rename(\n                old_key=normalize_key(old) if old.strip() else \"\",\n                new_key=normalize_key(require(new)),\n                effective=parse_stamp(require(effective), default_offset=None),\n                origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_EDGE = re.compile(r'^\\s*\"([^\"]+)\"\\s*->\\s*\"([^\"]+)\"\\s*(?:\\[(.*)\\])?\\s*;?\\s*$')\n_ATTR = re.compile(r'(\\w+)\\s*=\\s*(\"([^\"]*)\"|[^,\\s\\]]+)')\n\n\ndef read_dependencies(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if \"->\" not in line:\n            continue\n        origin = reader.next()\n        try:\n            m = _EDGE.match(line)\n            if not m:\n                raise ValueError(\"edge\")\n            attrs = {}\n            for a in _ATTR.finditer(m.group(3) or \"\"):\n                attrs[a.group(1)] = a.group(3) if a.group(3) is not None else a.group(2)\n            corpus.dependencies.append(Dependency(\n                upstream=normalize_key(m.group(1)),\n                downstream=normalize_key(m.group(2)),\n                lag=to_int(attrs.get(\"lag\", \"0\"), lo=0),\n                valid_from=parse_stamp(attrs[\"valid_from\"], default_offset=None) if attrs.get(\"valid_from\") else None,\n                valid_to=parse_stamp(attrs[\"valid_to\"], default_offset=None) if attrs.get(\"valid_to\") else None,\n                origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\ndef read_producers(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    lines = read_text(path).splitlines()\n    for line in lines[1:]:\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            parts = line.split(\"|\")\n            if len(parts) != 4:\n                raise ValueError(\"columns\")\n            dataset, key, frm, to = (p.strip() for p in parts)\n            corpus.producers.append(Producer(\n                dataset=normalize_key(require(dataset)),\n                key=normalize_key(require(key)),\n                valid_from=parse_stamp(require(frm), default_offset=None),\n                valid_to=parse_stamp(to, default_offset=None) if to else None,\n                origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_PROP_KEY = re.compile(r\"^sla\\.(.+)\\.(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z)$\")\n\n\ndef _split_property(line: str):\n    key = []\n    i = 0\n    while i < len(line):\n        ch = line[i]\n        if ch == \"\\\\\" and i + 1 < len(line):\n            key.append(line[i + 1])\n            i += 2\n            continue\n        if ch in \"=: \\t\":\n            break\n        key.append(ch)\n        i += 1\n    rest = line[i:].lstrip(\" \\t\")\n    if rest[:1] in (\"=\", \":\"):\n        rest = rest[1:]\n    return \"\".join(key), rest.strip()\n\n\ndef read_sla_overrides(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for raw in read_text(path).splitlines():\n        line = raw.strip()\n        if not line or line[0] in \"#!\":\n            continue\n        origin = reader.next()\n        try:\n            key, value = _split_property(line)\n            m = _PROP_KEY.match(key)\n            if not m:\n                raise ValueError(\"key\")\n            if value == \"\":\n                minutes = None\n            else:\n                minutes = to_int(value, lo=0)\n            corpus.sla_overrides.append(SlaOverride(\n                key=normalize_key(m.group(1)),\n                effective=parse_stamp(m.group(2), default_offset=None),\n                minutes=minutes,\n                origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_MONEY = re.compile(r\"^\\d+(?:\\.\\d{1,2})?$\")\n\n\ndef read_rates(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    lines = read_text(path).splitlines()\n    for line in lines[1:]:\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            parts = line.split()\n            if len(parts) != 6:\n                raise ValueError(\"columns\")\n            tier, bucket, effective, base, per_minute, currency = parts\n            if bucket not in (\"B0\", \"B30\", \"B120\") or currency != \"EUR\":\n                raise ValueError(\"bucket or currency\")\n            if not _MONEY.match(base) or not _MONEY.match(per_minute):\n                raise ValueError(\"amount\")\n            corpus.rates.append(RateRow(\n                tier=to_int(tier, 1, 3), bucket=bucket,\n                effective=parse_stamp(effective, default_offset=None),\n                base=base, per_minute=per_minute, origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n",
    "src/quillfen/parsers/ical.py": "\"\"\"Calendar sources: freeze windows (iCalendar), team holidays (xCal), on-call rota (jCal).\"\"\"\nfrom __future__ import annotations\n\nimport json\nimport re\nimport xml.etree.ElementTree as ET\nfrom pathlib import Path\n\nfrom ..keys import normalize_mail\nfrom ..records import CalendarEvent, Corpus, Holiday\nfrom ..timebase import instant\nfrom .common import Reader, read_text, require\n\n_LOCAL = re.compile(r\"^(\\d{4})(\\d{2})(\\d{2})T(\\d{2})(\\d{2})(\\d{2})$\")\n_XLOCAL = re.compile(r\"^(\\d{4})-(\\d{2})-(\\d{2})T(\\d{2}):(\\d{2}):(\\d{2})$\")\n\n\ndef unfold(text: str) -> list:\n    \"\"\"Logical content lines of an iCalendar file.\"\"\"\n    out = []\n    for raw in text.replace(\"\\r\\n\", \"\\n\").split(\"\\n\"):\n        if raw[:1] in (\" \", \"\\t\") and out:\n            out[-1] += raw[1:]\n        else:\n            out.append(raw)\n    return out\n\n\ndef _wall(text: str) -> int:\n    m = _LOCAL.match(text.strip())\n    if not m:\n        raise ValueError(\"local date-time\")\n    return instant(*(int(g) for g in m.groups()))\n\n\ndef _prop(line: str):\n    head, value = line.split(\":\", 1)\n    parts = head.split(\";\")\n    params = {}\n    for p in parts[1:]:\n        if \"=\" in p:\n            k, v = p.split(\"=\", 1)\n            params[k.upper()] = v\n    return parts[0].upper(), params, value\n\n\ndef rrule_dict(text: str) -> dict:\n    out = {}\n    for part in text.split(\";\"):\n        if \"=\" in part:\n            k, v = part.split(\"=\", 1)\n            out[k.upper()] = v\n    return out\n\n\ndef read_freezes(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    event = None\n    for line in unfold(read_text(path)):\n        if line == \"BEGIN:VEVENT\":\n            event = []\n            continue\n        if line == \"END:VEVENT\":\n            origin = reader.next()\n            try:\n                corpus.freezes.append(_freeze(event, origin, corpus))\n            except (ValueError, KeyError):\n                reader.malformed(origin)\n            event = None\n            continue\n        if event is not None and \":\" in line:\n            event.append(_prop(line))\n\n\ndef _freeze(props, origin, corpus) -> CalendarEvent:\n    uid = None\n    zone = None\n    start = end = rid = None\n    rule = {}\n    exdates = []\n    cats = []\n    cancelled = False\n    for name, params, value in props:\n        if name == \"UID\":\n            uid = value.strip()\n        elif name in (\"DTSTART\", \"DTEND\", \"RECURRENCE-ID\"):\n            zone = params.get(\"TZID\", zone)\n            w = _wall(value)\n            if name == \"DTSTART\":\n                start = w\n            elif name == \"DTEND\":\n                end = w\n            else:\n                rid = w\n        elif name == \"RRULE\":\n            rule = rrule_dict(value)\n        elif name == \"EXDATE\":\n            for v in value.split(\",\"):\n                m = _LOCAL.match(v.strip())\n                if m:\n                    exdates.append(instant(*(int(g) for g in m.groups())))\n        elif name == \"CATEGORIES\":\n            for c in value.split(\",\"):\n                m = re.fullmatch(r\"TIER([123])\", c.strip().upper())\n                if m:\n                    cats.append(int(m.group(1)))\n        elif name == \"STATUS\":\n            cancelled = value.strip().upper() == \"CANCELLED\"\n    require(uid)\n    if rid is None:\n        if start is None or end is None or end <= start:\n            raise ValueError(\"series needs DTSTART before DTEND\")\n    elif not cancelled and (start is None or end is None):\n        raise ValueError(\"override needs times\")\n    if not corpus.zones.knows(require(zone)):\n        raise ValueError(\"zone\")\n    return CalendarEvent(uid=uid, zone=zone, start_wall=start, end_wall=end, rrule=rule, exdates=exdates,\n                         categories=cats, recurrence_id=rid, cancelled=cancelled, attendee=None, team=None,\n                         origin=origin)\n\n\n_NS = \"{urn:ietf:params:xml:ns:icalendar-2.0}\"\n\n\ndef read_holidays(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    root = ET.fromstring(path.read_bytes())\n    for ev in root.iter(_NS + \"vevent\"):\n        origin = reader.next()\n        try:\n            date = require(ev.findtext(\"%sproperties/%sdtstart/%sdate\" % (_NS, _NS, _NS)))\n            team = require(ev.findtext(\"%sproperties/%sx-team/%stext\" % (_NS, _NS, _NS)))\n            y, m, d = (int(x) for x in re.fullmatch(r\"(\\d{4})-(\\d{2})-(\\d{2})\", date.strip()).groups())\n            instant(y, m, d)\n            corpus.holidays.append(Holiday(team=\"team:\" + team.strip(), date=(y, m, d), origin=origin))\n        except (ValueError, AttributeError):\n            reader.malformed(origin)\n\n\ndef read_rota(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    cal = json.loads(read_text(path))\n    for comp in cal[2]:\n        if comp[0] != \"vevent\":\n            continue\n        origin = reader.next()\n        try:\n            props = {}\n            params = {}\n            for p in comp[1]:\n                props[p[0]] = p[3]\n                params[p[0]] = p[1]\n            uid = require(props.get(\"uid\"))\n            rid = None\n            zone = None\n            start = None\n            if \"recurrence-id\" in props:\n                zone = params[\"recurrence-id\"].get(\"tzid\")\n                rid = _xwall(props[\"recurrence-id\"])\n            if \"dtstart\" in props:\n                zone = params[\"dtstart\"].get(\"tzid\")\n                start = _xwall(props[\"dtstart\"])\n            if rid is None and start is None:\n                raise ValueError(\"dtstart\")\n            days = 0\n            if \"duration\" in props:\n                m = re.fullmatch(r\"P(\\d+)D\", props[\"duration\"])\n                if not m:\n                    raise ValueError(\"duration\")\n                days = int(m.group(1))\n            rule = {}\n            for k, v in (props.get(\"rrule\") or {}).items():\n                if k == \"until\":\n                    v = v.replace(\"-\", \"\").replace(\":\", \"\")\n                rule[k.upper()] = str(v)\n            cancelled = str(props.get(\"status\", \"\")).upper() == \"CANCELLED\"\n            attendee = normalize_mail(props[\"attendee\"]) if props.get(\"attendee\") else None\n            if zone is not None and not corpus.zones.knows(zone):\n                raise ValueError(\"zone\")\n            corpus.rota.append(CalendarEvent(uid=uid, zone=zone or \"UTC\", start_wall=start,\n                                             end_wall=start + days * 86400 if start is not None else None,\n                                             rrule=rule, exdates=[], categories=[], recurrence_id=rid,\n                                             cancelled=cancelled, attendee=attendee,\n                                             team=(\"team:\" + props[\"x-team\"]) if props.get(\"x-team\") else None,\n                                             origin=origin))\n        except (ValueError, KeyError, TypeError):\n            reader.malformed(origin)\n\n\ndef _xwall(text: str) -> int:\n    m = _XLOCAL.match(str(text))\n    if not m:\n        raise ValueError(\"date-time\")\n    return instant(*(int(g) for g in m.groups()))\n",
    "src/quillfen/parsers/landing.py": "\"\"\"Physical partition evidence: object store, HDFS audit, warehouse registry, catalog, partner transfers, deletions.\"\"\"\nfrom __future__ import annotations\n\nimport csv\nimport gzip\nimport io\nimport re\nimport xml.etree.ElementTree as ET\nfrom html.parser import HTMLParser\nfrom pathlib import Path\n\nfrom ..keys import normalize_key\nfrom ..records import Corpus, PartitionEvent\nfrom ..timebase import instant, parse_stamp\nfrom .common import MONTHS, Reader, host_instant, read_text, require\n\n\ndef _event(corpus, origin, dataset, nominal, at, kind=\"land\"):\n    corpus.partition_events.append(PartitionEvent(dataset=normalize_key(require(dataset)), nominal=nominal, at=at,\n                                                  kind=kind, origin=origin))\n\n\n_TS = re.compile(r\"ts=(\\d{4})(\\d{2})(\\d{2})T(\\d{2})(\\d{2})Z\")\n\n\ndef read_objectstore(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    text = gzip.decompress(path.read_bytes()).decode(\"utf-8\")\n    rows = list(csv.reader(io.StringIO(text)))\n    for row in rows[1:]:\n        if not row:\n            continue\n        origin = reader.next()\n        try:\n            if len(row) != 5:\n                raise ValueError(\"columns\")\n            key = row[1]\n            m = _TS.search(key)\n            if not m or not key.endswith(\"/_SUCCESS\"):\n                raise ValueError(\"object key\")\n            dataset = key[: m.start()].rstrip(\"/\")\n            nominal = instant(*(int(g) for g in m.groups()))\n            _event(corpus, origin, dataset, nominal, parse_stamp(require(row[3]), default_offset=0))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_HDFS = re.compile(r\"^(\\d{4})-(\\d{2})-(\\d{2}) (\\d{2}):(\\d{2}):(\\d{2}),\\d{3} INFO FSNamesystem\\.audit: (.*)$\")\n_HDFS_SRC = re.compile(r\"^/warehouse/(.+)/(\\d{4})/(\\d{2})/(\\d{2})/(\\d{2})(\\d{2})/_SUCCESS$\")\n\n\ndef read_hdfs(path: Path, corpus: Corpus) -> None:\n    \"\"\"Only creations of a partition's _SUCCESS marker are landings; other audit lines carry no evidence.\"\"\"\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            m = _HDFS.match(line)\n            if not m:\n                raise ValueError(\"audit line\")\n            kv = dict(p.split(\"=\", 1) for p in m.group(7).split() if \"=\" in p)\n            if kv.get(\"cmd\") != \"create\" or not str(kv.get(\"src\", \"\")).endswith(\"/_SUCCESS\"):\n                continue\n            src = _HDFS_SRC.match(kv[\"src\"])\n            if not src:\n                raise ValueError(\"src\")\n            wall = instant(*(int(m.group(k)) for k in range(1, 7)))\n            at = host_instant(corpus, require(kv.get(\"host\")), wall)\n            nominal = instant(*(int(src.group(k)) for k in range(2, 7)))\n            _event(corpus, origin, src.group(1), nominal, at)\n        except ValueError:\n            reader.malformed(origin)\n\n\n_TUPLE = re.compile(r\"\\(\\s*'((?:[^']|'')*)'\\s*,\\s*'((?:[^']|'')*)'\\s*,\\s*'((?:[^']|'')*)'\\s*\\)\")\n\n\ndef read_warehouse(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    text = read_text(path)\n    for stmt in re.finditer(r\"INSERT INTO partition_registry \\(dataset, partition_ts, registered_at\\) VALUES(.*?);\", text, re.S):\n        for tup in _TUPLE.finditer(stmt.group(1)):\n            origin = reader.next()\n            try:\n                dataset, part, registered = (g.replace(\"''\", \"'\") for g in tup.groups())\n                _event(corpus, origin, dataset, parse_stamp(part, default_offset=0), parse_stamp(registered, default_offset=0))\n            except ValueError:\n                reader.malformed(origin)\n\n\n_ATOM = \"{http://www.w3.org/2005/Atom}\"\n\n\ndef read_catalog(path: Path, corpus: Corpus) -> None:\n    \"\"\"Catalog notices: 'published' marks a landing; a 'withdrawn' notice is catalogue metadata only.\"\"\"\n    reader = Reader(corpus, path.name)\n    root = ET.fromstring(path.read_bytes())\n    for entry in root.iter(_ATOM + \"entry\"):\n        origin = reader.next()\n        try:\n            cat = entry.find(_ATOM + \"category\")\n            term = cat.get(\"term\") if cat is not None else None\n            if term != \"published\":\n                continue\n            title = require(entry.findtext(_ATOM + \"title\")).split()\n            if len(title) != 2:\n                raise ValueError(\"title\")\n            _event(corpus, origin, title[0], parse_stamp(title[1], default_offset=None),\n                   parse_stamp(require(entry.findtext(_ATOM + \"updated\")), default_offset=None))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_XFER_FILE = re.compile(r\"^/incoming/(.+)_(\\d{4})(\\d{2})(\\d{2})(\\d{2})(\\d{2})\\.csv\\.gz$\")\n\n\ndef read_partner(path: Path, corpus: Corpus) -> None:\n    \"\"\"xferlog: only completed ('c') incoming transfers are landings.\"\"\"\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            f = line.split()\n            if len(f) != 18:\n                raise ValueError(\"fields\")\n            mon, day, clock, year = f[1], int(f[2]), f[3], int(f[4])\n            if mon not in MONTHS:\n                raise ValueError(\"month\")\n            h, mi, s = (int(x) for x in clock.split(\":\"))\n            if f[17] != \"c\" or f[11] != \"i\":\n                continue\n            fm = _XFER_FILE.match(f[8])\n            if not fm:\n                raise ValueError(\"filename\")\n            at = host_instant(corpus, f[6], instant(year, MONTHS[mon], day, h, mi, s))\n            nominal = instant(*(int(fm.group(k)) for k in range(2, 7)))\n            _event(corpus, origin, fm.group(1), nominal, at)\n        except ValueError:\n            reader.malformed(origin)\n\n\nclass _Table(HTMLParser):\n    def __init__(self):\n        super().__init__()\n        self.rows = []\n        self._row = None\n        self._cell = None\n        self._in_table = False\n\n    def handle_starttag(self, tag, attrs):\n        if tag == \"table\" and dict(attrs).get(\"id\") == \"deletions\":\n            self._in_table = True\n        elif self._in_table and tag == \"tr\":\n            self._row = []\n        elif self._in_table and tag == \"td\" and self._row is not None:\n            self._cell = []\n\n    def handle_endtag(self, tag):\n        if tag == \"table\":\n            self._in_table = False\n        elif tag == \"td\" and self._cell is not None:\n            self._row.append(\"\".join(self._cell).strip())\n            self._cell = None\n        elif tag == \"tr\" and self._row is not None:\n            if self._row:\n                self.rows.append(self._row)\n            self._row = None\n\n    def handle_data(self, data):\n        if self._cell is not None:\n            self._cell.append(data)\n\n\ndef read_deletions(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    table = _Table()\n    table.feed(read_text(path))\n    for cells in table.rows:\n        origin = reader.next()\n        try:\n            if len(cells) != 4:\n                raise ValueError(\"columns\")\n            m = re.fullmatch(r\"(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}) UTC\", cells[2])\n            if not m:\n                raise ValueError(\"deleted at\")\n            _event(corpus, origin, cells[0], parse_stamp(require(cells[1]), default_offset=None),\n                   parse_stamp(m.group(1), default_offset=0), kind=\"retract\")\n        except ValueError:\n            reader.malformed(origin)\n",
    "src/quillfen/parsers/ops.py": "\"\"\"Operations sources: pauses, operator audit, approvals, backfills, outages, incident register.\"\"\"\nfrom __future__ import annotations\n\nimport email.utils\nimport re\nimport xml.etree.ElementTree as ET\nimport zipfile\nfrom pathlib import Path\n\nfrom ..keys import normalize_key, normalize_mail\nfrom ..records import Approval, Backfill, Corpus, IncidentScope, OperatorAction, OutageNotice, PauseEvent\nfrom ..timebase import instant, parse_stamp\nfrom .common import Reader, read_text, require\n\nEXCEL_EPOCH = instant(1899, 12, 30)\n\n\ndef _target(text: str):\n    key, _, nominal = require(text).rpartition(\"@\")\n    return normalize_key(require(key)), parse_stamp(require(nominal), default_offset=None)\n\n\ndef read_pauses(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            fields = dict(part.split(\":\", 1) for part in line.split(\"\\t\") if \":\" in part)\n            action = require(fields.get(\"action\"))\n            if action not in (\"pause\", \"unpause\"):\n                raise ValueError(\"action\")\n            corpus.pauses.append(PauseEvent(key=normalize_key(require(fields.get(\"job\"))),\n                                            at=parse_stamp(require(fields.get(\"time\")), default_offset=None),\n                                            action=action, origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_SS = \"{http://schemas.openxmlformats.org/spreadsheetml/2006/main}\"\n\n\ndef _sheet_rows(path: Path):\n    with zipfile.ZipFile(path) as z:\n        root = ET.fromstring(z.read(\"xl/worksheets/sheet1.xml\"))\n    for row in root.iter(_SS + \"row\"):\n        cells = []\n        for c in row.findall(_SS + \"c\"):\n            if c.get(\"t\") == \"inlineStr\":\n                cells.append(\"\".join(t.text or \"\" for t in c.iter(_SS + \"t\")))\n            else:\n                v = c.find(_SS + \"v\")\n                cells.append(v.text if v is not None else \"\")\n        yield cells\n\n\ndef read_operator(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    rows = list(_sheet_rows(path))\n    for cells in rows[1:]:\n        origin = reader.next()\n        try:\n            stamp, actor, action, target = cells[0], cells[1], cells[2], cells[3]\n            if not re.fullmatch(r\"\\d+(\\.\\d+)?\", stamp.strip()):\n                raise ValueError(\"timestamp must be a spreadsheet serial\")\n            at = EXCEL_EPOCH + int(round(float(stamp) * 86400))\n            key, nominal = _target(target)\n            corpus.operator_actions.append(OperatorAction(at=at, actor=require(actor).strip().lower(),\n                                                          action=require(action).strip(), key=key,\n                                                          nominal=nominal, origin=origin))\n        except (ValueError, IndexError):\n            reader.malformed(origin)\n\n\ndef read_approvals(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    messages = []\n    current = None\n    previous_blank = True\n    for line in read_text(path).splitlines():\n        if line.startswith(\"From \") and previous_blank:\n            current = []\n            messages.append(current)\n        elif current is not None:\n            current.append(line)\n        previous_blank = line.strip() == \"\"\n    for msg in messages:\n        origin = reader.next()\n        try:\n            headers = {}\n            for line in msg:\n                if line.strip() == \"\":\n                    break\n                if \":\" in line:\n                    k, v = line.split(\":\", 1)\n                    headers[k.strip().lower()] = v.strip()\n            parsed = email.utils.parsedate_to_datetime(require(headers.get(\"date\")))\n            if parsed is None or parsed.tzinfo is None:\n                raise ValueError(\"date\")\n            key, nominal = _target(headers.get(\"x-quillfen-interval\"))\n            sender = email.utils.parseaddr(require(headers.get(\"from\")))[1]\n            corpus.approvals.append(Approval(sender=normalize_mail(require(sender)), at=int(parsed.timestamp()),\n                                             key=key, nominal=nominal, origin=origin))\n        except (ValueError, TypeError):\n            reader.malformed(origin)\n\n\n_EDN = re.compile(r'\\{(.*)\\}')\n_EDN_PAIR = re.compile(r':([\\w-]+)\\s+(#inst\\s+\"[^\"]*\"|\"(?:[^\"\\\\]|\\\\.)*\")')\n\n\ndef read_backfills(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        m = _EDN.search(line)\n        if not m or line.lstrip().startswith(\";\"):\n            continue\n        origin = reader.next()\n        try:\n            pairs = {}\n            for k, v in _EDN_PAIR.findall(m.group(1)):\n                if v.startswith(\"#inst\"):\n                    v = parse_stamp(re.search(r'\"([^\"]*)\"', v).group(1).replace(\".000\", \"\"), default_offset=None)\n                else:\n                    v = v[1:-1]\n                pairs[k] = v\n            corpus.backfills.append(Backfill(run_id=require(pairs.get(\"run-id\")), key=normalize_key(require(pairs.get(\"job\"))),\n                                             nominal=require(pairs.get(\"nominal\")), origin=origin))\n        except (ValueError, AttributeError):\n            reader.malformed(origin)\n\n\ndef read_outages(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    root = ET.fromstring(path.read_bytes())\n    for item in root.iter(\"item\"):\n        origin = reader.next()\n        try:\n            guid = require(item.findtext(\"guid\")).strip().split(\"/\")[0]\n            pub = email.utils.parsedate_to_datetime(require(item.findtext(\"pubDate\")))\n            if pub is None:\n                raise ValueError(\"pubDate\")\n            desc = dict(p.split(\"=\", 1) for p in require(item.findtext(\"description\")).split(\";\") if \"=\" in p)\n            a, b = require(desc.get(\"window\")).split(\"/\")\n            status = require(desc.get(\"status\")).strip()\n            if status not in (\"active\", \"retracted\"):\n                raise ValueError(\"status\")\n            corpus.outages.append(OutageNotice(guid=guid, published=int(pub.timestamp()),\n                                               window_start=parse_stamp(a, default_offset=None),\n                                               window_end=parse_stamp(b, default_offset=None),\n                                               status=status, origin=origin))\n        except (ValueError, TypeError):\n            reader.malformed(origin)\n\n\ndef read_incidents(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        s = line.strip()\n        if not s.startswith(\"|\") or s.startswith(\"|---\") or s.lower().startswith(\"| outage\"):\n            continue\n        origin = reader.next()\n        try:\n            cells = [c.strip() for c in s.strip(\"|\").split(\"|\")]\n            if len(cells) != 3:\n                raise ValueError(\"columns\")\n            corpus.incidents.append(IncidentScope(outage=require(cells[0]), dataset=normalize_key(require(cells[1])),\n                                                  origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n",
    "src/quillfen/parsers/org.py": "\"\"\"Organisation sources: ownership history, team handle registry, directory, pager contacts, hosts.\"\"\"\nfrom __future__ import annotations\n\nimport csv\nimport datetime as _dt\nimport io\nimport re\nfrom pathlib import Path\n\nfrom ..keys import normalize_handle, normalize_mail\nfrom ..records import Contact, Corpus, DirectoryChange, DirectoryPerson, HandleBinding, HostBinding, OwnershipCommit\nfrom ..timebase import parse_stamp\nfrom .common import Reader, read_text, require\n\n\ndef read_hosts(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    rows = list(csv.reader(io.StringIO(read_text(path))))\n    for row in rows[1:]:\n        if not row:\n            continue\n        origin = reader.next()\n        try:\n            if len(row) != 5:\n                raise ValueError(\"columns\")\n            host, pool, zone, frm, to = (c.strip() for c in row)\n            if not corpus.zones.knows(require(zone)):\n                raise ValueError(\"zone\")\n            corpus.hosts.append(HostBinding(\n                host=require(host), zone=zone,\n                valid_from=parse_stamp(frm, default_offset=None) if frm else None,\n                valid_to=parse_stamp(to, default_offset=None) if to else None,\n                origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\ndef read_ownership(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    blocks = re.split(r\"(?m)^(?=commit [0-9a-f]{40}$)\", read_text(path))\n    for block in blocks:\n        if not block.startswith(\"commit \"):\n            continue\n        origin = reader.next()\n        try:\n            date = re.search(r\"(?m)^Date:\\s+(.+)$\", block)\n            committed = int(_dt.datetime.strptime(require(date.group(1) if date else None).strip(),\n                                                  \"%a %b %d %H:%M:%S %Y %z\").timestamp())\n            changes = []\n            for line in block.splitlines():\n                if line.startswith(\"+jobs/\") or line.startswith(\"-jobs/\"):\n                    parts = line[1:].split()\n                    changes.append((line[0], parts[0], [normalize_handle(h) for h in parts[1:]]))\n            corpus.ownership.append(OwnershipCommit(committed=committed, changes=changes, origin=origin))\n        except (ValueError, AttributeError):\n            reader.malformed(origin)\n\n\n_BLOCK = re.compile(r'handle\\s+\"([^\"]+)\"\\s*\\{(.*?)\\}', re.S)\n_FIELD = re.compile(r'(\\w+)\\s*=\\s*\"([^\"]*)\"')\n\n\ndef read_handles(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for m in _BLOCK.finditer(read_text(path)):\n        origin = reader.next()\n        try:\n            fields = dict(_FIELD.findall(m.group(2)))\n            frm, to = fields.get(\"valid_from\", \"\"), fields.get(\"valid_to\", \"\")\n            corpus.handles.append(HandleBinding(\n                handle=normalize_handle(m.group(1)),\n                team=\"team:\" + require(fields.get(\"team\")).strip(),\n                valid_from=parse_stamp(frm, default_offset=None) if frm else None,\n                valid_to=parse_stamp(to, default_offset=None) if to else None,\n                origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\ndef _ldif_records(text: str):\n    lines = []\n    for raw in text.splitlines():\n        if raw.startswith(\" \") and lines:\n            lines[-1] += raw[1:]\n        else:\n            lines.append(raw)\n    record = []\n    for line in lines + [\"\"]:\n        if line.strip() == \"\":\n            if record:\n                yield record\n            record = []\n        elif not line.startswith(\"#\"):\n            record.append(line)\n\n\ndef ldif_attributes(record):\n    \"\"\"Attribute name -> list of values for one LDIF entry.\"\"\"\n    attrs = {}\n    for line in record:\n        if line == \"-\" or \":\" not in line:\n            continue\n        name, value = line.split(\":\", 1)\n        attrs.setdefault(name.strip().lower(), []).append(value.strip())\n    return attrs\n\n\ndef read_directory(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for record in _ldif_records(read_text(path)):\n        if len(record) == 1 and record[0].lower().startswith(\"version:\"):\n            continue\n        origin = reader.next()\n        try:\n            attrs = ldif_attributes(record)\n            uid = require((attrs.get(\"uid\") or [None])[0] or _uid_from_dn(attrs))\n            if \"changetype\" in attrs:\n                if attrs[\"changetype\"][0] != \"modify\":\n                    raise ValueError(\"changetype\")\n                op = \"add\" if \"add\" in attrs else (\"delete\" if \"delete\" in attrs else None)\n                for mail in attrs.get(\"mail\", []):\n                    corpus.directory_changes.append(DirectoryChange(uid=uid, op=require(op), mail=normalize_mail(mail), origin=origin))\n                continue\n            employee = require((attrs.get(\"employeenumber\") or [None])[0])\n            mails = [normalize_mail(m) for m in attrs.get(\"mail\", [])]\n            corpus.people.append(DirectoryPerson(employee=employee, uid=uid, mails=mails, origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\ndef _uid_from_dn(attrs):\n    dn = (attrs.get(\"dn\") or [\"\"])[0]\n    m = re.match(r\"uid=([^,]+)\", dn)\n    return m.group(1) if m else None\n\n\ndef read_contacts(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    text = read_text(path).replace(\"\\r\\n\", \"\\n\")\n    text = re.sub(r\"\\n[ \\t]\", \"\", text)\n    for m in re.finditer(r\"BEGIN:VCARD\\n(.*?)END:VCARD\", text, re.S):\n        origin = reader.next()\n        try:\n            mails, handles = [], []\n            for line in m.group(1).splitlines():\n                if \":\" not in line:\n                    continue\n                name, value = line.split(\":\", 1)\n                name = name.split(\";\")[0].upper()\n                if name == \"EMAIL\" and value.strip():\n                    mails.append(normalize_mail(value))\n                elif name == \"X-PAGER-HANDLE\" and value.strip():\n                    handles.append(value.strip().lower())\n            if not mails or not handles:\n                raise ValueError(\"contact needs an address and a handle\")\n            corpus.contacts.append(Contact(mails=mails, handles=handles, origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n",
    "src/quillfen/parsers/scheduler.py": "\"\"\"Scheduler exports: US (SQLite), EU (semicolon text), APAC (JSON lines), legacy cron hosts (syslog).\"\"\"\nfrom __future__ import annotations\n\nimport json\nimport re\nimport sqlite3\nfrom pathlib import Path\n\nfrom ..keys import normalize_key\nfrom ..records import Corpus, Transition\nfrom ..timebase import instant, parse_stamp\nfrom .common import MONTHS, Reader, host_instant, read_text, require\n\nSTATES = {\"queued\", \"running\", \"success\", \"failed\", \"up_for_retry\", \"removed\", \"cleared\"}\n\n\ndef _state(text) -> str:\n    s = require(text).strip()\n    if s not in STATES:\n        raise ValueError(\"state\")\n    return s\n\n\ndef read_us(path: Path, corpus: Corpus) -> None:\n    con = sqlite3.connect(\"file:%s?mode=ro\" % path.as_posix(), uri=True)\n    try:\n        rows = con.execute(\"SELECT rowid, run_id, job, nominal_utc, state, at_utc FROM task_transitions ORDER BY rowid\").fetchall()\n    finally:\n        con.close()\n    reader = Reader(corpus, path.name)\n    for rowid, run_id, job, nominal, state, at in rows:\n        origin = reader.next()\n        try:\n            corpus.transitions.append(Transition(run_id=require(run_id), key=normalize_key(require(job)),\n                                                 nominal=parse_stamp(require(nominal), default_offset=None),\n                                                 state=_state(state), at=parse_stamp(require(at), default_offset=0),\n                                                 origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_EU_STAMP = re.compile(r\"^(\\d{2})\\.(\\d{2})\\.(\\d{4}) (\\d{2}):(\\d{2}):(\\d{2})$\")\n\n\ndef eu_instant(corpus: Corpus, text: str) -> int:\n    \"\"\"The EU exporter writes Europe/Berlin wall time.\"\"\"\n    m = _EU_STAMP.match(require(text).strip())\n    if not m:\n        raise ValueError(\"eu stamp\")\n    d, mo, y, h, mi, s = (int(g) for g in m.groups())\n    return corpus.zones.wall_to_instant(\"Europe/Berlin\", instant(y, mo, d, h, mi, s))\n\n\ndef read_eu(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    lines = read_text(path).splitlines()\n    for line in lines[1:]:\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            parts = line.split(\";\")\n            if len(parts) != 5:\n                raise ValueError(\"columns\")\n            run_id, job, nominal, state, at = parts\n            corpus.transitions.append(Transition(run_id=require(run_id), key=normalize_key(require(job)),\n                                                 nominal=parse_stamp(require(nominal), default_offset=None),\n                                                 state=_state(state), at=eu_instant(corpus, at), origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\ndef read_apac(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            row = json.loads(line)\n            ts = row.get(\"ts_ms\")\n            nominal = row.get(\"nominal_ms\")\n            if not isinstance(ts, int) or not isinstance(nominal, int) or isinstance(ts, bool):\n                raise ValueError(\"epoch millis\")\n            corpus.transitions.append(Transition(run_id=require(row.get(\"run\")), key=normalize_key(require(row.get(\"job\"))),\n                                                 nominal=nominal // 1000, state=_state(row.get(\"state\")),\n                                                 at=ts // 1000, origin=origin))\n        except (ValueError, AttributeError):\n            reader.malformed(origin)\n\n\n_SYSLOG = re.compile(r\"^([A-Z][a-z]{2}) +(\\d{1,2}) (\\d{2}):(\\d{2}):(\\d{2}) (\\S+) qf-sched\\[\\d+\\]: (.*)$\")\n\n\ndef syslog_year(corpus: Corpus, month: int, day: int, hour: int, minute: int, second: int) -> int:\n    \"\"\"Syslog stamps carry no year: take the year that puts the stamp nearest the period start.\"\"\"\n    anchor = corpus.period_start\n    y0 = time_year(anchor)\n    best = None\n    for y in (y0 - 1, y0, y0 + 1):\n        try:\n            t = instant(y, month, day, hour, minute, second)\n        except ValueError:\n            continue\n        if best is None or abs(t - anchor) < best[0]:\n            best = (abs(t - anchor), y)\n    if best is None:\n        raise ValueError(\"date\")\n    return best[1]\n\n\ndef time_year(t: int) -> int:\n    import time\n    return time.gmtime(t).tm_year\n\n\ndef read_legacy(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            m = _SYSLOG.match(line)\n            if not m or m.group(1) not in MONTHS:\n                raise ValueError(\"syslog line\")\n            mo = MONTHS[m.group(1)]\n            d, h, mi, s = (int(m.group(k)) for k in range(2, 6))\n            y = syslog_year(corpus, mo, d, h, mi, s)\n            at = host_instant(corpus, m.group(6), instant(y, mo, d, h, mi, s))\n            kv = dict(p.split(\"=\", 1) for p in m.group(7).split() if \"=\" in p)\n            corpus.transitions.append(Transition(run_id=require(kv.get(\"run\")), key=normalize_key(require(kv.get(\"job\"))),\n                                                 nominal=parse_stamp(require(kv.get(\"nominal\")), default_offset=None),\n                                                 state=_state(kv.get(\"state\")), at=at, origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n",
    "src/quillfen/parsers/specs.py": "\"\"\"Job definition sources: platform TOML, analytics JSON, finance XML, legacy INI with its crontab.\"\"\"\nfrom __future__ import annotations\n\nimport configparser\nimport datetime as _dt\nimport json\nimport re\nimport tomllib\nimport xml.etree.ElementTree as ET\nfrom pathlib import Path\n\nfrom ..core.cron import Schedule\nfrom ..keys import normalize_key\nfrom ..records import Corpus, SpecRevision\nfrom ..timebase import instant, parse_offset, parse_stamp\nfrom .common import Reader, read_text, require, to_int\n\n\ndef _aware(value) -> int:\n    if not isinstance(value, _dt.datetime) or value.tzinfo is None:\n        raise ValueError(\"effective must be an offset date-time\")\n    return int(value.timestamp())\n\n\ndef _zone(corpus: Corpus, text) -> str:\n    text = require(text).strip()\n    if not corpus.zones.knows(text):\n        raise ValueError(\"unknown zone %s\" % text)\n    return text\n\n\ndef _schedule(text) -> str:\n    text = \" \".join(require(text).split())\n    Schedule(text)\n    return text\n\n\ndef read_period(path: Path, corpus: Corpus) -> None:\n    data = tomllib.loads(read_text(path))\n    s = data[\"settlement\"]\n    corpus.period_start = _aware(s[\"period_start\"])\n    corpus.period_end = _aware(s[\"period_end\"])\n\n\ndef read_platform(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    data = tomllib.loads(read_text(path))\n    for row in data.get(\"revision\", []):\n        origin = reader.next()\n        try:\n            corpus.specs.append(SpecRevision(\n                key=normalize_key(require(row.get(\"job\"))),\n                effective=_aware(row.get(\"effective\")),\n                schedule=_schedule(row.get(\"schedule\")),\n                zone=_zone(corpus, row.get(\"zone\")),\n                sla_minutes=to_int(row.get(\"sla_minutes\"), lo=0),\n                tier=to_int(row.get(\"tier\"), 1, 3),\n                enabled=_bool(row.get(\"enabled\")),\n                origin=origin))\n        except (ValueError, TypeError, KeyError):\n            reader.malformed(origin)\n\n\ndef _bool(v) -> bool:\n    if isinstance(v, bool):\n        return v\n    raise ValueError(\"enabled must be a boolean\")\n\n\ndef read_analytics(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    data = json.loads(read_text(path))\n    for row in data.get(\"revisions\", []):\n        origin = reader.next()\n        try:\n            seconds = to_int(row.get(\"sla_seconds\"), lo=0)\n            if seconds % 60:\n                raise ValueError(\"sla must be whole minutes\")\n            tier = re.fullmatch(r\"T([123])\", str(row.get(\"tier\")))\n            if not tier:\n                raise ValueError(\"tier\")\n            state = row.get(\"state\")\n            if state not in (\"active\", \"disabled\"):\n                raise ValueError(\"state\")\n            corpus.specs.append(SpecRevision(\n                key=normalize_key(require(row.get(\"job\"))),\n                effective=to_int(row.get(\"effective_ms\"), lo=0) // 1000,\n                schedule=_schedule(row.get(\"cron\")),\n                zone=_zone(corpus, row.get(\"tz\")),\n                sla_minutes=seconds // 60,\n                tier=int(tier.group(1)),\n                enabled=state == \"active\",\n                origin=origin))\n        except (ValueError, TypeError):\n            reader.malformed(origin)\n\n\n_DURATION = re.compile(r\"^PT(?:(\\d+)H)?(?:(\\d+)M)?$\")\n\n\ndef read_finance(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    root = ET.fromstring(path.read_bytes())\n    for el in root.iter(\"revision\"):\n        origin = reader.next()\n        try:\n            m = _DURATION.match(require(el.findtext(\"sla\")).strip())\n            if not m or not (m.group(1) or m.group(2)):\n                raise ValueError(\"sla must be an ISO 8601 duration\")\n            minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)\n            enabled = (el.findtext(\"enabled\") or \"\").strip()\n            if enabled not in (\"yes\", \"no\"):\n                raise ValueError(\"enabled\")\n            corpus.specs.append(SpecRevision(\n                key=normalize_key(require(el.get(\"job\"))),\n                effective=parse_stamp(require(el.get(\"effective\")), default_offset=None),\n                schedule=_schedule(el.findtext(\"schedule\")),\n                zone=_zone(corpus, el.findtext(\"zone\")),\n                sla_minutes=minutes,\n                tier=to_int(el.findtext(\"tier\"), 1, 3),\n                enabled=enabled == \"yes\",\n                origin=origin))\n        except (ValueError, TypeError):\n            reader.malformed(origin)\n\n\n_SECTION = re.compile(r\"^(.+?)\\s+@\\s+(\\d{4})-(\\d{2})-(\\d{2}) (\\d{2}):(\\d{2}):(\\d{2}) ([+-]\\d{4})$\")\n_SLA = re.compile(r\"^(?:(\\d+)h)?(?:(\\d+)m)?$\")\n_REV = re.compile(r\"^#\\s*rev\\s+(\\S+)\\s+(\\S+)\\s*$\")\n\n\ndef read_legacy(ini_path: Path, cron_path: Path, corpus: Corpus) -> None:\n    \"\"\"Legacy definitions: the crontab governs the schedule, the INI governs every other field.\"\"\"\n    schedules = {}\n    reader = Reader(corpus, cron_path.name)\n    lines = read_text(cron_path).splitlines()\n    i = 0\n    while i < len(lines):\n        m = _REV.match(lines[i].strip())\n        if not m:\n            i += 1\n            continue\n        origin = reader.next()\n        body = lines[i + 1].strip() if i + 1 < len(lines) else \"\"\n        i += 2\n        try:\n            parts = body.split()\n            if len(parts) < 7:\n                raise ValueError(\"crontab entry\")\n            expr = \" \".join(parts[:5])\n            Schedule(expr)\n            key = normalize_key(m.group(1))\n            if normalize_key(parts[-1]) != key:\n                raise ValueError(\"entry names a different job\")\n            schedules[(key, parse_stamp(m.group(2), default_offset=None))] = expr\n        except ValueError:\n            reader.malformed(origin)\n\n    reader = Reader(corpus, ini_path.name)\n    cp = configparser.ConfigParser(interpolation=None, strict=False, comment_prefixes=(\";\", \"#\"))\n    cp.read_string(read_text(ini_path))\n    for section in cp.sections():\n        origin = reader.next()\n        try:\n            m = _SECTION.match(section.strip())\n            if not m:\n                raise ValueError(\"section\")\n            y, mo, d, h, mi, s = (int(m.group(k)) for k in range(2, 8))\n            effective = instant(y, mo, d, h, mi, s) - parse_offset(m.group(8)) * 60\n            key = normalize_key(m.group(1))\n            body = cp[section]\n            sla = _SLA.match(require(body.get(\"sla\")).strip())\n            if not sla or not (sla.group(1) or sla.group(2)):\n                raise ValueError(\"sla\")\n            disabled = require(body.get(\"disabled\")).strip()\n            if disabled not in (\"yes\", \"no\"):\n                raise ValueError(\"disabled\")\n            corpus.specs.append(SpecRevision(\n                key=key,\n                effective=effective,\n                schedule=schedules.get((key, effective)),\n                zone=_zone(corpus, body.get(\"zone\")),\n                sla_minutes=int(sla.group(1) or 0) * 60 + int(sla.group(2) or 0),\n                tier=to_int(body.get(\"tier\"), 1, 3),\n                enabled=disabled == \"no\",\n                origin=origin))\n        except (ValueError, TypeError):\n            reader.malformed(origin)\n",
    "src/quillfen/parsers/workers.py": "\"\"\"Worker pool logs and clock calibration sources. Worker stamps are host clock readings.\"\"\"\nfrom __future__ import annotations\n\nimport re\nimport xml.etree.ElementTree as ET\nfrom decimal import Decimal, InvalidOperation\nfrom pathlib import Path\nfrom urllib.parse import parse_qs, unquote, urlsplit\n\nfrom ..keys import normalize_key\nfrom ..records import ClockSample, Corpus, WorkerEvent\nfrom ..timebase import instant, parse_offset, parse_stamp\nfrom .common import MONTHS, Reader, read_text, require\n\nEVENTS = {\"start\", \"commit\", \"fail\"}\n\n\ndef _event(text) -> str:\n    e = require(text).strip().lower()\n    if e not in EVENTS:\n        raise ValueError(\"event\")\n    return e\n\n\ndef _worker(corpus, origin, host, run, job, nominal, event, local_ms):\n    corpus.worker_events.append(WorkerEvent(host=require(host), run_id=require(run), key=normalize_key(require(job)),\n                                            nominal=parse_stamp(require(nominal), default_offset=None),\n                                            event=_event(event), local_ms=local_ms, origin=origin))\n\n\ndef logfmt_pairs(line: str) -> dict:\n    \"\"\"key=value pairs of one worker log line.\"\"\"\n    pairs = {}\n    i, n = 0, len(line)\n    while i < n:\n        while i < n and line[i] == \" \":\n            i += 1\n        start = i\n        while i < n and line[i] not in \"= \":\n            i += 1\n        key = line[start:i]\n        if i >= n or line[i] != \"=\":\n            continue\n        i += 1\n        if i < n and line[i] == '\"':\n            i += 1\n            buf = []\n            while i < n and line[i] != '\"':\n                if line[i] == \"\\\\\" and i + 1 < n:\n                    buf.append(line[i + 1])\n                    i += 2\n                    continue\n                buf.append(line[i])\n                i += 1\n            i += 1\n            value = \"\".join(buf)\n        else:\n            start = i\n            while i < n and line[i] != \" \":\n                i += 1\n            value = line[start:i]\n        if key:\n            pairs[key] = value\n    return pairs\n\n\ndef read_logfmt(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            kv = logfmt_pairs(line)\n            local = parse_stamp(require(kv.get(\"ts\")), default_offset=None)\n            _worker(corpus, origin, kv.get(\"host\"), kv.get(\"run\"), kv.get(\"job\"), kv.get(\"nominal\"), kv.get(\"event\"), local * 1000)\n        except ValueError:\n            reader.malformed(origin)\n\n\n_CEF_KEY = re.compile(r\"(?<!\\\\)\\s(\\w+)=\")\nCEF_EVENTS = {\"4100\": \"start\", \"4101\": \"commit\", \"4102\": \"fail\"}\n\n\ndef read_cef(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.startswith(\"CEF:\"):\n            continue\n        origin = reader.next()\n        try:\n            head = line.split(\"|\", 7)\n            if len(head) != 8:\n                raise ValueError(\"header\")\n            ext = \" \" + head[7]\n            marks = [(m.start(), m.group(1), m.end()) for m in _CEF_KEY.finditer(ext)]\n            fields = {}\n            for idx, (pos, key, vstart) in enumerate(marks):\n                vend = marks[idx + 1][0] if idx + 1 < len(marks) else len(ext)\n                fields[key] = ext[vstart:vend].replace(\"\\\\=\", \"=\").replace(\"\\\\\\\\\", \"\\\\\")\n            labels = {}\n            for k, v in list(fields.items()):\n                if k.endswith(\"Label\"):\n                    labels[v] = fields.get(k[:-5])\n            rt = require(fields.get(\"rt\"))\n            if not re.fullmatch(r\"\\d+\", rt):\n                raise ValueError(\"rt\")\n            _worker(corpus, origin, fields.get(\"dhost\"), labels.get(\"run\"), labels.get(\"job\"), labels.get(\"nominal\"),\n                    CEF_EVENTS.get(head[4]), int(rt))\n        except ValueError:\n            reader.malformed(origin)\n\n\ndef read_w3c(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    columns = []\n    for line in read_text(path).splitlines():\n        if line.startswith(\"#\"):\n            if line.startswith(\"#Fields:\"):\n                columns = line[len(\"#Fields:\"):].split()\n            continue\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            values = line.split(\" \")\n            if len(values) != len(columns):\n                raise ValueError(\"columns\")\n            row = dict(zip(columns, values))\n            local = parse_stamp(\"%s %s\" % (row[\"date\"], row[\"time\"]), default_offset=0)\n            _worker(corpus, origin, row.get(\"s-computername\"), row.get(\"cs-run\"), row.get(\"cs-job\"), row.get(\"cs-nominal\"),\n                    row.get(\"x-event\"), local * 1000)\n        except (ValueError, KeyError):\n            reader.malformed(origin)\n\n\nEVTX_EVENTS = {\"4100\": \"start\", \"4101\": \"commit\", \"4102\": \"fail\"}\n_SYSTIME = re.compile(r\"^(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2})(?:\\.(\\d{1,7}))?Z$\")\n\n\ndef read_evtx(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    root = ET.fromstring(path.read_bytes())\n    for ev in root.iter(\"Event\"):\n        origin = reader.next()\n        try:\n            system = ev.find(\"System\")\n            m = _SYSTIME.match(require(system.find(\"TimeCreated\").get(\"SystemTime\")))\n            if not m:\n                raise ValueError(\"SystemTime\")\n            frac = (m.group(2) or \"\").ljust(3, \"0\")[:3]\n            local_ms = parse_stamp(m.group(1) + \"Z\", default_offset=None) * 1000 + int(frac)\n            data = {d.get(\"Name\"): (d.text or \"\") for d in ev.iter(\"Data\")}\n            _worker(corpus, origin, system.findtext(\"Computer\"), data.get(\"run\"), data.get(\"job\"), data.get(\"nominal\"),\n                    EVTX_EVENTS.get((system.findtext(\"EventID\") or \"\").strip()), local_ms)\n        except (ValueError, AttributeError):\n            reader.malformed(origin)\n\n\n_ACCESS = re.compile(r'^\\S+ \\S+ (\\S+) \\[(\\d{2})/([A-Z][a-z]{2})/(\\d{4}):(\\d{2}):(\\d{2}):(\\d{2}) ([+-]\\d{4})\\] \"POST (\\S+) HTTP/1\\.[01]\"')\n\n\ndef read_access(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.strip():\n            continue\n        origin = reader.next()\n        try:\n            m = _ACCESS.match(line)\n            if not m or m.group(3) not in MONTHS:\n                raise ValueError(\"access line\")\n            wall = instant(int(m.group(4)), MONTHS[m.group(3)], int(m.group(2)), int(m.group(5)), int(m.group(6)), int(m.group(7)))\n            local = wall - parse_offset(m.group(8)) * 60\n            url = urlsplit(m.group(9))\n            parts = url.path.strip(\"/\").split(\"/\")\n            if len(parts) != 3 or parts[0] != \"runs\":\n                raise ValueError(\"path\")\n            q = parse_qs(url.query)\n            _worker(corpus, origin, m.group(1), unquote(parts[1]), (q.get(\"job\") or [None])[0], (q.get(\"nominal\") or [None])[0],\n                    parts[2], local * 1000)\n        except ValueError:\n            reader.malformed(origin)\n\n\n_PB_FIELD = re.compile(r'^\\s*(\\w+):\\s*(?:\"((?:[^\"\\\\]|\\\\.)*)\"|(\\S+))\\s*$')\n_PB_TIME = re.compile(r\"^\\s*local_time\\s*\\{\\s*seconds:\\s*(-?\\d+)(?:\\s+nanos:\\s*(\\d+))?\\s*\\}\\s*$\")\n\n\ndef read_pbtxt(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    block = None\n    for line in read_text(path).splitlines():\n        s = line.strip()\n        if s == \"event {\":\n            block = {}\n            continue\n        if block is None:\n            continue\n        if s == \"}\":\n            origin = reader.next()\n            try:\n                seconds = int(require(block.get(\"seconds\")))\n                if seconds < 0:\n                    raise ValueError(\"seconds\")\n                local_ms = seconds * 1000 + int(block.get(\"nanos\", \"0\")) // 1000000\n                _worker(corpus, origin, block.get(\"host\"), block.get(\"run_id\"), block.get(\"job\"), block.get(\"nominal\"),\n                        block.get(\"kind\"), local_ms)\n            except ValueError:\n                reader.malformed(origin)\n            block = None\n            continue\n        t = _PB_TIME.match(line)\n        if t:\n            block[\"seconds\"] = t.group(1)\n            block[\"nanos\"] = t.group(2) or \"0\"\n            continue\n        f = _PB_FIELD.match(line)\n        if f:\n            block[f.group(1)] = f.group(2).replace('\\\\\"', '\"') if f.group(2) is not None else f.group(3)\n\n\n_PROM = re.compile(r'^node_timex_offset_seconds\\{([^}]*)\\}\\s+(\\S+)\\s+(\\d+)\\s*$')\n\n\ndef read_prometheus(path: Path, corpus: Corpus) -> None:\n    reader = Reader(corpus, path.name)\n    for line in read_text(path).splitlines():\n        if not line.startswith(\"node_timex_offset_seconds\"):\n            continue\n        origin = reader.next()\n        try:\n            m = _PROM.match(line)\n            if not m:\n                raise ValueError(\"sample\")\n            labels = dict(re.findall(r'(\\w+)=\"([^\"]*)\"', m.group(1)))\n            try:\n                seconds = Decimal(m.group(2))\n            except InvalidOperation:\n                raise ValueError(\"value\")\n            if not seconds.is_finite():\n                raise ValueError(\"value\")\n            ms = seconds * 1000\n            if ms != ms.to_integral_value():\n                raise ValueError(\"sub-millisecond offset\")\n            corpus.clock_samples.append(ClockSample(host=require(labels.get(\"host\")), at_ms=int(m.group(3)),\n                                                    offset_ms=int(ms), origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n\n\n_MS = re.compile(r\"^(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2})\\.(\\d{3})Z$\")\n\n\ndef _ms(text) -> int:\n    m = _MS.match(require(text).strip())\n    if not m:\n        raise ValueError(\"millisecond stamp\")\n    return parse_stamp(m.group(1) + \"Z\", default_offset=None) * 1000 + int(m.group(2))\n\n\ndef read_heartbeats(path: Path, corpus: Corpus) -> None:\n    \"\"\"Heartbeat offset = host clock at sending minus scheduler clock at receipt (latency ignored).\"\"\"\n    reader = Reader(corpus, path.name)\n    blocks = re.split(r\"\\n\\s*\\n\", read_text(path))\n    for block in blocks:\n        if not block.strip():\n            continue\n        origin = reader.next()\n        try:\n            fields = dict((k.strip(), v.strip()) for k, v in (ln.split(\":\", 1) for ln in block.strip().splitlines() if \":\" in ln))\n            sent, received = _ms(fields.get(\"sent\")), _ms(fields.get(\"received\"))\n            corpus.clock_samples.append(ClockSample(host=require(fields.get(\"host\")), at_ms=received,\n                                                    offset_ms=sent - received, origin=origin))\n        except ValueError:\n            reader.malformed(origin)\n",
    "src/quillfen/pipeline.py": "\"\"\"Settlement run: corpus in, settled tables out.\"\"\"\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, field\n\nfrom .core import audit, calendars, deps, evidence, status\nfrom .core.clock import ClockBook\nfrom .core.commitments import SlaBook, SpecTimeline, expand\nfrom .core.identity import Identity\nfrom .core.landing import Producers, partition_streams\nfrom .core.ownership import Ownership\nfrom .core.people import People\nfrom .parsers import read_corpus\nfrom .report import blame as blame_mod\nfrom .report.chargeback import split\nfrom .report.ledger import sort_key\nfrom .report.penalty import RateCard, bucket, lateness_minutes\nfrom .timebase import DAY\n\n\n@dataclass\nclass Settlement:\n    corpus: object\n    identity: object\n    intervals: list\n    evidence: dict\n    statuses: dict\n    upstreams: dict\n    ledger: list\n    blame: list\n    accountability: list\n    chargeback: dict\n    unowned: dict\n    audit: list\n    people: object\n    teams: list = field(default_factory=list)\n    mark_decisions: list = field(default_factory=list)\n    streams: dict = field(default_factory=dict)\n    commits: list = field(default_factory=list)\n    clock: object = None\n    waits: list = field(default_factory=list)\n    freezes: list = field(default_factory=list)\n    shifts: list = field(default_factory=list)\n    tier_charge: dict = field(default_factory=dict)\n\n\ndef settle(input_dir) -> Settlement:\n    corpus = read_corpus(input_dir)\n    zones = corpus.zones\n    p0, p1 = corpus.period_start, corpus.period_end\n\n    identity = Identity(corpus.renames, [s.key for s in corpus.specs], p1)\n    timeline = SpecTimeline(identity, corpus.specs)\n    sla = SlaBook(identity, corpus.sla_overrides, corpus)\n    intervals = expand(identity, timeline, sla, zones, p0, p1)\n\n    producers = Producers(corpus.producers, identity, corpus)\n    streams = partition_streams(corpus.partition_events, producers, corpus)\n    backfill_runs = {b.run_id for b in _known(corpus.backfills, identity, corpus)}\n    clock = ClockBook(corpus.clock_samples)\n    workers = evidence.index_by_interval(corpus.worker_events, identity, corpus)\n    transitions = evidence.index_by_interval(corpus.transitions, identity, corpus)\n    marks = evidence.index_by_interval(corpus.operator_actions, identity, corpus)\n    approvals = evidence.index_by_interval(corpus.approvals, identity, corpus)\n    people = People(corpus.people, corpus.directory_changes, corpus.contacts)\n    mark_decisions = []\n    for key, actions in marks.items():\n        for m in actions:\n            if m.action != \"mark_success\":\n                continue\n            accepted = evidence.mark_accepted(m, approvals.get(key, []), people)\n            mark_decisions.append((key, m, accepted))\n            if not accepted:\n                corpus.reject(m.origin, \"UNAPPROVED_MARK\")\n    pauses = status.pause_windows(corpus.pauses, identity, corpus)\n    graph = deps.DependencyGraph(corpus.dependencies, identity, corpus)\n\n    ownership = Ownership(corpus.ownership, corpus.handles, identity)\n    horizon = p1 + 60 * DAY\n    freezes = calendars.freeze_windows(corpus.freezes, zones, horizon)\n    holidays = {}\n    for h in corpus.holidays:\n        holidays.setdefault(h.team, set()).add(h.date)\n    for iv in intervals.values():\n        iv.suspension = status.suspension_of(iv, freezes, pauses, holidays, ownership.teams, zones)\n\n    ordered = sorted(intervals.values(), key=sort_key)\n    ev = {}\n    for iv in ordered:\n        ev[iv.key] = evidence.resolve(iv, producers, streams, workers, backfill_runs, clock, transitions, marks,\n                                      approvals, people)\n\n    nominals = {}\n    for iv in intervals.values():\n        nominals.setdefault(iv.job.index, []).append(iv.nominal)\n    for lst in nominals.values():\n        lst.sort()\n    upstreams = {iv.key: deps.upstream_intervals(graph, iv, nominals) for iv in ordered}\n    waits = []\n    for iv in ordered:\n        seen = set()\n        for e in graph.edges_into(iv.job, iv.nominal):\n            up = identity.resolve_key(e.upstream, iv.nominal)\n            waited = deps.governing_upstream(nominals.get(up.index, []), iv.nominal, e.lag)\n            if (up.index, e.lag, waited) not in seen:\n                seen.add((up.index, e.lag, waited))\n                waits.append((iv, up, e.lag, waited))\n\n    outages = status.active_outages(corpus.outages, corpus.incidents)\n    statuses = {}\n    for iv in sorted(intervals.values(), key=lambda i: i.nominal):\n        ups = [statuses[(u, n)] for u, n, _ in upstreams[iv.key] if (u, n) in statuses]\n        statuses[iv.key] = status.classify(iv, ev[iv.key], outages, ups, p1)\n\n    rates = RateCard(corpus.rates)\n    ledger = []\n    for iv in ordered:\n        st = statuses[iv.key]\n        row = {\"interval\": iv, \"status\": st, \"reason\": ev[iv.key].unresolvable if st == \"UNRESOLVABLE\" else \"\",\n               \"landed_at\": ev[iv.key].landed_at, \"minutes\": None, \"bucket\": None, \"penalty\": None}\n        if st in (\"LATE\", \"MISSED\"):\n            end = ev[iv.key].landed_at if st == \"LATE\" else p1\n            minutes = lateness_minutes(end - iv.deadline)\n            row[\"minutes\"] = minutes\n            row[\"bucket\"] = bucket(minutes)\n            row[\"penalty\"] = rates.price(iv.tier, row[\"bucket\"], iv.deadline, minutes)\n        ledger.append(row)\n\n    parents = {}\n    for iv in ordered:\n        if statuses[iv.key] != \"EXCUSED_UPSTREAM\":\n            continue\n        cands = []\n        for u, n, _ in upstreams[iv.key]:\n            if (u, n) in statuses and statuses[(u, n)] not in (\"MET\", \"SUSPENDED\"):\n                cands.append(((u, n), ev[(u, n)].landed_at, identity.jobs[u].canonical))\n        parents[iv.key] = blame_mod.blame_parent(cands)\n    blame_rows = []\n    for iv in ordered:\n        if iv.key in parents:\n            root, depth = blame_mod.root_of(iv.key, parents)\n            blame_rows.append((iv, parents[iv.key], root, depth, ownership.teams(identity.jobs[root[0]], intervals[root].deadline)))\n\n    teams = sorted({h.team for h in corpus.handles})\n    charge = {t: {\"penalty\": 0, \"late\": 0, \"missed\": 0, \"blamed\": 0} for t in teams}\n    unowned = {\"penalty\": 0, \"late\": 0, \"missed\": 0}\n    tier_charge = {\"teams\": {t: {} for t in teams}, \"unowned\": {}}\n    shifts = calendars.rota_shifts(corpus.rota, zones, horizon)\n    accountability = []\n    for row in ledger:\n        if row[\"status\"] not in (\"LATE\", \"MISSED\"):\n            continue\n        iv = row[\"interval\"]\n        owning = ownership.teams(iv.job, iv.deadline)\n        field_name = \"late\" if row[\"status\"] == \"LATE\" else \"missed\"\n        if not owning:\n            unowned[\"penalty\"] += row[\"penalty\"]\n            unowned[field_name] += 1\n            cell = tier_charge[\"unowned\"].setdefault(iv.tier, {\"penalty\": 0, \"late\": 0, \"missed\": 0})\n            cell[\"penalty\"] += row[\"penalty\"]\n            cell[field_name] += 1\n            continue\n        for team, amount in split(row[\"penalty\"], owning).items():\n            entry = charge.setdefault(team, {\"penalty\": 0, \"late\": 0, \"missed\": 0, \"blamed\": 0})\n            entry[\"penalty\"] += amount\n            entry[field_name] += 1\n            cell = tier_charge[\"teams\"].setdefault(team, {}).setdefault(iv.tier, {\"penalty\": 0, \"late\": 0, \"missed\": 0})\n            cell[\"penalty\"] += amount\n            cell[field_name] += 1\n        for team in owning:\n            accountability.append((iv, team, on_call(shifts, people, team, iv.deadline)))\n    for _, _, _, _, root_teams in blame_rows:\n        for team in root_teams:\n            charge.setdefault(team, {\"penalty\": 0, \"late\": 0, \"missed\": 0, \"blamed\": 0})[\"blamed\"] += 1\n\n    return Settlement(corpus=corpus, identity=identity, intervals=ordered, evidence=ev, statuses=statuses,\n                      upstreams=upstreams, ledger=ledger, blame=blame_rows, accountability=accountability,\n                      chargeback=charge, unowned=unowned,\n                      audit=audit.illegal_transitions(transitions), people=people, teams=teams,\n                      mark_decisions=mark_decisions, streams=streams,\n                      commits=[(key, w) for key, events in workers.items() for w in events\n                               if w.event == \"commit\" and w.run_id not in backfill_runs],\n                      clock=clock, waits=waits, freezes=freezes, shifts=shifts, tier_charge=tier_charge)\n\n\ndef _known(records, identity, corpus):\n    out = []\n    for r in records:\n        if identity.known(r.key):\n            out.append(r)\n        else:\n            corpus.reject(r.origin, \"UNKNOWN_JOB\")\n    return out\n\n\ndef on_call(shifts: list, people, team: str, at: int) -> str:\n    \"\"\"The rota occurrence covering the instant; overlapping occurrences go to the latest start, then the\n    smaller person id. Attendees the directory cannot place are ignored.\"\"\"\n    best = None\n    for tm, a, b, attendee in shifts:\n        if tm != team or not (a <= at < b):\n            continue\n        pid = people.by_mail(attendee) if attendee else None\n        if pid is None:\n            continue\n        cand = (-a, pid)\n        if best is None or cand < best:\n            best = cand\n    return best[1] if best else \"UNASSIGNED\"\n",
    "src/quillfen/records.py": "\"\"\"Normalised records produced by the parsers and consumed by the settlement core.\"\"\"\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, field\nfrom typing import Optional\n\n\n@dataclass\nclass Origin:\n    source: str\n    ordinal: int\n\n\n@dataclass\nclass SpecRevision:\n    key: str\n    effective: int\n    schedule: Optional[str]\n    zone: str\n    sla_minutes: int\n    tier: int\n    enabled: bool\n    origin: Origin\n\n\n@dataclass\nclass Rename:\n    old_key: str\n    new_key: str\n    effective: int\n    origin: Origin\n\n\n@dataclass\nclass Dependency:\n    upstream: str\n    downstream: str\n    lag: int\n    valid_from: Optional[int]\n    valid_to: Optional[int]\n    origin: Origin\n\n\n@dataclass\nclass Producer:\n    dataset: str\n    key: str\n    valid_from: int\n    valid_to: Optional[int]\n    origin: Origin\n\n\n@dataclass\nclass SlaOverride:\n    key: str\n    effective: int\n    minutes: Optional[int]\n    origin: Origin\n\n\n@dataclass\nclass RateRow:\n    tier: int\n    bucket: str\n    effective: int\n    base: str\n    per_minute: str\n    origin: Origin\n\n\n@dataclass\nclass OwnershipCommit:\n    committed: int\n    changes: list\n    origin: Origin\n\n\n@dataclass\nclass HandleBinding:\n    handle: str\n    team: str\n    valid_from: Optional[int]\n    valid_to: Optional[int]\n    origin: Origin\n\n\n@dataclass\nclass DirectoryPerson:\n    employee: str\n    uid: str\n    mails: list\n    origin: Origin\n\n\n@dataclass\nclass DirectoryChange:\n    uid: str\n    op: str\n    mail: str\n    origin: Origin\n\n\n@dataclass\nclass Contact:\n    mails: list\n    handles: list\n    origin: Origin\n\n\n@dataclass\nclass CalendarEvent:\n    uid: str\n    zone: str\n    start_wall: Optional[int]\n    end_wall: Optional[int]\n    rrule: dict\n    exdates: list\n    categories: list\n    recurrence_id: Optional[int]\n    cancelled: bool\n    attendee: Optional[str]\n    team: Optional[str]\n    origin: Origin\n\n\n@dataclass\nclass Holiday:\n    team: str\n    date: tuple\n    origin: Origin\n\n\n@dataclass\nclass PauseEvent:\n    key: str\n    at: int\n    action: str\n    origin: Origin\n\n\n@dataclass\nclass Transition:\n    run_id: str\n    key: str\n    nominal: int\n    state: str\n    at: int\n    origin: Origin\n\n\n@dataclass\nclass WorkerEvent:\n    host: str\n    run_id: str\n    key: str\n    nominal: int\n    event: str\n    local_ms: int\n    origin: Origin\n\n\n@dataclass\nclass ClockSample:\n    host: str\n    at_ms: int\n    offset_ms: int\n    origin: Origin\n\n\n@dataclass\nclass PartitionEvent:\n    dataset: str\n    nominal: int\n    at: int\n    kind: str\n    origin: Origin\n\n\n@dataclass\nclass OperatorAction:\n    at: int\n    actor: str\n    action: str\n    key: str\n    nominal: int\n    origin: Origin\n\n\n@dataclass\nclass Approval:\n    sender: str\n    at: int\n    key: str\n    nominal: int\n    origin: Origin\n\n\n@dataclass\nclass OutageNotice:\n    guid: str\n    published: int\n    window_start: int\n    window_end: int\n    status: str\n    origin: Origin\n\n\n@dataclass\nclass IncidentScope:\n    outage: str\n    dataset: str\n    origin: Origin\n\n\n@dataclass\nclass Backfill:\n    run_id: str\n    key: str\n    nominal: int\n    origin: Origin\n\n\n@dataclass\nclass HostBinding:\n    host: str\n    zone: str\n    valid_from: Optional[int]\n    valid_to: Optional[int]\n    origin: Origin\n\n\n@dataclass\nclass Corpus:\n    period_start: int = 0\n    period_end: int = 0\n    zones: object = None\n    hosts: list = field(default_factory=list)\n    specs: list = field(default_factory=list)\n    renames: list = field(default_factory=list)\n    dependencies: list = field(default_factory=list)\n    producers: list = field(default_factory=list)\n    sla_overrides: list = field(default_factory=list)\n    rates: list = field(default_factory=list)\n    ownership: list = field(default_factory=list)\n    handles: list = field(default_factory=list)\n    people: list = field(default_factory=list)\n    directory_changes: list = field(default_factory=list)\n    contacts: list = field(default_factory=list)\n    freezes: list = field(default_factory=list)\n    holidays: list = field(default_factory=list)\n    rota: list = field(default_factory=list)\n    pauses: list = field(default_factory=list)\n    transitions: list = field(default_factory=list)\n    worker_events: list = field(default_factory=list)\n    clock_samples: list = field(default_factory=list)\n    partition_events: list = field(default_factory=list)\n    operator_actions: list = field(default_factory=list)\n    approvals: list = field(default_factory=list)\n    outages: list = field(default_factory=list)\n    incidents: list = field(default_factory=list)\n    backfills: list = field(default_factory=list)\n    rejects: list = field(default_factory=list)\n\n    def reject(self, origin: Origin, code: str) -> None:\n        self.rejects.append((origin.source, origin.ordinal, code))\n",
    "src/quillfen/report/__init__.py": "",
    "src/quillfen/report/blame.py": "\"\"\"Blame for intervals excused by their upstream.\"\"\"\nfrom __future__ import annotations\n\n\ndef blame_parent(candidates: list):\n    \"\"\"candidates: (upstream key, landed_at or None, canonical job). The latest-landing upstream is to blame,\n    an upstream that never landed counts as latest; ties go to the smaller canonical job id.\"\"\"\n    ranked = sorted(candidates, key=lambda c: (0 if c[1] is None else 1, -(c[1] or 0), c[2]))\n    return ranked[0][0]\n\n\ndef root_of(key, parents: dict):\n    \"\"\"Follow blame parents to the first interval that was not itself excused by an upstream.\"\"\"\n    depth = 1\n    node = parents[key]\n    while node in parents:\n        node = parents[node]\n        depth += 1\n    return node, depth\n",
    "src/quillfen/report/chargeback.py": "\"\"\"Penalty split across owning teams.\"\"\"\nfrom __future__ import annotations\n\n\ndef split(amount: int, teams: list) -> dict:\n    \"\"\"Equal shares in minor units; each leftover unit goes to the next team in ascending team id order.\"\"\"\n    ordered = sorted(teams)\n    share, leftover = divmod(amount, len(ordered))\n    return {team: share + (1 if i < leftover else 0) for i, team in enumerate(ordered)}\n",
    "src/quillfen/report/ledger.py": "\"\"\"Row ordering shared by the per-interval outputs.\"\"\"\nfrom __future__ import annotations\n\n\ndef sort_key(interval):\n    return (interval.deadline, interval.job.canonical, interval.nominal)\n",
    "src/quillfen/report/money.py": "\"\"\"Monetary amounts in integer minor units.\"\"\"\nfrom __future__ import annotations\n\n\ndef to_minor(amount: str) -> int:\n    \"\"\"Rate card amount -> integer minor units.\"\"\"\n    whole, _, frac = amount.strip().partition(\".\")\n    return int(whole or \"0\") * 100 + int((frac + \"00\")[:2])\n",
    "src/quillfen/report/penalty.py": "\"\"\"Lateness, buckets and penalties.\"\"\"\nfrom __future__ import annotations\n\nfrom .money import to_minor\n\n\ndef lateness_minutes(seconds_late: int) -> int:\n    \"\"\"Whole minutes, any started minute counts.\"\"\"\n    return -(-seconds_late // 60)\n\n\ndef bucket(minutes: int) -> str:\n    if minutes < 30:\n        return \"B0\"\n    if minutes < 120:\n        return \"B30\"\n    return \"B120\"\n\n\nclass RateCard:\n    def __init__(self, rows: list):\n        self.rows = {}\n        for r in rows:\n            self.rows.setdefault((r.tier, r.bucket), []).append(r)\n        for lst in self.rows.values():\n            lst.sort(key=lambda r: (r.effective, r.origin.ordinal))\n\n    def price(self, tier: int, bucket_name: str, at: int, minutes: int) -> int:\n        row = None\n        for r in self.rows.get((tier, bucket_name), []):\n            if r.effective <= at:\n                row = r\n        if row is None:\n            return 0\n        return to_minor(row.base) + to_minor(row.per_minute) * minutes\n",
    "src/quillfen/report/reconcile.py": "\"\"\"Reconciliation identities computed from the rendered outputs themselves.\"\"\"\nfrom __future__ import annotations\n\nimport csv\nimport io\nimport json\nimport xml.etree.ElementTree as ET\n\n\ndef _csv_rows(text):\n    return list(csv.DictReader(io.StringIO(text)))\n\n\ndef identities(out: dict) -> list:\n    ledger = _csv_rows(out[\"ledger.csv\"])\n    commitments = _csv_rows(out[\"commitments.csv\"])\n    blame = [l for l in out[\"blame.jsonl\"].splitlines() if l.strip()]\n    accountability = _csv_rows(out[\"accountability.csv\"])\n    unresolvable = json.loads(out[\"unresolvable.json\"])\n    root = ET.fromstring(out[\"chargeback.xml\"])\n    charged = sum(int(t.get(\"penalty_minor\")) for t in root.iter(\"team\")) + sum(int(u.get(\"penalty_minor\")) for u in root.iter(\"unowned\"))\n    settled = sum(int(r[\"penalty_minor\"]) for r in ledger if r[\"penalty_minor\"])\n    owning_pairs = sum(int(t.get(\"late\")) + int(t.get(\"missed\")) for t in root.iter(\"team\"))\n    return [\n        (\"intervals\", len(commitments), len(ledger)),\n        (\"penalty\", settled, charged),\n        (\"blame\", sum(1 for r in ledger if r[\"status\"] == \"EXCUSED_UPSTREAM\"), len(blame)),\n        (\"accountability\", owning_pairs, len(accountability)),\n        (\"unresolvable\", sum(1 for r in ledger if r[\"status\"] == \"UNRESOLVABLE\"), len(unresolvable)),\n    ]\n",
    "src/quillfen/report/writers.py": "\"\"\"Writes the settlement output set.\"\"\"\nfrom __future__ import annotations\n\nimport csv\nimport io\nimport json\nfrom pathlib import Path\nimport xml.etree.ElementTree as ET\nfrom xml.sax.saxutils import quoteattr\n\nfrom ..core.landing import governing_land\nfrom ..keys import interval_id\nfrom ..timebase import MINUTE, fmt\nfrom .reconcile import identities\n\nOUTPUTS = [\"job_identity.tsv\", \"people.jsonl\", \"rejects.csv\", \"commitments.csv\", \"evidence.jsonl\",\n           \"dependency_resolution.csv\", \"state_audit.csv\", \"ledger.csv\", \"blame.jsonl\", \"accountability.csv\",\n           \"unresolvable.json\", \"chargeback.xml\", \"reconciliation.toml\", \"wall_clock.csv\", \"freeze_occurrences.csv\",\n           \"partition_landings.tsv\", \"clock_corrections.csv\", \"mark_decisions.csv\", \"upstream_waits.xml\",\n           \"oncall_shifts.jsonl\", \"team_tiers.json\", \"output_manifest.json\"]\nTIERS = (1, 2, 3)\n\n\ndef _iid(settlement, job_index, nominal):\n    return interval_id(settlement.identity.jobs[job_index].canonical, fmt(nominal))\n\n\ndef _csv(rows, header, delimiter=\",\"):\n    buf = io.StringIO()\n    w = csv.writer(buf, delimiter=delimiter, lineterminator=\"\\n\")\n    w.writerow(header)\n    w.writerows(rows)\n    return buf.getvalue()\n\n\ndef _num(v):\n    return \"\" if v is None else str(v)\n\n\ndef _local(zones, zone, t):\n    \"\"\"Wall reading of an instant in a zone, with the offset in force: 2026-03-29T03:00:00+02:00.\"\"\"\n    offset = zones.offset_at(zone, t)\n    sign = \"-\" if offset < 0 else \"+\"\n    return \"%s%s%02d:%02d\" % (fmt(t + offset * MINUTE)[:-1], sign, abs(offset) // 60, abs(offset) % 60)\n\n\ndef _overlaps(a, b, s):\n    return a < s.corpus.period_end and b > s.corpus.period_start\n\n\ndef record_count(name, text):\n    \"\"\"Records of one rendered output, as output_manifest.json counts them.\"\"\"\n    if name.endswith((\".csv\", \".tsv\")):\n        return len(list(csv.reader(io.StringIO(text), delimiter=\"\\t\" if name.endswith(\".tsv\") else \",\"))) - 1\n    if name.endswith(\".jsonl\"):\n        return sum(1 for line in text.splitlines() if line.strip())\n    if name == \"unresolvable.json\":\n        return len(json.loads(text))\n    if name == \"team_tiers.json\":\n        return len(json.loads(text)[\"teams\"]) + 1\n    if name.endswith(\".xml\"):\n        return len(list(ET.fromstring(text)))\n    return sum(1 for line in text.splitlines() if line.startswith(\"[\"))\n\n\ndef render(s) -> dict:\n    ident = s.identity\n    out = {}\n\n    rows = []\n    for job in ident.jobs:\n        for name, frm, to in job.names:\n            rows.append((job.canonical, name, \"\" if frm <= -(10 ** 14) else fmt(frm), \"\" if to >= 10 ** 14 else fmt(to)))\n    rows.sort(key=lambda r: (r[0], r[2] != \"\", r[2], r[1]))\n    out[\"job_identity.tsv\"] = _csv(rows, [\"canonical_job\", \"name\", \"held_from\", \"held_to\"], delimiter=\"\\t\")\n\n    lines = []\n    for pid in sorted(s.people.mails):\n        lines.append(json.dumps({\"person\": pid, \"emails\": sorted(s.people.mails[pid]),\n                                 \"pager_handles\": sorted(s.people.handles.get(pid, ()))}, sort_keys=True))\n    out[\"people.jsonl\"] = \"\".join(l + \"\\n\" for l in lines)\n\n    rej = sorted(set(s.corpus.rejects), key=lambda r: (r[0], r[1]))\n    out[\"rejects.csv\"] = _csv(rej, [\"source\", \"ordinal\", \"reason\"])\n\n    rows = []\n    for iv in s.intervals:\n        rows.append((_iid(s, iv.job.index, iv.nominal), iv.job.canonical, fmt(iv.nominal), fmt(iv.deadline), iv.tier,\n                     iv.sla_minutes, iv.suspension))\n    out[\"commitments.csv\"] = _csv(rows, [\"interval\", \"canonical_job\", \"nominal\", \"deadline\", \"tier\", \"sla_minutes\", \"suspension\"])\n\n    lines = []\n    for iv in s.intervals:\n        e = s.evidence[iv.key]\n        lines.append(json.dumps({\"interval\": _iid(s, iv.job.index, iv.nominal), \"tier\": e.tier,\n                                 \"landed_at\": fmt(e.landed_at) if e.landed_at is not None else None,\n                                 \"candidates\": e.candidates}, sort_keys=True))\n    out[\"evidence.jsonl\"] = \"\".join(l + \"\\n\" for l in lines)\n\n    rows = []\n    for iv in s.intervals:\n        for u, n, lag in sorted(s.upstreams[iv.key], key=lambda x: (_iid(s, x[0], x[1]), x[2])):\n            rows.append((_iid(s, iv.job.index, iv.nominal), _iid(s, u, n), lag))\n    out[\"dependency_resolution.csv\"] = _csv(rows, [\"interval\", \"upstream_interval\", \"lag\"])\n\n    rows = sorted((ident.jobs[idx].canonical, fmt(nom), run, a, b, fmt(at)) for idx, nom, run, a, b, at in s.audit)\n    rows.sort(key=lambda r: (r[0], r[1], r[2], r[5], r[3], r[4]))\n    out[\"state_audit.csv\"] = _csv(rows, [\"canonical_job\", \"nominal\", \"run_id\", \"from_state\", \"to_state\", \"at\"])\n\n    rows = []\n    for r in s.ledger:\n        iv = r[\"interval\"]\n        rows.append((_iid(s, iv.job.index, iv.nominal), r[\"status\"], r[\"reason\"], fmt(r[\"landed_at\"]),\n                     _num(r[\"minutes\"]), r[\"bucket\"] or \"\", _num(r[\"penalty\"])))\n    out[\"ledger.csv\"] = _csv(rows, [\"interval\", \"status\", \"reason\", \"landed_at\", \"lateness_minutes\", \"bucket\", \"penalty_minor\"])\n\n    lines = []\n    for iv, parent, root, depth, teams in s.blame:\n        lines.append(json.dumps({\"interval\": _iid(s, iv.job.index, iv.nominal), \"parent\": _iid(s, *parent),\n                                 \"root\": _iid(s, *root), \"depth\": depth, \"root_teams\": list(teams)}, sort_keys=True))\n    out[\"blame.jsonl\"] = \"\".join(l + \"\\n\" for l in lines)\n\n    rows = [(_iid(s, iv.job.index, iv.nominal), team, person) for iv, team, person in s.accountability]\n    out[\"accountability.csv\"] = _csv(rows, [\"interval\", \"team\", \"person\"])\n\n    entries = [{\"interval\": _iid(s, r[\"interval\"].job.index, r[\"interval\"].nominal), \"reason\": r[\"reason\"]}\n               for r in s.ledger if r[\"status\"] == \"UNRESOLVABLE\"]\n    out[\"unresolvable.json\"] = json.dumps(entries, indent=2, sort_keys=True) + \"\\n\"\n\n    p0, p1 = s.corpus.period_start, s.corpus.period_end\n    xml = ['<?xml version=\"1.0\" encoding=\"utf-8\"?>', \"<chargeback period_start=%s period_end=%s>\" % (quoteattr(fmt(p0)), quoteattr(fmt(p1)))]\n    for team in sorted(s.chargeback):\n        c = s.chargeback[team]\n        xml.append('  <team id=%s penalty_minor=\"%d\" late=\"%d\" missed=\"%d\" blamed_downstream=\"%d\"/>' % (\n            quoteattr(team), c[\"penalty\"], c[\"late\"], c[\"missed\"], c[\"blamed\"]))\n    u = s.unowned\n    xml.append('  <unowned penalty_minor=\"%d\" late=\"%d\" missed=\"%d\"/>' % (u[\"penalty\"], u[\"late\"], u[\"missed\"]))\n    xml.append(\"</chargeback>\")\n    out[\"chargeback.xml\"] = \"\\n\".join(xml) + \"\\n\"\n\n    toml = []\n    for name, lhs, rhs in identities(out):\n        toml += [\"[identity.%s]\" % name, \"lhs = %d\" % lhs, \"rhs = %d\" % rhs, \"residual = %d\" % (lhs - rhs), \"\"]\n    out[\"reconciliation.toml\"] = \"\\n\".join(toml)\n\n    zones = s.corpus.zones\n    rows = [(_iid(s, iv.job.index, iv.nominal), iv.zone, _local(zones, iv.zone, iv.nominal), _local(zones, iv.zone, iv.deadline))\n            for iv in s.intervals]\n    out[\"wall_clock.csv\"] = _csv(rows, [\"interval\", \"zone\", \"local_nominal\", \"local_deadline\"])\n\n    rows = sorted((fmt(a), fmt(b), \";\".join(str(t) for t in sorted(tiers))) for a, b, tiers in s.freezes if _overlaps(a, b, s))\n    out[\"freeze_occurrences.csv\"] = _csv(rows, [\"start\", \"end\", \"tiers\"])\n\n    rows = []\n    for (dataset, nominal), stream in s.streams.items():\n        landed_at, lands = governing_land(stream)\n        if lands:\n            retracts = sum(1 for e in stream if e.kind == \"retract\")\n            rows.append((dataset, fmt(nominal), lands, retracts, fmt(landed_at)))\n    rows.sort(key=lambda r: (r[0], r[1]))\n    out[\"partition_landings.tsv\"] = _csv(rows, [\"dataset\", \"nominal\", \"lands\", \"retracts\", \"governing_landed_at\"], delimiter=\"\\t\")\n\n    rows = []\n    for (job_index, nominal), w in s.commits:\n        corrected = s.clock.correct(w.host, w.local_ms)\n        rows.append((_iid(s, job_index, nominal), w.host, w.local_ms, fmt(corrected)))\n    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]))\n    out[\"clock_corrections.csv\"] = _csv(rows, [\"interval\", \"host\", \"local_ms\", \"corrected_at\"])\n\n    rows = []\n    for (job_index, nominal), m, accepted in s.mark_decisions:\n        rows.append((_iid(s, job_index, nominal), m.actor, fmt(m.at),\n                     \"true\" if accepted else \"false\"))\n    rows.sort()\n    out[\"mark_decisions.csv\"] = _csv(rows, [\"interval\", \"actor\", \"marked_at\", \"accepted\"])\n\n    status_of = {r[\"interval\"].key: r[\"status\"] for r in s.ledger}\n    position = {iv.key: i for i, iv in enumerate(s.intervals)}\n    waits = sorted(s.waits, key=lambda w: (position[w[0].key], w[1].canonical, w[2], -1 if w[3] is None else w[3]))\n    xml = ['<?xml version=\"1.0\" encoding=\"utf-8\"?>', \"<upstream_waits>\"]\n    for iv, up, lag, waited in waits:\n        waited_id = \"\" if waited is None else _iid(s, up.index, waited)\n        state = \"\" if waited is None else status_of.get((up.index, waited), \"\")\n        xml.append(\"  <wait interval=%s upstream_job=%s lag=\\\"%d\\\" waited_on=%s status=%s/>\" % (\n            quoteattr(_iid(s, iv.job.index, iv.nominal)), quoteattr(up.canonical), lag, quoteattr(waited_id), quoteattr(state)))\n    xml.append(\"</upstream_waits>\")\n    out[\"upstream_waits.xml\"] = \"\\n\".join(xml) + \"\\n\"\n\n    rows = []\n    for team, a, b, attendee in s.shifts:\n        if not _overlaps(a, b, s):\n            continue\n        rows.append((team or \"\", fmt(a), fmt(b), (s.people.by_mail(attendee) if attendee else None) or \"\"))\n    rows.sort()\n    out[\"oncall_shifts.jsonl\"] = \"\".join(json.dumps({\"team\": t, \"start\": a, \"end\": b, \"person\": p or None}, sort_keys=True) + \"\\n\"\n                                         for t, a, b, p in rows)\n\n    def cells(by_tier):\n        return {str(t): {\"late\": by_tier.get(t, {}).get(\"late\", 0), \"missed\": by_tier.get(t, {}).get(\"missed\", 0),\n                         \"penalty_minor\": by_tier.get(t, {}).get(\"penalty\", 0)} for t in TIERS}\n    tiers_doc = {\"teams\": {team: cells(s.tier_charge[\"teams\"].get(team, {})) for team in sorted(s.chargeback)},\n                 \"unowned\": cells(s.tier_charge[\"unowned\"])}\n    out[\"team_tiers.json\"] = json.dumps(tiers_doc, indent=2, sort_keys=True) + \"\\n\"\n\n    manifest = {name: record_count(name, text) for name, text in out.items()}\n    out[\"output_manifest.json\"] = json.dumps({\"outputs\": manifest}, indent=2, sort_keys=True) + \"\\n\"\n    return out\n\n\ndef write(settlement, output_dir) -> None:\n    output_dir = Path(output_dir)\n    output_dir.mkdir(parents=True, exist_ok=True)\n    for name, text in render(settlement).items():\n        (output_dir / name).write_text(text, encoding=\"utf-8\", newline=\"\\n\")\n",
    "src/quillfen/timebase.py": "\"\"\"Instants, wall clocks and the shipped zone table.\"\"\"\nfrom __future__ import annotations\n\nimport bisect\nimport calendar\nimport re\nfrom dataclasses import dataclass, field\n\nMINUTE = 60\nHOUR = 3600\nDAY = 86400\nFOREVER = 10 ** 15\n\n_ISO = re.compile(r\"^(\\d{4})-(\\d{2})-(\\d{2})[T ](\\d{2}):(\\d{2})(?::(\\d{2})(?:\\.(\\d+))?)?\\s*(Z|[+-]\\d{2}:?\\d{2})?$\")\n\n\ndef instant(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> int:\n    \"\"\"Whole seconds since the epoch for a UTC civil time (raises on impossible dates).\"\"\"\n    if not (1 <= month <= 12) or not (1 <= day <= calendar.monthrange(year, month)[1]):\n        raise ValueError(\"impossible date\")\n    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):\n        raise ValueError(\"impossible time\")\n    return calendar.timegm((year, month, day, hour, minute, second, 0, 0, 0))\n\n\ndef civil(t: int) -> tuple:\n    import time\n    s = time.gmtime(t)\n    return s.tm_year, s.tm_mon, s.tm_mday, s.tm_hour, s.tm_min, s.tm_sec, s.tm_wday\n\n\ndef fmt(t: int | None) -> str:\n    if t is None:\n        return \"\"\n    y, mo, d, h, mi, s, _ = civil(t)\n    return \"%04d-%02d-%02dT%02d:%02d:%02dZ\" % (y, mo, d, h, mi, s)\n\n\ndef parse_offset(text: str) -> int:\n    \"\"\"'+05:30', '-0800', 'Z' -> minutes east of UTC.\"\"\"\n    text = text.strip()\n    if text in (\"Z\", \"z\", \"UTC\", \"GMT\"):\n        return 0\n    m = re.match(r\"^([+-])(\\d{2}):?(\\d{2})$\", text)\n    if not m:\n        raise ValueError(\"bad offset %r\" % text)\n    minutes = int(m.group(2)) * 60 + int(m.group(3))\n    return -minutes if m.group(1) == \"-\" else minutes\n\n\ndef parse_stamp(text: str, default_offset: int | None = 0) -> int:\n    \"\"\"ISO-like timestamp with optional offset; fractional seconds are dropped.\"\"\"\n    m = _ISO.match(text.strip())\n    if not m:\n        raise ValueError(\"bad timestamp %r\" % text)\n    y, mo, d, h, mi = (int(m.group(i)) for i in range(1, 6))\n    s = int(m.group(6) or 0)\n    off = m.group(8)\n    base = instant(y, mo, d, h, mi, s)\n    if off is None:\n        if default_offset is None:\n            raise ValueError(\"timestamp without offset %r\" % text)\n        return base - default_offset * 60\n    return base - parse_offset(off) * 60\n\n\n@dataclass\nclass ZoneTable:\n    \"\"\"Offsets per zone from tz_transitions.csv; link rows alias one zone name to another.\"\"\"\n\n    transitions: dict = field(default_factory=dict)\n    links: dict = field(default_factory=dict)\n\n    def add(self, zone: str, effective: int, offset_minutes: int) -> None:\n        self.transitions.setdefault(zone, []).append((effective, offset_minutes))\n\n    def seal(self) -> None:\n        for z in self.transitions:\n            self.transitions[z].sort()\n\n    def target(self, zone: str) -> str:\n        hops = 0\n        while zone in self.links and hops < 16:\n            zone = self.links[zone]\n            hops += 1\n        return zone\n\n    def knows(self, zone: str) -> bool:\n        return self.target(zone) in self.transitions\n\n    def offset_at(self, zone: str, t: int) -> int:\n        rows = self.transitions[self.target(zone)]\n        i = bisect.bisect_right(rows, (t, 10 ** 9)) - 1\n        return rows[max(i, 0)][1]\n\n    def wall(self, zone: str, t: int) -> int:\n        \"\"\"Wall clock of `zone` at instant `t`, expressed as seconds on a UTC-like scale.\"\"\"\n        return t + self.offset_at(zone, t) * MINUTE\n\n    def instants_for_wall(self, zone: str, wall: int) -> list:\n        \"\"\"Every instant whose wall clock in `zone` reads `wall` (0, 1 or 2 of them).\"\"\"\n        rows = self.transitions[self.target(zone)]\n        seen = set()\n        out = []\n        for _, off in rows:\n            if off in seen:\n                continue\n            seen.add(off)\n            t = wall - off * MINUTE\n            if self.offset_at(zone, t) == off:\n                out.append(t)\n        return sorted(set(out))\n\n    def wall_to_instant(self, zone: str, wall: int) -> int:\n        \"\"\"Source timestamps written as wall time: a repeated reading takes its earlier instant.\"\"\"\n        found = self.instants_for_wall(zone, wall)\n        if not found:\n            raise ValueError(\"wall time does not occur in %s\" % zone)\n        return found[0]\n\n    def transition_before(self, zone: str, wall: int):\n        \"\"\"For a wall time that does not occur: (instant of the jump, offset before, offset after).\"\"\"\n        rows = self.transitions[self.target(zone)]\n        for i in range(1, len(rows)):\n            t, off = rows[i]\n            prev = rows[i - 1][1]\n            if off > prev and t + prev * MINUTE <= wall < t + off * MINUTE:\n                return t, prev, off\n        return None\n\n\ndef wall_parts(wall: int) -> tuple:\n    return civil(wall)\n",
    "tests/__init__.py": "",
    "tests/test_cron.py": "import unittest\n\nfrom quillfen.core.cron import Schedule\n\n\nclass ScheduleTests(unittest.TestCase):\n    def test_steps_ranges_and_names(self):\n        s = Schedule(\"*/15 1-23/4 * JAN-MAR MON-FRI\")\n        self.assertEqual(sorted(s.minutes), [0, 15, 30, 45])\n        self.assertEqual(sorted(s.hours), [1, 5, 9, 13, 17, 21])\n        self.assertEqual(sorted(s.months), [1, 2, 3])\n        self.assertEqual(sorted(s.days_of_week), [1, 2, 3, 4, 5])\n\n    def test_sunday_is_zero_or_seven(self):\n        self.assertEqual(Schedule(\"0 0 * * 7\").days_of_week, Schedule(\"0 0 * * 0\").days_of_week)\n\n    def test_weekday_only_schedule(self):\n        s = Schedule(\"30 6 * * 1-5\")\n        self.assertTrue(s.day_matches(2026, 3, 2))\n        self.assertFalse(s.day_matches(2026, 3, 1))\n\n    def test_invalid_expression(self):\n        with self.assertRaises(ValueError):\n            Schedule(\"61 * * * *\")\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
    "tests/test_keys.py": "import unittest\n\nfrom quillfen.keys import interval_id, normalize_handle, normalize_key, normalize_mail\n\n\nclass KeyTests(unittest.TestCase):\n    def test_separators_collapse(self):\n        self.assertEqual(normalize_key(\" Stage-Orders_Daily \"), \"stage.orders.daily\")\n        self.assertEqual(normalize_key(\"stage/orders..daily\"), \"stage.orders.daily\")\n\n    def test_dataset_names_share_the_rule(self):\n        self.assertEqual(normalize_key(\"LAKE/orders_daily\"), \"lake.orders.daily\")\n\n    def test_handles_and_mail(self):\n        self.assertEqual(normalize_handle(\"@Quillfen/Ingest-Core\"), \"quillfen/ingest-core\")\n        self.assertEqual(normalize_mail(\"mailto:A.Rao@Quillfen.example\"), \"a.rao@quillfen.example\")\n\n    def test_interval_id(self):\n        self.assertEqual(interval_id(\"job:a.b\", \"2026-03-01T00:00:00Z\"), \"job:a.b@2026-03-01T00:00:00Z\")\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
    "tests/test_money.py": "import unittest\n\nfrom quillfen.records import Origin, RateRow\nfrom quillfen.report.penalty import RateCard, bucket, lateness_minutes\nfrom quillfen.timebase import instant\n\n\nclass MoneyTests(unittest.TestCase):\n    def test_bucket_bands(self):\n        self.assertEqual(bucket(0), \"B0\")\n        self.assertEqual(bucket(45), \"B30\")\n        self.assertEqual(bucket(600), \"B120\")\n\n    def test_whole_minute_lateness(self):\n        self.assertEqual(lateness_minutes(7200), 120)\n\n    def test_latest_rate_row_applies(self):\n        o = Origin(\"ratecard.fwf\", 1)\n        card = RateCard([RateRow(2, \"B30\", instant(2026, 1, 1), \"2\", \"1\", o),\n                         RateRow(2, \"B30\", instant(2026, 3, 1), \"5\", \"2\", o)])\n        self.assertEqual(card.price(2, \"B30\", instant(2026, 2, 1), 40), 200 + 100 * 40)\n        self.assertEqual(card.price(2, \"B30\", instant(2026, 3, 2), 40), 500 + 200 * 40)\n        self.assertEqual(card.price(1, \"B30\", instant(2026, 3, 2), 40), 0)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
    "tests/test_readers.py": "import tempfile\nimport unittest\nfrom pathlib import Path\n\nfrom quillfen.parsers.graph import read_producers, read_rates\nfrom quillfen.parsers.workers import logfmt_pairs, read_heartbeats\nfrom quillfen.records import Corpus\n\n\nclass ReaderTests(unittest.TestCase):\n    def setUp(self):\n        self.dir = tempfile.TemporaryDirectory()\n        self.root = Path(self.dir.name)\n\n    def tearDown(self):\n        self.dir.cleanup()\n\n    def test_rate_rows_and_rejects(self):\n        p = self.root / \"ratecard.fwf\"\n        p.write_text(\"TIER BUCKET EFFECTIVE_FROM          BASE      PER_MINUTE CUR\\n\"\n                     \"1    B0     2026-01-01T00:00:00Z 2         1          EUR\\n\"\n                     \"1    B30    2026-01-01T00:00:00Z 12,50     1          EUR\\n\", encoding=\"utf-8\")\n        c = Corpus()\n        read_rates(p, c)\n        self.assertEqual(len(c.rates), 1)\n        self.assertEqual(c.rejects, [(\"ratecard.fwf\", 2, \"MALFORMED_RECORD\")])\n\n    def test_producer_rows(self):\n        p = self.root / \"dataset_producers.psv\"\n        p.write_text(\"dataset|producer_job|valid_from|valid_to\\n\"\n                     \"LAKE/Orders_Daily|Stage-Orders-Daily|2025-01-01T00:00Z|\\n\", encoding=\"utf-8\")\n        c = Corpus()\n        read_producers(p, c)\n        self.assertEqual((c.producers[0].dataset, c.producers[0].key, c.producers[0].valid_to),\n                         (\"lake.orders.daily\", \"stage.orders.daily\", None))\n\n    def test_plain_logfmt(self):\n        kv = logfmt_pairs('ts=2026-03-04T05:00:00Z host=wk-a-01 event=commit msg=\"run commit finished\"')\n        self.assertEqual(kv[\"event\"], \"commit\")\n        self.assertEqual(kv[\"msg\"], \"run commit finished\")\n\n    def test_heartbeat_offset(self):\n        p = self.root / \"heartbeats.txt\"\n        p.write_text(\"host: wk-e-01\\nsent: 2026-03-04T05:00:02.250Z\\nreceived: 2026-03-04T05:00:00.250Z\\n\", encoding=\"utf-8\")\n        c = Corpus()\n        read_heartbeats(p, c)\n        self.assertEqual(c.clock_samples[0].offset_ms, 2000)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
    "tests/test_timebase.py": "import unittest\n\nfrom quillfen.timebase import ZoneTable, fmt, instant, parse_stamp\n\n\ndef berlin_2026():\n    z = ZoneTable()\n    z.add(\"Europe/Berlin\", 0, 60)\n    z.add(\"Europe/Berlin\", instant(2026, 3, 29, 1), 120)\n    z.add(\"Europe/Berlin\", instant(2026, 10, 25, 1), 60)\n    z.links[\"CET\"] = \"Europe/Berlin\"\n    z.seal()\n    return z\n\n\nclass TimebaseTests(unittest.TestCase):\n    def test_parse_with_offset(self):\n        self.assertEqual(fmt(parse_stamp(\"2026-03-04 10:00:00+05:30\", default_offset=None)), \"2026-03-04T04:30:00Z\")\n\n    def test_parse_without_offset_uses_default(self):\n        self.assertEqual(fmt(parse_stamp(\"2026-03-04 10:00:00\", default_offset=0)), \"2026-03-04T10:00:00Z\")\n\n    def test_offset_lookup_and_links(self):\n        z = berlin_2026()\n        self.assertEqual(z.offset_at(\"CET\", instant(2026, 4, 1)), 120)\n        self.assertEqual(z.offset_at(\"Europe/Berlin\", instant(2026, 3, 29, 0, 59, 59)), 60)\n\n    def test_repeated_wall_reading_takes_earlier_instant(self):\n        z = berlin_2026()\n        t = z.wall_to_instant(\"Europe/Berlin\", instant(2026, 10, 25, 2, 30))\n        self.assertEqual(fmt(t), \"2026-10-25T00:30:00Z\")\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n",
}
# Each entry turns one repaired function back into its shipped form.
INJECTIONS = [
    {"module": "quillfen.parsers", "clause": "2.4", "function": "scheduler.syslog_year", "path": "src/quillfen/parsers/scheduler.py", "repaired": "def syslog_year(corpus: Corpus, month: int, day: int, hour: int, minute: int, second: int) -> int:\n    \"\"\"Syslog stamps carry no year: take the year that puts the stamp nearest the period start.\"\"\"\n    anchor = corpus.period_start\n    y0 = time_year(anchor)\n    best = None\n    for y in (y0 - 1, y0, y0 + 1):\n        try:\n            t = instant(y, month, day, hour, minute, second)\n        except ValueError:\n            continue\n        if best is None or abs(t - anchor) < best[0]:\n            best = (abs(t - anchor), y)\n    if best is None:\n        raise ValueError(\"date\")\n    return best[1]\n", "shipped": "def syslog_year(corpus: Corpus, month: int, day: int, hour: int, minute: int, second: int) -> int:\n    \"\"\"Syslog stamps carry no year: a legacy export only covers its own settlement year.\"\"\"\n    year = time_year(corpus.period_start)\n    instant(year, month, day, hour, minute, second)\n    return year\n"},
    {"module": "quillfen.parsers", "clause": "2.2", "function": "ical.unfold", "path": "src/quillfen/parsers/ical.py", "repaired": "        if raw[:1] in (\" \", \"\\t\") and out:\n            out[-1] += raw[1:]\n", "shipped": "        if raw[:1] in (\" \", \"\\t\") and out:\n            out[-1] += raw\n"},
    {"module": "quillfen.parsers", "clause": "2.5", "function": "scheduler.eu_instant", "path": "src/quillfen/parsers/scheduler.py", "repaired": "    \"\"\"The EU exporter writes Europe/Berlin wall time.\"\"\"\n    m = _EU_STAMP.match(require(text).strip())\n    if not m:\n        raise ValueError(\"eu stamp\")\n    d, mo, y, h, mi, s = (int(g) for g in m.groups())\n    return corpus.zones.wall_to_instant(\"Europe/Berlin\", instant(y, mo, d, h, mi, s))\n", "shipped": "    \"\"\"The EU exporter writes day-first UTC stamps.\"\"\"\n    m = _EU_STAMP.match(require(text).strip())\n    if not m:\n        raise ValueError(\"eu stamp\")\n    d, mo, y, h, mi, s = (int(g) for g in m.groups())\n    return corpus.zones.wall_to_instant(\"UTC\", instant(y, mo, d, h, mi, s))\n"},
    {"module": "quillfen.parsers", "clause": "2.3", "function": "workers.logfmt_pairs", "path": "src/quillfen/parsers/workers.py", "repaired": "            while i < n and line[i] != '\"':\n                if line[i] == \"\\\\\" and i + 1 < n:\n                    buf.append(line[i + 1])\n                    i += 2\n                    continue\n                buf.append(line[i])\n                i += 1\n", "shipped": "            while i < n and line[i] != '\"':\n                buf.append(line[i])\n                i += 1\n"},
    {"module": "quillfen.parsers", "clause": "2.6", "function": "org.ldif_attributes", "path": "src/quillfen/parsers/org.py", "repaired": "        name, value = line.split(\":\", 1)\n        attrs.setdefault(name.strip().lower(), []).append(value.strip())\n", "shipped": "        name, value = line.split(\":\", 1)\n        attrs[name.strip().lower()] = [value.strip()]\n"},
    {"module": "quillfen.core", "clause": "3.2", "function": "identity.Identity.resolve_key", "path": "src/quillfen/core/identity.py", "repaired": "        \"\"\"The job holding `key` at `at`; else its most recent holder before `at`; else its first holder after.\"\"\"\n        spans = self.holders.get(key)\n        if not spans:\n            return None\n        for frm, to, idx in spans:\n            if frm <= at < to:\n                return self.jobs[idx]\n        before = [(to, idx) for frm, to, idx in spans if to <= at]\n        if before:\n            return self.jobs[max(before)[1]]\n        return self.jobs[min((frm, idx) for frm, to, idx in spans if frm > at)[1]]\n", "shipped": "        \"\"\"The job a key names: the latest job to have taken that name.\"\"\"\n        spans = self.holders.get(key)\n        if not spans:\n            return None\n        return self.jobs[max((frm, idx) for frm, to, idx in spans)[1]]\n"},
    {"module": "quillfen.core", "clause": "3.4", "function": "cron.Schedule.day_matches", "path": "src/quillfen/core/cron.py", "repaired": "        \"\"\"Standard cron: when both day fields are restricted, a day matching either one qualifies.\"\"\"\n        if month not in self.months:\n            return False\n        weekday = (calendar.weekday(year, month, day) + 1) % 7\n        by_dom = day in self.days_of_month\n        by_dow = weekday in self.days_of_week\n        if self.dom_restricted and self.dow_restricted:\n            return by_dom or by_dow\n        return by_dom and by_dow\n", "shipped": "        \"\"\"A day qualifies when it satisfies the month, day-of-month and day-of-week fields.\"\"\"\n        if month not in self.months:\n            return False\n        weekday = (calendar.weekday(year, month, day) + 1) % 7\n        by_dom = day in self.days_of_month\n        by_dow = weekday in self.days_of_week\n        return by_dom and by_dow\n"},
    {"module": "quillfen.core", "clause": "3.6", "function": "cron.wall_to_fires", "path": "src/quillfen/core/cron.py", "repaired": "    found = zones.instants_for_wall(zone, wall)\n    if len(found) == 1:\n        return found\n    if not found:\n        jump = zones.transition_before(zone, wall)\n        return [jump[0]] if jump else []\n    return [found[-1]]\n", "shipped": "    found = zones.instants_for_wall(zone, wall)\n    if len(found) == 1:\n        return found\n    if not found:\n        # The clock jumped over this reading; keep the pre-jump offset so the run keeps its place.\n        jump = zones.transition_before(zone, wall)\n        return [wall - jump[1] * 60] if jump else []\n    return [found[0]]\n"},
    {"module": "quillfen.core", "clause": "5.4", "function": "clock.ClockBook.correct", "path": "src/quillfen/core/clock.py", "repaired": "        more than a day older than it. Offsets are local clock minus true time.\"\"\"\n        lst = self.by_host.get(host)\n        if not lst:\n            return None\n        i = bisect.bisect_right(self.keys[host], local_ms) - 1\n        if i < 0:\n            return None\n        at_ms, offset_ms = lst[i]\n        if local_ms - at_ms > WINDOW_MS:\n            return None\n        return (local_ms - offset_ms) // 1000\n", "shipped": "        more than a day older than it. Offsets are the correction to apply to the local clock.\"\"\"\n        lst = self.by_host.get(host)\n        if not lst:\n            return None\n        i = bisect.bisect_right(self.keys[host], local_ms) - 1\n        if i < 0:\n            return None\n        at_ms, offset_ms = lst[i]\n        if local_ms - at_ms > WINDOW_MS:\n            return None\n        return (local_ms + offset_ms) // 1000\n"},
    {"module": "quillfen.core", "clause": "3.8", "function": "commitments.SlaBook.effective_sla", "path": "src/quillfen/core/commitments.py", "repaired": "        \"\"\"Latest override at or before the nominal instant; an empty override cancels back to the base.\"\"\"\n        current = None\n        for o in self.by_job.get(job.index, []):\n            if o.effective > nominal:\n                break\n            current = o.minutes\n", "shipped": "        \"\"\"Latest override at or before the nominal instant; a blank override cancels back to the base.\"\"\"\n        current = None\n        for o in self.by_job.get(job.index, []):\n            if o.effective > nominal:\n                break\n            current = o.minutes or None\n"},
    {"module": "quillfen.core", "clause": "5.3", "function": "landing.governing_land", "path": "src/quillfen/core/landing.py", "repaired": "    \"\"\"(instant of the governing land event or None, number of land events).\"\"\"\n    lands = [e for e in stream if e.kind == \"land\"]\n    if not lands:\n        return None, 0\n    last_retract = None\n    for i, e in enumerate(stream):\n        if e.kind == \"retract\":\n            last_retract = i\n    if last_retract is None:\n        return lands[0].at, len(lands)\n    after = [e for e in stream[last_retract + 1:] if e.kind == \"land\"]\n    return (after[0].at if after else None), len(lands)\n", "shipped": "    \"\"\"(instant of the governing land event or None, number of land events).\n\n    A partition is available from its first landing; later landings only refresh data already there.\"\"\"\n    lands = [e for e in stream if e.kind == \"land\"]\n    if not lands:\n        return None, 0\n    return lands[0].at, len(lands)\n"},
    {"module": "quillfen.core", "clause": "5.7", "function": "evidence.mark_accepted", "path": "src/quillfen/core/evidence.py", "repaired": "    \"\"\"An operator mark counts only when an approval that precedes it was sent by someone other than the actor.\"\"\"\n    actor = people.person_of_handle.get(mark.actor.lower())\n    for a in approvals:\n        if a.at > mark.at:\n            continue\n        approver = people.by_mail(a.sender)\n        if approver is not None and actor is not None and approver != actor:\n            return True\n    return False\n", "shipped": "    \"\"\"An operator mark counts once the interval carries an approval (see the operations runbook).\"\"\"\n    return bool(approvals)\n"},
    {"module": "quillfen.core", "clause": "6.3", "function": "deps.governing_upstream", "path": "src/quillfen/core/deps.py", "repaired": "    i = bisect.bisect_left(nominals, nominal) - 1 - lag\n", "shipped": "    i = bisect.bisect_right(nominals, nominal) - 1 - lag\n"},
    {"module": "quillfen.core", "clause": "6.1", "function": "status.classify", "path": "src/quillfen/core/status.py", "repaired": "    if any(a <= interval.deadline < b and (evidence.datasets & scope) for a, b, scope in outages):\n        return \"EXCUSED_OUTAGE\"\n    if any(s not in (\"MET\", \"SUSPENDED\") for s in upstream_statuses):\n        return \"EXCUSED_UPSTREAM\"\n", "shipped": "    if any(s not in (\"MET\", \"SUSPENDED\") for s in upstream_statuses):\n        return \"EXCUSED_UPSTREAM\"\n    if any(a <= interval.deadline < b and (evidence.datasets & scope) for a, b, scope in outages):\n        return \"EXCUSED_OUTAGE\"\n"},
    {"module": "quillfen.report", "clause": "6.4", "function": "blame.root_of", "path": "src/quillfen/report/blame.py", "repaired": "    \"\"\"Follow blame parents to the first interval that was not itself excused by an upstream.\"\"\"\n    depth = 1\n    node = parents[key]\n    while node in parents:\n        node = parents[node]\n        depth += 1\n    return node, depth\n", "shipped": "    \"\"\"The interval an excused interval waited on is where its blame lands.\"\"\"\n    return parents[key], 1\n"},
    {"module": "quillfen.report", "clause": "7.3", "function": "money.to_minor", "path": "src/quillfen/report/money.py", "repaired": "    whole, _, frac = amount.strip().partition(\".\")\n    return int(whole or \"0\") * 100 + int((frac + \"00\")[:2])\n", "shipped": "    return int(float(amount) * 100)\n"},
    {"module": "quillfen.report", "clause": "7.2", "function": "penalty.bucket", "path": "src/quillfen/report/penalty.py", "repaired": "    if minutes < 30:\n        return \"B0\"\n    if minutes < 120:\n        return \"B30\"\n", "shipped": "    if minutes <= 30:\n        return \"B0\"\n    if minutes <= 120:\n        return \"B30\"\n"},
    {"module": "quillfen.report", "clause": "7.1", "function": "penalty.lateness_minutes", "path": "src/quillfen/report/penalty.py", "repaired": "    \"\"\"Whole minutes, any started minute counts.\"\"\"\n    return -(-seconds_late // 60)\n", "shipped": "    \"\"\"Whole minutes late.\"\"\"\n    return seconds_late // 60\n"},
    {"module": "quillfen.report", "clause": "7.5", "function": "chargeback.split", "path": "src/quillfen/report/chargeback.py", "repaired": "    \"\"\"Equal shares in minor units; each leftover unit goes to the next team in ascending team id order.\"\"\"\n    ordered = sorted(teams)\n    share, leftover = divmod(amount, len(ordered))\n    return {team: share + (1 if i < leftover else 0) for i, team in enumerate(ordered)}\n", "shipped": "    \"\"\"Equal shares in minor units; the leftover stays with the first owning team.\"\"\"\n    share, leftover = divmod(amount, len(teams))\n    return {team: share + (leftover if i == 0 else 0) for i, team in enumerate(teams)}\n"},
    {"module": "quillfen.report", "clause": "8.1", "function": "ledger.sort_key", "path": "src/quillfen/report/ledger.py", "repaired": "    return (interval.deadline, interval.job.canonical, interval.nominal)\n", "shipped": "    return (interval.job.canonical, interval.nominal)\n"},
]
# ============================================================================ grading
# Everything below grades the delivered artifacts. Ground truth comes only from the generator and the
# independent reference settlement above, seeded here; the delivered engine runs as an unprivileged
# subprocess on extracts it has never seen.
import collections as _collections
import csv as _csv
import hashlib as _hashlib
import io as _io
import json as _json
import os as _os
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import tomllib as _tomllib
import xml.etree.ElementTree as _ET
import zipfile as _zipfile
from pathlib import Path as _Path

from rewardkit import criteria, criterion

OUT = _Path(_os.environ.get("QF_ARTIFACTS", "/app/out"))
ARCHIVE = OUT / "patched-repo.zip"
ENGINE_TIMEOUT = 900
UNITTEST_TIMEOUT = 300
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
OUTPUT_FILES = ["job_identity.tsv", "people.jsonl", "rejects.csv", "commitments.csv", "evidence.jsonl",
                "dependency_resolution.csv", "state_audit.csv", "ledger.csv", "blame.jsonl", "accountability.csv",
                "unresolvable.json", "chargeback.xml", "reconciliation.toml", "wall_clock.csv", "freeze_occurrences.csv",
                "partition_landings.tsv", "clock_corrections.csv", "mark_decisions.csv", "upstream_waits.xml",
                "oncall_shifts.jsonl", "team_tiers.json", "output_manifest.json"]
STATUS_NAMES = ["SUSPENDED", "UNRESOLVABLE", "MET", "EXCUSED_OUTAGE", "EXCUSED_UPSTREAM", "LATE", "MISSED"]

_SUPPORT_TRIGGERS = {"eu_local", "ics_fold", "logfmt_escape", "ldif_multi", "dom_dow", "sla_zero",
                     "outage_upstream", "key_reuse", "skew"}
_CRUX = set(ALL_FEATURES) - _SUPPORT_TRIGGERS
EXTRACTS = {
    "crux_fold": (41101, 0.35, civil(2026, 10, 18), civil(2026, 11, 15), _CRUX),
    "crux_gap": (41102, 0.35, civil(2027, 3, 1), civil(2027, 3, 31), _CRUX),
    "probe_sources": (41103, 0.3, civil(2027, 12, 18), civil(2028, 1, 16),
                      _CRUX | {"eu_local", "ics_fold", "logfmt_escape", "ldif_multi"}),
    "probe_schedule": (41104, 0.3, civil(2026, 10, 20), civil(2026, 11, 12), _CRUX | {"key_reuse", "dom_dow", "sla_zero"}),
    "probe_evidence": (41105, 0.3, civil(2027, 3, 5), civil(2027, 4, 2), _CRUX | {"skew", "outage_upstream"}),
    "shipped": (20260301, 1.0, civil(2026, 3, 1), civil(2026, 4, 1), set(ALL_FEATURES)),
}
_CACHE = {}


def _root_only_tests_present():
    try:
        st = _Path("/tests").stat()
    except FileNotFoundError:
        return False
    return st.st_uid == 0 and (st.st_mode & 0o077) == 0


def _untrusted(command):
    if _os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if _os.name == "posix" and _os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if _os.name == "posix" and _os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _scratch(prefix):
    path = _Path(_tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o755)
    return path


def _open_tree(root):
    for p in [root, *root.rglob("*")]:
        p.chmod(0o755 if p.is_dir() else 0o644)


def _writable_by_runner(path):
    path.mkdir(parents=True, exist_ok=True)
    if _os.name == "posix" and _os.geteuid() == 0:
        import pwd
        import grp
        _os.chown(path, pwd.getpwnam("nobody").pw_uid, grp.getgrnam("nogroup").gr_gid)
    path.chmod(0o755)
    return path


# ---------------------------------------------------------------------------- extracts and truth
def _extract(name):
    key = ("extract", name)
    if key not in _CACHE:
        seed, scale, p0, p1, feats = EXTRACTS[name]
        world = build(default_params(seed, p0, p1, scale=scale, features=feats))
        rendered = render(world)
        data = _scratch("qf-extract-%s-" % name)
        for fname, blob in rendered.files.items():
            (data / fname).write_bytes(blob)
        _open_tree(data)
        _CACHE[key] = (data, rendered.D, settle(rendered.D))
    return _CACHE[key]


def _truth_tables(name):
    key = ("truth", name)
    if key not in _CACHE:
        data, D, res = _extract(name)
        canon, commits, order, ev = res["canon"], res["commits"], res["order"], res["evidence"]

        def iid(k):
            return "%s@%s" % (canon[k[0]], iso(k[1]))
        T = {}
        T["job_identity"] = sorted((canon[j], name_, "" if frm <= -(1 << 61) else iso(frm), "" if to >= (1 << 61) else iso(to))
                                   for j, spans in enumerate(res["ident"].jobs) for name_, frm, to in spans)
        T["people"] = sorted(("emp:" + eid, tuple(sorted(r["emails"])), tuple(sorted(r["handles"]))) for eid, r in res["people"].items())
        T["rejects"] = sorted(set((s, str(o), c) for s, o, c in res["rejects"]))
        T["state_audit"] = sorted(res["state_audit"])
        T["commitments"] = {iid(k): (canon[k[0]], iso(k[1]), iso(commits[k]["deadline"]), str(commits[k]["tier"]),
                                     str(commits[k]["sla"]), commits[k]["suspension"]) for k in order}
        T["order"] = [iid(k) for k in order]
        T["dependency"] = sorted((iid(k), iid((u, n)), str(lag)) for k in order for (u, n, lag) in res["upstream_of"][k] if (u, n) in commits)
        T["unresolvable"] = sorted((iid(r["key"]), r["reason"]) for r in res["ledger"] if r["status"] == "UNRESOLVABLE")
        T["evidence"] = {iid(k): (ev[k]["tier"], iso(ev[k]["landed_at"]) if ev[k]["landed_at"] is not None else None, ev[k]["candidates"]) for k in order}
        T["ledger_status"] = {iid(r["key"]): (r["status"], r["reason"]) for r in res["ledger"]}
        T["ledger_money"] = {iid(r["key"]): ("" if r["minutes"] is None else str(r["minutes"]), r["bucket"] or "",
                                             "" if r["penalty"] is None else str(r["penalty"])) for r in res["ledger"]}
        T["ledger_landed"] = {iid(r["key"]): (r["status"], r["reason"], iso(ev[r["key"]]["landed_at"]) if ev[r["key"]]["landed_at"] is not None else "") for r in res["ledger"]}
        T["blame_parent"] = {iid(b["key"]): iid(b["parent"]) for b in res["blame"]}
        T["blame_root"] = {iid(b["key"]): (iid(b["root"]), b["depth"], tuple(b["root_teams"])) for b in res["blame"]}
        T["accountability"] = sorted(res["accountability"])
        cb = res["chargeback"]
        T["cb_penalty"] = (sorted((t, v["penalty"]) for t, v in cb.items()), res["unowned"]["penalty"])
        T["cb_counts"] = (sorted((t, v["late"], v["missed"], v["blamed"]) for t, v in cb.items()), (res["unowned"]["late"], res["unowned"]["missed"]))
        led = res["ledger"]
        pen_total = sum(r["penalty"] for r in led if r["penalty"] is not None)
        acc_pairs = sum(v["late"] + v["missed"] for v in cb.values())
        T["reconciliation"] = {
            "intervals": (len(order), len(led)),
            "penalty": (pen_total, sum(v["penalty"] for v in cb.values()) + res["unowned"]["penalty"]),
            "blame": (sum(1 for r in led if r["status"] == "EXCUSED_UPSTREAM"), len(res["blame"])),
            "accountability": (acc_pairs, len(res["accountability"])),
            "unresolvable": (sum(1 for r in led if r["status"] == "UNRESOLVABLE"), len(T["unresolvable"])),
        }
        T["status_counts"] = {s: sum(1 for r in led if r["status"] == s) for s in STATUS_NAMES}
        _extend_truth(T, res, EXTRACTS[name][2], EXTRACTS[name][3], iid)
        _CACHE[key] = T
    return _CACHE[key]


def _extend_truth(T, res, p0, p1, iid):
    """Truth for the per-mechanism outputs, from the same reference settlement."""
    zt, canon, commits, order = res["zt"], res["canon"], res["commits"], res["order"]

    def local(zone, t):
        return iso(zt.to_local(zone, t))[:-1] + fmt_offset(zt.offset(zone, t))

    def emp(pid):
        return "emp:" + pid if pid is not None else ""
    T["wall_clock"] = {iid(k): (commits[k]["zone"], local(commits[k]["zone"], k[1]), local(commits[k]["zone"], commits[k]["deadline"]))
                       for k in order}
    T["freezes"] = sorted((iso(a), iso(b), ";".join(str(t) for t in sorted(tiers))) for a, b, tiers in res["freeze_occ"] if a < p1 and b > p0)
    rows = []
    for (ds, nom), evs in res["part_events"].items():
        lands = sum(1 for e in evs if e[4] == "land")
        if not lands:
            continue
        seen_land, retracts = False, 0
        for e in evs:
            if e[4] == "land":
                seen_land = True
            elif seen_land:
                retracts += 1
        g = res["governing_land"][(ds, nom)][0]
        rows.append((ds, iso(nom), str(lands), str(retracts), iso(g) if g is not None else ""))
    T["partitions"] = sorted(rows)
    T["clock"] = sorted((iid((j, nom)), host, str(ms), iso(c) if c is not None else "") for j, nom, host, ms, c in res["worker_rows"])
    T["marks"] = sorted((iid(k), m["actor"].strip().lower(), iso(m["at"]),
                         "true" if res["mark_accepted"](m, k) else "false") for k, ms in res["marks"].items() for m in ms)
    T["waits"] = sorted((iid(k), canon[u], str(lag), iid((u, w)) if w is not None else "", res["status"][(u, w)][0] if w is not None else "")
                        for k, u, lag, w in res["waits"])
    T["shifts"] = sorted((tm, iso(a), iso(b), emp(res["person_of_mail"].get(att.lower()) if att else None))
                         for tm, a, b, att in res["rota_occ"] if a < p1 and b > p0)
    tc = res["tier_charge"]

    def cells(by_tier):
        return tuple((by_tier.get(t, {}).get("late", 0), by_tier.get(t, {}).get("missed", 0), by_tier.get(t, {}).get("penalty", 0))
                     for t in (1, 2, 3))
    T["team_tiers"] = (sorted((tm, cells(tc["teams"].get(tm, {}))) for tm in res["chargeback"]), cells(tc["unowned"]))
    T["manifest"] = {
        "job_identity.tsv": len(T["job_identity"]), "people.jsonl": len(T["people"]), "rejects.csv": len(T["rejects"]),
        "commitments.csv": len(order), "evidence.jsonl": len(order), "dependency_resolution.csv": len(T["dependency"]),
        "state_audit.csv": len(T["state_audit"]), "ledger.csv": len(res["ledger"]), "blame.jsonl": len(res["blame"]),
        "accountability.csv": len(T["accountability"]), "unresolvable.json": len(T["unresolvable"]),
        "chargeback.xml": len(res["chargeback"]) + 1, "reconciliation.toml": len(T["reconciliation"]),
        "wall_clock.csv": len(order), "freeze_occurrences.csv": len(T["freezes"]), "partition_landings.tsv": len(T["partitions"]),
        "clock_corrections.csv": len(T["clock"]), "mark_decisions.csv": len(T["marks"]), "upstream_waits.xml": len(T["waits"]),
        "oncall_shifts.jsonl": len(T["shifts"]), "team_tiers.json": len(res["chargeback"]) + 1,
    }


def _extend_run(T, out):
    wall = _read_csv(out / "wall_clock.csv")
    T["wall_clock"] = {r["interval"]: (r["zone"], r["local_nominal"], r["local_deadline"]) for r in wall}
    T["order_wall_clock"] = [r["interval"] for r in wall]
    T["freezes"] = sorted((r["start"], r["end"], r["tiers"]) for r in _read_csv(out / "freeze_occurrences.csv"))
    T["partitions"] = sorted((r["dataset"], r["nominal"], r["lands"], r["retracts"], r["governing_landed_at"])
                             for r in _read_csv(out / "partition_landings.tsv", "\t"))
    T["clock"] = sorted((r["interval"], r["host"], r["local_ms"], r["corrected_at"]) for r in _read_csv(out / "clock_corrections.csv"))
    T["marks"] = sorted((r["interval"], r["actor"], r["marked_at"], r["accepted"]) for r in _read_csv(out / "mark_decisions.csv"))
    root = _ET.fromstring((out / "upstream_waits.xml").read_text(encoding="utf-8"))
    T["waits"] = sorted((e.get("interval"), e.get("upstream_job"), e.get("lag"), e.get("waited_on"), e.get("status")) for e in root)
    T["shifts"] = sorted((d["team"], d["start"], d["end"], d["person"] or "") for d in _read_jsonl(out / "oncall_shifts.jsonl"))
    doc = _json.loads((out / "team_tiers.json").read_text(encoding="utf-8"))

    def cells(by_tier):
        return tuple((by_tier[str(t)]["late"], by_tier[str(t)]["missed"], by_tier[str(t)]["penalty_minor"]) for t in (1, 2, 3))
    T["team_tiers"] = (sorted((tm, cells(v)) for tm, v in doc["teams"].items()), cells(doc["unowned"]))
    T["manifest"] = _json.loads((out / "output_manifest.json").read_text(encoding="utf-8"))["outputs"]


# ---------------------------------------------------------------------------- reading a settlement run
def _read_csv(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(_csv.DictReader(fh, delimiter=delimiter))


def _read_jsonl(path):
    return [_json.loads(line) for line in _Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_tables(out):
    """Parse one run's output directory into comparable tables; None when anything is missing or unreadable."""
    try:
        T = {}
        T["job_identity"] = sorted((r["canonical_job"], r["name"], r["held_from"], r["held_to"]) for r in _read_csv(out / "job_identity.tsv", "\t"))
        T["people"] = sorted((d["person"], tuple(d["emails"]), tuple(d["pager_handles"])) for d in _read_jsonl(out / "people.jsonl"))
        T["rejects"] = sorted(set((r["source"], r["ordinal"], r["reason"]) for r in _read_csv(out / "rejects.csv")))
        T["state_audit"] = sorted((r["canonical_job"], r["nominal"], r["run_id"], r["from_state"], r["to_state"], r["at"]) for r in _read_csv(out / "state_audit.csv"))
        com = _read_csv(out / "commitments.csv")
        T["commitments"] = {r["interval"]: (r["canonical_job"], r["nominal"], r["deadline"], r["tier"], r["sla_minutes"], r["suspension"]) for r in com}
        evid = _read_jsonl(out / "evidence.jsonl")
        led = _read_csv(out / "ledger.csv")
        T["order"] = [r["interval"] for r in com]
        T["order_evidence"] = [d["interval"] for d in evid]
        T["order_ledger"] = [r["interval"] for r in led]
        T["dependency"] = sorted((r["interval"], r["upstream_interval"], r["lag"]) for r in _read_csv(out / "dependency_resolution.csv"))
        T["unresolvable"] = sorted((d["interval"], d["reason"]) for d in _json.loads((out / "unresolvable.json").read_text(encoding="utf-8")))
        T["evidence"] = {d["interval"]: (d["tier"], d["landed_at"], d["candidates"]) for d in evid}
        T["ledger_status"] = {r["interval"]: (r["status"], r["reason"]) for r in led}
        T["ledger_money"] = {r["interval"]: (r["lateness_minutes"], r["bucket"], r["penalty_minor"]) for r in led}
        T["ledger_landed"] = {r["interval"]: (r["status"], r["reason"], r["landed_at"]) for r in led}
        bl = _read_jsonl(out / "blame.jsonl")
        T["blame_parent"] = {d["interval"]: d["parent"] for d in bl}
        T["blame_root"] = {d["interval"]: (d["root"], d["depth"], tuple(d["root_teams"])) for d in bl}
        T["accountability"] = sorted((r["interval"], r["team"], r["person"]) for r in _read_csv(out / "accountability.csv"))
        root = _ET.fromstring((out / "chargeback.xml").read_text(encoding="utf-8"))
        teams = root.findall("team")
        unowned = root.find("unowned")
        T["cb_penalty"] = (sorted((t.get("id"), int(t.get("penalty_minor"))) for t in teams), int(unowned.get("penalty_minor")))
        T["cb_counts"] = (sorted((t.get("id"), int(t.get("late")), int(t.get("missed")), int(t.get("blamed_downstream"))) for t in teams),
                          (int(unowned.get("late")), int(unowned.get("missed"))))
        rec = _tomllib.loads((out / "reconciliation.toml").read_text(encoding="utf-8"))["identity"]
        T["reconciliation"] = {k: (v["lhs"], v["rhs"]) for k, v in rec.items() if v.get("residual") == v["lhs"] - v["rhs"]}
        T["status_counts"] = {s: sum(1 for r in led if r["status"] == s) for s in STATUS_NAMES}
        _extend_run(T, out)
        return T
    except Exception:
        return None


# ---------------------------------------------------------------------------- trees and runs
def _write_tree(files, prefix):
    root = _scratch(prefix)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    _open_tree(root)
    return root


def _reference_tree():
    if "reference_tree" not in _CACHE:
        _CACHE["reference_tree"] = _write_tree(REFERENCE_TREE, "qf-reference-")
    return _CACHE["reference_tree"]


def _shipped_files():
    files = dict(REFERENCE_TREE)
    for d in INJECTIONS:
        files[d["path"]] = files[d["path"]].replace(d["repaired"], d["shipped"], 1)
    return files


def _shipped_tree():
    if "shipped_tree" not in _CACHE:
        _CACHE["shipped_tree"] = _write_tree(_shipped_files(), "qf-shipped-")
    return _CACHE["shipped_tree"]


def _archive_names():
    try:
        with _zipfile.ZipFile(ARCHIVE) as zf:
            return [i.filename for i in zf.infolist()]
    except Exception:
        return None


def _agent_tree():
    if "agent_tree" in _CACHE:
        return _CACHE["agent_tree"]
    tree = None
    try:
        with _zipfile.ZipFile(ARCHIVE) as zf:
            root = _scratch("qf-archive-")
            for info in zf.infolist():
                rel = _Path(info.filename)
                if info.filename.endswith("/"):
                    continue
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("unsafe member")
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info))
            _open_tree(root)
            if (root / "src" / "quillfen" / "__main__.py").is_file():
                tree = root
    except Exception:
        tree = None
    _CACHE["agent_tree"] = tree
    return tree


def _settle_with(tree, extract, tag):
    key = ("run", str(tree), extract, tag)
    if key in _CACHE:
        return _CACHE[key]
    data = _extract(extract)[0]
    out = _writable_by_runner(_scratch("qf-run-%s-" % extract)) / "out"
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(tree / "src"), "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": "/tmp", "LANG": "C.UTF-8"}
    result = None
    try:
        proc = _subprocess.run(_untrusted([_sys.executable, "-B", "-m", "quillfen", "settle", str(data), str(out)]),
                               cwd=str(tree), env=env, capture_output=True, text=True, timeout=ENGINE_TIMEOUT)
        if proc.returncode == 0 and out.is_dir():
            result = out
    except (_subprocess.TimeoutExpired, OSError):
        result = None
    _CACHE[key] = result
    return result


def _agent_tables(extract, tag="first"):
    tree = _agent_tree()
    if tree is None:
        return None
    out = _settle_with(tree, extract, tag)
    return _run_tables(out) if out is not None else None


def _matches(facet, extracts=("crux_fold", "crux_gap")):
    facets = (facet,) if isinstance(facet, str) else tuple(facet)
    for name in extracts:
        got = _agent_tables(name)
        if got is None or any(got.get(f) != _truth_tables(name)[f] for f in facets):
            return False
    return True


# ---------------------------------------------------------------------------- repair records
def _json_artifact(name):
    try:
        return _json.loads((OUT / name).read_text(encoding="utf-8"))
    except Exception:
        return None


def _module_records():
    records = {}
    for fname, module in [("module_core.json", "quillfen.core"), ("module_parser.json", "quillfen.parsers"),
                          ("module_report.json", "quillfen.report")]:
        doc = _json_artifact(fname)
        if not isinstance(doc, dict) or doc.get("module") != module or not isinstance(doc.get("repairs"), list):
            return None
        records[module] = doc["repairs"]
    return records


_UNITTEST_RUNNER = r'''
import json, sys, unittest
ids = json.loads(sys.argv[1])
result = {}
for test_id in ids:
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(test_id)
    except Exception:
        result[test_id] = "missing"
        continue
    cases = []
    stack = [suite]
    while stack:
        s = stack.pop()
        if isinstance(s, unittest.TestSuite):
            stack.extend(s)
        else:
            cases.append(s)
    if not cases or any(type(c).__name__ in ("_FailedTest", "ModuleImportFailure") for c in cases):
        result[test_id] = "missing"
        continue
    r = unittest.TestResult()
    suite.run(r)
    result[test_id] = "pass" if r.wasSuccessful() and r.testsRun > 0 else "fail"
print("@@RESULT@@" + json.dumps(result))
'''


def _run_unittests(files, tests_dir, ids, prefix):
    """Run test ids against a tree built from `files` with `tests_dir` (the archive's tests) laid over it."""
    root = _write_tree(files, prefix)
    if tests_dir is not None:
        dest = root / "tests"
        if dest.exists():
            _shutil.rmtree(dest)
        _shutil.copytree(tests_dir, dest)
        _open_tree(root)
    runner = root / "_grade_runner.py"
    runner.write_text(_UNITTEST_RUNNER, encoding="utf-8")
    runner.chmod(0o644)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(root / "src") + _os.pathsep + str(root),
           "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp", "LANG": "C.UTF-8", "TMPDIR": "/tmp"}
    try:
        proc = _subprocess.run(_untrusted([_sys.executable, "-B", str(runner), _json.dumps(ids)]), cwd=str(root), env=env,
                               capture_output=True, text=True, timeout=UNITTEST_TIMEOUT)
        marker = [l for l in proc.stdout.splitlines() if l.startswith("@@RESULT@@")]
        return _json.loads(marker[-1][len("@@RESULT@@"):]) if marker else None
    except (_subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _regression_entries():
    doc = _json_artifact("test_fixes.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("tests"), list):
        return None
    entries = [(t.get("id"), t.get("clause")) for t in doc["tests"] if isinstance(t, dict)]
    if not entries or any(not isinstance(i, str) or not isinstance(c, str) for i, c in entries):
        return None
    return entries


def _regression_outcomes():
    if "regression" in _CACHE:
        return _CACHE["regression"]
    outcome = None
    tree = _agent_tree()
    entries = _regression_entries()
    if tree is not None and entries is not None and (tree / "tests").is_dir():
        ids = sorted(set(i for i, _ in entries))
        on_reference = _run_unittests(REFERENCE_TREE, tree / "tests", ids, "qf-regress-ref-")
        in_archive = _run_in_archive(tree, ids)
        variants = {}
        for d in INJECTIONS:
            files = dict(REFERENCE_TREE)
            files[d["path"]] = files[d["path"]].replace(d["repaired"], d["shipped"], 1)
            variants[d["clause"] + "|" + d["function"]] = _run_unittests(files, tree / "tests", ids, "qf-regress-var-")
        outcome = {"entries": entries, "reference": on_reference, "archive": in_archive, "variants": variants}
    _CACHE["regression"] = outcome
    return outcome


def _run_in_archive(tree, ids):
    runner_root = _scratch("qf-regress-own-")
    runner = runner_root / "_grade_runner.py"
    runner.write_text(_UNITTEST_RUNNER, encoding="utf-8")
    _open_tree(runner_root)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(tree / "src") + _os.pathsep + str(tree),
           "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp", "LANG": "C.UTF-8", "TMPDIR": "/tmp"}
    try:
        proc = _subprocess.run(_untrusted([_sys.executable, "-B", str(runner), _json.dumps(ids)]), cwd=str(tree), env=env,
                               capture_output=True, text=True, timeout=UNITTEST_TIMEOUT)
        marker = [l for l in proc.stdout.splitlines() if l.startswith("@@RESULT@@")]
        return _json.loads(marker[-1][len("@@RESULT@@"):]) if marker else None
    except (_subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _outputs_changed(before, after):
    """Record-level differences between two runs, keyed as the output contract prescribes."""
    keys = {
        "job_identity.tsv": ("canonical_job", "name", "held_from"), "rejects.csv": ("source", "ordinal"),
        "commitments.csv": ("interval",), "ledger.csv": ("interval",), "dependency_resolution.csv": ("interval", "upstream_interval"),
        "accountability.csv": ("interval", "team"),
        "state_audit.csv": ("canonical_job", "nominal", "run_id", "from_state", "to_state", "at"),
        "people.jsonl": ("person",), "evidence.jsonl": ("interval",), "blame.jsonl": ("interval",), "unresolvable.json": ("interval",),
        "wall_clock.csv": ("interval",), "freeze_occurrences.csv": ("start", "end", "tiers"),
        "partition_landings.tsv": ("dataset", "nominal"), "clock_corrections.csv": ("interval", "host", "local_ms"),
        "mark_decisions.csv": ("interval", "actor", "marked_at"), "oncall_shifts.jsonl": ("team", "start", "end"),
        "upstream_waits.xml": ("interval", "upstream_job", "lag"),
    }

    def index(directory, name):
        path = directory / name
        if name.endswith(".tsv") or name.endswith(".csv"):
            rows = _read_csv(path, "\t" if name.endswith(".tsv") else ",")
            return {tuple(r[k] for k in keys[name]): tuple(sorted(r.items())) for r in rows}
        if name.endswith(".jsonl"):
            return {tuple(d[k] for k in keys[name]): _json.dumps(d, sort_keys=True) for d in _read_jsonl(path)}
        if name == "unresolvable.json":
            return {tuple(d[k] for k in keys[name]): _json.dumps(d, sort_keys=True) for d in _json.loads(path.read_text(encoding="utf-8"))}
        if name == "team_tiers.json":
            doc = _json.loads(path.read_text(encoding="utf-8"))
            found = {team: _json.dumps(v, sort_keys=True) for team, v in doc["teams"].items()}
            found["unowned"] = _json.dumps(doc["unowned"], sort_keys=True)
            return found
        if name == "output_manifest.json":
            return dict(_json.loads(path.read_text(encoding="utf-8"))["outputs"])
        if name == "upstream_waits.xml":
            root = _ET.fromstring(path.read_text(encoding="utf-8"))
            return {tuple(e.get(k) for k in keys[name]): tuple(sorted(e.attrib.items())) for e in root}
        if name.endswith(".xml"):
            root = _ET.fromstring(path.read_text(encoding="utf-8"))
            return {(e.get("id") if e.tag == "team" else "unowned"): tuple(sorted(e.attrib.items())) for e in root}
        return {k: tuple(sorted(v.items())) for k, v in _tomllib.loads(path.read_text(encoding="utf-8"))["identity"].items()}

    counts = {}
    for name in OUTPUT_FILES:
        a, b = index(before, name), index(after, name)
        counts[name] = len(a.keys() ^ b.keys()) + sum(1 for k in a.keys() & b.keys() if a[k] != b[k])
    return counts


def _truth_outputs_changed():
    if "truth_changed" not in _CACHE:
        shipped_out = _settle_with(_shipped_tree(), "shipped", "shipped-engine")
        reference_out = _settle_with(_reference_tree(), "shipped", "reference-engine")
        _CACHE["truth_changed"] = _outputs_changed(shipped_out, reference_out)
    return _CACHE["truth_changed"]


# ============================================================================ positive tests
def _impl_test_job_identity_matches_unseen_extracts():
    """POSITIVE: job_identity.tsv equals the reference on two held-out extracts."""
    assert _matches("job_identity")


def _impl_test_people_match_unseen_extracts():
    """POSITIVE: people.jsonl equals the reference on two held-out extracts."""
    assert _matches("people")


def _impl_test_rejects_and_mark_decisions_match_unseen_extracts():
    """POSITIVE: rejects.csv and mark_decisions.csv equal the reference on two held-out extracts."""
    assert _matches(("rejects", "marks"))


def _impl_test_state_audit_matches_unseen_extracts():
    """POSITIVE: state_audit.csv equals the reference on two held-out extracts."""
    assert _matches("state_audit")


def _impl_test_commitments_and_wall_clock_match_unseen_extracts():
    """POSITIVE: commitments.csv and wall_clock.csv rows equal the reference on two held-out extracts."""
    assert _matches(("commitments", "wall_clock"))


def _impl_test_dependency_resolution_and_upstream_waits_match_unseen_extracts():
    """POSITIVE: dependency_resolution.csv and upstream_waits.xml equal the reference on two held-out extracts."""
    assert _matches(("dependency", "waits"))


def _impl_test_unresolvable_matches_unseen_extracts():
    """POSITIVE: unresolvable.json equals the reference on two held-out extracts."""
    assert _matches("unresolvable")


def _impl_test_interval_outputs_follow_canonical_order():
    """POSITIVE: commitments, evidence, ledger and wall_clock list intervals in contract order."""
    for name in ("crux_fold", "crux_gap"):
        got = _agent_tables(name)
        want = _truth_tables(name)["order"]
        assert got is not None
        assert got["order"] == want and got["order_evidence"] == want and got["order_ledger"] == want
        assert got["order_wall_clock"] == want


def _impl_test_evidence_and_partition_landings_match_unseen_extracts():
    """POSITIVE: evidence.jsonl and partition_landings.tsv equal the reference."""
    assert _matches(("evidence", "partitions"))


def _impl_test_ledger_statuses_match_unseen_extracts():
    """POSITIVE: ledger statuses and reasons equal the reference."""
    assert _matches("ledger_status")


def _impl_test_ledger_penalties_match_unseen_extracts():
    """POSITIVE: ledger lateness, bucket and penalty columns equal the reference."""
    assert _matches("ledger_money")


def _impl_test_blame_parents_match_unseen_extracts():
    """POSITIVE: blame parents equal the reference."""
    assert _matches("blame_parent")


def _impl_test_blame_roots_match_unseen_extracts():
    """POSITIVE: blame roots, depths and root teams equal the reference."""
    assert _matches("blame_root")


def _impl_test_accountability_and_oncall_shifts_match_unseen_extracts():
    """POSITIVE: accountability.csv and oncall_shifts.jsonl equal the reference."""
    assert _matches(("accountability", "shifts"))


def _impl_test_chargeback_penalties_match_unseen_extracts():
    """POSITIVE: chargeback penalties per team and unowned equal the reference."""
    assert _matches("cb_penalty")


def _impl_test_chargeback_counts_and_team_tiers_match_unseen_extracts():
    """POSITIVE: chargeback late, missed and blamed counts and team_tiers.json equal the reference."""
    assert _matches(("cb_counts", "team_tiers"))


def _impl_test_reconciliation_and_output_manifest_match_unseen_extracts():
    """POSITIVE: reconciliation.toml identities and output_manifest.json counts equal the reference."""
    assert _matches(("reconciliation", "manifest"))


def _impl_test_source_reading_probe_settles():
    """POSITIVE: ledger statuses, landed instants and freeze occurrences equal the reference on the source reading probe."""
    assert _matches(("ledger_landed", "freezes"), extracts=("probe_sources",))


def _impl_test_schedule_probe_settles():
    """POSITIVE: ledger statuses and landed instants equal the reference on the schedule probe."""
    assert _matches("ledger_landed", extracts=("probe_schedule",))


def _impl_test_evidence_probe_settles():
    """POSITIVE: ledger statuses, landed instants and clock corrections equal the reference on the evidence probe."""
    assert _matches(("ledger_landed", "clock"), extracts=("probe_evidence",))


_SETTLEMENT_GROUPS = {
    "records": ("job_identity", "people", "rejects", "state_audit", "commitments", "wall_clock", "evidence", "partitions",
                "clock", "marks"),
    "money": ("ledger_status", "ledger_money", "ledger_landed", "cb_penalty", "cb_counts", "team_tiers", "accountability",
              "shifts", "freezes"),
    "lineage": ("dependency", "waits", "unresolvable", "blame_parent", "blame_root", "reconciliation", "manifest"),
}


def _delivered_settlement():
    if "delivered_settlement" not in _CACHE:
        folder = OUT / "settlement"
        present = folder.is_dir() and sorted(p.name for p in folder.iterdir()) == sorted(OUTPUT_FILES)
        _CACHE["delivered_settlement"] = _run_tables(folder) if present else None
    return _CACHE["delivered_settlement"]


def _settlement_group_matches(group):
    got = _delivered_settlement()
    if got is None:
        return False
    truth = _truth_tables("shipped")
    if group == "records" and not (got["order"] == truth["order"] == got["order_evidence"] == got["order_ledger"] == got["order_wall_clock"]):
        return False
    return all(got.get(f) == truth[f] for f in _SETTLEMENT_GROUPS[group])


def _impl_test_summary_and_settlement_records_match_shipped_month():
    """POSITIVE: summary.json status counts and the settlement's identity, rejects, commitments, evidence, landing, clock and mark files equal the reference for the shipped month."""
    doc = _json_artifact("summary.json")
    assert isinstance(doc, dict)
    truth = _truth_tables("shipped")
    seed, scale, p0, p1, feats = EXTRACTS["shipped"]
    assert doc.get("period_start") == iso(p0) and doc.get("period_end") == iso(p1)
    assert doc.get("status_counts") == truth["status_counts"]
    assert _settlement_group_matches("records")


def _impl_test_summary_penalties_and_settlement_money_match_shipped_month():
    """POSITIVE: summary.json penalties and the settlement's ledger, chargeback, tier, accountability, shift and freeze files equal the reference for the shipped month."""
    doc = _json_artifact("summary.json")
    assert isinstance(doc, dict)
    teams, unowned = _truth_tables("shipped")["cb_penalty"]
    assert doc.get("penalty_minor_by_team") == dict(teams)
    assert doc.get("unowned_penalty_minor") == unowned
    assert _settlement_group_matches("money")


def _impl_test_repair_report_and_settlement_lineage_match_shipped_month():
    """POSITIVE: repair-report.json and the settlement's dependency, wait, unresolvable, blame, reconciliation and manifest files equal the reference for the shipped month."""
    doc = _json_artifact("repair-report.json")
    assert isinstance(doc, dict) and isinstance(doc.get("outputs_changed"), dict)
    assert doc["outputs_changed"] == _truth_outputs_changed()
    assert _settlement_group_matches("lineage")


def _impl_test_module_records_name_every_repaired_clause():
    """POSITIVE: module records name exactly the clauses the shipped engine departed from."""
    records = _module_records()
    assert records is not None
    for module in ("quillfen.core", "quillfen.parsers", "quillfen.report"):
        claimed = sorted(str(r.get("clause")) for r in records[module] if isinstance(r, dict))
        expected = sorted(d["clause"] for d in INJECTIONS if d["module"] == module)
        assert claimed == expected, module


def _impl_test_module_records_name_every_repaired_function():
    """POSITIVE: module records pair each clause with its departing function."""
    records = _module_records()
    assert records is not None
    for module in ("quillfen.core", "quillfen.parsers", "quillfen.report"):
        claimed = sorted((str(r.get("clause")), str(r.get("function"))) for r in records[module] if isinstance(r, dict))
        expected = sorted((d["clause"], d["function"]) for d in INJECTIONS if d["module"] == module)
        assert claimed == expected, module


def _impl_test_regression_tests_pin_every_repaired_clause():
    """POSITIVE: every repaired clause has a listed test passing on the repaired engine and failing with that defect restored."""
    outcome = _regression_outcomes()
    assert outcome is not None and outcome["reference"] is not None
    for d in INJECTIONS:
        variant = outcome["variants"][d["clause"] + "|" + d["function"]]
        assert variant is not None
        pinned = [i for i, c in outcome["entries"] if c == d["clause"]
                  and outcome["reference"].get(i) == "pass" and variant.get(i) == "fail"]
        assert pinned, d["clause"]


# ============================================================================ negative tests
# Inverted polarity: each returns normally (and so costs its weight) only when the shortcut is present.
# A missing or unreadable artifact makes each of them fail, so an untouched container is never penalised.

def _impl_negative_settlement_differs_between_identical_runs():
    """NEGATIVE: two runs over one extract write different bytes."""
    # Inverted: passes when two runs of the delivered engine over one extract write different bytes.
    tree = _agent_tree()
    assert tree is not None
    first = _settle_with(tree, "crux_fold", "first")
    second = _settle_with(tree, "crux_fold", "second")
    assert first is not None and second is not None
    differs = any((first / n).read_bytes() != (second / n).read_bytes() for n in OUTPUT_FILES if (first / n).is_file() and (second / n).is_file())
    assert differs


def _impl_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the engine writes one ledger for two different extracts."""
    # Inverted: passes when the engine writes the same ledger for two different extracts.
    tree = _agent_tree()
    assert tree is not None
    a = _settle_with(tree, "crux_fold", "first")
    b = _settle_with(tree, "crux_gap", "first")
    assert a is not None and b is not None and (a / "ledger.csv").is_file() and (b / "ledger.csv").is_file()
    assert (a / "ledger.csv").read_bytes() == (b / "ledger.csv").read_bytes()


def _impl_negative_repair_breaks_shipped_unit_tests():
    """NEGATIVE: a shipped unit test fails against the delivered source."""
    # Inverted: passes when a shipped unit test fails against the delivered src tree.
    tree = _agent_tree()
    assert tree is not None
    shipped_tests = {rel: text for rel, text in REFERENCE_TREE.items() if rel.startswith("tests/")}
    ids = []
    for rel, text in sorted(shipped_tests.items()):
        if not rel.endswith(".py") or rel.endswith("__init__.py"):
            continue
        module = rel[:-3].replace("/", ".")
        import ast as _ast
        for node in _ast.parse(text).body:
            if isinstance(node, _ast.ClassDef):
                for item in node.body:
                    if isinstance(item, _ast.FunctionDef) and item.name.startswith("test"):
                        ids.append("%s.%s.%s" % (module, node.name, item.name))
    files = {rel: (tree / rel).read_text(encoding="utf-8") for rel in _relative_files(tree / "src", tree)}
    files.update(shipped_tests)
    result = _run_unittests(files, None, ids, "qf-shipped-suite-")
    assert result is not None
    assert any(v != "pass" for v in result.values())


def _relative_files(folder, root):
    return [p.relative_to(root).as_posix() for p in folder.rglob("*.py") if "__pycache__" not in p.parts]


def _impl_negative_regression_record_lists_unsound_tests():
    """NEGATIVE: a listed regression test is missing from the archive or fails against the repaired engine."""
    # Inverted: passes when a listed test id cannot be loaded from the archive, or loads but fails on the repaired reference engine.
    outcome = _regression_outcomes()
    assert outcome is not None and outcome["reference"] is not None and outcome["archive"] is not None
    assert any(v == "missing" for v in outcome["archive"].values()) or any(v == "fail" for v in outcome["reference"].values())


def _impl_negative_shipped_month_records_disagree_with_archive_engine():
    """NEGATIVE: summary.json or a settlement file disagrees with the delivered engine's own run of the shipped month."""
    # Inverted: passes when summary.json, or the delivered settlement folder, differs from what the delivered engine itself settles.
    doc = _json_artifact("summary.json")
    tables = _agent_tables("shipped")
    assert isinstance(doc, dict) and tables is not None
    teams, unowned = tables["cb_penalty"]
    own = {"status_counts": tables["status_counts"], "penalty_minor_by_team": dict(teams), "unowned_penalty_minor": unowned}
    delivered = _delivered_settlement()
    assert any(doc.get(k) != v for k, v in own.items()) or (delivered is not None and delivered != tables)


def _impl_negative_repair_report_disagrees_with_archive_engine():
    """NEGATIVE: repair-report.json disagrees with the delivered engine's own run."""
    # Inverted: passes when repair-report.json differs from the delivered engine's own difference against the shipped engine.
    doc = _json_artifact("repair-report.json")
    tree = _agent_tree()
    assert isinstance(doc, dict) and tree is not None
    own = _settle_with(tree, "shipped", "first")
    shipped_out = _settle_with(_shipped_tree(), "shipped", "shipped-engine")
    assert own is not None and shipped_out is not None
    try:
        counts = _outputs_changed(shipped_out, own)
    except Exception:
        counts = None
    assert counts is not None and doc.get("outputs_changed") != counts


def _impl_negative_archive_ships_compiled_bytecode():
    """NEGATIVE: the archive carries compiled bytecode."""
    # Inverted: passes when the archive carries a __pycache__ directory or a .pyc file.
    names = _archive_names()
    assert names is not None
    assert any("__pycache__" in n.split("/") or n.endswith(".pyc") for n in names)


def _definitions(text):
    """Top-level functions, classes and their methods of one module, keyed by qualified name."""
    import ast as _ast
    try:
        tree = _ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    found = {}
    for node in tree.body:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            found[node.name] = node
        elif isinstance(node, _ast.ClassDef):
            found[node.name] = node
            for item in node.body:
                if isinstance(item, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    found[node.name + "." + item.name] = item
    return found


def _archive_source(tree, rel):
    path = tree / rel
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def _impl_negative_archive_drops_shipped_definition():
    """NEGATIVE: the archive drops a shipped module, class or function, or changes a shipped signature."""
    # Inverted: passes when a shipped source module, class, function or method is missing from the archive or takes other parameters.
    import ast as _ast
    tree = _agent_tree()
    assert tree is not None
    departures = []
    for rel, text in sorted(_shipped_files().items()):
        if not (rel.startswith("src/") and rel.endswith(".py")):
            continue
        delivered = _archive_source(tree, rel)
        theirs = _definitions(delivered) if delivered is not None else None
        if theirs is None:
            departures.append(rel)
            continue
        for name, node in _definitions(text).items():
            other = theirs.get(name)
            if other is None or type(other) is not type(node):
                departures.append(rel + "::" + name)
            elif not isinstance(node, _ast.ClassDef) and _ast.dump(other.args) != _ast.dump(node.args):
                departures.append(rel + "::" + name)
    assert departures


def _impl_negative_departing_function_keeps_shipped_body():
    """NEGATIVE: a function whose shipped body departs from the contract is delivered with that body unchanged."""
    # Inverted: passes when a departing function is present in the archive with its shipped statements (docstring aside) intact.
    import ast as _ast
    tree = _agent_tree()
    assert tree is not None
    shipped = _shipped_files()

    def statements(node):
        body = list(node.body)
        if body and isinstance(body[0], _ast.Expr) and isinstance(body[0].value, _ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        return [_ast.dump(s) for s in body]

    untouched = []
    for d in INJECTIONS:
        qualified = d["function"].split(".", 1)[1]
        delivered = _archive_source(tree, d["path"])
        theirs = _definitions(delivered) if delivered is not None else None
        mine = _definitions(shipped[d["path"]]).get(qualified)
        if theirs is None or mine is None or qualified not in theirs:
            continue
        if statements(theirs[qualified]) == statements(mine):
            untouched.append(d["function"])
    assert untouched


# ============================================================================ rewardkit criteria
# rewardkit calls checks from worker threads and aborts the whole reward on an uncaught exception.
# Checks run one at a time because the extract, run and regression caches and OUT are shared module
# state and every engine run is held to ENGINE_TIMEOUT; a raised assertion scores the check False.
_GRADE_LOCK = _threading.Lock()


def _bind(workspace):
    global OUT, ARCHIVE
    OUT = _Path(_os.environ.get("QF_ARTIFACTS", str(_Path(str(workspace)) / "out")))
    ARCHIVE = OUT / "patched-repo.zip"


def _pass(workspace, check):
    with _GRADE_LOCK:
        _bind(workspace)
        try:
            check()
            return True
        except Exception:
            return False


@criterion(description="job_identity.tsv equals the reference on two held-out extracts")
def test_job_identity_matches_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_job_identity_matches_unseen_extracts)


@criterion(description="people.jsonl equals the reference on two held-out extracts")
def test_people_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_people_match_unseen_extracts)


@criterion(description="rejects.csv and mark_decisions.csv equal the reference on two held-out extracts")
def test_rejects_and_mark_decisions_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_rejects_and_mark_decisions_match_unseen_extracts)


@criterion(description="state_audit.csv equals the reference on two held-out extracts")
def test_state_audit_matches_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_state_audit_matches_unseen_extracts)


@criterion(description="commitments.csv and wall_clock.csv rows equal the reference on two held-out extracts")
def test_commitments_and_wall_clock_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_commitments_and_wall_clock_match_unseen_extracts)


@criterion(description="dependency_resolution.csv and upstream_waits.xml equal the reference on two held-out extracts")
def test_dependency_resolution_and_upstream_waits_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_dependency_resolution_and_upstream_waits_match_unseen_extracts)


@criterion(description="unresolvable.json equals the reference on two held-out extracts")
def test_unresolvable_matches_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_unresolvable_matches_unseen_extracts)


@criterion(description="commitments, evidence, ledger and wall_clock list intervals in contract order")
def test_interval_outputs_follow_canonical_order(workspace):
    return _pass(workspace, _impl_test_interval_outputs_follow_canonical_order)


@criterion(description="evidence.jsonl and partition_landings.tsv equal the reference")
def test_evidence_and_partition_landings_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_evidence_and_partition_landings_match_unseen_extracts)


@criterion(description="ledger statuses and reasons equal the reference")
def test_ledger_statuses_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_ledger_statuses_match_unseen_extracts)


@criterion(description="ledger lateness, bucket and penalty columns equal the reference")
def test_ledger_penalties_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_ledger_penalties_match_unseen_extracts)


@criterion(description="blame parents equal the reference")
def test_blame_parents_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_blame_parents_match_unseen_extracts)


@criterion(description="blame roots, depths and root teams equal the reference")
def test_blame_roots_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_blame_roots_match_unseen_extracts)


@criterion(description="accountability.csv and oncall_shifts.jsonl equal the reference")
def test_accountability_and_oncall_shifts_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_accountability_and_oncall_shifts_match_unseen_extracts)


@criterion(description="chargeback penalties per team and unowned equal the reference")
def test_chargeback_penalties_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_chargeback_penalties_match_unseen_extracts)


@criterion(description="chargeback late, missed and blamed counts and team_tiers.json equal the reference")
def test_chargeback_counts_and_team_tiers_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_chargeback_counts_and_team_tiers_match_unseen_extracts)


@criterion(description="reconciliation.toml identities and output_manifest.json counts equal the reference")
def test_reconciliation_and_output_manifest_match_unseen_extracts(workspace):
    return _pass(workspace, _impl_test_reconciliation_and_output_manifest_match_unseen_extracts)


@criterion(description="ledger statuses, landed instants and freeze occurrences equal the reference on the source reading probe")
def test_source_reading_probe_settles(workspace):
    return _pass(workspace, _impl_test_source_reading_probe_settles)


@criterion(description="ledger statuses and landed instants equal the reference on the schedule probe")
def test_schedule_probe_settles(workspace):
    return _pass(workspace, _impl_test_schedule_probe_settles)


@criterion(description="ledger statuses, landed instants and clock corrections equal the reference on the evidence probe")
def test_evidence_probe_settles(workspace):
    return _pass(workspace, _impl_test_evidence_probe_settles)


@criterion(description="summary.json status counts and the settlement's identity, rejects, commitments, evidence, landing, clock and mark files equal the reference for the shipped month")
def test_summary_and_settlement_records_match_shipped_month(workspace):
    return _pass(workspace, _impl_test_summary_and_settlement_records_match_shipped_month)


@criterion(description="summary.json penalties and the settlement's ledger, chargeback, tier, accountability, shift and freeze files equal the reference for the shipped month")
def test_summary_penalties_and_settlement_money_match_shipped_month(workspace):
    return _pass(workspace, _impl_test_summary_penalties_and_settlement_money_match_shipped_month)


@criterion(description="repair-report.json and the settlement's dependency, wait, unresolvable, blame, reconciliation and manifest files equal the reference for the shipped month")
def test_repair_report_and_settlement_lineage_match_shipped_month(workspace):
    return _pass(workspace, _impl_test_repair_report_and_settlement_lineage_match_shipped_month)


@criterion(description="module records name exactly the clauses the shipped engine departed from")
def test_module_records_name_every_repaired_clause(workspace):
    return _pass(workspace, _impl_test_module_records_name_every_repaired_clause)


@criterion(description="module records pair each clause with its departing function")
def test_module_records_name_every_repaired_function(workspace):
    return _pass(workspace, _impl_test_module_records_name_every_repaired_function)


@criterion(description="every repaired clause has a listed test passing on the repaired engine and failing with that defect restored")
def test_regression_tests_pin_every_repaired_clause(workspace):
    return _pass(workspace, _impl_test_regression_tests_pin_every_repaired_clause)


@criterion(description="two runs over one extract write different bytes")
def negative_settlement_differs_between_identical_runs(workspace):
    return _pass(workspace, _impl_negative_settlement_differs_between_identical_runs)


@criterion(description="the engine writes one ledger for two different extracts")
def negative_weight_hardcoded_sample_answers(workspace):
    return _pass(workspace, _impl_negative_weight_hardcoded_sample_answers)


@criterion(description="a shipped unit test fails against the delivered source")
def negative_repair_breaks_shipped_unit_tests(workspace):
    return _pass(workspace, _impl_negative_repair_breaks_shipped_unit_tests)


@criterion(description="a listed regression test is missing from the archive or fails against the repaired engine")
def negative_regression_record_lists_unsound_tests(workspace):
    return _pass(workspace, _impl_negative_regression_record_lists_unsound_tests)


@criterion(description="summary.json or a settlement file disagrees with the delivered engine's own run of the shipped month")
def negative_shipped_month_records_disagree_with_archive_engine(workspace):
    return _pass(workspace, _impl_negative_shipped_month_records_disagree_with_archive_engine)


@criterion(description="repair-report.json disagrees with the delivered engine's own run")
def negative_repair_report_disagrees_with_archive_engine(workspace):
    return _pass(workspace, _impl_negative_repair_report_disagrees_with_archive_engine)


@criterion(description="the archive carries compiled bytecode")
def negative_archive_ships_compiled_bytecode(workspace):
    return _pass(workspace, _impl_negative_archive_ships_compiled_bytecode)


@criterion(description="the archive drops a shipped module, class or function, or changes a shipped signature")
def negative_archive_drops_shipped_definition(workspace):
    return _pass(workspace, _impl_negative_archive_drops_shipped_definition)


@criterion(description="a function whose shipped body departs from the contract is delivered with that body unchanged")
def negative_departing_function_keeps_shipped_body(workspace):
    return _pass(workspace, _impl_negative_departing_function_keeps_shipped_body)


criteria.test_job_identity_matches_unseen_extracts(weight=1)
criteria.test_people_match_unseen_extracts(weight=1)
criteria.test_rejects_and_mark_decisions_match_unseen_extracts(weight=1)
criteria.test_state_audit_matches_unseen_extracts(weight=1)
criteria.test_commitments_and_wall_clock_match_unseen_extracts(weight=1)
criteria.test_dependency_resolution_and_upstream_waits_match_unseen_extracts(weight=1)
criteria.test_unresolvable_matches_unseen_extracts(weight=1)
criteria.test_interval_outputs_follow_canonical_order(weight=1)
criteria.test_evidence_and_partition_landings_match_unseen_extracts(weight=5)
criteria.test_ledger_statuses_match_unseen_extracts(weight=5)
criteria.test_ledger_penalties_match_unseen_extracts(weight=5)
criteria.test_blame_parents_match_unseen_extracts(weight=5)
criteria.test_blame_roots_match_unseen_extracts(weight=3)
criteria.test_accountability_and_oncall_shifts_match_unseen_extracts(weight=3)
criteria.test_chargeback_penalties_match_unseen_extracts(weight=5)
criteria.test_chargeback_counts_and_team_tiers_match_unseen_extracts(weight=3)
criteria.test_reconciliation_and_output_manifest_match_unseen_extracts(weight=3)
criteria.test_source_reading_probe_settles(weight=5)
criteria.test_schedule_probe_settles(weight=5)
criteria.test_evidence_probe_settles(weight=5)
criteria.test_summary_and_settlement_records_match_shipped_month(weight=5)
criteria.test_summary_penalties_and_settlement_money_match_shipped_month(weight=5)
criteria.test_repair_report_and_settlement_lineage_match_shipped_month(weight=5)
criteria.test_module_records_name_every_repaired_clause(weight=5)
criteria.test_module_records_name_every_repaired_function(weight=3)
criteria.test_regression_tests_pin_every_repaired_clause(weight=5)
criteria.negative_settlement_differs_between_identical_runs(weight=-3)
criteria.negative_weight_hardcoded_sample_answers(weight=-5)
criteria.negative_repair_breaks_shipped_unit_tests(weight=-3)
criteria.negative_regression_record_lists_unsound_tests(weight=-3)
criteria.negative_shipped_month_records_disagree_with_archive_engine(weight=-3)
criteria.negative_repair_report_disagrees_with_archive_engine(weight=-3)
criteria.negative_archive_ships_compiled_bytecode(weight=-1)
criteria.negative_archive_drops_shipped_definition(weight=-3)
criteria.negative_departing_function_keeps_shipped_body(weight=-3)
