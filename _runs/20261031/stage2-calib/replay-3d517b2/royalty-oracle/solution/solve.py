#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

REPORTS=("manifest.json","data_quality.json","statement_ledger.json","waterfall_ledger.json","recoupment_ledger.json","participant_statements.json","project_rollups.json","exception_register.json","audit_trace.json")

def rows(path:Path)->list[dict[str,Any]]:return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def stamp(value:str)->datetime:return datetime.fromisoformat(value.replace("Z","+00:00"))
def rounded(value:Decimal)->int:return int(value.quantize(Decimal("1"),rounding=ROUND_HALF_UP))
def canonical(value:Any)->str:return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def write(path:Path,value:Any)->None:path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=True)+"\n")

def main(data:Path,out:Path)->None:
    out.mkdir(parents=True,exist_ok=True)
    policy=json.loads((data/"policy.json").read_text()); periods=list(policy["periods"]); period_rank={p:i for i,p in enumerate(periods)}
    contracts={x["project_id"]:x for x in json.loads((data/"contracts.json").read_text())}
    raw_statements=rows(data/"statement_revisions.jsonl");raw_pools=rows(data/"cost_pools.jsonl");raw_allocations=rows(data/"allocations.jsonl")
    raw_advances=rows(data/"advances.jsonl");raw_withholding=rows(data/"withholding_rules.jsonl");raw_adjustments=rows(data/"adjustments.jsonl");raw_fx=rows(data/"fx_rates.jsonl")
    issues:list[dict[str,Any]]=[]
    fx={}; territories={}
    for r in raw_fx:
        try:valid=r["currency"] not in fx and int(r["numerator"])>0 and int(r["denominator"])>0
        except (KeyError,TypeError,ValueError):valid=False
        if valid:fx[r["currency"]]=r
        else:issues.append({"code":"INVALID_FX","record_id":r.get("rate_id","?")})
    for r in raw_withholding:
        try:valid=r["territory"] not in territories and 0<=int(r["withholding_bps"])<=10000
        except (KeyError,TypeError,ValueError):valid=False
        if valid:territories[r["territory"]]=r
        else:issues.append({"code":"INVALID_WITHHOLDING","record_id":r.get("rule_id","?")})

    grouped:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for r in raw_statements:grouped[r["statement_id"]].append(r)
    decisions=[];winners=[]
    for sid in sorted(grouped):
        ordered=sorted(grouped[sid],key=lambda r:(int(r["revision"]),stamp(r["recorded_at"]),r["record_id"]));winner=ordered[-1]
        peers=[r for r in ordered if int(r["revision"])==int(winner["revision"]) and r["recorded_at"]==winner["recorded_at"]]
        if len({canonical({k:v for k,v in r.items() if k!="record_id"}) for r in peers})>1:issues.append({"code":"REVISION_TIE_CONFLICT","record_id":sid})
        decisions.append({"statement_id":sid,"winner_record_id":winner["record_id"],"discarded_record_ids":sorted(r["record_id"] for r in ordered if r is not winner)})
        if winner["status"]=="active":winners.append(winner)
    effective=[]
    for r in winners:
        try:valid=r["project_id"] in contracts and r["period"] in period_rank and r["territory"] in territories and r["currency"] in fx and int(r["amount_minor"])>=0
        except (KeyError,TypeError,ValueError):valid=False
        if not valid:issues.append({"code":"INVALID_STATEMENT","record_id":r.get("statement_id","?")});continue
        rate=fx[r["currency"]];gross=rounded(Decimal(int(r["amount_minor"])*int(rate["numerator"]))/Decimal(int(rate["denominator"])))
        wh=rounded(Decimal(gross*int(territories[r["territory"]]["withholding_bps"]))/Decimal(10000));base=gross-wh
        fee=rounded(Decimal(base*int(contracts[r["project_id"]]["distributor_fee_bps"]))/Decimal(10000))
        effective.append({"statement_id":r["statement_id"],"project_id":r["project_id"],"period":r["period"],"territory":r["territory"],"currency":r["currency"],"amount_minor":int(r["amount_minor"]),"gross_cents":gross,"withholding_cents":wh,"distributor_fee_cents":fee,"net_receipts_cents":gross-wh-fee})
    effective.sort(key=lambda r:(r["project_id"],period_rank[r["period"]],r["statement_id"]))

    pools=[];pool_priorities:set[tuple[str,int]]=set()
    for r in raw_pools:
        pool_key:tuple[str,int]=(str(r.get("project_id","")),int(r.get("priority",0)))
        try:valid=r["project_id"] in contracts and int(r["priority"])>0 and int(r["opening_cents"])>=0 and pool_key not in pool_priorities
        except (KeyError,TypeError,ValueError):valid=False
        if valid:pools.append(r);pool_priorities.add(pool_key)
        else:issues.append({"code":"INVALID_POOL","record_id":r.get("pool_id","?")})
    allocations=[]
    for r in raw_allocations:
        try:valid=r["project_id"] in contracts and 0<=int(r["share_bps"])<=10000
        except (KeyError,TypeError,ValueError):valid=False
        if valid:allocations.append(r)
        else:issues.append({"code":"INVALID_ALLOCATION","record_id":r.get("allocation_id","?")})
    alloc_by_project:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for r in allocations:alloc_by_project[r["project_id"]].append(r)
    invalid_projects=set()
    for pid in contracts:
        if sum(int(r["share_bps"]) for r in alloc_by_project[pid])!=10000:
            issues.append({"code":"INVALID_ALLOCATION_TOTAL","record_id":pid});invalid_projects.add(pid)
    valid_participants={(r["project_id"],r["participant_id"]) for r in allocations}
    advances=[];advance_priorities:set[tuple[str,str,int]]=set()
    for r in raw_advances:
        advance_key:tuple[str,str,int]=(str(r.get("project_id","")),str(r.get("participant_id","")),int(r.get("priority",0)))
        try:valid=(r["project_id"],r["participant_id"]) in valid_participants and int(r["priority"])>0 and int(r["opening_cents"])>=0 and advance_key not in advance_priorities
        except (KeyError,TypeError,ValueError):valid=False
        if valid:advances.append(r);advance_priorities.add(advance_key)
        else:issues.append({"code":"INVALID_ADVANCE","record_id":r.get("advance_id","?")})
    adjustments=[]
    for r in raw_adjustments:
        try:valid=(r["project_id"],r["participant_id"]) in valid_participants and r["period"] in period_rank and isinstance(int(r["amount_cents"]),int)
        except (KeyError,TypeError,ValueError):valid=False
        if valid:adjustments.append(r)
        else:issues.append({"code":"INVALID_ADJUSTMENT","record_id":r.get("adjustment_id","?")})
    adj:dict[tuple[str,str,str],int]=defaultdict(int)
    for r in adjustments:adj[(r["project_id"],r["period"],r["participant_id"])]+=int(r["amount_cents"])

    statement_groups:dict[tuple[str,str],list[dict[str,Any]]]=defaultdict(list)
    for r in effective:statement_groups[(r["project_id"],r["period"])].append(r)
    pool_groups:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for r in pools:pool_groups[r["project_id"]].append(r)
    advance_groups:dict[tuple[str,str],list[dict[str,Any]]]=defaultdict(list)
    for r in advances:advance_groups[(r["project_id"],r["participant_id"])].append(r)
    pool_balance={r["pool_id"]:int(r["opening_cents"]) for r in pools};advance_balance={r["advance_id"]:int(r["opening_cents"]) for r in advances}
    waterfall=[];pool_rows=[];advance_rows=[];participant_rows=[]
    for pid in sorted(contracts):
        for period in periods:
            ss=statement_groups[(pid,period)] if pid not in invalid_projects else []
            gross=sum(r["gross_cents"] for r in ss);wh=sum(r["withholding_cents"] for r in ss);fee=sum(r["distributor_fee_cents"] for r in ss);net=sum(r["net_receipts_cents"] for r in ss)
            remaining=net;pool_recouped=0
            for pool in sorted(pool_groups[pid],key=lambda r:(int(r["priority"]),r["pool_id"])):
                opening=pool_balance[pool["pool_id"]];taken=min(opening,remaining);remaining-=taken;pool_recouped+=taken;pool_balance[pool["pool_id"]]=opening-taken
                pool_rows.append({"project_id":pid,"period":period,"pool_id":pool["pool_id"],"priority":int(pool["priority"]),"opening_balance_cents":opening,"recouped_cents":taken,"closing_balance_cents":opening-taken})
            waterfall.append({"project_id":pid,"period":period,"gross_cents":gross,"withholding_cents":wh,"distributor_fee_cents":fee,"net_receipts_cents":net,"pool_recouped_cents":pool_recouped,"distributable_cents":remaining})
            allocs=sorted(alloc_by_project[pid],key=lambda r:r["participant_id"]);floors={};fractions=[]
            for a in allocs:
                numerator=remaining*int(a["share_bps"]);floors[a["participant_id"]]=numerator//10000;fractions.append((numerator%10000,a["participant_id"]))
            for _,participant in sorted(fractions,key=lambda x:(-x[0],x[1]))[:remaining-sum(floors.values())]:floors[participant]+=1
            for a in allocs:
                participant=a["participant_id"];share=floors[participant];left=share;recouped=0
                for advance in sorted(advance_groups[(pid,participant)],key=lambda r:(int(r["priority"]),r["advance_id"])):
                    opening=advance_balance[advance["advance_id"]];taken=min(opening,left);left-=taken;recouped+=taken;advance_balance[advance["advance_id"]]=opening-taken
                    advance_rows.append({"project_id":pid,"period":period,"participant_id":participant,"advance_id":advance["advance_id"],"priority":int(advance["priority"]),"opening_balance_cents":opening,"recouped_cents":taken,"closing_balance_cents":opening-taken})
                adjustment=adj[(pid,period,participant)]
                participant_rows.append({"project_id":pid,"period":period,"participant_id":participant,"share_bps":int(a["share_bps"]),"gross_share_cents":share,"advance_recouped_cents":recouped,"payable_before_adjustment_cents":left,"adjustment_cents":adjustment,"payable_cents":left+adjustment})
    issues.sort(key=lambda r:(r["code"],r["record_id"]));exceptions:list[dict[str,Any]]=list(issues)
    for r in participant_rows:
        if abs(r["payable_cents"])>=int(policy["material_cents"]):exceptions.append({"code":"MATERIAL_PAYMENT","record_id":f'{r["project_id"]}:{r["period"]}:{r["participant_id"]}',"amount_cents":r["payable_cents"]})
    exceptions.sort(key=lambda r:(r["code"],r["record_id"]))
    rollups=[]
    for pid in sorted(contracts):
        ws=[r for r in waterfall if r["project_id"]==pid];ps=[r for r in participant_rows if r["project_id"]==pid]
        rollups.append({"project_id":pid,"gross_cents":sum(r["gross_cents"] for r in ws),"withholding_cents":sum(r["withholding_cents"] for r in ws),"distributor_fee_cents":sum(r["distributor_fee_cents"] for r in ws),"net_receipts_cents":sum(r["net_receipts_cents"] for r in ws),"pool_recouped_cents":sum(r["pool_recouped_cents"] for r in ws),"distributable_cents":sum(r["distributable_cents"] for r in ws),"advance_recouped_cents":sum(r["advance_recouped_cents"] for r in ps),"adjustment_cents":sum(r["adjustment_cents"] for r in ps),"payable_cents":sum(r["payable_cents"] for r in ps)})
    audit=[];previous="0"*64
    for r in participant_rows:
        h=hashlib.sha256((previous+canonical(r)).encode()).hexdigest();audit.append({"project_id":r["project_id"],"period":r["period"],"participant_id":r["participant_id"],"previous_hash":previous,"row_hash":h});previous=h
    input_files=[{"name":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size} for p in sorted(data.iterdir()) if p.is_file()]
    counts={"statement_revisions":len(raw_statements),"cost_pools":len(raw_pools),"allocations":len(raw_allocations),"advances":len(raw_advances),"withholding_rules":len(raw_withholding),"adjustments":len(raw_adjustments),"fx_rates":len(raw_fx)}
    reports={"manifest.json":{"engine_version":policy["engine_version"],"input_files":input_files,"effective_statement_count":len(effective),"waterfall_period_count":len(waterfall),"participant_statement_count":len(participant_rows)},"data_quality.json":{"input_file_count":len(input_files),"record_counts":counts,"issue_count":len(issues),"issues":issues},"statement_ledger.json":{"revision_decisions":decisions,"effective_statements":effective},"waterfall_ledger.json":{"periods":waterfall},"recoupment_ledger.json":{"project_pools":pool_rows,"participant_advances":advance_rows},"participant_statements.json":{"statements":participant_rows},"project_rollups.json":{"projects":rollups},"exception_register.json":{"exceptions":exceptions},"audit_trace.json":{"rows":audit,"final_hash":previous}}
    for name,value in reports.items():write(out/name,value)

if __name__=="__main__":
    if len(sys.argv)!=3:print("usage: calculate_royalties.py DATA_DIR OUT_DIR",file=sys.stderr);raise SystemExit(2)
    main(Path(sys.argv[1]),Path(sys.argv[2]))
