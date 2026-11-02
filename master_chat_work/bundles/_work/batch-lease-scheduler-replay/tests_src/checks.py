

# ---------------------------------------------------------------------------
# Books the checks run on, and their expected documents.
# ---------------------------------------------------------------------------

PLANTED_CASES = (
    "expiry", "dead", "eviction", "preemption", "coinc3", "coinc_comp_exp", "coinc_x_ready",
    "victim_tie_start", "victim_tie_prio", "preempt2_expire", "token_at_deadline", "token_on_preempted",
    "cancel_running_resumed", "cancel_preempted_with_children", "stale_while_retry_runs",
    "resume_before_old_finish", "event_at_internal", "cascade_waiting", "cascade_unsubmitted",
    "cascade_depth4", "audit_redelivery", "audit_finished", "audit_stale_attempt", "audit_not_running",
    "event_submit", "event_heartbeat", "event_fail", "event_cancel", "event_boost", "event_worker_down",
    "event_worker_up", "redeliver_heartbeat", "redeliver_fail", "redeliver_cancel", "redeliver_boost",
    "redeliver_submit", "boost_unsubmitted")
HIDDEN_SETS = 3


def _expected(book: dict) -> dict:
    docs = documents(book)
    return {name: json.loads(json.dumps(doc)) for name, doc in zip(DOCUMENTS, docs)}


def _hidden(k: int) -> dict:
    """Hidden corpus k: a fresh generated book, its files, expected documents and the package run."""
    key = "hidden-%d" % k
    if key not in _CACHE:
        model = make_book(EVAL_SEED + 7919 * k, "hidden", HIDDEN_SETS)
        _assert_bounds(model)
        cases = Counter()
        for counts in case_counts(model).values():
            cases.update(counts)
        missing = [name for name in PLANTED_CASES if not cases[name]]
        assert not missing, "generator left cases unplanted: %s" % missing
        folder = _write_corpus(model, _scratch("book-") / "book", seed=CHALLENGE_SEED + k)
        book = _parse_book(folder)
        expected = _expected(book)
        outcomes = {edge["outcome"] for body in expected["dependency_resolution.json"]["sets"].values()
                    for edge in body["edges"]}
        assert outcomes == {"satisfied", "broken", "open"}, "edge outcomes not all planted"
        status, stdout, out = run_package(folder)
        _CACHE[key] = {"book": book, "folder": folder, "expected": expected,
                       "status": status, "stdout": stdout, "out": out}
    return _CACHE[key]


def _shipped_dir() -> Path:
    if "shipped" not in _CACHE:
        folder = _scratch("shipped-") / "data"
        folder.mkdir()
        for name, blob in _SHIPPED_DATA.items():
            (folder / name).write_bytes(zlib.decompress(base64.b64decode(blob)))
        _CACHE["shipped"] = folder
    return _CACHE["shipped"]


def _shipped() -> dict:
    if "shipped-book" not in _CACHE:
        book = _parse_book(_shipped_dir())
        _CACHE["shipped-book"] = {"book": book, "expected": _expected(book)}
    return _CACHE["shipped-book"]


def _small_book() -> dict:
    """A fresh two-set book in the shipped size range, as a model."""
    return make_book(CHALLENGE_SEED, "shipped", 2)


def _documents_of(out: Path) -> dict:
    return {name: read_json(out / name) for name in DOCUMENTS}


def _compare(got, want, label: str) -> None:
    where = first_diff(got, want)
    assert where is None, "%s differs first at %s" % (label, where)


def _hidden_document(k: int, name: str) -> None:
    run = _hidden(k)
    assert run["status"] == 0, "exit status %s on hidden book %d" % (run["status"], k)
    _compare(read_json(run["out"] / name), run["expected"][name], "hidden book %d %s" % (k, name))


def _shipped_document(name: str) -> None:
    _compare(read_json(OUT_ROOT / name), _shipped()["expected"][name], "/app/out/" + name)


# ---------------------------------------------------------------------------
# Positive checks.
# ---------------------------------------------------------------------------

