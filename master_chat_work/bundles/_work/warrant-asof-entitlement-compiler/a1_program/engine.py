"""Bitemporal entitlement evaluation for one corpus at one as-of instant."""

from __future__ import annotations

import heapq
import json
from collections import defaultdict

import ident
import wtime
from wtime import INF

ACTIVE_EVENTS = {"hire", "rehire", "leave_end"}
ENDING_EVENTS = {"terminate", "leave_start"}
CLASSES = ("invisible", "rejected", "unresolved", "collapsed", "accepted")


class Ledger:
    def __init__(self) -> None:
        self.counts: dict[str, dict[str, int]] = defaultdict(lambda: {c: 0 for c in CLASSES})
        self.rejects: list[tuple[str, str, str]] = []
        self.unresolved: list[tuple[str, str, str]] = []

    def mark(self, src: str, cls: str, rid: str = "", reason: str = "") -> None:
        self.counts[src][cls] += 1
        if cls == "rejected":
            self.rejects.append((src, rid, reason))
        elif cls == "unresolved":
            self.unresolved.append((src, rid, reason))


class Compiler:
    def __init__(self, corpus, config: dict, journal_rejects=(), overrides: dict | None = None) -> None:
        self.c = corpus
        self.cfg = dict(config)
        if overrides:
            self.cfg.update(overrides)
        self.E = wtime.parse_instant(self.cfg["as_of"])
        self.R = wtime.parse_instant(self.cfg["recorded_cutoff"])
        self.zones = wtime.Zones(corpus.tz_rules)
        self.led = Ledger()
        self.journal_rejects = list(journal_rejects)
        self._reach_cache: dict[str, dict[str, int]] = {}
        self._roles()
        self._people()
        self._accounts()
        self._aliases()
        self._hr()
        self._mfa()
        self._directory()
        self._bindings()
        self._tickets()
        self._secops()
        self._oncall()
        self._attestations()

    # ---------------------------------------------------------------- helpers
    def visible(self, src: str, rid: str, raw, unit: str = "iso") -> bool:
        """True when the row is visible; marks invisible or bad_timestamp rows."""
        try:
            if unit == "iso":
                ok = wtime.parse_instant(raw) <= self.R
            elif unit == "s":
                ok = wtime.parse_epoch(raw) <= self.R
            else:
                ok = wtime.parse_epoch(raw, 1000) <= self.R * 1000
        except wtime.BadTime:
            self.led.mark(src, "rejected", rid, "bad_timestamp")
            return False
        if not ok:
            self.led.mark(src, "invisible")
        return ok

    def instant(self, raw):
        return wtime.parse_instant(raw)

    def resolve(self, value) -> str | None:
        """A handle field: its own winning account first, then a visible alias."""
        key = ident.norm_handle(value)
        if key in self.handle_owner:
            return self.handle_owner[key]
        target = self.alias.get(key)
        if target is not None:
            return self.handle_owner.get(target)
        return None

    def resolve_subject(self, ref) -> str | None:
        pid = ident.norm_subject(ref)
        if pid is not None:
            return pid if pid in self.universe else None
        return self.resolve(ref)

    def role_perms(self, role: str, env: str) -> frozenset[str]:
        hit = self._role_perm_cache.get((role, env))
        if hit is not None:
            return hit
        out: set[str] = set()
        stack, seen = [role], set()
        while stack:
            r = stack.pop()
            if r in seen:
                continue
            seen.add(r)
            spec = self.c.roles.get(r)
            if spec is None:
                continue
            for perm in spec.get("permissions", []):
                scope = self.c.permissions.get(perm, {}).get("scope")
                if scope == env or scope == "both":
                    out.add(perm)
            stack.extend(spec.get("includes", []))
        value = frozenset(out)
        self._role_perm_cache[(role, env)] = value
        return value

    # ---------------------------------------------------------------- loaders
    def _roles(self) -> None:
        self.role_index = {}
        self._role_perm_cache: dict[tuple[str, str], frozenset[str]] = {}
        for name, spec in self.c.roles.items():
            self.role_index[name.lower()] = name
            for legacy in spec.get("legacy_names", []):
                self.role_index[legacy.lower()] = name

    def _people(self) -> None:
        self.emp_site = {}
        for row in self.c.employees:
            pid = ident.norm_employee(row["employee_no"])
            self.emp_site[pid] = self.c.hr_sites[row["site"]]["tz"]
            self.led.mark(row["_src"], "accepted")
        by_ctr = defaultdict(list)
        for row in self.c.contracts:
            src = row["_src"]
            rid = f"{row['contractor_id']}#{row['amendment_no']}"
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                start = wtime.parse_date(row["start_date"])
                end = wtime.parse_date(row["end_date"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            if end < start:
                self.led.mark(src, "rejected", rid, "window_inverted")
                continue
            sponsor = ident.norm_employee(row["sponsor"])
            if sponsor not in self.emp_site:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            cid = ident.norm_contractor(row["contractor_id"])
            by_ctr[cid].append((int(row["amendment_no"]), self._payload(row), src, start, end,
                                sponsor, self.c.hr_sites[row["site"]]["tz"]))
        self.contract = {}
        for cid, rows in by_ctr.items():
            rows.sort(key=lambda item: item[:2])
            for extra in rows[:-1]:
                self.led.mark(extra[2], "collapsed")
            _, _, src, start, end, sponsor, tz = rows[-1]
            self.led.mark(src, "accepted")
            self.contract[cid] = (start, end, sponsor, tz)
        self.universe = set(self.emp_site) | set(self.contract)

    def _accounts(self) -> None:
        order = [s.strip() for s in self.cfg["idp_shard_priority"].split(",")]
        by_handle = defaultdict(list)
        for row in self.c.accounts:
            src = row["_src"]
            rid = f"{row.get('handle')}#{row.get('generation')}"
            if not self.visible(src, rid, row.get("synced_at")):
                continue
            shard = src.removeprefix("idp_accounts_").removesuffix(".jsonl")
            rank = order.index(shard) if shard in order else len(order)
            by_handle[ident.norm_handle(row["handle"])].append(
                (-int(row["generation"]), rank, json.dumps(row, sort_keys=True), src, rid, row))
        self.handle_owner: dict[str, str | None] = {}
        self.enabled: set[str] = set()
        for key, cands in by_handle.items():
            cands.sort(key=lambda item: item[:3])
            for loser in cands[1:]:
                self.led.mark(loser[3], "collapsed")
            _, _, _, src, rid, row = cands[0]
            pid = ident.norm_subject(row.get("subject_ref"))
            if pid not in self.universe:
                self.led.mark(src, "unresolved", rid, "orphan_account")
                self.handle_owner[key] = None
                continue
            self.led.mark(src, "accepted")
            self.handle_owner[key] = pid
            if row.get("state") == "enabled":
                self.enabled.add(pid)

    def _aliases(self) -> None:
        self.alias: dict[str, str] = {}
        for row in self.c.aliases:
            src, rid = row["_src"], row["alias"]
            if not self.visible(src, rid, row["created_at"]):
                continue
            key = ident.norm_handle(row["alias"])
            target = ident.norm_handle(row["handle"])
            if key in self.handle_owner:
                # the alias is itself a handle with a winning account: no effect
                self.led.mark(src, "accepted")
                continue
            if self.handle_owner.get(target) is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.alias[key] = target
            self.led.mark(src, "accepted")

    def _hr(self) -> None:
        events = {}
        for row in self.c.hr_events:
            src, rid = row["_src"], row["event_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                day = wtime.parse_date(row["effective_date"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            pid = ident.norm_employee(row["employee_no"])
            if pid not in self.emp_site:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.led.mark(src, "accepted")
            events[rid] = [pid, row["event"], day]
        governing = {}
        for row in self.c.hr_corrections:
            src, rid = row["_src"], row["correction_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            rec = self.instant(row["recorded_at"])
            day = None
            if row["action"] == "redate":
                try:
                    day = wtime.parse_date(row["new_effective_date"])
                except wtime.BadTime:
                    self.led.mark(src, "rejected", rid, "bad_timestamp")
                    continue
            if row["event_id"] not in events:
                self.led.mark(src, "accepted")
                continue
            governing.setdefault(row["event_id"], []).append((rec, rid, row["action"], day, src))
        for event_id, rows in governing.items():
            rows.sort(key=lambda item: (item[0], item[1]))
            for extra in rows[:-1]:
                self.led.mark(extra[4], "collapsed")
            _, _, action, day, src = rows[-1]
            self.led.mark(src, "accepted")
            if action == "void":
                events.pop(event_id)
            else:
                events[event_id][2] = day
        self.timeline = defaultdict(list)
        for event_id, (pid, kind, day) in events.items():
            at = self.zones.local_midnight(self.emp_site[pid], day)
            self.timeline[pid].append((at, event_id, kind))
        for rows in self.timeline.values():
            rows.sort()

    def emp_active(self, pid: str, t: int) -> bool:
        state = False
        for at, _, kind in self.timeline.get(pid, []):
            if at > t:
                break
            state = kind in ACTIVE_EVENTS
        return state

    def emp_until(self, pid: str, t: int) -> int:
        for at, _, kind in self.timeline.get(pid, []):
            if at > t and kind in ENDING_EVENTS:
                return at
        return INF

    def status(self, pid: str, t: int) -> tuple[bool, int]:
        if pid.startswith("emp:"):
            if not self.emp_active(pid, t):
                return False, 0
            return True, self.emp_until(pid, t)
        start, end, sponsor, tz = self.contract[pid]
        lo = self.zones.local_midnight(tz, start)
        hi = self.zones.local_midnight(tz, wtime.add_days(end, 1))
        if not (lo <= t < hi) or not self.emp_active(sponsor, t):
            return False, 0
        return True, min(hi, self.emp_until(sponsor, t))

    def _mfa(self) -> None:
        self.mfa_events = defaultdict(list)
        for row in self.c.mfa:
            src, rid = row["_src"], row["event_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                at = self.instant(row["at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            pid = self.resolve(row["handle"])
            if pid is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.led.mark(src, "accepted")
            self.mfa_events[pid].append((at, rid, row["action"]))
        for rows in self.mfa_events.values():
            rows.sort()

    def mfa_ok(self, pid: str, t: int) -> bool:
        last = None
        for item in self.mfa_events.get(pid, []):
            if item[0] > t:
                break
            last = item
        return last is not None and last[2] == "enroll"

    def _directory(self) -> None:
        members = {}
        for row in self.c.members:
            src, rid = row["_src"], row["mid"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                added = self.instant(row["added_at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            member = row["member"].strip()
            if row["group_id"] not in self.c.groups or (
                member.startswith("group:") and member[6:] not in self.c.groups
            ):
                self.led.mark(src, "rejected", rid, "unknown_target")
                continue
            if member.startswith("group:"):
                node = ("g", member[6:])
            else:
                pid = self.resolve(member)
                if pid is None:
                    self.led.mark(src, "unresolved", rid, "unknown_handle")
                    continue
                node = ("p", pid)
            self.led.mark(src, "accepted")
            members[rid] = [node, row["group_id"], added, INF]
        for row in self.c.removals:
            src, rid = row["_src"], row["removal_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                removed = self.instant(row["removed_at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            self.led.mark(src, "accepted")
            if row["mid"] in members:
                members[row["mid"]][3] = min(members[row["mid"]][3], removed)
        self.user_edges = defaultdict(list)
        self.group_edges = defaultdict(list)
        for node, group, added, removed in members.values():
            if added <= self.E < removed:
                (self.user_edges if node[0] == "p" else self.group_edges)[node[1]].append((group, removed))

    def reach(self, pid: str) -> dict[str, int]:
        """Groups the principal is in, each with its largest membership bound."""
        hit = self._reach_cache.get(pid)
        if hit is not None:
            return hit
        best: dict[str, int] = {}
        heap = [(-cap, g) for g, cap in self.user_edges.get(pid, [])]
        heapq.heapify(heap)
        while heap:
            neg, g = heapq.heappop(heap)
            if g in best:
                continue
            cap = -neg
            best[g] = cap
            for nxt, edge_cap in self.group_edges.get(g, []):
                if nxt not in best:
                    heapq.heappush(heap, (-min(cap, edge_cap), nxt))
        self._reach_cache[pid] = best
        return best

    def _bindings(self) -> None:
        self.bound = {}
        for env in ("dev", "prod"):
            table = defaultdict(list)
            for row in self.c.bindings[env]:
                src, rid = row["_src"], row["binding_id"]
                if not self.visible(src, rid, row["recorded_at"]):
                    continue
                try:
                    lo = self.instant(row["bound_from"])
                    hi = self.instant(row["bound_until"]) if row["bound_until"] else INF
                except wtime.BadTime:
                    self.led.mark(src, "rejected", rid, "bad_timestamp")
                    continue
                if hi <= lo:
                    self.led.mark(src, "rejected", rid, "window_inverted")
                    continue
                role = self.role_index.get(row["role"].strip().lower())
                if role is None or row["group_id"] not in self.c.groups:
                    self.led.mark(src, "rejected", rid, "unknown_target")
                    continue
                self.led.mark(src, "accepted")
                if lo <= self.E < hi:
                    table[row["group_id"]].append((role, hi))
            self.bound[env] = table

    def _target(self, target, env: str):
        if not isinstance(target, str) or ":" not in target:
            return None, "unknown_target"
        kind, name = target.split(":", 1)
        if kind == "role":
            role = self.role_index.get(name.strip().lower())
            if role is None:
                return None, "unknown_target"
            return self.role_perms(role, env), None
        if kind == "perm":
            spec = self.c.permissions.get(name)
            if spec is None:
                return None, "unknown_target"
            if spec["scope"] not in (env, "both"):
                return None, "out_of_scope"
            return {name}, None
        return None, "unknown_target"

    @staticmethod
    def _generation(row) -> int:
        gen = row.get("export_generation")
        return gen if isinstance(gen, int) and not isinstance(gen, bool) else -1

    @staticmethod
    def _payload(row) -> str:
        return json.dumps({k: v for k, v in row.items() if k != "_src"}, sort_keys=True)

    def _tickets(self) -> None:
        groups = defaultdict(list)
        for row in self.c.requests:
            src = row["_src"]
            rid = str(row.get("ticket"))
            if not self.visible(src, rid, row.get("recorded_at")):
                continue
            groups[rid].append(row)
        self.tickets = {}
        for rid in sorted(groups):
            rows = groups[rid]
            top_gen = max(self._generation(r) for r in rows)
            top = []
            for r in rows:
                if self._generation(r) == top_gen:
                    top.append(r)
                else:
                    self.led.mark(r["_src"], "collapsed")
            if len(top) > 1:
                payloads = {self._payload(r) for r in top}
                if len(payloads) > 1:
                    for r in top:
                        self.led.mark(r["_src"], "unresolved", rid, "conflicting_duplicate")
                    continue
                top.sort(key=lambda r: r["_src"])
                for r in top[1:]:
                    self.led.mark(r["_src"], "collapsed")
            row = top[0]
            src = row["_src"]
            if "effective_from" not in row or "effective_until" not in row:
                self.led.mark(src, "rejected", rid, "missing_field")
                continue
            try:
                frm = None if row["effective_from"] is None else self.instant(row["effective_from"])
                until = None if row["effective_until"] is None else self.instant(row["effective_until"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            if frm is not None and until is not None and until <= frm:
                self.led.mark(src, "rejected", rid, "window_inverted")
                continue
            perms, reason = self._target(row.get("target"), row["env"])
            if reason:
                self.led.mark(src, "rejected", rid, reason)
                continue
            ben = self.resolve(row.get("beneficiary"))
            req = self.resolve(row.get("requester"))
            if ben is None or req is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.tickets[rid] = {
                "src": src, "env": row["env"], "ben": ben, "req": req, "perms": perms,
                "frm": frm, "until": until, "rec": self.instant(row["recorded_at"]),
                "approvals": [], "correction": None, "revoked": INF,
            }

        for row in self.c.approvals:
            src, rid = row["_src"], row["approval_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                decided = self.instant(row["decided_at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            who = self.resolve(row["approver"])
            if who is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.led.mark(src, "accepted")
            t = self.tickets.get(row["ticket"])
            if t is not None:
                t["approvals"].append((decided, rid, who, row["decision"]))

        corr = defaultdict(list)
        for row in self.c.corrections:
            src = row["_src"]
            rid = f"{row.get('ticket')}#{row.get('revision')}"
            if not self.visible(src, rid, row.get("recorded_at"), unit="s"):
                continue
            if "effective_until" not in row:
                self.led.mark(src, "rejected", rid, "missing_field")
                continue
            try:
                until = None if row["effective_until"] is None else self.instant(row["effective_until"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            if row["ticket"] not in self.tickets:
                self.led.mark(src, "accepted")
                continue
            corr[row["ticket"]].append(
                (int(row["revision"]), wtime.parse_epoch(row["recorded_at"]),
                 self._payload(row), src, until))
        for ticket, rows in corr.items():
            rows.sort(key=lambda item: item[:3])
            for extra in rows[:-1]:
                self.led.mark(extra[3], "collapsed")
            self.led.mark(rows[-1][3], "accepted")
            self.tickets[ticket]["correction"] = ("set", rows[-1][4])

        for row in self.c.self_revocations:
            src, rid = row["_src"], row["rev_id"]
            if not self.visible(src, rid, row["recorded_at"], unit="ms"):
                continue
            try:
                at = self.instant(row["effective_at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            who = self.resolve(row["revoker"])
            if who is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            t = self.tickets.get(row["ticket"])
            if t is None:
                self.led.mark(src, "accepted")
                continue
            if who not in (t["ben"], t["req"]):
                self.led.mark(src, "rejected", rid, "revoker_not_party")
                continue
            self.led.mark(src, "accepted")
            t["revoked"] = min(t["revoked"], at)

        freeze = defaultdict(list)
        for w in self.c.freeze:
            freeze[w["env"]].append((self.instant(w["start"]), self.instant(w["end"])))
        self.held = []
        for rid in sorted(self.tickets):
            t = self.tickets[rid]
            env = t["env"]
            needed = int(self.cfg[f"{env}.approvals_required"])
            hours = int(self.cfg[f"{env}.max_grant_hours"])
            requested_until = t["correction"][1] if t["correction"] is not None else t["until"]
            requested_until = INF if requested_until is None else requested_until
            t["requested_until"] = requested_until
            qualifying = []
            for decided, aid, who, decision in sorted(t["approvals"]):
                if not who.startswith("emp:"):
                    continue
                if who == t["ben"] or who == t["req"]:
                    continue
                if not self.emp_active(who, decided):
                    continue
                qualifying.append((decided, aid, who, decision))
            vetoed = any(item[3] == "reject" for item in qualifying)
            seen, threshold = set(), None
            for decided, aid, who, decision in qualifying:
                if decision != "approve" or who in seen:
                    continue
                seen.add(who)
                if len(seen) == needed:
                    threshold = decided
            if vetoed:
                t["state"] = "vetoed"
            elif len(seen) < needed:
                t["state"] = "pending"
            else:
                t["state"] = "approved"
            if t["state"] != "approved":
                self.led.mark(t["src"], "accepted")
                if requested_until == INF or requested_until > self.E:
                    self.held.append((env, rid, t["state"]))
                continue
            requested_start = t["frm"] if t["frm"] is not None else t["rec"]
            start = requested_start if threshold is None else max(requested_start, threshold)
            t["requested_start"] = requested_start
            t["start"] = start
            t["end"] = min(requested_until, start + hours * 3600, t["revoked"])
            if self.cfg[f"{env}.freeze_applies"] and any(lo <= start < hi for lo, hi in freeze[env]):
                self.led.mark(t["src"], "rejected", rid, "freeze_window")
                t["state"] = "frozen"
                continue
            self.led.mark(t["src"], "accepted")

    def _secops(self) -> None:
        self.secops_caps = defaultdict(list)
        for row in self.c.secops:
            src, rid = row["_src"], row["case"]
            if not self.visible(src, rid, row.get("recorded_at")):
                continue
            try:
                at = self.instant(row["effective_at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            scope = row["scope"]
            if scope.startswith("perm:") and scope[5:] not in self.c.permissions:
                self.led.mark(src, "rejected", rid, "unknown_target")
                continue
            pid = self.resolve_subject(row["subject"])
            if pid is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.led.mark(src, "accepted")
            self.secops_caps[pid].append((scope, at))

    def secops_cap(self, pid: str, env: str, perm: str) -> int:
        cap = INF
        for scope, at in self.secops_caps.get(pid, []):
            if scope == "all" or scope == f"env:{env}" or scope == f"perm:{perm}":
                cap = min(cap, at)
        return cap

    def _oncall(self) -> None:
        assigned = defaultdict(list)
        for row in self.c.assignments:
            src, rid = row["_src"], row["assignment_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                week = wtime.parse_date(row["week_start"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            if row["rotation"] not in self.c.rotations:
                self.led.mark(src, "rejected", rid, "unknown_target")
                continue
            who = self.resolve(row["holder"])
            if who is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            assigned[(row["rotation"], week)].append(
                (int(row["revision"]), self.instant(row["recorded_at"]), src, rid, who))
        self.week_holder = {}
        for key, rows in assigned.items():
            rows.sort(key=lambda item: (item[0], item[1], item[3]))
            for extra in rows[:-1]:
                self.led.mark(extra[2], "collapsed")
            self.led.mark(rows[-1][2], "accepted")
            self.week_holder[key] = rows[-1][4]
        swaps = defaultdict(list)
        for row in self.c.swaps:
            src, rid = row["_src"], row["swap_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                day = wtime.parse_date(row["shift_date"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            if row["rotation"] not in self.c.rotations:
                self.led.mark(src, "rejected", rid, "unknown_target")
                continue
            a, b = self.resolve(row["from_holder"]), self.resolve(row["to_holder"])
            if a is None or b is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            swaps[(row["rotation"], day)].append((self.instant(row["recorded_at"]), rid, src, a, b))
        self.shift_holder = {}
        for key in sorted(swaps):
            holder = self.assigned_holder(*key)
            for _, rid, src, a, b in sorted(swaps[key]):
                if holder is not None and a == holder:
                    holder = b
                    self.led.mark(src, "accepted")
                else:
                    self.led.mark(src, "rejected", rid, "swap_mismatch")
            self.shift_holder[key] = holder

    def assigned_holder(self, rot: str, day) -> str | None:
        week = wtime.add_days(day, -wtime.weekday(day))
        return self.week_holder.get((rot, week))

    def holder(self, rot: str, day) -> str | None:
        if (rot, day) in self.shift_holder:
            return self.shift_holder[(rot, day)]
        return self.assigned_holder(rot, day)

    def shift_days(self, spec: dict, day) -> bool:
        if spec["cadence"] == "daily":
            return True
        return wtime.weekday(day) == int(spec["weekday"])

    def shift_window(self, spec: dict, day) -> tuple[int, int]:
        start = self.zones.local_wall(spec["tz"], day, spec["start"])
        return start, start + int(spec["duration_minutes"]) * 60

    def current_shift(self, spec: dict):
        """The shift of this rotation in effect at as_of, latest starting one."""
        today = wtime.local_date_of(self.zones, spec["tz"], self.E)
        span = int(spec["duration_minutes"]) * 60 // 86400 + 3
        hit = None
        for back in range(0, span):
            day = wtime.add_days(today, -back)
            if not self.shift_days(spec, day):
                continue
            s, e = self.shift_window(spec, day)
            if s <= self.E < e and (hit is None or s > hit[1]):
                hit = (day, s, e)
        return hit

    def oncall_bound(self, rot: str, spec: dict, day, end: int, who: str) -> int:
        """The shift end, carried through following shifts of the same holder."""
        bound = end
        step = 1 if spec["cadence"] == "daily" else 7
        cur = day
        for _ in range(520):
            cur = wtime.add_days(cur, step)
            if not self.shift_days(spec, cur):
                break
            s, e = self.shift_window(spec, cur)
            if s > bound or self.holder(rot, cur) != who:
                break
            bound = max(bound, e)
        return bound

    def on_call(self, env: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = defaultdict(dict)
        for rot, spec in sorted(self.c.rotations.items()):
            if spec["env"] != env:
                continue
            hit = self.current_shift(spec)
            if hit is None:
                continue
            day, _, end = hit
            who = self.holder(rot, day)
            if who is None:
                continue
            bound = self.oncall_bound(rot, spec, day, end, who)
            for perm in self.role_perms(spec["role"], env):
                out[who][perm] = max(out[who].get(perm, 0), bound)
        return out

    def _attestations(self) -> None:
        self.attest = defaultdict(list)
        for row in self.c.attestations:
            src, rid = row["_src"], row["attestation_id"]
            if not self.visible(src, rid, row["recorded_at"]):
                continue
            try:
                at = self.instant(row["reviewed_at"])
            except wtime.BadTime:
                self.led.mark(src, "rejected", rid, "bad_timestamp")
                continue
            if row["permission"] not in self.c.permissions:
                self.led.mark(src, "rejected", rid, "unknown_target")
                continue
            reviewer, subject = self.resolve(row["reviewer"]), self.resolve(row["subject"])
            if reviewer is None or subject is None:
                self.led.mark(src, "unresolved", rid, "unknown_handle")
                continue
            self.led.mark(src, "accepted")
            if reviewer == subject:
                continue
            self.attest[(subject, row["permission"], row["env"])].append((at, rid, row["decision"]))
        for rows in self.attest.values():
            rows.sort()

    def attested(self, pid: str, perm: str, env: str) -> bool:
        days = int(self.cfg["attestation_max_age_days"])
        last = None
        for item in self.attest.get((pid, perm, env), []):
            if item[0] > self.E:
                break
            last = item
        return last is not None and last[2] == "keep" and last[0] >= self.E - days * 86400

    # ---------------------------------------------------------------- compile
    def eligibility(self, env: str) -> dict[str, str]:
        out = {}
        need_mfa = bool(self.cfg[f"{env}.require_mfa"])
        for pid in sorted(self.universe):
            active, _ = self.status(pid, self.E)
            if not active:
                out[pid] = "inactive"
            elif pid not in self.enabled:
                out[pid] = "disabled"
            elif need_mfa and not self.mfa_ok(pid, self.E):
                out[pid] = "mfa_blocked"
            else:
                out[pid] = "eligible"
        return out

    def compile(self, env: str, only: set | None = None) -> dict:
        elig = self.eligibility(env)
        bg = self.on_call(env)
        elevated = defaultdict(lambda: defaultdict(list))
        active = 0
        for rid in sorted(self.tickets):
            t = self.tickets[rid]
            if t["env"] != env or t["state"] != "approved":
                continue
            if elig.get(t["ben"]) != "eligible":
                continue
            if t["start"] <= self.E < t["end"]:
                active += 1
                for perm in t["perms"]:
                    elevated[t["ben"]][perm].append((t["start"], t["end"], rid))
        attest_on = bool(self.cfg[f"{env}.attestation_required"])
        sod_on = bool(self.cfg[f"{env}.sod_enforced"])
        pairs = sorted((p for p in self.c.sod if p["env"] == env), key=lambda p: p["rule"])
        profile, unattested, sod_log = {}, [], []
        for pid in sorted(elig):
            if elig[pid] != "eligible":
                continue
            if only is not None and pid not in only:
                continue
            self.principal(pid, env, bg, elevated, attest_on, sod_on, pairs,
                           profile, unattested, sod_log)
        return {
            "profile": profile, "eligibility": elig, "unattested": unattested, "sod": sod_log,
            "active": active,
        }

    def principal(self, pid, env, bg, elevated, attest_on, sod_on, pairs,
                  profile, unattested, sod_log) -> None:
        _, p_until = self.status(pid, self.E)
        standing: dict[str, int] = {}
        for g, cap in self.reach(pid).items():
            for role, hi in self.bound[env].get(g, []):
                bound = min(cap, hi)
                for perm in self.role_perms(role, env):
                    if bound > standing.get(perm, 0):
                        standing[perm] = bound
        elev = {perm: list(v) for perm, v in elevated.get(pid, {}).items()}
        oncall = bg.get(pid, {})
        perms = set(standing) | set(elev) | set(oncall)
        if attest_on:
            for perm in sorted(perms):
                if not self.c.permissions[perm].get("critical"):
                    continue
                if (perm in standing or perm in elev) and not self.attested(pid, perm, env):
                    standing.pop(perm, None)
                    elev.pop(perm, None)
                    unattested.append((env, pid, perm))
        if sod_on:
            for pair in pairs:
                a, b = pair["a"], pair["b"]
                has_a = a in standing or a in elev
                has_b = b in standing or b in elev
                if not (has_a and has_b):
                    continue
                stand_a, stand_b = a in standing, b in standing
                if stand_a and stand_b:
                    sod_log.append((env, pid, pair["rule"], "standing_conflict", None))
                    continue
                if stand_a:
                    loser = b
                elif stand_b:
                    loser = a
                else:
                    start_a = min(x[0] for x in elev[a])
                    start_b = min(x[0] for x in elev[b])
                    if start_a != start_b:
                        loser = a if start_a > start_b else b
                    else:
                        loser = max(a, b)
                elev.pop(loser, None)
                sod_log.append((env, pid, pair["rule"], "suspended", loser))
        for perm in sorted(perms):
            comps = []
            if perm in standing:
                comps.append(standing[perm])
            if perm in elev:
                comps.append(max(x[1] for x in elev[perm]))
            if perm in oncall:
                comps.append(oncall[perm])
            if not comps:
                continue
            value = min(max(comps), p_until, self.secops_cap(pid, env, perm))
            if value <= self.E:
                continue
            profile[f"{pid}|{perm}"] = (value, perm in oncall)
