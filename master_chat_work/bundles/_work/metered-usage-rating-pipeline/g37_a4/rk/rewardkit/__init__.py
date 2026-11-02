class _Criteria:
    def __init__(self):
        self.__dict__["items"] = {}
        self.__dict__["defs"] = {}
    def __getattr__(self, name):
        def reg(weight=1, **kw):
            self.items[name] = weight
        return reg
criteria = _Criteria()
def criterion(description="", **kw):
    def deco(fn):
        criteria.defs[fn.__name__] = fn
        return fn
    return deco
