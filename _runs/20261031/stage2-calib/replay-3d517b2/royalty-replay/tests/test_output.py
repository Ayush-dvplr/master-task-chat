"""Behavioral verifier for the 75407a55-6665-505e-95d8-5ff9bdb3384f."""
# pyright: reportMissingImports=false
from __future__ import annotations
import ast,base64,hashlib,json,os,signal,subprocess,sys,tempfile,threading,zlib
from pathlib import Path
from typing import Any,Callable
from rewardkit import criteria,criterion
SAMPLE_SEED=5619038472
CHALLENGE_SEED=920417635
EVAL_SEED=184306792
OUT=Path("/app/out");SCRIPT=OUT/"calculate_royalties.py"
REPORTS=("manifest.json","data_quality.json","statement_ledger.json","waterfall_ledger.json","recoupment_ledger.json","participant_statements.json","project_rollups.json","exception_register.json","audit_trace.json")
_SETPRIV=["setpriv","--reuid=nobody","--regid=nogroup","--clear-groups"]
_BLOB="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"
SCENARIOS=("revision_tie","fx_half_up","withholding_half_up","pool_priority","largest_remainder","advance_priority","period_carry","signed_adjustment")
_EXPECTED={"revision_tie":"d57484313b301903d01573e30839bf0b365ad69ad0a6f46270db25a2efb103b4","fx_half_up":"f4ee0900e009d559db01cbe7b3c1ff75113f8bf70d82eb188b12f43faea79e04","withholding_half_up":"12f45ec42971b4cbf54a9c83c7bdf9628a5a83d5179a91b49d2a1380958bb8f3","pool_priority":"e92f219944d6677ef7e9f9611c4d3f6260fe5f230d305528def7c66ca1343c17","largest_remainder":"00c00fc388f65d15370eb1b9206938214d764e7e2402f3eb465e5fee5629214b","advance_priority":"0486961eb3c1d65785893c6ae0dccaa3ea16b0c98f11480de89e4d5fc9889916","period_carry":"7110727db340dcfdc025ef7f974f3f0865da7c06b1e8dce5f28e7f66f3323fb3","signed_adjustment":"29c3decc107d4921c3297d9151ff2beffceaf7442792b6d68ddead85f85e533c"}
def _rows(p:Path)->list[dict[str,Any]]:return [json.loads(x) for x in p.read_text().splitlines() if x]
def _write_rows(p:Path,v:list[dict[str,Any]])->None:p.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in v))
def _apply(d:Path,s:str)->None:
    if s=="revision_tie":
        p=d/"statement_revisions.jsonl";v=_rows(p);x=dict(next(r for r in v if r["record_id"]=="ST-3A"));x["record_id"]="ST-3Z";x["amount_minor"]=9600001;v.append(x);_write_rows(p,v)
    elif s=="fx_half_up":
        p=d/"statement_revisions.jsonl";v=_rows(p);next(r for r in v if r["record_id"]=="ST-2A")["amount_minor"]=1;_write_rows(p,v);p=d/"fx_rates.jsonl";v=_rows(p);x=next(r for r in v if r["currency"]=="GBP");x["numerator"]=1;x["denominator"]=2;_write_rows(p,v)
    elif s=="withholding_half_up":
        p=d/"statement_revisions.jsonl";v=_rows(p);next(r for r in v if r["record_id"]=="ST-1B")["amount_minor"]=10001;_write_rows(p,v);p=d/"withholding_rules.jsonl";v=_rows(p);next(r for r in v if r["territory"]=="US")["withholding_bps"]=5000;_write_rows(p,v)
    elif s=="pool_priority":
        p=d/"cost_pools.jsonl";v=_rows(p);next(r for r in v if r["pool_id"]=="POOL-A-MKT")["opening_cents"]=1000000;next(r for r in v if r["pool_id"]=="POOL-A-PROD")["opening_cents"]=20000000;_write_rows(p,v)
    elif s=="largest_remainder":
        p=d/"allocations.jsonl";v=[r for r in _rows(p) if r["project_id"]!="PROJ-B"]+[{
        "allocation_id":"AL-B-X","project_id":"PROJ-B","participant_id":"ALPHA-B","share_bps":3333},{"allocation_id":"AL-B-Y","project_id":"PROJ-B","participant_id":"BETA-B","share_bps":3333},{"allocation_id":"AL-B-Z","project_id":"PROJ-B","participant_id":"GAMMA-B","share_bps":3334}];_write_rows(p,v)
        for name in ("advances.jsonl","adjustments.jsonl"):
            p=d/name;_write_rows(p,[r for r in _rows(p) if r["project_id"]!="PROJ-B"])
    elif s=="advance_priority":
        p=d/"advances.jsonl";v=_rows(p);next(r for r in v if r["advance_id"]=="ADV-A-1")["opening_cents"]=250000;v.append({"advance_id":"ADV-A-Z","project_id":"PROJ-A","participant_id":"ARTIST-A","priority":2,"opening_cents":700000});_write_rows(p,v)
    elif s=="period_carry":
        p=d/"statement_revisions.jsonl";v=_rows(p);next(r for r in v if r["record_id"]=="ST-1B")["amount_minor"]=1000000;next(r for r in v if r["record_id"]=="ST-2A")["amount_minor"]=0;_write_rows(p,v)
    elif s=="signed_adjustment":
        p=d/"adjustments.jsonl";v=_rows(p);next(r for r in v if r["adjustment_id"]=="ADJ-1")["amount_cents"]=-975001;_write_rows(p,v)
    else:raise ValueError(s)
