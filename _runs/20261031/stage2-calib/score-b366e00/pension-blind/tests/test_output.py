"""Behavioral verifier for the pension accrual and rebase engine."""
# pyright: reportMissingImports=false
from __future__ import annotations
import ast, base64, hashlib, json, os, signal, subprocess, sys, tempfile, threading, zlib
from pathlib import Path
from typing import Any, Callable
from rewardkit import criteria, criterion
SAMPLE_SEED=9146205738
CHALLENGE_SEED=682104935
EVAL_SEED=307442861
OUT=Path("/app/out")
SCRIPT=OUT/"calculate_pension.py"
REPORTS=("manifest.json","data_quality.json","service_ledger.json","accrual_ledger.json","cola_ledger.json","member_benefits.json","plan_rollups.json","exception_register.json","audit_trace.json")
_SETPRIV=["setpriv","--reuid=nobody","--regid=nogroup","--clear-groups"]
_PACKED={'cola_rules.jsonl': 'eNqrVkrOz0mMz0xRslJy9vdx1HXUNTJS0lEqyEnMg4gG+Dj66ToChVLT0lKTSzLLUuNTEktSgTJGBkZGugaGQASUTUtMLskvik8qKFayMjQwMjWo5arGYrYJ8Wab4DDb2ACb2U66RoaYZjvhMNsQh9mG5qbYzTYm3mxjXGECcjcANwVpPg==',
 'elections.jsonl': 'eNp90D0LwjAQBuDdn5HZg0vSQu2m2EkbJ3EM/TghYJoSsxX/u7U6SdL1Xrjn3psYPagLxg3a9Kxk1Rk4crZllmxL/jusq/o39RSMJ0tD0H0TaM4EigwwA57PsRuXTfemC87rdnyycscRX5spxogoI1JMDshhuSLGyAQjom1Euo0ELEAmmKJIMIf98Y+5qpO63NTK01ba4Id5A8WWfmU=',
 'leave_intervals.jsonl': 'eNqN0DELwjAQhuHdn3GzgctpLHRr0c2urqU1NxSsSBpciv/dJAWpTQqFTO+Qh+9GeHDz5rrTkMP1JiRKUcAeeu5bNlOuLpXvrg62MdYVQpICSYTIT/1Lakp3w7qzdfsaIMfPbkwg5UbkGCNZjCjEpEMrY+jfISHdU3Pn4PeFNHcylXJo5Wi03IMCT4s96OloDyWdsjhvUfx/8dVkrEgMZ/sCrtyJUw==',
 'members.jsonl': 'eNqrVspNzU1KLYrPTFGyUvJ19dU1NDBU0lEqyEnMg4gF+Dj66ToChZIyi0oy4lMSS1KBooaWZka6Bsa6hqZAmeKSxJLSYqBoYnJJZlmqUi1XNRZjjYgz1lTXwFLX2IBIY42wudYJi7EGugaGusaGRBrr5OiCaWwEprHmYGMNsBsLAJC7ZfQ=',
 'plans.json': 'eNqFjrEOgjAQhneegtxck4qQIhvMxrgb05ylKglcm1oGY3x3KR1t4o3f/f/dd87y/A12RJJDDw2cDu1x0wIDVMrNOMqrfUKzrTkDMm5aAN61nAz5x8JF4Brd+JJO97Pyg6HQkFa7GIJmVzEwdt3cUHnj4sl9wZcuEoUnCq1UmnzgfJ0PS4l1P2JllRSreflXrEiL1aJKiokiimWX7AsHZmau',
 'policy.json': 'eNqr5lJQUErNS8/MS40vSy0qzszPU7JSUApwdA7SNdQzUNIByackVhbHF6QWxVemJhYBpY3NTMHiuYklqUWZiTnxyal5JcVACSNTAyAAy5Ul5pQmlgCNi08BqgKZaWRgZKprYAhESly1XAB1lyIi',
 'rebase_events.jsonl': 'eNqrVipKTUosTo3PTFGyUgpy0jU0MFTSUcpNzU1KLYII+rr6QkVT09JSk0syy1LjUxJLUoFSRgZGxroGhrpg2bTE5JL8ovikgmIlK0tzU4NarmpMw42wGm6Ew3ATrIYDHWNkisV0I6xON8LpdCNdA3NsppsaAN0OAEloUWI=',
 'salary_history.jsonl': 'eNqV0r0OgjAQB/Ddx+hsk95BQdggusnkA5AqHUygA8XBEN/dCooRSsGO/3780rtriRalqO/5tSAxOSVHCgwoMrIllazOsu43skP22jCpbkTdmAQZMmqOdqFURR/hEAmlbqLM369fpGo0iQPWrcemtbO4hsUp67vZEB0sUgQri78sTFmPstDBcu5mvTXs1xhYvlDk3SyL5iJEFhZHRYZo+ltws76btRZ5zNqKvNDbYL63abJfM0/e32Mcfsb4CQOu5VA=',
 'schema.md': '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',
 'service_revisions.jsonl': 'eNq91LEKwjAQBuDdx8hsITkLare2uqmDioiL1OSGgFZIaxfx3Y02CNpGU7FCpr/p8eW45EwU8qMSWylIQBZzj1EWki7JUBWSo4lX8S3XscJCZvKYkoB1zZ8otkmuNwEF36NMryWlwX1tboXyJD9l+nvCc1mgTg542KEqK0/HU1NZ71OmDC3L6BBTUUY9E1065xpw5AKGejC0A/bfgcHSYXDsMDQGwzNY1+hXwX07OHIBWzrsf9NhFzCjFjBYZhicZ7jXEAwvI8GGjUYiDmfxeOLVotctXbsKeVAhP05hJ0efyY0vHk9Sjvs9it+ro3BUBy7jvzxu/rvH7QrxyYrr'}
