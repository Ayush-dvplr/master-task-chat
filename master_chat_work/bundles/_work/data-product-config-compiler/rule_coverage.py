"""G11: one mutant of the repaired tool per contract rule; every row must fail at least one test."""
from __future__ import annotations

import json
import sys

from score import BUNDLE, L1_FULL, L2_FULL, L4_FULL, N1_FULL, N1_ONE, N3_FULL, N3_ONE, N4_FULL, SCRATCH, WORK, score

C = "config_contract.md"
T = "        if retired_owners.get(product[\"owner\"], \"9999-99-99\") <= day:\n"

RULES = [
    ("compile writes the five documents and creates --out", "8-10", "compile never creates --out",
     [("cli.py", "    os.makedirs(out_dir, exist_ok=True)\n    for name in emit.DOCUMENTS:",
       "    for name in emit.DOCUMENTS:")], []),
    ("export-report writes report.json", "11", "report written as report.txt",
     [("cli.py", 'emit.write_document(out_dir, "report.json", report)', 'emit.write_document(out_dir, "report.txt", report)')], []),
    ("D is the manifest compile_date", "12", "delivery compiled for a fixed other date",
     [], [('    day = json.loads((DATA / "release_manifest.json").read_text())["compile_date"]\n', '    day = "2026-01-15"\n')]),
    ("inputs never changed, writes only inside --out, read-only data folder", "13-15",
     "compile drops a cache file beside its data",
     [("cli.py", "    os.makedirs(out_dir, exist_ok=True)\n    for name in emit.DOCUMENTS:",
       "    open(os.path.join(data_dir, '.dpcc_cache'), 'w').close()\n"
       "    os.makedirs(out_dir, exist_ok=True)\n    for name in emit.DOCUMENTS:")], []),
    ("any folder and any data folder name", "14-15", "compile insists on a folder named data",
     [("cli.py", "    missing = loaders.missing_inputs(data_dir)\n",
       "    if os.path.basename(os.path.normpath(data_dir)) != 'data':\n"
       "        raise loaders.InputError(2, 'error: missing input data')\n"
       "    missing = loaders.missing_inputs(data_dir)\n")], []),
    ("an error writes no document", "17-18", "an empty summary.json is written before the checks",
     [("cli.py", "    missing = loaders.missing_inputs(data_dir)\n",
       "    os.makedirs(out_dir, exist_ok=True)\n"
       "    open(os.path.join(out_dir, 'summary.json'), 'w').close()\n"
       "    missing = loaders.missing_inputs(data_dir)\n")], []),
    ("missing input names the first absent file in Inputs order", "20-21", "names the last absent file",
     [("cli.py", "% missing[0])", "% missing[-1])")], []),
    ("invalid date exits 2", "22", "calendar check dropped (pattern only)",
     [("cli.py", "        datetime.date.fromisoformat(text)\n", "        pass\n")], []),
    ("catalog mismatch names the smallest canonical id, exit 3", "23-24", "names the largest id",
     [("cli.py", "% difference[0])", "% difference[-1])")], []),
    ("product ids compared upper case without hyphens", "28-29", "deprecation.log ids used raw",
     L4_FULL, []),
    ("output documents write the canonical id", "28-29", "override ids kept as written",
     [("loaders.py", '        record["product"] = canon(record["product"])\n', "")], []),
    ("assignment: the row with the latest active_from", "38-39", "first row covering D in file order", N1_FULL, []),
    ("active owner: the assignment itself covers D", "40-42", "latest row among those covering D", N1_ONE, []),
    ("text integer: only the digits 0 to 9", "89", "any int() text read as an integer", N4_FULL, []),
    ("text boolean: only true or false", "89-90", "any other word read as false",
     [("loaders.py", '        if text not in ("true", "false"):\n            raise ValueError(value)\n', "")], []),
    ("text not of the key's type is passed over, earlier value kept", "91-92", "unreadable text kept as written",
     [("loaders.py", "    except ValueError:\n        return PASSED\n", "    except ValueError:\n        return _unquote(raw)\n")], []),
    ("quota_cap: excess given back and handed out again among products under their cap", "140-143",
     "remaining quota re-shared from scratch each round", N3_FULL, []),
    ("quota_cap: each cap applies again after the round, repeat until nothing is given back", "143-144",
     "at most two rounds", N3_ONE, []),
    ("quota_cap: units no product can take are not handed out", "144", "untakeable units go to the smallest id",
     [("quota.py", "    return held\n", "    if pool and held:\n        held[min(held)] += pool\n    return held\n")], []),
    ("event dated by the first ten characters", "33-34", "event dated by year and month",
     [("loaders.py", '            when = parts[0][:10]\n            pid = canon(fields["product"])\n',
       '            when = parts[0][:7]\n            pid = canon(fields["product"])\n')], []),
    ("active owner: no RETIRE owner event on or before D", "40-42", "owner retirement events ignored",
     L1_FULL, []),
    ("assignment: rows with active_from on or before D", "38-39", "active_from must be strictly before D",
     [("resolve.py", 'row["active_from"] <= day:', 'row["active_from"] < day:')], []),
    ("status retired only for a RETIRE product event on or before D", "43-44", "any RETIRE product event retires",
     [("resolve.py", "        if pid in retired and retired[pid] <= day:\n", "        if pid in retired:\n")], []),
    ("team is null for orphaned products", "45", "orphaned products keep their last CSV team",
     [("resolve.py", '            status[pid], team[pid] = "orphaned", None\n',
       '            status[pid], team[pid] = "orphaned", by_owner.get(product["owner"], [{"team": None}])[-1]["team"]\n')], []),
    ("compiled products are active and orphaned", "46", "only active products are compiled",
     [("cli.py", '    compiled = {pid for pid in products if status[pid] != "retired"}\n',
       '    compiled = {pid for pid in products if status[pid] == "active"}\n')], []),
    ("owners.csv empty active_to is open", "63-64", "empty active_to read as closed",
     [("resolve.py", 'latest["active_to"] != "" and ', 'latest["active_to"] == "" or ')], []),
    ("deprecation.log is not in time order (earliest event counts)", "66-68", "last event in the file counts",
     [("loaders.py", "            if pid not in retired or when < retired[pid]:\n", "            if True:\n")], []),
    ("selectors apply in file order, later wins", "69-71", "selectors applied in reverse file order",
     [("resolve.py", "    for rule in rules:\n", "    for rule in reversed(rules):\n")], []),
    ("team overrides apply to products whose team is the name", "72-73", "team overrides never applied",
     [("resolve.py", "        merge(settings, team_layer.get(team_name, []))\n", "        pass\n")], []),
    ("product override values keep their JSON type", "74-77", "JSON values converted like text",
     L2_FULL, []),
    ("env files only feed the profiles", "78-80", "config.json also takes env_dev.toml",
     [("cli.py", "resolve.resolve(pid, products[pid], team[pid], base, rules, team_layer, product_layer)\n",
       "resolve.resolve(pid, products[pid], team[pid], base, rules, team_layer, product_layer,\n"
       "                                        loaders.load_env(data_dir, 'dev', schema))\n")], []),
    ("text layers: one pair of double quotes stripped", "87-88", "quotes kept",
     [("loaders.py", "        return raw[1:-1]\n", "        return raw\n")], []),
    ("text layers: boolean true or false in any case", "89-90", "boolean read case sensitive",
     [("loaders.py", "        text = str(value).strip().lower()\n", "        text = str(value).strip()\n")], []),
    ("text layers: list comma separated, empty text is the empty list", "90-91", "empty text gives one empty item",
     [("loaders.py", '        return [] if text == "" else [item.strip() for item in text.split(",")]\n',
       '        return [item.strip() for item in text.split(",")]\n')], []),
    ("JSON layers keep their type, never converted", "97-99", "JSON values converted like text",
     L2_FULL, []),
    ("integer bounds", "98-99", "integer bounds unchecked",
     [("resolve.py", '    if spec["type"] == "integer" and not spec["min"] <= value <= spec["max"]:\n        return "bounds", None\n', "")], []),
    ("enum values", "98-99", "enum values unchecked",
     [("resolve.py", '    if spec["type"] == "enum" and value not in spec["values"]:\n        return "bounds", None\n', "")], []),
    ("unknown_product for a product that is not compiled", "106-107", "overrides of retired products accepted",
     [("cli.py", "loaders.load_product_overrides(data_dir), compiled)", "loaders.load_product_overrides(data_dir), set(products))")], []),
    ("unknown_key", "108", "unknown key reported as type",
     [("resolve.py", '        return "unknown_key", None\n', '        return "type", None\n')], []),
    ("type: null for a key that is not optional", "77, 109", "null deletes any key",
     [("resolve.py", '            return None, None\n        return "type", None\n', '            return None, None\n        return None, None\n')], []),
    ("bounds reason", "110", "out of bounds reported as type",
     [("resolve.py", '    if spec["type"] == "integer" and not spec["min"] <= value <= spec["max"]:\n        return "bounds", None\n',
       '    if spec["type"] == "integer" and not spec["min"] <= value <= spec["max"]:\n        return "type", None\n')], []),
    ("precedence: team overrides below products.ini settings", "114-121", "team overrides above products.ini",
     [("resolve.py", "        merge(settings, team_layer.get(team_name, []))\n    merge(settings, product[\"lines\"])\n",
       "        pass\n    merge(settings, product[\"lines\"])\n    if team_name is not None:\n"
       "        merge(settings, team_layer.get(team_name, []))\n")], []),
    ("product overrides in ascending seq", "122", "product overrides in file order",
     [("resolve.py", '    for record in sorted(product_records, key=lambda entry: entry["seq"]):\n',
       "    for record in product_records:\n")], []),
    ("profiles: env defaults then tier section after base", "124-125", "tier section before defaults",
     [("resolve.py", '        merge(settings, env_sections.get("defaults", []))\n        merge(settings, env_sections.get("tier." + product["tier"], []))\n',
       '        merge(settings, env_sections.get("tier." + product["tier"], []))\n        merge(settings, env_sections.get("defaults", []))\n')], []),
    ("merging: null removes, empty list replaces, unmentioned keeps", "129-130", "empty list skipped",
     [("resolve.py", "        else:\n            settings[key] = value\n", "        elif value != []:\n            settings[key] = value\n")], []),
    ("quota: rounded down, leftovers by largest dropped fraction", "134-138", "each share rounded to nearest",
     [("quota.py", "    units = {pid: quota * weight // total for pid, weight in weights.items()}\n",
       "    units = {pid: round(quota * weight / total) for pid, weight in weights.items()}\n    return units\n")], []),
    ("quota: ties by product id ascending", "136-138", "ties by product id descending",
     [("quota.py", "(-(quota * weights[pid] % total), pid))", "(-(quota * weights[pid] % total), [-ord(c) for c in pid]))")], []),
    ("quota: denominator over active products, orphaned get 0", "135, 144-145", "orphaned products share the quota",
     [("cli.py", '(quotas["shared"], {pid: settings[pid]["weight"] for pid in active},', '(quotas["shared"], {pid: settings[pid]["weight"] for pid in sorted(compiled)},')], []),
    ("documents: two-space indent, sorted keys, final newline", "149-150", "keys in insertion order",
     [("emit.py", "json.dumps(document, indent=2, sort_keys=True)", "json.dumps(document, indent=2)")], []),
    ("config.json: settings null for retired products", "154-156", "retired products get empty settings",
     [("emit.py", '"settings": settings.get(pid),', '"settings": settings.get(pid, {}),')], []),
    ("profiles: cluster_quota is the env quota", "160-162", "profiles carry the shared quota",
     [("cli.py", "emit.profile_document(env, manifest, day, quotas[env], active,", 'emit.profile_document(env, manifest, day, quotas["shared"], active,')], []),
    ("validation_report: product rows by ascending seq", "166-169", "product rows by descending seq",
     [("resolve.py", '    rejected_products.sort(key=lambda entry: entry["seq"])\n', '    rejected_products.sort(key=lambda entry: -entry["seq"])\n')], []),
    ("validation_report: team rows by team then key", "166-169", "team rows by team descending",
     [("resolve.py", "    for team_name in sorted(team_overrides):\n", "    for team_name in sorted(team_overrides, reverse=True):\n")], []),
    ("summary.json counts and quota totals", "173-176", "config quota total counts products",
     [("cli.py", '    totals = {"config": sum(shares.values())}\n', '    totals = {"config": len(shares)}\n')], []),
    ("report.json sha256 of each document", "180-182", "sha1 digests",
     [("emit.py", "hashlib.sha256(handle.read())", "hashlib.sha1(handle.read())")], []),
]