def _check_rows_reshuffled() -> None:
    """POSITIVE: the hidden book 2 with other row order, blank event lines and a stray file."""
    base = _hidden(2)
    folder = _write_corpus(base["book"], _scratch("book-") / "book", seed=SAMPLE_SEED, blank_every=5)
    (folder / "notes.txt").write_text("set,job\n1,2\n", encoding="utf-8")
    status, _, out = run_package(folder)
    assert status == 0, "exit status %s" % status
    _compare(read_json(out / "module_core.json"), base["expected"]["module_core.json"], "reshuffled core")


def _check_policy_changed() -> None:
    """POSITIVE: 40 shipped sets replayed under another lease length and retry delay."""
    shipped = _shipped()["book"]
    draw = random.Random(SAMPLE_SEED)
    chosen = sorted(draw.sample(sorted(shipped["sets"]), 40))
    lease = draw.choice([n for n in range(2, 21) if n != shipped["lease"]])
    delay = draw.choice([n for n in range(1, 11) if n != shipped["delay"]])
    model = {"lease": lease, "delay": delay, "pools": shipped["pools"],
             "sets": {sid: shipped["sets"][sid] for sid in chosen}}
    folder = _write_corpus(model, _scratch("book-") / "book", seed=SAMPLE_SEED + 1)
    status, _, out = run_package(folder)
    assert status == 0, "exit status %s" % status
    _compare(read_json(out / "summary.json"), _expected(model)["summary.json"], "policy-changed summary")


def _check_run_twice() -> None:
    """POSITIVE: a relocated copy of hidden book 3 under another hash seed gives the same documents."""
    first = _hidden(3)
    assert first["status"] == 0, "exit status %s" % first["status"]
    moved = _scratch("again-") / "elsewhere"
    shutil.copytree(first["folder"], moved)
    status, _, out = run_package(moved, hashseed="4093")
    assert status == 0, "exit status %s on the second run" % status
    _compare(_documents_of(out), _documents_of(first["out"]), "second run")


def _check_worker_capacity() -> None:
    """POSITIVE: on hidden books 1 and 4 every checkpoint pairs workers and running jobs one to one."""
    for k in (1, 4):
        run = _hidden(k)
        assert run["status"] == 0, "exit status %s on hidden book %d" % (run["status"], k)
        core = read_json(run["out"] / "module_core.json")["sets"]
        for sid, body in run["book"]["sets"].items():
            for point in core[str(sid)]["checkpoints"]:
                where = "hidden book %d set %s t %s" % (k, sid, point["t"])
                running = {j: x["worker"] for j, x in point["jobs"].items() if x["state"] == "running"}
                held = {w: x["job"] for w, x in point["workers"].items() if x["job"] is not None}
                assert len(set(running.values())) == len(running), where + ": a worker runs two jobs"
                assert {str(w): int(j) for j, w in running.items()} == held, where + ": workers and jobs disagree"
                for w in held:
                    assert point["workers"][w]["up"], where + ": a down worker holds a job"
                    job = held[w]
                    assert body["workers"][int(w)][0] == body["jobs"][job][0], where + ": job outside its pool"


def _check_state_invariants() -> None:
    """POSITIVE: on hidden books 1 and 4 attempts, remaining work and terminal states stay in range."""
    for k in (1, 4):
        run = _hidden(k)
        assert run["status"] == 0, "exit status %s on hidden book %d" % (run["status"], k)
        core = read_json(run["out"] / "module_core.json")["sets"]
        metrics = read_json(run["out"] / "module_metrics.json")["sets"]
        for sid, body in run["book"]["sets"].items():
            final = {}
            for point in core[str(sid)]["checkpoints"]:
                for j, x in point["jobs"].items():
                    where = "hidden book %d set %s t %s job %s" % (k, sid, point["t"], j)
                    limit = body["jobs"][int(j)][2]
                    assert 1 <= x["attempt"] <= limit + 1, where + ": attempt out of range"
                    assert 0 <= x["remaining"] <= body["work"][int(j)], where + ": remaining out of range"
                    if x["state"] == "completed":
                        assert x["remaining"] == 0, where + ": completed job has work left"
                    if j in final:
                        assert x["state"] == final[j], where + ": a terminal job changed state"
                    if x["state"] in TERMINAL:
                        final[j] = x["state"]
            runs = Counter(str(row[1]) for row in core[str(sid)]["dispatches"])
            jobs = metrics[str(sid)]["jobs"]
            for j, counts in jobs.items():
                assert counts["runs"] == runs[j], "hidden book %d set %s job %s: runs vs dispatches" % (k, sid, j)
            for field, total in metrics[str(sid)]["totals"].items():
                if field != "audit":
                    assert total == sum(c[field] for c in jobs.values()), "set %s: totals.%s" % (sid, field)


