import csv, os, datetime, collections
import xml.etree.ElementTree as ET
D = "/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind2-20261101T0345-81c3/environment/data"
root = ET.parse(os.path.join(D, "tariff.xml")).getroot()
VERS = []
for v in root.findall("version"):
    bands = []
    for b in v.findall("band"):
        fh, fm = map(int, b.get("from").split(":"))
        th, tm = map(int, b.get("to").split(":"))
        bands.append((fh*60+fm, th*60+tm, int(b.get("cents_per_kwh"))))
    VERS.append((v.get("valid_from"), v.get("valid_to"), bands))
def ver_for(date):
    out = [v for v in VERS if v[0] <= date <= v[1]]
    assert len(out) == 1, (date, out)
    return out[0][2]
def price_at(bands, minute):
    m = minute % 1440
    for a, b, c in bands:
        if a < b:
            if a <= m < b: return c
        else:
            if m >= a or m < b: return c
    raise KeyError(m)
def T(s): return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M")

RULES = {}
RULES["start"] = lambda bands, m: price_at(bands, m)
RULES["end"] = lambda bands, m: price_at(bands, m+15)
RULES["prev"] = lambda bands, m: price_at(bands, m-15)
RULES["hour"] = lambda bands, m: price_at(bands, (m//60)*60)
RULES["halfhour"] = lambda bands, m: price_at(bands, (m//30)*30)
RULES["hourend"] = lambda bands, m: price_at(bands, (m//60)*60+59)
RULES["maxhour"] = lambda bands, m: max(price_at(bands, (m//60)*60+k) for k in (0,15,30,45))
RULES["minhour"] = lambda bands, m: min(price_at(bands, (m//60)*60+k) for k in (0,15,30,45))
RULES["maxslot"] = lambda bands, m: max(price_at(bands, m), price_at(bands, m+15))
RULES["minslot"] = lambda bands, m: min(price_at(bands, m), price_at(bands, m+15))

rows = list(csv.DictReader(open(os.path.join(D, "settlements.csv"))))
bad = collections.Counter()
per = collections.defaultdict(lambda: collections.Counter())
tot = collections.Counter()
for r in rows:
    s, e = T(r["start"]), T(r["end"])
    mins = int((e-s).total_seconds()//60)
    assert mins % 15 == 0 and mins > 0, r
    n = mins//15
    kwh = int(r["kwh"])
    assert kwh % n == 0, (r, n)
    per_slot = kwh//n
    bands = ver_for(r["settled_date"])
    slots = [s + datetime.timedelta(minutes=15*i) for i in range(n)]
    tot[r["depot"]] += 1
    for name, fn in RULES.items():
        c = sum(per_slot * fn(bands, t.hour*60+t.minute) for t in slots)
        if c == int(r["cents"]):
            per[r["depot"]][name] += 1
for d in ("North","South","West","East"):
    print(d, tot[d], dict(per[d]))
