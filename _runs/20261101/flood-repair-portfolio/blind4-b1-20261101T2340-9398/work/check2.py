import sys
sys.path.insert(0,'app'); import derive_report as d
orig=d.solve_portfolio
def feas(n,adj,cm,co,m):
    for i in range(n):
        if m>>i&1 and adj[i]&m: return False
    return all(bin(c&m).count('1')<=d.SHARED_CAP for c in cm)
def brute(n,W,adj,cm,co):
    # simple exact search: include/exclude in index order with feasibility
    best=[-1,0]
    def rec(i,m,w):
        if i==n:
            if w>best[0]: best[:]=[w,m]
            return
        rec(i+1,m,w)
        if not adj[i]&m:
            j=co[i]
            if j<0 or bin(cm[j]&m).count('1')<d.SHARED_CAP: rec(i+1,m|1<<i,w+W[i])
    rec(0,0,0); return best[1]
def cmp(n,W,adj,cm,co):
    o,b,wd=d.elimination_order(n,adj,cm)
    r1=d.solve_dp(n,W,adj,cm,co,o,b)
    if n<=40:
        s=d.DP_MAX_WIDTH; d.DP_MAX_WIDTH=-1; r2=orig(n,W,adj,cm,co); d.DP_MAX_WIDTH=s
        if r1!=r2:
            w=lambda m: sum(W[i] for i in range(n) if m>>i&1)
            r3=brute(n,W,adj,cm,co) if n<=26 else None
            print('n',n,'crews',len(cm),'dp feas',feas(n,adj,cm,co,r1),'bnb feas',feas(n,adj,cm,co,r2),'dp>bnb',w(r1)>w(r2),'brute==dp',r3==r1 if r3 is not None else '-', 'brute==bnb', r3==r2 if r3 is not None else '-', 'dbenefit',(w(r1)>>n)-(w(r2)>>n))
    return r1
d.solve_portfolio=cmp
sys.argv=['x','environment/data','work/probe_out']; d.main()