def main() -> int:
    contract = (BUNDLE / "environment" / "data" / C).read_text().splitlines()
    rows, bad = [], 0
    for index, (rule, lines, mutant, edits, solve_edits) in enumerate(RULES):
        for part in lines.split(", "):
            first, _, last = part.partition("-")
            assert 1 <= int(first) <= int(last or first) <= len(contract), lines
        result = score("rule%02d" % index, edits, solve_edits)
        failed = result["failed"]
        bad += not failed
        rows.append({"rule": rule, "where": "%s:%s" % (C, lines), "mutant": mutant, "failed": failed,
                     "pct": result["pct"]})
        print("%2d %-60s %3d failed  %s" % (index, rule[:60], len(failed), ",".join(failed)[:150]), flush=True)
    out = ["# RULE_COVERAGE", "",
           "Each mutant is one wrong edit on the repaired tool (or, for the compile date, on the delivery step); "
           "the tests are run as in the verifier. Every row fails at least one test.", "",
           "| rule | file:line | mutant | tests failed |", "|---|---|---|---|"]
    for row in rows:
        out.append("| %s | %s | %s | %d (%s) |" % (row["rule"], row["where"], row["mutant"], len(row["failed"]),
                                                 ", ".join(row["failed"])))
    out += ["", "Rows with no failing test: %d" % bad, "", "## Lessons for the master", "",
            "rule coverage needs one mutant per contract sentence, written against the repaired tool | no change: the prompt already asks for it"]
    (WORK / "RULE_COVERAGE.md").write_text("\n".join(out) + "\n")
    (WORK / "rule_coverage.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("uncovered", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