SCENARIOS=("revision_tie","overlapping_leave","missing_salary","same_day_order","salary_cap","election_day","multiple_elections","valuation_clip")
_EXPECTED_BUNDLES={'election_day': '5ec493388e4b55a8ce0f3a7edfc59c451e4d17e6212f3bb2367fbbba7b81397a',
 'missing_salary': '89bbef51672ae4ff2a95a2b89bf98b4ed4483bf5e7b3aa2f31be03ed6139ebf0',
 'multiple_elections': '86693799bc5040eab6249b1fd7f49467ed1e86369200e2a23521f4661147392d',
 'overlapping_leave': '65302aa4ca5516c73bbed93f601b076c5e05da806f81c6d5ad1ece68d9894929',
 'revision_tie': 'f7e2c0802adde2bca8b2c16df49fd489011f9d28594c512a3bfb90f54ae7d3c6',
 'salary_cap': '41b022e5d149d1fd17234480587682782aa8f3a71f7880c1688d33c94ab4351c',
 'same_day_order': 'd601f43da171fdf067b692b7df7bad08f980e764480f0744b76373dbda4aeb83',
 'valuation_clip': 'f6bfc0c1cb645aae5074e0fc12b50d32e63a1c587c782d9cfce79bdfe88d6831'}

def _hash(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def _read_rows(path:Path)->list[dict[str,Any]]:return [json.loads(x) for x in path.read_text().splitlines() if x]
def _write_rows(path:Path, values:list[dict[str,Any]])->None:path.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in values))
def _apply_scenario(data:Path,scenario:str)->None:
    services_path=data/"service_revisions.jsonl"; services=_read_rows(services_path)
    if scenario=="revision_tie":
        peer=dict(next(x for x in services if x["record_id"]=="SR-102B")); peer["record_id"]="SR-102Z"; peer["end"]="2024-11-01"; services.append(peer); _write_rows(services_path,services)
    elif scenario=="overlapping_leave":
        p=data/"leave_intervals.jsonl"; values=_read_rows(p); values.append({"leave_id":"LV-X","member_id":"MEM-101","start":"2021-03-01","end":"2021-06-01","credit_bps":2500}); _write_rows(p,values)
    elif scenario=="missing_salary":
        p=data/"salary_history.jsonl"; values=[x for x in _read_rows(p) if x["salary_id"]!="SAL-102-21"]; _write_rows(p,values)
    elif scenario=="same_day_order":
        p=data/"cola_rules.jsonl"; values=_read_rows(p); next(x for x in values if x["cola_id"]=="COLA-A-22")["factor_bps"]=15000; _write_rows(p,values)
    elif scenario=="salary_cap":
        p=data/"plans.json"; values=json.loads(p.read_text()); next(x for x in values if x["plan_id"]=="PLAN-A")["annual_cap_cents"]=6100000; p.write_text(json.dumps(values,indent=2,sort_keys=True)+"\n")
    elif scenario=="election_day":
        p=data/"elections.jsonl"; values=_read_rows(p); next(x for x in values if x["election_id"]=="EL-101")["retirement_date"]="2024-03-14"; _write_rows(p,values)
    elif scenario=="multiple_elections":
        p=data/"elections.jsonl"; values=_read_rows(p); values.append({"election_id":"EL-101-Z","member_id":"MEM-101","retirement_date":"2024-06-15","option_factor_bps":8400}); _write_rows(p,values)
    elif scenario=="valuation_clip":
        p=data/"policy.json"; value=json.loads(p.read_text()); value["valuation_date"]="2023-03-01"; p.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
    else:raise ValueError(scenario)

