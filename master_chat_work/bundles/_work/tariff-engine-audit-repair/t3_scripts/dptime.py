import sys, time, signal
sys.path.insert(0, '.')
from load import load
import vouch
m = load()
exec(open('stmt_block.py').read(), m.__dict__)
texts = m._statement_texts(sys.argv[1])
rows = m._voucher_rows(texts); bal = m._balances(texts)
def alarm(*a): raise TimeoutError
signal.signal(signal.SIGALRM, alarm)
for a in sorted(rows):
    T = bal.get(a,0); want = m._redeem(T, rows[a])
    for name in sys.argv[2:]:
        signal.alarm(int(sys.argv[0:1] and 25)); t=time.time()
        try: got = (m._redeem if name == "REF" else getattr(vouch, name))(T, rows[a]); res = got == want
        except TimeoutError: res = "TIMEOUT"
        except MemoryError: res = "MEM"
        signal.alarm(0)
        print(a, T, len(rows[a]), name, "%.2fs" % (time.time()-t), res, flush=True)
