"""G11 rule coverage: one mutant of solve.py per contract rule, scored with the real tests.

Usage: python3 -B rule_coverage.py   (writes RULE_COVERAGE.md and rule_coverage.json next to this file)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from cost_table import BUNDLE, FULL, RUNALL, SOLVE, TESTS, patch

WORK = Path(__file__).resolve().parent
SCRATCH = Path("/tmp/mu-p2/rules")
C = "rating_contract.md"

RULES = [
    ("collector name is the line's region", "9-10", "region written as the collector file stem",
     [('"region": ln["region"],', '"region": "collector_" + ln["region"],')]),
    ("header line is not a record", "11-12", "header counted as a record against the control",
     [("if len(records) != month.controls[region]:",
       "if len(records) + (region in ('central', 'east')) != month.controls[region]:")]),
    ("accepted line excludes duplicates", "13-14", "duplicates counted as accepted",
     [('"accepted": tally["accepted"]}', '"accepted": tally["accepted"] + tally["duplicates"]}')]),
    ("month window in UTC, end exclusive", "15-17", "window widened by one day on each side",
     [("self.end = (self.start + dt.timedelta(days=32)).replace(day=1)",
       "self.end = (self.start + dt.timedelta(days=32)).replace(day=1) + dt.timedelta(days=1)\n"
       "        self.start = self.start - dt.timedelta(days=1)")]),
    ("rating order ties broken by record_id", "18-19", "rating order by timestamp only",
     [('lines.sort(key=lambda ln: (ln["when"], ln["record_id"]))', 'lines.sort(key=lambda ln: ln["when"])')]),
    ("plan and segment in force at the line's timestamp", "20-21", "state at the end of the month for every line",
     [('state = month.state_at(ln["account_id"], ln["when"])',
       'state = month.state_at(ln["account_id"], month.end)')]),
    ("credit base = lines of committed accounts of accounts.csv (LV-MU-3, noise)", "22-23, 30-31",
     "base, credit and true-up by the plan in force at the line", FULL["LV-MU-3"]),
    ("credit pool is the region's own pool", "32-33", "pools rotated one region along",
     [('self.pools = {p.get("region").strip(): Decimal(p.get("amount").strip()) for p in tree.iter("pool")}',
       'self.pools = {p.get("region").strip(): Decimal(p.get("amount").strip()) for p in tree.iter("pool")}\n'
       '        self.pools = dict(zip(REGIONS, [self.pools[r] for r in REGIONS[1:] + REGIONS[:1]]))')]),
    ("minimum is the region's pool minimum", "34-35, 114-116", "minimums read as zero",
     [('Decimal(p.get("minimum").strip()) for p in tree.iter("pool")}', 'Decimal(0) for p in tree.iter("pool")}')]),
    ("output directory created when absent", "43-46", "no mkdir of the output directory",
     [("args.output.mkdir(parents=True, exist_ok=True)", "pass")]),
    ("independent of the start directory", "45-46", "output written relative to the working directory",
     [("args = parser.parse_args(argv)", "args = parser.parse_args(argv)\n    args.output = pathlib.Path(args.output.name)")]),
    ("same input gives the same output", "46-47", "quarantined list in random order",
     [('quarantined.sort(key=lambda q: (q["collector"], q["record_id"]))',
       'import random\n    random.shuffle(quarantined)')]),
    ("standard library only", "47-48", "imports a third-party module",
     [("import argparse\n", "import argparse\nimport pandas\n")]),
    ("missing input exits non-zero naming the file", "55-57", "no presence check (traceback instead)",
     [("""        for name in REQUIRED:
            if not (folder / name).is_file():
                raise InputError(f"missing input: {name}")
