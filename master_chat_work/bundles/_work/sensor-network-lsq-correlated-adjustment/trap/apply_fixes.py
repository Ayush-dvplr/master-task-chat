from pathlib import Path
b=Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sensor-network-lsq-correlated-adjustment')

def replace_one(s,a,c):
 assert s.count(a)==1,(a[:80],s.count(a))
 return s.replace(a,c)

p=b/'tests/judge.toml';s=p.read_text()
s=replace_one(s,'description = "The agent writes derive_report.py as maintainable code: descriptive function names, explicit errors for malformed input, and no dead code, debug prints or bare except clauses."','description = "The agent writes derive_report.py so that a missing or unparsable input file stops the run with an error message naming that file."')
s=replace_one(s,'type = "safety and boundaries"','type = "instruction following"')
p.write_text(s)

p=b/'solution/solve.py';s=p.read_text()
s=replace_one(s,'# ------------------------------------------------------------- file readers\ndef table_rows', '# ------------------------------------------------------------- file readers\nCURRENT_INPUT = None\n\ndef source_path(path: Path) -> Path:\n    global CURRENT_INPUT\n    CURRENT_INPUT = path\n    return path\n\ndef table_rows')
s=replace_one(s,'    lines = path.read_text(encoding="utf-8").splitlines()','    lines = source_path(path).read_text(encoding="utf-8").splitlines()')
s=replace_one(s,'        path = data_dir / name\n        if delim == "json":','        path = source_path(data_dir / name)\n        if delim == "json":')
s=replace_one(s,'        result.append(to_observation(ident, rec, decl, factors, centring))','        try:\n            result.append(to_observation(ident, rec, decl, factors, centring))\n        except (ValueError, KeyError, IndexError, TypeError, ArithmeticError) as exc:\n            raise ValueError(f"{shard}: {exc}") from exc')
s=replace_one(s,'with zipfile.ZipFile(data_dir / "adjustment_control_workbook.xlsx") as book:', 'with zipfile.ZipFile(source_path(data_dir / "adjustment_control_workbook.xlsx")) as book:')
s=replace_one(s,'for line in (data_dir / "iteration_policy.yaml").read_text(encoding="utf-8").splitlines():','for line in source_path(data_dir / "iteration_policy.yaml").read_text(encoding="utf-8").splitlines():')
s=replace_one(s,'    write_reports(Path(argv[1]), Path(argv[2]))\n    return 0','    try:\n        write_reports(Path(argv[1]), Path(argv[2]))\n    except (OSError, ValueError, KeyError, IndexError, TypeError, EOFError,\n            ArithmeticError, csv.Error, ET.ParseError, zipfile.BadZipFile) as exc:\n        source = getattr(exc, "filename", None) or CURRENT_INPUT or Path(argv[1])\n        print(f"input {source}: {exc}", file=sys.stderr)\n        return 1\n    return 0')
p.write_text(s)

p=b/'solution/TRUTH.md';s=p.read_text();s=replace_one(s,'fix_patch_sha256: 6ecfa4ebda20143e5c354aa377b3e0d8b6504dd1d6d958232ae3e632580d0135\n','');p.write_text(s)