def _variant(root:Path,s:str)->Path:
    d=root/"data";d.mkdir(parents=True);packed=json.loads(zlib.decompress(base64.b64decode(_BLOB)))
    for name,text in packed.items():(d/name).write_text(text)
    _apply(d,s)
    for p in d.iterdir():p.chmod(0o644)
    d.chmod(0o755);return d
def _write_corpus(root:Path,fresh:bool=True)->Path:return _variant(root,"revision_tie" if fresh else "pool_priority")
def _grant(x:str)->None:
    p=Path(x)
    if not x.startswith("/app") or not p.exists():return
    try:
        p.chmod(p.stat().st_mode|(0o555 if p.is_dir() else 0o444))
        for parent in p.parents:
            parent.chmod(parent.stat().st_mode|0o555)
            if parent==Path("/app"):break
    except OSError:pass
def _command(args:list[str])->list[str]:
    if os.name=="posix" and os.geteuid()==0:
        for x in args:_grant(x)
        return [*_SETPRIV,*args]
    return args
def _run(data:Path,out:Path)->None:
    out.parent.chmod(0o777);out.mkdir(mode=0o777)
    for n in REPORTS:(out/n).write_text('{"stale":true}\n');(out/n).chmod(0o666)
    p=subprocess.Popen(_command([sys.executable,"-I","-S",str(SCRIPT),str(data),str(out)]),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"LANG":"C.UTF-8"})
    try:stdout,stderr=p.communicate(timeout=120)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait();raise AssertionError("timeout")
    assert p.returncode==0,f"exit {p.returncode}: {stdout[-300:]} {stderr[-300:]}"
_ACTUAL:dict[str,Path]={};_TEMPS:dict[str,tempfile.TemporaryDirectory[str]]={};_LOCK=threading.Lock()
def _out(s:str)->Path:
    with _LOCK:
        if s not in _ACTUAL:
            t=tempfile.TemporaryDirectory();_TEMPS[s]=t;r=Path(t.name);r.chmod(0o777);d=_variant(r,s);o=r/"out";_run(d,o);_ACTUAL[s]=o
        return _ACTUAL[s]
def _bundle(p:Path)->str:
    h=hashlib.sha256()
    for n in REPORTS:h.update(n.encode());h.update(b"\0");h.update((p/n).read_bytes())
    return h.hexdigest()
def _holds(f:Callable[[],Any])->bool:
    try:f()
    except Exception:return False
    return True
def _artifacts()->None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size>0
    for n in REPORTS:assert isinstance(json.loads((OUT/n).read_text()),dict)
def _exact(s:str)->None:assert _bundle(_out(s))==_EXPECTED[s]
def _serialization()->None:
    for n in REPORTS:
        text=(OUT/n).read_text();assert text==json.dumps(json.loads(text),indent=2,sort_keys=True)+"\n"
def _safe()->None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size>0;text=SCRIPT.read_text(errors="replace");low=text.lower();assert "/tests" not in low and "rewardkit" not in low
    forbidden={"requests","urllib","socket","pandas","numpy"}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node,ast.Import):assert not ({x.name.split('.')[0] for x in node.names}&forbidden)
        if isinstance(node,ast.ImportFrom):assert (node.module or "").split('.')[0] not in forbidden
