def criterion(*a, **k):
    def d(f): return f
    return d(a[0]) if a and callable(a[0]) else d
class _C:
    def __getattr__(self, n): return lambda *a, **k: None
criteria = _C()
