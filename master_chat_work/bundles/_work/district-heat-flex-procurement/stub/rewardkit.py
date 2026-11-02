"""Local stand-in for rewardkit: records @criterion checks and their registered weights."""
CHECKS = {}
WEIGHTS = {}


def criterion(description):
    def wrap(fn):
        CHECKS[fn.__name__] = (fn, description)
        return fn
    return wrap


class _Criteria:
    def __getattr__(self, name):
        def register(weight):
            WEIGHTS[name] = weight
        return register


criteria = _Criteria()
