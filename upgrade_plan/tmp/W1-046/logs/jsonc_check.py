import json,re,sys
def strip(t):
    out=[];i=0;ins=False
    while i<len(t):
        c=t[i]
        if ins:
            out.append(c)
            if c=='\\': out.append(t[i+1]); i+=2; continue
            if c=='"': ins=False
            i+=1; continue
        if c=='"': ins=True; out.append(c); i+=1; continue
        if t.startswith('//',i):
            j=t.find('\n',i); i=len(t) if j<0 else j; continue
        if t.startswith('/*',i):
            j=t.find('*/',i); i=j+2; continue
        out.append(c); i+=1
    return ''.join(out)
data=json.loads(strip(open(sys.argv[1]).read()))
schema=json.load(open(sys.argv[2]))
def resolve(s):
    while isinstance(s,dict) and '$ref' in s:
        ref=s['$ref'].lstrip('#/').split('/'); x=schema
        for r in ref: x=x[r]
        s=x
    return s
def walk(d,s,path):
    s=resolve(s)
    if not isinstance(d,dict): 
        t=s.get('type') if isinstance(s,dict) else None
        print('  ',path,'=',json.dumps(d),'type',t, 'enum',s.get('enum') if isinstance(s,dict) else None); return
    props=s.get('properties',{})
    for k,v in d.items():
        if k not in props:
            print('MISSING KEY',path+'.'+k, 'additionalProperties', s.get('additionalProperties')); continue
        walk(v,props[k],path+'.'+k)
walk(data,schema,'')
print('parsed ok')
