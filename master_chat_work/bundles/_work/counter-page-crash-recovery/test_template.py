"""Checks for the repaired pagerecover package and the recovery documents it writes.

The package is taken from /app/out/package.zip, unpacked into a scratch directory and run
as an unprivileged user from a foreign working directory on books generated here.
"""
import ast
import base64
import copy
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile
import zlib
from pathlib import Path

from rewardkit import criteria, criterion

BOOK_SEED = int("5113927")
SHIPPED_SEED = int("806610")
PACKAGE = "pagerecover"
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
ARCHIVE = OUT_DIR / "package.zip"
DOCUMENTS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")
BOOK_FILES = ("journal.jsonl", "disk_pages.bin", "page_map.ini", "checkpoint.toml",
              "txn_catalog.csv", "audit_queries.json")
CATEGORIES = {"packaging", "dependency", "decoding", "config", "validation", "recovery", "reporting", "cli"}
RUN_TIMEOUT = 300
TIME_LIMIT = 60.0
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUNNER = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); sys.argv = [sys.argv[2]] + sys.argv[3:]; "
           "runpy.run_module(sys.argv[0], run_name='__main__', alter_sys=True)")
_VERSION_PROBE = "import sys; sys.path.insert(0, sys.argv[1]); import pagerecover; print(pagerecover.__version__)"
SHIPPED_DATA_LINE
_CACHE = {}


# ---------------------------------------------------------------- book generator (same one that wrote /app/data)

BOOKGEN_BODY_LINE


# ---------------------------------------------------------------- sandbox helpers

def _memo(key, build):
    if key not in _CACHE:
        try:
            _CACHE[key] = (True, build())
        except Exception as exc:  # cached so every dependent check reports the same cause
            _CACHE[key] = (False, exc)
    ok, value = _CACHE[key]
    if not ok:
        raise value
    return value


def _scratch(prefix):
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o777)
    return path


def _open_tree(root):
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o777)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o644)


def _shipped_file(name):
    return zlib.decompress(base64.b64decode("".join(_SHIPPED_DATA[name])))


def _shipped_json(name):
    return json.loads(_shipped_file(name).decode("utf-8"))


def _root_only_tests_present():
    try:
        info = os.stat("/tests")
    except OSError:
        return False
    return info.st_uid == 0 and stat.S_IMODE(info.st_mode) & 0o077 == 0


def _grant_read(argument):
    """Agent editors can leave 0600 files; the unprivileged run needs to read what the agent built."""
    path = Path(str(argument))
    try:
        if not path.is_absolute() or APP_ROOT not in (path, *path.parents) or not path.exists():
            return
        for parent in [path, *path.parents]:
            mode = parent.stat().st_mode
            extra = stat.S_IROTH | (stat.S_IXOTH if stat.S_ISDIR(mode) else 0)
            parent.chmod(stat.S_IMODE(mode) | extra)
            if parent == APP_ROOT:
                break
    except OSError:
        pass


def _untrusted_command(command):
    if os.name != "posix":
        raise RuntimeError("checks need a POSIX host")
    if os.geteuid() != 0:
        if _root_only_tests_present():
            raise RuntimeError("checks must start as root to drop privileges")
        return list(command)
    for argument in command:
        _grant_read(argument)
    return _SETPRIV + list(command)


def _env(home):
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home), "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}


def _run(command, cwd, timeout=RUN_TIMEOUT, extra_env=None):
    env = _env(cwd)
    env.update(extra_env or {})
    started = time.monotonic()
    try:
        done = subprocess.run(_untrusted_command(command), text=True, capture_output=True, env=env,
                              cwd=str(cwd), timeout=timeout)
    except subprocess.TimeoutExpired:
        done = subprocess.CompletedProcess(command, -9, "", "timed out after %d s" % timeout)
    return done, time.monotonic() - started


def _artifact(name):
    path = OUT_DIR / name
    _grant_read(path)
    return path


def _json_artifact(name):
    path = _artifact(name)
    assert path.is_file(), "%s is missing" % path
    return json.loads(path.read_text(encoding="utf-8"))


