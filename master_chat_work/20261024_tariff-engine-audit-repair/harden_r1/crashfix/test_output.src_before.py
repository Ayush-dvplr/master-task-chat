"""Checks for the repaired tariff package delivered under /app/out."""

from __future__ import annotations

import ast
import base64
import csv
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
import zlib
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

H1_SEED = int("740213")
H3_SEED = int("518806")
H5_SEED = int("962457")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
ARTIFACTS = [
    "/app/out/patched-repo.zip",
    "/app/out/repair-report.json",
    "/app/out/module_core.json",
    "/app/out/module_parser.json",
    "/app/out/module_report.json",
    "/app/out/test_fixes.json",
    "/app/out/summary.json",
]
INPUT_FILES = ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv", "rate_card.json")
CORRECTED = ["test_commitment_credit_base", "test_partial_period_standing_charge"]
REUSED_IDS = ("A0003", "A0010", "A0042")
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

_SHIPPED_DATA: dict[str, str] = {}
_DATA_CACHE: list[Path] = []
_MEMO: dict[str, Any] = {}


# ---------------------------------------------------------------- plumbing

def _open_tree(root: Path) -> Path:
    """Make a tree the checks built readable by the unprivileged runner."""
    for path in [root, *root.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root


def _scratch(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o755)
    return path


def _data_dir() -> Path:
    """The agent's /app/ci and /app/repo, rebuilt here: the verifier container never has them."""
    if not _DATA_CACHE:
        root = _scratch("shipped-data-")
        for rel, blob in _SHIPPED_DATA.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.decompress(base64.b64decode(blob)))
        _DATA_CACHE.append(_open_tree(root))
    return _DATA_CACHE[0]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
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
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _artifact(name: str) -> Path:
    return OUT_DIR / name


def _load_json(name: str) -> Any:
    return json.loads(_artifact(name).read_text(encoding="utf-8"))


def _memo(key: str, build) -> Any:
    """Compute once per verifier run; a failure is remembered and raised again."""
    if key not in _MEMO:
        try:
            _MEMO[key] = (True, build())
        except Exception as error:  # remembered so each dependent check fails alike
            _MEMO[key] = (False, error)
    ok, value = _MEMO[key]
    if not ok:
        raise value
    return value


def _extract_archive() -> Path:
    archive = _artifact("patched-repo.zip")
    assert archive.is_file(), "patched-repo.zip missing"
    dest = _scratch("repo-patch-check-")
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            rel = Path(info.filename)
            assert not rel.is_absolute() and ".." not in rel.parts, "unsafe archive member"
            assert not info.filename.endswith("/"), "directory entries are not needed"
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
    return _open_tree(dest)


def _repo() -> Path:
    return _memo("repo", _extract_archive)


def _env(repo: Path | None) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"}
    if repo is not None:
        env["PYTHONPATH"] = str(repo / "src")
    return env


