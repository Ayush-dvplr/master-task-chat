import sys
sys.path.insert(0,'app'); import derive_report as d
exec(open('work/check2.py').read().split('def cmp')[0].split('orig=d.solve_portfolio')[1])
st=[0,0,0]
def cmp(n,W,adj,cm,co):
    o,b,wd=d.elimination_order(n,adj,cm); r1=d.solve_dp(n,W,adj,cm,co,o,b)
    assert feas(n,adj,cm,co,r1)
    if n<=26:
        st[0]+=1; st[1]+= brute(n,W,adj,cm,co)!=r1
    else: st[2]+=1
    return r1
d.solve_portfolio=cmp
sys.argv=['x','environment/data','work/probe_out']; d.main()
print('brute-checked',st[0],'mismatch',st[1],'too big for brute',st[2])
