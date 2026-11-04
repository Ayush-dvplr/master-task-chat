#!/usr/bin/env python3
"""Structure QC: the deterministic shape checks for one input bundle.

What this script enforces (each check ID maps to a rule in the MD gates):

  S1-S10 bundle tree: naming, required files (solution/TRUTH.md and
         tests/reward.toml included; solve.py optional; nothing else),
         cheat/ and tests/test_weights.json forbidden, input kept in one or
         more named directories under environment/, forbidden files, CRLF line endings, and the agent image
         copying nothing from outside environment/, and every artifact
         directory writable by uid 1000 in the agent image, and the
         openhands-sdk agent runtime pre-baked into it, and the uid 1000
         agent account (with HOME) created in it.
  T1-T15 task.toml: parses, exact key ORDER per the authoritative template
         (extra sections fail), schema_version "1.4", absolute artifact
         paths, description/keywords/tags limits, a non-empty category,
         positive timings, junior > expert, environment_mode = "separate",
         the pinned per-role network_mode trio, the pinned corpus-wide values
         (task name included), authors naming a real person, and the fixed
         [verifier.env] judge wiring.
  X1-X3  bundle-wide text sweeps: em/en dash ban, unresolved placeholders
         and work markers, 100 MB per-file ceiling.

Every ID:

  S1  directory name matches ^[a-z0-9][a-z0-9-]{2,63}$.
  S2  every required file exists (solve.py is optional).
  S3  cheat/ (fail), tests/test_weights.json (fail), tests/rubric.json (fail);
      a trajectories/ directory of recorded runs at the root warns; any other
      entry outside the tree fails.
  S4  environment/ holds at least one input directory besides the Dockerfile
      (any name: data/, repo/, fixtures/...); every one holds at least one file
      and is copied into the image by a COPY/ADD in environment/Dockerfile.
  S5  no reward.txt, reward.json, reward-details.json, ctrf.json, .DS_Store,
      __pycache__/, .git/, .pytest_cache/ anywhere; the four grader-output
      names warn instead under trajectories/.
  S6  CRLF: fail in .sh files, warn elsewhere.
  S7  environment/Dockerfile copies nothing from outside environment/;
      wildcard sources warn.
  S8  every artifact's directory is writable by uid 1000 ([agent] user) in
      the image environment/Dockerfile builds (replayed: mkdir, chown, chmod,
      COPY --chown, WORKDIR, USER, useradd -u); root-owned or another uid
      fails, a user with no stated uid warns, /tmp is always writable.
  S9  environment/Dockerfile pre-bakes the openhands-sdk runtime: a venv at
      /opt/openhands-sdk-venv, openhands-sdk==1.55.1 openhands-tools==1.55.1
      litellm==1.105.0 fastapi pip-installed into it (uv or pip), a build-time
      "import openhands.sdk", chmod -R a+rX on the venv, and apt packages
      curl ca-certificates tmux.
  S10 environment/Dockerfile creates the uid 1000 agent account with a home
      (useradd -u 1000 ... -m) and sets ENV HOME.
  T1  task.toml parses.
  T2  root keys, required table order, required table keys and order,
      no extra sections, no docker_image, environment_mode = "separate".
  T3  schema_version is exactly "1.4".
  T4  artifacts: non-empty array of absolute paths, no "..", no backslash.
  T5  [task] description: non-empty, one paragraph, at most 100 words.
  T6  [task] keywords: at least one non-empty string.
  T7  [metadata] category: a non-empty string.
  T8  [metadata] tags: at least one non-empty string.
  T9  estimated_duration_sec and both time estimates positive.
  T10 junior_time_estimate_min strictly greater than expert's.
  T11 [verifier]/[agent] timeout_sec and build_timeout_sec positive.
  T12 network_mode per role, pinned hosts, no allow_internet anywhere.
  T13 pinned values ([task] name = terminal-bench/<dir> included) and
      positive-integer cpus/memory_mb/storage_mb.
  T14 authors: non-empty array of { name, email } tables; name is your own
      name in any capitalisation or script (blank, a placeholder like "Task
      Author", or digits/symbols fail); email domain is ethara.ai or a
      subdomain; an email that cannot be related to the name warns.
  T15 [verifier.env] is exactly OPENAI_API_KEY = "${OPENAI_API_KEY:-}".
  X1  no em/en dash in any text file; a text-named file read as binary warns.
  X2  unresolved generator placeholders fail; TODO/FIXME/XXX/PLACEHOLDER
      markers warn (read each in context).
  X3  no file over 100 MB.

Usage: python3 structure_qc.py /path/to/bundle
Exit codes: 0 = pass (warns allowed), 1 = fail, 2 = usage error.
"""

from __future__ import annotations

import re
import shlex
import sys
import tomllib
from itertools import permutations
from pathlib import Path
from typing import Any

FAILS: list[str] = []
WARNS: list[str] = []
PASSES: list[str] = []


def fail(check: str, msg: str) -> None:
    FAILS.append(f"FAIL [{check}] {msg}")


def warn(check: str, msg: str) -> None:
    WARNS.append(f"WARN [{check}] {msg}")


def ok(check: str, msg: str) -> None:
    PASSES.append(f"pass [{check}] {msg}")


def fails_for(check: str) -> int:
    return sum(1 for line in FAILS if line.startswith(f"FAIL [{check}] "))