def _run(command: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(_untrusted_command(command), text=True, capture_output=True, env=env,
                          cwd=str(cwd), timeout=120)


def _cli(data: Path) -> subprocess.CompletedProcess:
    repo = _repo()
    return _run([sys.executable, "-B", "-m", "tariff", str(data)], _env(repo), _scratch("cwd-"))


_ISOLATED = (
    "import runpy, sys\n"
    "src, data = sys.argv[1], sys.argv[2]\n"
    "sys.path.insert(0, src)\n"
    "sys.argv = ['tariff', data]\n"
    "runpy.run_module('tariff', run_name='__main__', alter_sys=True)\n"
)
_API = (
    "import json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import tariff\n"
    "print(json.dumps(tariff.build_invoices(sys.argv[2])))\n"
)


def _write_texts(texts: dict[str, str], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def _delivered(corpus: str) -> dict[str, Any]:
    """The delivered package's document for one corpus, run the way that corpus is run."""
    def build() -> dict[str, Any]:
        texts = _corpus_texts(corpus)
        if corpus == "relocated":
            base = _scratch("moved-")
            shutil.copytree(_repo(), base / "checkout" / "billing-engine")
            data = _write_texts(texts, base / "feeds" / "cycle-inputs")
            _open_tree(base)
            command = [sys.executable, "-I", "-B", "-c", _ISOLATED,
                       str(base / "checkout" / "billing-engine" / "src"), str(data)]
            done = _run(command, _env(None), _scratch("elsewhere-"))
        elif corpus == "api":
            data = _open_tree(_write_texts(texts, _scratch("api-") / "data"))
            command = [sys.executable, "-I", "-B", "-c", _API, str(_repo() / "src"), str(data)]
            done = _run(command, _env(None), _scratch("elsewhere-"))
        else:
            data = _open_tree(_write_texts(texts, _scratch(f"{corpus}-") / "data"))
            done = _cli(data)
        assert done.returncode == 0, f"{corpus}: exit {done.returncode}: {done.stderr[-400:]}"
        document = json.loads(done.stdout)
        assert isinstance(document, dict) and set(document) == {"invoices", "exceptions"}, "document keys"
        return document
    return _memo(f"doc:{corpus}", build)


def _shipped_texts() -> dict[str, str]:
    ci = _data_dir() / "ci"
    return {name: (ci / name).read_text(encoding="utf-8") for name in INPUT_FILES}


def _shipped_delivered() -> dict[str, Any]:
    def build() -> dict[str, Any]:
        done = _cli(_data_dir() / "ci")
        assert done.returncode == 0, f"shipped: exit {done.returncode}: {done.stderr[-400:]}"
        return json.loads(done.stdout)
    return _memo("doc:shipped", build)


# ---------------------------------------------------------------- reference reading of the contract

def _even_cents(value: Fraction) -> int:
    scaled = value * 100
    whole = scaled.numerator // scaled.denominator
    rest = scaled - whole
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and whole % 2 == 1):
        whole += 1
    return whole


def _amount(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


class _Ledger:
    """The contract read literally, with exact fractions."""

    def __init__(self, texts: dict[str, str]):
        card = json.loads(texts["rate_card.json"], parse_float=Fraction)
        self.plans = card["plans"]
        self.periods: dict[str, tuple[date, date, str, Fraction]] = {}
        for row in csv.DictReader(io.StringIO(texts["billing_periods.csv"])):
            row = {key.strip(): (value or "").strip() for key, value in row.items()}
            self.periods[row["account"]] = (date.fromisoformat(row["start"]), date.fromisoformat(row["end"]),
                                            row["plan"], Fraction(row["commitment"]))
        self.windows: dict[tuple[str, str], tuple[date, date | None]] = {}
        for row in csv.DictReader(io.StringIO(texts["accounts.csv"])):
            row = {key.strip(): (value or "").strip() for key, value in row.items()}
            until = date.fromisoformat(row["active_to"]) if row["active_to"] else None
            self.windows[(row["account"], row["meter"])] = (date.fromisoformat(row["active_from"]), until)
        self.reads = [json.loads(line) for line in texts["meter_reads.jsonl"].splitlines() if line.strip()]
        self.ties: dict[str, int] = {}

    def _reason(self, account: str, meter: str, day: date, quantity: Any, taken: set) -> str | None:
        if type(quantity) is not int or quantity < 0:
            return "malformed_quantity"
        window = self.windows.get((account, meter))
        if window is None:
            return "unknown_meter"
        if day < window[0] or (window[1] is not None and day > window[1]):
            return "inactive_meter"
        start, end = self.periods[account][:2]
        if not start <= day <= end:
            return "outside_period"
        if (account, meter, day) in taken:
            return "duplicate_read"
        return None

    def document(self) -> dict[str, Any]:
        taken: set = set()
        usage: dict[tuple[str, str], int] = {}
        exceptions = []
        for read in self.reads:
            account, meter = read["account"].strip(), read["meter"].strip()
            day = date.fromisoformat(read["day"].strip())
            reason = self._reason(account, meter, day, read["quantity"], taken)
            if reason is None:
                taken.add((account, meter, day))
                usage[(account, meter)] = usage.get((account, meter), 0) + read["quantity"]
            else:
                exceptions.append({"read_id": read["read_id"].strip(), "account": account, "reason": reason})
        exceptions.sort(key=lambda row: row["read_id"])
        invoices = [self._invoice(account, usage) for account in sorted(self.periods)]
        return {"invoices": invoices, "exceptions": exceptions}

    def _invoice(self, account: str, usage: dict) -> dict[str, Any]:
        start, end, plan_name, commitment = self.periods[account]
        plan = self.plans[plan_name]
        span = (end - start).days + 1
        lines, ties = [], 0
        for meter in sorted(m for (a, m) in self.windows if a == account):
            quantity, floor = usage.get((account, meter), 0), 0
            for number, tier in enumerate(plan["tiers"], 1):
                cap = tier["up_to"]
                top = quantity if cap is None else min(quantity, cap)
                if top > floor:
                    lines.append((meter, "energy", number, top - floor, (top - floor) * tier["rate"]))
                if cap is None or quantity <= cap:
                    break
                floor = cap
            since, until = self.windows[(account, meter)]
            first, last = max(since, start), end if until is None else min(until, end)
            days = (last - first).days + 1
            if days > 0:
                lines.append((meter, "standing", 0, days, plan["standing_charge"] * days / span))
        rows, subtotal = [], 0
        for meter, kind, tier, units, exact in lines:
            cents = _even_cents(exact)
            if exact * 100 - (exact * 100).numerator // (exact * 100).denominator == Fraction(1, 2) and cents % 2 == 0:
                ties += 1
            subtotal += cents
            rows.append({"meter": meter, "kind": kind, "tier": tier, "units": units, "amount": _amount(cents)})
        total = subtotal
        if Fraction(subtotal, 100) >= commitment:
            total = _even_cents(Fraction(subtotal, 100) * (1 - plan["credit_rate"]))
        self.ties[account] = ties
        return {"account": account, "period": {"start": start.isoformat(), "end": end.isoformat()},
                "plan": plan_name, "lines": rows, "subtotal": _amount(subtotal),
                "credit": _amount(subtotal - total), "total": _amount(total)}


def _expected(corpus: str) -> dict[str, Any]:
    texts = _shipped_texts() if corpus == "shipped" else _corpus_texts(corpus)
    return _memo(f"ref:{corpus}", lambda: _Ledger(texts).document())


# ---------------------------------------------------------------- hidden corpora

def _rate_text(units: int) -> str:
    return f"{units // 10000}.{units % 10000:04d}"


def _tie_units(rate: int, limit: int) -> list[int]:
    """Units whose line lands on half a cent with an even cent below and the binary float product above it."""
    found = []
    for units in range(1, limit):
        value = units * rate
        if value % 100 != 50 or (value // 100) % 2:
            continue
        if Fraction((rate / 10000) * units) > Fraction(value, 10000):
            found.append(units)
    return found


def _tie_rate(rng: random.Random, low: int, high: int, limit: int) -> tuple[int, list[int]]:
    while True:
        rate = rng.randrange(low, high)
        if rate % 4 == 0 or Fraction(rate / 10000) <= Fraction(rate, 10000):
            continue
        units = _tie_units(rate, limit)
        if len(units) >= 3:
            return rate, units


def _card_text(plans: dict[str, dict[str, Any]]) -> str:
    parts = []
    for name, plan in plans.items():
        tiers = ", ".join(
            "{" + f'"up_to": {"null" if cap is None else cap}, "rate": {_rate_text(rate)}' + "}"
            for cap, rate in plan["tiers"])
        parts.append(f'    "{name}": {{"standing_charge": {_amount(plan["standing"])}, '
                     f'"credit_rate": {plan["credit"]}, "tiers": [{tiers}]}}')
    return '{\n  "currency": "EUR",\n  "plans": {\n' + ",\n".join(parts) + "\n  }\n}\n"


def _read_line(read: dict[str, Any]) -> str:
    return ('{"read_id": ' + json.dumps(read["read_id"]) + ', "account": ' + json.dumps(read["account"])
            + ', "meter": ' + json.dumps(read["meter"]) + ', "day": ' + json.dumps(read["day"])
            + ', "quantity": ' + read["quantity"] + "}")


def _assemble(plans, periods, meters, reads) -> dict[str, str]:
    return {
        "meter_reads.jsonl": "".join(_read_line(read) + "\n" for read in reads),
        "accounts.csv": "account,meter,active_from,active_to\n"
        + "".join(f"{a},{m},{f},{t}\n" for a, m, f, t in meters),
        "billing_periods.csv": "account,start,end,plan,commitment\n"
        + "".join(f"{a},{s},{e},{p},{c}\n" for a, s, e, p, c in periods),
        "rate_card.json": _card_text(plans),
    }


def _period(rng: random.Random) -> tuple[date, date]:
    while True:
        start = date(rng.choice([2026, 2027]), rng.randrange(1, 13), rng.randrange(2, 28))
        end = start + timedelta(days=rng.choice([27, 29, 32, 33, 34]) - 1)
        if (end.year, end.month) != (start.year, start.month):
            return start, end


def _split(rng: random.Random, total: int, parts: int) -> list[int]:
    cuts = sorted(rng.sample(range(1, total), parts - 1)) if total > parts else []
    bounds = [0, *cuts, total]
    return [b - a for a, b in zip(bounds, bounds[1:])] if cuts else [total]


def _corpus(seed: int, size: int, reuse: tuple[str, ...]) -> tuple[dict[str, str], dict[str, Any]]:
    rng = random.Random(seed)
    tag = "".join(rng.choice("KLMNPRSTVW") for _ in range(2))
    plans: dict[str, dict[str, Any]] = {}
    tie_units: dict[str, list[tuple[int, int]]] = {}
    scale_step = rng.randrange(30, 41)
    for index, credit in enumerate(["0.05", "0.02", "0.06", "0.04"]):
        first = rng.randrange(80, 261)
        second = first + rng.randrange(200, 501)
        middle, middle_units = _tie_rate(rng, 1800, 2400, second - first)
        last, last_units = _tie_rate(rng, 1150, 1800, 1500)
        head = 80 * scale_step if index == 0 else rng.randrange(2400, 3200)
        name = f"{tag}-{index + 1}"
        plans[name] = {"standing": rng.randrange(1200, 7000), "credit": credit,
                       "tiers": [(first, head), (second, middle), (None, last)]}
        tie_units[name] = [(first, u) for u in middle_units] + [(second, u) for u in last_units]
    names = list(plans)
    accounts = sorted({*reuse, *(f"{tag[0]}{n:04d}" for n in rng.sample(range(1, 10000), size - len(reuse)))})
    credit_ties = {accounts[1]: names[1], accounts[4]: names[2]}
    equal = {accounts[7]: names[3]}
    meter_ids = iter(f"{tag[1]}{n:05d}" for n in rng.sample(range(1, 100000), size * 6))
    read_ids = iter(f"H{n:05d}" for n in rng.sample(range(10000, 100000), size * 40))
    periods, meters, reads, pairs = [], [], [], []
    tuned: dict[str, dict[str, Any]] = {}
    kinds = ["late", "early", "gone"]

    def add(account, meter, day, quantity, pad=False):
        read = {"read_id": next(read_ids), "account": account, "meter": meter, "day": day.isoformat(),
                "quantity": quantity}
        if pad or rng.random() < 0.04:
            read["read_id"], read["account"], read["meter"] = f" {read['read_id']}", f"{account} ", f" {meter}  "
        reads.append(read)
        return read

    for position, account in enumerate(accounts):
        plan_name = credit_ties.get(account) or equal.get(account) or rng.choice(names)
        start, end = _period(rng)
        span = (end - start).days + 1
        days = [start + timedelta(days=k) for k in range(span)]
        periods.append([account, start.isoformat(), end.isoformat(), plan_name, None])
        own = [next(meter_ids) for _ in range(4)]
        for meter in own[:3]:
            meters.append((account, meter, (start - timedelta(days=rng.randrange(30, 400))).isoformat(), ""))
        quiet = account in credit_ties or account in equal
        kind = "open" if quiet else (kinds[position % 3] if position < 6 else rng.choice(["open", "open", *kinds]))
        since, until = start - timedelta(days=rng.randrange(20, 300)), None
        if kind == "late":
            since = start + timedelta(days=rng.randrange(1, span - 2))
        elif kind == "early":
            until = start + timedelta(days=rng.randrange(0, span - 3))
        elif kind == "gone":
            until = start - timedelta(days=rng.randrange(1, 40))
            since = until - timedelta(days=rng.randrange(20, 200))
        meters.append((account, own[3], since.isoformat(), "" if until is None else until.isoformat()))
        if not quiet and position % 3 == 1:
            # an active meter whose only read is rejected still pays its standing line
            own.append(next(meter_ids))
            meters.append((account, own[4], (start - timedelta(days=rng.randrange(30, 400))).isoformat(), ""))
            add(account, own[4], rng.choice(days), rng.choice(["null", "false", "7.5", "-3"]))
        used: dict[str, set] = {meter: set() for meter in own}
        accepted_first: dict[str, dict[str, Any]] = {}
        for meter in own[:3]:
            floor, extra = rng.choice(tie_units[plan_name])
            parts = _split(rng, floor + extra, rng.choice([2, 3]))
            for part, day in zip(parts, rng.sample(days, len(parts))):
                read = add(account, meter, day, str(part))
                used[meter].add(day)
                accepted_first.setdefault(meter, read)
        live = [d for d in days if d >= since and (until is None or d <= until)]
        for day in rng.sample(live, min(len(live), rng.choice([2, 3]))) if kind != "gone" else []:
            add(account, own[3], day, str(rng.randrange(0, 300)))
            used[own[3]].add(day)
        if quiet:
            spare = [d for d in days if d not in used[own[3]]]
            tuned[account] = add(account, own[3], rng.choice(spare), "0")
        # a quoted integer on a day of its own, so reading it would move the energy line
        spare = [d for d in days if d not in used[own[0]]]
        quoted = rng.randrange(20, 90)
        add(account, own[0], rng.choice(spare), json.dumps(rng.choice([str(quoted), f" {quoted} ", f"{quoted} "])))
        # same day, same quantity again on a tie meter
        twin = accepted_first[own[1]]
        pairs.append((twin, add(account, own[1], date.fromisoformat(twin["day"]), twin["quantity"])))
        outside = end + timedelta(days=rng.randrange(1, 6)) if rng.random() < 0.5 else start - timedelta(days=rng.randrange(1, 6))
        add(account, own[1], outside, str(rng.randrange(5, 200)))
        if position % 4 == 0:
            add(account, own[1], outside, str(rng.randrange(5, 200)))
        spare = [d for d in days if d not in used[own[2]]]
        add(account, own[2], rng.choice(spare), rng.choice(["2.5", "12.0", "1E2", "3e1", "true", "false", "null", "-4", "40.00"]))
        stranger = rng.choice([m for (_, m, _, _) in meters if m not in own] or ["Z00000"])
        add(account, stranger, rng.choice(days), rng.choice([str(rng.randrange(1, 90)), json.dumps(str(rng.randrange(1, 90)))]))
        if kind in ("late", "early", "gone"):
            away = start - timedelta(days=3) if kind == "late" else end + timedelta(days=3)
            add(account, own[3], away, str(rng.randrange(1, 90)))
            gap = [d for d in days if d < since or (until is not None and d > until)]
            if gap:
                add(account, own[3], rng.choice(gap), str(rng.randrange(1, 90)))
        if not quiet and kind != "gone" and used[own[3]]:
            day = rng.choice(sorted(used[own[3]]))
            first = next(r for r in reads if r["meter"].strip() == own[3] and r["day"] == day.isoformat())
            pairs.append((first, add(account, own[3], day, str(int(first["quantity"]) + rng.randrange(1, 40)))))
        if kind == "open" and not quiet:
            spare = [d for d in days if d not in used[own[3]]]
            day = rng.choice(spare)
            pairs.append((add(account, own[3], day, "null"), add(account, own[3], day, str(rng.randrange(1, 60)))))
            used[own[3]].add(day)
            day = rng.choice([d for d in days if d not in used[own[3]]])
            pairs.append((add(account, own[3], day, str(rng.randrange(1, 60))), add(account, own[3], day, "-7")))
    add("Q" + tag, "Z" + tag, date(2026, 6, 1), "10")

    order = list(range(len(reads)))
    rng.shuffle(order)
    reads = [reads[i] for i in order]
    for first, second in pairs:
        a, b = reads.index(first), reads.index(second)
        if a > b:
            reads[a], reads[b] = reads[b], reads[a]

    def texts_for(chosen: set[str] | None, commitments: dict[str, str]) -> dict[str, str]:
        keep = (lambda account: True) if chosen is None else (lambda account: account in chosen)
        rows = [[*row[:4], commitments.get(row[0], "0.00")] for row in periods if keep(row[0])]
        return _assemble(plans, rows, [m for m in meters if keep(m[0])],
                         [r for r in reads if keep(r["account"].strip())])

    for account, read in tuned.items():
        for quantity in range(0, 600):
            read["quantity"] = str(quantity)
            cents = _cents_of(_Ledger(texts_for({account}, {})).document()["invoices"][0]["subtotal"])
            if account in equal or cents % 50 == 25:
                break
        else:
            raise AssertionError("no settling quantity for a credit tie")
    ledger = _Ledger(texts_for(None, {}))
    subtotals = {inv["account"]: _cents_of(inv["subtotal"]) for inv in ledger.document()["invoices"]}
    commitments = {}
    for account, cents in subtotals.items():
        if account in equal:
            commitments[account] = _amount(cents)
        elif account in credit_ties:
            commitments[account] = _amount(cents - rng.randrange(0, cents // 4))
        else:
            commitments[account] = _amount(int(cents * rng.choice([0.6, 0.75, 0.9, 1.05, 1.2, 1.4])))
    texts = texts_for(None, commitments)
    info = {"plans": plans, "first_plan": names[0], "scale_step": scale_step, "credit_ties": sorted(credit_ties),
            "equal": sorted(equal), "subtotals": subtotals, "ties": dict(ledger.ties), "kinds": None}
    _assert_bounds(texts, info)
    return texts, info


def _cents_of(text: str) -> int:
    whole, cents = text.split(".")
    return int(whole) * 100 + int(cents)


def _assert_bounds(texts: dict[str, str], info: dict[str, Any]) -> None:
    """Every corpus stays inside what the contract promises about its inputs."""
    ledger = _Ledger(texts)
    for account, (start, end, plan, commitment) in ledger.periods.items():
        span = (end - start).days + 1
        assert 1 <= span <= 62 and span not in (28, 30, 31), account
        assert (commitment * 100).denominator == 1, account
        assert info["ties"][account] >= 3, f"{account} has {info['ties'][account]} half-cent lines"
    for plan in ledger.plans.values():
        assert (plan["standing_charge"] * 100).denominator == 1
        assert 0 <= plan["credit_rate"] <= 1 and (plan["credit_rate"] * 10000).denominator == 1
        assert all((tier["rate"] * 10 ** 8).denominator == 1 for tier in plan["tiers"])
        assert [t["up_to"] for t in plan["tiers"]][-1] is None
    for account in info["credit_ties"]:
        cents = info["subtotals"][account]
        assert cents % 50 == 25 and ledger.periods[account][3] * 100 <= cents, account
    for account in info["equal"]:
        assert ledger.periods[account][3] * 100 == info["subtotals"][account], account
    ids = [json.loads(line)["read_id"].strip() for line in texts["meter_reads.jsonl"].splitlines()]
    assert len(ids) == len(set(ids))
    quoted = {json.loads(line)["account"].strip() for line in texts["meter_reads.jsonl"].splitlines()
              if isinstance(json.loads(line)["quantity"], str)}
    assert set(ledger.periods) <= quoted


def _rescaled(texts: dict[str, str], info: dict[str, Any], seed: int) -> dict[str, str]:
    """Rows shuffled and one plan's first rate multiplied by 1.0375 (83/80), still four decimals."""
    plans = {name: dict(plan) for name, plan in info["plans"].items()}
    first = plans[info["first_plan"]]
    (cap, rate), *rest = first["tiers"]
    assert rate == 80 * info["scale_step"]
    first["tiers"] = [(cap, 83 * info["scale_step"]), *rest]
    lines = texts["meter_reads.jsonl"].splitlines(keepends=True)
    random.Random(seed).shuffle(lines)
    return {**texts, "meter_reads.jsonl": "".join(lines), "rate_card.json": _card_text(plans)}


def _rotated(texts: dict[str, str], seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    out = dict(texts)
    for name in ("meter_reads.jsonl", "accounts.csv", "billing_periods.csv"):
        lines = texts[name].splitlines(keepends=True)
        head, body = (lines[:1], lines[1:]) if name.endswith(".csv") else ([], lines)
        k = rng.randrange(1, len(body))
        out[name] = "".join(head + body[k:] + body[:k])
    return out


def _corpus_texts(corpus: str) -> dict[str, str]:
    def build() -> dict[str, str]:
        if corpus == "fresh":
            return _corpus(H1_SEED, 30, REUSED_IDS)[0]
        if corpus == "rescaled":
            texts, info = _memo("fresh-info", lambda: _corpus(H1_SEED, 30, REUSED_IDS))
            return _rescaled(texts, info, H1_SEED + 1)
        if corpus == "relocated":
            return _corpus(H3_SEED, 24, ())[0]
        if corpus == "rotated":
            return _rotated(_corpus_texts("relocated"), H3_SEED + 1)
        if corpus == "api":
            return _corpus(H5_SEED, 45, ())[0]
        raise KeyError(corpus)
    return _memo(f"texts:{corpus}", build)


def _write_corpus(target: str) -> None:
    for corpus in ("fresh", "rescaled", "relocated", "rotated", "api"):
        _write_texts(_corpus_texts(corpus), Path(target) / corpus)


# ---------------------------------------------------------------- owned rows

def _by_account(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    invoices = document["invoices"]
    assert isinstance(invoices, list)
    return {invoice["account"]: invoice for invoice in invoices}


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _lines_of(invoice: dict[str, Any], kinds: tuple[str, ...]) -> list[Any]:
    return [line for line in invoice["lines"] if line.get("kind") in kinds]


def _check_lines(corpus: str, kinds: tuple[str, ...]) -> None:
    want = _by_account(_expected(corpus))
    got = _by_account(_delivered(corpus) if corpus != "shipped" else _shipped_delivered())
    assert list(got) == list(want), "invoice accounts or order differ"
    wrong = [a for a in want if not _same(_lines_of(got[a], kinds), _lines_of(want[a], kinds))]
    assert not wrong, f"{len(wrong)} invoices with wrong {'/'.join(kinds)} lines, first {wrong[0]}"


def _check_heads(corpus: str) -> None:
    want = _by_account(_expected(corpus))
    got = _by_account(_delivered(corpus))
    assert list(got) == list(want), "invoice accounts or order differ"
    keys = ["account", "period", "plan", "subtotal"]
    wrong = [a for a in want
             if set(got[a]) != set(want[a]) or not _same([got[a][k] for k in keys], [want[a][k] for k in keys])]
    assert not wrong, f"{len(wrong)} invoices with wrong heads or subtotals, first {wrong[0]}"


def _check_settlement(corpus: str) -> None:
    want = _by_account(_expected(corpus))
    got = _by_account(_delivered(corpus) if corpus != "shipped" else _shipped_delivered())
    assert list(got) == list(want), "invoice accounts or order differ"
    keys = ["credit", "total"] if corpus != "shipped" else ["subtotal", "credit", "total"]
    wrong = [a for a in want if not _same([got[a][k] for k in keys], [want[a][k] for k in keys])]
    assert not wrong, f"{len(wrong)} invoices with wrong {'/'.join(keys)}, first {wrong[0]}"


def _check_exceptions(corpus: str) -> None:
    got = _delivered(corpus) if corpus != "shipped" else _shipped_delivered()
    assert _same(got["exceptions"], _expected(corpus)["exceptions"]), "exception list differs"


# ---------------------------------------------------------------- deliverable checks

def _shipped_repo_files() -> list[str]:
    return sorted(rel.removeprefix("repo/") for rel in _SHIPPED_DATA if rel.startswith("repo/"))


def _check_archive_and_metadata() -> None:
    config = json.loads((_data_dir() / "ci" / "build_config.json").read_text())["archive"]
    manifest = json.loads((_data_dir() / "ci" / "package_manifest.json").read_text())
    method = {"stored": zipfile.ZIP_STORED, "deflated": zipfile.ZIP_DEFLATED}[config["compression"]]
    with zipfile.ZipFile(_artifact("patched-repo.zip")) as zf:
        infos = zf.infolist()
    names = [info.filename for info in infos]
    assert names == sorted(names), "members are not sorted"
    assert not any(n.endswith("/") or "__pycache__" in n or n.endswith(".pyc") for n in names), "stray members"
    assert set(_shipped_repo_files()) <= set(names), "a repository file is missing"
    for info in infos:
        assert info.date_time == tuple(config["timestamp"]), info.filename
        assert info.compress_type == method, info.filename
        assert (info.external_attr >> 16) & 0o777 == int(config["mode"], 8), info.filename
    project = tomllib.loads((_repo() / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == manifest["version"], "pyproject version"
    assert project["requires-python"] == manifest["requires_python"], "requires-python"
    assert project["dependencies"] == [], "dependencies"
    done = _run([sys.executable, "-B", "-c", "import tariff; print(repr(tariff.VERSION))"], _env(_repo()), _scratch("cwd-"))
    assert done.returncode == 0 and done.stdout.strip() == repr(manifest["version"]), "tariff.VERSION"
    for path in sorted((_repo() / "src" / "tariff").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            for root in roots:
                assert root == "tariff" or root in sys.stdlib_module_names, f"{path.name} imports {root}"
                assert root not in {"socket", "urllib", "http", "ssl", "ftplib", "smtplib", "sitecustomize"}, root


def _check_visible_tests_pass() -> None:
    repo = _repo()
    done = _run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                _env(repo), repo)
    assert done.returncode == 0, done.stderr[-600:]
    assert "Ran 0 tests" not in done.stderr


def _test_functions(text: str) -> dict[str, str]:
    found = {}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            found[node.name] = ast.dump(node)
    return found


def _visible_texts() -> tuple[str, str]:
    shipped = (_data_dir() / "repo" / "tests" / "test_visible.py").read_text(encoding="utf-8")
    delivered = (_repo() / "tests" / "test_visible.py").read_text(encoding="utf-8")
    return shipped, delivered


def _check_corrected_tests() -> None:
    shipped, delivered = (_test_functions(text) for text in _visible_texts())
    changed = sorted(name for name in shipped if name in delivered and delivered[name] != shipped[name])
    fixes = _load_json("test_fixes.json")
    listed = fixes["corrected_tests"]
    assert isinstance(listed, list) and listed == sorted(listed), "corrected_tests must be a sorted list"
    assert set(CORRECTED) <= set(listed) and set(listed) <= set(changed), f"corrected_tests {listed} vs changed {changed}"
    assert fixes["visible_tests_preserved"] is True


def _case_texts(case: dict[str, Any], card: str) -> dict[str, str]:
    meters = "".join(f"{case['account']},{m['meter']},{m['active_from']},{m['active_to']}\n" for m in case["meters"])
    period = case["period"]
    return {
        "meter_reads.jsonl": "".join(json.dumps(read) + "\n" for read in case["reads"]),
        "accounts.csv": "account,meter,active_from,active_to\n" + meters,
        "billing_periods.csv": "account,start,end,plan,commitment\n"
        + f"{case['account']},{period['start']},{period['end']},{case['plan']},{case['commitment']}\n",
        "rate_card.json": card,
    }


def _check_regression_rows() -> None:
    ci = _data_dir() / "ci"
    card = (ci / "rate_card.json").read_text(encoding="utf-8")
    rows = []
    for line in (ci / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        total = _Ledger(_case_texts(case, card)).document()["invoices"][0]["total"]
        rows.append({"name": case["name"], "expected": case["customer_claim"], "actual": total,
                     "passed": total == case["customer_claim"]})
    fixes = _load_json("test_fixes.json")
    assert _same(fixes["regression_cases"], rows), "regression rows differ"
    assert fixes["all_regressions_passed"] is all(row["passed"] for row in rows)


def _lint_errors(module: str) -> int:
    report = json.loads((_data_dir() / "ci" / "lint_report.json").read_text())
    return sum(1 for issue in report["issues"]
               if issue["module"] == f"tariff.{module}" and issue["severity"] == "error")


def _strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def _check_module_notes() -> None:
    extras = {"core": "validations", "parser": "contract_terms", "report": "deterministic"}
    for module, extra in extras.items():
        note = _load_json(f"module_{module}.json")
        assert set(note) == {"module", "status", "fixes", "lint_errors", extra}, module
        assert note["module"] == module and note["status"] == "fixed" and _strings(note["fixes"]), module
        assert type(note["lint_errors"]) is int and note["lint_errors"] == _lint_errors(module), module
    assert _strings(_load_json("module_core.json")["validations"])
    assert _load_json("module_parser.json")["contract_terms"] == ["VERSION", "build_invoices", "render"]
    assert _load_json("module_report.json")["deterministic"] is True


def _check_summary() -> None:
    summary = _load_json("summary.json")
    inputs = sorted({rel.split("/")[1] for rel in _SHIPPED_DATA if rel.startswith("ci/")})
    assert set(summary) == {"package", "status", "inputs_used", "artifacts", "artifact_count", "stdlib_only"}
    assert summary["package"] == "tariff" and summary["status"] == "complete"
    assert summary["inputs_used"] == inputs and summary["artifacts"] == ARTIFACTS
    assert type(summary["artifact_count"]) is int and summary["artifact_count"] == 7
    assert summary["stdlib_only"] is True


def _previously_failing() -> list[str]:
    names = set()
    for line in (_data_dir() / "ci" / "failing_tests.log").read_text(encoding="utf-8").splitlines():
        if line.startswith("test_") and (line.endswith(" ... FAIL") or line.endswith(" ... ERROR")):
            names.add(line.split()[0].removeprefix("test_"))
    return sorted(names)


def _check_repair_report() -> None:
    report = _load_json("repair-report.json")
    assert report["package"] == "tariff" and _strings(report["fixes"])
    checks = report["checks"]
    assert isinstance(checks, list) and checks
    assert all(set(c) == {"name", "passed"} and isinstance(c["name"], str) and type(c["passed"]) is bool for c in checks)
    assert any(c["passed"] is True for c in checks)
    assert _load_json("test_fixes.json")["previously_failing"] == _previously_failing()


def _check_missing_source() -> None:
    data = _write_texts(_corpus_texts("fresh"), _scratch("missing-") / "data")
    (data / "meter_reads.jsonl").unlink()
    (data / "billing_periods.csv").unlink()
    done = _cli(_open_tree(data))
    assert done.returncode == 2, done.returncode
    assert done.stdout == "", "standard output must stay empty"
    assert done.stderr.strip() == "missing input: meter_reads.jsonl", done.stderr[-200:]


def _check_two_runs() -> None:
    data = _open_tree(_write_texts(_corpus_texts("fresh"), _scratch("twice-") / "data"))
    first, second = _cli(data), _cli(data)
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout and first.stdout.strip()


def _shipped_invoice_reused() -> bool:
    shipped = _by_account(_expected("shipped"))
    hidden = _by_account(_delivered("fresh"))
    return any(a in shipped and a in hidden and _same(hidden[a], shipped[a]) for a in REUSED_IDS)


def _visible_test_removed() -> bool:
    shipped, delivered = _visible_texts()
    if set(_test_functions(shipped)) - set(_test_functions(delivered)):
        return True
    tree = ast.parse(delivered)
    for node in ast.walk(tree):
        name = node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""
        if name in {"skip", "skipIf", "skipUnless", "skipTest", "SkipTest", "expectedFailure"}:
            return True
    return False


def _holds(check) -> bool:
    try:
        check()
        return True
    except Exception:
        return False


def _fires(probe) -> bool:
    try:
        return bool(probe())
    except Exception:
        return False


if __name__ == "__main__":
    _write_corpus(sys.argv[1])


# ---------------------------------------------------------------- criteria

@criterion(description="patched-repo.zip follows build_config.json and the repaired metadata matches package_manifest.json")
def archive_and_metadata_follow_build_config(workspace: Path) -> bool:
    return _holds(_check_archive_and_metadata)


@criterion(description="The delivered tests/test_visible.py passes against the delivered package")
def delivered_visible_tests_pass(workspace: Path) -> bool:
    return _holds(_check_visible_tests_pass)


@criterion(description="test_fixes.json corrected_tests names the changed visible tests, including both contradicting ones")
def corrected_tests_name_the_changed_tests(workspace: Path) -> bool:
    return _holds(_check_corrected_tests)


@criterion(description="Every regression_cases row carries the contract total of its case")
def regression_rows_match_contract(workspace: Path) -> bool:
    return _holds(_check_regression_rows)


@criterion(description="The three module notes carry the stated keys, lint error counts and extras")
def module_notes_follow_contract(workspace: Path) -> bool:
    return _holds(_check_module_notes)


@criterion(description="summary.json lists every /app/ci file and the seven artifacts in task order")
def summary_lists_inputs_and_artifacts(workspace: Path) -> bool:
    return _holds(_check_summary)


@criterion(description="repair-report.json has its stated shape and previously_failing matches failing_tests.log")
def repair_report_and_failing_cases(workspace: Path) -> bool:
    return _holds(_check_repair_report)


@criterion(description="The exception list for the shipped /app/ci files is exact")
def shipped_exceptions_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_exceptions("shipped"))


@criterion(description="Every standing line for the shipped /app/ci files is exact")
def shipped_standing_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("shipped", ("standing",)))


@criterion(description="Every energy line, subtotal, credit and total for the shipped /app/ci files is exact")
def shipped_energy_and_settlement_exact(workspace: Path) -> bool:
    return _holds(lambda: (_check_lines("shipped", ("energy",)), _check_settlement("shipped")))


@criterion(description="The exception list for a fresh corpus of other periods is exact")
def fresh_exceptions_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_exceptions("fresh"))


@criterion(description="Every energy line for a fresh corpus of other periods is exact")
def fresh_energy_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("fresh", ("energy",)))


@criterion(description="Every standing line for a fresh corpus of other periods is exact")
def fresh_standing_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("fresh", ("standing",)))


@criterion(description="Every invoice head and subtotal for a fresh corpus of other periods is exact")
def fresh_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("fresh"))


@criterion(description="Every credit and total for a fresh corpus of other periods is exact")
def fresh_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("fresh"))


@criterion(description="Every line is exact on the fresh corpus with rows shuffled and one rate scaled by 1.0375")
def rescaled_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("rescaled", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the shuffled, rescaled corpus")
def rescaled_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("rescaled"))


@criterion(description="Every credit and total is exact on the shuffled, rescaled corpus")
def rescaled_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("rescaled"))


@criterion(description="Every line is exact on a second corpus run from relocated copies with python -I in a foreign directory")
def relocated_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("relocated", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the relocated corpus")
def relocated_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("relocated"))


@criterion(description="Every credit and total is exact on the relocated corpus")
def relocated_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("relocated"))


@criterion(description="Every line is exact on the relocated corpus with the rows of every file rotated")
def rotated_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("rotated", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the rotated corpus")
def rotated_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("rotated"))


@criterion(description="Every credit and total is exact on the rotated corpus")
def rotated_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("rotated"))


