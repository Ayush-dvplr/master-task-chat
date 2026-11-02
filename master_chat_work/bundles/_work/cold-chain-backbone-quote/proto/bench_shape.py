import random, sys, time, multiprocessing as mp
sys.path.insert(0, '.')
import ref, solvers, wide
tt = wide.load_template(); tt.WIDTH = 10**9
shape = eval(sys.argv[1]); seed = int(sys.argv[2]); count = int(sys.argv[3]); cap = float(sys.argv[4])
def lu(proj, q):
    t = time.time(); g = solvers.frontier_lastuse(proj, solvers.greedy_order(proj)); q.put((time.time()-t, g))
def main():
  rng = random.Random(seed)
  for i in range(count):
      P = wide.wide_project(rng, **shape); proj = tt._as_project(P)
      t = time.time(); want = ref.solve(proj); tr = time.time()-t
      q = mp.Queue(); p = mp.Process(target=lu, args=(proj, q)); p.start(); p.join(cap)
      if p.is_alive():
          p.terminate(); res = 'timeout>%.0f' % cap
      else:
          s, g = q.get(); res = '%.2fs %s cost %s vs %s' % (s, tuple(g) == tuple(want) if g else None, g and g[0], want[0])
      print(i, 'n', P['n'], 'cold', len(P['terms']), 'links', len(P['edges']), 'ref %.3f' % tr, 'lastuse_greedy', res, flush=True)

if __name__ == '__main__':
    main()