""", "")]),
    ("collector_south.txt is Latin-1", "61", "south read as UTF-8",
     [('encoding = "latin-1" if region == "south" else "utf-8"', 'encoding = "utf-8"')]),
    ("surrounding spaces trimmed from every text field", "61-62", "central product name not trimmed",
     [("r[2].strip(), r[3].strip(), text_units(r[4]))", "r[2].strip(), r[3], text_units(r[4]))")]),
    ("central timestamp is UTC", "66-68", "central timestamp read as +05:30 local time",
     [('utc(r[1], "%Y-%m-%d %H:%M:%S")', 'utc(r[1], "%Y-%m-%d %H:%M:%S") - dt.timedelta(hours=5, minutes=30)')]),
    ("east epoch seconds", "69-71", "epoch read one hour late",
     [("int(epoch.strip())", "int(epoch.strip()) + 3600")]),
    ("north units JSON integer only (LV-MU-1, noise)", "72-74", "north units cleaned like text", FULL["LV-MU-1"]),
    ("south fixed width columns", "75-77", "account read from characters 24-33",
     [("line[24:34].strip()", "line[23:33].strip()")]),
    ("west timestamp converted to UTC", "78-81", "west wall-clock time taken as UTC",
     [("dt.datetime.fromisoformat(stamp).astimezone(UTC)", "dt.datetime.fromisoformat(stamp).replace(tzinfo=UTC)")]),
    ("text units are ASCII digits only", "83-85", "text units accept whole-valued decimals and signs",
     [("""    raw = raw.strip()
    if raw and all("0" <= ch <= "9" for ch in raw):
        return int(raw)
    return None""", """    try:
        value = float(raw.strip())
    except ValueError:
        return None
    return int(value) if value == int(value) else None""")]),
    ("account ids upper-cased with hyphens removed (LV-MU-4, noise)", "92-93", "plan_changes ids only trimmed",
     [('acct = canonical(fields.pop("account"))', 'acct = fields.pop("account").strip()')]),
    ("accounts.csv gives the start plan", "97-99", "every account starts committed",
     [('"plan": row["plan"].strip()}', '"plan": "committed"}')]),
    ("unmatched plan_changes lines ignored", "101-104", "unmatched lines counted as applied",
     [("""            if acct not in self.start_state:
                continue""", """            if acct not in self.start_state:
                self.change_applied += 1
                continue""")]),
    ("product names matched on the collector's own key only", "105-109", "any collector's name accepted",
     [("                self.alias[region][parser[section][region].strip()] = code",
       "                for other in REGIONS:\n"
       "                    self.alias[other][parser[section][region].strip()] = code")]),
    ("unit comes from products.ini", "105-107", "unit written as the lower-case code",
     [('{"unit": month.unit[code],', '{"unit": code.lower(),')]),
    ("tier number from rate_card.json", "110-113", "tier numbered from 0 by position",
     [("[(int(t[\"tier\"]), {s: Decimal(v) for s, v in t[\"rates\"].items()})\n                                 for t in ladder]",
       "[(i, {s: Decimal(v) for s, v in t[\"rates\"].items()})\n                                 for i, t in enumerate(ladder)]")]),
    ("credit pool amount from commitments.xml", "114-116", "pools read as zero",
     [('Decimal(p.get("amount").strip()) for p in tree.iter("pool")}', 'Decimal(0) for p in tree.iter("pool")}')]),
    ("control mismatch exits non-zero naming the file", "117-121", "control check removed",
     [("""        if len(records) != month.controls[region]:
            raise InputError(f"control mismatch: {name}")
""", "")]),
    ("duplicates dropped before any other check", "125-128", "no duplicate removal",
     [("""            if rid in seen:
                tally["duplicates"] += 1
                continue
