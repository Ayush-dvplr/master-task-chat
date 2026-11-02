"""Local stand-in so the oracle copy imports outside the verifier image (proto only)."""
class _C:
    def __getattr__(self, name):
        return lambda **kw: None
criteria = _C()
def criterion(**kw):
    return lambda f: f
