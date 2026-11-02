"""Build one-, two- and three-lever reflex variants of solution/solve.py and
score each with the REAL tests (score.py); also report shipped figures.

usage: python3 variants.py OUT_JSON
"""
import json
import subprocess
import sys
import tempfile
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).parent
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/"
              "sensor-network-lsq-correlated-adjustment")
SRC = (BUNDLE / "solution" / "solve.py").read_text()

PATCHES = {
    # A: the second pass re-enters the whole rule (fits branch re-checked).
    "A": ("        shares.update(largest_remainder(total, held))",
          "        shares.update(closure_shares(total, held, floor))"),
    # B: one level: the named mark's own centring only.
    "B": ("            value += setup_variance(marks[parent], trail | {parent})",
          "            value += own_centring(marks[parent])"),
    # C: district read from the per-line region field.
    "C": ("        obs.region = DISTRICT_OF_SHARD[shard]",
          "        obs.region = rec[\"region\"].strip()"),
}


def build(levers, folder):
    text = SRC
    for lv in levers:
        old, new = PATCHES[lv]
        assert text.count(old) == 1, lv
        text = text.replace(old, new)
    path = folder / f"variant_{''.join(levers) or 'oracle'}.py"
    path.write_text(text)
    return path


def shipped_figures(prog, folder):
    data = folder / "shipped"
    if not data.exists():
        subprocess.run([sys.executable, str(BUNDLE / "tests" / "test_output.py"), str(data)],
                       check=True, env={"PYTHONPATH": str(HERE), "PYTHONDONTWRITEBYTECODE": "1",
                                        "PATH": "/usr/bin:/bin"})
    out = folder / ("out_" + prog.stem)
    out.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(prog), str(data), str(out)], check=True, capture_output=True)
    mt = json.loads((out / "model_test.json").read_text())
    rs = json.loads((out / "residual_summary.json").read_text())
    tr = json.loads((out / "normal_matrix_trace.json").read_text())
    adj = json.loads((out / "adjusted_state.json").read_text())
    return {"vtpv": mt["quadratic_form_vtpv"], "verdict": mt["verdict"],
            "variance_of_unit_weight": adj["variance_of_unit_weight"],
            "sum_signed": rs["sum_signed_micrometres"], "trace": tr["trace_decimal"]}


def main():
    folder = Path(tempfile.mkdtemp(prefix="snlsq-variants-"))
    combos = [()] + [c for r in (1, 2, 3) for c in combinations("ABC", r)]
    result = {}
    for levers in combos:
        prog = build(levers, folder)
        proc = subprocess.run([sys.executable, str(HERE / "score.py"), str(prog)],
                              capture_output=True, text=True,
                              env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
        lines = proc.stdout.strip().splitlines()
        failed = [ln.split()[2] for ln in lines if ln.startswith("fail")]
        score_line = lines[-1] if lines else proc.stderr[-400:]
        name = "".join(levers) or "oracle"
        result[name] = {"score": score_line, "failed": failed,
                        "shipped": shipped_figures(prog, folder)}
        print(name, score_line, flush=True)
    Path(sys.argv[1]).write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