""", "")]),
    ("check order gives the quarantine reason", "130-137", "units checked before the account",
     [("""            elif acct not in month.start_state:
                reason = "unknown_account"
            elif product not in month.alias[region]:
                reason = "unknown_product"
            elif units is None:
                reason = "units_not_integer\"""", """            elif units is None:
                reason = "units_not_integer"
            elif acct not in month.start_state:
                reason = "unknown_account"
            elif product not in month.alias[region]:
                reason = "unknown_product\"""")]),
    ("change effective at its own timestamp, inclusive", "144-147", "change effective only after its timestamp",
     [("            if stamp > when:", "            if stamp >= when:")]),
    ("fields a change does not name keep their value", "146-147", "unnamed fields reset to accounts.csv",
     [("            state.update(update)", "            state = {**self.start_state[acct], **update}")]),
    ("same-timestamp changes in file order", "148-149", "same-timestamp changes in reverse file order",
     [("            entries.sort(key=lambda e: e[0])", "            entries.reverse()\n            entries.sort(key=lambda e: e[0])")]),
    ("tier counter counts earlier lines in all collectors", "27-29, 153-154", "tier counted per collector",
     [('key = (month.group[ln["account_id"]], ln["product"])', 'key = (month.group[ln["account_id"]], ln["product"], ln["region"])')]),
    ("tier counter shared by the billing group", "24-29", "tier counter per account",
     [('key = (month.group[ln["account_id"]], ln["product"])', 'key = (ln["account_id"], ln["product"])')]),
    ("billing group follows the parent column to its end (LV-MU-5)", "24-26, 96-99",
     "billing group read one level up", FULL["LV-MU-5"]),
    ("parent column read in canonical id form", "24-26, 92-93", "parent only trimmed",
     [('parent[acct] = canonical(row["parent"] or "")', 'parent[acct] = (row["parent"] or "").strip()'),
      ("            while node not in self.group and parent[node]:",
       "            while node not in self.group and parent.get(node):")]),
    ("tier from earlier lines only, whole line one tier", "27-29, 153-155", "tier from units including the line itself",
     [('tier_no, rates = month.tier_for(ln["product"], used[key])',
       'tier_no, rates = month.tier_for(ln["product"], used[key] + ln["units"])')]),
    ("unit rate for the segment in force", "155-156", "unit rate for the start segment",
     [("rate=rates[state[\"segment\"]])", "rate=rates[month.start_state[ln[\"account_id\"]][\"segment\"]])")]),
    ("charge exact, half-even at 0.01 (LV-MU-2, noise)", "158-160", "half-up rounding",
     [("rounding=ROUND_HALF_EVEN)", "rounding=\"ROUND_HALF_UP\")")]),
    ("totals are sums of rounded line charges", "160-161", "charge totals rounded from exact sums",
     [('ln["charge"] = to_cents(ln["rate"] * ln["units"])',
       'ln["exact"] = ln["rate"] * ln["units"]\n        ln["charge"] = to_cents(ln["exact"])'),
      ('return {"charge": money(sum((ln["charge"] for ln in lines), ZERO)),',
       'return {"charge": money(to_cents(sum((ln["exact"] for ln in lines), ZERO))),')]),
    ("base at or below the pool: each counted line gets its own charge", "167-169",
     "pool shared in proportion even when it covers the base",
     [("        if base[region] <= pool:", "        if False:")]),
    ("credit and true-up shares exact, rounded half-even", "172-177, 185-188", "shares truncated to the cent",
     [('    first = [(ln, to_cents(total * ln["charge"] / denom)) for ln in part]',
       '    first = [(ln, (total * ln["charge"] / denom).quantize(CENT, rounding="ROUND_DOWN")) for ln in part]'),
      ('        ln[field] = to_cents(total * ln["charge"] / kept)',
       '        ln[field] = (total * ln["charge"] / kept).quantize(CENT, rounding="ROUND_DOWN")')]),
    ("shares below 0.50 receive 0.00", "174-175, 186", "no 0.50 floor (one proportional pass)",
     [('FLOOR = Decimal("0.50")', 'FLOOR = Decimal("0.00")')]),
    ("every cent of the pool shared again over the lines that held 0.50 (LV-MU-6)", "174-176",
     "second pass gives held lines their own charge when their summed charge fits the pool", FULL["LV-MU-6"]),
    ("no line holds 0.50: every share 0.00", "177-178, 188-189", "first-pass shares kept when none holds 0.50",
     [("""    for ln in held:
        ln[field] = to_cents(total * ln["charge"] / kept)""", """    for ln in held:
        ln[field] = to_cents(total * ln["charge"] / kept)
    if not held:
        for ln, share in first:
            ln[field] = share""")]),
    ("true-up only when the credit base is below the minimum", "182-183", "true-up of the gap whenever a minimum exists",
     [("        if base[region] < minimum:", "        if minimum > 0:"),
      ('share_with_floor(minimum - base[region], counted[region], base[region], "true_up")',
       'share_with_floor(abs(minimum - base[region]), counted[region], base[region], "true_up")')]),
    ("shortfall = minimum minus credit base", "183-184", "whole minimum shared as true-up",
     [('share_with_floor(minimum - base[region], counted[region], base[region], "true_up")',
       'share_with_floor(minimum, counted[region], base[region], "true_up")')]),
    ("every cent of the shortfall shared again over the lines that held 0.50 (LV-MU-7)", "185-187",
     "second pass shares the shortfall recomputed from the lines still standing", FULL["LV-MU-7"]),
    ("true-up only on lines counted in the credit base", "183-184, 188-189",
     "true-up shared over every line of the region",
     [('share_with_floor(minimum - base[region], counted[region], base[region], "true_up")',
       'share_with_floor(minimum - base[region], [x for x in lines if x["region"] == region], '
       'sum((x["charge"] for x in lines if x["region"] == region), ZERO), "true_up")')]),
    ("net = charge minus credit plus true-up", "192", "net without the true-up",
     [('ln["net"] = ln["charge"] - ln["credit"] + ln["true_up"]', 'ln["net"] = ln["charge"] - ln["credit"]')]),
    ("credit totals are sums of line credits", "192-193, 216", "credit applied reported as the pool",
     [('"credit_base": money(base[region]), "credit_applied": money(applied),',
       '"credit_base": money(base[region]), "credit_applied": money(month.pools[region]),')]),
    ("money values are two-decimal strings", "197-198", "money written as JSON numbers",
     [('    return f"{value:.2f}"', '    return float(f"{value:.2f}")')]),
    ("unit rates are four-decimal strings", "198-199", "unit rate written as a JSON number",
     [("\"unit_rate\": f\"{ln['rate']:.4f}\"", "\"unit_rate\": float(ln['rate'])")]),
    ("timestamps end in Z", "199-200", "timestamp written with +00:00",
     [('"timestamp": ln["when"].strftime("%Y-%m-%dT%H:%M:%SZ")', '"timestamp": ln["when"].isoformat()')]),
    ("normalized.jsonl in rating order", "204-207", "lines written in collector order",
     [("""    with open(args.output / "normalized.jsonl", "w", encoding="utf-8") as handle:
        for ln in lines:""", """    with open(args.output / "normalized.jsonl", "w", encoding="utf-8") as handle:
        for ln in sorted(lines, key=lambda x: (REGIONS.index(x["region"]), x["record_id"])):""")]),
    ("summary accounts_billed is distinct accounts", "208-210", "accounts_billed counts lines",
     [('"accounts_billed": len({ln["account_id"] for ln in lines}),', '"accounts_billed": len(lines),')]),
    ("product_summary lines per product", "211-213", "product lines counts distinct accounts",
     [('products[code] = {"unit": month.unit[code], "lines": len(part),',
       'products[code] = {"unit": month.unit[code], "lines": len({ln["account_id"] for ln in part}),')]),
    ("credit_unallocated = pool minus applied", "214-218", "credit_unallocated sign flipped",
     [('"credit_unallocated": money(month.pools[region] - applied)', '"credit_unallocated": money(applied - month.pools[region])')]),
    ("region minimum written from commitments.xml", "218", "region minimum written as the credit pool",
     [('"minimum": money(month.minimums[region])', '"minimum": money(month.pools[region])')]),
    ("segment documents use the segment in force", "219-222", "segment documents use the start segment",
     [('part = [ln for ln in lines if ln["segment"] == segment]',
       'part = [ln for ln in lines if month.start_state[ln["account_id"]]["segment"] == segment]')]),
    ("data_quality plan_changes counts", "223-229", "plan_changes lines counts matched lines only",
     [('"plan_changes": {"lines": month.change_lines,', '"plan_changes": {"lines": month.change_applied,')]),
    ("every run finishes within 20 seconds", "48-49", "billing group found by walking the parent column again for every account",
     FULL["LV-MU-8"]),
]


