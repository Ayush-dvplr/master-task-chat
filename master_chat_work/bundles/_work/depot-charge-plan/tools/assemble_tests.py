"""Assemble BUNDLE/tests/test_output.py from the WORK generator, the proto2 reference and
WORK/tests_src/infra.py, embedding the shipped data folder.  Usage: assemble_tests.py"""
import ast
import base64
import os
import sys
import zlib
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "depot-charge-plan"
DATA = BUNDLE / "environment" / "data"


def segments(path, names, drop_core=False):
    src = path.read_text()
    tree = ast.parse(src)
    lines = src.splitlines()
    out = []
    for node in tree.body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            start = node.lineno - 1
            if getattr(node, "decorator_list", None):
                start = node.decorator_list[0].lineno - 1
            text = "\n".join(lines[start:node.end_lineno])
            if drop_core:
                text = text.replace("core.", "")
            out.append(text)
    return "\n\n\n".join(out)


FAMILIES = [("policy_audit", "policy_audit.json", "the per-bus policy audit"),
            ("region_north", "region_North.json", "the North depot report"),
            ("region_south", "region_South.json", "the South depot report"),
            ("region_west", "region_West.json", "the West depot report"),
            ("region_east", "region_East.json", "the East depot report"),
            ("segment_commercial", "segment_commercial.json", "the commercial class report"),
            ("segment_public", "segment_public.json", "the public class report"),
            ("summary", "summary.json", "the summary")]
CORPUS = {"h1": "first", "h2": "second", "h3": "third", "h4": "fourth (largest)"}


def crit(name, desc, call, weight):
    return ('@criterion(description=%r)\ndef %s(workspace: Path) -> bool:\n    return _holds(%s)\n'
            % (desc, name, call), "criteria.%s(weight=%d)" % (name, weight))


def criteria_text():
    items = [crit("program_and_reports_present",
                  "The delivered /app/out/derive_report.py parses as Python and /app/out holds all nine report files.",
                  "_check_present", 1)]
    for short, doc, label in [("policy_audit", "policy_audit.json", "policy audit"),
                              ("summary", "summary.json", "summary"),
                              ("data_quality", "data_quality.json", "data quality report"),
                              ("segment_public", "segment_public.json", "public class report"),
                              ("region_east", "region_East.json", "East depot report")]:
        items.append(crit("shipped_%s_exact" % short,
                          "The delivered /app/out/%s for the shipped data equals the %s derived from the written rules, as a whole document." % (doc, label),
                          "_check_delivered, %r" % doc, 3))
    for key in ["h1", "h2", "h3", "h4"]:
        for short, doc, label in FAMILIES:
            items.append(crit("fresh_%s_%s_exact" % (key, short),
                              "On the %s fresh data folder, the program's %s equals %s derived from the written rules, as a whole document." % (CORPUS[key], doc, label),
                              "_check_fresh, %r, %r" % (key, doc), 5))
        if key in ("h1", "h3"):
            items.append(crit("fresh_%s_data_quality_exact" % key,
                              "On the %s fresh data folder, the program's data_quality.json equals the data quality report derived from the written rules, as a whole document." % CORPUS[key],
                              "_check_fresh, %r, 'data_quality.json'" % key, 3))
    for i in range(1, 10):
        key = "u%d" % i
        for short, doc, label in FAMILIES:
            items.append(crit("fresh_%s_%s_exact" % (key, short),
                              "On held-out data folder %s, whose disruption notice lists a feeder limit above feeder_kwh_per_slot for some slots, the program's %s equals %s derived from the written rules, as a whole document." % (key, doc, label),
                              "_check_uplift, %r, %r" % (key, doc), 5))
    items.append(crit("reordered_copy_policy_audit_exact",
                      "On a copy of the second fresh data folder with its file rows reordered and the public class weight changed, the program's policy_audit.json equals the one derived from the written rules.",
                      "_check_altered", 3))
    items.append(crit("relocated_fresh_summary_exact",
                      "Run from an unrelated working directory on a further fresh data folder of its own, placed several folders deep and graded by no other check, the program's summary.json equals the one derived from the written rules.",
                      "_check_relocated", 3))
    items.append(crit("default_paths_run_summary_exact",
                      "With a further fresh data folder placed at /app/data and the program started as python3 /app/out/derive_report.py with no flags, the summary.json it writes into /app/out equals the one derived from the written rules.",
                      "_check_default_paths", 3))
    items.append(crit("missing_settlements_stops_naming_file",
                      "On the shipped data without settlements.csv, the program exits non-zero and its error output names settlements.csv.",
                      "_check_missing_input", 3))
    items.append(crit("malformed_tariff_stops_naming_file",
                      "On the shipped data with tariff.xml cut off halfway so it is no longer well formed XML, the program exits non-zero and its error output names tariff.xml.",
                      "_check_malformed_input", 3))
    items.append(crit("negative_outside_library_or_network_import",
                      "The delivered program imports a module outside the Python 3 standard library or a network module.",
                      "_check_outside_library_import", -3))
    items.append(crit("negative_hardcoded_sample_answers",
                      "The delivered program's source carries every bus id that the shipped answers list as short.",
                      "_check_hardcoded_sample_answers", -5))
    items.append(crit("negative_run_writes_outside_output_folder",
                      "In the run started with no flags, the program creates a file outside /app/out, anywhere under /app, /tmp, /var/tmp or /dev/shm.",
                      "_check_wrote_outside_output", -1))
    funcs = "\n\n".join(f for f, _ in items)
    regs = "\n".join(r for _, r in items)
    return funcs + "\n\n" + regs + "\n"


def main():
    gen = segments(WORK / "gen_core.py", {"DEPOTS", "S", "TYPES", "RATE2T", "CAB_KWH", "FLEET_ROWS", "PAD_DAYS",
                                           "price_of", "gen", "bands_rng", "cents", "fits", "conv", "_w", "render",
                                           "uplift"})
    core = segments(WORK / "proto2" / "core.py", {"MCF", "dp", "build", "extract", "tie_pass", "solve_flow"})
    sp = segments(WORK / "proto2" / "solve_proto.py", {"FMT", "load", "write"}, drop_core=True)
    infra = (WORK / "tests_src" / "infra.py").read_text()
    blobs = {}
    for p in sorted(DATA.rglob("*")):
        if p.is_file():
            blobs[p.relative_to(DATA).as_posix()] = base64.b64encode(zlib.compress(p.read_bytes(), 9)).decode()
    emb = ["_SHIPPED_DATA: dict[str, str] = {"]
    for k, v in blobs.items():
        emb.append("    %r: (" % k)
        for i in range(0, len(v), 96):
            emb.append("        %r" % v[i:i + 96])
        emb.append("    ),")
    emb.append("}")
    head, tail = infra.split("# ==== CHECKS ====\n", 1)
    tail = tail.rstrip() + "\n\n\n" + criteria_text()
    text = "\n\n\n".join([
        head.rstrip(),
        "# ---- seeded generator of fresh input sets (verifier only) ----\n\n" + gen,
        "# ---- reference derivation from the written contract ----\n\n" + core,
        sp,
        "\n".join(emb),
        "# ==== CHECKS ====\n" + tail.lstrip(),
    ]) + "\n"
    dst = BUNDLE / "tests" / "test_output.py"
    dst.write_text(text)
    print("wrote", dst, len(text.splitlines()), "lines", len(blobs), "embedded files")


if __name__ == "__main__":
    main()
