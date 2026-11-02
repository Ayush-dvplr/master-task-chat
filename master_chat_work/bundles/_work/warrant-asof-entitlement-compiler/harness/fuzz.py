"""usage: fuzz.py <prog_dir> <seed:scale:variant> <mutation|all> ...
Builds a corpus with the bundle generator, applies one documented-edge mutation before
attestations are derived, then diffs the program against the reference."""
import csv, io, json, random, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, "/h")
from load_t import load
import sweep_lib as S

t = load()


def rd_csv(root, name, delim=","):
    text = (root / name).read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    return rows, list(rows[0].keys()) if rows else text.splitlines()[0].split(delim)


def wr_csv(root, name, rows, fields, delim=","):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n", delimiter=delim)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    (root / name).write_text(buf.getvalue(), encoding="utf-8")


def rd_jl(root, name):
    return [json.loads(x) for x in (root / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def wr_jl(root, name, rows):
    (root / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


M = {}


def mut(f):
    M[f.__name__] = f
    return f


@mut
def corr_epoch_text(root, r):
    rows = rd_jl(root, "grant_corrections.jsonl")
    for x in rows:
        x["recorded_at"] = str(x["recorded_at"])
    wr_jl(root, "grant_corrections.jsonl", rows)


@mut
def member_spaces(root, r):
    for n in ("dir_members_site_a.csv", "dir_members_site_b.csv"):
        rows, f = rd_csv(root, n)
        for x in rows:
            if not x["member"].startswith("group:"):
                x["member"] = "  " + x["member"] + " "
        wr_csv(root, n, rows, f)


@mut
def approver_spaces(root, r):
    rows, f = rd_csv(root, "grant_approvals.csv")
    for x in rows:
        x["approver"] = " " + x["approver"].upper() + "  "
    wr_csv(root, "grant_approvals.csv", rows, f)


@mut
def role_upper(root, r):
    for n in ("role_bindings_dev.csv", "role_bindings_prod.csv"):
        rows, f = rd_csv(root, n)
        for x in rows:
            x["role"] = x["role"].upper()
        wr_csv(root, n, rows, f)


@mut
def legacy_role_upper(root, r):
    cat = json.loads((root / "role_catalog.json").read_text())["roles"]
    for n in ("role_bindings_dev.csv", "role_bindings_prod.csv"):
        rows, f = rd_csv(root, n)
        for x in rows:
            name = x["role"].lower()
            for k, v in cat.items():
                if k.lower() == name and v.get("legacy_names"):
                    x["role"] = v["legacy_names"][0].upper()
        wr_csv(root, n, rows, f)


@mut
def target_legacy(root, r):
    cat = json.loads((root / "role_catalog.json").read_text())["roles"]
    for p in sorted(root.glob("grant_requests_*.jsonl")):
        rows = rd_jl(root, p.name)
        for x in rows:
            tg = x.get("target")
            if isinstance(tg, str) and tg.startswith("role:"):
                v = cat.get(tg[5:])
                if v and v.get("legacy_names"):
                    x["target"] = "role:" + v["legacy_names"][0].title()
        wr_jl(root, p.name, rows)


@mut
def group_cycle(root, r):
    rows, f = rd_csv(root, "dir_members_site_a.csv")
    groups = sorted({x["group_id"] for x in rows})
    base = rows[0]
    add = []
    k = min(6, len(groups))
    for i, g in enumerate(groups[:k]):
        h = groups[(i + 1) % k]
        add.append(dict(base, mid=f"A-9{i:05d}", group_id=g, member=f"group:{h}"))
    wr_csv(root, "dir_members_site_a.csv", rows + add, f)


@mut
def nested_deep(root, r):
    rows, f = rd_csv(root, "dir_members_site_b.csv")
    groups = sorted({x["group_id"] for x in rows})
    base = rows[0]
    add = [dict(base, mid=f"B-9{i:05d}", group_id=groups[i + 1], member=f"group:{groups[i]}") for i in range(min(8, len(groups) - 1))]
    wr_csv(root, "dir_members_site_b.csv", rows + add, f)


@mut
def emp_ref_forms(root, r):
    for n in ("hr_events_2025.csv", "hr_events_2026h1.csv", "hr_events_2026h2.csv"):
        rows, f = rd_csv(root, n)
        for x in rows:
            no = int(x["employee_no"].lstrip("Ee-") or 0)
            x["employee_no"] = r.choice([f"e{no}", f"E-{no:06d}", f"e-{no:06d}", f"{no}"])
        wr_csv(root, n, rows, f)


@mut
def emp_ref_seven(root, r):
    rows, f = rd_csv(root, "hr_events_2025.csv")
    for x in rows[:20]:
        no = int(x["employee_no"].lstrip("Ee-") or 0)
        x["employee_no"] = f"0{no:06d}"
    wr_csv(root, "hr_events_2025.csv", rows, f)


@mut
def ctr_ref_forms(root, r):
    rows, f = rd_csv(root, "contractor_contracts.csv")
    for x in rows:
        cid = int("".join(ch for ch in x["contractor_id"] if ch.isdigit()))
        x["contractor_id"] = r.choice([f"ctr-{cid:04d}", f"C{cid}", f"CTR{cid}", f"c-{cid}"])
    wr_csv(root, "contractor_contracts.csv", rows, f)


@mut
def journal_bool_int(root, r):
    rows = rd_jl(root, "policy_change_journal.jsonl")
    schema = json.loads((root / "config_schema.json").read_text())["keys"]
    rec = rows[0]["recorded_at"]
    eff = rows[0]["effective_at"]
    seq = max(x["seq"] for x in rows) + 1
    add = []
    for k, v in schema.items():
        name = k if v["scope"] == "global" else f"prod.{k}"
        if v["type"] == "int":
            add.append({"seq": seq, "key": name, "value": True, "effective_at": eff, "recorded_at": rec}); seq += 1
            add.append({"seq": seq, "key": name, "value": float(v.get("min", 1)), "effective_at": eff, "recorded_at": rec}); seq += 1
        if v["type"] == "bool":
            add.append({"seq": seq, "key": name, "value": 1, "effective_at": eff, "recorded_at": rec}); seq += 1
            add.append({"seq": seq, "key": name, "value": "true", "effective_at": eff, "recorded_at": rec}); seq += 1
    wr_jl(root, "policy_change_journal.jsonl", rows + add)


@mut
def journal_null_cancel(root, r):
    rows = rd_jl(root, "policy_change_journal.jsonl")
    rec = rows[0]["recorded_at"]
    keys = sorted({x["key"] for x in rows})
    seq = max(x["seq"] for x in rows) + 1
    add = []
    for k in keys:
        add.append({"seq": seq, "key": k, "value": None, "effective_at": rows[0]["effective_at"], "recorded_at": rec}); seq += 1
    wr_jl(root, "policy_change_journal.jsonl", rows + add)


@mut
def journal_tie_seq(root, r):
    rows = rd_jl(root, "policy_change_journal.jsonl")
    rec = rows[0]["recorded_at"]
    eff = rows[0]["effective_at"]
    seq = max(x["seq"] for x in rows) + 10
    add = [{"seq": seq + 5, "key": "dev.max_grant_hours", "value": 7, "effective_at": eff, "recorded_at": rec},
           {"seq": seq, "key": "dev.max_grant_hours", "value": 9, "effective_at": eff, "recorded_at": rec},
           {"seq": seq + 1, "key": "dev.approvals_required", "value": 2, "effective_at": eff, "recorded_at": rec}]
    wr_jl(root, "policy_change_journal.jsonl", add + rows)


@mut
def instant_edge_valid(root, r):
    """valid but unusual instants: +00:00, -00:00 style offsets and leap day."""
    rows, f = rd_csv(root, "grant_approvals.csv")
    for x in rows:
        v = x["decided_at"]
        if v.endswith("Z"):
            x["decided_at"] = v[:-1] + "+00:00"
    wr_csv(root, "grant_approvals.csv", rows, f)


@mut
def instant_edge_bad(root, r):
    rows, f = rd_csv(root, "grant_approvals.csv")
    bad = ["2027-02-29T10:00:00Z", "2027-03-01T24:00:00Z", "2027-03-01T10:60:00Z", "2027-03-01T10:00:60Z",
           "2027-03-01T10:00:00+5:30", "2027-03-01T10:00:00+05:30:00", "2027-3-01T10:00:00Z", "2027-03-01T10:00:00 Z",
           "2027-03-01T10:00:00+24:00", " 2027-03-01T10:00:00Z", "2027-03-01t10:00:00Z", "2027-13-01T10:00:00Z"]
    for i, x in enumerate(rows[60:60 + len(bad) * 3]):
        x["decided_at"] = bad[i % len(bad)]
    wr_csv(root, "grant_approvals.csv", rows, f)


@mut
def date_edge_bad(root, r):
    rows, f = rd_csv(root, "hr_events_2025.csv")
    bad = ["2025-02-29", "2025-2-01", "2025-04-31", " 2025-03-01", "20250301", "2025-03-01 "]
    for i, x in enumerate(rows[55:55 + len(bad) * 2]):
        x["effective_date"] = bad[i % len(bad)]
    wr_csv(root, "hr_events_2025.csv", rows, f)


@mut
def epoch_edge(root, r):
    rows, f = rd_csv(root, "revocations_selfservice.csv")
    for i, x in enumerate(rows[55:70]):
        v = x["recorded_at"]
        x["recorded_at"] = [v + ".0", "+" + v, " " + v, v[:-3] + "e3", "0x10"][i % 5]
    wr_csv(root, "revocations_selfservice.csv", rows, f)


@mut
def alias_is_handle(root, r):
    rows, f = rd_csv(root, "directory_aliases.tsv", "\t")
    acc = rd_jl(root, "idp_accounts_east.jsonl")
    handles = sorted({a["handle"] for a in acc})
    add = [dict(rows[0], alias=handles[i].upper(), handle=handles[i + 1]) for i in range(0, 20, 2)]
    wr_csv(root, "directory_aliases.tsv", rows + add, f, "\t")


@mut
def alias_chain(root, r):
    rows, f = rd_csv(root, "directory_aliases.tsv", "\t")
    add = []
    for i, x in enumerate(rows[:15]):
        add.append(dict(x, alias=f"chain{i}@corp.mail", handle=x["alias"]))
    wr_csv(root, "directory_aliases.tsv", rows + add, f, "\t")
    # point some members at the chained aliases
    m, fm = rd_csv(root, "dir_members_site_c.csv")
    for i, x in enumerate(m[:15]):
        if not x["member"].startswith("group:"):
            x["member"] = f"chain{i}@corp.mail"
    wr_csv(root, "dir_members_site_c.csv", m, fm)


@mut
def alias_case(root, r):
    rows, f = rd_csv(root, "directory_aliases.tsv", "\t")
    for x in rows:
        x["alias"] = x["alias"].upper()
        x["handle"] = " " + x["handle"].title() + " "
    wr_csv(root, "directory_aliases.tsv", rows, f, "\t")


@mut
def approver_contractor(root, r):
    rows, f = rd_csv(root, "grant_approvals.csv")
    acc = rd_jl(root, "idp_accounts_east.jsonl") + rd_jl(root, "idp_accounts_west.jsonl")
    ctr = sorted({a["handle"] for a in acc if a["handle"].startswith("x.")})
    for i, x in enumerate(rows):
        if i % 4 == 0:
            x["approver"] = ctr[i % len(ctr)]
    wr_csv(root, "grant_approvals.csv", rows, f)


@mut
def window_equal(root, r):
    for p in sorted(root.glob("grant_requests_*.jsonl")):
        rows = rd_jl(root, p.name)
        for x in rows[50:58]:
            if x.get("effective_from"):
                x["effective_until"] = x["effective_from"]
        wr_jl(root, p.name, rows)
    rows, f = rd_csv(root, "contractor_contracts.csv")
    for x in rows[50:60]:
        x["end_date"] = x["start_date"]
    wr_csv(root, "contractor_contracts.csv", rows, f)
    for n in ("role_bindings_dev.csv", "role_bindings_prod.csv"):
        rows, f = rd_csv(root, n)
        for x in rows[:4]:
            x["bound_until"] = x["bound_from"]
        wr_csv(root, n, rows, f)


@mut
def dup_rows(root, r):
    for n in ("grant_approvals.csv", "hr_events_2025.csv", "oncall_swaps.csv"):
        rows, f = rd_csv(root, n)
        wr_csv(root, n, rows + rows[50:60], f)
    rows = rd_jl(root, "revocations_secops.jsonl")
    wr_jl(root, "revocations_secops.jsonl", rows + rows[50:60])


@mut
def dup_ticket_identical(root, r):
    shards = sorted(root.glob("grant_requests_*.jsonl"))
    a = rd_jl(root, shards[-1].name)
    b = rd_jl(root, shards[0].name)
    wr_jl(root, shards[0].name, b + a[:40])


@mut
def dup_ticket_differ(root, r):
    shards = sorted(root.glob("grant_requests_*.jsonl"))
    a = rd_jl(root, shards[-1].name)
    b = rd_jl(root, shards[1].name)
    extra = []
    for x in a[:40]:
        y = dict(x)
        y["requester"] = y["requester"].upper()
        extra.append(y)
    wr_jl(root, shards[1].name, b + extra)


@mut
def mfa_comments_blank(root, r):
    lines = (root / "idp_mfa_events.log").read_text().splitlines()
    out = []
    for i, x in enumerate(lines):
        out.append(x)
        if i % 20 == 5:
            out.append("# mid comment " + str(i))
    (root / "idp_mfa_events.log").write_text("\n".join(out) + "\n")


@mut
def mfa_handle_case(root, r):
    lines = (root / "idp_mfa_events.log").read_text().splitlines()
    out = []
    for x in lines:
        if not x.startswith("#") and " handle=" in x:
            a, b = x.split(" handle=", 1)
            h, rest = b.split(" ", 1)
            x = f"{a} handle={h.upper()} {rest}"
        out.append(x)
    (root / "idp_mfa_events.log").write_text("\n".join(out) + "\n")


@mut
def secops_ref_handle(root, r):
    rows = rd_jl(root, "revocations_secops.jsonl")
    for i, x in enumerate(rows):
        s = x["subject"]
        if s and s[0].isdigit():
            x["subject"] = ["e" + s.lstrip("0"), "E-" + s, s.zfill(6)][i % 3]
    wr_jl(root, "revocations_secops.jsonl", rows)


@mut
def secops_scope_unknown(root, r):
    rows = rd_jl(root, "revocations_secops.jsonl")
    for x in rows[50:60]:
        x["scope"] = ["env:qa", "perm:nope.x", "ALL", "Env:dev", "perm:"][rows.index(x) % 5]
    wr_jl(root, "revocations_secops.jsonl", rows)


@mut
def hr_corr_tie(root, r):
    rows, f = rd_csv(root, "hr_corrections.csv")
    add = []
    for i, x in enumerate(rows[:10]):
        y = dict(x)
        y["correction_id"] = x["correction_id"] + "Z" if i % 2 else "HRC-0000" + str(i)
        y["action"] = "redate" if x["action"] == "void" else "void"
        y["new_effective_date"] = "2026-01-15" if y["action"] == "redate" else ""
        add.append(y)
    wr_csv(root, "hr_corrections.csv", rows + add, f)


@mut
def swap_tie(root, r):
    rows, f = rd_csv(root, "oncall_swaps.csv")
    add = []
    for i, x in enumerate(rows[:20]):
        y = dict(x, swap_id=x["swap_id"] + "b", from_holder=x["to_holder"], to_holder=x["from_holder"])
        add.append(y)
    wr_csv(root, "oncall_swaps.csv", add + rows, f)


@mut
def rota_dst_wall(root, r):
    d = json.loads((root / "oncall_rotations.json").read_text())
    for i, x in enumerate(d["rotations"]):
        x["start"] = ["02:30", "03:30", "01:30", "02:00", "03:00"][i % 5]
    (root / "oncall_rotations.json").write_text(json.dumps(d, indent=2))


@mut
def rota_short_shifts(root, r):
    d = json.loads((root / "oncall_rotations.json").read_text())
    for i, x in enumerate(d["rotations"]):
        x["duration_minutes"] = [600, 1500, 2880, 60, 1439][i % 5]
    (root / "oncall_rotations.json").write_text(json.dumps(d, indent=2))


@mut
def tz_no_transitions(root, r):
    d = json.loads((root / "tz_rules.json").read_text())
    for i, (k, v) in enumerate(sorted(d["zones"].items())):
        if i % 2 == 0:
            v["transitions"] = []
        else:
            v["transitions"] = v["transitions"][2:]
    (root / "tz_rules.json").write_text(json.dumps(d, indent=2))


@mut
def role_include_cycle(root, r):
    d = json.loads((root / "role_catalog.json").read_text())
    names = sorted(d["roles"])
    for i in range(0, 8):
        d["roles"][names[i]]["includes"] = sorted(set(d["roles"][names[i]]["includes"]) | {names[(i + 1) % 8]})
    (root / "role_catalog.json").write_text(json.dumps(d, indent=2))


@mut
def ini_variants(root, r):
    txt = (root / "site_policy.ini").read_text()
    txt = txt.replace(" = ", "=").replace("[global]", "; comment\n[global]")
    (root / "site_policy.ini").write_text(txt)


@mut
def cutoff_ms_edge(root, r):
    ini = (root / "site_policy.ini").read_text()
    cut = [l.split("=", 1)[1].strip() for l in ini.splitlines() if l.startswith("recorded_cutoff")][0]
    R = t.stamp(cut)
    rows, f = rd_csv(root, "revocations_selfservice.csv")
    for i, x in enumerate(rows[50:62]):
        x["recorded_at"] = str(R * 1000 + [0, 1, 999, -1][i % 4])
    wr_csv(root, "revocations_selfservice.csv", rows, f)
    c = rd_jl(root, "grant_corrections.jsonl")
    for i, x in enumerate(c[50:58]):
        x["recorded_at"] = R + [0, 1][i % 2]
    wr_jl(root, "grant_corrections.jsonl", c)


@mut
def crlf(root, r):
    for n in ("hr_events_2025.csv", "grant_approvals.csv"):
        p = root / n
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))


@mut
def bom(root, r):
    for n in ("hr_events_2025.csv",):
        p = root / n
        p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes())


