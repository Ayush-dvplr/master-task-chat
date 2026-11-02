"""Build BUNDLE/tests/test_output.py from tests_template.py, the two cores and the shipped data."""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "data-product-config-compiler"
DATA = BUNDLE / "environment" / "data"
TARGET = BUNDLE / "tests" / "test_output.py"
HIDDEN_SEED = 318907
INPUTS = (
    "release_manifest.json", "schema_registry.json", "base_layer.yaml", "products.ini", "owners.csv",
    "deprecation.log", "selectors.rules", "team_overrides.json", "product_overrides.jsonl",
    "env_dev.toml", "env_prod.toml", "cluster_quota.json",
)

TIER_TEXT = {
    "visible": "on the delivered /app/out documents for the shipped release",
    "hard": "on a fresh release from another seed and scale, compiled by the delivered tool.zip as another user "
            "from a renamed input folder and a foreign working directory",
}

FAMILIES = (
    ("status_team", "Every catalog product in config.json has the contract status, owner, tier and team on the compile date", "_check_status_team", ()),
    ("settings_int", "Every compiled product in config.json has the contract weight, retention_days, replicas, partitions and freshness_sla_min", "_check_settings_int", ()),
    ("settings_other", "Every compiled product in config.json has the contract pii_scan, alerts_enabled, encryption, notify, tags and cost_center", "_check_settings_other", ()),
    ("config_quota", "config.json carries the contract header and the contract quota for every catalog product", "_check_quota", ("config.json",)),
    ("dev_deploy", "profile_dev.json lists every active product with the contract alerts_enabled, pii_scan and replicas", "_check_deploy", ("profile_dev.json",)),
    ("dev_quota", "profile_dev.json carries the contract header and the contract quota for every active product", "_check_quota", ("profile_dev.json",)),
    ("prod_deploy", "profile_prod.json lists every active product with the contract alerts_enabled, pii_scan and replicas", "_check_deploy", ("profile_prod.json",)),
    ("prod_quota", "profile_prod.json carries the contract header and the contract quota for every active product", "_check_quota", ("profile_prod.json",)),
    ("rejected_overrides", "validation_report.json lists exactly the contract rejected overrides, in contract order and with contract reasons", "_check_document", ("validation_report.json",)),
    ("summary", "summary.json equals the contract summary of the release", "_check_document", ("summary.json",)),
)

EXTRA = (
    ("report_run", 1, "_check_report", "The delivered /app/out/report.json reports ok, names the tool and gives the sha256 of each of the five delivered documents for the shipped release"),
    ("date_shift", 5, "_check_date_shift", "Compiling a fresh release for a compile date 45 days later with the delivered tool.zip gives the contract status and team for every catalog product"),
    ("quota_rescale", 5, "_check_quota_rescale", "Compiling a fresh release with rescaled cluster quotas with the delivered tool.zip gives the contract quota for every product in config.json and both profiles"),
    ("shuffled_relocated", 5, "_check_shuffled", "Compiling a fresh release whose product_overrides.jsonl and owners.csv rows are shuffled, from a renamed folder, gives the contract integer settings for every compiled product"),
    ("missing_input", 1, "_check_missing_input", "With two inputs removed the delivered tool.zip exits 2 with the contract missing-input line for the first missing input and writes no document"),
    ("invalid_date", 1, "_check_invalid_date", "Given an impossible --date the delivered tool.zip exits 2 with the contract invalid-date line and writes no document"),
    ("catalog_mismatch", 1, "_check_catalog_mismatch", "With one product dropped from the manifest catalog the delivered tool.zip exits 3 with the contract catalog-mismatch line naming it and writes no document"),
    ("determinism", 1, "_check_determinism", "Compiling the same fresh release twice with the delivered tool.zip gives byte-identical documents"),
    ("config_quota_capped", 5, "_check_quota, 'capped', 'config.json'", "Compiling a fresh release in which many products carry a quota_cap with the delivered tool.zip gives the contract quota for every catalog product in config.json"),
    ("dev_quota_capped", 5, "_check_quota, 'capped', 'profile_dev.json'", "Compiling a fresh release in which many products carry a quota_cap with the delivered tool.zip gives the contract quota for every active product in profile_dev.json"),
    ("prod_quota_capped", 5, "_check_quota, 'capped', 'profile_prod.json'", "Compiling a fresh release in which many products carry a quota_cap with the delivered tool.zip gives the contract quota for every active product in profile_prod.json"),
    ("readonly_inputs", 3, "_check_read_only", "Compiling a fresh release from a read-only renamed input folder as another user gives the contract config.json"),
    ("document_format", 1, "_check_format", "Every document the delivered tool.zip writes for a fresh release is JSON with two-space indent, sorted keys and one trailing newline"),
    ("tool_zip_layout", 1, "_check_layout", "The delivered /app/out/tool.zip holds cli.py at its root"),
    ("negative_hardcoded_sample_answers", -5, "_check_restates_shipped", "The delivered tool.zip writes the shipped release name into config.json for a fresh release with another name"),
)


def criteria_block() -> str:
    out, regs = [], []
    for name, stem, fn, args in FAMILIES:
        for tier, suffix, weight in (("visible", "", 3), ("hard", "_hard", 5)):
            extra = "".join(", %r" % arg for arg in args)
            out.append("@criterion(description=%r)\ndef %s%s(workspace: Path) -> bool:\n    return _holds(%s, %r%s)\n\n"
                       % ("%s, %s." % (stem, TIER_TEXT[tier]), name, suffix, fn, tier, extra))
            regs.append("criteria.%s%s(weight=%d)" % (name, suffix, weight))
    for name, weight, fn, desc in EXTRA:
        out.append("@criterion(description=%r)\ndef %s(workspace: Path) -> bool:\n    return _holds(%s)\n\n" % (desc + ".", name, fn))
        regs.append("criteria.%s(weight=%d)" % (name, weight))
    return "\n".join(out) + "\n" + "\n".join(regs) + "\n"


def strip_core(path: Path) -> str:
    return "".join(line for line in path.read_text().splitlines(True) if not line.startswith("from __future__"))


def main() -> None:
    text = (WORK / "tests_template.py").read_text()
    blobs = "".join("    %r: %r,\n" % (name, base64.b64encode(zlib.compress((DATA / name).read_bytes(), 9)).decode())
                    for name in INPUTS)
    text = text.replace("@@HIDDEN_SEED@@", str(HIDDEN_SEED))
    text = text.replace("# @@REF_CORE@@\n", strip_core(WORK / "ref_core.py"))
    text = text.replace("# @@GEN_CORE@@\n", strip_core(WORK / "gen_core.py"))
    text = text.replace("# @@SHIPPED_DATA@@\n", blobs)
    text = text.replace("# @@CRITERIA@@\n", criteria_block())
    assert "@@" not in text
    TARGET.write_text(text)
    print("wrote", TARGET, len(text.splitlines()), "lines")


if __name__ == "__main__":
    main()