def _refusal(book_dir: Path, line: str) -> None:
    status, stdout, out = run_package(book_dir)
    assert status == 2, "exit status %s, expected 2" % status
    assert stdout == line + "\n", "printed %r, expected %r" % (stdout[:120], line)
    written = [name for name in DOCUMENTS if (out / name).exists()]
    assert not written, "wrote %s while refusing" % written


def _free_id(taken) -> int:
    return max(taken) + 17


def _check_refuse_missing_input() -> None:
    """POSITIVE: two absent files and a bad policy; the first absent file in contract order is named."""
    model = _small_book()
    model["lease"] = 0
    folder = _write_corpus(model, _scratch("book-") / "book", seed=1)
    (folder / "events.jsonl").unlink()
    (folder / "durations.csv").unlink()
    _refusal(folder, "ERROR MISSING_INPUT durations.csv")


def _check_refuse_invalid_policy() -> None:
    """POSITIVE: a retry delay above its bound together with a duration row for an undefined job."""
    model = _small_book()
    model["delay"] = 11
    body = model["sets"][max(model["sets"])]
    body["work"][_free_id(body["jobs"])] = 4
    _refusal(_write_corpus(model, _scratch("book-") / "book", seed=2), "ERROR INVALID_POLICY")


def _conflict(body: dict) -> None:
    event = dict(body["events"][len(body["events"]) // 2])
    last = body["checkpoints"][-1]
    event["t"] = event["t"] + 1 if event["t"] < last else event["t"] - 1
    body["events"].append(event)


def _check_refuse_unknown_entity() -> None:
    """POSITIVE: an event names a worker the set lacks, alongside an event id conflict."""
    model = _small_book()
    body = model["sets"][max(model["sets"])]
    taken = [e["id"] for e in body["events"]]
    body["events"].append({"id": _free_id(taken), "t": 1, "type": "worker_up", "worker": _free_id(body["workers"])})
    _conflict(body)
    _refusal(_write_corpus(model, _scratch("book-") / "book", seed=3), "ERROR UNKNOWN_ENTITY")


def _cycle(body: dict) -> None:
    edges = {tuple(e) for e in body["deps"]}
    jobs = sorted(body["jobs"])
    for a, b, c in zip(jobs, jobs[1:], jobs[2:]):
        if not {(a, b), (b, c), (c, a)} & edges:
            body["deps"] += [[a, b], [b, c], [c, a]]
            return
    raise AssertionError("no room for a cycle")


def _check_refuse_event_conflict() -> None:
    """POSITIVE: one event id carries two different events, alongside a dependency cycle."""
    model = _small_book()
    body = model["sets"][max(model["sets"])]
    _conflict(body)
    _cycle(body)
    _refusal(_write_corpus(model, _scratch("book-") / "book", seed=4), "ERROR EVENT_ID_CONFLICT")


def _check_refuse_cycle() -> None:
    """POSITIVE: three dependency rows close a cycle."""
    model = _small_book()
    _cycle(model["sets"][min(model["sets"])])
    _refusal(_write_corpus(model, _scratch("book-") / "book", seed=5), "ERROR DEPENDENCY_CYCLE")


def _check_artifacts_present() -> None:
    """POSITIVE: the seven deliverables exist; the six JSON files parse."""
    for path in ARTIFACT_PATHS:
        _grant_read(path)
        assert path.is_file() and path.stat().st_size > 0, "missing or empty %s" % path
    assert zipfile.is_zipfile(ARCHIVE_PATH), "package.zip is no zip archive"
    for path in ARTIFACT_PATHS[1:]:
        read_json(path)


def _check_call_and_module_agree() -> None:
    """POSITIVE: leasebook.main and python -m leasebook write the same documents for one book."""
    folder = _write_corpus(_small_book(), _scratch("book-") / "book", seed=6)
    first_status, _, first = run_package(folder, mode="call")
    second_status, _, second = run_package(folder, mode="module")
    assert first_status == 0 and second_status == 0, "exit status %s / %s" % (first_status, second_status)
    _compare(_documents_of(second), _documents_of(first), "python -m output")


def _archive_version() -> tuple[str, str]:
    root = extract_archive()
    declared = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    probe = "import sys; sys.path.insert(0, sys.argv[1]); import leasebook; print(leasebook.__version__)"
    done = subprocess.run(_untrusted([sys.executable, "-I", "-c", probe, str(root / "src")]), cwd=_scratch("cwd-"),
                          capture_output=True, text=True, timeout=RUN_TIMEOUT)
    return declared, done.stdout.strip()


def _check_selftest_matches_rerun() -> None:
    """POSITIVE: selftest.json equals a fresh unittest run of the archived tests."""
    tree = _scratch("selftest-") / "tree"
    shutil.copytree(extract_archive(), tree)
    _open_tree(tree)
    for base, _, _ in os.walk(tree):
        os.chmod(base, 0o777)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(tree)}
    done = subprocess.run(_untrusted([sys.executable, "-m", "unittest", "discover", "-s", "tests"]), cwd=tree,
                          env=env, capture_output=True, text=True, timeout=RUN_TIMEOUT * 2)
    tail = [line for line in done.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    assert tail and tail[0].startswith("Ran "), "no unittest summary"
    ran = int(tail[0].split()[1])
    lost = 0
    for word in ("failures", "errors", "skipped"):
        marker = word + "="
        for line in tail[1:]:
            if marker in line:
                lost += int(line.split(marker, 1)[1].split(",")[0].split(")")[0])
    declared, _ = _archive_version()
    want = {"package": PACKAGE, "version": declared, "tests_run": ran, "tests_passed": ran - lost}
    _compare(read_json(SELFTEST_PATH), want, "selftest.json")


def _check_build_report() -> None:
    """POSITIVE: build_report.json lists the archive members and hash, and versions agree."""
    declared, imported = _archive_version()
    assert declared == imported, "pyproject version %r vs __version__ %r" % (declared, imported)
    want = {"package": PACKAGE, "version": declared, "files": sorted(archive_names()),
            "archive_sha256": hashlib.sha256(ARCHIVE_PATH.read_bytes()).hexdigest()}
    _compare(read_json(BUILD_REPORT_PATH), want, "build_report.json")


def _check_shipped_tests_kept() -> None:
    """POSITIVE: every test file of the shipped project.zip is in package.zip byte for byte."""
    shipped = zipfile.ZipFile(io.BytesIO((_shipped_dir() / "project.zip").read_bytes()))
    kept = [name for name in shipped.namelist() if name.startswith("tests/") and not name.endswith("/")]
    assert kept, "shipped project.zip has no tests"
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        names = set(archive.namelist())
        for name in kept:
            assert name in names, "package.zip lacks %s" % name
            assert archive.read(name) == shipped.read(name), "package.zip changed %s" % name


# ---------------------------------------------------------------------------
# Negative checks (assertion holds when the cheat is present).
# ---------------------------------------------------------------------------

def _check_negative_package_reads_grader_paths() -> None:
    """NEGATIVE: package source names the verifier's own directories."""
    text = source_text()
    marks = ['"/tests', "'/tests", '"/logs/', "'/logs/"]
    assert any(mark in text for mark in marks), "honest baseline: no grader path in package source"


def _check_negative_hardcoded_sample_answers() -> None:
    """NEGATIVE: the archive carries a finished document or a shipped dispatch hash."""
    members = {PurePosixPath(name).name for name in archive_names()}
    if members & set(DOCUMENTS):
        return
    text = source_text()
    hashes = [body["dispatch_sha256"][:16] for body in _shipped()["expected"]["summary.json"]["sets"].values()]
    assert any(h in text for h in hashes), "honest baseline: no stored answer in the archive"