@mut
def blank_lines_jsonl(root, r):
    p = root / "grant_requests_2026_05.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n\n".join(lines) + "\n\n")


@mut
def att_upper_perm(root, r):
    pass  # placeholder: attestations derived after mutation; handled by reference


def main():
    prog = Path(sys.argv[1])
    seed, scale, variant = sys.argv[2].split(":")
    seed, scale = int(seed), float(scale)
    names = sys.argv[3:]
    if names == ["all"]:
        names = [k for k in M if k not in ("att_upper_perm", "bom")]
    combo = None
    if names and names[0] == "combo":
        combo, names = names[1:], ["combo"]
        M["combo"] = lambda root, r: [M[c](root, r) for c in combo]
    b0 = Path(tempfile.mkdtemp(prefix="fb-"))
    gb = t.generate(b0, seed, scale, variant)
    t.attest_from_reference(b0, gb, seed)
    base = S.reference(t, b0)
    for name in names:
        root = Path(tempfile.mkdtemp(prefix="fz-"))
        g = t.generate(root, seed, scale, variant)
        rr = random.Random(seed * 31 + 7)
        try:
            M[name](root, rr)
        except Exception as e:
            print(f"## {name} MUTATION-ERROR {e!r}", flush=True)
            continue
        t.attest_from_reference(root, g, seed)
        try:
            exp = S.reference(t, root)
        except Exception as e:
            print(f"## {name} REF-ERROR {e!r}", flush=True)
            got, tp = S.run(prog, root, Path(tempfile.mkdtemp(prefix="fo-")))
            print("    prog:", {k: (v if isinstance(v, tuple) else "ok") for k, v in got.items()})
            continue
        got, tp = S.run(prog, root, Path(tempfile.mkdtemp(prefix="fo-")))
        diffs = [d for d in (S.cmp(t, k, exp[k], got[k]) for k in exp) if d]
        eff = sum(1 for k in exp if k != "summary" and exp[k] != base.get(k))
        print(f"## {name} prog {tp:.1f}s -> {'EXACT' if not diffs else 'DIFF'} refchanged={eff}", flush=True)
        for d in diffs:
            print("   ", d[:700], flush=True)


main()