def _determinism()->None:
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);r.chmod(0o777);d=_variant(r,"revision_tie");before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()};a,b=r/"a",r/"b";_run(d,a);_run(d,b);assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()};assert {n:(a/n).read_bytes() for n in REPORTS}=={n:(b/n).read_bytes() for n in REPORTS}
def _source(markers:tuple[str,...],count:int=1)->None:assert sum(x in SCRIPT.read_text(errors="replace") for x in markers)>=count
@criterion(description="The reusable program and all nine JSON reports exist and parse.")
def artifact_set(workspace:Path)->bool:return _holds(_artifacts)
@criterion(description="A fresh equal-rank statement conflict produces all nine exact reports.")
def scenario_revision_tie(workspace:Path)->bool:return _holds(lambda:_exact("revision_tie"))
@criterion(description="A fresh FX half-up midpoint produces all nine exact reports.")
def scenario_fx_half_up(workspace:Path)->bool:return _holds(lambda:_exact("fx_half_up"))
@criterion(description="A fresh withholding half-up midpoint produces all nine exact reports.")
def scenario_withholding_half_up(workspace:Path)->bool:return _holds(lambda:_exact("withholding_half_up"))
@criterion(description="A fresh chronological project-pool priority case produces all nine exact reports.")
def scenario_pool_priority(workspace:Path)->bool:return _holds(lambda:_exact("pool_priority"))
@criterion(description="A fresh largest-remainder participant split produces all nine exact reports.")
def scenario_largest_remainder(workspace:Path)->bool:return _holds(lambda:_exact("largest_remainder"))
@criterion(description="A fresh multi-advance priority case produces all nine exact reports.")
def scenario_advance_priority(workspace:Path)->bool:return _holds(lambda:_exact("advance_priority"))
@criterion(description="A fresh cross-period project-pool carry case produces all nine exact reports.")
def scenario_period_carry(workspace:Path)->bool:return _holds(lambda:_exact("period_carry"))
@criterion(description="A fresh signed participant adjustment case produces all nine exact reports.")
def scenario_signed_adjustment(workspace:Path)->bool:return _holds(lambda:_exact("signed_adjustment"))
@criterion(description="All JSON uses sorted-key two-space serialization with trailing newlines.")
def canonical_serialization(workspace:Path)->bool:return _holds(_serialization)
@criterion(description="The submission is nonempty, local, standard-library code that does not inspect graders.")
def local_safe_source(workspace:Path)->bool:return _holds(_safe)
@criterion(description="Fresh runs are deterministic and do not mutate inputs.")
def deterministic_no_mutation(workspace:Path)->bool:return _holds(_determinism)
@criterion(description="Detects hardcoded visible identifiers, values, or report digests.")
def negative_hardcoded_sample_answers(workspace:Path)->bool:return _holds(lambda:_source(("PROJ-A","ST-1B","ARTIST-A","5619038472"),3))
@criterion(description="Detects attempts to inspect verifier or reward files.")
def negative_reads_verifier(workspace:Path)->bool:return _holds(lambda:_source(("/tests","rewardkit","judge.toml","test_output")))
@criterion(description="Detects external dependencies, network access, or subprocess delegation.")
def negative_external_or_subprocess(workspace:Path)->bool:return _holds(lambda:_source(("requests","urllib","socket","pandas","numpy","subprocess")))
criteria.artifact_set(weight=1)
criteria.scenario_revision_tie(weight=5);criteria.scenario_fx_half_up(weight=5);criteria.scenario_withholding_half_up(weight=5);criteria.scenario_pool_priority(weight=5)
criteria.scenario_largest_remainder(weight=5);criteria.scenario_advance_priority(weight=5);criteria.scenario_period_carry(weight=5);criteria.scenario_signed_adjustment(weight=5)
criteria.canonical_serialization(weight=3);criteria.local_safe_source(weight=3);criteria.deterministic_no_mutation(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5);criteria.negative_reads_verifier(weight=-5);criteria.negative_external_or_subprocess(weight=-3)
if __name__=="__main__":
    target=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/royalty-corpus");_write_corpus(target,True);print(target/"data")
