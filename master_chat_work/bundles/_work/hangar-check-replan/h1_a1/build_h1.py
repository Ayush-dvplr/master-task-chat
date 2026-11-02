"""harden_r1 build: patch BUNDLE tests/solution/instruction from the pre_build snapshot.

Every replace asserts exactly one match. Run: python3 -B build_h1.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRE = HERE / "pre_build"
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/hangar-check-replan")


def once(text, old, new):
    n = text.count(old)
    assert n == 1, "expected 1 match, got %d: %r" % (n, old[:80])
    return text.replace(old, new, 1)


# ---------------------------------------------------------------- tests/test_output.py
t = (PRE / "tests" / "test_output.py").read_text(encoding="utf-8")

t = once(t, "import shutil\n", "import shutil\nimport signal\n")
t = once(t, "import threading\n", "import threading\nimport time\n")

FORM_CODE = r'''

_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
_W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
# held-out Word forms: table -> (file, header pair, value cell)
_FORM_TABLES = {"allow": ("planning_limits.docx", ("base", "allowance_shifts"), 1),
                "close": ("disruption_notice.docx", ("base", "from"), 2),
                "avail": ("disruption_notice.docx", ("tail", "available_from"), 1)}
_FORM_ROOT = '<w:document xmlns:w="'
_FORM_ROOT_WIDE = ('<w:document xmlns:mc="%s" xmlns:w14="%s" xmlns:w15="%s" mc:Ignorable="w14 w15" xmlns:w="'
                   % (_MC, _W14, _W15))
_FORM_RUN = re.compile(r'<w:r><w:t xml:space="preserve">[^<]*</w:t></w:r>')


def _form_rows(kind, rows, cell):
    """The data rows of one table written in WordprocessingML form `kind`; every cell keeps its text."""
    if kind == "sdt":
        items = "".join('<w:sdt><w:sdtPr><w:id w:val="%d"/><w15:repeatingSectionItem/></w:sdtPr>'
                        '<w:sdtContent>%s</w:sdtContent></w:sdt>' % (900 + k, row) for k, row in enumerate(rows))
        return ('<w:sdt><w:sdtPr><w:alias w:val="rows"/><w:id w:val="899"/><w15:repeatingSection/></w:sdtPr>'
                '<w:sdtContent>%s</w:sdtContent></w:sdt>' % items)
    if kind == "cxml":
        return "".join('<w:customXml w:uri="urn:planning" w:element="row">%s</w:customXml>' % row for row in rows)
    assert kind == "alt", kind
    out = []
    for row in rows:
        cells = re.findall(r"<w:tc>.*?</w:tc>", row, re.S)
        run = _FORM_RUN.search(cells[cell]).group(0)
        choice = run.replace("<w:r>", '<w:r><w:rPr><w14:ligatures w14:val="standard"/></w:rPr>', 1)
        cells[cell] = cells[cell].replace(run, '<mc:AlternateContent><mc:Choice Requires="w14">%s</mc:Choice>'
                                          '<mc:Fallback>%s</mc:Fallback></mc:AlternateContent>' % (choice, run), 1)
        head, tail = row[:row.index("<w:tc>")], row[row.rindex("</w:tc>") + len("</w:tc>"):]
        out.append(head + "".join(cells) + tail)
    return "".join(out)


def _form_plain(doc):
    """Undo the held-out Word forms by text: the plain document part write_docx wrote."""
    doc = doc.replace(_FORM_ROOT_WIDE, _FORM_ROOT, 1)
    doc = re.sub(r"<w:sdt><w:sdtPr>.*?</w:sdtPr><w:sdtContent>", "", doc, flags=re.S)
    doc = doc.replace("</w:sdtContent></w:sdt>", "")
    doc = re.sub(r"<w:customXml [^>]*>|</w:customXml>", "", doc)
    return re.sub(r"<mc:AlternateContent><mc:Choice [^>]*>.*?</mc:Choice><mc:Fallback>(.*?)</mc:Fallback>"
                  r"</mc:AlternateContent>", r"\1", doc, flags=re.S)


def _reform(data, table, kind):
    """Rewrite the data rows of one table of a held-out folder in another WordprocessingML form, values unchanged."""
    name, head, cell = _FORM_TABLES[table]
    path = Path(data) / name
    before = _docx_tables(path)
    with zipfile.ZipFile(path) as z:
        items = [(info, z.read(info)) for info in z.infolist()]
    k = next(i for i, (info, _) in enumerate(items) if info.filename == "word/document.xml")
    doc = items[k][1].decode("utf-8")
    new = doc
    for tbl in re.findall(r"<w:tbl>.*?</w:tbl>", doc, re.S):
        rows = re.findall(r"<w:tr>.*?</w:tr>", tbl, re.S)
        if tuple(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", rows[0])[:2]) == head:
            assert len(rows) > 1, "table %s has no data rows" % table
            new = doc.replace(tbl, tbl.replace("".join(rows[1:]), _form_rows(kind, rows[1:], cell), 1), 1)
            break
    assert new != doc, "table %s not found in %s" % (table, name)
    new = new.replace(_FORM_ROOT, _FORM_ROOT_WIDE, 1)
    assert _form_plain(new) == doc, "held-out form of %s changed a value" % name
    ET.fromstring(new.encode("utf-8"))
    items[k] = (items[k][0], new.encode("utf-8"))
    with zipfile.ZipFile(path, "w") as z:
        for info, blob in items:
            z.writestr(info, blob)
    assert _docx_tables(path) != before, "held-out form of %s reads the same row by row" % name
'''
t = once(t, "    return out\n\n\ndef _date(s):", "    return out\n" + FORM_CODE + "\n\ndef _date(s):")

OLD_HIDDEN_TAIL = '          "h4": (3, False, "bind", False), "h5": (5, False, "bind", True), "h6": (6, False, "bind", False)}\n'
t = once(t, OLD_HIDDEN_TAIL, OLD_HIDDEN_TAIL +
         '# name: (seed, table, Word form of its data rows)\n'
         'FORMS = {"h7": (7, "allow", "sdt"), "h8": (8, "allow", "cxml"), "h9": (9, "allow", "alt"),\n'
         '         "h10": (10, "close", "sdt"), "h11": (11, "close", "cxml"), "h12": (12, "close", "alt"),\n'
         '         "h13": (13, "avail", "sdt"), "h14": (14, "avail", "cxml"), "h15": (15, "avail", "alt")}\n')

t = once(t, "_CASE_LOCK = threading.Lock()\n",
         "_CASE_LOCK = threading.Lock()\n"
         "# one untrusted run at a time; held across the run and the sweep of what it left\n"
         "_RUN_LOCK = threading.RLock()\n")

LAUNCH = r'''

def _stop_untrusted(group: int) -> None:
    """Kill the run's process group and, when isolated, every process left under the dropped uid."""
    if os.name != "posix":
        return
    try:
        os.killpg(group, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if os.geteuid() != 0:
        return
    import pwd
    uid = str(pwd.getpwnam("nobody").pw_uid)
    for _ in range(20):
        found = False
        for entry in sorted(Path("/proc").iterdir()):
            if not entry.name.isdigit():
                continue
            try:
                status = (entry / "status").read_text(encoding="utf-8")
            except OSError:
                continue
            line = next((row for row in status.splitlines() if row.startswith("Uid:")), "")
            if uid not in line.split()[1:2] or "State:\tZ" in status:
                continue
            found = True
            try:
                os.kill(int(entry.name), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if not found:
            return
        time.sleep(0.05)


def _launch(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run an untrusted command in its own session; when this returns, every process it started is gone."""
    with _RUN_LOCK, tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(_untrusted_command(command), cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=err,
                                start_new_session=True)
        try:
            proc.wait(timeout=RUN_LIMIT)
        except subprocess.TimeoutExpired:
            _stop_untrusted(proc.pid)
            proc.wait()
            raise
        finally:
            _stop_untrusted(proc.pid)
        err.seek(0)
        return subprocess.CompletedProcess(command, proc.returncode, "", err.read())
'''
t = once(t, "\n\ndef _run_program(", LAUNCH + "\n\ndef _run_program(")

t = once(t,
         '        subprocess.run(_untrusted_command(["python3", str(SCRIPT), str(data), str(out)]), cwd=str(cwd), check=True,\n'
         '                       timeout=RUN_LIMIT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n',
         '        run = _launch(["python3", str(SCRIPT), str(data), str(out)], cwd)\n'
         '        if run.returncode != 0:\n'
         '            raise subprocess.CalledProcessError(run.returncode, run.args)\n')

t = once(t,
         '        root = Path(tempfile.mkdtemp(prefix="hangar-%s-" % name))\n'
         '        root.chmod(0o755)\n'
         '        case: dict[str, Any] = {}\n',
         '        root = Path(tempfile.mkdtemp(prefix="hangar-%s-" % name))\n'
         '        case: dict[str, Any] = {}\n')
t = once(t,
         '                case["meta"] = inst["meta"]\n'
         '            else:\n'
         '                data = _mutant_data(name, root)\n',
         '                case["meta"] = inst["meta"]\n'
         '            elif name in FORMS:\n'
         '                seed, table, kind = FORMS[name]\n'
         '                data = root / "data"\n'
         '                data.mkdir()\n'
         '                inst, want = _planted_corpus(name, seed, False, "bind", False, data)\n'
         '                case["meta"] = inst["meta"]\n'
         '                _reform(data, table, kind)\n'
         '                _seal(data)\n'
         '            else:\n'
         '                data = _mutant_data(name, root)\n')
t = once(t,
         '            case["stray"] = []\n'
         '            case["got"] = _run_program(data, work, case["stray"])\n',
         '            case["stray"] = []\n'
         '            with _RUN_LOCK:\n'
         '                root.chmod(0o755)\n'
         '                try:\n'
         '                    case["got"] = _run_program(data, work, case["stray"])\n'
         '                finally:\n'
         '                    root.chmod(0o700)\n'
         '                    shutil.rmtree(work, ignore_errors=True)\n')

t = once(t,
         '    run = subprocess.run(_untrusted_command(["python3", str(SCRIPT), str(data), str(out)]), cwd=str(cwd),\n'
         '                         timeout=RUN_LIMIT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,\n'
         '                         errors="replace")\n',
         '    run = _launch(["python3", str(SCRIPT), str(data), str(out)], cwd)\n')

# negative writes-outside also covers the new folders
t = once(t, 'for name in list(HIDDEN) + ["m1", "m2"]:', 'for name in list(HIDDEN) + list(FORMS) + ["m1", "m2"]:')

# registrations: copy the h6 blocks
SUFFIX_ALLOW = ("settlement_per_check", "settlement_by_base_and_segment", "settlement_summary")
SUFFIX_PLAN = ("plan_rows", "plan_group_totals", "settlement_per_check", "settlement_summary")
blocks = {}
for suffix in set(SUFFIX_ALLOW + SUFFIX_PLAN):
    m = re.findall(r'@criterion\(description="On held-out data folder h6, [^\n]*\n'
                   r'def h6_%s\(workspace: Path\) -> bool:\n    return [^\n]*\n' % suffix, t)
    assert len(m) == 1, suffix
    blocks[suffix] = m[0]
new_regs, new_weights = [], []
for n in range(7, 16):
    suffixes = SUFFIX_ALLOW if n <= 9 else SUFFIX_PLAN
    for suffix in suffixes:
        new_regs.append(blocks[suffix].replace("h6", "h%d" % n) + "\n\n")
        new_weights.append("criteria.h%d_%s(weight=5)\n" % (n, suffix))
first_penalty = '@criterion(description="Penalty: the program text carries request ids of the shipped plan.")'
t = once(t, first_penalty, "".join(new_regs) + first_penalty)
t = once(t, "criteria.negative_hardcoded_sample_answers(weight=-5)\n",
         "".join(new_weights) + "criteria.negative_hardcoded_sample_answers(weight=-5)\n")
for n in range(1, 7):  # W2 allows weights in {1, 3, 5}: old settlement checks 5 -> 1, plan rows stay 3
    for suffix in ("settlement_per_check", "settlement_by_base_and_segment", "settlement_summary"):
        t = once(t, "criteria.h%d_%s(weight=5)\n" % (n, suffix), "criteria.h%d_%s(weight=1)\n" % (n, suffix))
(BUNDLE / "tests" / "test_output.py").write_text(t, encoding="utf-8")

# ---------------------------------------------------------------- tests/reward.toml
r = (PRE / "tests" / "reward.toml").read_text(encoding="utf-8")
r = once(r, "test_output = 0.0036496350364963502", "test_output = %r" % (1 / 460))
r = once(r, "judge = 0.011904761904761904", "judge = %r" % (1 / 78))
(BUNDLE / "tests" / "reward.toml").write_text(r, encoding="utf-8")

# ---------------------------------------------------------------- tests/judge.toml
j = (PRE / "tests" / "judge.toml").read_text(encoding="utf-8")
parts = j.split("[[criterion]]\n")
head, crit = parts[0], parts[1:]
ANN = ('type = "binary"\nweight = 3\n\n[criterion.annotations]\nmode = "judged"\ntype = "agent behavior"\n'
       'evaluation_target = "trajectory"\nimportance = "important"\n\n')
R19 = ('id = "R19"\nname = "reruns_with_a_closure_added"\n'
       'description = "The agent runs /app/out/derive_report.py on a copy of the inputs in which it added a row to the '
       'base and from table of disruption_notice.docx, and shows a check whose start_date or finish_date in '
       'policy_audit.json differs from the run on the shipped inputs."\n' + ANN)
R20 = ('id = "R20"\nname = "reruns_with_a_revised_availability"\n'
       'description = "The agent runs /app/out/derive_report.py on a copy of the inputs in which it changed or added the '
       'available_from value of a tail in disruption_notice.docx, and shows that the start_date in policy_audit.json '
       'of a check of that tail differs from the run on the shipped inputs."\n' + ANN)
kept = []
for block in crit:
    cid = re.match(r'id = "(R\d+)"', block).group(1)
    if cid in ("R6", "R8", "R9"):
        continue
    kept.append(block)
    if cid == "R14":
        kept += [R19, R20]
assert len(kept) == 17
kept = [re.sub(r'^id = "R\d+"', 'id = "R%d"' % (k + 1), b, count=1) for k, b in enumerate(kept)]  # J2 sequential ids
j = head + "".join("[[criterion]]\n" + b for b in kept)
(BUNDLE / "tests" / "judge.toml").write_text(j, encoding="utf-8")

# ---------------------------------------------------------------- solution/solve.py
s = (PRE / "solution" / "solve.py").read_text(encoding="utf-8")
READER = '''MCE = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_WRAPPERS = (WML + "sdt", WML + "sdtContent", WML + "customXml")


def _branch(node):
    """The one branch of an mc:AlternateContent a reader keeps: Fallback, else the first Choice."""
    fallback = node.find(MCE + "Fallback")
    return fallback if fallback is not None else node.find(MCE + "Choice")


def _content(parent, tag):
    """Children of `parent` with `tag`, looking through content controls, custom XML and AlternateContent."""
    for child in parent:
        if child.tag == tag:
            yield child
        elif child.tag in _WRAPPERS:
            yield from _content(child, tag)
        elif child.tag == MCE + "AlternateContent":
            kept = _branch(child)
            if kept is not None:
                yield from _content(kept, tag)


def _text(node):
    """The w:t text under `node`, one branch of each AlternateContent, nested tables left out."""
    for child in node:
        if child.tag == WML + "t":
            yield child.text or ""
        elif child.tag == MCE + "AlternateContent":
            kept = _branch(child)
            if kept is not None:
                yield from _text(kept)
        elif child.tag != WML + "tbl":
            yield from _text(child)


'''
s = once(s, "class InputError(Exception):\n", READER + "class InputError(Exception):\n")
s = once(s,
         '            for table_row in table.findall(WML + "tr"):\n'
         '                grid.append(["".join(node.text or "" for node in cell.iter(WML + "t")).strip()\n'
         '                             for cell in table_row.findall(WML + "tc")])\n',
         '            for table_row in _content(table, WML + "tr"):\n'
         '                grid.append(["".join(_text(cell)).strip() for cell in _content(table_row, WML + "tc")])\n')
(BUNDLE / "solution" / "solve.py").write_text(s, encoding="utf-8")

# ---------------------------------------------------------------- solution/solve.sh
sh = (PRE / "solution" / "solve.sh").read_text(encoding="utf-8")
P10 = '''

    # P10 a closure row on the start day of a scheduled check moves that check
    r = next(x for x in plan if x["decision"] == "scheduled")
    d = copy_data("p10")
    add_row(os.path.join(d, "disruption_notice.docx"), ("base", "from"), [r["base"], r["start_date"], 1])
    assert run(d, d + "_out").returncode == 0
    got = {x["request_id"]: x for x in outputs(d + "_out")["policy_audit.json"]["checks"]}[r["request_id"]]
    assert (got["start_date"], got["finish_date"]) != (r["start_date"], r["finish_date"])
    say("P10", "closure %s from %s for 1 day: %s start %s finish %s -> start %s finish %s"
        % (r["base"], r["start_date"], r["request_id"], r["start_date"], r["finish_date"],
           got["start_date"], got["finish_date"]))

    # P11 a later available_from for the tail of a scheduled check moves that check
    import tomllib
    with open(os.path.join(DATA, "fleet_limits.toml"), "rb") as f:
        end = str(tomllib.load(f)["season_end"])
    r = next(x for x in plan if x["decision"] == "scheduled" and x["start_date"] < end)
    later = (datetime.date.fromisoformat(r["start_date"]) + datetime.timedelta(days=1)).isoformat()
    d = copy_data("p11")
    path = os.path.join(d, "disruption_notice.docx")
    if any(row[0] == r["tail"] for row in tables(path)[("tail", "available_from")]):
        set_cell(path, r["tail"], 1, later)
    else:
        add_row(path, ("tail", "available_from"), [r["tail"], later])
    assert run(d, d + "_out").returncode == 0
    got = {x["request_id"]: x for x in outputs(d + "_out")["policy_audit.json"]["checks"]}[r["request_id"]]
    assert got["start_date"] != r["start_date"]
    say("P11", "tail %s available_from %s: %s start %s -> %s"
        % (r["tail"], later, r["request_id"], r["start_date"], got["start_date"]))
'''
P9_END = '''    say("P9", "East empty: region_East.json %s, summary row %s" % (json.dumps(o9["region_East.json"]), east[0]))\n'''
sh = once(sh, P9_END, P9_END.rstrip("\n") + P10)
ADD_ROW = '''def add_row(path, head, values):
    """Append a row, copied from the last row, to the table whose header starts with `head`."""
    import copy
    with zipfile.ZipFile(path) as z:
        parts = {i.filename: z.read(i.filename) for i in z.infolist()}
    root = ET.fromstring(parts["word/document.xml"])
    for tbl in root.iter("{%s}tbl" % WNS):
        rows = tbl.findall("{%s}tr" % WNS)
        if tuple(cell_text(tc) for tc in rows[0].findall("{%s}tc" % WNS))[:2] == head:
            row = copy.deepcopy(rows[-1])
            for tc, value in zip(row.findall("{%s}tc" % WNS), values):
                list(tc.iter("{%s}t" % WNS))[0].text = str(value)
            tbl.append(row)
    parts["word/document.xml"] = ET.tostring(root, xml_declaration=True, encoding="UTF-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in parts.items():
            z.writestr(name, blob)


if __name__ == "__main__":
'''
sh = once(sh, 'if __name__ == "__main__":\n', ADD_ROW)
(BUNDLE / "solution" / "solve.sh").write_text(sh, encoding="utf-8")

# ---------------------------------------------------------------- instruction.md (route1 R0.7)
ins = (BUNDLE / "instruction.md").read_text(encoding="utf-8")
if "Leave enough of that time" not in ins:
    ins = once(ins, "You have 7200 seconds to complete this task.\n",
               "You have 7200 seconds to complete this task. Leave enough of that time to finish and write your final reply.\n")
    (BUNDLE / "instruction.md").write_text(ins, encoding="utf-8")
print("BUILD_OK")