def _archive_members():
    def build():
        path = _artifact("package.zip")
        assert path.is_file(), "%s is missing" % path
        with zipfile.ZipFile(path) as zf:
            return [(info, zf.read(info)) for info in zf.infolist()]
    return _memo("members", build)


def _extract_archive():
    def build():
        root = _scratch("package-") / "pkg"
        root.mkdir()
        for info, data in _archive_members():
            name = info.filename
            assert not name.startswith("/") and ".." not in name.split("/"), "unsafe member %s" % name
            assert "\\" not in name and "\x00" not in name, "unsafe member %s" % name
            if name.endswith("/"):
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        _open_tree(root.parent)
        assert (root / "src" / PACKAGE / "__init__.py").is_file(), "archive has no src/%s/__init__.py" % PACKAGE
        return root
    return _memo("extract", build)


def _shipped_project():
    def build():
        with zipfile.ZipFile(io.BytesIO(_shipped_file("project.zip"))) as zf:
            return {name[len("project/"):]: zf.read(name) for name in zf.namelist() if name.startswith("project/")}
    return _memo("project", build)


# ---------------------------------------------------------------- books

def _scaled(book, factor):
    scaled = copy.deepcopy(book)
    for img in scaled["images"]:
        for d in img["disk"].values():
            d["slots"] = [v * factor for v in d["slots"]]
        for r in img["records"]:
            for ch in r.get("changes", ()):
                ch["delta"] *= factor
    return scaled


def _rejection_book():
    book = build_book(BOOK_SEED + 3, "restart", 11, dense=True, min_restarts=2)
    plan = [("E_BAD_IMAGE",), ("E_BAD_IMAGE",), ("E_UNKNOWN_PAGE",), ("E_DUP_LSN",), ("E_BAD_CHAIN",),
            ("E_BAD_IMAGE", "E_BAD_CHAIN"), ("E_UNKNOWN_PAGE", "E_DUP_LSN"), ("E_DUP_LSN", "E_BAD_CHAIN"),
            ("E_BAD_CHAIN/undo_next",)]
    rng = Rng(BOOK_SEED ^ 0x4E7)
    for img, codes in zip(book["images"], plan):
        pristine = copy.deepcopy(img)
        while True:
            for code in reversed(codes):
                plant_defect(rng, img, code)
            if validate(img) == codes[0].split("/")[0]:
                break
            img.clear()
            img.update(copy.deepcopy(pristine))
    return book


def _book(name):
    def build():
        if name == "shipped":
            book = shipped_book(SHIPPED_SEED)
            files = render_book(book, Rng(SHIPPED_SEED ^ 0xF11E))
            for fname, data in files.items():
                assert hashlib.sha256(data).hexdigest() == _SHIPPED_SHA[fname], "generator drift on %s" % fname
            return book
        if name == "dense":
            book = build_book(BOOK_SEED, "dense", 12, dense=True, min_restarts=2)
        elif name == "restart":
            book = build_book(BOOK_SEED + 1, "restart", 12, dense=True, min_restarts=2)
        elif name == "max":
            book = build_book(BOOK_SEED + 2, "max", 12, dense=True, min_restarts=2)
        elif name == "rejection":
            book = _rejection_book()
        elif name == "relocated":
            book = build_book(BOOK_SEED + 4, "dense", 8, dense=True, min_restarts=2)
        elif name == "scaled":
            book = _scaled(_book("dense"), 3)
        elif name == "missing":
            book = build_book(BOOK_SEED + 5, "light", 3, light=True)
        else:
            raise KeyError(name)
        assert len(book["images"]) <= 40 and all(_fits(img) for img in book["images"]), "book outside limits"
        return book
    return _memo(("book", name), build)


def _book_dir(name):
    def build():
        base = _scratch("book-")
        where = base / ("relocated book" if name == "relocated" else "book") / "inputs"
        where.mkdir(parents=True)
        files = render_book(_book(name), Rng(BOOK_SEED * 7 + len(name)))
        for fname, data in files.items():
            (where / fname).write_bytes(data)
        if name == "missing":
            (where / Rng(BOOK_SEED).choice(sorted(BOOK_FILES))).unlink()
        _open_tree(base)
        return where
    return _memo(("dir", name), build)