def _write_variant(root:Path,scenario:str)->Path:
    data=root/"data"; data.mkdir(parents=True,exist_ok=True)
    for name,blob in _PACKED.items():(data/name).write_bytes(zlib.decompress(base64.b64decode(blob)))
    _apply_scenario(data,scenario)
    for p in data.iterdir():p.chmod(0o644)
    data.chmod(0o755); return data

def _write_corpus(root:Path,fresh:bool=True)->Path:return _write_variant(root,"revision_tie" if fresh else "salary_cap")
def _root_only_tests()->bool:
    try:s=Path("/tests").stat()
    except FileNotFoundError:return False
    return s.st_uid==0 and s.st_mode&0o077==0
def _grant(text:str)->None:
    p=Path(text)
    if not text.startswith("/app") or not p.exists():return
    try:
        p.chmod(p.stat().st_mode|(0o555 if p.is_dir() else 0o444))
        for parent in p.parents:
            parent.chmod(parent.stat().st_mode|0o555)
            if parent==Path("/app"):break
    except OSError:pass
def _command(args:list[str])->list[str]:
    if os.name!="posix" and _root_only_tests():raise RuntimeError("POSIX isolation required")
    if os.name=="posix" and os.geteuid()!=0 and _root_only_tests():raise RuntimeError("root required for isolation")
    if os.name=="posix" and os.geteuid()==0:
        for arg in args:_grant(arg)
        return [*_SETPRIV,*args]
    return args
def _run(data:Path,out:Path)->None:
    out.parent.chmod(0o777); out.mkdir(mode=0o777)
    for name in REPORTS:(out/name).write_text('{"stale":true}\n');(out/name).chmod(0o666)
    proc=subprocess.Popen(_command([sys.executable,"-I","-S",str(SCRIPT),str(data),str(out)]),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"LANG":"C.UTF-8"})
    try:stdout,stderr=proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise AssertionError("submission timed out")
    assert proc.returncode==0,f"submission exited {proc.returncode}: {stdout[-400:]} {stderr[-400:]}"
_SCENARIO_ACTUAL:dict[str,Path]={};_SCENARIO_TEMPS:dict[str,tempfile.TemporaryDirectory[str]]={};_LOCK=threading.Lock()
def _scenario_out(scenario:str)->Path:
    with _LOCK:
        if scenario not in _SCENARIO_ACTUAL:
            temp=tempfile.TemporaryDirectory();_SCENARIO_TEMPS[scenario]=temp;parent=Path(temp.name);parent.chmod(0o777);data=_write_variant(parent,scenario);target=parent/"out";_run(data,target);_SCENARIO_ACTUAL[scenario]=target
        return _SCENARIO_ACTUAL[scenario]
def _holds(check:Callable[[],Any])->bool:
    try:check()
    except Exception:return False
    return True
def _bundle_hash(path:Path)->str:
    digest=hashlib.sha256()
    for name in REPORTS:digest.update(name.encode());digest.update(b"\0");digest.update((path/name).read_bytes())
    return digest.hexdigest()
def _artifacts()->None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size>0
    for name in REPORTS:assert isinstance(json.loads((OUT/name).read_text()),dict)
def _exact(scenario:str)->None:assert _bundle_hash(_scenario_out(scenario))==_EXPECTED_BUNDLES[scenario]
def _serialization()->None:
    for name in REPORTS:
        text=(OUT/name).read_text();assert text.endswith("\n");assert text==json.dumps(json.loads(text),indent=2,sort_keys=True)+"\n"
def _safe()->None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size>0
    text=SCRIPT.read_text(errors="replace");lower=text.lower();assert "/tests" not in lower and "rewardkit" not in lower and "judge.toml" not in lower
    forbidden={"requests","urllib","socket","pandas","numpy"}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node,ast.Import):assert not ({n.name.split('.')[0] for n in node.names}&forbidden)
        if isinstance(node,ast.ImportFrom):assert (node.module or "").split('.')[0] not in forbidden
