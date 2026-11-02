from __future__ import annotations

import json
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
QC = ROOT.parent / "Input_Bundle_QC"
AUTHOR = "Ram Lakhan <ram.lakhan@ethara.ai>"


def _archetypes() -> list[str]:
    return sorted(
        path.name
        for path in TEMPLATES.iterdir()
        if path.is_dir() and (path / "archetype.toml").is_file()
    )


class GeneratorContractTests(unittest.TestCase):
    def generate(
        self,
        output: Path,
        name: str,
        *flags: str,
        archetype: str = "format-recovery",
        author: str | None = AUTHOR,
    ) -> subprocess.CompletedProcess[str]:
        output.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--out",
                str(output),
                "--name",
                name,
                "--archetype",
                archetype,
                "--category",
                "file-operations",
                "--seed",
                "42",
                *(["--author", author] if author else []),
                *flags,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def validate(self, bundle: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(bundle)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_default_run_never_emits_a_cheat_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(Path(tmp), "no-cheat-default")
            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = Path(tmp) / "no-cheat-default"
            self.assertFalse((bundle / "cheat").exists())
            self.assertEqual(self.validate(bundle).returncode, 0)

    def test_with_cheat_flag_is_no_longer_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(Path(tmp), "rejects-with-cheat", "--with-cheat")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unrecognized arguments", result.stderr.lower())

    def test_every_archetype_ships_without_a_cheat_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for archetype in _archetypes():
                with self.subTest(archetype=archetype):
                    name = f"no-cheat-{archetype}"
                    result = self.generate(out, name, archetype=archetype)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse((out / name / "cheat").exists())

    def test_author_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(Path(tmp), "authors-missing", author=None)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--author is required", result.stderr)

    def test_author_is_recorded_as_a_name_email_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(Path(tmp), "authors-single")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = tomllib.loads(
                (Path(tmp) / "authors-single" / "task.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                data["task"]["authors"],
                [{"name": "Ram Lakhan", "email": "ram.lakhan@ethara.ai"}],
            )

    def test_multiple_authors_are_recorded_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(
                Path(tmp),
                "authors-multiple",
                "--author",
                "Poonam Chourey <poonam.chourey@ethara.ai>",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = tomllib.loads(
                (Path(tmp) / "authors-multiple" / "task.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [a["name"] for a in data["task"]["authors"]],
                ["Ram Lakhan", "Poonam Chourey"],
            )

    def test_non_ethara_email_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(
                Path(tmp), "authors-domain", author="Ram Lakhan <ram.lakhan@example.com>"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ethara.ai", result.stderr)

    def test_placeholder_or_lowercase_name_is_rejected(self) -> None:
        for bad in ("ram lakhan <ram.lakhan@ethara.ai>", "Ram <ram@ethara.ai>", "ram.lakhan@ethara.ai"):
            with self.subTest(author=bad), tempfile.TemporaryDirectory() as tmp:
                result = self.generate(Path(tmp), "authors-bad", author=bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("author", result.stderr.lower())

    def test_duplicate_author_emails_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(Path(tmp), "authors-duplicate", "--author", AUTHOR)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("more than once", result.stderr)

    def test_every_template_judge_toml_pins_the_judge_header(self) -> None:
        for archetype in _archetypes():
            with self.subTest(archetype=archetype):
                data = tomllib.loads(
                    (TEMPLATES / archetype / "tests" / "judge.toml").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    list(data["judge"]),
                    ["judge", "mode", "timeout", "atif-trajectory", "weight"],
                )
                self.assertEqual(data["judge"]["atif-trajectory"], "/logs/agent/trajectory.json")
                self.assertGreaterEqual(len(data["criterion"]), 8)

    def test_every_template_declares_its_input_directories(self) -> None:
        for archetype in _archetypes():
            with self.subTest(archetype=archetype):
                manifest = tomllib.loads((TEMPLATES / archetype / "archetype.toml").read_text(encoding="utf-8"))
                dirs = {item["dir"]: item["mount"] for item in manifest["inputs"]}
                dockerfile = (TEMPLATES / archetype / "environment" / "Dockerfile").read_text(encoding="utf-8")
                for name, mount in dirs.items():
                    self.assertRegex(dockerfile, rf"(?m)^COPY (--\S+ )*{name} {mount}$")
                    self.assertTrue((TEMPLATES / archetype / "environment" / name).is_dir())

    def test_multi_directory_inputs_are_emitted_copied_and_embedded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.generate(Path(tmp), "multi-input", archetype="repo-patch")
            self.assertEqual(result.returncode, 0, result.stderr)
            env = Path(tmp) / "multi-input" / "environment"
            self.assertEqual(sorted(p.name for p in env.iterdir()), ["Dockerfile", "ci", "repo"])
            self.assertTrue((env / "repo" / "pyproject.toml").is_file())
            self.assertTrue((env / "ci" / "failing_tests.log").is_file())
            tests_py = (Path(tmp) / "multi-input" / "tests" / "test_output.py").read_text(encoding="utf-8")
            self.assertIn('"failing_tests.log":', tests_py)
            self.assertNotIn("{{SHIPPED", tests_py)

    def test_generator_rejects_an_input_directory_the_dockerfile_never_copies(self) -> None:
        path = TEMPLATES / "repo-patch" / "environment" / "Dockerfile"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original.replace("COPY ci /app/ci\n", ""), encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp:
                result = self.generate(Path(tmp), "input-not-copied", archetype="repo-patch")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COPY ci /app/ci", result.stderr)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_generator_rejects_an_unsafe_input_directory_name(self) -> None:
        path = TEMPLATES / "cli-config" / "archetype.toml"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original.replace('dir = "data"', 'dir = "../data"', 1), encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp:
                result = self.generate(Path(tmp), "unsafe-input", archetype="cli-config")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("plain directory name", result.stderr)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_every_template_judge_annotation_carries_only_the_four_keys(self) -> None:
        for archetype in _archetypes():
            with self.subTest(archetype=archetype):
                data = tomllib.loads((TEMPLATES / archetype / "tests" / "judge.toml").read_text(encoding="utf-8"))
                for c in data["criterion"]:
                    self.assertEqual(list(c["annotations"]), ["mode", "type", "evaluation_target", "importance"])

    def test_generator_rejects_a_retired_annotation_key(self) -> None:
        path = TEMPLATES / "format-recovery" / "tests" / "judge.toml"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original.replace('evaluation_target = ', 'kind = "outcome"\nevaluation_target = ', 1), encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp:
                result = self.generate(Path(tmp), "judge-retired-key")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("annotations", result.stderr)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_generator_rejects_an_extra_judge_header_key(self) -> None:
        path = TEMPLATES / "format-recovery" / "tests" / "judge.toml"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original.replace('timeout = 300\n', 'timeout = 300\nreasoning_effort = "medium"\n', 1), encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp:
                result = self.generate(Path(tmp), "judge-extra-key")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reasoning_effort", result.stderr)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_generator_rejects_a_judge_toml_without_the_trajectory_key(self) -> None:
        path = TEMPLATES / "format-recovery" / "tests" / "judge.toml"
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(
                original.replace('atif-trajectory = "/logs/agent/trajectory.json"\n', ""),
                encoding="utf-8",
            )
            with tempfile.TemporaryDirectory() as tmp:
                result = self.generate(Path(tmp), "judge-no-trajectory")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("atif-trajectory", result.stderr)
        finally:
            path.write_text(original, encoding="utf-8")

    def test_every_archetype_emits_the_five_file_tests_dir_and_reward_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for archetype in _archetypes():
                with self.subTest(archetype=archetype):
                    name = f"tree-{archetype}"
                    result = self.generate(out, name, archetype=archetype)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    tests = out / name / "tests"
                    self.assertEqual(
                        sorted(p.name for p in tests.iterdir()),
                        ["Dockerfile", "judge.toml", "reward.toml", "test.sh", "test_output.py"],
                    )
                    weights = tomllib.loads((tests / "reward.toml").read_text())["reward"][0][
                        "weights"
                    ]
                    judge = tomllib.loads((tests / "judge.toml").read_text())["criterion"]
                    judge_pos = sum(c["weight"] for c in judge if c["weight"] > 0)
                    self.assertEqual(weights["judge"], 0.5 / judge_pos)

    def test_every_criterion_wrapper_calls_a_defined_check(self) -> None:
        import ast

        for archetype in _archetypes():
            with self.subTest(archetype=archetype):
                tree = ast.parse((TEMPLATES / archetype / "tests" / "test_output.py").read_text())
                defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
                called = {
                    node.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Name) and node.id.startswith("_check_")
                }
                self.assertEqual(sorted(called - defined), [])

    def test_privilege_dropping_templates_grant_read_on_agent_programs(self) -> None:
        for archetype in _archetypes():
            source = (TEMPLATES / archetype / "tests" / "test_output.py").read_text()
            if "setpriv" not in source:
                continue
            with self.subTest(archetype=archetype):
                self.assertIn("def _grant_read(", source)
                dropper = source.split("_SETPRIV, *command")[0].rsplit("def ", 1)[-1]
                self.assertIn("_grant_read(argument)", dropper)

    def test_every_archetype_passes_the_structure_judge_and_tests_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for archetype in _archetypes():
                name = f"qc-{archetype}"
                self.assertEqual(self.generate(out, name, archetype=archetype).returncode, 0)
                for script in ("structure_qc.py", "instruction_qc.py", "tests_qc.py", "judge_qc.py"):
                    with self.subTest(archetype=archetype, script=script):
                        proc = subprocess.run(
                            [sys.executable, str(QC / script), str(out / name)],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        fails = [ln for ln in proc.stdout.splitlines() if ln.startswith("FAIL")]
                        self.assertEqual(fails, [], proc.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
