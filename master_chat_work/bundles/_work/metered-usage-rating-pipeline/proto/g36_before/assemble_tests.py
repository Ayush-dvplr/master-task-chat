"""Assemble BUNDLE/tests/test_output.py from tests_template.py, ref_core.py, gen_core.py and the shipped data."""
import base64
import sys
import zlib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "metered-usage-rating-pipeline"
DATA = BUNDLE / "environment" / "data"
HIDDEN_SEED = 58213
INPUTS = (
    "collector_central.csv", "collector_east.tsv", "collector_north.jsonl",
    "collector_south.txt", "collector_west.log", "accounts.csv",
    "plan_changes.log", "rate_card.json", "commitments.xml", "products.ini",
    "collector_controls.json",
)
REGIONS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")

TIER_TEXT = {
    "visible": "on the delivered /app/out documents for the shipped month",
    "hard": "on a fresh month from another seed and scale, run by the delivered program as another user from a renamed input folder and a foreign working directory",
}


def families():
    """(name, description stem, check function, extra args) for every row-owned family."""
    out = [("accepted_lines", "normalized.jsonl lists exactly the accepted lines in rating order with record_id, region, timestamp, account_id, product and units equal to the contract",
            "_check_accepted_lines", ())]
    for r in REGIONS:
        out.append(("rating_" + r, "every %s line in normalized.jsonl carries the segment, tier, unit_rate and charge the contract gives it" % r,
                    "_check_rating", (r,)))
    for r in REGIONS:
        out.append(("credit_" + r, "every %s line in normalized.jsonl carries the plan and credit the contract gives it" % r,
                    "_check_credit", (r,)))
    for r in REGIONS:
        out.append(("true_up_" + r, "every %s line in normalized.jsonl carries the true_up the contract gives it" % r,
                    "_check_true_up", (r,)))
    for r in REGIONS:
        out.append(("region_" + r, "region_%s.json equals the contract document for that region, every key" % r,
                    "_check_document", ("region_%s.json" % r,)))
    for s in SEGMENTS:
        out.append(("segment_" + s, "segment_%s.json equals the contract document for that segment, every key" % s,
                    "_check_document", ("segment_%s.json" % s,)))
    out.append(("product_summary", "product_summary.json equals the contract document, every product and key",
                "_check_document", ("product_summary.json",)))
    out.append(("summary", "summary.json equals the contract document, every key", "_check_document", ("summary.json",)))
    out.append(("data_quality", "data_quality.json equals the contract document: collector counts, reasons, quarantined records and plan change counts",
                "_check_document", ("data_quality.json",)))
    return out


def criteria_block():
    lines = []
    regs = []
    for name, stem, fn, args in families():
        for tier, suffix, weight in (("visible", "", 3), ("hard", "_hard", 5)):
            full = name + suffix
            call = ", ".join([repr(tier)] + [repr(a) for a in args])
            desc = "%s, %s." % (stem[0].upper() + stem[1:], TIER_TEXT[tier])
            lines += ["", "", "@criterion(description=%r)" % desc,
                      "def %s(workspace: Path) -> bool:" % full,
                      "    return _holds(%s, %s)" % (fn, call)]
            regs.append("criteria.%s(weight=%d)" % (full, weight))
    extra = [
        ("mutation_tier_scale", 5, "_check_tier_scale",
         "On the fresh month with every non-zero tier threshold raised by 3.75 percent (rounded up) and collector rows shuffled, product_summary.json equals the contract document."),
        ("mutation_small_commitment", 3, "_check_small_commitment",
         "On the fresh month with one region's pool set to 1.00 and its minimum set 1.00 above its credit base, that region's region document equals the contract document."),
        ("mutation_near_base_pool", 5, "_check_near_base_pool",
         "On the fresh month with one region's pool set 0.01 below its credit base, that region's region document equals the contract document."),
        ("missing_collector", 3, "_check_missing_collector",
         "The program completes the fresh month, and with one collector file removed it exits non-zero with 'missing input: <file name>' on stderr."),
        ("control_mismatch", 3, "_check_control_mismatch",
         "The program completes the fresh month, and with one record removed from a collector file it exits non-zero with 'control mismatch: <file name>' on stderr."),
        ("determinism", 3, "_check_determinism",
         "Two runs of the program on the same fresh month write byte-identical, non-empty output documents."),
        ("transform_exists", 1, "_check_program_exists", "/app/out/transform.py exists and is not empty."),
        ("negative_hardcoded_sample_answers", -5, "_check_restates_shipped",
         "Fires when the program, run on a fresh month, writes the shipped month's month, charge, credit or net into summary.json."),
    ]
    for name, weight, fn, desc in extra:
        lines += ["", "", "@criterion(description=%r)" % desc,
                  "def %s(workspace: Path) -> bool:" % name,
                  "    return _holds(%s)" % fn]
        regs.append("criteria.%s(weight=%d)" % (name, weight))
    for k in (1, 2, 3):
        long_checks = [
            ("long_%d_finishes" % k, 3, "_check_long_finishes", (k,),
             "On long fresh month %d, the program exits 0 within 15 seconds and writes every output document." % k),
            ("long_%d_normalized" % k, 5, "_check_long_document", (k, "normalized.jsonl"),
             "On long fresh month %d, normalized.jsonl equals the contract document." % k),
            ("long_%d_summary" % k, 5, "_check_long_document", (k, "summary.json"),
             "On long fresh month %d, summary.json equals the contract document." % k),
            ("long_%d_product_summary" % k, 3, "_check_long_document", (k, "product_summary.json"),
             "On long fresh month %d, product_summary.json equals the contract document." % k),
        ]
        for name, weight, fn, args, desc in long_checks:
            lines += ["", "", "@criterion(description=%r)" % desc,
                      "def %s(workspace: Path) -> bool:" % name,
                      "    return _holds(%s, %s)" % (fn, ", ".join(repr(a) for a in args))]
            regs.append("criteria.%s(weight=%d)" % (name, weight))
    return "\n".join(lines + ["", ""] + regs) + "\n"


def strip_core(path):
    text = path.read_text(encoding="utf-8")
    return "\n".join(l for l in text.splitlines() if not l.startswith("from __future__")).rstrip() + "\n"


def main():
    template = (WORK / "tests_template.py").read_text(encoding="utf-8")
    blobs = []
    for name in INPUTS:
        raw = (DATA / name).read_bytes()
        blobs.append('    "%s": "%s",' % (name, base64.b64encode(zlib.compress(raw, 9)).decode("ascii")))
    text = (template.replace("@@HIDDEN_SEED@@", str(HIDDEN_SEED))
            .replace("# @@REF_CORE@@", strip_core(WORK / "ref_core.py"))
            .replace("# @@GEN_CORE@@", strip_core(WORK / "gen_core.py"))
            .replace("# @@SHIPPED_DATA@@", "\n".join(blobs))
            .replace("# @@CRITERIA@@", criteria_block()))
    assert "@@" not in text
    target = BUNDLE / "tests" / "test_output.py"
    target.write_text(text, encoding="utf-8")
    print("wrote", target, len(text.splitlines()), "lines")


if __name__ == "__main__":
    sys.exit(main())
