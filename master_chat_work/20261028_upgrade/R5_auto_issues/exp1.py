import importlib.util,sys
from datetime import datetime
spec=importlib.util.spec_from_file_location('a','/tmp/R5-auto-1/auto_copy.py'); a=importlib.util.module_from_spec(spec); sys.modules['a']=a; spec.loader.exec_module(a)
n=datetime.fromisoformat('2026-10-28T17:54:49+05:30')
r='subscription usage limit reached during cold-chain-backbone-quote (requeued at the front). Resume once the limit resets.'
print('reason ->',a.parse_reset(r,n,60))
print('litellm ->',a.parse_reset('all 1 accounts exhausted; soonest reset in 4698s',n,60))
print('LIMIT_RE matches reason:',bool(a.LIMIT_RE.search(r)))
s=datetime.fromisoformat('2026-10-27T01:07:01+05:30')
print('next_occurrence 01:07 after 01:07:01 ->',a.next_occurrence('01:07',s))
print('classify doom:',a.classify({'name':'UnknownError','data':{'message':'The user has specified a rule which prevents you from using this specific tool call'}}))
print('classify rate:',a.classify({'name':'APIError','data':{'message':"This request would exceed your account's rate limit"}}))
# worker_down flag never cleared: simulate watch_once health branch
calls=iter([False,True,True,False])
a.healthy=lambda u: next(calls) if 'w' in u else True
st={'worker_url':'http://w','worker_down_reported':False}
ev=[]
for i in range(4):
    ok=a.healthy(st['worker_url'])
    if not ok and not st.get('worker_down_reported'):
        st['worker_down_reported']=True; ev.append(f'poll{i}: ERROR down')
print('replayed watch_once:1390-1397 with health F,T,T,F ->',ev,'(second outage at poll3 NOT reported)')
