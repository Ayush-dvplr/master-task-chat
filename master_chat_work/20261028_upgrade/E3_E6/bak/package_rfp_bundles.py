#!/usr/bin/env python3
"""Package finished bundles into the team's hand-off convention.

The convention is defined by STRUCTURE.md in the reference bundle: one
directory per task uuid holding BOTH the task definition and every model's
trajectories, rather than the split input/output trees this harness produces
internally.

  <uuid>/
    README.md instruction.md task.toml
    environment/  solution/  tests/
    trajectories/<model>/pass_summary.json + run_1 .. run_8/

Driven by the jobs tree, not by any one corpus: each run's config.json records
``task.path``, the bundle the task was actually run from, so a task authored in
forge_tasks/, touchstones/ or anywhere else packages the same way with no
configuration. A job whose config.json predates that field is skipped by name
lookup in --corpus, and reported rather than passed over in silence.

This is the only delivery builder. It keeps report.json, reward.json,
reward_raw.json, reward-details.json, test-stdout.txt and trajectory_usage.json,
renames "Run N" to "run_N", and writes score.json in the exact field order
scripts/STRUCTURE.md section 6 specifies.

STRUCTURE.md itself is not copied into the bundles. It documents the layout for
whoever maintains this packager; the delivered corpus does not carry it, and
shipping a spec alongside the artefacts it describes only invites the two to
drift apart.

Nothing is copied out of artifacts/ selectively -- section 5 is explicit that
the subtree is evidence and must not be edited, so it is copied verbatim.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
CORPUS_DEFAULT = HARNESS.parent / "forge_tasks"
JOBS_DEFAULT = HARNESS / "Output"
OUT_DEFAULT = HARNESS / "Output_RFP"

#: STRUCTURE.md section 6, top-level order. Copied verbatim from report.json.
SCORE_ORDER = ("model", "run_index", "rubric", "rubric_weights_percentage",
               "test_weights_percentage", "final_reward", "judge_model")
#: Section 6, rubric item order. justification only when passed is false.
RUBRIC_ORDER = ("number", "criterion", "type", "evaluation_target",
                "importance", "score", "is_positive", "passed", "justification")
#: Section 4: agent/ holds exactly one file.
AGENT_KEEP = "trajectory.json"
#: Section 4: verifier/ holds exactly these six.
VERIFIER_KEEP = (
    "ctrf.json",
    "reward.json",
    "reward_raw.json",
    "reward-details.json",
    "score.json",
    "test-stdout.txt",
)
#: Files copied directly from the run root; trajectory_usage.json is resolved separately.
RUN_ROOT_KEEP = ("config.json", "report.json", "result.json")

RUN_RE = re.compile(r"^Run (\d+)$")


def _score_from_report(report: dict) -> dict:
    """verifier/score.json in the order section 6 fixes.

    Values are copied, never recomputed: the convention says so explicitly, and
    a recomputed percentage that disagreed with report.json would make the two
    files contradict each other inside one run.
    """
    rubric = []
    for item in report.get("rubric") or []:
        if not isinstance(item, dict):
            continue
        ordered = {k: item[k] for k in RUBRIC_ORDER if k in item}
        if item.get("passed") is not False:
            ordered.pop("justification", None)
        rubric.append(ordered)
    out = {}
    for key in SCORE_ORDER:
        if key == "rubric":
            out["rubric"] = rubric
        elif key in report:
            out[key] = report[key]
    return out


def _trajectory_usage_source(src: Path, model_dir: Path) -> Path | None:
    """Return the recorded usage file for one run, preferring run-local data."""
    candidates = (
        src / "trajectory_usage.json",
        src / "verifier" / "trajectory_usage.json",
        model_dir / "trajectory_usage.json",
    )
    return next((path for path in candidates if path.is_file()), None)


def _required_run_sources(src: Path, model_dir: Path) -> dict[str, Path]:
    """Resolve delivery-required evidence and fail before writing partial output."""
    sources = {
        "trajectory_usage.json": _trajectory_usage_source(src, model_dir),
        "verifier/reward_raw.json": src / "verifier" / "reward_raw.json",
        "verifier/reward-details.json": src / "verifier" / "reward-details.json",
    }
    missing = [name for name, path in sources.items() if path is None or not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{src}: missing delivery evidence: {', '.join(missing)}")
    return {name: path for name, path in sources.items() if path is not None}


def _package_run(src: Path, dst: Path, model_dir: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)

    required = _required_run_sources(src, model_dir)

    agent_src = src / "agent" / AGENT_KEEP
    if agent_src.is_file():
        (dst / "agent").mkdir(exist_ok=True)
        shutil.copy2(agent_src, dst / "agent" / AGENT_KEEP)

    # Section 5: evidence, copied whole and untouched.
    if (src / "artifacts").is_dir():
        shutil.copytree(src / "artifacts", dst / "artifacts", dirs_exist_ok=True)

    for name in RUN_ROOT_KEEP:
        if (src / name).is_file():
            shutil.copy2(src / name, dst / name)
    shutil.copy2(required["trajectory_usage.json"], dst / "trajectory_usage.json")

    vdst = dst / "verifier"
    vdst.mkdir(exist_ok=True)
    for name in VERIFIER_KEEP:
        if name == "score.json":
            continue
        source = required.get(f"verifier/{name}", src / "verifier" / name)
        if source.is_file():
            shutil.copy2(source, vdst / name)

    report_p = src / "report.json"
    if report_p.is_file():
        report = json.loads(report_p.read_text())
        (vdst / "score.json").write_text(
            json.dumps(_score_from_report(report), indent=2) + "\n")


def _task_source(bundle: Path) -> Path | None:
    """The task bundle this job was run from, per any run's config.json.

    Read from the run rather than inferred from the job directory name: the
    name is set by whoever launched the run, while ``task.path`` is recorded by
    harbor at execution time and so cannot drift from what actually ran.
    """
    for cfg in sorted(bundle.glob("trajectory/*/*/config.json")):
        try:
            data = json.loads(cfg.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        path = (data.get("task") or {}).get("path")
        if path:
            # Kiro runs use a staged copy with a widened verifier allowlist;
            # package the original task it was staged from instead.
            marker = Path(path) / ".kiro-staged-from"
            if marker.is_file():
                return Path(marker.read_text().strip())
            return Path(path)
    return None


def _corpus_by_name(corpus: Path) -> dict[str, Path]:
    """name -> bundle, for jobs whose config.json carries no task.path."""
    out: dict[str, Path] = {}
    if not corpus.is_dir():
        return out
    for d in sorted(corpus.iterdir()):
        toml = d / "task.toml"
        if toml.is_file():
            name = _task_name(toml)
            if name:
                out[name] = d
    return out


def _discover(jobs_root: Path, corpus: Path) -> dict[Path, list[Path]]:
    """task source -> job bundles that ran it."""
    by_name = _corpus_by_name(corpus)
    found: dict[Path, list[Path]] = {}
    for traj in sorted(jobs_root.glob("*/trajectory")):
        bundle = traj.parent
        src = _task_source(bundle)
        if src is None or not src.is_dir():
            current = by_name.get(bundle.name)
            if current is not None:
                src = current
        if src is None:
            print(f"  {bundle.name}: no task.path in config.json and no "
                  f"match in {corpus.name}/, skipped")
            continue
        if not src.is_dir():
            print(f"  {bundle.name}: task source {src} no longer exists, skipped")
            continue
        found.setdefault(src.resolve(), []).append(bundle)
    return found


def _task_name(task_toml: Path) -> str | None:
    m = re.search(r'^name\s*=\s*"([^"]+)"', task_toml.read_text(), re.M)
    return m.group(1).split("/")[-1] if m else None


def package(task_src: Path, bundles: list[Path], out_root: Path) -> bool:
    """One <uuid>/ bundle: the task definition plus every model's trajectories."""
    seen_models: set[str] = set()
    for bundle in bundles:
        for model_dir in sorted((bundle / "trajectory").iterdir()):
            if not model_dir.is_dir() or model_dir.name in seen_models:
                continue
            seen_models.add(model_dir.name)
            for run in sorted(model_dir.iterdir()):
                if run.is_dir() and RUN_RE.match(run.name):
                    _required_run_sources(run, model_dir)

    dst = out_root / task_src.name
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    for f in ("README.md", "instruction.md", "task.toml"):
        if (task_src / f).is_file():
            shutil.copy2(task_src / f, dst / f)
    for d in ("environment", "solution", "tests"):
        if (task_src / d).is_dir():
            shutil.copytree(task_src / d, dst / d)

    # The convention places the answer key inside solution/; some corpora keep
    # it at the bundle root.
    if (task_src / "TRUTH.md").is_file():
        (dst / "solution").mkdir(exist_ok=True)
        shutil.copy2(task_src / "TRUTH.md", dst / "solution" / "TRUTH.md")

    total = 0
    for bundle in bundles:
        for model_dir in sorted((bundle / "trajectory").iterdir()):
            if not model_dir.is_dir():
                continue
            mdst = dst / "trajectories" / model_dir.name
            if mdst.exists():
                print(f"    {model_dir.name}: already packaged from another "
                      f"job, {bundle.name} skipped")
                continue
            mdst.mkdir(parents=True)
            summary = model_dir / "pass_summary.json"
            if summary.is_file():
                shutil.copy2(summary, mdst / "pass_summary.json")
            n = 0
            for run in sorted(model_dir.iterdir()):
                m = RUN_RE.match(run.name)
                if not (run.is_dir() and m):
                    continue
                _package_run(run, mdst / f"run_{int(m.group(1))}", model_dir)
                n += 1
            total += n
            print(f"    {model_dir.name}: {n} run(s)")
    print(f"  {task_src.name} ({task_src.parent.name}/): {total} run(s)")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=OUT_DEFAULT,
                    help=f"output root (default: {OUT_DEFAULT.name}/)")
    ap.add_argument("--corpus", type=Path, default=CORPUS_DEFAULT,
                    help="fallback lookup for jobs with no task.path")
    ap.add_argument("--jobs", type=Path, default=JOBS_DEFAULT)
    a = ap.parse_args(argv)

    if not a.jobs.is_dir():
        print(f"  no jobs at {a.jobs}, nothing to package")
        return 0

    found = _discover(a.jobs, a.corpus)
    if not found:
        print("  no packageable jobs found")
        return 0

    a.out.mkdir(parents=True, exist_ok=True)
    built = 0
    for task_src in sorted(found):
        built += package(task_src, found[task_src], a.out)
    print(f"\n  packaged {built} bundle(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
