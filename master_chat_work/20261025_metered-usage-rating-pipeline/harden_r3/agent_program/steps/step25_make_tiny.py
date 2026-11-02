import datetime
import json
import os
import shutil

d = "/tmp/tiny/in"
shutil.rmtree("/tmp/tiny", ignore_errors=True)
os.makedirs(d)
shutil.copy("/app/data/products.ini", d)

open(f"{d}/collector_central.csv", "w").write(
    """record_id,timestamp,account,product,units
CEN-0001,2026-12-01 00:00:00,AC1001,compute_hours,3
CEN-0001,2026-12-01 00:00:00,AC1001,compute_hours,3
CEN-0002,2026-11-30 23:59:59,AC1001,compute_hours,5
CEN-0003,2027-01-01 00:00:00,AC1001,compute_hours,5
CEN-0004,2026-12-02 00:00:00,AC9999,compute_hours,5
CEN-0005,2026-12-02 01:00:00,AC1001,gpu,5
CEN-0006,2026-12-02 02:00:00,AC1001,compute_hours,7.0
CEN-0007,2026-12-03 00:00:00, ac-1002 ,compute_hours,1
"""
)

ep = lambda *a: int(datetime.datetime(*a, tzinfo=datetime.timezone.utc).timestamp())
open(f"{d}/collector_east.tsv", "w").write(
    "id\tepoch\taccount\tproduct\tqty\n"
    f"EAS-0001\t{ep(2026,12,4)}\tAC1001\tvm-hours\t10\n"
    f"EAS-0002\t{ep(2026,12,5)}\tAC1003\tstorage-gbd\t1\n"
)
open(f"{d}/collector_north.jsonl", "w").write("")
line = "SOU-0001".ljust(10) + "20261204000000" + "AC1002".ljust(10) + "STORAGE".ljust(12) + "     1" + "Köln".ljust(20)
open(f"{d}/collector_south.txt", "w", encoding="latin-1").write(line + "\n")
open(f"{d}/collector_west.log", "w").write(
    "2027-01-01T00:30:00+01:00 rec=WES-0001 acct=AC1003 product=compute qty=2\n"
)
open(f"{d}/accounts.csv", "w").write(
    "account_id,segment,plan,parent\n"
    "AC1001,enterprise,committed,\n"
    "AC1002,consumer,payg,AC1001\n"
    "AC1003,smb,committed,\n"
)
open(f"{d}/plan_changes.log", "w").write(
    "2026-12-03T00:00:00Z change account=AC-1002 segment=smb\n"
    "2026-12-10T00:00:00Z change account=AC9999 plan=payg\n"
)
segs = ["consumer", "smb", "corporate", "enterprise"]
card = {
    "currency": "USD",
    "products": {
        "CMP": {"tiers": [{"tier": 1, "from": 0, "rates": {s: 0.1250 for s in segs}},
                           {"tier": 2, "from": 4, "rates": {s: 1.0000 for s in segs}}]},
        "STO": {"tiers": [{"tier": 1, "from": 0, "rates": {s: 0.0100 for s in segs}}]},
        "EGR": {"tiers": [{"tier": 1, "from": 0, "rates": {s: 0.0100 for s in segs}}]},
        "SUP": {"tiers": [{"tier": 1, "from": 0, "rates": {s: 0.0100 for s in segs}}]},
    },
}
text = json.dumps(card, indent=2).replace("0.125,", "0.1250,").replace("1.0,", "1.0000,").replace("0.01,", "0.0100,")
text = text.replace("0.125\n", "0.1250\n").replace("1.0\n", "1.0000\n").replace("0.01\n", "0.0100\n")
open(f"{d}/rate_card.json", "w").write(text)
open(f"{d}/collector_controls.json", "w").write(json.dumps({
    "month": "2026-12",
    "collectors": {
        "central": {"file": "collector_central.csv", "records": 8},
        "east": {"file": "collector_east.tsv", "records": 2},
        "north": {"file": "collector_north.jsonl", "records": 0},
        "south": {"file": "collector_south.txt", "records": 1},
        "west": {"file": "collector_west.log", "records": 1},
    }}, indent=2))
open(f"{d}/commitments.xml", "w").write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<commitments month="2026-12" currency="USD">\n'
    '  <pool region="central" amount="0.50" minimum="0.00"/>\n'
    '  <pool region="east" amount="5.00" minimum="20.00"/>\n'
    '  <pool region="north" amount="100.00" minimum="10.00"/>\n'
    '  <pool region="south" amount="0.00" minimum="0.00"/>\n'
    '  <pool region="west" amount="0.00" minimum="0.00"/>\n</commitments>\n'
)
print("fixture written")