def _expected(name):
    return _memo(("expected", name), lambda: documents(_book(name)))


def _run_package(name, attempt=1):
    def build():
        root = _extract_archive()
        base = _scratch("run-")
        out = base / "out dir"
        cwd = base / "elsewhere"
        cwd.mkdir()
        _open_tree(base)
        done, elapsed = _run([sys.executable, "-I", "-B", "-c", _RUNNER, str(root / "src"), PACKAGE, "recover",
                              "--data", str(_book_dir(name)), "--out", str(out)], cwd)
        return done, elapsed, out
    return _memo(("run", name, attempt), build)


def _delivered(name, attempt=1):
    def build():
        done, _elapsed, out = _run_package(name, attempt)
        assert done.returncode == 0, "package exited %s on the %s book: %s" % (
            done.returncode, name, done.stderr.strip()[-600:])
        docs = {}
        for doc in DOCUMENTS:
            path = out / doc
            assert path.is_file(), "package wrote no %s for the %s book" % (doc, name)
            docs[doc] = json.loads(path.read_text(encoding="utf-8"))
        return docs
    return _memo(("delivered", name, attempt), build)


def _first_difference(want, got, path="$"):
    if isinstance(want, dict) and isinstance(got, dict):
        for key in sorted(set(want) | set(got), key=str):
            if key not in got:
                return "%s.%s missing" % (path, key)
            if key not in want:
                return "%s.%s unexpected" % (path, key)
            found = _first_difference(want[key], got[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(want, list) and isinstance(got, list):
        for index, (a, b) in enumerate(zip(want, got)):
            found = _first_difference(a, b, "%s[%d]" % (path, index))
            if found:
                return found
        if len(want) != len(got):
            return "%s: length %d != %d" % (path, len(got), len(want))
        return None
    if type(want) is not type(got) or want != got:
        return "%s: %r != %r" % (path, got, want)
    return None


def _same(label, want, got):
    found = _first_difference(want, got)
    assert found is None, "%s differs first at %s" % (label, found)


# ---------------------------------------------------------------- checks

def _check_artifacts():
    for name in ("package.zip", "selftest.json", "build_report.json") + DOCUMENTS:
        path = _artifact(name)
        assert path.is_file() and path.stat().st_size > 0, "%s is missing or empty" % path
        if name.endswith(".json"):
            json.loads(path.read_text(encoding="utf-8"))


def _check_archive_layout():
    targets = _shipped_json("expected_targets.json")
    flags = _shipped_json("compiler_flags.json")
    stamp = tuple(int(x) for x in re.split(r"[-T:]", flags["deterministic_zip_timestamps"]))
    method = {"stored": zipfile.ZIP_STORED, "deflated": zipfile.ZIP_DEFLATED}[flags["zip_compression"]]
    names = []
    for info, _data in _archive_members():
        if info.filename.endswith("/"):
            continue
        names.append(info.filename)
        assert info.compress_type == method, "%s uses compression %d" % (info.filename, info.compress_type)
        assert info.date_time == stamp, "%s has timestamp %s" % (info.filename, info.date_time)
    assert len(names) == len(set(names)), "archive repeats a member"
    missing = sorted(set(targets["archive_members"]) - set(names))
    assert not missing, "archive lacks %s" % missing
    extra = sorted(n for n in set(names) - set(targets["archive_members"])
                   if not re.fullmatch(r"src/pagerecover/[A-Za-z0-9_]+\.py", n))
    assert not extra, "archive holds unexpected members %s" % extra


def _check_package_metadata():
    root = _extract_archive()
    wanted = _shipped_json("dependency_manifest.json")["required_version"]
    meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = meta.get("project", {})
    assert project.get("name") == PACKAGE, "pyproject names %r" % project.get("name")
    assert project.get("version") == wanted, "pyproject version %r != %r" % (project.get("version"), wanted)
    assert project.get("requires-python") in (">=3.12", ">=3.12.0"), "requires-python %r" % project.get(
        "requires-python")
    assert not project.get("dependencies"), "runtime dependencies %r" % project.get("dependencies")
    package_dir = meta.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    assert package_dir.get("") == "src", "package-dir %r" % package_dir
    cwd = _scratch("probe-")
    done, _ = _run([sys.executable, "-I", "-B", "-c", _VERSION_PROBE, str(root / "src")], cwd, timeout=60)
    assert done.returncode == 0, "importing the archived package failed: %s" % done.stderr.strip()[-400:]
    assert done.stdout.strip() == wanted, "__version__ %r != %r" % (done.stdout.strip(), wanted)


def _changed_modules():
    shipped = _shipped_project()
    changed = []
    for info, data in _archive_members():
        name = info.filename
        if name.startswith("src/pagerecover/") and not name.endswith("/") and name.count("/") == 2:
            if shipped.get(name) != data:
                changed.append(name.rsplit("/", 1)[1])
    return sorted(changed)


def _check_build_report():
    report = _json_artifact("build_report.json")
    wanted = _shipped_json("dependency_manifest.json")["required_version"]
    assert report.get("ok") is True, "build_report ok is %r" % report.get("ok")
    assert report.get("package") == PACKAGE and report.get("version") == wanted, "build_report names %r %r" % (
        report.get("package"), report.get("version"))
    assert report.get("layout") == "src" and report.get("python") == "3.12", "build_report layout/python wrong"
    assert report.get("fixed_modules") == _changed_modules(), "fixed_modules %r != %r" % (
        report.get("fixed_modules"), _changed_modules())
    cats = report.get("fix_categories")
    assert isinstance(cats, list) and cats and cats == sorted(set(cats)) and set(cats) <= CATEGORIES, (
        "fix_categories %r" % cats)


def _ci_commands():
    commands, inside = [], False
    for line in _shipped_file("ci_config.yaml").decode("utf-8").splitlines():
        if line.startswith("commands:"):
            inside = True
            continue
        if inside and line.startswith("  - "):
            text = line[4:].strip()
            if text.startswith("'") and text.endswith("'"):
                text = text[1:-1].replace("''", "'")
            commands.append(text)
        elif inside and line and not line.startswith(" "):
            inside = False
    return commands


def _archive_unittest():
    def build():
        root = _extract_archive()
        done, _ = _run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], root,
                       timeout=120, extra_env={"PYTHONPATH": str(root / "src")})
        ran = re.search(r"^Ran (\d+) tests?", done.stderr, re.M)
        assert ran, "archive tests did not run: %s" % done.stderr.strip()[-400:]
        passed = len(re.findall(r" \.\.\. ok$", done.stderr, re.M))
        return int(ran.group(1)), passed
    return _memo("unittest", build)


