from __future__ import annotations

import base64
import os
import random
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from rewardkit import criteria, criterion

HIDDEN_SEED = int("@@HIDDEN_SEED@@")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
PROGRAM = OUT_DIR / "transform.py"
DOCUMENTS = [
    "normalized.jsonl", "summary.json", "data_quality.json", "product_summary.json",
    "region_central.json", "region_east.json", "region_north.json", "region_south.json",
    "region_west.json", "segment_consumer.json", "segment_corporate.json",
    "segment_enterprise.json", "segment_smb.json",
]
RUN_LIMIT_SEC = 15
# (collector rows, accounts, sub-resellers) of each long fresh month
LONG_SHAPES = ((13000, 76000, 11000), (14000, 80000, 11500), (15000, 84000, 12000))
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

# @@REF_CORE@@

# @@GEN_CORE@@

_SHIPPED_DATA: dict[str, str] = {
# @@SHIPPED_DATA@@
}
_CACHE: dict[str, object] = {}


def _shipped_files() -> dict[str, bytes]:
    """The agent's /app/data, rebuilt here: the verifier container never has it."""
    if "shipped" not in _CACHE:
        _CACHE["shipped"] = {name: zlib.decompress(base64.b64decode(blob)) for name, blob in _SHIPPED_DATA.items()}
    return _CACHE["shipped"]


def _hidden_month() -> str:
    rng = random.Random(HIDDEN_SEED)
    return "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))


def _hidden_files() -> dict[str, bytes]:
    """A fresh month from the embedded seeded generator, at a different scale from the shipped one."""
    if "hidden" not in _CACHE:
        _CACHE["hidden"] = gen_month(HIDDEN_SEED, _hidden_month(), 1600, 1200, True, ref_compute)
    return _CACHE["hidden"]


def _long_files(k: int) -> dict[str, bytes]:
    """Fresh month k from the same generator, longer, with one reseller over many sub-resellers."""
    key = "long-%d" % k
    if key not in _CACHE:
        seed = HIDDEN_SEED * 31 + k
        rng = random.Random(seed)
        month = "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))
        rows, accounts, resellers = LONG_SHAPES[k - 1]
        _CACHE[key] = gen_month(seed, month, rows, accounts, True, ref_compute, resellers=resellers)
    return _CACHE[key]


