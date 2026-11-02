import re,sys
L=open(sys.argv[1],encoding='utf-8',errors='replace').read().split('\n')
acts=[i for i,l in enumerate(L) if l.startswith('Agent Action')]
acts.append(len(L))
for k in range(len(acts)-1):
    a,b=acts[k],acts[k+1]
    seg=L[a:b]
    summ=next((l[9:] for l in seg if l.startswith('Summary:')),'')
    cmd=''
    for j,l in enumerate(seg):
        if l.startswith('$ '): cmd=l[2:]; break
        if l.strip().startswith('path:'): cmd='EDIT '+' '.join(x.strip() for x in seg[j-1:j+1])
    tok=next((l for l in seg if l.startswith('Tokens:')),'')
    m=re.search(r'\$ \(total ([\d.]+)',' '.join(seg[seg.index(tok):seg.index(tok)+3]) if tok else '')
    ts=[re.findall(r'(?:Nov  1|11/01/26) (\d\d:\d\d(?::\d\d)?)',l) for l in seg]
    ts=sorted(set(t for x in ts for t in x))
    ec=next((l for l in seg if 'Exit code' in l),'')
    print(f"{k+1:2d} L{a+1:5d}-{b:5d} ${m.group(1) if m else '?':>7} ts={ts[-3:] if ts else ''} {ec[-8:]} | {summ[:70]} | {cmd[:150]}")