@criterion(description="Every line is exact on a larger corpus read through tariff.build_invoices")
def api_lines_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_lines("api", ("energy", "standing")))


@criterion(description="Every invoice head and subtotal is exact on the build_invoices corpus")
def api_subtotals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_heads("api"))


@criterion(description="Every credit and total is exact on the build_invoices corpus")
def api_credits_and_totals_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_settlement("api"))


@criterion(description="With input files deleted the command names the first missing one, prints nothing and exits 2")
def missing_source_is_named(workspace: Path) -> bool:
    return _holds(_check_missing_source)


@criterion(description="Two runs on the same fresh corpus print identical documents")
def two_runs_are_identical(workspace: Path) -> bool:
    return _holds(_check_two_runs)


@criterion(description="Penalty: an invoice for a reused account id on a fresh corpus repeats its shipped invoice")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened: the package returned stored shipped invoices for other inputs.
    return _fires(_shipped_invoice_reused)


@criterion(description="Penalty: a shipped visible test function is missing or skipped in the delivered tests")
def negative_visible_test_removed(workspace: Path) -> bool:
    # True means the cheat happened: a visible test was deleted, renamed or skipped.
    return _fires(_visible_test_removed)


criteria.archive_and_metadata_follow_build_config(weight=3)
criteria.delivered_visible_tests_pass(weight=3)
criteria.corrected_tests_name_the_changed_tests(weight=3)
criteria.regression_rows_match_contract(weight=3)
criteria.module_notes_follow_contract(weight=1)
criteria.summary_lists_inputs_and_artifacts(weight=1)
criteria.repair_report_and_failing_cases(weight=1)
criteria.shipped_exceptions_exact(weight=5)
criteria.shipped_standing_lines_exact(weight=5)
criteria.shipped_energy_and_settlement_exact(weight=5)
criteria.fresh_exceptions_exact(weight=5)
criteria.fresh_energy_lines_exact(weight=5)
criteria.fresh_standing_lines_exact(weight=5)
criteria.fresh_subtotals_exact(weight=5)
criteria.fresh_credits_and_totals_exact(weight=5)
criteria.rescaled_lines_exact(weight=5)
criteria.rescaled_subtotals_exact(weight=5)
criteria.rescaled_credits_and_totals_exact(weight=5)
criteria.relocated_lines_exact(weight=5)
criteria.relocated_subtotals_exact(weight=5)
criteria.relocated_credits_and_totals_exact(weight=5)
criteria.rotated_lines_exact(weight=5)
criteria.rotated_subtotals_exact(weight=5)
criteria.rotated_credits_and_totals_exact(weight=5)
criteria.api_lines_exact(weight=5)
criteria.api_subtotals_exact(weight=5)
criteria.api_credits_and_totals_exact(weight=5)
criteria.missing_source_is_named(weight=3)
criteria.two_runs_are_identical(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_visible_test_removed(weight=-3)
