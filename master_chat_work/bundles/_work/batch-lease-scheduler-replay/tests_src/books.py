

# ---------------------------------------------------------------------------
# Book files: writing generated books and reading the embedded shipped book.
# ---------------------------------------------------------------------------

EVENT_KEYS = ("job", "attempt", "delta", "worker")
BOUNDS = {"sets": 500, "jobs": 160, "workers": 24, "events": 1200, "time": 5000,
          "work": (1, 60), "priority": (0, 9), "delta": (-3, 3), "limit": (0, 3),
          "ticks": (2, 20), "delay": (1, 10)}


def _write_corpus(book: dict, out: Path, seed: int = 0, blank_every: int = 0) -> Path:
    """Write a book model as the eight input files, rows shuffled within each set."""
    shuffle = random.Random(seed ^ 0x2F6B)
    out.mkdir(parents=True, exist_ok=True)
    (out / "policy.ini").write_text(
        "[lease]\nticks = %d\n\n[retry]\ndelay = %d\n" % (book["lease"], book["delay"]), encoding="utf-8")
    pools = [{"pool": name, "preempt": flag} for name, flag in book["pools"].items()]
    (out / "pools.json").write_text(json.dumps({"pools": pools}, indent=2) + "\n", encoding="utf-8")
    tables = {"workers.csv": [], "jobs.tsv": [], "durations.csv": [], "dependencies.csv": []}
    events, marks = [], []
    for sid, body in book["sets"].items():
        parts = {
            "workers.csv": [(sid, w, p, "up" if up else "down") for w, (p, up) in body["workers"].items()],
            "jobs.tsv": [(sid, j, p, pr, lim) for j, (p, pr, lim) in body["jobs"].items()],
            "durations.csv": [(sid, j, n) for j, n in body["work"].items()],
            "dependencies.csv": [(sid, p, c) for p, c in body["deps"]],
        }
        for name, rows in parts.items():
            shuffle.shuffle(rows)
            tables[name] += rows
        lines = list(body["events"])
        shuffle.shuffle(lines)
        lines.sort(key=lambda event: event["t"])
        for event in lines:
            record = {"set": sid, "id": event["id"], "t": event["t"], "type": event["type"]}
            record.update({key: event[key] for key in EVENT_KEYS if key in event})
            events.append(record)
        marks += [(sid, t) for t in body["checkpoints"]]
    headers = {"workers.csv": "set,worker,pool,state", "jobs.tsv": "set\tjob\tpool\tpriority\tretry_limit",
               "durations.csv": "set,job,work", "dependencies.csv": "set,parent,child"}
    for name, rows in tables.items():
        sep = "\t" if name.endswith(".tsv") else ","
        text = headers[name] + "\n" + "".join(sep.join(str(v) for v in row) + "\n" for row in rows)
        (out / name).write_text(text, encoding="utf-8")
    chunks = []
    for count, record in enumerate(events, 1):
        chunks.append(json.dumps(record) + "\n")
        if blank_every and count % blank_every == 0:
            chunks.append("\n")
    (out / "events.jsonl").write_text("".join(chunks), encoding="utf-8")
    (out / "checkpoints.txt").write_text("".join("%d %d\n" % mark for mark in marks), encoding="utf-8")
    return out


def _parse_book(folder: Path) -> dict:
    """Read a well-formed book directory into the in-memory book model."""
    section, policy = None, {}
    for line in (folder / "policy.ini").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.strip("[]").strip()
        elif "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            policy[(section, key)] = int(value)
    pools = {p["pool"]: p["preempt"] for p in json.loads((folder / "pools.json").read_text())["pools"]}
    sets: dict = {}
    for line in (folder / "checkpoints.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            sid, t = (int(x) for x in line.split())
            body = sets.setdefault(sid, {"workers": {}, "jobs": {}, "work": {}, "deps": [],
                                         "events": [], "checkpoints": []})
            body["checkpoints"].append(t)

    def table(name: str, sep: str):
        lines = [x for x in (folder / name).read_text(encoding="utf-8").splitlines() if x.strip()]
        head = lines[0].split(sep)
        return [dict(zip(head, x.split(sep))) for x in lines[1:]]

    for row in table("workers.csv", ","):
        sets[int(row["set"])]["workers"][int(row["worker"])] = [row["pool"], row["state"] == "up"]
    for row in table("jobs.tsv", "\t"):
        sets[int(row["set"])]["jobs"][int(row["job"])] = [row["pool"], int(row["priority"]), int(row["retry_limit"])]
    for row in table("durations.csv", ","):
        sets[int(row["set"])]["work"][int(row["job"])] = int(row["work"])
    for row in table("dependencies.csv", ","):
        sets[int(row["set"])]["deps"].append([int(row["parent"]), int(row["child"])])
    for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            event = json.loads(line)
            sets[event.pop("set")]["events"].append(event)
    for body in sets.values():
        body["checkpoints"].sort()
    return {"lease": policy[("lease", "ticks")], "delay": policy[("retry", "delay")], "pools": pools, "sets": sets}


def _assert_bounds(book: dict) -> None:
    """Every drawn value stays inside the bounds the contract states."""
    low, high = BOUNDS["ticks"]
    assert low <= book["lease"] <= high and BOUNDS["delay"][0] <= book["delay"] <= BOUNDS["delay"][1]
    assert 1 <= len(book["sets"]) <= BOUNDS["sets"]
    for body in book["sets"].values():
        assert len(body["jobs"]) <= BOUNDS["jobs"] and len(body["workers"]) <= BOUNDS["workers"]
        assert len(body["events"]) <= BOUNDS["events"] and body["checkpoints"]
        assert len(set(body["checkpoints"])) == len(body["checkpoints"])
        last = body["checkpoints"][-1]
        assert 0 <= body["checkpoints"][0] and last <= BOUNDS["time"]
        for pool, priority, limit in body["jobs"].values():
            assert pool in book["pools"]
            assert BOUNDS["priority"][0] <= priority <= BOUNDS["priority"][1]
            assert BOUNDS["limit"][0] <= limit <= BOUNDS["limit"][1]
        assert set(body["work"]) == set(body["jobs"])
        assert all(BOUNDS["work"][0] <= n <= BOUNDS["work"][1] for n in body["work"].values())
        submits = Counter()
        seen = {}
        for event in body["events"]:
            assert 0 <= event["t"] <= last
            if event["id"] in seen:
                assert seen[event["id"]] == event, "id reused with other content"
                continue
            seen[event["id"]] = event
            if event["type"] == "submit":
                submits[event["job"]] += 1
            if event["type"] == "boost":
                assert event["delta"] != 0 and BOUNDS["delta"][0] <= event["delta"] <= BOUNDS["delta"][1]
        assert max(submits.values(), default=1) == 1, "a job submitted twice"
        up = {w: flag for w, (_, flag) in body["workers"].items()}
        for event in sorted(seen.values(), key=lambda e: (e["t"], e["id"])):
            if event["type"] in ("worker_down", "worker_up"):
                assert up[event["worker"]] == (event["type"] == "worker_down"), "worker toggle out of state"
                up[event["worker"]] = event["type"] == "worker_up"
