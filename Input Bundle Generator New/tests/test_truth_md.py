"""Contract tests for the TRUTH.md golden-trajectory artifact (FORMAT_SPEC.md §15).

Every generated bundle must carry a solution/TRUTH.md that documents the
derivation answering instruction.md. These tests cover three things:

1. Every archetype ships a TRUTH.md template and renders it cleanly.
2. The rendered document's factual claims agree with the bundle it describes.
3. The validator actually rejects a TRUTH.md that has been broken.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generate_bundle.py"
VALIDATOR = ROOT / "validate_bundle.py"
TEMPLATES = ROOT / "templates"

TRUTH_SECTIONS = (
    "## Defect",
    "## Load-bearing work",
    "## Verification",
    "## Root cause",
    "## Solution shape",
    "## Ordered plan",
    "## Pitfalls",
    "## Provenance",
)

# Mirrors validate_bundle.RESIDUAL_MARKER_RE.
RESIDUAL_MARKER_RE = re.compile(
    r"\{\{[A-Z0-9_]+\}\}|__[A-Z][A-Z0-9_]*__|<TAG>"
    r"|\bTODO\b|\bFIXME\b|\bXXX\b|\bPLACEHOLDER\b"
)
PROVENANCE_RE = re.compile(r"^```yaml\n(.*?)^```$", re.M | re.S)

REQUIRED_PROVENANCE_KEYS = (
    "uuid",
    "instance_id",
    "task_name",
    "fix_patch_sha256",
    "solve_py_sha256",
    "language",
)


def archetypes() -> list[str]:
    return sorted(
        path.name
        for path in TEMPLATES.iterdir()
        if path.is_dir() and (path / "archetype.toml").is_file()
    )


def generate(out: Path, name: str, *flags: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--author",
            "Ram Lakhan <ram.lakhan@ethara.ai>",
            "--out",
            str(out),
            "--name",
            name,
            "--seed",
            "4242",
            *flags,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return out / name


def validate(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(bundle)],
        check=False,
        capture_output=True,
        text=True,
    )


def provenance_values(text: str) -> dict[str, str]:
    match = PROVENANCE_RE.search(text)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key_match = re.match(r"^([a-z_][a-z0-9_]*):(?:\s+(.*))?$", line)
        if key_match:
            raw = (key_match.group(2) or "").strip()
            raw = raw.split("  #")[0].strip()
            values[key_match.group(1)] = raw.strip("'\"")
    return values


class TruthTemplateTests(unittest.TestCase):
    def test_every_archetype_ships_a_truth_template(self) -> None:
        missing = [
            a
            for a in archetypes()
            if not (TEMPLATES / a / "solution" / "TRUTH.md").is_file()
        ]
        self.assertEqual(
            missing, [], f"archetypes without a TRUTH.md template: {missing}"
        )

    def test_templates_declare_the_canonical_sections(self) -> None:
        for archetype in archetypes():
            with self.subTest(archetype=archetype):
                text = (TEMPLATES / archetype / "solution" / "TRUTH.md").read_text(
                    encoding="utf-8"
                )
                positions = [text.find(f"\n{section}\n") for section in TRUTH_SECTIONS]
                self.assertNotIn(-1, positions, "a canonical section is missing")
                self.assertEqual(
                    positions,
                    sorted(positions),
                    "canonical sections are out of order",
                )

    def test_templates_avoid_residual_markers_other_than_placeholders(self) -> None:
        """Templates legitimately contain {{...}}; they must contain nothing else."""
        banned = re.compile(
            r"__[A-Z][A-Z0-9_]*__|<TAG>|\bTODO\b|\bFIXME\b|\bXXX\b|\bPLACEHOLDER\b"
        )
        for archetype in archetypes():
            with self.subTest(archetype=archetype):
                text = (TEMPLATES / archetype / "solution" / "TRUTH.md").read_text(
                    encoding="utf-8"
                )
                self.assertIsNone(
                    banned.search(text), "template contains a residual marker"
                )

    def test_multiline_tokens_sit_at_column_zero(self) -> None:
        """A block token nested in a list item renders as broken Markdown."""
        block_tokens = (
            "{{TRUTH_ARTIFACT_LIST}}",
            "{{TRUTH_POSITIVE_TEST_LIST}}",
            "{{TRUTH_NEGATIVE_TEST_LIST}}",
            "{{TRUTH_RUBRIC_LIST}}",
            "{{TRUTH_PROVENANCE_BLOCK}}",
        )
        for archetype in archetypes():
            text = (TEMPLATES / archetype / "solution" / "TRUTH.md").read_text(
                encoding="utf-8"
            )
            for number, line in enumerate(text.splitlines(), start=1):
                for token in block_tokens:
                    if token in line:
                        with self.subTest(
                            archetype=archetype, token=token, line=number
                        ):
                            self.assertEqual(
                                line,
                                token,
                                "block token must be alone on its own line at column 0",
                            )

    def test_grammar_tokens_are_confined_to_format_recovery(self) -> None:
        """Grammar placeholders are only populated for format-recovery."""
        grammar = re.compile(
            r"\{\{(?:GRAMMAR_[A-Z0-9_]+|MAGIC_[A-Z]+|VERSION_NUM[A-Z_]*"
            r"|FORMAT_TAG|FORMAT_EXT|CONTAINER_NOUN|PRODUCER_SYSTEM)\}\}"
        )
        for archetype in archetypes():
            if archetype == "format-recovery":
                continue
            with self.subTest(archetype=archetype):
                text = (TEMPLATES / archetype / "solution" / "TRUTH.md").read_text(
                    encoding="utf-8"
                )
                found = sorted(set(grammar.findall(text)))
                self.assertEqual(
                    found, [], f"{archetype} uses format-recovery-only tokens"
                )


class TruthGenerationTests(unittest.TestCase):
    bundles: dict[str, Path] = {}
    _tmp: tempfile.TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        out = Path(cls._tmp.name)
        for archetype in archetypes():
            cls.bundles[archetype] = generate(
                out, f"truth-{archetype}", "--archetype", archetype
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def truth(self, archetype: str) -> str:
        return (self.bundles[archetype] / "solution" / "TRUTH.md").read_text(
            encoding="utf-8"
        )

    def test_truth_md_is_written_into_every_bundle_solution_dir(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                self.assertTrue((bundle / "solution" / "TRUTH.md").is_file())

    def test_no_placeholder_survives_either_pass(self) -> None:
        for archetype in self.bundles:
            with self.subTest(archetype=archetype):
                match = RESIDUAL_MARKER_RE.search(self.truth(archetype))
                self.assertIsNone(
                    match, f"unresolved marker {match.group(0) if match else ''!r}"
                )

    def test_title_names_the_bundle(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                first = self.truth(archetype).splitlines()[0]
                self.assertEqual(first, f"# TRUTH.md - {bundle.name}")

    def test_sections_are_present_and_ordered(self) -> None:
        for archetype in self.bundles:
            with self.subTest(archetype=archetype):
                text = self.truth(archetype)
                positions = [text.find(f"\n{section}\n") for section in TRUTH_SECTIONS]
                self.assertNotIn(-1, positions)
                self.assertEqual(positions, sorted(positions))

    def test_defect_items_are_classified(self) -> None:
        for archetype in self.bundles:
            with self.subTest(archetype=archetype):
                text = self.truth(archetype)
                body = text.split("## Defect", 1)[1].split("## Load-bearing work", 1)[0]
                self.assertGreaterEqual(
                    body.count("(focal)"), 2, "need >=2 focal defects"
                )
                self.assertGreaterEqual(
                    body.count("(drift)"), 1, "need >=1 drift defect"
                )
                self.assertGreaterEqual(body.count("(trap)"), 1, "need >=1 trap defect")

    def test_document_is_a_derivation_not_a_stub(self) -> None:
        for archetype in self.bundles:
            with self.subTest(archetype=archetype):
                self.assertGreater(len(self.truth(archetype)), 4000)

    def test_provenance_digests_match_the_shipped_solution(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                values = provenance_values(self.truth(archetype))
                for key, rel in (
                    ("fix_patch_sha256", "solution/solve.sh"),
                    ("solve_py_sha256", "solution/solve.py"),
                ):
                    digest = hashlib.sha256((bundle / rel).read_bytes()).hexdigest()
                    self.assertEqual(values.get(key), digest, f"{key} is stale")

    def test_provenance_carries_every_required_key(self) -> None:
        for archetype in self.bundles:
            with self.subTest(archetype=archetype):
                values = provenance_values(self.truth(archetype))
                missing = [k for k in REQUIRED_PROVENANCE_KEYS if not values.get(k)]
                self.assertEqual(
                    missing, [], f"missing or empty provenance keys: {missing}"
                )

    def test_provenance_identity_matches_task_toml(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                values = provenance_values(self.truth(archetype))
                declared = tomllib.loads(
                    (bundle / "task.toml").read_text(encoding="utf-8")
                )
                self.assertEqual(values.get("instance_id"), bundle.name)
                self.assertEqual(values.get("task_name"), declared["task"]["name"])

    def test_channel_a_facts_agree_with_test_weights(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                text = self.truth(archetype)
                source = (bundle / "tests" / "test_output.py").read_text(encoding="utf-8")
                weights = {
                    name: int(w)
                    for name, w in re.findall(
                        r"^criteria\.(\w+)\(weight=(-?\d+)\)$", source, re.M
                    )
                }
                self.assertTrue(weights, "no criteria registrations found")
                positive_total = sum(w for w in weights.values() if w > 0)
                negative_total = sum(w for w in weights.values() if w < 0)
                self.assertIn(
                    str(positive_total), text, "positive weight total not stated"
                )
                self.assertIn(
                    str(negative_total), text, "negative weight total not stated"
                )
                for name in weights:
                    self.assertIn(name, text, f"check {name} is never named")

    def test_rubric_criteria_are_reproduced(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                text = self.truth(archetype)
                judge = tomllib.loads(
                    (bundle / "tests" / "judge.toml").read_text(encoding="utf-8")
                )
                self.assertIn(f"{len(judge['criterion'])} criteria", text)

    def test_declared_artifacts_are_reproduced(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                text = self.truth(archetype)
                declared = tomllib.loads(
                    (bundle / "task.toml").read_text(encoding="utf-8")
                )
                for artifact in declared["artifacts"]:
                    self.assertIn(artifact, text, f"artifact {artifact} is never named")

    def test_channel_combining_rule_matches_reward_toml(self) -> None:
        """tests/reward.toml gives each channel half; TRUTH.md must say the same."""
        for archetype in self.bundles:
            with self.subTest(archetype=archetype):
                self.assertIn("gives each half", self.truth(archetype))

    def test_truth_md_is_not_shipped_into_the_agent_image(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                dockerfile = (bundle / "environment" / "Dockerfile").read_text(
                    encoding="utf-8"
                )
                self.assertNotIn("TRUTH.md", dockerfile)

    def test_generation_is_deterministic_for_a_fixed_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repeat = generate(
                Path(tmp), "truth-format-recovery", "--archetype", "format-recovery"
            )
            self.assertEqual(
                (repeat / "solution" / "TRUTH.md").read_bytes(),
                (
                    self.bundles["format-recovery"] / "solution" / "TRUTH.md"
                ).read_bytes(),
            )

    def test_every_generated_bundle_passes_the_validator(self) -> None:
        for archetype, bundle in self.bundles.items():
            with self.subTest(archetype=archetype):
                result = validate(bundle)
                self.assertEqual(result.returncode, 0, result.stdout[-3000:])
                self.assertIn("§15 TRUTH.md", result.stdout)


class TruthValidatorRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.bundle = generate(
            Path(self._tmp.name), "truth-reject", "--archetype", "cli-config"
        )
        self.truth = self.bundle / "solution" / "TRUTH.md"
        self.assertEqual(
            validate(self.bundle).returncode, 0, "fixture must start clean"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def assert_rejected(self, needle: str) -> None:
        result = validate(self.bundle)
        self.assertNotEqual(
            result.returncode, 0, "validator accepted a broken TRUTH.md"
        )
        self.assertIn(needle, result.stdout)

    def test_missing_file_is_rejected(self) -> None:
        self.truth.unlink()
        self.assert_rejected("FAIL[§15.1]")

    def test_stub_is_rejected(self) -> None:
        self.truth.write_text("# TRUTH.md - truth-reject\n", encoding="utf-8")
        self.assert_rejected("FAIL[§15.1]")

    def test_wrong_title_is_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(text.replace("# TRUTH.md - truth-reject", "# TRUTH", 1))
        self.assert_rejected("FAIL[§15.2]")

    def test_missing_section_is_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(text.replace("## Pitfalls", "## Gotchas", 1))
        self.assert_rejected("FAIL[§15.3]")

    def test_reordered_sections_are_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        head, _, tail = text.partition("## Root cause")
        pitfalls_head, _, pitfalls_tail = tail.partition("## Pitfalls")
        # Move Pitfalls ahead of Root cause.
        self.truth.write_text(
            head + "## Pitfalls" + pitfalls_tail + "## Root cause" + pitfalls_head
        )
        self.assert_rejected("FAIL[§15.3]")

    def test_unclassified_defects_are_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(text.replace("(focal)", "(important)"))
        self.assert_rejected("FAIL[§15.4]")

    def test_missing_provenance_key_is_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(text.replace("\nlanguage:", "\nlang:", 1))
        self.assert_rejected("FAIL[§15.5]")

    def test_authoring_attribution_is_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(text.replace("\nlanguage:", "\nauthored_by: harbor-generator\nlanguage:", 1))
        self.assert_rejected("FAIL[§15.5]")

    def test_generation_narration_is_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(text.replace("## Defect\n", "## Defect\n\nThis bundle was scaffolded by generate_bundle.py.\n", 1))
        self.assert_rejected("FAIL[§15.5]")

    def test_mismatched_instance_id_is_rejected(self) -> None:
        text = self.truth.read_text(encoding="utf-8")
        self.truth.write_text(
            text.replace("instance_id: truth-reject", "instance_id: other", 1)
        )
        self.assert_rejected("FAIL[§15.6]")

    def test_stale_solution_digest_is_rejected(self) -> None:
        """Editing solve.sh without regenerating must invalidate the bundle."""
        solve = self.bundle / "solution" / "solve.sh"
        solve.write_text(
            solve.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8"
        )
        self.assert_rejected("FAIL[§15.7]")

    def test_contradicting_the_weight_total_is_rejected(self) -> None:
        tests_py = self.bundle / "tests" / "test_output.py"
        source = tests_py.read_text(encoding="utf-8")
        match = re.search(r"^criteria\.(\w+)\(weight=1\)$", source, re.M)
        self.assertIsNotNone(match, "fixture needs a weight-1 check to raise")
        tests_py.write_text(
            source.replace(match.group(0), f"criteria.{match.group(1)}(weight=3)", 1),
            encoding="utf-8",
        )
        self.assert_rejected("FAIL[§15.8]")

    def test_unnamed_negative_test_is_rejected(self) -> None:
        tests_py = self.bundle / "tests" / "test_output.py"
        source = tests_py.read_text(encoding="utf-8")
        old = re.search(r"^criteria\.(negative_\w+)\(weight=-\d\)$", source, re.M).group(1)
        source = re.sub(rf"\b{old}\b", "negative_undocumented_vector", source)
        tests_py.write_text(source, encoding="utf-8")
        self.assert_rejected("FAIL[§15.8]")


class TruthGeneratorContractTests(unittest.TestCase):
    def test_generation_aborts_when_the_template_is_absent(self) -> None:
        template = TEMPLATES / "data-pipeline" / "solution" / "TRUTH.md"
        original = template.read_bytes()
        template.unlink()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(GENERATOR),
                        "--author",
                        "Ram Lakhan <ram.lakhan@ethara.ai>",
                        "--out",
                        tmp,
                        "--name",
                        "truth-absent",
                        "--archetype",
                        "data-pipeline",
                        "--seed",
                        "4242",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertNotEqual(
                result.returncode, 0, "generator silently skipped TRUTH.md"
            )
            self.assertIn("TRUTH.md", result.stderr)
        finally:
            template.write_bytes(original)

    def test_generation_aborts_on_an_unresolved_token(self) -> None:
        template = TEMPLATES / "data-pipeline" / "solution" / "TRUTH.md"
        original = template.read_text(encoding="utf-8")
        template.write_text(
            original + "\nDangling: {{TRUTH_NOT_A_REAL_TOKEN}}\n", encoding="utf-8"
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(GENERATOR),
                        "--author",
                        "Ram Lakhan <ram.lakhan@ethara.ai>",
                        "--out",
                        tmp,
                        "--name",
                        "truth-dangling",
                        "--archetype",
                        "data-pipeline",
                        "--seed",
                        "4242",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertNotEqual(
                result.returncode, 0, "generator shipped an unresolved token"
            )
            self.assertIn("TRUTH_NOT_A_REAL_TOKEN", result.stderr)
        finally:
            template.write_text(original, encoding="utf-8")

    def test_generator_never_emits_a_cheat_directory(self) -> None:
        """The generator must never scaffold a cheat/ overlay (feature removed)."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle = generate(
                Path(tmp),
                "truth-no-cheat",
                "--archetype",
                "format-recovery",
            )
            self.assertFalse((bundle / "cheat").exists())
            self.assertTrue((bundle / "solution" / "TRUTH.md").is_file())
            self.assertEqual(validate(bundle).returncode, 0)

    def test_auto_selected_archetype_still_produces_a_valid_truth_md(self) -> None:
        """--archetype omitted means the generator picks; every pick must work."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for seed in ("1", "17", "1234", "99999"):
                name = f"truth-auto-{seed}"
                subprocess.run(
                    [
                        sys.executable,
                        str(GENERATOR),
                        "--author",
                        "Ram Lakhan <ram.lakhan@ethara.ai>",
                        "--out",
                        str(out),
                        "--name",
                        name,
                        "--seed",
                        seed,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                with self.subTest(seed=seed):
                    bundle = out / name
                    self.assertTrue((bundle / "solution" / "TRUTH.md").is_file())
                    result = validate(bundle)
                    self.assertEqual(result.returncode, 0, result.stdout[-3000:])


if __name__ == "__main__":
    unittest.main()
