import csv,json,pathlib,collections
OUT=pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_test_design_study')
rows=list(csv.DictReader((OUT/'inventory.csv').open())); by={r['id8']:r for r in rows}
sel=json.loads((OUT/'scratch/selection.json').read_text())
patterns={
'P1_heldout_exact':['59417607','8eae0f87','3f39299a','18b5d99f','98ed74c1','f348165e','a710b00e'],
'P2_carrier_variation':['6285fcad','1d61e794','9d1784a5','ceadc676','37a0c3d6','b42c61b9','5048c412'],
'P3_induction_state':['05550e00','28a29cf0','8defd7be','6d12f970','aa314fee','275f885b'],
'P4_authority_decoy':['80202e15','9f5486ac'],
'P5_scale_runtime':['fabbe645'],
'P6_large_system_repair':['9cc598a9','f2d019d0'],
}
assert set(sum(patterns.values(),[]))==set(sel['selected'])
summary={}
for name,ids in patterns.items():
 loss=sum(float(by[x]['lost_pct']) for x in ids)
 summary[name]={'tasks':ids,'task_count':len(ids),'test_points_lost_sum':round(loss,2),'mean_test_points_lost':round(loss/len(ids),2),'raw_positive_weight_lost':round(sum(float(by[x]['lost_positive_weight']) for x in ids),2)}
authors=sorted({a.strip() for x in sel['selected'] for a in by[x]['author'].split(';')})
contrast=[]
for author in authors:
 easy=sorted((r for r in rows if r['band']=='Easy' and author in [a.strip() for a in r['author'].split(';')]),key=lambda r:float(r['lost_pct']))
 contrast.append({'author':author,'easy_id':easy[0]['id8'] if easy else None,'easy_test_loss_pct':float(easy[0]['lost_pct']) if easy else None,'easy_test_pass_pct':round(100-float(easy[0]['lost_pct']),2) if easy else None,'easy_final':float(easy[0]['final_score']) if easy else None})
metrics={'selected':len(sel['selected']),'omitted':len(sel['omitted']),'changed_qualifying':len(sel['new']),'hard_expert_qualifying':len(sel['hard_expert']),'patterns':summary,'easy_contrasts':contrast,'stdout_reward_only':sum(int(by[x]['stdout_bytes'])<=20 for x in sel['selected']),'verified_timeout_task_ids':[x for x in sel['selected'] if __import__('re').search(r'timed out|timeoutexpired|timeout',next(pathlib.Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2').glob(x+'-*/trajectories/claude-opus-5/run_1/verifier/test-stdout.txt')).read_text(errors='replace'),__import__('re').I)],'verified_majority_documented_misread_on_shipped_like_ids':[]}
(OUT/'scratch/metrics.json').write_text(json.dumps(metrics,indent=2))
print(json.dumps(metrics,indent=2))
