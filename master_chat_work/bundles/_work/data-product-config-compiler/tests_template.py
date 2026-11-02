from __future__ import annotations

import base64
import os
import random
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

from rewardkit import criteria, criterion

HIDDEN_SEED = int("@@HIDDEN_SEED@@")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
TOOL_ARCHIVE = OUT_DIR / "tool.zip"
DOCUMENTS = ("config.json", "profile_dev.json", "profile_prod.json", "validation_report.json", "summary.json")
RUN_LIMIT_SEC = 600
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

# @@REF_CORE@@

# @@GEN_CORE@@

_SHIPPED_DATA: dict[str, str] = {
# @@SHIPPED_DATA@@
}
_CACHE: dict[str, object] = {}


def _shipped_files() -> dict[str, bytes]:
    """The agent's /app/data inputs, rebuilt here: the verifier container never has them."""
    if "shipped" not in _CACHE:
        _CACHE["shipped"] = {name: zlib.decompress(base64.b64decode(blob)) for name, blob in _SHIPPED_DATA.items()}
    return _CACHE["shipped"]


def _hidden_release() -> tuple[str, str, int]:
    rng = random.Random(HIDDEN_SEED)
    year = rng.choice((2027, 2028, 2029))
    month = rng.randint(1, 12)
    day = "%04d-%02d-%02d" % (year, month, rng.randint(1, 28))
    return day, "%04d.%02d-r%d" % (year, month, rng.randint(4, 9)), rng.randint(420, 520)


def _hidden_files() -> dict[str, bytes]:
    """A fresh release from the embedded seeded generator, at another scale and date than the shipped one."""
    if "hidden" not in _CACHE:
        day, release, size = _hidden_release()
        files = gen_corpus(HIDDEN_SEED, size, True, day, release, ref_compute)
        want = ref_dump(ref_compute(files)["config.json"])
        for variant in ({"owner_events": False}, {"canon_log": False}, {"lenient_json": True}, {"assign": "first"},
                        {"assign": "last"}, {"text": "lenient"}, {"cap": "restart"}):
            assert ref_dump(ref_compute(files, **variant)["config.json"]) != want, variant
        _CACHE["hidden"] = files
    return _CACHE["hidden"]


def _shifted_date() -> str:
    files = _hidden_files()
    day = gen_shifted(files)
    want = ref_dump(ref_compute(files, day)["config.json"])
    assert ref_dump(ref_compute(files, day, assign="latest_covering")["config.json"]) != want
    return day


def _rescaled_files() -> dict[str, bytes]:
    if "rescaled" not in _CACHE:
        _CACHE["rescaled"] = gen_rescaled(_hidden_files(), HIDDEN_SEED + 1)
    return _CACHE["rescaled"]


def _capped_files() -> dict[str, bytes]:
    if "capped" not in _CACHE:
        files = gen_capped(_hidden_files(), HIDDEN_SEED + 3, ref_compute)
        want = ref_compute(files)
        quota_docs = ("config.json", "profile_dev.json", "profile_prod.json")
        restart, single = ref_compute(files, cap="restart"), ref_compute(files, cap="single")
        assert all(want[name] != restart[name] for name in quota_docs)
        assert any(want[name] != single[name] for name in quota_docs)
        _CACHE["capped"] = files
    return _CACHE["capped"]


def _shuffled_files() -> dict[str, bytes]:
    if "shuffled" not in _CACHE:
        _CACHE["shuffled"] = gen_shuffled(_hidden_files(), HIDDEN_SEED + 2)
    return _CACHE["shuffled"]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _set_modes(path: Path, dir_mode: int, file_mode: int) -> None:
    for item in [path, *path.rglob("*")]:
        item.chmod(dir_mode if item.is_dir() else file_mode)


def _grant_read(program: Path) -> None:
    """Make the program and its folder readable by the other user before the uid drop."""
    program.chmod(program.stat().st_mode | 0o444)
    program.parent.chmod(program.parent.stat().st_mode | 0o555)