def _check_selftest():
    report = _json_artifact("selftest.json")
    wanted = _shipped_json("dependency_manifest.json")["required_version"]
    run, passed = _archive_unittest()
    core = _expected("shipped")["module_core.json"]["images"]
    rejected = sum(1 for e in core.values() if e["status"] == "rejected")
    expect = {
        "ok": run == passed and run > 0, "package": PACKAGE, "version": wanted, "archive": "/app/out/package.zip",
        "tests_run": run, "tests_passed": passed, "ci_commands": _ci_commands(),
        "reports": ["/app/out/" + doc for doc in DOCUMENTS], "images_total": len(core),
        "images_recovered": len(core) - rejected, "images_rejected": rejected,
    }
    _same("selftest.json", expect, {key: report.get(key) for key in expect})


def _check_shipped(doc):
    _same("/app/out/" + doc, _expected("shipped")[doc], _json_artifact(doc))


def _check_book(name, doc):
    _same("%s of the %s book" % (doc, name), _expected(name)[doc], _delivered(name)[doc])


def _check_timing():
    done, elapsed, _out = _run_package("max")
    assert done.returncode == 0, "package exited %s on the max book" % done.returncode
    assert elapsed <= TIME_LIMIT, "max book took %.1f s" % elapsed


def _check_missing_input():
    done, _elapsed, out = _run_package("missing")
    gone = Rng(BOOK_SEED).choice(sorted(BOOK_FILES))
    assert done.returncode != 0, "package exited 0 with %s missing" % gone
    assert gone in done.stderr, "stderr does not name %s: %r" % (gone, done.stderr.strip()[-300:])
    written = sorted(p.name for p in out.glob("*.json")) if out.is_dir() else []
    assert not written, "package wrote %s with an input missing" % written


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _check_rerun_identical():
    before = _tree_digest(_book_dir("restart"))
    first = _delivered("restart")
    second = _delivered("restart", attempt=2)
    for doc in DOCUMENTS:
        _same("second run %s" % doc, first[doc], second[doc])
    assert _tree_digest(_book_dir("restart")) == before, "package changed its input book"


