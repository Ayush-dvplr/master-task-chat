#!/usr/bin/env python3
"""Read only triage of teammate or assigned Harbor tasks (upgrade plan P19).

Usage:
  python3 triage_tasks.py --tasks-dir DIR [--tasks-dir DIR2 ...] --out OUTDIR
                          [--settings settings.json] [--kit KIT_DIR]

For every task found under the tasks folders (a bundle at any depth, its run
folders, or run folders alone) it writes one ranked table and one section per
task: inventory, structure problems, every run classified TRUSTED, BROKEN or
UNSURE with the evidence file and line, likely design families D1 to D9, the
checks the paid model lost, quick QC risk hints tied to kit check ids, a
transparent score and a recommendation.

Outputs in OUTDIR: TRIAGE.md, triage.csv, triage.json. Nothing is written
anywhere else; the tasks folders are only read. No Docker, no network, no
model calls. Standard library only, Python 3.9 or later.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import OrderedDict

VERSION = "1.0"

DEFAULTS = {"gate": {"tests": 85.0, "rubric": 85.0, "final": 40.0},
            "slip_cap_pct": 50.0, "paid_model": "claude-opus-5", "what_if_max": 3,
            "kill_tests": 95.0}

# Kit layout (Input_Bundle_QC/structure_qc.py REQUIRED and ALLOWED_ENTRIES).
REQUIRED = ["instruction.md", "task.toml", "environment/Dockerfile", "solution/solve.sh",
            "solution/TRUTH.md", "tests/Dockerfile", "tests/test.sh", "tests/test_output.py",
            "tests/judge.toml", "tests/reward.toml"]
ALLOWED = {"": {"instruction.md", "task.toml", "environment", "solution", "tests"},
           "environment": {"Dockerfile"},
           "solution": {"solve.sh", "solve.py", "TRUTH.md"},
           "tests": {"Dockerfile", "test.sh", "test_output.py", "judge.toml", "reward.toml"}}
FORBIDDEN_NAMES = {"reward.txt", "reward.json", "reward-details.json", "ctrf.json", ".DS_Store"}
FORBIDDEN_DIRS = {"__pycache__", ".git", ".pytest_cache"}
SKIP_WALK = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv"}
RUN_FILES = {"reward-details.json", "ctrf.json", "reward.json", "reward.txt", "test-stdout.txt",
             "score.json", "reward_raw.json"}
TEXT_EXT = {".md", ".txt", ".py", ".sh", ".toml", ".json", ".jsonl", ".csv", ".tsv", ".yaml",
            ".yml", ".ini", ".cfg", ".xml", ".html", ".rst", ".log", ".sql", ".conf", ""}
DOC_EXT = {".md", ".txt", ".rst", ".html", ".ini", ".cfg", ".conf", ".yaml", ".yml"}

# Default check ids (kit at origin/main, see upgrade_plan/tmp/W1-030/FIX_MAP.md).
KIT_IDS = OrderedDict([
    ("IN-14", ("01_Instruction_QC.md", "end state and rules of engagement, never the fix path")),
    ("IN-17", ("01_Instruction_QC.md", "the instruction must not pre announce what the agent should discover")),
    ("CL-4", ("Final_checklist.md", "partial credit tracks partial correctness; exempt when the exact bar is stated")),
    ("DS-27", ("02_Data_Solution_QC.md", "TRUTH.md describes the task, not how it was made")),
    ("AL-7", ("05_Alignment_Integrity_QC.md", "no unearned measured claims")),
    ("JD-12", ("04_Judge_QC.md", "at least 8 criteria (fail), at most 35 (warn)")),
    ("TS-23", ("03_Tests_QC.md", "at least 10 checks (fail), at most 35 (warn)")),
    ("TS-24", ("03_Tests_QC.md", "agent code runs as a subprocess, unprivileged, with a timeout")),
    ("DS-21", ("02_Data_Solution_QC.md", "solvable from instruction.md and environment/")),
    ("S2", ("structure_qc.py", "every required file exists")),
    ("S3", ("structure_qc.py", "nothing else at root, environment/, solution/, tests/")),
    ("S4", ("structure_qc.py", "environment/ holds at least one input directory")),
    ("S5", ("structure_qc.py", "no grader output or cache files outside trajectories/")),
    ("S6", ("structure_qc.py", "no CRLF in .sh files")),
    ("X1", ("structure_qc.py", "no em or en dash in any text file")),
    ("X3", ("structure_qc.py", "no file over 100 MB")),
])
OUR_IDS = {"BR-SL1": "BUILD_RULES.md DOCS, NO STEPS (P16)", "SLIP": "settings slip_cap_pct (PL answer, ENTRY 87)",
           "WHAT-IF": "settings what_if_max (PL answer, ENTRY 87)"}

# Broken score signs.
PERM_RE = re.compile(r"Permission denied|PermissionError|\bEACCES\b|\[Errno 13\]|Operation not permitted")
API_RE = re.compile(r"rate.?limit|APIError|APIConnectionError|api_error|status code [45]\d\d|Error code: ?[45]\d\d|"
                    r"Internal Server Error|overloaded_error|service unavailable|judge (call )?(failed|error)|"
                    r"could not (parse|evaluate) the|failed to (parse|call) (the )?(judge|model)|"
                    r"context.length.exceeded|invalid.api.key|AuthenticationError|litellm\.\w*Error", re.I)
CRASH_RE = re.compile(r"INTERNALERROR|ERROR collecting|ImportError while|ModuleNotFoundError|SyntaxError: |"
                      r"collected 0 items|no tests ran|Traceback \(most recent call last\)")
TIMEOUT_RE = re.compile(r"verifier.{0,40}timed? ?out|timed out after \d+(\.\d+)? ?s(econds)?|Timeout(Error|Expired)|"
                        r"test\.sh.{0,20}(timed out|killed)", re.I)
UID_DROP_RE = re.compile(r"setpriv|--reuid|\b65532\b|runuser\b|os\.setuid\(|\"user\"\s*:|\buser\s*=\s*_?[A-Z_]*UID|gosu\b|su -s")
READ_FIX_RE = re.compile(r"st_mode[^\n]*\||\|\s*extra\b|S_IROTH|S_IRGRP|chmod\s+(-R\s+)?[ugoa]*\+r|a\+rX?|"
                         r"copyfile\(|copy2\(|shutil\.copy\(|write_bytes\(\s*\w+\.read\(|extractall\(")
MODE600_RE = re.compile(r"-rw-------\.?\s+\d+\s+\S+\s+\S+\s+\d+\s+\w+\s+\d+\s+[\d:]+\s+([^\s\\\"']+)")
SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|authorization)(\W{0,3})([:=]\s*)?(\"?)[^\s\"',;]{4,}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
SKKEY_RE = re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_-]{8,}")

INPUT_TOKEN = re.compile(r"(hidden_[a-z0-9]+|h\d+|seed\d+|case_[a-z0-9]+|s\d+|q\d+)", re.I)
EXEC_NAME = re.compile(r"(^|_)(hidden|held|fresh|unseen|seed|probe|program|run|driver|minted|trap|untrapped|replay|"
                       r"event|scenario|variant|mutat|reseed|corpus|generated|deterministic|empty|rerun)", re.I)
SHIPPED_NAME = re.compile(r"(^|_)(shipped|visible|sample|artifact|artifacts|exists?|present|parse|parses|schema|"
                          r"deliver|delivers|recorded|decoded|serializ|serialis|canonical|layout|keys|json)(_|$)", re.I)
WHOLE_DOC_NAME = re.compile(r"(exact|matches|match|whole|full|identical|bytes|reproduces)", re.I)
PER_ROW_NAME = re.compile(r"(row|rows|field|fields|per_|each_|column|key|keys|entry|entries|record|records|line|lines)", re.I)

FAMILY_TEXT = OrderedDict([
    ("D1", ("a documented branch only the hidden data fires",
            re.compile(r"\b(unseen|held[- ]out|hidden (data|inputs?|runs?|cases?)|other (inputs|data|days|runs|seeds|estates)|"
                       r"not every documented|does not reach every|any (other )?input|new inputs)\b", re.I))),
    ("D2", ("carrier or encoding variation inside a named standard",
            re.compile(r"\b(RFC ?\d{3,4}|ISO[ /-]?\d{3,5}|ECMA-?\d{2,3}|IEEE ?\d{3,4}|W3C|UTF-(8|16|32)|"
                       r"namespaces?|as (defined|specified) (by|in)|conform(s|ing)? to|every (form|encoding) the)\b", re.I))),
    ("D3", ("a documented rule misread or over applied",
            re.compile(r"\b(precedence|takes priority|outranks|authority|no more widely|never (right|wins) just|"
                       r"only where|scope of|supersed\w*|newer .{0,20}does not)\b", re.I))),
    ("D4", ("a stated runtime on a large hidden input",
            re.compile(r"\b(\d+ ?(seconds|second|s) (limit|budget|wall)|time limit|within \d+ ?(seconds|s|minutes)|"
                       r"runtime (budget|limit)|run time|times the reference)\b", re.I))),
    ("D5", ("one detail buried in a very long document",
            re.compile(r"\b(is increased by|is reduced by|instead of|is replaced by|notwithstanding|in place of|"
                       r"as if|overrid\w+)\b", re.I))),
    ("D6", ("many interacting seeded faults",
            re.compile(r"\b(seeded (defects?|faults?)|defects?|faults?|repair|broken (rules?|records?))\b", re.I))),
    ("D8", ("carried state that never heals",
            re.compile(r"\b(carried|carry(ing)? (forward|over)|running (total|balance|state)|cumulative|"
                       r"never heals?|deferr\w+|brought forward)\b", re.I))),
    ("D9", ("one clause hardening contracts",
            re.compile(r"\b(must raise|named error|exit (code|status) [1-9]|refuses?|rejects? (the|any|a))\b", re.I))),
])
DECOY_FILE = re.compile(r"(legacy|_old|old_|deprecated|draft|stale|superseded|obsolete|backup|_copy|archive|retired)", re.I)
GEN_RE = re.compile(r"random\.Random\(|\bseed\b|def _?(mint|gen|generate|make|build)_\w*\(|held_out|fresh_|hidden_|reseed", re.I)

STEP_RE = re.compile(r"^\s*(?:\d+[.)]|[-*]|step \d+[:.])\s+(?:first|then|next|finally|compute|calculate|read|parse|load|"
                     r"sort|group|apply|write|emit|run|iterate|loop|for each|build|merge|join|filter|normali[sz]e|round|"
                     r"sum|subtract|add|multiply|divide|scan|walk|decode|match|replay)\b", re.I)
ANNOUNCE_RE = re.compile(r"\b(note that|beware|watch out|be careful|careful:|trap|traps|gotcha|pitfall|tricky|"
                         r"do not be fooled|hidden (rule|branch|trap)s?|there (are|is) (\d+|one|two|three|four|five|six|seven|"
                         r"eight|nine|ten|eleven|twelve|fifteen|twenty) (hidden |subtle )?(rules|traps|defects|conventions|quirks))\b", re.I)
EXACT_BAR_RE = re.compile(r"only an exact match|exact(ly)? match|byte[- ]for[- ]byte|byte[- ]identical|costs the whole|"
                          r"graded whole|must match exactly|character for character|one (cent|unit|byte) out of place|"
                          r"exact bar|compared exactly|exact comparison", re.I)
TRUTH_SCORE_RE = re.compile(r"(opus|claude|gpt|glm|gemini|sonnet|paid run|trajectory|pass_summary).{0,60}"
                            r"(\d{1,3}(\.\d+)?\s*%|scor(e|ed|es)\s*\d|final\s*\d|\d{1,3}\.\d+\b)", re.I)
WHATIF_RE = re.compile(r"\bwhat if\b|\bwould (be|have|become|change)\b|\bif \w+ (were|had been)\b|\bcounterfactual\b", re.I)


def redact(s):
    s = SECRET_RE.sub(lambda m: m.group(1) + m.group(2) + (m.group(3) or "") + "[redacted]", s)
    s = SKKEY_RE.sub("[redacted]", s)
    return EMAIL_RE.sub("[email]", s)


def snip(s, n=160):
    return redact(re.sub(r"\s+", " ", str(s or "")).strip())[:n]


def read_text(path, limit=8 * 1024 * 1024):
    try:
        if os.path.getsize(path) > limit:
            with open(path, "rb") as f:
                return f.read(limit).decode("utf-8", "replace")
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def load_json(path):
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None


def find_line(text, regex, start=0):
    """First (line number, line) in text matching regex, or (None, '')."""
    for i, line in enumerate(text.splitlines(), 1):
        if i <= start:
            continue
        if regex.search(line):
            return i, line
    return None, ""


def all_lines(text, regex, cap=50):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if regex.search(line):
            out.append((i, line))
            if len(out) >= cap:
                break
    return out


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pct(x):
    """Score as a percent: values at most 1.0 from reward files are fractions."""
    v = fnum(x)
    if v is None:
        return None
    return v


# ---------------------------------------------------------------- settings and kit

def load_settings(path):
    s = json.loads(json.dumps(DEFAULTS))
    s["source"] = "defaults (85, 85, 40, 50)"
    if path:
        d = load_json(path)
        if not isinstance(d, dict):
            sys.exit("cannot read settings file %s" % path)
        g = d.get("gate") or {}
        for k in ("tests", "rubric", "final"):
            if fnum(g.get(k)) is not None:
                s["gate"][k] = float(g[k])
        if fnum(d.get("slip_cap_pct")) is not None:
            s["slip_cap_pct"] = float(d["slip_cap_pct"])
        if fnum(d.get("what_if_max")) is not None:
            s["what_if_max"] = int(d["what_if_max"])
        m = (d.get("models") or {}).get("paid_run")
        if m:
            s["paid_model"] = str(m)
        s["source"] = path
    return s


def load_kit(kit_dir):
    """Map check id to 'kit file:line' when a kit folder is given."""
    found = {}
    if not kit_dir:
        return found
    if not os.path.isdir(kit_dir):
        sys.exit("kit folder not found: %s" % kit_dir)
    for name in sorted(os.listdir(kit_dir)):
        p = os.path.join(kit_dir, name)
        if not os.path.isfile(p) or not name.endswith((".md", ".py")):
            continue
        for i, line in enumerate(read_text(p).splitlines(), 1):
            for cid in KIT_IDS:
                if cid in found:
                    continue
                if re.match(r"^\s*(?:[-*|]\s*(?:\[ \]\s*)?)?%s\b" % re.escape(cid), line):
                    found[cid] = "%s:%d" % (name, i)
    return found


def cid_ref(cid, kit):
    if cid in OUR_IDS:
        return "%s (%s)" % (cid, OUR_IDS[cid])
    if kit:
        return "%s (%s)" % (cid, kit.get(cid, "id not found in the given kit"))
    return cid


# ---------------------------------------------------------------- discovery

def is_run_dir(d, names):
    if "verifier" in names and os.path.isdir(os.path.join(d, "verifier")):
        try:
            if set(os.listdir(os.path.join(d, "verifier"))) & RUN_FILES:
                return True
        except OSError:
            pass
    if os.path.basename(d) != "verifier" and ({"reward-details.json", "ctrf.json"} & set(names)):
        return True
    if "result.json" in names and ("agent" in names or "verifier" in names or "exception.txt" in names):
        r = load_json(os.path.join(d, "result.json"))
        if isinstance(r, dict) and "trial_name" in r:
            return True
    return False


def is_bundle_root(d, names):
    if "instruction.md" in names or "task.toml" in names:
        return True
    return "tests" in names and "environment" in names and os.path.isdir(os.path.join(d, "tests"))


def discover(top):
    bundles, runs, summaries = [], [], []
    top = os.path.abspath(top)
    for d, dirs, files in os.walk(top):
        rel_parts = os.path.relpath(d, top).split(os.sep)
        dirs[:] = sorted(x for x in dirs if x not in SKIP_WALK)
        names = set(dirs) | set(files)
        inside_run = any(p in ("artifacts", "agent", "verifier", "logs") for p in rel_parts)
        if inside_run:
            dirs[:] = []
            continue
        if is_run_dir(d, names):
            runs.append(d)
            dirs[:] = [x for x in dirs if x not in ("artifacts", "agent", "verifier", "logs")]
        elif is_bundle_root(d, names):
            bundles.append(d)
            # input folders can be large; inventory reads them separately
            dirs[:] = [x for x in dirs if x != "environment"]
        if "pass_summary.json" in files:
            summaries.append(os.path.join(d, "pass_summary.json"))
    return bundles, runs, summaries


def task_name_of_bundle(b):
    t = read_text(os.path.join(b, "task.toml"), 200000)
    m = re.search(r'^\s*name\s*=\s*"(?:terminal-bench/)?([^"]+)"', t, re.M)
    return m.group(1) if m else None


def ancestor(path, candidates):
    best = None
    for c in candidates:
        if path == c or path.startswith(c + os.sep):
            if best is None or len(c) > len(best):
                best = c
    return best


# ---------------------------------------------------------------- inventory

def inventory(b, settings):
    inv = OrderedDict()
    probs = []
    for rel in REQUIRED + ["solution/solve.py"]:
        inv[rel] = os.path.isfile(os.path.join(b, rel))
    inv["trajectories/"] = os.path.isdir(os.path.join(b, "trajectories"))
    for rel in REQUIRED:
        if not inv[rel]:
            probs.append(("S2", "missing required file: %s" % rel))
    for folder, allowed in ALLOWED.items():
        d = os.path.join(b, folder) if folder else b
        if not os.path.isdir(d):
            if folder:
                probs.append(("S2", "missing folder: %s/" % folder))
            continue
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if name in allowed:
                continue
            if folder == "environment" and os.path.isdir(p) and not name.startswith("."):
                continue
            if not folder and name == "trajectories" and os.path.isdir(p):
                probs.append(("S3", "warn: trajectories/ at the root (accepted by delivery policy, delete for a clean root)"))
                continue
            relp = (folder + "/" if folder else "") + name
            probs.append(("S3", "unexpected entry %s%s" % (relp, "/" if os.path.isdir(p) else "")))
    env = os.path.join(b, "environment")
    data_bytes, data_files, exts, input_dirs = 0, 0, {}, []
    big = []
    if os.path.isdir(env):
        for name in sorted(os.listdir(env)):
            p = os.path.join(env, name)
            if os.path.isdir(p) and not name.startswith("."):
                input_dirs.append(name)
        if not input_dirs:
            probs.append(("S4", "environment/ holds no input directory"))
        for d, dirs, files in os.walk(env):
            dirs[:] = [x for x in dirs if x not in SKIP_WALK]
            for f in files:
                p = os.path.join(d, f)
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                if os.path.relpath(p, env) == "Dockerfile":
                    continue
                data_bytes += sz
                data_files += 1
                e = os.path.splitext(f)[1].lower() or "(none)"
                exts[e] = exts.get(e, 0) + 1
                if sz > 100 * 1024 * 1024:
                    big.append(os.path.relpath(p, b))
    for p in big:
        probs.append(("X3", "file over 100 MB: %s" % p))
    # forbidden names and dash and CRLF sweep outside trajectories/
    dash_files, dash_first = 0, None
    for d, dirs, files in os.walk(b):
        relp = os.path.relpath(d, b)
        parts = relp.split(os.sep)
        if parts[0] == "trajectories":
            dirs[:] = []
            continue
        for x in list(dirs):
            if x in FORBIDDEN_DIRS:
                probs.append(("S5", "forbidden folder %s" % os.path.normpath(os.path.join(relp, x))))
        dirs[:] = [x for x in dirs if x not in SKIP_WALK]
        for f in files:
            p = os.path.join(d, f)
            rp = os.path.normpath(os.path.join(relp, f))
            if f in FORBIDDEN_NAMES:
                probs.append(("S5", "forbidden file %s" % rp))
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXT:
                continue
            try:
                if os.path.getsize(p) > 3 * 1024 * 1024:
                    continue
            except OSError:
                continue
            raw = read_text(p)
            if ext == ".sh" and "\r\n" in raw:
                probs.append(("S6", "CRLF line endings in %s" % rp))
            if "—" in raw or "–" in raw:
                dash_files += 1
                if dash_first is None:
                    ln, _ = find_line(raw, re.compile("[–—]"))
                    dash_first = "%s:%s" % (rp, ln)
    if dash_files:
        probs.append(("X1", "em or en dash in %d text file(s), first at %s" % (dash_files, dash_first)))
    stats = {"data_kb": data_bytes // 1024, "data_files": data_files,
             "formats": len(exts), "top_formats": " ".join("%s:%d" % kv for kv in sorted(exts.items(), key=lambda kv: -kv[1])[:5]),
             "input_dirs": input_dirs}
    return inv, probs, stats


def test_criteria(b):
    """Current test checks from tests/test_output.py: {name: weight}."""
    t = read_text(os.path.join(b, "tests", "test_output.py"))
    out = OrderedDict()
    for m in re.finditer(r"^criteria\.(\w+)\(\s*weight\s*=\s*(-?[\d.]+)", t, re.M):
        out[m.group(1)] = float(m.group(2))
    if not out:
        for m in re.finditer(r"^def (test_\w+)\(", t, re.M):
            out[re.sub(r"^test_", "", m.group(1))] = None
    return out


def judge_criteria(b):
    t = read_text(os.path.join(b, "tests", "judge.toml"))
    crits = []
    for block in re.split(r"^\[\[criterion\]\]\s*$", t, flags=re.M)[1:]:
        c = {}
        for key in ("id", "name", "description"):
            m = re.search(r'^\s*%s\s*=\s*"((?:[^"\\]|\\.)*)"' % key, block, re.M)
            c[key] = m.group(1) if m else ""
        m = re.search(r"^\s*weight\s*=\s*(-?[\d.]+)", block, re.M)
        c["weight"] = float(m.group(1)) if m else None
        crits.append(c)
    return crits


# ---------------------------------------------------------------- runs

def run_index(path):
    m = re.search(r"(?:run[_ ]?|Run )(\d+)$", os.path.basename(path), re.I)
    return int(m.group(1)) if m else None


def find_summary(run_path, summaries):
    p = os.path.dirname(run_path)
    for _ in range(3):
        s = os.path.join(p, "pass_summary.json")
        if s in summaries:
            return s
        p = os.path.dirname(p)
    return None


def model_of(run_path, result, summary, config):
    if isinstance(summary, dict) and summary.get("model"):
        return str(summary["model"]), None
    agent = None
    if isinstance(result, dict):
        ai = result.get("agent_info") or {}
        agent = ai.get("name")
        mi = ai.get("model_info") or {}
        if mi.get("name"):
            return str(mi["name"]), agent
        cfg = (result.get("config") or {}).get("agent") or {}
        if cfg.get("model_name"):
            return str(cfg["model_name"]), agent or cfg.get("name")
    if isinstance(config, dict):
        a = config.get("agent") or {}
        if a.get("model_name"):
            return str(a["model_name"]), agent or a.get("name")
        if a.get("name"):
            agent = agent or a.get("name")
    for part in reversed(run_path.split(os.sep)):
        if re.match(r"(claude|gpt|glm|gemini|o\d|oracle|nop|qwen|deepseek|kimi)", part, re.I):
            return part, agent
    return agent or "unknown", agent


def parse_checks(run):
    """Fill run['checks'] (test layer) and run['judge'] from the verifier files."""
    v = run["vdir"]
    det = load_json(os.path.join(v, "reward-details.json")) if v else None
    checks, judge = [], []
    src = None
    if isinstance(det, dict) and isinstance(det.get("reward"), dict):
        src = "reward-details.json"
        run["reward_score"] = fnum(det["reward"].get("score"))
        for comp in det["reward"].get("components") or []:
            crit = ((comp.get("detail") or {}).get("criteria")) or []
            layer = comp.get("name") or "?"
            if layer == "judge":
                for c in crit:
                    judge.append({"id": c.get("id") or "", "name": c.get("name") or "", "weight": fnum(c.get("weight")) or 0.0,
                                  "value": fnum(c.get("value")) or 0.0, "why": c.get("reasoning") or "",
                                  "desc": c.get("description") or ""})
                jo = (comp.get("detail") or {}).get("judge_output")
                if isinstance(jo, str) and API_RE.search(jo) and not crit:
                    run["signals"].append(("BROKEN", "judge or API error", "%s judge_output: %s" % (rel_v(run, "reward-details.json"), snip(jo, 120))))
                if (comp.get("detail") or {}).get("error"):
                    run["signals"].append(("BROKEN", "judge or API error", "%s judge error: %s" % (rel_v(run, "reward-details.json"), snip((comp.get("detail") or {}).get("error"), 120))))
            else:
                for c in crit:
                    checks.append({"name": c.get("name") or c.get("id") or "", "weight": fnum(c.get("weight")) or 0.0,
                                   "value": fnum(c.get("value")) or 0.0, "msg": c.get("reasoning") or "",
                                   "layer": layer})
    ctrf = load_json(os.path.join(v, "ctrf.json")) if v else None
    if isinstance(ctrf, dict):
        res = ctrf.get("results") or {}
        tests = res.get("tests") or []
        run["ctrf_summary"] = res.get("summary") or {}
        if not checks:
            src = src or "ctrf.json"
            for t in tests:
                w = fnum(t.get("weight"))
                w = 1.0 if w is None else w
                passed = t.get("status") == "passed"
                val = (1.0 if passed else 0.0) if w >= 0 else (0.0 if passed else 1.0)
                checks.append({"name": t.get("name") or "", "weight": w, "value": val,
                               "msg": " ".join(str(t.get(k) or "") for k in ("message", "trace")).strip(), "layer": "test_output"})
        else:
            # messages only
            msgs = {t.get("name"): " ".join(str(t.get(k) or "") for k in ("message", "trace")).strip() for t in tests}
            for c in checks:
                if not c["msg"] and msgs.get(c["name"]):
                    c["msg"] = msgs[c["name"]]
        if (run["ctrf_summary"] or {}).get("tests") == 0:
            run["signals"].append(("BROKEN", "grader crash", "%s: summary tests 0 (no check ran)" % rel_v(run, "ctrf.json")))
    if not judge:
        sc = load_json(os.path.join(v, "score.json")) if v else None
        if not isinstance(sc, dict):
            sc = run.get("report") if isinstance(run.get("report"), dict) else None
        if isinstance(sc, dict):
            for r in sc.get("rubric") or []:
                w = 1.0 if r.get("is_positive", True) else -1.0
                judge.append({"id": "R%s" % r.get("number"), "name": "", "weight": w,
                              "value": fnum(r.get("score")) if r.get("passed") is None else (1.0 if r.get("passed") else 0.0),
                              "why": r.get("justification") or "", "desc": r.get("criterion") or ""})
    run["checks"], run["judge"], run["checks_source"] = checks, judge, src


def rel_v(run, name):
    return os.path.join(run["rel"], "verifier", name) if run["vdir"] and run["vdir"].endswith("verifier") else os.path.join(run["rel"], name)


def layer_pct(items):
    pos = sum(i["weight"] for i in items if i["weight"] > 0)
    got = sum(i["weight"] * min(max(i["value"], 0.0), 1.0) for i in items if i["weight"] > 0)
    pen = sum(i["weight"] * min(max(i["value"], 0.0), 1.0) for i in items if i["weight"] < 0)
    return (100.0 * (got + pen) / pos) if pos else None, pos


def scores(run, summary):
    """tests, rubric, final percent, with the source of each."""
    t = r = f = None
    srcs = []
    if isinstance(summary, dict):
        per = summary.get("per_run") or []
        idx = run["index"]
        row = None
        for p in per:
            if idx is not None and p.get("run_index") == idx:
                row = p
        if row is None and len(per) == 1:
            row = per[0]
        if row:
            t, r, f = fnum(row.get("test_weights_percentage")), fnum(row.get("rubric_weights_percentage")), fnum(row.get("combined_score"))
            srcs.append("pass_summary.json")
    rep = run.get("report")
    if t is None and isinstance(rep, dict):
        t, r, f = fnum(rep.get("test_weights_percentage")), fnum(rep.get("rubric_weights_percentage")), fnum(rep.get("final_reward"))
        if t is not None:
            srcs.append("report.json")
    ct, _ = layer_pct(run["checks"]) if run["checks"] else (None, 0)
    cj, _ = layer_pct(run["judge"]) if run["judge"] else (None, 0)
    if t is None and ct is not None:
        t = ct
        srcs.append("checks")
    if r is None and cj is not None:
        r = cj
    if f is None:
        rs = run.get("reward_score")
        if rs is None and run["vdir"]:
            rj = load_json(os.path.join(run["vdir"], "reward.json"))
            if isinstance(rj, dict):
                rs = fnum(rj.get("reward"))
        if rs is not None:
            f = rs * 100.0 if abs(rs) <= 1.0 else rs
        elif t is not None and r is not None:
            f = 0.5 * t + 0.5 * r
    run["tests"], run["rubric"], run["final"] = t, r, f
    run["computed_tests"] = ct
    run["score_source"] = "+".join(srcs) or ("verifier files" if f is not None else "none")


def scan_verifier_text(run):
    """Text of verifier outputs (never the agent's work or the judge's reading of it)."""
    texts = []
    v = run["vdir"]
    if v and os.path.isdir(v):
        for name in sorted(os.listdir(v)):
            p = os.path.join(v, name)
            if os.path.isfile(p) and (name.endswith((".txt", ".log")) or name in ("ctrf.json",)):
                texts.append((os.path.join(run["rel"], os.path.relpath(p, run["path"])), read_text(p, 4 * 1024 * 1024)))
    for name in ("exception.txt",):
        p = os.path.join(run["path"], name)
        if os.path.isfile(p):
            texts.append((os.path.join(run["rel"], name), read_text(p, 1024 * 1024)))
    for c in run["checks"]:
        if c["msg"]:
            texts.append(("%s check %s" % (run["checks_source"] or "verifier", c["name"]), c["msg"]))
    return texts


def classify(run, task):
    sig = run["signals"]
    res = run.get("result") if isinstance(run.get("result"), dict) else {}
    exc = res.get("exception_info") if isinstance(res, dict) else None
    rel_res = os.path.join(run["rel"], "result.json")
    if isinstance(exc, dict) and exc:
        et = str(exc.get("exception_type") or "")
        em = str(exc.get("exception_message") or "")
        ev = "%s exception_info: %s: %s" % (rel_res, et, snip(em, 140))
        if re.search(r"AgentTimeout", et):
            run["notes"].append("agent hit its time limit (a genuine result, not a broken grade): " + ev)
        elif re.search(r"RewardFileNotFound|RewardFile", et):
            sig.append(("BROKEN", "missing outputs", ev))
        elif re.search(r"Timeout|timed out", et + em, re.I):
            sig.append(("BROKEN", "grader timeout", ev))
        elif API_RE.search(et + " " + em):
            sig.append(("BROKEN", "judge or API error", ev))
        else:
            sig.append(("BROKEN", "grader crash", ev))
    has_score_file = bool(run["vdir"]) and any(os.path.isfile(os.path.join(run["vdir"], n)) for n in RUN_FILES)
    if not has_score_file and not run.get("summary_only"):
        sig.append(("BROKEN", "missing outputs", "%s: no verifier score file (reward-details, ctrf, reward, test-stdout)" % run["rel"]))
    texts = scan_verifier_text(run)
    for where, txt in texts:
        ln, line = find_line(txt, PERM_RE)
        if ln:
            sig.append(("BROKEN", "permission denied", "%s:%s %s" % (where, ln, snip(line, 140))))
            break
    for where, txt in texts:
        if " check " in where:
            continue  # a per check timeout or traceback is the program's own failure
        ln, line = find_line(txt, TIMEOUT_RE)
        if ln:
            sig.append(("BROKEN", "grader timeout", "%s:%s %s" % (where, ln, snip(line, 140))))
            break
    for where, txt in texts:
        if " check " in where:
            continue
        ln, line = find_line(txt, CRASH_RE)
        if ln and not run["checks"]:
            sig.append(("BROKEN", "grader crash", "%s:%s %s" % (where, ln, snip(line, 140))))
            break
        if ln:
            run["notes"].append("verifier output carries an error line, checks still scored: %s:%s %s" % (where, ln, snip(line, 100)))
            break
    for j in run["judge"]:
        if API_RE.search(j["why"] or ""):
            sig.append(("BROKEN", "judge or API error", "%s judge %s: %s" % (run["checks_source"] or "score.json", j["id"] or j["name"], snip(j["why"], 120))))
            break
    if run["judge"] and all(not (j["why"] or "").strip() for j in run["judge"]) and all((j["value"] or 0) == 0 for j in run["judge"] if j["weight"] > 0):
        sig.append(("UNSURE", "judge gave no reasoning and no points", "%s: %d criteria, all empty" % (run["rel"], len(run["judge"]))))
    if task.get("judge_crits") and run["checks_source"] and not run["judge"] and not run.get("summary_only"):
        sig.append(("UNSURE", "judge criteria missing from the run", "%s: judge.toml has %d criteria, the run has none" % (run["rel"], len(task["judge_crits"]))))
    if (run["tests"] == 0 and (run["rubric"] or 0) == 0 and run["final"] is not None and run["final"] <= 0
            and any(s[0] == "BROKEN" for s in sig)):
        sig.append(("BROKEN", "all zero with errors", "%s: tests 0, rubric 0" % run["rel"]))
    # permission hazard: tests drop the uid and nothing makes the program readable
    perm = task.get("perm") or {}
    lost_tests = run["tests"] is not None and run["tests"] < 99.99
    if perm.get("drop") and lost_tests and not any(s[1] == "permission denied" for s in sig):
        exec_pass = [c["name"] for c in run["checks"] if c["weight"] > 0 and c["value"] >= 1 and EXEC_NAME.search(c["name"])
                     and not SHIPPED_NAME.search(c["name"])]
        pos = [c for c in run["checks"] if c["weight"] > 0]
        shipped_pass = [c for c in pos if SHIPPED_NAME.search(c["name"]) and c["value"] >= 1]
        others = [c for c in pos if not SHIPPED_NAME.search(c["name"])]
        shipped = [c for c in pos if SHIPPED_NAME.search(c["name"])]
        sw = sum(c["weight"] for c in shipped)
        spw = sum(c["weight"] for c in shipped_pass)
        split = bool(shipped_pass) and bool(others) and sw > 0 and spw / sw >= 0.75 and all(c["value"] < 1 for c in others)
        m600 = run.get("mode600") or []
        delivered = task.get("deliverables") or set()
        m600_del = [m for m in m600 if os.path.basename(m[1]) in delivered or m[1] in run.get("artifact_names", set())]
        if perm.get("fix") and not split:
            run["notes"].append("tests drop the uid (%s) and make agent files readable (%s): permission ruled out" % (perm["drop"], perm["fix"]))
        elif exec_pass and not split:
            run["notes"].append("tests drop the uid (%s); check %s ran the program and passed: permission ruled out" % (perm["drop"], exec_pass[0]))
        else:
            ev = "tests drop the uid at %s; no read grant for the delivered program found" % perm["drop"]
            if perm.get("fix"):
                ev = "tests drop the uid at %s; a read grant exists (%s) but the score shows the split" % (perm["drop"], perm["fix"])
            parts = []
            if m600_del:
                parts.append("agent listed %s as -rw------- (%s)" % (os.path.basename(m600_del[0][1]), m600_del[0][0]))
            if split:
                parts.append("%d shipped or interface checks passed while all %d other positive checks failed" % (len(shipped_pass), len(others)))
            neg_fired = [c["name"] for c in run["checks"] if c["weight"] < 0 and c["value"] > 0]
            if split and neg_fired:
                parts.append("negative %s fired, which a program that never ran can trip" % neg_fired[0])
            if m600_del and split and not perm.get("fix"):
                sig.append(("BROKEN", "permission denied (inferred)", ev + "; " + "; ".join(parts)))
            else:
                sig.append(("UNSURE", "permission risk", ev + ("; " + "; ".join(parts) if parts else "; no run evidence either way")))
    # recorded versus computed
    if run["tests"] is not None and run["computed_tests"] is not None and abs(run["tests"] - run["computed_tests"]) > 1.0:
        sig.append(("UNSURE", "recorded score differs from the checks", "%s: recorded tests %.2f, checks give %.2f" % (run["rel"], run["tests"], run["computed_tests"])))
    if run.get("summary_only"):
        sig.append(("UNSURE", "summary only", "%s: pass_summary.json without a run folder, nothing to verify" % run["rel"]))
    fails = [c for c in run["checks"] if c["weight"] > 0 and c["value"] < 1]
    if len(fails) >= 5:
        ms = set(snip(c["msg"], 80) for c in fails)
        if len(ms) == 1 and list(ms)[0]:
            sig.append(("UNSURE", "every failed check has the same message", "%s: %d failed checks: %s" % (run["rel"], len(fails), list(ms)[0])))
    steps = run.get("agent_steps")
    if run["paid"] and steps is not None and steps < 3:
        sig.append(("UNSURE", "agent barely ran", "%s: %d agent steps in agent/trajectory.json" % (run["rel"], steps)))
    if run["final"] is None and not any(s[0] == "BROKEN" for s in sig):
        sig.append(("UNSURE", "no score found", "%s: no score in any run file" % run["rel"]))
    prio = ["permission denied", "permission denied (inferred)", "grader crash", "grader timeout", "judge or API error",
            "missing outputs", "all zero with errors"]
    broken = sorted([s for s in sig if s[0] == "BROKEN"], key=lambda s: prio.index(s[1]) if s[1] in prio else 99)
    run["signals"] = broken + [s for s in sig if s[0] != "BROKEN"]
    unsure = [s for s in sig if s[0] == "UNSURE"]
    if broken:
        run["status"], run["sign"], run["evidence"] = "BROKEN", broken[0][1], broken[0][2]
    elif unsure:
        run["status"], run["sign"], run["evidence"] = "UNSURE", unsure[0][1], unsure[0][2]
    else:
        run["status"], run["sign"], run["evidence"] = "TRUSTED", "", ""


def read_run(path, top, summaries, settings, task):
    rel = os.path.relpath(path, top)
    vdir = os.path.join(path, "verifier") if os.path.isdir(os.path.join(path, "verifier")) else path
    run = {"path": path, "rel": os.path.join(os.path.basename(top), rel), "vdir": vdir, "signals": [], "notes": [],
           "index": run_index(path)}
    run["result"] = load_json(os.path.join(path, "result.json"))
    run["report"] = load_json(os.path.join(path, "report.json"))
    spath = find_summary(path, summaries)
    summary = load_json(spath) if spath else None
    run["summary_path"] = spath
    model, agent = model_of(path, run["result"], summary, load_json(os.path.join(path, "config.json")))
    run["model"], run["agent"] = model, agent
    run["paid"] = model == settings["paid_model"] and (agent or "") not in ("oracle", "nop")
    parse_checks(run)
    scores(run, summary)
    traj = None
    for cand in ("agent/trajectory.json", "artifacts/logs/agent/trajectory.json"):
        p = os.path.join(path, cand)
        if os.path.isfile(p):
            traj = p
            break
    run["mode600"] = []
    run["agent_steps"] = None
    if traj:
        txt = read_text(traj, 40 * 1024 * 1024)
        j = None
        try:
            j = json.loads(txt)
        except ValueError:
            j = None
        if isinstance(j, dict) and isinstance(j.get("steps"), list):
            run["agent_steps"] = sum(1 for s in j["steps"] if isinstance(s, dict) and s.get("source") == "agent")
            for s in j["steps"]:
                blob = json.dumps(s)
                for m in MODE600_RE.finditer(blob.replace("\\n", "\n")):
                    run["mode600"].append(("agent/trajectory.json step %s" % s.get("step_id"), m.group(1)))
        else:
            for m in MODE600_RE.finditer(txt.replace("\\n", "\n")):
                run["mode600"].append(("agent/trajectory.json", m.group(1)))
    names = set()
    art = os.path.join(path, "artifacts")
    if os.path.isdir(art):
        for d, dirs, files in os.walk(art):
            if os.path.relpath(d, art).split(os.sep)[0] == "logs":
                dirs[:] = []
                continue
            names.update(files)
    run["artifact_names"] = names
    classify(run, task)
    return run


def summary_only_runs(summaries, claimed, top, settings, task_of):
    out = []
    for s in summaries:
        d = os.path.dirname(s)
        if any(r.startswith(d + os.sep) for r in claimed):
            continue
        out.append(d)
    return out


# ---------------------------------------------------------------- levers and QC hints

def doc_files(b):
    """instruction.md and readable docs under environment/ input folders."""
    out = []
    p = os.path.join(b, "instruction.md")
    if os.path.isfile(p):
        out.append(p)
    env = os.path.join(b, "environment")
    if os.path.isdir(env):
        for d, dirs, files in os.walk(env):
            dirs[:] = [x for x in dirs if x not in SKIP_WALK]
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in DOC_EXT:
                    q = os.path.join(d, f)
                    try:
                        if os.path.getsize(q) <= 5 * 1024 * 1024:
                            out.append(q)
                    except OSError:
                        pass
    return out


def perm_static(b):
    info = {}
    for rel in ("tests/test_output.py", "tests/test.sh"):
        t = read_text(os.path.join(b, rel))
        ln, line = find_line(t, UID_DROP_RE)
        if ln and "drop" not in info:
            info["drop"] = "%s:%d" % (rel, ln)
        ln2, line2 = find_line(t, READ_FIX_RE)
        if ln2 and "fix" not in info:
            info["fix"] = "%s:%d" % (rel, ln2)
    return info


def deliverables(b):
    t = read_text(os.path.join(b, "task.toml"), 200000)
    m = re.search(r"^\s*artifacts\s*=\s*\[(.*?)\]", t, re.M | re.S)
    out = set()
    if m:
        for p in re.findall(r'"([^"]+)"', m.group(1)):
            out.add(os.path.basename(p.rstrip("/")))
    ins = read_text(os.path.join(b, "instruction.md"))
    for p in re.findall(r"/app/[\w./-]+\.(?:py|sh|js|ts|rb|go|pl)", ins):
        out.add(os.path.basename(p))
    return out


def levers(task, settings):
    b = task["bundle"]
    fam = OrderedDict()
    if b:
        docs = doc_files(b)
        texts = [(os.path.relpath(p, b), read_text(p)) for p in docs]
        truth = read_text(os.path.join(b, "solution", "TRUTH.md"))
        tests = read_text(os.path.join(b, "tests", "test_output.py"))
        for fid, (label, rx) in FAMILY_TEXT.items():
            ev = []
            for rp, t in texts:
                for ln, line in all_lines(t, rx, 3):
                    ev.append("%s:%d %s" % (rp, ln, snip(line, 110)))
                if len(ev) >= 3:
                    break
            fam[fid] = {"label": label, "evidence": ev, "hits": len(ev)}
        gl = all_lines(tests, GEN_RE, 400)
        fam["D1"]["generator"] = len(gl)
        if gl:
            fam["D1"]["evidence"].insert(0, "tests/test_output.py:%d hidden data generator or held out inputs (%d lines)" % (gl[0][0], len(gl)))
        tl = all_lines(tests, re.compile(r"timeout\s*=\s*\d+"), 3)
        if tl:
            fam["D4"]["evidence"].insert(0, "tests/test_output.py:%d %s" % (tl[0][0], snip(tl[0][1], 90)))
        longest = max(texts, key=lambda x: len(x[1].split()), default=("", ""))
        words = len(longest[1].split())
        fam["D5"]["long_doc"] = (longest[0], words)
        if words >= 15000:
            fam["D5"]["evidence"].insert(0, "%s has %d words" % (longest[0], words))
        else:
            fam["D5"]["evidence"] = []
        d6 = all_lines(truth, re.compile(r"seeded (defects?|faults?)|\b\d+ (defects|faults)\b", re.I), 2)
        if d6:
            fam["D6"]["evidence"].insert(0, "solution/TRUTH.md:%d %s" % (d6[0][0], snip(d6[0][1], 100)))
        decoys = []
        env = os.path.join(b, "environment")
        if os.path.isdir(env):
            for d, dirs, files in os.walk(env):
                for f in files:
                    if DECOY_FILE.search(f):
                        decoys.append(os.path.relpath(os.path.join(d, f), b))
        dl = all_lines(truth, re.compile(r"\bdecoy", re.I), 2)
        dec_ev = ["decoy named file %s" % x for x in decoys[:2]] + ["solution/TRUTH.md:%d %s" % (ln, snip(l, 100)) for ln, l in dl]
        fam["decoy"] = {"label": "decoys", "evidence": dec_ev, "hits": len(dec_ev)}
    task["families"] = fam
    # checks lost in the basis runs
    basis = task["basis_runs"]
    lost = OrderedDict()
    pos_total = 0.0
    for r in basis:
        pos = sum(c["weight"] for c in r["checks"] if c["weight"] > 0)
        pos_total += pos
        for c in r["checks"]:
            if c["weight"] > 0 and c["value"] < 1:
                lost[c["name"]] = lost.get(c["name"], 0.0) + c["weight"] * (1 - c["value"])
    n = len(basis) or 1
    pos_avg = pos_total / n if basis else 0.0
    lost_list = sorted(((k, v / n) for k, v in lost.items()), key=lambda kv: -kv[1])
    task["lost"] = [(k, round(v, 3), round(100.0 * v / pos_avg, 2) if pos_avg else None) for k, v in lost_list]
    task["pos_weight"] = round(pos_avg, 3)
    # largest share one slip took: single check or one property across inputs
    names = [k for k, _ in lost_list]
    weight_of = dict(lost_list)
    parent = {k: k for k in names}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    toks = {k: k.split("_") for k in names}
    for i, a in enumerate(names):
        for bname in names[i + 1:]:
            ta, tb = toks[a], toks[bname]
            if len(ta) == len(tb) and len(ta) >= 2 and sum(1 for x, y in zip(ta, tb) if x != y) == 1:
                parent[root(a)] = root(bname)
    groups = {}
    for k in names:
        groups.setdefault(root(k), []).append(k)
    best = (None, 0.0)
    for g in groups.values():
        w = sum(weight_of[x] for x in g)
        if w > best[1]:
            best = (g, w)
    by_input = {}
    for k in names:
        m = INPUT_TOKEN.search(k)
        if m:
            by_input[m.group(1).lower()] = by_input.get(m.group(1).lower(), 0.0) + weight_of[k]
    if by_input:
        ik, iw = max(by_input.items(), key=lambda kv: kv[1])
        if iw > best[1]:
            best = (["input " + ik], iw)
    task["slip"] = None
    if best[0] and pos_avg:
        label = best[0][0] if len(best[0]) == 1 else "%s and %d similar" % (best[0][0], len(best[0]) - 1)
        task["slip"] = (label, round(100.0 * best[1] / pos_avg, 2))
    # whole document upper bound
    hidden_lost = sum(w for k, w in lost_list if not SHIPPED_NAME.search(k))
    task["hidden_lost_pct"] = round(100.0 * hidden_lost / pos_avg, 2) if pos_avg else None


def qc_hints(task, settings, kit):
    b = task["bundle"]
    hints = []
    if not b:
        return hints
    ins = read_text(os.path.join(b, "instruction.md"))
    for rp, t in [("instruction.md", ins)] + [(os.path.relpath(p, b), read_text(p)) for p in doc_files(b)[1:]]:
        sl = all_lines(t, STEP_RE, 50)
        if len(sl) >= 3:
            cid = "IN-14" if rp == "instruction.md" else "BR-SL1"
            hints.append((cid, "%s:%d step list, %d numbered or bulleted method lines (first: %s)" % (rp, sl[0][0], len(sl), snip(sl[0][1], 70))))
    for rp, t in [("instruction.md", ins)] + [(os.path.relpath(p, b), read_text(p)) for p in doc_files(b)[1:]]:
        al = all_lines(t, ANNOUNCE_RE, 3)
        if al:
            hints.append(("IN-17", "%s:%d announced trap wording: %s" % (rp, al[0][0], snip(al[0][1], 90))))
    if ins and not EXACT_BAR_RE.search(ins):
        hints.append(("CL-4", "instruction.md: no exact bar sentence found (CL-4 exemption needs one)"))
    cur = task.get("cur_tests") or {}
    wsum = sum(w for w in cur.values() if w and w > 0)
    if wsum:
        whole = sum(w for k, w in cur.items() if w and w > 0 and WHOLE_DOC_NAME.search(k) and not PER_ROW_NAME.search(k))
        perrow = [k for k, w in cur.items() if w and w > 0 and PER_ROW_NAME.search(k)]
        if whole / wsum >= 0.8 and not perrow:
            hints.append(("CL-4", "tests/test_output.py: %.0f%% of positive weight on whole document checks, no per row or per field check" % (100 * whole / wsum)))
    npos = len([k for k, w in cur.items() if w is None or w > 0])
    if cur:
        if len(cur) < 10:
            hints.append(("TS-23", "tests/test_output.py: %d checks, under 10" % len(cur)))
        elif len(cur) > 35:
            hints.append(("TS-23", "tests/test_output.py: %d checks, over 35 (warn)" % len(cur)))
    truth = read_text(os.path.join(b, "solution", "TRUTH.md"))
    tl = all_lines(truth, TRUTH_SCORE_RE, 3)
    if tl:
        hints.append(("DS-27", "solution/TRUTH.md:%d states run scores: %s (AL-7 asks each to be marked and sourced)" % (tl[0][0], snip(tl[0][1], 90))))
    jc = task.get("judge_crits") or []
    if os.path.isfile(os.path.join(b, "tests", "judge.toml")):
        if len(jc) < 8:
            hints.append(("JD-12", "tests/judge.toml: %d criteria, under 8" % len(jc)))
        elif len(jc) > 35:
            hints.append(("JD-12", "tests/judge.toml: %d criteria, over 35 (warn)" % len(jc)))
        wi = [c for c in jc if WHATIF_RE.search(c.get("description") or "")]
        if len(wi) > settings["what_if_max"]:
            hints.append(("WHAT-IF", "tests/judge.toml: %d what if figure criteria, cap %d (first %s)" % (len(wi), settings["what_if_max"], wi[0].get("id") or wi[0].get("name"))))
    perm = task.get("perm") or {}
    if perm.get("drop") and not perm.get("fix"):
        hints.append(("TS-24", "%s runs agent code as another uid; no read grant for the delivered program found (an editor written file is 0600)" % perm["drop"]))
    if task.get("slip") and task["slip"][1] > settings["slip_cap_pct"]:
        hints.append(("SLIP", "one slip took %.1f%% of positive test points (%s), cap %.0f%%" % (task["slip"][1], task["slip"][0], settings["slip_cap_pct"])))
    if task.get("trusted") and task["trusted"]["tests"] is not None and task["trusted"]["tests"] < 10:
        hints.append(("DS-21", "trusted tests under 10 percent: check that a shipped line decides every graded value before trusting the low score"))
    return [(cid, cid_ref(cid, kit), text) for cid, text in hints]


# ---------------------------------------------------------------- score and recommendation

def mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def score_task(task, settings):
    g = settings["gate"]
    tr = task["trusted"]
    parts = OrderedDict()
    if tr and tr["final"] is not None:
        dist = max((tr["tests"] or 0) - g["tests"], (tr["rubric"] or 0) - g["rubric"], tr["final"] - g["final"])
        task["gate_distance"] = round(dist, 2)
        parts["gate"] = 40.0 if dist < 0 else round(40.0 * max(0.0, 1 - dist / 50.0), 1)
    else:
        task["gate_distance"] = None
        parts["gate"] = 15.0
    lev = 0.0
    if tr and tr["tests"] is not None:
        lev += min(20.0, (100.0 - tr["tests"]) * 0.2)
    fams = [k for k, v in (task.get("families") or {}).items() if v.get("evidence")]
    lev += min(10.0, 2.0 * len(fams))
    parts["levers"] = round(lev, 1)
    struct_fails = [p for p in task["problems"] if not p[1].startswith("warn")]
    parts["qc"] = round(max(0.0, 20.0 - 3.0 * len(task["hints"]) - 2.0 * len(struct_fails)), 1)
    eff = 10.0
    if not task["bundle"]:
        eff -= 6
    if task.get("changed"):
        eff -= 2
    if not tr:
        eff -= 3
    if task.get("slip") and task["slip"][1] > settings["slip_cap_pct"]:
        eff -= 3
    if task["stats"].get("data_kb", 0) > 50 * 1024:
        eff -= 1
    if tr and tr["tests"] is not None and tr["tests"] < 10:
        eff -= 3
    parts["effort"] = max(0.0, eff)
    task["score_parts"] = parts
    task["score"] = round(sum(parts.values()), 1)
    # recommendation
    paid = [r for r in task["runs"] if r["paid"]]
    if not task["bundle"] and not task["runs"]:
        rec, why = "DROP", "nothing to triage in the folder"
    elif not tr:
        if paid:
            bad = [r for r in paid if r["status"] != "TRUSTED"]
            rec, why = "RE RUN FIRST", "no trusted %s run: %s" % (settings["paid_model"], "; ".join(sorted(set("%s %s" % (r["status"], r["sign"]) for r in bad))))
        else:
            rec, why = "RE RUN FIRST", "no %s run in the folder; P13 step 3b: QC first, then one paid run gives the score" % settings["paid_model"]
    elif task.get("changed"):
        rec, why = "REGRADE", "tests or judge changed after the trusted run (%s); K2: regrade the last valid run" % task["changed"]
    elif tr["tests"] is not None and tr["tests"] >= settings["kill_tests"]:
        rec, why = "DROP", "trusted tests %.1f at or over the kill line %.0f" % (tr["tests"], settings["kill_tests"])
    elif task["gate_distance"] is not None and task["gate_distance"] > 35:
        rec, why = "DROP", "trusted run %.1f points over the gate; levers would need a redesign" % task["gate_distance"]
    elif task["gate_distance"] is not None and task["gate_distance"] < 0:
        rec, why = "FIX AND PUSH", "trusted run under the gate (final %.1f); QC with the fix map, keep the design" % tr["final"]
    else:
        rec, why = "HARDEN WITH OWNER", "trusted run %.1f points over the gate; hardening changes the design, so the owner agrees first" % task["gate_distance"]
    if not task["bundle"] and task["runs"]:
        why = "runs only, no bundle found; " + why
    if rec == "FIX AND PUSH" and tr["tests"] is not None and tr["tests"] < 10:
        why += "; very low tests: confirm solvability (DS-21) first"
    broken = [r for r in paid if r["status"] == "BROKEN"]
    if broken and tr:
        why += "; %d broken paid run(s) left out" % len(broken)
    task["rec"], task["why"] = rec, why


# ---------------------------------------------------------------- per task assembly

def build_tasks(tops, settings):
    tasks = OrderedDict()
    for top in tops:
        top = os.path.abspath(top)
        bundles, runs, summaries = discover(top)
        bundles = [b for b in bundles if not any(b.startswith(r + os.sep) for r in runs)]
        by_name = {}
        for b in bundles:
            for nm in (os.path.basename(b), task_name_of_bundle(b)):
                if nm:
                    by_name.setdefault(nm, b)
        assign = {}
        for r in runs:
            b = ancestor(r, bundles)
            if not b:
                res = load_json(os.path.join(r, "result.json"))
                tn = (res or {}).get("task_name") if isinstance(res, dict) else None
                if tn:
                    tn = tn.split("/")[-1]
                    b = by_name.get(tn)
                if not b:
                    for part in os.path.relpath(r, top).split(os.sep):
                        if part in by_name:
                            b = by_name[part]
                            break
            if not b:
                first = os.path.relpath(r, top).split(os.sep)[0]
                b = "RUNS::" + os.path.join(top, first)
            assign.setdefault(b, []).append(r)
        extra = []
        for s in summaries:
            d = os.path.dirname(s)
            if not any(r.startswith(d + os.sep) for r in runs):
                b = ancestor(d, bundles) or ("RUNS::" + os.path.join(top, os.path.relpath(d, top).split(os.sep)[0]))
                extra.append((b, d))
        keys = list(bundles) + [k for k in assign if k.startswith("RUNS::")] + [b for b, _ in extra if b.startswith("RUNS::")]
        for key in keys:
            if key in tasks:
                continue
            bundle = None if key.startswith("RUNS::") else key
            root = key[6:] if key.startswith("RUNS::") else key
            name = os.path.basename(root)
            if any(t["name"] == name for t in tasks.values()):
                name = os.path.relpath(root, os.path.dirname(top))
            tasks[key] = {"name": name, "path": root, "bundle": bundle, "top": top, "run_paths": assign.get(key, []),
                          "summary_dirs": [d for b2, d in extra if b2 == key], "summaries": summaries}
    out = []
    for key, t in tasks.items():
        b = t["bundle"]
        if b:
            t["inventory"], t["problems"], t["stats"] = inventory(b, settings)
            t["cur_tests"] = test_criteria(b)
            t["judge_crits"] = judge_criteria(b)
            t["perm"] = perm_static(b)
            t["deliverables"] = deliverables(b)
        else:
            t["inventory"], t["problems"], t["stats"] = OrderedDict(), [], {"data_kb": 0, "data_files": 0, "formats": 0, "top_formats": "", "input_dirs": []}
            t["cur_tests"], t["judge_crits"], t["perm"], t["deliverables"] = OrderedDict(), [], {}, set()
        t["runs"] = [read_run(p, t["top"], t["summaries"], settings, t) for p in sorted(t["run_paths"])]
        for d in t["summary_dirs"]:
            s = load_json(os.path.join(d, "pass_summary.json")) or {}
            for row in (s.get("per_run") or [{}]):
                run = {"path": d, "rel": os.path.join(os.path.basename(t["top"]), os.path.relpath(d, t["top"])), "vdir": None,
                       "signals": [], "notes": [], "index": row.get("run_index"), "summary_only": True,
                       "model": s.get("model") or "unknown", "agent": None, "checks": [], "judge": [], "checks_source": None,
                       "tests": fnum(row.get("test_weights_percentage")), "rubric": fnum(row.get("rubric_weights_percentage")),
                       "final": fnum(row.get("combined_score")), "computed_tests": None, "score_source": "pass_summary.json",
                       "mode600": [], "agent_steps": None, "artifact_names": set()}
                run["paid"] = run["model"] == settings["paid_model"]
                classify(run, t)
                t["runs"].append(run)
        paid = [r for r in t["runs"] if r["paid"]]
        trusted = [r for r in paid if r["status"] == "TRUSTED"]
        t["basis_runs"] = trusted or paid
        t["basis_trusted"] = bool(trusted)
        t["recorded"] = {"tests": mean([r["tests"] for r in paid]), "rubric": mean([r["rubric"] for r in paid]),
                         "final": mean([r["final"] for r in paid])} if paid else None
        t["trusted"] = {"tests": mean([r["tests"] for r in trusted]), "rubric": mean([r["rubric"] for r in trusted]),
                        "final": mean([r["final"] for r in trusted]), "n": len(trusted)} if trusted else None
        # tests or judge changed after the run
        t["changed"] = ""
        if b and trusted:
            last = trusted[-1]
            run_names = {c["name"]: c["weight"] for c in last["checks"]}
            cur = t["cur_tests"]
            if run_names and cur:
                added = [k for k in cur if k not in run_names]
                gone = [k for k in run_names if k not in cur]
                rew = [k for k in cur if k in run_names and cur[k] is not None and abs((cur[k] or 0) - run_names[k]) > 1e-9]
                if added or gone or rew:
                    t["changed"] = "tests: %d added, %d removed, %d reweighted since the run" % (len(added), len(gone), len(rew))
            jr = last["judge"]
            jc = t["judge_crits"]
            if jr and jc:
                rk = set((j["name"] or j["desc"]).strip() for j in jr)
                ck = set((c["name"] if jr[0]["name"] else c["description"]).strip() for c in jc)
                if rk != ck:
                    diff = len(rk ^ ck)
                    t["changed"] += ("; " if t["changed"] else "") + "judge: %d criteria differ from the run" % diff
        levers(t, settings)
        out.append(t)
    return out


# ---------------------------------------------------------------- output

def fmt(v, nd=1):
    return "" if v is None else ("%.*f" % (nd, v))


def trf(d):
    if not d:
        return "none"
    return "%s / %s / %s" % (fmt(d["tests"]), fmt(d["rubric"]), fmt(d["final"]))


def write_outputs(tasks, settings, kit, out_dir, tops):
    os.makedirs(out_dir, exist_ok=True)
    tasks.sort(key=lambda t: (-t["score"], t["name"]))
    g = settings["gate"]
    L = []
    L.append("TRIAGE (read only, triage_tasks.py %s)" % VERSION)
    L.append("")
    L.append("Tasks folders: %s" % ", ".join(os.path.basename(os.path.abspath(x)) for x in tops))
    L.append("Gate: tests under %g, rubric under %g, final under %g; slip cap %g percent; paid model %s; settings from %s." % (
        g["tests"], g["rubric"], g["final"], settings["slip_cap_pct"], settings["paid_model"], os.path.basename(settings["source"]) if os.path.sep in settings["source"] else settings["source"]))
    L.append("Kit ids: %s." % ("located in the given kit folder" if kit else "default ids (no kit folder given)"))
    L.append("Scores are percent: tests / rubric / final. Trusted means paid model runs with no broken or unsure sign; broken runs never count.")
    L.append("Every QC risk and family line is a hint with its file and line, never a verdict.")
    L.append("")
    L.append("RANKED TABLE")
    L.append("")
    L.append("| rank | task | score | recommendation | trusted T / R / F | recorded T / R / F | paid runs T B U | sign | to gate | families | slip pct | QC hints | why |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, t in enumerate(tasks, 1):
        paid = [r for r in t["runs"] if r["paid"]]
        cnt = "%d %d %d" % (sum(r["status"] == "TRUSTED" for r in paid), sum(r["status"] == "BROKEN" for r in paid), sum(r["status"] == "UNSURE" for r in paid))
        signs = sorted(set(r["sign"] for r in paid if r["sign"]))
        fams = [k for k, v in t["families"].items() if v.get("evidence")]
        t["rank"] = i
        L.append("| %d | %s | %.1f | %s | %s | %s | %s | %s | %s | %s | %s | %d | %s |" % (
            i, t["name"], t["score"], t["rec"], trf(t["trusted"]), trf(t["recorded"]), cnt, "; ".join(signs) or "none",
            fmt(t["gate_distance"]) if t["gate_distance"] is not None else "unknown", " ".join(fams) or "none",
            fmt(t["slip"][1]) if t.get("slip") else "", len(t["hints"]), t["why"].replace("|", "/")))
    L.append("")
    L.append("Score parts: gate 0 to 40 (40 when the trusted run is under the gate, falls with the distance, 15 when unknown); levers 0 to 30 (0.2 per lost test percent, at most 20, plus 2 per family with evidence, at most 10); QC 0 to 20 (20 minus 3 per QC hint and 2 per structure fail); effort 0 to 10 (minus 6 no bundle, 3 no trusted run, 3 slip over the cap, 3 trusted tests under 10 (solvability check first), 2 regrade needed, 1 data over 50 MB).")
    L.append("")
    for t in tasks:
        L.append("TASK %d. %s" % (t["rank"], t["name"]))
        L.append("")
        L.append("Recommendation: %s. %s." % (t["rec"], t["why"]))
        p = t["score_parts"]
        L.append("Score %.1f = gate %.1f + levers %.1f + QC %.1f + effort %.1f. Distance to gate: %s." % (
            t["score"], p["gate"], p["levers"], p["qc"], p["effort"], fmt(t["gate_distance"]) if t["gate_distance"] is not None else "unknown"))
        L.append("Real score (trusted %s runs): %s. Recorded score (every paid run): %s." % (
            settings["paid_model"], trf(t["trusted"]), trf(t["recorded"])))
        if t["bundle"]:
            have = [k for k, v in t["inventory"].items() if v]
            miss = [k for k, v in t["inventory"].items() if not v and k != "solution/solve.py" and k != "trajectories/"]
            L.append("Inventory: bundle at %s; present %d of %d kit files%s; data %d KB in %d files, %d formats (%s)." % (
                os.path.relpath(t["bundle"], os.path.dirname(t["top"])), len([k for k in have if k in REQUIRED]), len(REQUIRED),
                ("; missing " + ", ".join(miss)) if miss else "", t["stats"]["data_kb"], t["stats"]["data_files"], t["stats"]["formats"], t["stats"]["top_formats"] or "none"))
            L.append("Tests now: %d checks, positive weight %s; judge now: %d criteria." % (
                len(t["cur_tests"]), fmt(sum(w for w in t["cur_tests"].values() if w and w > 0)), len(t["judge_crits"])))
        else:
            L.append("Inventory: no bundle found, runs only.")
        if t["problems"]:
            L.append("Structure problems:")
            for n, (cid, text) in enumerate(t["problems"], 1):
                L.append("%d. %s %s" % (n, cid_ref(cid, kit), text))
        else:
            L.append("Structure problems: none found." if t["bundle"] else "Structure problems: not checked (no bundle).")
        L.append("Runs:")
        if not t["runs"]:
            L.append("1. none found")
        for n, r in enumerate(t["runs"], 1):
            L.append("%d. %s %s, model %s%s: tests %s, rubric %s, final %s (from %s)%s" % (
                n, r["status"], ("(" + r["sign"] + ")") if r["sign"] else "", r["model"],
                "" if r["paid"] else " (not the paid model, shown only)", fmt(r["tests"]), fmt(r["rubric"]), fmt(r["final"]),
                r["score_source"], ("; evidence: " + r["evidence"]) if r["evidence"] else ""))
            L.append("   folder %s" % r["rel"])
            for s in r["signals"][1:3]:
                L.append("   also %s %s: %s" % (s[0], s[1], s[2]))
            for note in r["notes"][:2]:
                L.append("   note: %s" % note)
        L.append("Levers and traps (likely families, hints):")
        fams = [(k, v) for k, v in t["families"].items() if v.get("evidence")]
        if not fams:
            L.append("1. none found in the docs or tests")
        for n, (k, v) in enumerate(fams, 1):
            L.append("%d. %s %s: %s" % (n, k, v["label"], " | ".join(v["evidence"][:2])))
        if t["lost"]:
            src = "trusted" if t["basis_trusted"] else "untrusted (no trusted run)"
            L.append("Checks the paid model lost (%s runs, positive test weight %s):" % (src, fmt(t["pos_weight"])))
            for n, (k, w, sh) in enumerate(t["lost"][:8], 1):
                L.append("%d. %s lost %s (%s percent)" % (n, k, fmt(w, 2), fmt(sh)))
            if len(t["lost"]) > 8:
                L.append("%d. and %d more" % (9, len(t["lost"]) - 8))
            if t.get("slip"):
                L.append("Largest share one slip took: %s percent (%s) against the cap %g percent; all hidden input checks lost together %s percent." % (
                    fmt(t["slip"][1]), t["slip"][0], settings["slip_cap_pct"], fmt(t["hidden_lost_pct"])))
        elif t["basis_runs"]:
            L.append("Checks the paid model lost: none.")
        L.append("QC risk hints:")
        if not t["hints"]:
            L.append("1. none found")
        for n, (cid, ref, text) in enumerate(t["hints"], 1):
            L.append("%d. %s: %s" % (n, ref, text))
        L.append("Next: %s" % next_step(t, settings))
        L.append("")
    md = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "TRIAGE.md"), "w", encoding="utf-8") as f:
        f.write(md)
    cols = ["rank", "task", "score", "recommendation", "why", "trusted_tests", "trusted_rubric", "trusted_final",
            "trusted_runs", "recorded_tests", "recorded_rubric", "recorded_final", "paid_runs", "broken_runs", "unsure_runs",
            "broken_signs", "gate_distance", "families", "slip_pct", "slip_check", "hidden_lost_pct", "qc_hints",
            "structure_problems", "regrade", "score_gate", "score_levers", "score_qc", "score_effort", "data_kb", "path"]
    with open(os.path.join(out_dir, "triage.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for t in tasks:
            paid = [r for r in t["runs"] if r["paid"]]
            tr, rc = t["trusted"] or {}, t["recorded"] or {}
            w.writerow([t["rank"], t["name"], t["score"], t["rec"], t["why"], tr.get("tests"), tr.get("rubric"), tr.get("final"),
                        tr.get("n", 0), rc.get("tests"), rc.get("rubric"), rc.get("final"), len(paid),
                        sum(r["status"] == "BROKEN" for r in paid), sum(r["status"] == "UNSURE" for r in paid),
                        "; ".join(sorted(set(r["sign"] for r in paid if r["sign"]))), t["gate_distance"],
                        " ".join(k for k, v in t["families"].items() if v.get("evidence")),
                        t["slip"][1] if t.get("slip") else "", t["slip"][0] if t.get("slip") else "", t["hidden_lost_pct"],
                        len(t["hints"]), len(t["problems"]), t["changed"], t["score_parts"]["gate"], t["score_parts"]["levers"],
                        t["score_parts"]["qc"], t["score_parts"]["effort"], t["stats"].get("data_kb"),
                        os.path.relpath(t["path"], os.path.dirname(t["top"]))])
    js = {"version": VERSION, "settings": {"gate": g, "slip_cap_pct": settings["slip_cap_pct"], "paid_model": settings["paid_model"],
                                           "what_if_max": settings["what_if_max"], "source": settings["source"]},
          "kit_ids_located": kit, "tasks": []}
    for t in tasks:
        js["tasks"].append({
            "rank": t["rank"], "task": t["name"], "path": os.path.relpath(t["path"], os.path.dirname(t["top"])), "score": t["score"],
            "score_parts": t["score_parts"], "recommendation": t["rec"], "why": t["why"], "trusted": t["trusted"],
            "recorded": t["recorded"], "gate_distance": t["gate_distance"], "regrade": t["changed"],
            "inventory": t["inventory"], "structure_problems": [{"id": c, "text": x} for c, x in t["problems"]],
            "data": t["stats"], "tests_now": len(t["cur_tests"]), "judge_now": len(t["judge_crits"]),
            "runs": [{"folder": r["rel"], "model": r["model"], "paid": r["paid"], "status": r["status"], "sign": r["sign"],
                      "evidence": r["evidence"], "tests": r["tests"], "rubric": r["rubric"], "final": r["final"],
                      "score_source": r["score_source"], "signals": [{"level": s[0], "sign": s[1], "evidence": s[2]} for s in r["signals"]],
                      "notes": r["notes"],
                      "checks": [{"name": c["name"], "weight": c["weight"], "value": c["value"]} for c in r["checks"]],
                      "judge": [{"id": j["id"], "weight": j["weight"], "value": j["value"]} for j in r["judge"]]} for r in t["runs"]],
            "families": {k: {"label": v["label"], "evidence": v["evidence"]} for k, v in t["families"].items() if v.get("evidence")},
            "lost_checks": [{"check": k, "lost_weight": w, "share_pct": s} for k, w, s in t["lost"]],
            "positive_test_weight": t["pos_weight"], "slip": {"check": t["slip"][0], "pct": t["slip"][1]} if t.get("slip") else None,
            "hidden_lost_pct": t["hidden_lost_pct"],
            "qc_hints": [{"id": c, "ref": r, "text": x} for c, r, x in t["hints"]], "next": next_step(t, settings)})
    with open(os.path.join(out_dir, "triage.json"), "w", encoding="utf-8") as f:
        json.dump(js, f, indent=1, sort_keys=False, default=list)
    return md


def next_step(t, settings):
    rec = t["rec"]
    if rec == "RE RUN FIRST":
        signs = set(s[1] for r in t["runs"] if r["paid"] for s in r["signals"])
        if any(s.startswith("permission") for s in signs):
            return ("ask Ayush: replay the saved artifacts with readable modes (oracle replay, as the low score study did), "
                    "or regrade, or one new paid run after the tests grant read access; the owner agrees to any tests change.")
        if any("judge" in s for s in signs):
            return "ask Ayush: regrade the run (judge only) or one new paid run."
        return "ask Ayush: oracle and nop first, then one new paid run on the frozen bytes; no Docker without his choice."
    if rec == "REGRADE":
        return "ask Ayush: regrade the last valid run with the current tests and judge (K2), then triage again."
    if rec == "FIX AND PUSH":
        return "P13 intake (assigned or teammate_agreed), full QC, fix with the fix map, keep design and author, push under the gate."
    if rec == "HARDEN WITH OWNER":
        return "read the lost checks and families; propose a hardening that keeps the design; the owner agrees before any change (P13)."
    return "leave it unless Ayush wants it; say why in one line."


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read only triage of Harbor tasks and their runs.")
    ap.add_argument("--tasks-dir", action="append", required=True, help="folder holding task bundles, runs, or both (repeatable)")
    ap.add_argument("--settings", help="settings.json for gate, slip_cap_pct, models.paid_run, what_if_max")
    ap.add_argument("--out", required=True, help="output folder for TRIAGE.md, triage.csv, triage.json")
    ap.add_argument("--kit", help="QC kit folder (Input_Bundle_QC), only to locate check ids")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    for d in a.tasks_dir:
        if not os.path.isdir(d):
            sys.exit("tasks folder not found: %s" % d)
        top = os.path.abspath(d)
        if out == top or out.startswith(top + os.sep):
            sys.exit("refusing: --out %s is inside the tasks folder %s (triage never writes there)" % (out, top))
    settings = load_settings(a.settings)
    kit = load_kit(a.kit)
    tasks = build_tasks(a.tasks_dir, settings)
    for t in tasks:
        t["hints"] = []
    for t in tasks:
        t["hints"] = qc_hints(t, settings, kit)
        score_task(t, settings)
    write_outputs(tasks, settings, kit, out, a.tasks_dir)
    print("triage: %d tasks, %d runs; wrote %s" % (len(tasks), sum(len(t["runs"]) for t in tasks),
                                                     ", ".join(os.path.join(out, n) for n in ("TRIAGE.md", "triage.csv", "triage.json"))))
    for t in tasks:
        print("%2d  %5.1f  %-17s %s" % (t["rank"], t["score"], t["rec"], t["name"]))


if __name__ == "__main__":
    main()