def _tool_root() -> Path:
    """The delivered archive, unpacked into a fresh folder the other user can read."""
    if "tool" not in _CACHE:
        assert TOOL_ARCHIVE.is_file(), "/app/out/tool.zip missing"
        root = Path(tempfile.mkdtemp(prefix="unpacked-"))
        with zipfile.ZipFile(TOOL_ARCHIVE) as archive:
            for member in archive.namelist():
                target = (root / member).resolve()
                assert str(target).startswith(str(root.resolve())), "unsafe path in tool.zip: %s" % member
            archive.extractall(root)
        _set_modes(root, 0o755, 0o644)
        root.chmod(0o755)
        if os.geteuid() == 0 and not root.parent.stat().st_mode & 0o001:
            root.parent.chmod((root.parent.stat().st_mode & 0o7777) | 0o111)
        _CACHE["tool"] = root
    return _CACHE["tool"]


def _run(files: dict[str, bytes], label: str, date: str | None = None, read_only: bool = False) -> dict[str, object]:
    """Copy the inputs into a freshly named folder and run the delivered tool from a foreign working directory."""
    work = Path(tempfile.mkdtemp(prefix="rerun-"))
    source = work / ("inputs-" + label)
    source.mkdir()
    for name, blob in files.items():
        (source / name).write_bytes(blob)
    target = work / ("compiled-" + label)
    cwd = work / "elsewhere"
    cwd.mkdir()
    _set_modes(work, 0o777, 0o666)
    if read_only:
        _set_modes(source, 0o555, 0o444)
    if date is None:
        date = ref_compute_manifest_date(files)
    program = _tool_root() / "cli.py"
    _grant_read(program)
    command = [sys.executable, "-B", "-E", "-s", str(program), "compile",
               "--data", str(source), "--date", date, "--out", str(target)]
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(_untrusted_command(command), cwd=str(cwd), env=env, capture_output=True, text=True,
                              timeout=RUN_LIMIT_SEC, check=False)
    except subprocess.TimeoutExpired:
        return {"returncode": None, "stderr": "timed out", "out": target}
    return {"returncode": proc.returncode, "stderr": proc.stderr, "out": target}


def ref_compute_manifest_date(files: dict[str, bytes]) -> str:
    import json as _json
    return _json.loads(files["release_manifest.json"])["compile_date"]


def _cached_run(key: str, files_fn, date_fn=None, read_only: bool = False) -> dict[str, object]:
    if "run-" + key not in _CACHE:
        _CACHE["run-" + key] = _run(files_fn(), key, None if date_fn is None else date_fn(), read_only)
    return _CACHE["run-" + key]


def _load(folder: Path, name: str):
    import json as _json
    if folder == OUT_DIR and name in DOCUMENTS:
        run = _cached_run("shipped", _shipped_files)
        assert run["returncode"] == 0, "tool failed on the shipped release: %s" % str(run["stderr"])[-400:]
        assert (run["out"] / name).read_bytes() == (OUT_DIR / name).read_bytes(), \
            "/app/out/%s is not what the delivered tool writes for the shipped release" % name
    return _json.loads((folder / name).read_text(encoding="utf-8"))


def _expected(key: str, files_fn, date_fn=None) -> dict[str, object]:
    if "expected-" + key not in _CACHE:
        _CACHE["expected-" + key] = ref_compute(files_fn(), None if date_fn is None else date_fn())
    return _CACHE["expected-" + key]


def _first_diff(want, got, path: str = "$"):
    """Path of the first difference; value types must match exactly (1 differs from 1.0, "1" and True)."""
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


_RUNS = {
    "hidden": (_hidden_files, None, False),
    "shifted": (_hidden_files, _shifted_date, False),
    "rescaled": (_rescaled_files, None, False),
    "shuffled": (_shuffled_files, None, False),
    "capped": (_capped_files, None, False),
    "readonly": (_hidden_files, None, True),
}


def _source(tier: str):
    """(expected documents, folder holding the documents) for the delivered shipped release or a rerun."""
    if tier == "visible":
        return _expected("shipped", _shipped_files), OUT_DIR
    key = "hidden" if tier == "hard" else tier
    files_fn, date_fn, read_only = _RUNS[key]
    run = _cached_run(key, files_fn, date_fn, read_only)
    assert run["returncode"] == 0, "tool failed on the %s release: %s" % (tier, str(run["stderr"])[-400:])
    return _expected(key, files_fn, date_fn), run["out"]


