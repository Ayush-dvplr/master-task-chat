"""Plant the NL-1..NL-3 cases into generated corpora and measure oracle-vs-reflex differences (scratch)."""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from proto_ref import ref_compute_p  # noqa: E402
from gen_core import gen_corpus, gen_rescaled, gen_shuffled  # noqa: E402  (WORK is on sys.path via proto_ref)
from ref_core import ref_compute, ref_dump  # noqa: E402

AGENT = os.path.join(os.path.dirname(HERE), "agent_program", "src", "cli.py")
INT = ("weight", "retention_days", "replicas", "partitions", "freshness_sla_min")
OTHER = ("pii_scan", "alerts_enabled", "encryption", "notify", "tags", "cost_center")
VARIANTS = {
    "NL-1": [("assign", "any_first"), ("assign", "any_last"), ("assign", "latest_covering")],
    "NL-2": [("budget", "off"), ("budget", "nullgroup"), ("budget", "consume")],
    "NL-3": [("cap", "restart"), ("cap", "single"), ("cap", "off")],
    "NL-4": [("textmode", "lenient"), ("textmode", "isdigit"), ("textmode", "sign")],
}
FULL = str.maketrans("0123456789", "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19")


def odd_text(rng, kind, raw):
    if kind == "integer":
        n = raw.strip().strip('"')
        return rng.choice(["+" + n, n.translate(FULL), n.translate(FULL)])
    return rng.choice(["yes", "no", "on", "1", "0", "off"])


def _day(s):
    return dt.date.fromisoformat(s)


