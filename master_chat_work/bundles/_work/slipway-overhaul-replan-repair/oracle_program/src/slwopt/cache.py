"""The working store.

It holds the value in force for every cell and, beside that, up to the
retained number of superseded entries, so a configuration the round has
already stood in is read back rather than derived again. Dropping a superseded
entry moves no published quantity: a cell whose entry has gone is simply
derived once more.
"""


class Store:

    def __init__(self, retention):
        self.retention = int(retention)
        self.live = {}
        self.retired = {}
        self.stamps = {}
        self.clock = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _stamp(self, marker):
        self.clock += 1
        self.stamps[marker] = self.clock

    def _retire(self, name, entry):
        self.retired[(name, entry[0])] = (entry[1], entry[2])
        self._stamp((name, entry[0]))
        while len(self.retired) > self.retention:
            oldest = min(self.retired, key=lambda m: self.stamps.get(m, 0))
            del self.retired[oldest]
            self.stamps.pop(oldest, None)
            self.evictions += 1

    def take(self, name, key):
        """The value this cell holds for this key, when the store holds it."""
        standing = self.live.get(name)
        if standing is not None and standing[0] == key:
            self.hits += 1
            self._stamp((name, key))
            return standing[1], standing[2]
        kept = self.retired.get((name, key))
        if kept is not None:
            self.hits += 1
            del self.retired[(name, key)]
            self._stamp((name, key))
            if standing is not None:
                self._retire(name, standing)
            self.live[name] = (key, kept[0], kept[1])
            return kept[0], kept[1]
        self.misses += 1
        return None

    def put(self, name, key, value, digest):
        standing = self.live.get(name)
        if standing is not None and standing[0] != key:
            self._retire(name, standing)
        self.live[name] = (key, value, digest)
        self._stamp((name, key))