def _holds(check, *args):
    try:
        check(*args)
    except Exception as exc:
        print("%s: %s" % (getattr(check, "__name__", check), exc), file=sys.stderr)
        return False
    return True


def _fires(probe):
    try:
        return bool(probe())
    except Exception as exc:
        print("%s: %s" % (getattr(probe, "__name__", probe), exc), file=sys.stderr)
        return False


def _holds_book_ids():
    shipped_ids = {img["id"] for img in _book("shipped")["images"]}
    root = _extract_archive()
    for path in sorted((root / "src").rglob("*")):
        if path.is_file():
            text = path.read_bytes().decode("utf-8", "replace")
            for iid in shipped_ids:
                if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(iid), text):
                    return True
    hidden = set(_expected("dense")["module_core.json"]["images"])
    got = set(_delivered("dense")["module_core.json"].get("images", {}))
    return bool(got & shipped_ids) and got != hidden


def _shipped_tests_dropped():
    shipped = ast.parse(_shipped_project()["tests/test_smoke.py"].decode("utf-8"))
    wanted = {n.name for n in ast.walk(shipped) if isinstance(n, ast.FunctionDef) and n.name.startswith("test")}
    members = dict((info.filename, data) for info, data in _archive_members())
    if "tests/test_smoke.py" not in members:
        return True
    text = members["tests/test_smoke.py"].decode("utf-8", "replace")
    tree = ast.parse(text)
    have = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    if wanted - have:
        return True
    return bool(re.search(r"\b(skip|skipIf|skipUnless|skipTest|SkipTest|expectedFailure)\b", text))


# ---------------------------------------------------------------- criteria

@criterion(description="The seven deliverables exist under /app/out and every JSON one parses.")
def artifacts_present(workspace: Path) -> bool:
    return _holds(_check_artifacts)


@criterion(description="package.zip holds exactly the listed members plus added package modules, stored with the stated timestamp.")
def archive_layout(workspace: Path) -> bool:
    return _holds(_check_archive_layout)


@criterion(description="The archived pyproject.toml and pagerecover.__version__ carry the required name, version, Python floor, no dependencies and the src layout.")
def package_metadata(workspace: Path) -> bool:
    return _holds(_check_package_metadata)


@criterion(description="build_report.json carries the stated values and lists exactly the package modules the repair changed or created.")
def build_report_values(workspace: Path) -> bool:
    return _holds(_check_build_report)


@criterion(description="selftest.json reports the archive's real unittest counts, the CI commands unquoted, the report paths and the shipped book's image counts.")
def selftest_truthful(workspace: Path) -> bool:
    return _holds(_check_selftest)


