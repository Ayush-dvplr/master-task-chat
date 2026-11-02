def check(cid: str, witness: str) -> None:
    print(f"check {cid} ok", flush=True)
    print(f"  {cid}: {witness}", flush=True)


def legacy_first() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "config.json"
        proc = subprocess.run([sys.executable, "-B", str(TOOL / "cli.py"), "resolve-config", "--data", str(DATA),
                               "--out", str(target)], capture_output=True, text=True, check=False)
        as_of = json.loads(target.read_text(encoding="utf-8")).get("as_of") if target.exists() else None
    check("r5", f"original warrant-ctl resolve-config on /app/data before any repair: rc={proc.returncode} as_of={as_of}")


def settled_from(stderr: str) -> dict:
    for line in stderr.splitlines():
        if line.startswith("warrant-ctl: gateway conventions "):
            return dict(part.split("=", 1) for part in line.split()[3:])
    raise SystemExit("compile did not report the gateway conventions it settled")


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _emp(ref: str) -> str | None:
    match = re.fullmatch(r"[Ee]?-?(\d{1,6})", ref.strip())
    return f"emp:{int(match.group(1)):06d}" if match else None


def recompute_outside(config: dict, delivered: dict) -> tuple[int, int, str]:
    """Grant keys recomputed from the raw rows with this function's own parsing only."""
    def rows(pattern):
        out = []
        for path in sorted(DATA.glob(pattern)):
            with path.open(encoding="utf-8") as fh:
                out += [json.loads(line) for line in fh if line.strip()]
        return out

    def table(name, delimiter=","):
        with (DATA / name).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter=delimiter))

    as_of, cutoff = _when(config["as_of"]), _when(config["recorded_cutoff"])
    need, hours = int(config["prod.approvals_required"]), int(config["prod.max_grant_hours"])
    aliases = {r["alias"].strip().lower() for r in table("directory_aliases.tsv", "\t")}
    accounts = defaultdict(list)
    for acc in rows("idp_accounts_*.jsonl"):
        accounts[acc["handle"].strip().lower()].append((acc["generation"], acc["subject_ref"]))

    def person(handle):
        handle = handle.strip().lower()
        found = sorted(accounts.get(handle, []), reverse=True)
        if handle in aliases or not found or (len(found) > 1 and found[0][0] == found[1][0]):
            return None
        return _emp(found[0][1])

    busy = set()
    for name in [p.name for p in sorted(DATA.glob("dir_members_site_*.csv"))]:
        busy |= {r["member"].strip().lower() for r in table(name)}
    for name in ("oncall_assignments.csv", "oncall_swaps.csv"):
        busy |= {v.strip().lower() for r in table(name) for v in r.values() if v}
    busy |= {r["subject"].strip().lower() for r in rows("revocations_secops.jsonl")}
    moving = set()
    for path in sorted(DATA.glob("hr_events_*.csv")):
        moving |= {_emp(r["employee_no"]) for r in table(path.name) if r["event"] in ("terminate", "leave_start")}
    touched = {r["ticket"] for r in rows("grant_corrections.jsonl")}
    touched |= {r["ticket"] for r in table("revocations_selfservice.csv")}
    requests = defaultdict(list)
    for req in rows("grant_requests_*.jsonl"):
        requests[req["ticket"]].append(req)
    per_person = defaultdict(int)
    for found in requests.values():
        for req in found:
            if req["env"] == "prod":
                per_person[req["beneficiary"].strip().lower()] += 1
    votes = defaultdict(list)
    for row in table("grant_approvals.csv"):
        votes[row["ticket"]].append(row)
    agree, total, witness = 0, 0, "no candidate grant"
    for ticket in sorted(requests):
        found = requests[ticket]
        if len(found) != 1 or ticket in touched:
            continue
        req = found[0]
        ben = req["beneficiary"].strip().lower()
        pid, req_pid = person(ben), person(req["requester"])
        if (req["env"] != "prod" or not req["target"].startswith("perm:") or not req.get("effective_from")
                or not req.get("effective_until") or pid is None or pid in moving or ben in busy
                or per_person[ben] != 1 or _when(req["recorded_at"]) > cutoff):
            continue
        ballots = votes.get(ticket, [])
        if any(v["decision"] != "approve" or _when(v["recorded_at"]) > cutoff for v in ballots):
            continue
        seen, decided = set(), []
        for vote in sorted(ballots, key=lambda v: (_when(v["decided_at"]), v["approval_id"])):
            who = person(vote["approver"])
            if who is None or who in (pid, req_pid) or who in seen or who in moving:
                continue
            seen.add(who)
            decided.append(_when(vote["decided_at"]))
        if len(decided) < need:
            continue
        start = max(_when(req["effective_from"]), decided[need - 1])
        end = min(_when(req["effective_until"]), start + timedelta(hours=hours))
        key = f"{pid}|{req['target'][5:]}"
        if not start <= as_of < end or key not in delivered:
            continue
        total += 1
        mine = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        agree += mine == delivered[key]
        if total == 1:
            witness = f"{ticket} {key}: recomputed {mine}, delivered {delivered[key]}"
    return agree, total, witness