def _column(doc: dict, keys: tuple, nested: str | None = None) -> dict:
    """{product id: {key: value}} for every product row in a document; nested names a sub-object."""
    rows = doc.get("products") if isinstance(doc, dict) else None
    assert isinstance(rows, dict), "products is not an object"
    owned = {}
    for pid, row in rows.items():
        assert isinstance(row, dict), "%s row is not an object" % pid
        holder = row.get(nested) if nested else row
        if holder is None:
            owned[pid] = None
            continue
        assert isinstance(holder, dict), "%s %s is not an object" % (pid, nested)
        owned[pid] = {key: holder.get(key, "<absent>") for key in keys}
    return owned


def _header(doc: dict, keys: tuple) -> dict:
    assert isinstance(doc, dict), "document is not an object"
    return {key: doc.get(key, "<absent>") for key in keys}


_INT_KEYS = ("weight", "retention_days", "replicas", "partitions", "freshness_sla_min")
_OTHER_KEYS = ("pii_scan", "alerts_enabled", "encryption", "notify", "tags", "cost_center")
_DEPLOY_KEYS = ("alerts_enabled", "pii_scan", "replicas")


def _check_status_team(tier: str) -> None:
    want, folder = _source(tier)
    keys = ("status", "owner", "tier", "team")
    _same("config.json status, owner, tier and team", _column(want["config.json"], keys),
          _column(_load(folder, "config.json"), keys))


def _check_settings_int(tier: str) -> None:
    want, folder = _source(tier)
    _same("config.json integer settings", _column(want["config.json"], _INT_KEYS, "settings"),
          _column(_load(folder, "config.json"), _INT_KEYS, "settings"))


def _check_settings_other(tier: str) -> None:
    want, folder = _source(tier)
    _same("config.json boolean, enum, list and string settings", _column(want["config.json"], _OTHER_KEYS, "settings"),
          _column(_load(folder, "config.json"), _OTHER_KEYS, "settings"))


def _check_quota(tier: str, name: str) -> None:
    want, folder = _source(tier)
    got = _load(folder, name)
    keys = ("release", "compile_date", "cluster_quota") + (("env",) if name.startswith("profile") else ())
    _same(name + " header", _header(want[name], keys), _header(got, keys))
    _same(name + " quota", _column(want[name], ("quota",)), _column(got, ("quota",)))


def _check_deploy(tier: str, name: str) -> None:
    want, folder = _source(tier)
    _same(name + " deployment keys", _column(want[name], _DEPLOY_KEYS), _column(_load(folder, name), _DEPLOY_KEYS))


def _check_document(tier: str, name: str) -> None:
    want, folder = _source(tier)
    _same(name, want[name], _load(folder, name))


def _check_date_shift() -> None:
    want, folder = _source("shifted")
    got = _load(folder, "config.json")
    _same("config.json status and team at the later date", _column(want["config.json"], ("status", "team")),
          _column(got, ("status", "team")))


def _check_quota_rescale() -> None:
    want, folder = _source("rescaled")
    for name in ("config.json", "profile_dev.json", "profile_prod.json"):
        _same(name + " quota after rescale", _column(want[name], ("quota",)), _column(_load(folder, name), ("quota",)))


def _check_shuffled() -> None:
    want, folder = _source("shuffled")
    _same("config.json integer settings after row shuffle", _column(want["config.json"], _INT_KEYS, "settings"),
          _column(_load(folder, "config.json"), _INT_KEYS, "settings"))


def _check_read_only() -> None:
    want, folder = _source("readonly")
    _same("config.json from a read-only input folder", want["config.json"], _load(folder, "config.json"))


def _full_run_ok() -> None:
    run = _cached_run("hidden", _hidden_files)
    assert run["returncode"] == 0, "tool failed on the complete fresh release"
    assert (run["out"] / "config.json").is_file(), "complete fresh release wrote no config.json"


def _expect_error(run: dict, code: int, line: str) -> None:
    assert run["returncode"] == code, "exit status %r, expected %d" % (run["returncode"], code)
    lines = [text for text in str(run["stderr"]).splitlines() if text.strip()]
    assert line in lines, "stderr lacks the line %r" % line
    written = [name for name in DOCUMENTS if (run["out"] / name).exists()]
    assert not written, "documents written on error: %s" % written


