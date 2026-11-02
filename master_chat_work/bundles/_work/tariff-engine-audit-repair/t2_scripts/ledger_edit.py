p='test_output.src.py'
s=open(p).read()
def rep(a,b):
    global s
    assert s.count(a)==1,a
    s=s.replace(a,b)
rep('''    `off` names quiet rules read the habitual way instead (Q1 estimated reads,
    Q2 standing changes, Q3 several billing rows, Q4 allowance carried, Q5
    several meter rows); the planting asserts use it, the checks never do."""''','''    `off` names quiet rules read the habitual way instead (Q1 estimated reads,
    Q2 standing changes, Q3 several billing rows, Q4 allowance carried, Q5
    several meter rows, U1 plan revisions, D1 paid amounts, D2 cumulative
    reads, and their variants); the planting asserts use it, the checks never
    do."""''')
rep('''        self.reads = [json.loads(line) for line in texts["meter_reads.jsonl"].splitlines() if line.strip()]
        self.ties: dict[str, int] = {}
        self.passes: dict[str, int] = {}
''','''        self.reads = [json.loads(line) for line in texts["meter_reads.jsonl"].splitlines() if line.strip()]
        self.paid: dict[tuple[str, date], Fraction] = {}
        for row in csv.DictReader(io.StringIO(texts.get("payments.csv", ""))):
            row = {key.strip(): (value or "").strip() for key, value in row.items()}
            key = (row["account"], date.fromisoformat(row["start"]))
            self.paid[key] = self.paid.get(key, Fraction(0)) + Fraction(row["paid"])
        self.ties: dict[str, int] = {}
        self.passes: dict[str, int] = {}
        self.halves: dict[str, int] = {}
''')
rep('''                key = (account, self._row(account, day)[0], meter)
                usage[key] = usage.get(key, 0) + read["quantity"]
            else:
                exceptions.append({"read_id": read["read_id"].strip(), "account": account, "reason": reason})
        exceptions.sort(key=lambda row: row["read_id"])
        invoices = []
        for account in sorted(self.rows):
            carry = Fraction(0)
            for entry in self.rows[account]:
                invoice, left = self._invoice(account, entry, usage, carry)
                invoices.append(invoice)
                carry = Fraction(0) if "Q4" in self.off else left
        return {"invoices": invoices, "exceptions": exceptions}
''','''                accepted.append((read, account, meter, day))
            else:
                exceptions.append({"read_id": read["read_id"].strip(), "account": account, "reason": reason})
        exceptions.sort(key=lambda row: row["read_id"])
        billed = self._billed(accepted)
        for read, account, meter, day in accepted:
            key = (account, self._row(account, day)[0], meter)
            usage[key] = usage.get(key, 0) + billed[read["read_id"]]
        self.chosen: dict[str, Any] = {}
        for key in sorted(self.plans):
            if "U1" in self.off or not self.plans[key].get("revisions"):
                continue
            fits = [number for number, revision in enumerate(self.plans[key]["revisions"])
                    if self._fits(key, revision["tiers"], usage)]
            if len(fits) == 1 or (fits and "U1first" in self.off):
                self.chosen[key] = self.plans[key]["revisions"][fits[0]]["tiers"]
        self.ties, self.passes, self.halves = {}, {}, {}
        invoices = []
        for account in sorted(self.rows):
            invoices += self._chain(account, usage, self.chosen)
        return {"invoices": invoices, "exceptions": exceptions}

    def _billed(self, accepted: list) -> dict[str, int]:
        """Billed quantity per read id of the accepted reads."""
        billed, chains = {}, {}
        pool = accepted
        if "D2any" in self.off:
            pool = [(read, read["account"].strip(), read["meter"].strip(), date.fromisoformat(read["day"].strip()))
                    for read in self.reads if type(read["quantity"]) is int and read["quantity"] >= 0]
        for place, (read, account, meter, day) in enumerate(pool):
            if "D2" not in self.off and read.get("cumulative", False) is True:
                scope = self._row(account, day)[0] if "D2row" in self.off else None
                chains.setdefault((account, meter, scope), []).append((day, place, read))
        for read, account, meter, day in accepted:
            billed[read["read_id"]] = read["quantity"]
        for chain in chains.values():
            chain.sort(key=lambda item: item[1] if "D2file" in self.off else item[0])
            for place, (day, _, read) in enumerate(chain):
                if read["read_id"] not in billed:
                    continue
                count = read["quantity"]
                before = chain[place - 1][2]["quantity"] if place else None
                billed[read["read_id"]] = 0 if before is None else count if before > count else count - before
        return billed

    def _fits(self, key: str, tiers: list, usage: dict) -> bool:
        tried = dict(self.chosen)
        tried[key] = tiers
        for account in sorted(self.rows):
            if all(self._plan_key(entry[2]) != key for entry in self.rows[account]):
                continue
            for invoice in self._chain(account, usage, tried):
                paid = self.paid.get((account, date.fromisoformat(invoice["period"]["start"])))
                if self._plan_key(invoice["plan"]) == key and paid is not None and Fraction(invoice["total"]) != paid:
                    return False
        return True

    def _chain(self, account: str, usage: dict, chosen: dict) -> list[dict[str, Any]]:
        invoices, carry, owed = [], Fraction(0), False
        for entry in self.rows[account]:
            invoice, left = self._invoice(account, entry, usage, carry, chosen, owed)
            invoices.append(invoice)
            carry = Fraction(0) if "Q4" in self.off else left
            paid = self.paid.get((account, entry[0]), Fraction(0) if "D1zero" in self.off else None)
            owed = "D1" not in self.off and paid is not None and paid < Fraction(invoice["total"])
        return invoices
''')
rep('''        usage: dict[tuple[str, date, str], int] = {}
        exceptions = []
''','''        usage: dict[tuple[str, date, str], int] = {}
        exceptions, accepted = [], []
''')
rep('''    def _invoice(self, account: str, entry: tuple, usage: dict, carry: Fraction) -> tuple[dict[str, Any], Fraction]:
        start, end, plan_name, commitment, allowance = entry
        self.keys[account] = self._plan_key(plan_name)
        plan = self.plans[self.keys[account]]
        lines, ties, position = [], 0, 0
        for meter in sorted(m for (a, m) in self.spans if a == account):
            quantity, floor = usage.get((account, start, meter), 0), 0
            for number, tier in enumerate(plan["tiers"], 1):''','''    def _invoice(self, account: str, entry: tuple, usage: dict, carry: Fraction,
                 chosen: dict | None = None, owed: bool = False) -> tuple[dict[str, Any], Fraction]:
        start, end, plan_name, commitment, allowance = entry
        self.keys[account] = self._plan_key(plan_name)
        plan = self.plans[self.keys[account]]
        tiers = (chosen or {}).get(self.keys[account], plan["tiers"])
        lines, ties, position = [], 0, 0
        for meter in sorted(m for (a, m) in self.spans if a == account):
            quantity, floor = usage.get((account, start, meter), 0), 0
            if "N3" in self.off:
                position = 0
            for number, tier in enumerate(tiers, 1):''')
rep('''        left, live, passes = allowance + carry, [line for line in lines if line[1] == "energy"], 0
        while left > 0 and live:
            passes += 1''','''        left, live, passes = allowance + carry, [line for line in lines if line[1] == "energy"], 0
        while left > 0 and live and not ("N1" in self.off and passes):
            passes += 1''')
rep('''        if Fraction(subtotal, 100) >= commitment:
            kept''','''        if Fraction(subtotal, 100) >= commitment and not owed:
            kept''')
open(p,'w').write(s)
print("ok")