FORBIDDEN_NAMES = {"reward.txt", "reward.json", "reward-details.json", "ctrf.json", ".DS_Store"}
FORBIDDEN_DIRS = {"__pycache__", ".git", ".pytest_cache"}
# Recorded agent runs. Delivery policy accepts a bundle that ships them, so the
# directory itself and the grader output inside it warn instead of failing: no
# Dockerfile copies this directory, so nothing in it reaches either container
# and nothing in it can influence a score. Everything outside it is unchanged.
TRAJECTORY_DIR = "trajectories"
# Grader output that is a genuine record of a past run when it sits under
# trajectories/. .DS_Store is never a run record, so it stays a fail anywhere.
RUN_RECORD_NAMES = {"reward.txt", "reward.json", "reward-details.json", "ctrf.json"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# An author field that credits nobody. Checked case-insensitively.
# A name made only of these words is a stand-in, not a person ("Task Author",
# "Your Name", "Test User"). Any one of the STRONG words anywhere marks it too.
PLACEHOLDER_WORDS = {"task", "tasks", "author", "authors", "name", "names", "your", "my",
                     "full", "first", "last", "user", "test", "tester", "sample", "example",
                     "default", "team", "admin", "owner", "creator", "maintainer", "dev",
                     "developer", "bundle", "terminal", "bench", "ethara", "person", "someone",
                     "me", "none", "null", "na", "n", "a", "unknown", "anonymous", "tbd", "todo",
                     "placeholder", "john", "jane", "doe", "foo", "bar", "xxx", "abc",
                     "ib", "model", "training", "role", "handle", "new", "final", "copy"}
# Words no person is called, so one of them anywhere marks the whole field a
# stand-in. The second line is what taskers actually typed instead of a name
# ("IB Created", "task creation", "QC fixes", "Anubis Harness", "task-generator").
STRONG_PLACEHOLDER_WORDS = {"author", "authors", "placeholder", "tbd", "todo", "unknown",
                            "anonymous", "yourname", "taskauthor", "doe", "example", "sample",
                            "created", "creation", "creator", "generator", "generated",
                            "remediation", "fixed", "fixes", "harness", "anubis", "harbor", "qc"}
AUTHOR_DOMAIN = "ethara.ai"


def is_placeholder_name(name: str) -> bool:
    words = [w for w in re.split(r"[^a-z]+", name.lower()) if w]
    if "<" in name or "{" in name:
        return True
    if not words:
        # A name in a non-Latin script has no words this vocabulary can judge.
        return not any(character.isalpha() for character in name)
    return all(w in PLACEHOLDER_WORDS for w in words) or any(w in STRONG_PLACEHOLDER_WORDS for w in words)
REQUIRED = ["instruction.md", "task.toml",
            "environment/Dockerfile", "solution/solve.sh", "solution/TRUTH.md",
            "tests/Dockerfile", "tests/test.sh", "tests/test_output.py",
            "tests/judge.toml", "tests/reward.toml"]
# Exact contents of each directory the tree fixes; anything else fails S3.
ALLOWED_ENTRIES = {
    "": {"instruction.md", "task.toml", "environment", "solution", "tests"},
    "environment": {"Dockerfile"},  # plus any input directories (S4)
    "solution": {"solve.sh", "solve.py", "TRUTH.md"},
    "tests": {"Dockerfile", "test.sh", "test_output.py", "judge.toml", "reward.toml"},
}

# Exact key order per the authoritative template. A table the template does
# not name, or a sub-table it does not name, fails.
ROOT_KEYS = ["schema_version", "artifacts"]
TABLE_ORDER = ["task", "metadata", "verifier", "agent", "environment"]
TABLE_KEYS = {
    "task": ["name", "version", "description", "keywords", "authors"],
    "metadata": ["category", "platforms", "tags", "estimated_duration_sec",
                 "expert_time_estimate_min", "junior_time_estimate_min",
                 "null_floor", "discrimination_weight"],
    "verifier": ["timeout_sec", "environment_mode", "network_mode",
                 "allowed_hosts", "env", "environment"],
    "agent": ["timeout_sec", "network_mode", "allowed_hosts", "user"],
    "environment": ["build_timeout_sec", "network_mode", "cpus", "memory_mb",
                    "storage_mb", "gpus", "mcp_servers"],
    "verifier.environment": ["network_mode", "allowed_hosts"],
}
# Sub-tables that are part of their parent's required key list.
REQUIRED_SUBTABLES = {"verifier": {"env", "environment"}}
JUDGE_HOSTS = ["api.openai.com", "*.openai.com"]
AGENT_HOSTS = ["api.anthropic.com", "api.z.ai"]
# Fixed judge wiring, byte-identical in every published task: copied, not authored.
VERIFIER_ENV = {"OPENAI_API_KEY": "${OPENAI_API_KEY:-}"}
# Values settled once for the whole corpus so bundles stay comparable; the
# reviewer checks them letter-exact rather than judging them per task.
PINNED = {
    ("task", "version"): "1.0.0",
    ("metadata", "platforms"): ["linux/amd64", "linux/arm64"],
    ("metadata", "null_floor"): 0.0,
    ("metadata", "discrimination_weight"): 1.0,
    ("agent", "user"): "1000:1000",
    ("environment", "gpus"): 0,
    ("environment", "mcp_servers"): [],
}


def is_text(p: Path) -> bool:
    """A file is treated as text when its first 8 KB contain no null byte and
    decode as UTF-8. Binary files (corpus blobs, images) are skipped by every
    text sweep in this script."""
    try:
        chunk = p.read_bytes()[:8192]
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def positive(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def positive_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def check_tree(bundle: Path) -> None:
    """S1-S6: the bundle tree contract.

    S1  directory name matches ^[a-z0-9][a-z0-9-]{2,63}$ (lowercase kebab).
    S2  every required file exists: instruction.md, task.toml,
        environment/Dockerfile, solution/solve.sh, solution/TRUTH.md,
        tests/{Dockerfile, test.sh, test_output.py, judge.toml, reward.toml}.
        solution/solve.py is the only optional file.
    S3  three entries are called out by name: a cheat/ directory at the
        bundle root fails, since a shipped bundle must not carry an attack on
        its own grader; tests/test_weights.json fails, since test weights are
        registered in test_output.py and a second copy drifts;
        tests/rubric.json fails, since the judged channel is tests/judge.toml
        only and a second file is a second source of truth. A trajectories/
        directory of recorded agent runs at the bundle root warns instead of
        failing: no Dockerfile copies it, so it reaches neither container and
        cannot influence a score. Any other entry
        at the bundle root, in environment/, solution/ or tests/ fails: each
        holds exactly the entries the tree names. environment/ is the one
        open folder: besides the Dockerfile it holds the task's input
        directories, under whatever names the task needs, and nothing else
        (a loose file there fails).
    S4  environment/ holds at least one input directory. Each one carries at
        least one file and is a COPY/ADD source in environment/Dockerfile, so
        it reaches the agent at the path that COPY names (conventionally
        /app/<dir>); a directory nothing copies is dead weight the agent never
        sees, and fails.
    S5  forbidden anywhere: reward.txt / reward.json / reward-details.json /
        ctrf.json (runtime outputs of grading: shipping one means a pre-baked
        score), .DS_Store, __pycache__/, .git/, .pytest_cache/. The four
        grader-output names warn instead of failing when they sit under
        trajectories/, where they are the record of a past run rather than a
        score staged for this bundle's grading; .DS_Store is never a run
        record, so it fails there too.
    S6  CRLF line endings: fail in .sh files (the shebang becomes "bash\\r"
        and the script never runs, so no reward is written), warn elsewhere.
    """
    if not NAME_RE.match(bundle.name):
        fail("S1", f"bundle dir name '{bundle.name}' violates ^[a-z0-9][a-z0-9-]{{2,63}}$")
    else:
        ok("S1", "bundle name format")

    for rel in REQUIRED:
        if not (bundle / rel).is_file():
            fail("S2", f"missing required file: {rel}")
    if not fails_for("S2"):
        ok("S2", "all required files present")

    if (bundle / "cheat").exists():
        fail("S3", "cheat/ must not exist: a shipped bundle must not carry an attack "
                   "on its own grader. Delete it.")
    if (bundle / "tests" / "test_weights.json").exists():
        fail("S3", "tests/test_weights.json must not exist: weights are registered in "
                   "test_output.py with criteria.<name>(weight=W). Delete it.")
    if (bundle / "tests" / "rubric.json").exists():
        fail("S3", "tests/rubric.json must not exist: the judged channel is "
                   "tests/judge.toml only, and a second file is a second source of "
                   "truth for one channel. Delete it.")

    named = {"cheat", "tests/test_weights.json", "tests/rubric.json"}
    for folder, allowed in ALLOWED_ENTRIES.items():
        d = bundle / folder if folder else bundle
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            rel = p.relative_to(bundle).as_posix()
            if p.name in allowed or rel in named or p.name in FORBIDDEN_NAMES | FORBIDDEN_DIRS:
                continue
            if folder == "environment" and p.is_dir() and not p.name.startswith("."):
                continue
            if not folder and p.is_dir() and p.name == TRAJECTORY_DIR:
                warn("S3", f"{rel}/ holds recorded agent runs and is accepted by delivery "
                           "policy: no Dockerfile copies it, so it reaches neither container "
                           "and cannot influence a score. Delete it for a clean root.")
                continue
            only = (f"only {sorted(allowed)} and input directories" if folder == "environment"
                    else f"only {sorted(allowed)}")
            fail("S3", f"unexpected entry {rel}: {folder + '/' if folder else 'the bundle root'} holds "
                       f"{only}. Delete it.")

    env = bundle / "environment"
    dirs = sorted(p for p in env.iterdir() if p.is_dir() and not p.name.startswith(".")
                  and p.name not in FORBIDDEN_DIRS) if env.is_dir() else []
    if not dirs:
        fail("S4", "environment/ holds no input directory: the input the agent works on "
                   "lives in one or more directories next to the Dockerfile (e.g. data/)")
    df = env / "Dockerfile"
    copied: set[str] = set()
    for _, _, srcs in (copy_sources(df) if df.is_file() else []):
        for src in srcs:
            name = src.strip("./").split("/")[0]
            if name in {"", "*"}:
                # COPY . /app/ takes the whole context, carrying every input directory.
                copied |= {d.name for d in dirs}
            else:
                copied.add(name)
    for d in dirs:
        files = [p for p in d.rglob("*") if p.is_file()]
        if not files:
            fail("S4", f"environment/{d.name}/ carries no input files")
        if d.name not in copied:
            fail("S4", f"environment/{d.name}/ is never copied by environment/Dockerfile "
                       f"(add COPY {d.name} /app/{d.name}); the agent would never see it")
    if dirs and not fails_for("S4"):
        ok("S4", "input directories " + ", ".join(
            f"{d.name}/ ({sum(1 for p in d.rglob('*') if p.is_file())} files)" for d in dirs)
           + " all copied into the image")

    for p in sorted(bundle.rglob("*")):
        rel = p.relative_to(bundle)
        in_trajectory = rel.parts[:1] == (TRAJECTORY_DIR,)
        if p.name in FORBIDDEN_NAMES:
            if in_trajectory and p.name in RUN_RECORD_NAMES:
                warn("S5", f"{rel} is grader output from a recorded run, accepted by "
                           "delivery policy: nothing copies trajectories/ into either "
                           "container, so it is no pre-baked score for this bundle.")
            else:
                fail("S5", f"forbidden file: {rel}")
        if p.is_dir() and p.name in FORBIDDEN_DIRS:
            fail("S5", f"forbidden directory: {rel}")
        if p.is_file() and is_text(p) and b"\r\n" in p.read_bytes():
            if p.suffix == ".sh":
                fail("S6", f"CRLF line endings in {rel} (shebang becomes bash\\r, no reward written)")
            else:
                warn("S6", f"CRLF line endings in {rel} (hygiene; parsers tolerate it)")


AGENT_FORBIDDEN_NAMES = ("TRUTH.md", "task.toml", "solution", "tests")


def copy_sources(df: Path) -> list[tuple[int, str, list[str]]]:
    """(line number, line, source tokens) for every COPY/ADD in a Dockerfile
    that reads the build context (COPY --from=<stage> reads a build stage)."""
    out: list[tuple[int, str, list[str]]] = []
    text = df.read_text(encoding="utf-8", errors="replace")
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split(None, 1)
        if len(head) < 2 or head[0].upper() not in {"COPY", "ADD"} or "--from" in head[1]:
            continue
        args = [a for a in head[1].split() if not a.startswith("--")]
        if len(args) >= 2:
            out.append((i, line, args[:-1]))
    return out


def check_agent_image_scope(bundle: Path) -> None:
    """S7: the agent image must not copy anything from outside environment/.

    The Docker build context for environment/Dockerfile is environment/, so a
    correct bundle can only reach its input directories. Authors sometimes
    widen this by hand, and a widened context is how solution/TRUTH.md, the
    oracle or the tests would land in the agent's filesystem. TRUTH.md is the
    whole worked answer, so this is the difference between a hard task and a
    free one. A wildcard source warns: confirm by reading that it cannot match
    tests/ or solution/ material.
    """
    df = bundle / "environment" / "Dockerfile"
    if not df.is_file():
        return
    for i, line, srcs in copy_sources(df):
        for src in srcs:
            if src in {".", "./"}:
                fail("S7", f"environment/Dockerfile:{i} copies the whole build context "
                           f"({line!r}); narrow it to the exact paths the agent needs")
            elif src == ".." or src.startswith("../"):
                fail("S7", f"environment/Dockerfile:{i} reaches outside environment/ "
                           f"({line!r}); solution/ holds the oracle and TRUTH.md, "
                           f"tests/ holds the grader, and none of it may reach the agent")
            elif src.lstrip("./").split("/")[0] in AGENT_FORBIDDEN_NAMES:
                fail("S7", f"environment/Dockerfile:{i} copies {src!r}, which lives "
                           f"outside environment/ and must never reach the agent")
            elif any(ch in src for ch in "*?["):
                warn("S7", f"environment/Dockerfile:{i} copies a wildcard {src!r}; confirm "
                           "it cannot match tests/ or solution/ material")
    if not fails_for("S7"):
        ok("S7", "agent image copies nothing from outside environment/")


NAME_PUNCTUATION = " -.'\u2019"


def name_words(name: str) -> list[str]:
    return [w for w in re.split(rf"[{re.escape(NAME_PUNCTUATION)}]+", name.strip()) if w]


def is_name_shaped(name: str) -> bool:
    """A person's name in any script, judged on content rather than style.

    Capitalisation, script and initials are not judged: `Anjali kumari`,
    `JOSE GARCIA`, `Ram K. Lakhan`, `van der Berg`, `O'Brien` and non-Latin
    names all qualify. Only digits, `@`, underscores and other symbols
    disqualify, which is what separates a name from a handle like
    `task_creator` or an email.
    """
    text = name.strip()
    if not text or any(character.isdigit() for character in text):
        return False
    if not all(character.isalpha() or character in NAME_PUNCTUATION for character in text):
        return False
    words = name_words(text)
    return bool(words) and max(len(w) for w in words) >= 2


def email_in_domain(email: str) -> bool:
    host = email.strip().lower().rsplit("@", 1)[-1]
    return host == AUTHOR_DOMAIN or host.endswith("." + AUTHOR_DOMAIN)


def name_matches_email(name: str, email: str) -> bool:
    """True when the address plausibly belongs to the named person.

    Any name word of three letters or more appearing in the local part is
    enough, so the intern suffixes in real addresses relate fine
    (`abdus.samadint17` to `Abdus Samad Ali`). Initials count too (`rl`,
    `r.k.lakhan`). A name with no Latin words cannot be compared, so it is
    accepted rather than warned about. `r43243` still fails to relate.
    """
    local = re.sub(r"[^a-z]", "", email.strip().split("@", 1)[0].lower())
    words = [w for w in re.split(r"[^a-z]+", name.lower()) if w]
    if not words:
        return True
    if not local:
        return False
    if any(len(w) >= 3 and w in local for w in words):
        return True
    initials = "".join(w[0] for w in words)
    if len(initials) > 1 and (local.startswith(initials) or local.startswith(initials[::-1])):
        return True

    def build(rest: str, ws: tuple[str, ...], whole: bool) -> bool:
        if not ws:
            return not rest and whole
        w, tail = ws[0], ws[1:]
        return ((rest.startswith(w) and build(rest[len(w):], tail, True))
                or (rest.startswith(w[0]) and build(rest[1:], tail, whole))
                or build(rest, tail, whole))

    return any(build(local, p, False) for p in permutations(words[:4]))


def check_authors(authors: object) -> None:
    """T14: [task].authors, whose malformed shapes fail invisibly.

    harbor's Author model requires a non-empty ``name`` and rejects bare
    strings. On rejection the task directory stops being recognised as a task
    at all, so the bundle disappears from discovery instead of raising: nothing
    here can be relaxed on the grounds that "it still parses". The name
    must be a name rather than a handle or a stand-in, in whatever
    capitalisation and script the author uses; an email that cannot be
    related to the name warns, so the tasker confirms the author.
    """
    if not isinstance(authors, list) or not authors:
        fail("T14", "[task] authors must be a non-empty array of { name, email } tables: "
                    "the person who created the task must be credited")
        return
    for i, entry in enumerate(authors):
        where = f"[task] authors[{i}]"
        if not isinstance(entry, dict):
            fail("T14", f'{where} must be a table like {{ name = "Ada Lovelace", '
                        f'email = "ada.lovelace@company.ai" }}, got {entry!r}')
            continue
        extra = sorted(set(entry) - {"name", "email"})
        if extra:
            fail("T14", f"{where} has unexpected keys {extra}; only name and email are allowed")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            fail("T14", f"{where} name is blank. Fill in your own full name, like 'Ram Lakhan'.")
        elif EMAIL_RE.match(name.strip()):
            fail("T14", f"{where} name is an email address. name holds the author's "
                        "name and nothing else; the address belongs in email.")
        elif is_placeholder_name(name):
            fail("T14", f"{where} name {name!r} is a placeholder, not a person. Fill in your own full name, like 'Ram Lakhan'.")
        elif not is_name_shaped(name.strip()):
            fail("T14", f"{where} name {name!r} is not a name: it holds digits or symbols. "
                        "Any capitalisation, script, initial or particle is fine, so write your "
                        "own name as you spell it, like 'Ram Lakhan'.")
        elif len(name_words(name)) == 1:
            warn("T14", f"{where} name {name!r} is a single word; give your full name unless "
                        "that really is how you are credited")
        email = entry.get("email")
        if not isinstance(email, str) or not EMAIL_RE.match(email.strip()) or "<" in email:
            fail("T14", f"{where} email {email!r} is missing or not a well-formed address")
        elif not email_in_domain(email):
            fail("T14", f"{where} email {email!r} must be your ethara.ai address (the domain is "
                        f"{AUTHOR_DOMAIN} or a subdomain of it)")
        elif (isinstance(name, str) and is_name_shaped(name.strip())
              and not is_placeholder_name(name) and not name_matches_email(name, email)):
            warn("T14", f"{where} name {name!r} does not match the email {email!r}; "
                        "confirm it is the author")
    if not fails_for("T14"):
        plural = "entry" if len(authors) == 1 else "entries"
        ok("T14", f"[task] authors: {len(authors)} {plural}, valid shape")


def resolve(cfg: dict, path: str) -> Any:
    node: Any = cfg
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def check_shape(cfg: dict) -> None:
    """T2: root keys, required table order, and each required table's keys
    exactly and in template order. A table or sub-table the template does
    not name is an extra section and fails.
    docker_image is a publish-time output and fails wherever it appears.
    [verifier] environment_mode MUST be "separate": anything else (including
    absent) means tests/Dockerfile is never built and agent-visible files
    grade the agent."""
    root = [k for k in cfg if not isinstance(cfg[k], dict)]
    if root != ROOT_KEYS:
        fail("T2", f"root keys must be exactly {ROOT_KEYS} in order, found {root}")
    tables = [k for k in cfg if isinstance(cfg[k], dict) and k in TABLE_ORDER]
    if tables != [t for t in TABLE_ORDER if t in cfg]:
        fail("T2", f"required tables must appear in order {TABLE_ORDER}, found {tables}")
    for k in cfg:
        if isinstance(cfg[k], dict) and k not in TABLE_ORDER:
            fail("T2", f"[{k}] is not in the template: extra sections fail. Delete it.")
    for tbl in TABLE_ORDER:
        table = cfg.get(tbl)
        if isinstance(table, dict):
            for k, v in table.items():
                if isinstance(v, dict) and k not in REQUIRED_SUBTABLES.get(tbl, set()):
                    fail("T2", f"[{tbl}.{k}] is not in the template: extra sections "
                               "fail. Delete it.")
    for tbl, keys in TABLE_KEYS.items():
        table = resolve(cfg, tbl)
        if not isinstance(table, dict):
            fail("T2", f"[{tbl}] is missing: the authoritative template requires it")
            continue
        required_sub = REQUIRED_SUBTABLES.get(tbl, set())
        got = [k for k in table if not isinstance(table[k], dict) or k in required_sub]
        if "docker_image" in got:
            fail("T2", f"[{tbl}] docker_image is a publish-time output, not authored "
                       "input: harbor builds the image from the Dockerfile and records "
                       "the digest when the task is published. Delete the key.")
            got.remove("docker_image")
        if got != keys:
            fail("T2", f"[{tbl}] keys must be exactly {keys} in order, found {got}")
    mode = cfg.get("verifier", {}).get("environment_mode")
    if mode != "separate":
        fail("T2", f'[verifier] environment_mode must be "separate", got {mode!r} '
                   "(anything else means tests/Dockerfile is never built and the "
                   "verifier runs inside the agent container)")
    if not fails_for("T2"):
        ok("T2", "template shape, key order, environment_mode = separate")


def check_network(cfg: dict, raw: str) -> None:
    """T12: network_mode, declared per role, every role pinned.

    [environment] is "no-network" with no allowed_hosts: our tasks are
    offline tasks, and the key defaults to "public", so an omitted key ships
    an online task silently. [verifier] is "allowlist" with exactly the judge
    endpoint, and [verifier.environment] repeats both values exactly. [agent]
    is "allowlist" with exactly the model-provider hosts. allow_internet must
    not appear anywhere in task.toml: network_mode is the only network key.
    """
    envt = cfg.get("environment", {})
    vrf = cfg.get("verifier", {})
    agt = cfg.get("agent", {})
    if envt.get("network_mode") != "no-network":
        fail("T12", '[environment] network_mode must be "no-network": our tasks are '
             "offline tasks, solvable from the shipped image and environment/ input "
             f"alone. Got {envt.get('network_mode')!r}")
    if "allowed_hosts" in envt:
        fail("T12", "[environment] allowed_hosts is an extra key: the role is pinned "
             'to "no-network", which reaches nothing and so names no hosts')
    if vrf.get("network_mode") != "allowlist":
        fail("T12", '[verifier] network_mode must be "allowlist": the judged channel '
             "is scored by an LLM the verifier reaches over the network. "
             f"Got {vrf.get('network_mode')!r}")
    if vrf.get("allowed_hosts") != JUDGE_HOSTS:
        fail("T12", f"[verifier] allowed_hosts must be exactly {JUDGE_HOSTS} (the judge "
             f"endpoint), got {vrf.get('allowed_hosts')!r}")
    venvt = vrf.get("environment")
    if not isinstance(venvt, dict):
        fail("T12", "[verifier.environment] is missing: it repeats the verifier network "
             "policy for the verifier's own container and the template requires it")
    elif venvt.get("network_mode") != "allowlist" or venvt.get("allowed_hosts") != JUDGE_HOSTS:
        fail("T12", "[verifier.environment] must repeat [verifier] network_mode "
             f'"allowlist" and allowed_hosts {JUDGE_HOSTS} exactly, got '
             f"{venvt.get('network_mode')!r} / {venvt.get('allowed_hosts')!r}")
    if agt.get("network_mode") != "allowlist":
        fail("T12", '[agent] network_mode must be "allowlist": the agent harness has to '
             f"reach its own model provider. Got {agt.get('network_mode')!r}")
    if agt.get("allowed_hosts") != AGENT_HOSTS:
        fail("T12", f"[agent] allowed_hosts must be exactly {AGENT_HOSTS} (the model "
             f"provider hosts), got {agt.get('allowed_hosts')!r}")
    if "allow_internet" in raw:
        fail("T12", "allow_internet must not appear in task.toml: network_mode is the "
             "only network key")
    if not fails_for("T12"):
        ok("T12", "network_mode pinned per role")


def check_pinned(cfg: dict, bundle: Path) -> None:
    """T13: [task] name is terminal-bench/<bundle dir name>; the corpus-wide
    values are letter- and type-exact; cpus, memory_mb and storage_mb are
    positive integers."""
    want_name = f"terminal-bench/{bundle.name}"
    if cfg.get("task", {}).get("name") != want_name:
        fail("T13", f"[task] name must be {want_name!r}, got {cfg.get('task', {}).get('name')!r}")
    for (tbl, key), want in PINNED.items():
        got_val = cfg.get(tbl, {}).get(key)
        if got_val != want or type(got_val) is not type(want):
            fail("T13", f"[{tbl}] {key} is pinned to {want!r} for every bundle in the "
                 f"corpus, got {got_val!r}")
    envt = cfg.get("environment", {})
    for key in ("cpus", "memory_mb", "storage_mb"):
        if not positive_int(envt.get(key)):
            fail("T13", f"[environment] {key} must be a positive integer, got {envt.get(key)!r}")
    if not fails_for("T13"):
        ok("T13", "pinned values exact")


def check_toml(bundle: Path) -> dict | None:
    """T1-T15: task.toml must match the authoritative template exactly.

    T1  parses as TOML.
    T2  exact shape (see check_shape).
    T3  schema_version is exactly "1.4".
    T4  artifacts: non-empty list of ABSOLUTE container paths (the agent's
        deliverables the harness ferries into the verifier). Relative/bare
        names fail: docker compose cp resolves them against the image
        WORKDIR, which differs across images and providers. No "..", no
        backslashes.
    T5  description: non-empty, one paragraph, at most 100 words.
    T6  keywords: at least one non-empty string.
    T7  category: a non-empty string. There is no fixed vocabulary and no
        difficulty key; whether it describes the dominant work is judged by
        reading.
    T8  tags: at least one non-empty string.
    T9  estimated_duration_sec, expert/junior_time_estimate_min: positive.
    T10 junior_time_estimate_min strictly greater than expert's.
    T11 verifier/agent timeout_sec and build_timeout_sec: positive numbers.
    T12 network policy per role (see check_network).
    T13 pinned values (see check_pinned).
    T14 authors (see check_authors).
    T15 [verifier.env] is the fixed judge wiring: exactly OPENAI_API_KEY,
        holding its ${VAR:-default} placeholder. A value that is not a
        placeholder is a credential shipping to the client.

    Returns the parsed config.
    """
    p = bundle / "task.toml"
    if not p.is_file():
        return None
    raw = p.read_text(encoding="utf-8", errors="replace")
    try:
        cfg = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as e:
        fail("T1", f"task.toml does not parse: {e}")
        return None
    ok("T1", "task.toml parses")

    check_shape(cfg)

    sv = cfg.get("schema_version")
    if sv != "1.4":
        fail("T3", f'schema_version must be "1.4", got {sv!r}')

    arts = cfg.get("artifacts")
    if not isinstance(arts, list) or not arts or not all(isinstance(a, str) for a in arts):
        fail("T4", "artifacts must be a non-empty array of strings")
    else:
        for a in arts:
            if not a.startswith("/"):
                fail("T4", f"artifact must be an absolute container path (harness "
                     f"resolves relative paths against the image WORKDIR, which is "
                     f"undefined across providers/images): {a!r}")
            elif ".." in a.split("/"):
                fail("T4", f"artifact path must not contain '..' (harness rejects it): {a!r}")
            elif "\\" in a:
                fail("T4", f"artifact path must use forward slashes: {a!r}")
        if not fails_for("T4"):
            ok("T4", f"artifacts (absolute container paths): {arts}")

    task = cfg.get("task", {})
    md = cfg.get("metadata", {})
    desc = task.get("description")
    if not isinstance(desc, str) or not desc.strip():
        fail("T5", "[task] description missing or empty")
    else:
        if len(desc.split()) > 100:
            fail("T5", f"[task] description over 100 words ({len(desc.split())})")
        if re.search(r"\n\s*\n", desc.strip()):
            fail("T5", "[task] description is more than one paragraph")
    for check, tbl, key, val in (("T6", "task", "keywords", task.get("keywords")),
                                 ("T8", "metadata", "tags", md.get("tags"))):
        if not isinstance(val, list) or not val or not all(isinstance(x, str) and x.strip() for x in val):
            fail(check, f"[{tbl}] {key} must list at least one non-empty string")

    check_authors(task.get("authors"))

    cat = md.get("category")
    if not isinstance(cat, str) or not cat.strip():
        fail("T7", f"[metadata] category must be a non-empty string, got {cat!r}")
    else:
        ok("T7", f"[metadata] category: {cat!r} (no fixed vocabulary; whether it "
                 "describes the dominant work is judged by reading)")
    for key in ("estimated_duration_sec", "expert_time_estimate_min", "junior_time_estimate_min"):
        if not positive(md.get(key)):
            fail("T9", f"metadata.{key} must be a positive number, got {md.get(key)!r}")
    exp, jun = md.get("expert_time_estimate_min"), md.get("junior_time_estimate_min")
    if positive(exp) and positive(jun) and jun <= exp:
        fail("T10", f"junior_time_estimate_min ({jun}) must be > expert_time_estimate_min ({exp})")

    for label, v in (("[verifier] timeout_sec", cfg.get("verifier", {}).get("timeout_sec")),
                     ("[agent] timeout_sec", cfg.get("agent", {}).get("timeout_sec")),
                     ("[environment] build_timeout_sec",
                      cfg.get("environment", {}).get("build_timeout_sec"))):
        if not positive(v):
            fail("T11", f"{label} must be a positive number, got {v!r}")

    check_network(cfg, raw)
    check_pinned(cfg, bundle)

    venv = cfg.get("verifier", {}).get("env")
    if venv == VERIFIER_ENV:
        ok("T15", "[verifier.env] judge wiring exact")
    elif isinstance(venv, dict) and any(isinstance(v, str) and v and not v.startswith("${")
                                        for v in venv.values()):
        fail("T15", "[verifier.env] holds a literal value, not a ${VAR:-} placeholder. If "
             "that is a real credential it is now shipping to the client: rotate it and "
             "restore the placeholder.")
    else:
        fail("T15", f"[verifier.env] must be exactly {VERIFIER_ENV}, got {venv!r}")

    return cfg


DASH_RE = re.compile("[\u2013\u2014]")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}|__[A-Z][A-Z0-9_]*__|<TAG>")
WORK_MARKER_RE = re.compile(r"\b(TODO|FIXME|XXX|PLACEHOLDER)\b")
# A skipped binary is only worth reporting when its name says it should have
# been text, since a corpus of spreadsheets and archives is ordinary.
TEXT_SUFFIXES = {
    ".bash", ".cfg", ".conf", ".css", ".csv", ".env", ".html", ".ini", ".js",
    ".json", ".jsonl", ".log", ".md", ".properties", ".py", ".rst", ".sh",
    ".sql", ".toml", ".ts", ".tsv", ".txt", ".xml", ".yaml", ".yml",
}
TEXT_NAMES = {"Dockerfile", "Makefile", "README", "LICENSE", "CHANGELOG"}
AGENT_UID = "1000"
WORLD_WRITABLE_MODES = re.compile(r"^(0*[0-7]{0,2}[0-7][0-7][2367]|[ugo]*[ao][ugoa]*\+[rwxXst]*w[rwxXst]*)$")


def dockerfile_instructions(df: Path) -> list[tuple[int, str, str]]:
    """(first line number, OPCODE, argument text) per instruction, with backslash
    continuations joined and comment lines inside a continuation dropped."""
    out: list[tuple[int, str, str]] = []
    buf: list[str] = []
    start = 0
    for i, raw in enumerate(df.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if line.startswith("#") or (not line and not buf):
            continue
        if not buf:
            start = i
        if line.endswith("\\"):
            buf.append(line[:-1])
            continue
        buf.append(line)
        text = " ".join(buf).strip()
        buf = []
        head = text.split(None, 1)
        if head:
            out.append((start, head[0].upper(), head[1] if len(head) > 1 else ""))
    return out


def _abs(path: str, workdir: str) -> str:
    path = path.strip().strip('"').strip("'")
    if not path.startswith("/"):
        path = f"{workdir.rstrip('/')}/{path.removeprefix('./')}"
    parts: list[str] = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return "/" + "/".join(parts)


def _ancestors(path: str) -> list[str]:
    """path itself first, then each parent up to /."""
    out = [path]
    while path != "/":
        path = path.rsplit("/", 1)[0] or "/"
        out.append(path)
    return out


def image_ownership(df: Path) -> dict[str, str]:
    """Replay the final stage of a Dockerfile and return the owner of every path
    it creates, copies to or changes.

    owner is "agent" (uid 1000 owns it), "world" (world-writable), "root" (root
    or a user created with another uid), or "user:<name>" for a user whose uid
    the Dockerfile does not state (a base-image user, a variable, a useradd
    without -u).
    Only paths the Dockerfile creates, copies to or changes are known; the base
    image's own directories are not.
    """
    owner: dict[str, str] = {}
    agent_names = {AGENT_UID}
    other_names = {"root", "0"}
    workdir, user = "/", "root"

    def who(name: str) -> str:
        name = name.split(":", 1)[0]
        if name in agent_names:
            return "agent"
        return "root" if name in other_names else f"user:{name}"

    def create(path: str, as_user: str) -> None:
        for p in _ancestors(path):
            if p in owner:
                break
            owner[p] = who(as_user)

    def set_owner(path: str, value: str, recursive: bool) -> None:
        create(path, "root")
        owner[path] = value
        if recursive:
            for p in owner:
                if p.startswith(path.rstrip("/") + "/"):
                    owner[p] = value

    for _, op, arg in dockerfile_instructions(df):
        if op == "FROM":
            owner, workdir, user = {}, "/", "root"
        elif op == "USER":
            user = arg.strip()
        elif op == "WORKDIR":
            workdir = _abs(arg, workdir)
            create(workdir, user)
        elif op in {"COPY", "ADD"} and "--from" not in arg:
            flags = [a for a in arg.split() if a.startswith("--")]
            args = [a for a in arg.split() if not a.startswith("--")]
            if len(args) < 2:
                continue
            chown = next((f.split("=", 1)[1] for f in flags if f.startswith("--chown=")), None)
            dest = _abs(args[-1], workdir)
            create(dest, user)
            # COPY/ADD write root-owned files whatever USER says; only --chown changes that
            owner[dest] = who(chown) if chown else "root"
        elif op == "RUN" and not arg.lstrip().startswith("["):
            for cmd in re.split(r"&&|\|\||;|\|", arg):
                try:
                    words = shlex.split(cmd, comments=True)
                except ValueError:
                    words = cmd.split()
                if not words:
                    continue
                tool, rest = words[0].rsplit("/", 1)[-1], words[1:]
                opts = [w for w in rest if w.startswith("-")]
                plain = [w for w in rest if not w.startswith("-")]
                recursive = any(o in {"-R", "--recursive"} or (o.startswith("-") and not o.startswith("--") and "R" in o) for o in opts)
                if tool in {"useradd", "adduser"} and plain:
                    uid = None
                    for j, w in enumerate(rest):
                        if w in {"-u", "--uid"} and j + 1 < len(rest):
                            uid = rest[j + 1]
                        elif w.startswith("--uid="):
                            uid = w.split("=", 1)[1]
                    name = plain[-1]
                    if uid == AGENT_UID:
                        agent_names.add(name)
                    elif uid is not None:
                        other_names.add(name)
                elif tool == "mkdir":
                    for p in plain:
                        create(_abs(p, workdir), user)
                elif tool == "chown" and len(plain) >= 2:
                    value = who(plain[0])
                    for p in plain[1:]:
                        set_owner(_abs(p, workdir), value, recursive)
                elif tool == "chmod" and len(plain) >= 2 and WORLD_WRITABLE_MODES.match(plain[0]):
                    for p in plain[1:]:
                        set_owner(_abs(p, workdir), "world", recursive)
    return owner


def artifact_write_problems(df: Path, artifacts: list[str]) -> tuple[list[str], list[str]]:
    """(fail messages, warn messages) for artifacts uid 1000 cannot write.

    The artifact's directory is judged by the deepest path the Dockerfile
    knows on its chain: the directory itself must be agent-owned or
    world-writable, or, when only a parent is known, that parent must be (the
    oracle can then create the rest). /tmp is writable in every image.
    """
    owner = image_ownership(df)
    groups: dict[tuple[str, str], list[str]] = {}
    for art in artifacts:
        if not isinstance(art, str) or not art.startswith("/"):
            continue
        parent = _abs(art, "/").rsplit("/", 1)[0] or "/"
        known = next((p for p in _ancestors(parent) if p in owner), None)
        if known is None or known == "/":
            if parent == "/tmp" or parent.startswith("/tmp/"):
                continue
            groups.setdefault(("missing", parent), []).append(art)
        elif owner[known] == "root" or owner[known].startswith("user:"):
            groups.setdefault((owner[known], known), []).append(art)
    fails: list[str] = []
    warns: list[str] = []
    for (state, path), arts in groups.items():
        which = arts[0] if len(arts) == 1 else f"{len(arts)} artifacts ({arts[0]}, ...)"
        if state == "missing":
            fails.append(f"{which}: environment/Dockerfile never creates or chowns {path} "
                         f"(or a parent), so it is root-owned and uid {AGENT_UID} cannot write it")
        elif state == "root":
            fails.append(f"{which}: {path} is not owned by uid {AGENT_UID} in the image "
                         f"(root or another uid), so the agent and the oracle cannot write it; "
                         f"chown it to {AGENT_UID}:{AGENT_UID} after the last COPY into it")
        else:
            warns.append(f"{which}: {path} is owned by {state[5:]!r}, a user created "
                         f"without an explicit uid; confirm it is uid {AGENT_UID}")
    return fails, warns


OH_VENV = "/opt/openhands-sdk-venv"
OH_PACKAGES = {"openhands-sdk": "1.55.1", "openhands-tools": "1.55.1", "litellm": "1.105.0", "fastapi": None}
OH_APT = ("curl", "ca-certificates", "tmux")


def openhands_problems(df: Path) -> list[str]:
    """Missing pieces of the pre-baked openhands-sdk runtime in the final stage.

    The harness runs the openhands-sdk agent from /opt/openhands-sdk-venv and
    only installs it (over the network) when that venv cannot import
    openhands.sdk; under [environment] network_mode = "no-network" that install
    cannot run, so the image must carry it. Any install style passes (uv or
    python -m venv + pip) as long as every piece is there. openhands-sdk and
    openhands-tools are pinned to 1.55.1 and litellm to 1.105.0 (litellm
    1.106.0 fails to import with the mcp package openhands pulls in); fastapi
    is unpinned.
    """
    runs: list[str] = []
    for _, op, arg in dockerfile_instructions(df):
        if op == "FROM":
            runs = []
        elif op == "RUN":
            runs.append(arg)
    text = "\n".join(runs)
    venv = re.escape(OH_VENV)
    problems: list[str] = []
    if not re.search(rf"(-m\s+venv|\buv\s+venv|\bvirtualenv)\b[^\n&;|]*{venv}/?(\s|$|&|;)", text):
        problems.append(f"no virtualenv created at {OH_VENV} (python3.12 -m venv {OH_VENV} or uv venv {OH_VENV})")
    install_runs = [r for r in runs if re.search(r"\bpip3?\s+install\b", r) and OH_VENV in r]
    for pkg, pin in OH_PACKAGES.items():
        specs = [m.group(1) for r in install_runs
                 for m in re.finditer(rf"(?<![\w.-])({re.escape(pkg)}(?:[=<>!~]=?[^\s'\"&;|]*)?)(?=[\s'\"&;|]|$)", r)]
        if not specs:
            want = f"{pkg}=={pin}" if pin else pkg
            problems.append(f"{pkg} is not pip-installed into {OH_VENV} (install {want})")
        elif pin and f"{pkg}=={pin}" not in specs:
            problems.append(f"{pkg} installed as {specs[0]!r}; pin exactly {pkg}=={pin}")
    if not re.search(rf"{venv}/bin/python3?(\.\d+)?\s+-c\s+['\"]\s*import\s+openhands\.sdk", text):
        problems.append(f'no build-time import check ({OH_VENV}/bin/python -c "import openhands.sdk")')
    if not re.search(rf"chmod\s+(-\S*R\S*|--recursive)\s+(\S*[ao]\S*\+\S*r\S*|0?7[0-7][5-7])\s+{venv}/?(\s|$|&|;)", text):
        problems.append(f"{OH_VENV} is not made readable for uid 1000 (chmod -R a+rX {OH_VENV})")
    apt_runs = [r for r in runs if re.search(r"\b(apt-get|apt)\s+install\b|\bapk\s+add\b", r)]
    for pkg in OH_APT:
        if not any(re.search(rf"(?<![\w.-]){re.escape(pkg)}(?![\w.-])", r) for r in apt_runs):
            problems.append(f"system package {pkg} is not installed (apt-get install -y --no-install-recommends curl ca-certificates tmux)")
    return problems


AGENT_USER_RE = re.compile(r"\b(useradd|adduser)\b(?=[^\n&;|]*(?:-u|--uid)[\s=]+1000\b)")
CREATE_HOME_RE = re.compile(r"(?:^|\s)(?:-m|--create-home|-\w*m\w*)(?=\s|$)")


def agent_user_problems(df: Path) -> list[str]:
    """Missing pieces of the uid 1000 agent account in the final stage.

    [agent] user = "1000:1000" runs the agent and the oracle as uid 1000. The
    image must create that account with a home directory and point HOME at it,
    or tools that write under $HOME (uv, pip, the agent itself) fail.
    """
    runs: list[str] = []
    envs: list[str] = []
    for _, op, arg in dockerfile_instructions(df):
        if op == "FROM":
            runs, envs = [], []
        elif op == "RUN":
            runs.append(arg)
        elif op == "ENV":
            envs.append(arg)
    problems: list[str] = []
    adds = [seg for r in runs for seg in re.split(r"&&|;|\|\|", r) if AGENT_USER_RE.search(seg)]
    if not adds:
        problems.append("no uid 1000 account is created (RUN groupadd -g 1000 agent && "
                        "useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent)")
    elif not any(CREATE_HOME_RE.search(seg) for seg in adds):
        problems.append("the uid 1000 account is created without a home directory (add -m -d /home/agent)")
    if not any(re.match(r"HOME(=|\s+)[\"']?/\S+", e) for e in envs):
        problems.append("HOME is not set (ENV HOME=/home/agent)")
    return problems


def check_openhands_runtime(b: Path) -> None:
    """S9: environment/Dockerfile pre-bakes the openhands-sdk agent runtime."""
    df = b / "environment" / "Dockerfile"
    if not df.is_file():
        return
    problems = openhands_problems(df)
    for m in problems:
        fail("S9", f"environment/Dockerfile: {m}; the harness's openhands-sdk agent cannot install itself with no network")
    if not problems:
        ok("S9", f"openhands-sdk runtime pre-baked at {OH_VENV}")


def check_agent_user(b: Path) -> None:
    """S10: environment/Dockerfile creates the uid 1000 agent account with a home."""
    df = b / "environment" / "Dockerfile"
    if not df.is_file():
        return
    problems = agent_user_problems(df)
    for m in problems:
        fail("S10", f"environment/Dockerfile: {m}; [agent] user = \"1000:1000\" needs that account")
    if not problems:
        ok("S10", "uid 1000 agent account with HOME created")


def check_artifact_dirs(bundle: Path, cfg: dict | None) -> None:
    """S8: every declared artifact lands in a directory uid 1000 can write.

    [agent] user = "1000:1000" runs the agent and the oracle's solve.sh as uid
    1000. The script replays environment/Dockerfile (mkdir, chown, chmod,
    COPY/ADD --chown, WORKDIR, USER, useradd -u) and fails an artifact whose
    directory ends up root-owned or owned by another uid. A user whose uid the
    Dockerfile does not state warns. Paths the Dockerfile never touches are
    root-owned in every base image, except /tmp.
    """
    df = bundle / "environment" / "Dockerfile"
    arts = (cfg or {}).get("artifacts")
    if not df.is_file() or not isinstance(arts, list):
        return
    fails, warns = artifact_write_problems(df, arts)
    for m in fails:
        fail("S8", m)
    for m in warns:
        warn("S8", m)
    if not fails and not warns:
        ok("S8", f"every artifact directory is writable by uid {AGENT_UID}")


MAX_FILE_BYTES = 100 * 1024 * 1024  # Harbor build-context ceiling per file


def check_bundle_text(bundle: Path) -> None:
    """X1-X3: sweeps over every file in the bundle.

    X1  em dash (U+2014) and en dash (U+2013) are banned in every text file,
        including environment/ input - plain hyphen-minus is always fine.
        Binary files are skipped silently; only one whose name says it should
        have been text warns, so a real misdetection still gets looked at.
    X2  unresolved generator placeholders ({{NAME}}, __NAME__, <TAG>) mean the
        bundle is unfinished - fail. The author markers TODO/FIXME/XXX/
        PLACEHOLDER warn: a task that ships a real source tree to be debugged
        or patched carries genuine markers, so each hit is read in context.
    X3  no file may exceed 100 MB (Harbor build-context ceiling).
    """
    skipped: list[str] = []
    for p in sorted(bundle.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(bundle)
        if p.stat().st_size > MAX_FILE_BYTES:
            fail("X3", f"{rel} is {p.stat().st_size / 1048576:.0f} MB (> 100 MB ceiling)")
        if not is_text(p):
            if p.suffix.lower() in TEXT_SUFFIXES or p.name in TEXT_NAMES:
                skipped.append(str(rel))
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if DASH_RE.search(line):
                fail("X1", f"em/en dash (U+2013/U+2014) in {rel}:{i}")
            m = WORK_MARKER_RE.search(line)
            if m:
                warn("X2", f"work marker {m.group(1)!r} in {rel}:{i}; read in context "
                           "(task-owned or residue)")
        m = PLACEHOLDER_RE.search(text)
        if m:
            fail("X2", f"unresolved placeholder {m.group(0)!r} in {rel}")
    if not fails_for("X1"):
        ok("X1", "no em/en dashes in text files")
    if skipped:
        warn("X1", f"{len(skipped)} file(s) named like text but read as binary, "
                   f"re-check by hand: {', '.join(skipped[:10])}")
    if not fails_for("X3"):
        ok("X3", "no file over 100 MB")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    bundle = Path(sys.argv[1]).resolve()
    if not bundle.is_dir():
        print(f"usage error: {bundle} is not a directory")
        return 2

    check_tree(bundle)
    check_agent_image_scope(bundle)
    cfg = check_toml(bundle)
    check_artifact_dirs(bundle, cfg)
    check_openhands_runtime(bundle)
    check_agent_user(bundle)
    check_bundle_text(bundle)

    print(f"structure_qc: {bundle.name}")
    print("=" * 60)
    for line in PASSES:
        print(line)
    for line in WARNS:
        print(line)
    for line in FAILS:
        print(line)
    print("=" * 60)
    print(f"SUMMARY: {len(PASSES)} pass, {len(WARNS)} warn, {len(FAILS)} fail")
    print("VERDICT:", "FAIL" if FAILS else ("WARN - tasker approval needed" if WARNS else "PASS"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
