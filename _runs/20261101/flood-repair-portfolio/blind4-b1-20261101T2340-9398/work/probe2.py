import sys, signal, cProfile, pstats
sys.path.insert(0, 'app')
import derive_report as d
sys.setrecursionlimit(20000)
class Stop(Exception): pass
def h(*a): raise Stop()
signal.signal(signal.SIGALRM, h)
sys.argv = ['x', 'environment/data', 'work/probe_out']
pr = cProfile.Profile()
signal.alarm(25)
pr.enable()
try: d.main()
except Stop: pass
pr.disable()
pstats.Stats(pr).sort_stats('tottime').print_stats(8)