def _tier_scaled_files() -> dict[str, bytes]:
    """Hidden month with every tier threshold above zero scaled by 1.0375 (rounded up) and collector rows shuffled."""
    if "scaled" not in _CACHE:
        import json as _json
        files = dict(_hidden_files())
        card = _json.loads(files["rate_card.json"].decode("utf-8"), parse_float=_RD)
        text = files["rate_card.json"].decode("utf-8")
        for code in sorted(card["products"]):
            for tier in card["products"][code]["tiers"]:
                old = int(tier["from"])
                if old:
                    new = -(-old * 10375 // 10000)
                    text = text.replace('"from": %d,' % old, '"from": %d,' % new, 1)
        files["rate_card.json"] = text.encode("utf-8")
        rng = random.Random(HIDDEN_SEED + 1)
        for region, name in REF_FILES.items():
            raw = files[name].decode("latin-1")
            rows = raw.splitlines(keepends=True)
            head = rows[:1] if region in ("central", "east") else []
            body = rows[len(head):]
            rng.shuffle(body)
            files[name] = "".join(head + body).encode("latin-1")
        _CACHE["scaled"] = files
    return _CACHE["scaled"]


def _recommitted(files: dict[str, bytes], region: str, amount, minimum) -> dict[str, bytes]:
    """Copy of files with one region's pool element rewritten (None keeps that attribute)."""
    import re as _re
    text = files["commitments.xml"].decode("utf-8")
    pattern = r'<pool region="%s" amount="([0-9.]+)" minimum="([0-9.]+)"/>' % region
    found = _re.findall(pattern, text)
    assert len(found) == 1, region
    amount = found[0][0] if amount is None else amount
    minimum = found[0][1] if minimum is None else minimum
    text = _re.sub(pattern, '<pool region="%s" amount="%s" minimum="%s"/>' % (region, amount, minimum), text)
    out = dict(files)
    out["commitments.xml"] = text.encode("utf-8")
    return out


def _mutation_regions() -> tuple[str, str]:
    """(region given a 1.00 pool and a 1.00 shortfall, region given a pool 0.01 below its credit base)."""
    small, near = random.Random(HIDDEN_SEED + 4).sample(list(REF_REGIONS), 2)
    return small, near


def _small_commitment_files() -> dict[str, bytes]:
    if "small" not in _CACHE:
        region = _mutation_regions()[0]
        base = _RD(_expected("hidden", _hidden_files)["region_%s.json" % region]["credit_base"])
        _CACHE["small"] = _recommitted(_hidden_files(), region, "1.00", str(base + 1))
    return _CACHE["small"]


def _near_base_files() -> dict[str, bytes]:
    if "near" not in _CACHE:
        region = _mutation_regions()[1]
        base = _RD(_expected("hidden", _hidden_files)["region_%s.json" % region]["credit_base"])
        _CACHE["near"] = _recommitted(_hidden_files(), region, str(base - _RD("0.01")), None)
    return _CACHE["near"]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors can leave a file at mode 0600. The program is run as an
    unprivileged user, which then could not open it; the verifier runs as root,
    so widening the mode is allowed here and changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _open_tree(path: Path) -> None:
    for item in [path, *path.rglob("*")]:
        item.chmod(0o777 if item.is_dir() else 0o644)


def _run(files: dict[str, bytes], label: str) -> dict[str, object]:
    """Copy files into a freshly named directory and run the delivered program from a foreign cwd."""
    work = Path(tempfile.mkdtemp(prefix="rerun-"))
    source = work / ("extract-" + label)
    source.mkdir()
    for name, blob in files.items():
        (source / name).write_bytes(blob)
    target = work / ("reports-" + label)
    cwd = work / "elsewhere"
    cwd.mkdir()
    _open_tree(work)
    if not PROGRAM.is_file():
        return {"returncode": None, "stderr": "transform.py missing", "out": target}
    try:
        proc = subprocess.run(
            _untrusted_command([sys.executable, "-I", str(PROGRAM), "--input", str(source), "--output", str(target)]),
            cwd=str(cwd), capture_output=True, text=True, timeout=RUN_LIMIT_SEC, check=False)
    except subprocess.TimeoutExpired:
        return {"returncode": None, "stderr": "timed out", "out": target}
    return {"returncode": proc.returncode, "stderr": proc.stderr, "out": target}


def _cached_run(key: str, files_fn) -> dict[str, object]:
    if "run-" + key not in _CACHE:
        _CACHE["run-" + key] = _run(files_fn(), key)
    return _CACHE["run-" + key]


def _load(folder: Path, name: str):
    import json as _json
    path = folder / name
    text = path.read_text(encoding="utf-8")
    if name.endswith(".jsonl"):
        return [_json.loads(line) for line in text.splitlines() if line.strip()]
    return _json.loads(text)


def _expected(key: str, files_fn) -> dict[str, object]:
    if "expected-" + key not in _CACHE:
        _CACHE["expected-" + key] = ref_compute(files_fn())
    return _CACHE["expected-" + key]


def _first_diff(want, got, path: str = "$"):
    """Path of the first difference; value types must match exactly (1 differs from 1.0 and from True)."""
    if type(want) is not type(got):
        return "%s: expected %r, got %r" % (path, want, got)
    if isinstance(want, dict):
        for key in sorted(set(want) | set(got), key=str):
            if key not in got:
                return "%s.%s: missing" % (path, key)
            if key not in want:
                return "%s.%s: unexpected key" % (path, key)
            found = _first_diff(want[key], got[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(want, list):
        for index, (a, b) in enumerate(zip(want, got)):
            found = _first_diff(a, b, "%s[%d]" % (path, index))
            if found:
                return found
        if len(want) != len(got):
            return "%s: expected %d items, got %d" % (path, len(want), len(got))
        return None
    if want != got:
        return "%s: expected %r, got %r" % (path, want, got)
    return None


def _same(label: str, want, got) -> None:
    found = _first_diff(want, got)
    assert found is None, "%s differs at %s" % (label, found)


def _source(tier: str):
    """(expected documents, output folder) for the shipped month as delivered or for the hidden month."""
    if tier == "visible":
        return _expected("shipped", _shipped_files), OUT_DIR
    run = _cached_run("hidden", _hidden_files)
    assert run["returncode"] == 0, "program failed on a fresh month: %s" % str(run["stderr"])[-400:]
    return _expected("hidden", _hidden_files), run["out"]


def _rows_by_id(rows: list, region: str, keys: tuple) -> dict:
    owned = {}
    for row in rows:
        if isinstance(row, dict) and row.get("region") == region:
            owned[str(row.get("record_id"))] = {k: row.get(k) for k in keys}
    return owned


_LINE_KEYS = ("record_id", "region", "timestamp", "account_id", "product", "units")
_RATING_KEYS = ("segment", "tier", "unit_rate", "charge")
_CREDIT_KEYS = ("plan", "credit")
_TRUE_UP_KEYS = ("true_up",)


def _check_accepted_lines(tier: str) -> None:
    want, folder = _source(tier)
    got = [{k: row.get(k) for k in _LINE_KEYS} if isinstance(row, dict) else row
           for row in _load(folder, "normalized.jsonl")]
    _same("normalized.jsonl accepted lines", [{k: r[k] for k in _LINE_KEYS} for r in want["normalized.jsonl"]], got)


def _check_rating(tier: str, region: str) -> None:
    want, folder = _source(tier)
    _same("rating of %s lines" % region, _rows_by_id(want["normalized.jsonl"], region, _RATING_KEYS),
          _rows_by_id(_load(folder, "normalized.jsonl"), region, _RATING_KEYS))


def _check_credit(tier: str, region: str) -> None:
    want, folder = _source(tier)
    _same("credit of %s lines" % region, _rows_by_id(want["normalized.jsonl"], region, _CREDIT_KEYS),
          _rows_by_id(_load(folder, "normalized.jsonl"), region, _CREDIT_KEYS))


def _check_true_up(tier: str, region: str) -> None:
    want, folder = _source(tier)
    _same("true-up of %s lines" % region, _rows_by_id(want["normalized.jsonl"], region, _TRUE_UP_KEYS),
          _rows_by_id(_load(folder, "normalized.jsonl"), region, _TRUE_UP_KEYS))


def _check_document(tier: str, name: str) -> None:
    want, folder = _source(tier)
    _same(name, want[name], _load(folder, name))


def _check_tier_scale() -> None:
    run = _cached_run("scaled", _tier_scaled_files)
    assert run["returncode"] == 0, "program failed on the rescaled month: %s" % str(run["stderr"])[-400:]
    _same("product_summary.json after tier rescale", _expected("scaled", _tier_scaled_files)["product_summary.json"],
          _load(run["out"], "product_summary.json"))


def _check_small_commitment() -> None:
    region = _mutation_regions()[0]
    run = _cached_run("small", _small_commitment_files)
    assert run["returncode"] == 0, "program failed on the small-commitment month: %s" % str(run["stderr"])[-400:]
    name = "region_%s.json" % region
    _same(name + " with a 1.00 pool and a 1.00 shortfall", _expected("small", _small_commitment_files)[name],
          _load(run["out"], name))


def _check_near_base_pool() -> None:
    region = _mutation_regions()[1]
    run = _cached_run("near", _near_base_files)
    assert run["returncode"] == 0, "program failed on the near-base pool month: %s" % str(run["stderr"])[-400:]
    name = "region_%s.json" % region
    _same(name + " with its pool 0.01 below its credit base", _expected("near", _near_base_files)[name],
          _load(run["out"], name))


def _full_run_ok() -> None:
    run = _cached_run("hidden", _hidden_files)
    assert run["returncode"] == 0, "program failed on the complete fresh month"
    assert (run["out"] / "summary.json").is_file(), "complete fresh month wrote no summary.json"


def _check_long_finishes(k: int) -> None:
    run = _cached_run("long-%d" % k, lambda: _long_files(k))
    assert run["returncode"] is not None, "long fresh month %d: no result within %d seconds" % (k, RUN_LIMIT_SEC)
    assert run["returncode"] == 0, "long fresh month %d failed: %s" % (k, str(run["stderr"])[-400:])
    missing = [name for name in DOCUMENTS if not (run["out"] / name).is_file()]
    assert not missing, "long fresh month %d wrote no %s" % (k, ", ".join(missing))


def _check_long_document(k: int, name: str) -> None:
    run = _cached_run("long-%d" % k, lambda: _long_files(k))
    assert run["returncode"] == 0, "no documents for long fresh month %d within %d seconds" % (k, RUN_LIMIT_SEC)
    _same(name, _expected("long-%d" % k, lambda: _long_files(k))[name], _load(run["out"], name))


def _check_missing_collector() -> None:
    _full_run_ok()
    name = REF_FILES[random.Random(HIDDEN_SEED + 2).choice(REF_REGIONS)]
    files = {k: v for k, v in _hidden_files().items() if k != name}
    run = _run(files, "missing")
    assert run["returncode"] not in (0, None), "exit status %r with %s absent" % (run["returncode"], name)
    assert ("missing input: " + name) in str(run["stderr"]), "stderr lacks 'missing input: %s'" % name


def _check_control_mismatch() -> None:
    _full_run_ok()
    region = random.Random(HIDDEN_SEED + 3).choice(REF_REGIONS)
    name = REF_FILES[region]
    files = dict(_hidden_files())
    rows = files[name].decode("latin-1").splitlines(keepends=True)
    drop = 1 if region in ("central", "east") else 0
    files[name] = "".join(rows[:drop] + rows[drop + 1:]).encode("latin-1")
    run = _run(files, "short")
    assert run["returncode"] not in (0, None), "exit status %r with one record removed from %s" % (run["returncode"], name)
    assert ("control mismatch: " + name) in str(run["stderr"]), "stderr lacks 'control mismatch: %s'" % name


def _check_determinism() -> None:
    first = _cached_run("hidden", _hidden_files)
    assert first["returncode"] == 0, "first run on the fresh month failed"
    second = _run(_hidden_files(), "again")
    assert second["returncode"] == 0, "second run on the fresh month failed"
    for name in DOCUMENTS:
        a = (first["out"] / name).read_bytes()
        b = (second["out"] / name).read_bytes()
        assert a, "%s is empty" % name
        assert a == b, "%s differs between two runs at byte %d" % (name, next(
            (i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b))))


def _check_restates_shipped() -> None:
    # Holds only when the program, run on a fresh month, writes the shipped month's own figures.
    shipped = _expected("shipped", _shipped_files)["summary.json"]
    fresh = _expected("hidden", _hidden_files)["summary.json"]
    run = _cached_run("hidden", _hidden_files)
    got = _load(run["out"], "summary.json")
    restated = [key for key in ("month", "charge", "credit", "net")
                if got.get(key) == shipped[key] and fresh[key] != shipped[key]]
    assert restated, "fresh-month summary.json restates no shipped figure"


def _check_program_exists() -> None:
    assert PROGRAM.is_file() and PROGRAM.stat().st_size > 0, "transform.py missing or empty"


def _holds(check, *args) -> bool:
    try:
        check(*args)
    except Exception as exc:  # a check reports False with its reason; it never raises
        print("%s%r: %s" % (check.__name__, args, exc))
        return False
    return True


# @@CRITERIA@@
