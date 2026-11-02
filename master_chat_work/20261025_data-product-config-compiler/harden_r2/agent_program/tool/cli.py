"""dpcc: compile the data product configuration release.

Usage:
    python3 cli.py compile --data <folder> --date <YYYY-MM-DD> --out <folder>
    python3 cli.py export-report --out <folder>
"""

import argparse
import datetime
import os
import re
import sys

import emit
import loaders
import quota
import resolve


def check_date(text):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise loaders.InputError(2, "error: invalid date %s" % text)
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise loaders.InputError(2, "error: invalid date %s" % text) from None
    return text


def check_catalog(manifest, products):
    catalog = {loaders.canon(pid) for pid in manifest["catalog"]}
    difference = sorted(catalog.symmetric_difference(products))
    if difference:
        raise loaders.InputError(3, "error: catalog mismatch %s" % difference[0])


def _caps(settings, pids):
    return {pid: settings[pid]["quota_cap"] for pid in pids if "quota_cap" in settings[pid]}


def compile_release(data_dir, date, out_dir):
    """Compile every document for date and write them into out_dir."""
    missing = loaders.missing_inputs(data_dir)
    if missing:
        raise loaders.InputError(2, "error: missing input %s" % missing[0])
    day = check_date(date)
    manifest = loaders.load_manifest(data_dir)
    schema = loaders.load_schema(data_dir)
    products = loaders.load_products(data_dir, schema)
    check_catalog(manifest, products)

    base = loaders.load_base(data_dir, schema)
    owners = loaders.load_owners(data_dir)
    retired_products, retired_owners = loaders.load_deprecations(data_dir)
    rules = loaders.load_rules(data_dir, schema)
    quotas = loaders.load_quota(data_dir)

    status, team = resolve.classify(products, owners, retired_products, retired_owners, day)
    compiled = {pid for pid in products if status[pid] != "retired"}
    active = sorted(pid for pid in products if status[pid] == "active")
    rejected, team_layer, product_layer = resolve.screen_overrides(
        schema, loaders.load_team_overrides(data_dir), loaders.load_product_overrides(data_dir), compiled)

    settings = {}
    for pid in sorted(compiled):
        settings[pid] = resolve.resolve(pid, products[pid], team[pid], base, rules, team_layer, product_layer)
    weights = {pid: settings[pid]["weight"] for pid in active}
    shares = quota.split_quota(quotas["shared"], weights, _caps(settings, active))
    documents = {"config.json": emit.config_document(manifest, day, quotas["shared"], products, status, team,
                                                     settings, shares)}
    totals = {"config": sum(shares.values())}
    for env in ("dev", "prod"):
        sections = loaders.load_env(data_dir, env, schema)
        env_settings = {pid: resolve.resolve(pid, products[pid], team[pid], base, rules, team_layer, product_layer,
                                             sections) for pid in active}
        env_weights = {pid: env_settings[pid]["weight"] for pid in active}
        env_shares = quota.split_quota(quotas[env], env_weights, _caps(env_settings, active))
        totals[env] = sum(env_shares.values())
        documents["profile_%s.json" % env] = emit.profile_document(env, manifest, day, quotas[env], active,
                                                                   env_settings, env_shares)
    documents["validation_report.json"] = {"release": manifest["release"], "rejected_overrides": rejected}
    documents["summary.json"] = emit.summary_document(manifest, day, status, team, rejected, totals)

    os.makedirs(out_dir, exist_ok=True)
    for name in emit.DOCUMENTS:
        emit.write_document(out_dir, name, documents[name])


def export_report(out_dir):
    report = emit.report_document(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    emit.write_document(out_dir, "report.json", report)
    return 0 if report["ok"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dpcc")
    commands = parser.add_subparsers(dest="command", required=True)
    compile_cmd = commands.add_parser("compile")
    compile_cmd.add_argument("--data", required=True)
    compile_cmd.add_argument("--date", required=True)
    compile_cmd.add_argument("--out", required=True)
    report_cmd = commands.add_parser("export-report")
    report_cmd.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            compile_release(args.data, date=args.date, out_dir=args.out)
            return 0
        return export_report(args.out)
    except loaders.InputError as error:
        print(error.message, file=sys.stderr)
        return error.code


if __name__ == "__main__":
    sys.exit(main())