def plant(files, seed):
    rng = random.Random(seed * 7 + 3)
    files = dict(files)
    man = json.loads(files["release_manifest.json"])
    day = man["compile_date"]
    rows = files["owners.csv"].decode().splitlines()
    head, body = rows[0], rows[1:]
    cfg = ref_compute(files)["config.json"]["products"]
    owners = sorted({p["owner"] for p in cfg.values() if p["status"] == "active"})
    teams = sorted({p["team"] for p in cfg.values() if p["team"]})
    rng.shuffle(owners)
    d = _day(day)
    # NL-1: 8 owners get a later-started covering row (other team), 6 a later-started row that ended before D
    for i, owner in enumerate(owners[:14]):
        mine = [r for r in body if r.split(",")[0] == owner]
        cover = [r for r in mine if r.split(",")[2] <= day and (r.split(",")[3] == "" or r.split(",")[3] >= day)]
        if not cover:
            continue
        old = cover[0].split(",")
        start = _day(old[2])
        gap = (d - start).days
        if gap < 4:
            continue
        new_from = start + dt.timedelta(days=rng.randint(1, gap - 2))
        other = rng.choice([t for t in teams if t != old[1]])
        if i < 8:
            new_to = "" if rng.random() < 0.6 else str(d + dt.timedelta(days=rng.randint(1, 400)))
        else:
            new_to = str(new_from + dt.timedelta(days=rng.randint(0, max(0, (d - new_from).days - 1))))
            if new_to >= day:
                continue
        line = f"{owner},{other},{new_from},{new_to}"
        at = body.index(cover[0])
        body.insert(at + 1 if i % 2 else at, line)
    files["owners.csv"] = ("\n".join([head] + body) + "\n").encode()
    # NL-3: quota_cap key, per-product caps on ~6% of active products, a gold cap in env_dev
    sch = json.loads(files["schema_registry.json"])
    sch["keys"]["quota_cap"] = {"type": "integer", "min": 1, "max": 100000, "optional": True}
    files["schema_registry.json"] = (json.dumps(sch, indent=2) + "\n").encode()
    base = ref_compute_p(files, budget="off", cap="off")
    act = [p for p, v in base["config.json"]["products"].items() if v["status"] == "active"]
    lines = files["product_overrides.jsonl"].decode().splitlines()
    seq = max(json.loads(x)["seq"] for x in lines if x.strip()) + 1
    picked = rng.sample(act, max(6, len(act) * 10 // 100))
    for j, pid in enumerate(picked):
        share = base["config.json"]["products"][pid]["quota"]
        # 60% bind on the first pass, 40% sit just above their first share and bind only after a re-share
        capv = max(1, int(share * rng.uniform(0.4, 0.97))) if j % 5 < 3 else share + rng.randint(1, 3)
        lines.insert(rng.randrange(len(lines) + 1), json.dumps({"seq": seq, "product": pid, "key": "quota_cap", "value": capv}))
        seq += 1
    files["product_overrides.jsonl"] = ("\n".join(lines) + "\n").encode()
    dev = base["profile_dev.json"]["products"]
    gold = [v["quota"] for p, v in dev.items() if cfg.get(p, {}).get("tier") == "gold"]
    if gold:
        gcap = max(1, int(sorted(gold)[len(gold) // 2] * 0.85))
        txt = files["env_dev.toml"].decode().replace("[tier.gold]", f"[tier.gold]\nquota_cap = {gcap}", 1)
        files["env_dev.toml"] = txt.encode()
    # NL-2: change_budget = median accepted product-override count per team
    out = ref_compute_p(files, budget="off")
    prods = out["config.json"]["products"]
    rej = {r["seq"] for r in out["validation_report.json"]["rejected_overrides"] if r["source"] == "product_overrides"}
    count = {}
    for x in files["product_overrides.jsonl"].decode().splitlines():
        if x.strip():
            o = json.loads(x)
            pid = o["product"].upper().replace("-", "")
            if o["seq"] not in rej and prods[pid]["team"]:
                count[prods[pid]["team"]] = count.get(prods[pid]["team"], 0) + 1
    vals = sorted(count.values())
    man["change_budget"] = vals[len(vals) // 2]
    files["release_manifest.json"] = (json.dumps(man, indent=2) + "\n").encode()
    # NL-4: about 8% of integer/boolean setting lines in products.ini and 2 weight rules get a value outside the stated shape
    kinds = {k: v["type"] for k, v in sch["keys"].items()}
    out_lines = []
    for ln in files["products.ini"].decode().splitlines():
        k, eq, raw = ln.partition("=")
        if eq and kinds.get(k.strip()) in ("integer", "boolean") and rng.random() < 0.08:
            ln = f"{k.strip()} = {odd_text(rng, kinds[k.strip()], raw)}"
        out_lines.append(ln)
    files["products.ini"] = ("\n".join(out_lines) + "\n").encode()
    rl = files["selectors.rules"].decode().splitlines()
    wi = [i for i, x in enumerate(rl) if " set weight " in x]
    for i in rng.sample(wi, min(2, len(wi))):
        head_, _, n = rl[i].rpartition(" ")
        rl[i] = head_ + " " + odd_text(rng, "integer", n)
    files["selectors.rules"] = ("\n".join(rl) + "\n").encode()
    return files


def fams(out, kind):
    c = out["config.json"]
    P = c["products"]
    if kind == "status":
        return {p: (v["status"], v["team"]) for p, v in P.items()}
    if kind == "quota":
        return [c["cluster_quota"], {p: v["quota"] for p, v in P.items()}] + [
            {p: v["quota"] for p, v in out[f"profile_{e}.json"]["products"].items()} for e in ("dev", "prod")]
    if kind == "int":
        return {p: v["settings"] and [v["settings"].get(k) for k in INT] for p, v in P.items()}
    res = {
        "catalog_status": {p: (v["status"], v["owner"], v["tier"]) for p, v in P.items()},
        "team": {p: v["team"] for p, v in P.items()},
        "settings_int": {p: v["settings"] and [v["settings"].get(k) for k in INT] for p, v in P.items()},
        "settings_other": {p: v["settings"] and [v["settings"].get(k) for k in OTHER] for p, v in P.items()},
        "config_quota": [c["cluster_quota"], {p: v["quota"] for p, v in P.items()}],
        "rejected_overrides": out["validation_report.json"],
        "summary": out["summary.json"],
        "readonly": c,
    }
    for e in ("dev", "prod"):
        pr = out[f"profile_{e}.json"]["products"]
        res[f"{e}_deploy"] = {p: (v["alerts_enabled"], v["pii_scan"], v["replicas"]) for p, v in pr.items()}
        res[f"{e}_quota"] = {p: v["quota"] for p, v in pr.items()}
    return res


W = {k: 5 for k in ("catalog_status", "team", "settings_int", "settings_other", "config_quota", "dev_deploy",
                    "dev_quota", "prod_deploy", "prod_quota", "rejected_overrides", "summary")}
W.update(readonly=3, shuffled=5, rescale=5, date_shift=5)


def lost(run, files, seed, shifted):
    """Points of the hidden-tier rows a program `run(files, date)` loses against the planted oracle."""
    got, want = run(files, None), ref_compute_p(files)
    f1, f2 = fams(got, "all"), fams(want, "all")
    bad = [k for k in f1 if f1[k] != f2[k]]
    resc, shuf = gen_rescaled(files, seed + 1), gen_shuffled(files, seed + 2)
    if fams(run(resc, None), "quota") != fams(ref_compute_p(resc), "quota"):
        bad.append("rescale")
    if fams(run(shuf, None), "int") != fams(ref_compute_p(shuf), "int"):
        bad.append("shuffled")
    if fams(run(files, shifted), "status") != fams(ref_compute_p(files, date=shifted), "status"):
        bad.append("date_shift")
    return bad, sum(W[k] for k in bad)


def agent_run(files, date):
    with tempfile.TemporaryDirectory() as tmp:
        data, outd = os.path.join(tmp, "data"), os.path.join(tmp, "out")
        os.makedirs(data)
        for n, b in files.items():
            with open(os.path.join(data, n), "wb") as fh:
                fh.write(b)
        day = date or json.loads(files["release_manifest.json"])["compile_date"]
        subprocess.run([sys.executable, "-B", AGENT, "compile", "--data", data, "--date", day, "--out", outd],
                       check=True, capture_output=True, cwd=tmp)
        return {n: json.load(open(os.path.join(outd, n))) for n in
                ("config.json", "profile_dev.json", "profile_prod.json", "validation_report.json", "summary.json")}


def main():
    n_corp, n_agent = int(sys.argv[1]), int(sys.argv[2])
    res = {f"{lv}:{k}={v}": [] for lv, vs in VARIANTS.items() for k, v in vs}
    res["probe_agent"] = []
    for i in range(n_corp):
        seed = 50000 + i
        rng = random.Random(seed)
        day = "%04d-%02d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12), rng.randint(1, 28))
        files = plant(gen_corpus(seed, rng.randint(420, 520), True, day, f"{day[:7]}-r5", ref_compute), seed)
        shifted = str(_day(day) + dt.timedelta(days=45))
        for lv, vs in VARIANTS.items():
            for k, v in vs:
                bad, pts = lost(lambda f, d, k=k, v=v: ref_compute_p(f, date=d, **{k: v}), files, seed, shifted)
                res[f"{lv}:{k}={v}"].append((pts, bad))
        if i < n_agent:
            bad, pts = lost(agent_run, files, seed, shifted)
            res["probe_agent"].append((pts, bad))
        if i == 0:
            os.makedirs(os.path.join(HERE, "corpus0"), exist_ok=True)
            for n, b in files.items():
                open(os.path.join(HERE, "corpus0", n), "wb").write(b)
    summary = {}
    for key, rows in res.items():
        pts = [p for p, _ in rows]
        summary[key] = {"n": len(rows), "differing_share": round(sum(p > 0 for p in pts) / max(1, len(rows)), 3),
                        "mean_lost_pts": round(sum(pts) / max(1, len(rows)), 1),
                        "min_lost_pts": min(pts) if pts else None,
                        "mean_lost_pct_of_125": round(100 * sum(pts) / max(1, len(rows)) / 125, 1),
                        "rows_example": rows[0][1] if rows else None}
    json.dump(summary, open(os.path.join(HERE, "proto_result.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
