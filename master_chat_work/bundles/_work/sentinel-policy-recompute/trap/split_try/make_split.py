"""Build a split-shipped-check variant of the BUNDLE tests (G03-1/G03-3 trial) for trap measurement only.

Usage: make_split.py <out_file> <w_config> <w_profiles> <w_validation> <w_report> <w_summary> <w_toolzip>
"""
import re, sys
from pathlib import Path
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute")
src = (BUNDLE / "tests/test_output.py").read_text()
start = src.index("def test_shipped_artifacts_follow_field_specs():")
end = src.index("def test_negative_weight_hardcoded_sample_answers():")
NEW_TESTS = '''def assert_shipped_json(path: Path) -> Any:
    assert path.is_file() and path.stat().st_size > 0, f"missing or empty {path}"
    assert path.stat().st_size < MAX_MEMBER_BYTES, f"oversized {path}"
    assert_canonical(path.read_bytes(), path.name)
    document = load_json(path)
    found = [key for key in json_keys(document) if key in FORBIDDEN_KEYS]
    assert not found, f"{path.name} carries dynamic keys {found}"
    return document


def test_shipped_config_matches_policy_and_rebuild():
    """POSITIVE: the shipped config.json equals the authoritative configuration and its bytes equal the init and set rebuild."""
    assert_document(assert_shipped_json(CONFIG_PATH), expected_config(), "config.json")
    assert rebuild_config("shipped").read_bytes() == CONFIG_PATH.read_bytes(), "config.json bytes differ from the init and set rebuild"


def test_shipped_profiles_match_policy():
    """POSITIVE: both shipped profiles equal the authoritative profile documents."""
    shipped = reference_documents("shipped")
    for name, path in (("dev", PROFILE_DEV_PATH), ("prod", PROFILE_PROD_PATH)):
        assert_document(assert_shipped_json(path), expected_profile(name, shipped["policy_resolved.json"]), path.name)


def test_shipped_validation_report_follows_field_spec():
    """POSITIVE: the shipped validation_report.json carries true checks and the authoritative resolved documents."""
    shipped = reference_documents("shipped")
    validation = assert_shipped_json(VALIDATION_REPORT_PATH)
    checks = validation["checks"]
    assert validation["ok"] is True and checks["all_artifacts_present"] is True, "validation_report.json is not ok"
    assert checks["config_matches_policy"] is True and checks["config_scalar_flat"] is True, "validation_report.json checks are not true"
    assert checks["command_failures"] == [] and checks["required_artifacts"] == ARTIFACT_NAMES, "validation_report.json artifact checks differ"
    assert set(checks["profiles"]) == {"dev", "prod"}, "validation_report.json profiles differ"
    assert_document(validation["policy_resolved"], shipped["policy_resolved.json"], "validation_report.json policy_resolved")
    assert_document(validation["threshold_curve"], shipped["threshold_curve.json"], "validation_report.json threshold_curve")
    trace = validation["dependency_trace"]
    assert_document({key: trace.get(key) for key in TRACE_GRADED_KEYS}, shipped["dependency_trace.json"], "validation_report.json dependency_trace")
    rejected = json.dumps(trace.get("rejected_branches"))
    for name in ("B9", "legacy_override_table.ini", "superseded_windows.xml"):
        assert name in rejected, f"rejected_branches does not name {name}"


def test_shipped_report_records_transcript():
    """POSITIVE: the shipped report.json records the successful command transcript, the config digest and the trailer."""
    report = assert_shipped_json(REPORT_PATH)
    assert report.get("ok") is True and report.get("tool") == "sentinel-ctl", "report.json ok or tool is wrong"
    commands = report.get("commands")
    assert isinstance(commands, list) and commands, "report.json has no commands"
    seen = "\\n".join(" ".join(str(arg) for arg in item.get("argv", [])) for item in commands)
    for subcommand in ("resolve", "init", "set", "validate"):
        assert subcommand in seen, f"report.json commands lack a {subcommand} run"
    assert all(item.get("returncode") == 0 for item in commands), "report.json lists a failed command"
    assert report.get("config_sha256") == hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(), "report.json digest does not match config.json"
    assert report.get("trailer") == TRAILER, "report.json trailer is wrong"


def test_shipped_summary_lists_inputs_and_artifacts():
    """POSITIVE: the shipped summary.json lists the inputs, profiles and artifacts as its field spec says."""
    summary = assert_shipped_json(SUMMARY_PATH)
    assert summary["artifact_count"] == len(ARTIFACT_NAMES) and summary["artifacts"] == ARTIFACT_NAMES, "summary.json artifacts differ"
    assert summary["profiles"] == ["dev", "prod"] and summary["format_tag"] == FORMAT_TAG and summary["trailer"] == TRAILER, "summary.json fields differ"
    assert summary["inputs"] == sorted(summary["inputs"]) and summary["input_count"] == len(summary["inputs"]) >= 50, "summary.json inputs differ"


def test_shipped_tool_zip_layout_is_deterministic():
    """POSITIVE: the shipped tool.zip keeps the source member layout with pinned dates and modes and a repaired cli.py."""
    assert TOOL_ARCHIVE.is_file() and TOOL_ARCHIVE.stat().st_size < MAX_MEMBER_BYTES, "tool.zip is missing or oversized"
    with zipfile.ZipFile(TOOL_ARCHIVE) as zf:
        infos = zf.infolist()
        assert [info.filename for info in infos] == ["README.md", "cli.py", "schema.json"], "tool.zip member layout differs from the shipped archive"
        for info in infos:
            assert info.date_time == (1980, 1, 1, 0, 0, 0), f"tool.zip member {info.filename} has an unpinned timestamp"
            assert (info.external_attr >> 16) & 0o777 == 0o644, f"tool.zip member {info.filename} mode is not 0644"
        assert hashlib.sha256(zf.read("cli.py")).hexdigest() != SHIPPED_CLI_SHA256, "cli.py is the unrepaired shipped source"


'''
NAMES = ["shipped_config_matches_policy_and_rebuild", "shipped_profiles_match_policy", "shipped_validation_report_follows_field_spec",
         "shipped_report_records_transcript", "shipped_summary_lists_inputs_and_artifacts", "shipped_tool_zip_layout_is_deterministic"]
src = src[:start] + NEW_TESTS + src[end:]
wrap_old = re.search(r'@criterion\(description="[^"]*"\)\ndef shipped_artifacts_follow_field_specs\(workspace: Path\) -> bool:\n    return _passes\("shipped_artifacts_follow_field_specs", test_shipped_artifacts_follow_field_specs\)\n', src).group(0)
wraps = "\n\n".join(f'@criterion(description="split shipped check {n}.")\ndef {n}(workspace: Path) -> bool:\n    return _passes("{n}", test_{n})\n' for n in NAMES)
src = src.replace(wrap_old, wraps)
weights = [int(x) for x in sys.argv[2:8]]
src = src.replace("criteria.shipped_artifacts_follow_field_specs(weight=1)\n", "".join(f"criteria.{n}(weight={w})\n" for n, w in zip(NAMES, weights)))
Path(sys.argv[1]).write_text(src)
print("written", sys.argv[1], dict(zip(NAMES, weights)))