@criterion(description="/app/out/module_core.json equals the recovered page images of the shipped book in full.")
def shipped_core(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_core.json")


@criterion(description="/app/out/module_metrics.json equals the recovery figures of the shipped book in full.")
def shipped_metrics(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_metrics.json")


@criterion(description="/app/out/dependency_resolution.json equals the losers and appended records of the shipped book in full.")
def shipped_appended(workspace: Path) -> bool:
    return _holds(_check_shipped, "dependency_resolution.json")


@criterion(description="/app/out/summary.json equals the digests, client totals and audits of the shipped book in full.")
def shipped_summary(workspace: Path) -> bool:
    return _holds(_check_shipped, "summary.json")


@criterion(description="On a fresh book of dense crash images the archived package writes module_core.json exactly.")
def dense_core(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "module_core.json")


@criterion(description="On a fresh book of dense crash images the archived package writes module_metrics.json exactly.")
def dense_metrics(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "module_metrics.json")


@criterion(description="On a fresh book of dense crash images the archived package writes dependency_resolution.json exactly.")
def dense_appended(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "dependency_resolution.json")


@criterion(description="On a fresh book of dense crash images the archived package writes summary.json exactly.")
def dense_summary(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "summary.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes module_core.json exactly.")
def restart_core(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "module_core.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes module_metrics.json exactly.")
def restart_metrics(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "module_metrics.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes dependency_resolution.json exactly.")
def restart_appended(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "dependency_resolution.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes summary.json exactly.")
def restart_summary(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "summary.json")


@criterion(description="On a fresh book of images at the stated size limits the archived package writes module_core.json exactly.")
def max_core(workspace: Path) -> bool:
    return _holds(_check_book, "max", "module_core.json")


@criterion(description="On a fresh book of images at the stated size limits the archived package writes summary.json exactly.")
def max_summary(workspace: Path) -> bool:
    return _holds(_check_book, "max", "summary.json")


@criterion(description="The archived package recovers the book at the stated size limits within 60 seconds.")
def max_within_limit(workspace: Path) -> bool:
    return _holds(_check_timing)


@criterion(description="On a fresh book with defective images, including images with two defects, module_core.json carries the stated rejection codes and the other images exactly.")
def rejection_core(workspace: Path) -> bool:
    return _holds(_check_book, "rejection", "module_core.json")


@criterion(description="On a fresh book under a relocated path with spaces, run from a foreign directory, module_core.json is exact.")
def relocated_core(workspace: Path) -> bool:
    return _holds(_check_book, "relocated", "module_core.json")


@criterion(description="On a copy of the dense book whose page values and deltas were altered, summary.json follows the altered data exactly.")
def scaled_summary(workspace: Path) -> bool:
    return _holds(_check_book, "scaled", "summary.json")


@criterion(description="With one of the six inputs deleted the package exits nonzero, names that file on stderr and writes no document.")
def missing_input_rejected(workspace: Path) -> bool:
    return _holds(_check_missing_input)


@criterion(description="Running the package twice on the same book gives the same documents and leaves the book unchanged.")
def rerun_identical(workspace: Path) -> bool:
    return _holds(_check_rerun_identical)


@criterion(description="The archived package holds an image id of the shipped book or replays shipped figures for another book.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _fires(_holds_book_ids)


@criterion(description="The archive's tests/test_smoke.py drops or skips a test of the shipped one.")
def negative_shipped_tests_dropped(workspace: Path) -> bool:
    return _fires(_shipped_tests_dropped)


criteria.artifacts_present(weight=1)
criteria.archive_layout(weight=3)
criteria.package_metadata(weight=3)
criteria.build_report_values(weight=1)
criteria.selftest_truthful(weight=3)
criteria.shipped_core(weight=3)
criteria.shipped_metrics(weight=3)
criteria.shipped_appended(weight=3)
criteria.shipped_summary(weight=3)
criteria.dense_core(weight=5)
criteria.dense_metrics(weight=5)
criteria.dense_appended(weight=5)
criteria.dense_summary(weight=5)
criteria.restart_core(weight=5)
criteria.restart_metrics(weight=5)
criteria.restart_appended(weight=5)
criteria.restart_summary(weight=5)
criteria.max_core(weight=5)
criteria.max_summary(weight=3)
criteria.max_within_limit(weight=3)
criteria.rejection_core(weight=5)
criteria.relocated_core(weight=5)
criteria.scaled_summary(weight=5)
criteria.missing_input_rejected(weight=3)
criteria.rerun_identical(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_shipped_tests_dropped(weight=-3)