def self_check(settled: dict) -> None:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(TOOL))
    import corpus as corpus_mod
    import engine
    import gateway
    import policy
    import wtime

    corpus = corpus_mod.Corpus(DATA)
    config, rejects, _ = policy.resolve(corpus)
    base = engine.Compiler(corpus, config, rejects, conventions=settled)
    observed = []
    for row in corpus.attestations:
        if row.get("observed_state") in ("in_effect", "not_in_effect") and row.get("env") in gateway.ENVS:
            try:
                at = wtime.parse_instant(row["reviewed_at"])
            except wtime.BadTime:
                continue
            observed.append((at, row["attestation_id"], row["subject"], row["permission"], row["env"],
                             row["observed_state"] == "in_effect"))
    observed.sort()

    def shown(at, subject, perm, env, reading):
        return gateway.agrees(gateway.gateway_at(corpus, at, reading), [(subject, perm, env, True)])

    def compare(cid, dim, other, picks, label):
        for at, aid, subject, perm, env, seen in observed:
            if picks(at, base.resolve(subject), perm, env):
                mine = shown(at, subject, perm, env, settled)
                alt = shown(at, subject, perm, env, {**settled, dim: other})
                check(cid, f"{aid} {label} at {wtime.fmt(at)} observed {'in_effect' if seen else 'not_in_effect'}; "
                           f"{dim}={settled[dim]} gives {mine}, {dim}={other} gives {alt}")
                return
        check(cid, f"no observation {label}")

    grants = defaultdict(list)
    for t in base.tickets.values():
        if t.get("state") == "approved":
            for perm in t["perms"]:
                grants[(t["ben"], perm, t["env"])].append(t)
    compare("r1", "window", "closed" if settled["window"] == "half" else "half",
            lambda at, pid, perm, env: any(at == t["end"] for t in grants.get((pid, perm, env), ())),
            "reviewed exactly at a computed grant end")

    def termination_day(at, pid, perm, env):
        for who, kind, day in base.hr_events.values():
            if who == pid and kind == "terminate":
                site, utc = base.zones.local_midnight(base.emp_site[pid], day), wtime._civil(*day)
                if site != utc and min(site, utc) <= at < max(site, utc):
                    return True
        return False
    compare("r2", "hr", "utc" if settled["hr"] != "utc" else "site", termination_day,
            "between UTC midnight and site midnight of a termination day")

    def before_approval(at, pid, perm, env):
        for t in grants.get((pid, perm, env), ()):
            frm = t["frm"] if t["frm"] is not None else t["rec"]
            if frm <= at < t["start"]:
                return True
        return False
    compare("r3", "start", "requested" if settled["start"] != "requested" else "decided", before_approval,
            "after effective_from and before the approval that completed the grant")

    witness = "no member reaches one group by two routes with different removal instants"
    for pid in sorted(base.user_edges):
        bounds, stack, steps = defaultdict(set), [(g, cap, (g,)) for g, cap in base.user_edges[pid]], 0
        while stack and steps < 5000:
            group, cap, path = stack.pop()
            steps += 1
            bounds[group].add(cap)
            for nxt, edge in base.group_edges.get(group, []):
                if nxt not in path:
                    stack.append((nxt, min(cap, edge), path + (nxt,)))
        group = next((g for g in sorted(bounds) if len(bounds[g]) > 1), None)
        if group is not None:
            got = base.reach(pid)[group]
            witness = (f"{pid} reaches {group} by routes ending {sorted(wtime.fmt(b) for b in bounds[group])}; "
                       f"compiler bound {wtime.fmt(got)} is the later one: {got == max(bounds[group])}")
            break
    check("r4", witness)

    prod = base.compile("prod")["profile"]
    witness = "no live prod grant waits for an approval"
    with tempfile.TemporaryDirectory() as tmp:
        copy_root = Path(tmp) / "data"
        shutil.copytree(DATA, copy_root)
        for t in sorted(base.tickets.values(), key=lambda t: str(t.get("src"))):
            if not (t.get("state") == "approved" and t["env"] == "prod" and t["start"] <= base.E < t["end"]):
                continue
            aid = next((a for d, a, _, _ in t["approvals"] if d == t["start"]), None)
            if aid is None:
                continue
            with (DATA / "grant_approvals.csv").open(encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                fields, table = reader.fieldnames, list(reader)
            for row in table:
                if row["approval_id"] == aid:
                    row["decided_at"] = wtime.fmt(base.E + 3600)
            with (copy_root / "grant_approvals.csv").open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(table)
            altered = corpus_mod.Corpus(copy_root)
            alt_config, alt_rejects, _ = policy.resolve(altered)
            other = engine.Compiler(altered, alt_config, alt_rejects, conventions=settled).compile("prod")["profile"]
            changed = sorted(k for k in set(prod) | set(other) if prod.get(k) != other.get(k))
            if changed:
                witness = (f"approval {aid} decided_at moved to {wtime.fmt(base.E + 3600)} on a copy: "
                           f"{len(changed)} prod entries differ, first {changed[0]}")
                break
    check("r6", witness)

    delivered = json.loads((OUT / "profile_prod.json").read_text(encoding="utf-8"))
    agree, total, witness = recompute_outside(json.loads((OUT / "config.json").read_text(encoding="utf-8")),
                                              delivered)
    check("r7", f"{agree} of {total} grant keys recomputed outside the compiler agree; {witness}")

    counts = {}
    for start in ("requested", "decided"):
        reading = {**settled, "start": start}
        fits = 0
        for at in sorted({o[0] for o in observed}):
            rows = [(s, p, e, seen) for a, _, s, p, e, seen in observed if a == at]
            if not gateway.agrees(gateway.gateway_at(corpus, at, reading), rows):
                break
            fits += 1
        counts[start] = fits == len({o[0] for o in observed})
    check("r8", f"start readings scored {len(counts)}, reproducing every observation "
                f"{sum(counts.values())}: {', '.join(k for k, v in counts.items() if v)}")