def _check_missing_input() -> None:
    _full_run_ok()
    rng = random.Random(HIDDEN_SEED + 3)
    gone = sorted(rng.sample(REF_INPUTS, 2), key=REF_INPUTS.index)
    files = {k: v for k, v in _hidden_files().items() if k not in gone}
    _expect_error(_run(files, "missing"), 2, "error: missing input " + gone[0])


def _check_invalid_date() -> None:
    _full_run_ok()
    day = ref_compute_manifest_date(_hidden_files())
    bad = day[:5] + "02-30" if random.Random(HIDDEN_SEED + 4).random() < 0.5 else day[:5] + "13-0" + day[-1]
    _expect_error(_run(_hidden_files(), "baddate", date=bad), 2, "error: invalid date " + bad)


def _check_catalog_mismatch() -> None:
    import json as _json
    _full_run_ok()
    files = dict(_hidden_files())
    manifest = _json.loads(files["release_manifest.json"])
    catalog = manifest["catalog"]
    rng = random.Random(HIDDEN_SEED + 5)
    dropped = rng.sample(sorted(ref_canon(pid) for pid in catalog), 2)
    manifest["catalog"] = [pid for pid in catalog if ref_canon(pid) not in dropped]
    files["release_manifest.json"] = (_json.dumps(manifest, indent=2) + "\n").encode()
    _expect_error(_run(files, "mismatch"), 3, "error: catalog mismatch " + min(dropped))


def _check_determinism() -> None:
    first = _cached_run("hidden", _hidden_files)
    assert first["returncode"] == 0, "first run on the fresh release failed"
    second = _run(_hidden_files(), "again")
    assert second["returncode"] == 0, "second run on the fresh release failed"
    for name in DOCUMENTS:
        a = (first["out"] / name).read_bytes()
        b = (second["out"] / name).read_bytes()
        assert a, "%s is empty" % name
        assert a == b, "%s differs between two runs" % name


def _check_format() -> None:
    import json as _json
    run = _cached_run("hidden", _hidden_files)
    assert run["returncode"] == 0, "tool failed on the fresh release"
    for name in DOCUMENTS:
        raw = (run["out"] / name).read_bytes()
        want = (_json.dumps(_json.loads(raw), indent=2, sort_keys=True) + "\n").encode("utf-8")
        assert raw == want, "%s is not written with two-space indent, sorted keys and one final newline" % name


def _check_report() -> None:
    import hashlib
    import json as _json
    report = _load(OUT_DIR, "report.json")
    assert report.get("ok") is True and report.get("tool") == "dpcc", "report.json ok or tool wrong"
    documents = report.get("documents")
    assert isinstance(documents, dict) and sorted(documents) == sorted(DOCUMENTS), "report.json documents keys"
    for name in DOCUMENTS:
        digest = hashlib.sha256((OUT_DIR / name).read_bytes()).hexdigest()
        assert documents[name] == digest, "report.json sha256 of %s differs from the delivered file" % name
    assert _json.loads((OUT_DIR / "config.json").read_text())["release"] == _expected(
        "shipped", _shipped_files)["config.json"]["release"], "delivered config.json is for another release"


def _check_layout() -> None:
    with zipfile.ZipFile(TOOL_ARCHIVE) as archive:
        names = archive.namelist()
    assert "cli.py" in names, "tool.zip has no cli.py at its root"


def _check_restates_shipped() -> None:
    # Holds only when the tool, run on a fresh release, writes the shipped release name into config.json.
    shipped = _expected("shipped", _shipped_files)["config.json"]["release"]
    run = _cached_run("hidden", _hidden_files)
    got = _load(run["out"], "config.json")
    assert got.get("release") == shipped, "fresh-release config.json names its own release"


def _holds(check, *args) -> bool:
    try:
        check(*args)
    except Exception as exc:  # a check reports False with its reason; it never raises
        print("%s%r: %s" % (check.__name__, args, exc))
        return False
    return True

# @@CRITERIA@@
