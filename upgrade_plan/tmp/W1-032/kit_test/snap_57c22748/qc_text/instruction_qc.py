#!/usr/bin/env python3
"""Instruction QC: prose mechanics of instruction.md (two-pass code-aware scan).

Project rule: no em/en dashes, no high-register vocabulary an Indian speaker
would not use day to day, and no AI-tell phrases. Layout (headings, lists,
tables) is the author's choice. Code is exempt, so the scan runs in two passes:

Pass 1 (P1-P3) strips fenced code blocks and inline backtick spans, then checks
the prose residue for the rules above.
Pass 2 (C1-C6) checks the FULL text (code included) for content rules: the
mandatory timeout sentence, no mention of the grading surface, any /app path it
chooses to mention actually exists in the agent image, and every declared
artifact is reachable. The prompt owes no description of its inputs; it does
owe a destination for each deliverable, because the harness copies from exactly
the paths task.toml declares.

Every ID:

  P1  no em/en dash in prose.
  P2  no listed high-register word in prose.
  P3  no listed AI-tell phrase in prose.
  C1  "You have N seconds" present (N may be written 1,800) and N equals
      [agent] timeout_sec.
  C2  no grading/solution machinery named: test.sh, test_output.py,
      judge.toml, reward.toml, rewardkit, solve.sh, solve.py, TRUTH.md,
      /logs/verifier, reward.txt, reward.json, ctrf.json.
  C3  the word "reward" never appears.
  C4  every /app path the instruction names that a COPY/ADD in
      environment/Dockerfile covers exists in environment/; an uncovered
      /app/data path fails too.
  C5  every declared artifact appears by full path (bare filename warns).
  C6  "the grader", "checker" or "verifier" in prose warns.

Usage: python3 instruction_qc.py /path/to/bundle
Exit codes: 0 = pass (warns allowed), 1 = fail, 2 = usage error.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

FAILS: list[str] = []
WARNS: list[str] = []
PASSES: list[str] = []


def fail(check: str, msg: str) -> None:
    FAILS.append(f"FAIL [{check}] {msg}")


def warn(check: str, msg: str) -> None:
    WARNS.append(f"WARN [{check}] {msg}")


def ok(check: str, msg: str) -> None:
    PASSES.append(f"pass [{check}] {msg}")


BANNED_VOCAB = [
    "leverage", "utilize", "utilise", "delve", "meticulous", "meticulously",
    "comprehensive", "comprehensively", "endeavor", "endeavour", "furthermore",
    "moreover", "subsequently", "aforementioned", "henceforth", "myriad",
    "plethora", "paradigm", "robustly", "seamless", "seamlessly",
    "holistic", "pivotal", "facilitate", "streamline", "elucidate", "ascertain",
]
AI_TELLS = [
    "it's important to note", "it is important to note", "let's dive",
    "in this task, you will",
]
# NOTE: "kindly" and "please note" are deliberately NOT in this list: they are
# ordinary polite Indian workplace English. The model gate judges register in context.
# NOTE: the bare directory tokens "tests/" and "solution/" are deliberately NOT
# in this list. They match as plain substrings, so ordinary prose such as "your
# solution/approach" fails C2 while naming no machinery at all. IN-2 still forbids
# pointing the agent at those directories, and the model gate reads for it (IN-S5).
TESTS_SOLUTION_TOKENS = [
    "test.sh", "test_output.py", "judge.toml", "reward.toml", "rewardkit",
    "solve.sh", "solve.py", "TRUTH.md", "/logs/verifier",
    "reward.txt", "reward.json", "ctrf.json",
]
FENCE_RE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", re.S | re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
APP_PATH_RE = re.compile(r"/app/[A-Za-z0-9._/*?\[\]-]+")


def dockerfile_copies(df: Path) -> list[tuple[list[str], str]]:
    """(sources, absolute destination) for every COPY/ADD that reads the build
    context, with relative destinations resolved against WORKDIR."""
    out: list[tuple[list[str], str]] = []
    if not df.is_file():
        return out
    workdir = "/"
    for raw in df.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split(None, 1)
        if len(head) < 2:
            continue
        op = head[0].upper()
        if op == "FROM":
            workdir = "/"
            continue
        if op == "WORKDIR":
            wd = head[1].strip().strip('"')
            workdir = wd if wd.startswith("/") else f"{workdir.rstrip('/')}/{wd}"
            continue
        if op not in {"COPY", "ADD"} or "--from" in head[1]:
            continue
        args = [a for a in head[1].split() if not a.startswith("--")]
        if len(args) >= 2:
            dst = args[-1]
            if not dst.startswith("/"):
                base = workdir.rstrip("/")
                dst = base + "/" if dst in {".", "./"} else f"{base}/{dst.removeprefix('./')}"
            out.append((args[:-1], dst))
    return out


def image_path_exists(bundle: Path, path: str) -> bool | None:
    """True when a COPY/ADD puts an existing environment/ entry at path,
    False when a COPY/ADD covers path but the entry is absent, None when no
    COPY/ADD covers it (a RUN step or the agent may create it)."""
    env = bundle / "environment"
    covered = False
    for srcs, dst in dockerfile_copies(env / "Dockerfile"):
        dst_norm = dst.rstrip("/")
        for src in srcs:
            src_path = env / src
            if len(srcs) > 1 or (dst.endswith("/") and src_path.is_file()):
                target = f"{dst_norm}/{src_path.name}"
            else:
                target = dst_norm
            if path == target or path.startswith(target + "/"):
                covered = True
                rest = path[len(target):].lstrip("/")
                if (src_path / rest).exists() if rest else src_path.exists():
                    return True
    return False if covered else None


def strip_code(text: str) -> str:
    """Remove fenced code blocks (``` or ~~~) and inline backtick spans, leaving
    only the prose the register rules apply to. Code must never trigger prose
    violations."""
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check_prose(prose: str) -> None:
    """P1-P3: register rules on the code-stripped prose.

    P1  no em/en dashes (U+2013/U+2014); plain hyphen-minus is fine.
    P2  no high-register vocabulary (leverage, delve, comprehensive...). The
        list is deliberately not exhaustive; the model gate judges same-kind
        words in context. "crucial"/"robust" are excluded here (false-hit risk).
    P3  no AI-tell phrases ("it's important to note", "let's dive"...).
    """
    for m in re.finditer("[\u2013\u2014]", prose):
        fail("P1", f"em/en dash (line ~{line_no(prose, m.start())})")

    lower = prose.lower()
    hits = sorted({w for w in BANNED_VOCAB if re.search(rf"\b{re.escape(w)}\b", lower)})
    for w in hits:
        fail("P2", f"banned high-register word: {w!r} (list is not exhaustive; "
             "the model gate judges same-kind words)")
    for phrase in AI_TELLS:
        if phrase in lower:
            fail("P3", f"AI-tell phrase: {phrase!r}")


def check_content(text: str, bundle: Path) -> None:
    """C1-C6: content rules on the full instruction text, code included.

    C1  the sentence "You have N seconds to complete this task." is mandatory
        and N must equal [agent] timeout_sec in task.toml.
    C2  the instruction must never name the grading/solution surface: no
        test.sh, test_output.py, judge.toml, reward.toml, rewardkit, solve.sh,
        solve.py, TRUTH.md, /logs/verifier, reward or CTRF files. The bare
        directory names tests/ and solution/ are deliberately not matched
        here; IN-2 and IN-S5 own them.
        TRUTH.md is the whole worked answer, so naming it tells the agent an
        answer document exists and invites a hunt for it. Stating
        WHAT the work is judged on (the acceptance surface) is fine and
        expected; describing the machinery that checks it is the fail.
    C3  the word "reward" is banned - the agent must not be told a reward
        mechanism exists.
    C4  the instruction owes NOTHING about its inputs - it may name no file,
        no path and no format at all. But a pointer it does give must be
        real: every /app path it mentions that a COPY/ADD in
        environment/Dockerfile covers must exist in environment/ at the
        matching place, and an /app/data path no COPY/ADD covers fails too.
        Paths created by RUN steps or by the agent are judged by reading.
        Glob patterns and declared artifacts are skipped.
    C5  every artifact declared in task.toml must be reachable from the
        instruction, because the harness copies deliverables from those exact
        paths and perfect content in the wrong place scores nothing. The full
        path appearing verbatim passes silently. Only the bare filename
        appearing warns, since natural phrasing can still point at exactly
        one location and only a reviewer can judge that. Neither form
        appearing anywhere is the fail.
    C6  "the grader", "checker" or "verifier" in prose warns: confirm it
        describes no machinery.
    """
    m = re.search(r"[Yy]ou have ([\d,]+) seconds", text)
    if not m:
        fail("C1", 'mandatory sentence missing: "You have N seconds to complete this task."')
    else:
        n = int(m.group(1).replace(",", ""))
        toml_p = bundle / "task.toml"
        if toml_p.is_file():
            try:
                cfg = tomllib.loads(toml_p.read_text(encoding="utf-8", errors="replace"))
                agent_t = cfg.get("agent", {}).get("timeout_sec")
                if not isinstance(agent_t, (int, float)) or isinstance(agent_t, bool) or agent_t <= 0:
                    warn("C1", f"instruction says {n} seconds but [agent] timeout_sec is "
                         f"missing or not a positive number; could not cross-check")
                elif int(agent_t) != n:
                    fail("C1", f"instruction says {n} seconds but [agent] timeout_sec is {agent_t}")
                else:
                    ok("C1", f"timeout sentence matches agent timeout ({n}s)")
            except tomllib.TOMLDecodeError:
                warn("C1", "task.toml unparseable; could not cross-check timeout")

    lower = text.lower()
    for tok in TESTS_SOLUTION_TOKENS:
        if tok.lower() in lower:
            fail("C2", f"instruction mentions grading/solution surface: {tok!r}")
    if re.search(r"\breward\b", lower):
        fail("C3", "instruction mentions 'reward'")
    if re.search(r"\b(the )?(grader|checker|verifier)\b", strip_code(text).lower()):
        warn("C6", "instruction mentions a grader/checker/verifier in prose; confirm it "
                   "describes no machinery")

    artifacts: list[str] = []
    toml_p = bundle / "task.toml"
    if toml_p.is_file():
        try:
            raw_arts = tomllib.loads(toml_p.read_text(encoding="utf-8", errors="replace")).get("artifacts", [])
            artifacts = [a for a in raw_arts if isinstance(a, str)] if isinstance(raw_arts, list) else []
        except tomllib.TOMLDecodeError:
            artifacts = []
    for m in APP_PATH_RE.finditer(text):
        # Strip sentence-final punctuation the regex may have swallowed.
        path = m.group(0).rstrip(".,;:)").rstrip("/")
        # Glob patterns describe a set, not one entry; the model gate judges those.
        if any(ch in path for ch in "*?[") or any(
                path == a or a.startswith(path + "/") or path.startswith(a) for a in artifacts):
            continue
        found = image_path_exists(bundle, path)
        if found is False or (found is None and path.startswith("/app/data/")):
            fail("C4", f"instruction names {path} but no environment/Dockerfile COPY puts it there")
    for art in artifacts:
        if art in text:
            continue
        # The prompt may name the destination naturally ("leave decode.py in /app")
        # instead of pasting the absolute path. The filename alone is not proof the
        # agent can infer the one correct directory, so warn and let the gate judge.
        base = art.rsplit("/", 1)[-1]
        if base and re.search(rf"(?<![\w/.-]){re.escape(base)}(?![\w-])", text):
            warn("C5", f"declared artifact {art!r} is referred to as {base!r} but the full "
                 f"path never appears; confirm the wording points at exactly one location")
        else:
            fail("C5", f"declared artifact {art!r} never requested by the instruction")

    for cid, label in (("C2", "no scripted machinery names"), ("C3", "no 'reward'"),
                       ("C4", "every /app path resolvable through COPY/ADD exists"),
                       ("C5", "every declared artifact referenced")):
        if not any(line.startswith(f"FAIL [{cid}] ") for line in FAILS):
            ok(cid, label)

    # Online-lookup sentence: tasker decision - no check of any kind. The sentence
    # may be present or absent; neither state is reported or judged.


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    bundle = Path(sys.argv[1]).resolve()
    inst = bundle / "instruction.md"
    if not bundle.is_dir() or not inst.is_file():
        print(f"usage error: {bundle} is not a bundle with instruction.md")
        return 2

    text = inst.read_text(encoding="utf-8", errors="replace")
    check_prose(strip_code(text))
    check_content(text, bundle)

    print(f"instruction_qc: {bundle.name}")
    print("=" * 60)
    for line in PASSES + WARNS + FAILS:
        print(line)
    print("=" * 60)
    print(f"SUMMARY: {len(PASSES)} pass, {len(WARNS)} warn, {len(FAILS)} fail")
    print("VERDICT:", "FAIL" if FAILS else ("WARN - tasker approval needed" if WARNS else "PASS"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
