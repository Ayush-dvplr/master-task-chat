"""Splitting a cluster quota over the active products by weight."""


def split_quota(quota, weights):
    """Return {pid: units} for the given {pid: weight} of the active products.

    Largest remainder: every product gets the integer part of its share, then
    the units left over go one each by descending remainder, ties by id.
    """
    total = sum(weights.values())
    if total == 0:
        return {pid: 0 for pid in weights}
    shares, remainders = {}, []
    for pid, weight in weights.items():
        units, remainder = divmod(quota * weight, total)
        shares[pid] = units
        remainders.append((-remainder, pid))
    remainders.sort()
    for _, pid in remainders[:quota - sum(shares.values())]:
        shares[pid] += 1
    return shares
