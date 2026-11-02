import sys
from pathlib import Path
src=Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cohort-retention-reconciliation/solution/solve.py").read_text()
def sub(s,a,b):
    assert s.count(a)>=1,a
    return s.replace(a,b)
P={}
# L2a: normalise only events.csv identifiers
def L2a(s):
    s=sub(s,'def ident(text: str) -> str:','def raw_ident(text: str) -> str:\n    return text\n\n\ndef ident(text: str) -> str:')
    body_start=s.index('def tag_rows'); body_end=s.index('def first_of_each_key')
    head,mid,tail=s[:body_start],s[body_start:body_end],s[body_end:]
    head=head.replace('ident(row','raw_ident(row').replace('ident(kind)','raw_ident(kind)').replace('ident(plan)','raw_ident(plan)').replace('ident(self.accounts','raw_ident(self.accounts')
    return head+mid+tail
P['L2a']=L2a
P['L2none']=lambda s: sub(s,'    return text.strip().lower()','    return text')
P['L2b']=lambda s: sub(s,'raw_key = (account, raw["event_date"], kind)','raw_key = (raw["account_id"], raw["event_date"], raw["event_type"])')
P['L2c']=lambda s: sub(sub(s,'day = strict_day(raw["event_date"])','day = strict_day(raw["event_date"].strip())'),'int(raw["value_cents"]) if WHOLE_CENTS.fullmatch(raw["value_cents"])','int(raw["value_cents"].strip()) if WHOLE_CENTS.fullmatch(raw["value_cents"].strip())')
P['L1a']=lambda s: sub(s,'value = (row.get("value_cents") or "").strip()','value = row.get("value_cents") or ""')
P['L1b']=lambda s: sub(s,'"control_mismatches": list(study.extract.control_mismatches),','"control_mismatches": [],')
P['L3a']=lambda s: sub(s,'booked = -min(row.cents, held)','booked = -row.cents')
P['L3b']=lambda s: sub(sub(s,'held = balance.get(row.owner, 0)','held = balance.get(row.raw_key[0], 0)'),'balance[row.owner] = held + booked','balance[row.raw_key[0]] = held + booked')
P['L4a']=lambda s: sub(s,'override = self.overrides.get(self.segment_of(account))','override = None')
def L4b(s):
    s=sub(s,'def weight_on(self, account: str, day: date) -> int:\n        override = self.overrides.get(self.segment_of(account))','def weight_on(self, account: str, day: date, raw: str | None = None) -> int:\n        seen = raw if raw in self.accounts else account\n        override = self.overrides.get(self.segment_of(seen))')
    return sub(s,'extract.weight_on(row.owner, row.day)','extract.weight_on(row.owner, row.day, row.raw_key[0])')
P['L4b']=L4b
name=sys.argv[1]; s=src
for k in sys.argv[2:]: s=P[k](s)
Path(name).write_text(s)
