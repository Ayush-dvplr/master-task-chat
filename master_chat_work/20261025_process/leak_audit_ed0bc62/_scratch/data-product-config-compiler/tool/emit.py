"""Building and writing the output documents."""

import hashlib
import json
import os

DOCUMENTS = ("config.json", "profile_dev.json", "profile_prod.json", "validation_report.json", "summary.json")


def write_document(out_dir, name, document):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, indent=2) + "\n")
    return path


def config_document(manifest, day, quota, products, status, team, settings, shares):
    entries = {}
    for pid in sorted(products):
        entries[pid] = {
            "status": status[pid],
            "owner": products[pid]["owner"],
            "tier": products[pid]["tier"],
            "team": team[pid],
            "settings": settings.get(pid),
            "quota": shares.get(pid, 0),
        }
    return {"release": manifest["release"], "compile_date": day, "cluster_quota": quota, "products": entries}


def profile_document(env, manifest, day, quota, active, env_settings, shares):
    entries = {}
    for pid in active:
        resolved = env_settings[pid]
        entries[pid] = {
            "alerts_enabled": resolved["alerts_enabled"],
            "pii_scan": resolved["pii_scan"],
            "replicas": resolved["replicas"],
            "quota": shares[pid],
        }
    return {"env": env, "release": manifest["release"], "compile_date": day, "cluster_quota": quota,
            "products": entries}


def summary_document(manifest, day, status, team, rejected, totals):
    counts = {"active": 0, "orphaned": 0, "retired": 0}
    by_team = {}
    for pid, value in status.items():
        counts[value] += 1
        if value == "active":
            by_team[team[pid]] = by_team.get(team[pid], 0) + 1
    sources = {"team_overrides": 0, "product_overrides": 0}
    for entry in rejected:
        sources[entry["source"]] += 1
    return {"release": manifest["release"], "compile_date": day, "status_counts": counts,
            "active_by_team": by_team, "rejected_overrides": sources, "quota_total": totals}


def report_document(out_dir):
    digests = {}
    for name in DOCUMENTS:
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                digests[name] = hashlib.sha256(handle.read()).hexdigest()
        else:
            digests[name] = None
    return {"tool": "dpcc", "documents": digests, "ok": all(value is not None for value in digests.values())}
