import json
for g in json.load(open('work/diag/graphs.json')):
    n=g['n']; adj=[set(i for i in range(n) if a>>i&1) for a in g['adj']]
    # min-degree / min-fill elimination width
    for mode in ('deg','fill'):
        A=[set(s) for s in adj]; alive=set(range(n)); width=0
        while alive:
            if mode=='deg': v=min(alive,key=lambda x:len(A[x]))
            else:
                def fill(x):
                    nb=list(A[x]); return sum(1 for i in range(len(nb)) for j in range(i+1,len(nb)) if nb[j] not in A[nb[i]])
                v=min(alive,key=fill)
            nb=A[v]; width=max(width,len(nb))
            for a in nb:
                A[a]|=nb; A[a].discard(a); A[a].discard(v)
            alive.discard(v)
        print(n,mode,'treewidth<=',width)
    # bandwidth of identity order
    print('identity bandwidth', max(abs(i-j) for i in range(n) for j in adj[i]))