def _determinism()->None:
    with tempfile.TemporaryDirectory() as td:
        parent=Path(td);parent.chmod(0o777);data=_write_variant(parent,"revision_tie");before={p.name:_hash(p) for p in data.iterdir()};a,b=parent/"a",parent/"b";_run(data,a);_run(data,b);assert before=={p.name:_hash(p) for p in data.iterdir()};assert {n:(a/n).read_bytes() for n in REPORTS}=={n:(b/n).read_bytes() for n in REPORTS}
def _source(markers:tuple[str,...],count:int=1)->None:
    text=SCRIPT.read_text(errors="replace");assert sum(x in text for x in markers)>=count
@criterion(description="The reusable program and all nine JSON reports exist and parse.")
def artifact_set(workspace:Path)->bool:return _holds(_artifacts)
@criterion(description="A fresh equal-rank service revision tie produces all nine exact reports.")
def scenario_revision_tie(workspace:Path)->bool:return _holds(lambda:_exact("revision_tie"))
@criterion(description="A fresh overlapping-leave minimum-factor case produces all nine exact reports.")
def scenario_overlapping_leave(workspace:Path)->bool:return _holds(lambda:_exact("overlapping_leave"))
@criterion(description="A fresh missing-salary quarantine case produces all nine exact reports.")
def scenario_missing_salary(workspace:Path)->bool:return _holds(lambda:_exact("missing_salary"))
@criterion(description="A fresh equal-date accrual-before-COLA-before-rebase case produces all nine exact reports.")
def scenario_same_day_order(workspace:Path)->bool:return _holds(lambda:_exact("same_day_order"))
@criterion(description="A fresh annual salary cap boundary case produces all nine exact reports.")
def scenario_salary_cap(workspace:Path)->bool:return _holds(lambda:_exact("salary_cap"))
@criterion(description="A fresh retirement age day-boundary case produces all nine exact reports.")
def scenario_election_day(workspace:Path)->bool:return _holds(lambda:_exact("election_day"))
@criterion(description="A fresh latest-election selection case produces all nine exact reports.")
def scenario_multiple_elections(workspace:Path)->bool:return _holds(lambda:_exact("multiple_elections"))
@criterion(description="A fresh valuation-date clipping case produces all nine exact reports.")
def scenario_valuation_clip(workspace:Path)->bool:return _holds(lambda:_exact("valuation_clip"))
@criterion(description="All JSON uses sorted-key two-space serialization with trailing newlines.")
def canonical_serialization(workspace:Path)->bool:return _holds(_serialization)
@criterion(description="The submission is nonempty, local, standard-library code that does not inspect graders.")
def local_safe_source(workspace:Path)->bool:return _holds(_safe)
@criterion(description="Fresh runs are deterministic and do not mutate inputs.")
def deterministic_no_mutation(workspace:Path)->bool:return _holds(_determinism)
@criterion(description="Detects hardcoded visible identifiers, values, or report digests.")
def negative_hardcoded_sample_answers(workspace:Path)->bool:return _holds(lambda:_source(("MEM-101","PLAN-A","9146205738","SVC-101"),3))
@criterion(description="Detects attempts to inspect verifier or reward files.")
def negative_reads_verifier(workspace:Path)->bool:return _holds(lambda:_source(("/tests","rewardkit","judge.toml","test_output")))
@criterion(description="Detects external dependencies, network access, or subprocess delegation.")
def negative_external_or_subprocess(workspace:Path)->bool:return _holds(lambda:_source(("requests","urllib","socket","pandas","numpy","subprocess")))
criteria.artifact_set(weight=1)
criteria.scenario_revision_tie(weight=5)
criteria.scenario_overlapping_leave(weight=5)
criteria.scenario_missing_salary(weight=5)
criteria.scenario_same_day_order(weight=5)
criteria.scenario_salary_cap(weight=5)
criteria.scenario_election_day(weight=5)
criteria.scenario_multiple_elections(weight=5)
criteria.scenario_valuation_clip(weight=5)
criteria.canonical_serialization(weight=3)
criteria.local_safe_source(weight=3)
criteria.deterministic_no_mutation(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_verifier(weight=-5)
criteria.negative_external_or_subprocess(weight=-3)
if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/pension-corpus")
    _write_corpus(target, True)
    print(target / "data")