def score(label, source):
    app = SCRATCH / label
    if app.exists():
        shutil.rmtree(app)
    (app / "out").mkdir(parents=True)
    shutil.copytree(BUNDLE / "environment" / "data", app / "data")
    (app / "out" / "transform.py").write_text(source, encoding="utf-8")
    subprocess.run([sys.executable, "-B", str(app / "out" / "transform.py"), "--input", str(app / "data"),
                    "--output", str(app / "out")], capture_output=True, cwd=str(app / "out"))
    proc = subprocess.run([sys.executable, "-B", RUNALL, str(TESTS)], capture_output=True, text=True,
                          env={"APP_ROOT": str(app), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"},
                          cwd="/tmp", check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def weights():
    text = TESTS.read_text(encoding="utf-8")
    out = {}
    for line in text.splitlines():
        if line.startswith("criteria.") and "(weight=" in line:
            name = line[len("criteria."):line.index("(")]
            out[name] = float(line.split("weight=")[1].rstrip(")"))
    return out


def main():
    only = sys.argv[1:]
    w = weights()
    rows, results = [], {}
    for i, (rule, lines, mutant, edits) in enumerate(RULES, 1):
        label = "r%02d" % i
        if only and label not in only:
            continue
        res = score(label, patch(SOLVE, edits))
        failed = res["failed"]
        pts = sum(w[n] for n in failed)
        results[label] = {"rule": rule, "failed": failed, "pts": pts}
        cell = "%d (%g pts): %s" % (len(failed), pts, ", ".join(failed)) if failed else "0"
        rows.append("| %s | %s:%s | %s | %s |" % (rule, C, lines, mutant, cell))
        print(label, len(failed), pts, rule, flush=True)
    if only:
        return
    zero = [r for r in results.values() if not r["failed"]]
    head = ["# RULE_COVERAGE (G11) metered-usage-rating-pipeline", "",
            "One mutant of solution/solve.py per rule of environment/data/rating_contract.md, each dropping that "
            "rule alone, scored with the real tests/test_output.py (WORK/rule_coverage.py).", "",
            "| rule | file:line | mutant | tests failed |", "|---|---|---|---|"]
    tail = ["", "Rules uncovered: %d of %d." % (len(zero), len(results)), "",
            "Data guarantees (contract lines 84-85: well formed timestamps, units 1..999) are not program rules; the "
            "embedded generator asserts them on every hidden month (G12)."]
    (WORK / "RULE_COVERAGE.md").write_text("\n".join(head + rows + tail) + "\n", encoding="utf-8")
    (WORK / "rule_coverage.json").write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
