"""Splitting a cluster quota over the active products by weight."""


def _largest_remainder(quota, weights):
    """Hand out quota in proportion to weights: integer parts, then remainders."""
    total = sum(weights.values())
    if quota <= 0 or total <= 0:
        return {pid: 0 for pid in weights}
    units, remainder = {}, {}
    for pid, weight in weights.items():
        units[pid] = quota * weight // total
        remainder[pid] = quota * weight % total
    left = quota - sum(units.values())
    order = sorted(weights, key=lambda pid: (-remainder[pid], pid))
    for pid in order[:left]:
        units[pid] += 1
    return units


def split_quota(quota, weights, caps=None):
    """Return {pid: units} for the given {pid: weight}, honouring {pid: cap}."""
    caps = caps or {}
    units = _largest_remainder(quota, weights)
    while True:
        given_back = 0
        for pid, cap in caps.items():
            if pid in units and units[pid] > cap:
                given_back += units[pid] - cap
                units[pid] = cap
        if given_back == 0:
            return units
        eligible = {pid: weight for pid, weight in weights.items()
                    if pid not in caps or units[pid] < caps[pid]}
        if sum(eligible.values()) <= 0:
            return units
        for pid, extra in _largest_remainder(given_back, eligible).items():
            units[pid] += extra
