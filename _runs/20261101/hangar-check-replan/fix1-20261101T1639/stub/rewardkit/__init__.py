"""Host-only stand-in so the G12 generator survey can import tests/test_output.py."""
class _Criteria:
    def __getattr__(self, name):
        return lambda **kw: None
criteria = _Criteria()
def criterion(**kw):
    return lambda f: f
