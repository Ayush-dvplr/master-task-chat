import json,sys
t=json.load(open("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/traj_a4/job/trajectory/claude-opus-5/Run 1/agent/trajectory.json"))
steps=t['steps']
i=int(sys.argv[1]); a=int(sys.argv[2]) if len(sys.argv)>2 else 0; b=int(sys.argv[3]) if len(sys.argv)>3 else 4000
s=steps[i]
print("step_id",s.get('step_id'),s.get('timestamp'),s.get('source'))
if s.get('message'): print("MSG:",s['message'][a:b])
for tc in s.get('tool_calls') or []:
    print("CALL:",json.dumps(tc.get('arguments'))[a:b])
obs=s.get('observation')
if obs:
    for r in obs.get('results',[]):
        c=r.get('content')
        if isinstance(c,list): c=" ".join(x.get('text','') for x in c if isinstance(x,dict))
        print("OBS:",str(c)[a:b])