p=b/'tests/test_output.py';s=p.read_text()
s=replace_one(s,'rows.append([st, sf[st], f"restatement_{seq}"])','frame = sf[st]\n        if "station_frame" in CFG and st in ("ALPHA", "FICUS"):\n            frame = "FrameB" if frame != "FrameB" else "FrameA"\n        rows.append([st, frame, f"restatement_{seq}"])')
s=replace_one(s,'rows.append([str(ep), ec[ep]])\n    _write_csv_rows(data_dir / "epoch_campaign_map.csv", header, rows)','campaign = ec[ep]\n        if "epoch_campaign" in CFG and ep in (1, 2):\n            campaign = "Campaign2" if campaign != "Campaign2" else "Campaign1"\n        rows.append([str(ep), campaign])\n    _write_csv_rows(data_dir / "epoch_campaign_map.csv", header, rows)')
s=replace_one(s,'    want_w = {o.obs_id: (w.numerator, w.denominator)\n              for o, w in zip(ref["obs"], ref["weights_final"])}\n    wr = _rows(out, "final_weights.psv", "|")\n    assert len(wr) == len(want_w)\n    assert {r["obs_id"]: (int(r["weight_num"]), int(r["weight_den"])) for r in wr} == want_w','''\n\ndef _check_final_weights(name: str) -> None:\n    h = _hidden(name)\n    ref, out = h["ref"], h["out"]\n    assert h["code"] == 0, f"program exit status {h['code']}"\n    want_w = {o.obs_id: (w.numerator, w.denominator)\n              for o, w in zip(ref["obs"], ref["weights_final"])}\n    wr = _rows(out, "final_weights.psv", "|")\n    assert len(wr) == len(want_w)\n    assert {r["obs_id"]: (int(r["weight_num"]), int(r["weight_den"])) for r in wr} == want_w''')
s=replace_one(s,'    trace = ref["trace"]\n    got = _jload(out, "normal_matrix_trace.json")\n    assert (got["trace_num"], got["trace_den"]) == (trace.numerator, trace.denominator)\n    assert got["trace_decimal"] == frac_to_str(trace, 6)','''\n\ndef _check_normal_matrix_trace(name: str) -> None:\n    h = _hidden(name)\n    ref, out = h["ref"], h["out"]\n    assert h["code"] == 0, f"program exit status {h['code']}"\n    trace = ref["trace"]\n    got = _jload(out, "normal_matrix_trace.json")\n    assert (got["trace_num"], got["trace_den"]) == (trace.numerator, trace.denominator)\n    assert got["trace_decimal"] == frac_to_str(trace, 6)''')
for name in ('challenge','eval','audit'):
    marker=f'def test_{name}_rollup_documents():'
    addition=f'''def test_{name}_final_weights():\n    """POSITIVE: final_weights.psv matches the derived final weights on {name}."""\n    _check_final_weights("{name}")\n\n\n'''
    s=replace_one(s,marker,addition+marker)
    marker=f'def test_{name}_summary_reports():'
    # Keep the original summary function and add trace after it, before next function.
    start=s.index(marker)
    next_def=s.find('\n\ndef ',start+len(marker))
    assert next_def!=-1
    addition=f'''\n\ndef test_{name}_normal_matrix_trace():\n    """POSITIVE: normal_matrix_trace.json matches the derived trace on {name}."""\n    _check_normal_matrix_trace("{name}")'''
    s=s[:next_def]+addition+s[next_def:]
    s=replace_one(s,f'criteria.{name}_observation_sets(weight=3)',f'criteria.{name}_observation_sets(weight=2)\ncriteria.{name}_final_weights(weight=1)')
    s=replace_one(s,f'criteria.{name}_summary_reports(weight=3)',f'criteria.{name}_summary_reports(weight=2)\ncriteria.{name}_normal_matrix_trace(weight=1)')
    # Register split tests in rewardkit.
    marker=f'@criterion(description="hidden extract {1 if name=="challenge" else 2 if name=="eval" else 3}: the district, epoch and frame-campaign rollups match.")'
    addition=f'@criterion(description="hidden extract {1 if name=="challenge" else 2 if name=="eval" else 3}: final_weights.psv matches each derived final weight.")\ndef {name}_final_weights(workspace: Path) -> bool:\n    return _passes(test_{name}_final_weights)\n\n'
    s=replace_one(s,marker,addition+marker)
    # Put trace criterion ahead of next extract/isolated criterion by finding existing summary criteria wrapper.
    wrapper=f'def {name}_summary_reports(workspace: Path) -> bool:\n    return _passes(test_{name}_summary_reports)'
    addition=f'''\n\n@criterion(description="hidden extract {1 if name=="challenge" else 2 if name=="eval" else 3}: normal_matrix_trace.json matches the derived trace.")\ndef {name}_normal_matrix_trace(workspace: Path) -> bool:\n    return _passes(test_{name}_normal_matrix_trace)'''
    s=replace_one(s,wrapper,wrapper+addition)
# descriptions for original checks no longer claim split artifact
s=s.replace('the removed blunder set, the downweighted set and flags, and every final weight match.','the removed blunder set and downweighted flags match.')
s=s.replace('the removed blunder set, the downweighted set and flags, and every final weight match.','the removed blunder set and downweighted flags match.')
s=s.replace('status.txt, the YAML, Markdown and XML summaries and the normal matrix trace match the derived figures.','status.txt, the YAML, Markdown and XML summaries match the derived figures.')
s=s.replace('summaries and the normal matrix trace.','summaries.')
s=s.replace('removed, downweighted and final weights.','removed and downweighted sets and flags.')
s=s.replace('removed blunders, downweighted set and\n    flags, and every final weight.','removed blunders and downweighted flags.')
s=s.replace('status.txt, YAML, Markdown and XML summaries\n    and the normal matrix trace, against the derived figures.','status.txt, YAML, Markdown and XML summaries\n    against the derived figures.')
p.write_text(s)
print('applied')
