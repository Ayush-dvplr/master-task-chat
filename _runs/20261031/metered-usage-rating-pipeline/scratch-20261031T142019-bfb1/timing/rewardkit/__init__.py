class _C:
    def __getattr__(self, n):
        return lambda **k: None
criteria = _C()
def criterion(**k):
    return lambda f: f
