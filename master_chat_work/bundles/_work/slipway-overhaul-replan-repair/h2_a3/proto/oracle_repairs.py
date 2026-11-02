"""New oracle repairs on top of the fifteen catalogued ones.

Usage: python3 -B oracle_repairs.py <engine_root>
Each anchor must match its file exactly once.
"""
import sys
from pathlib import Path

REPAIRS = (
    ("DFC-16", "src/slwopt/cells.py",
     "        for name in list(self.accepted):\n"
     "            if name not in self.jobs:\n"
     "                del self.accepted[name]\n"
     "            else:\n"
     "                self.accepted[name] = [step for step in self.accepted[name]\n"
     "                                       if step in self.jobs]\n",
     "        accepted, rejected = graph.sift(self.journal, self.jobs)\n"
     "        self.accepted = accepted\n"
     "        self.edge_rejected = sorted(rejected)\n"),
    ("DFC-17", "src/slwopt/cells.py",
     "        self.groups, group_rejected = graph.groups(root, self.jobs)\n",
     "        self.groups, group_rejected = graph.groups(root, self.jobs, alias)\n"),
    ("DFC-18", "src/slwopt/graph.py",
     "def groups(root, jobs):\n"
     "    \"\"\"Stage p08. Open memberships, with a job standing in two open groups\n"
     "    kept by the group of the lower precedence number.\"\"\"\n"
     "    rows = [row for row in reading.delimited(root / \"exclusive_slot_groups.csv\")\n"
     "            if row[\"state\"] == \"open\" and row[\"member_job\"] in jobs]\n",
     "def groups(root, jobs, alias):\n"
     "    \"\"\"Stage p08. Open memberships, with a job standing in two open groups\n"
     "    kept by the group of the lower precedence number.\"\"\"\n"
     "    rows = []\n"
     "    for row in reading.delimited(root / \"exclusive_slot_groups.csv\"):\n"
     "        row = dict(row)\n"
     "        row[\"member_job\"] = alias.get(row[\"member_job\"], row[\"member_job\"])\n"
     "        if row[\"state\"] == \"open\" and row[\"member_job\"] in jobs:\n"
     "            rows.append(row)\n"),
    ("DFC-19", "src/slwopt/cells.py",
     "            if record.get(\"state\") == \"in_force\":\n"
     "                self.rules[record[\"rule_id\"]] = dict(record)\n",
     "            if record.get(\"state\") == \"in_force\":\n"
     "                record = dict(record)\n"
     "                for field in (\"first_job\", \"second_job\", \"anchor_job\"):\n"
     "                    if record.get(field):\n"
     "                        record[field] = alias.get(record[field], record[field])\n"
     "                self.rules[record[\"rule_id\"]] = record\n"),
    ("DFC-20", "src/slwopt/mutate.py",
     "    out = []\n"
     "    for record in sorted(rows, key=lambda r: int(r[\"sequence\"])):\n",
     "    alias = normalise.crosswalk(root)\n"
     "    out = []\n"
     "    for record in sorted(rows, key=lambda r: int(r[\"sequence\"])):\n"),
    ("DFC-21", "src/slwopt/mutate.py",
     "            payload[field] = value\n"
     "        out.append(",
     "            payload[field] = value\n"
     "        for field in (\"job_id\", \"requiring_job\", \"required_job\",\n"
     "                      \"member_job\"):\n"
     "            if field in payload:\n"
     "                payload[field] = alias.get(payload[field], payload[field])\n"
     "        out.append("),
    ("DFC-22", "src/slwopt/mutate.py",
     "        if requiring not in model.jobs or required not in model.jobs:\n"
     "            return kind, payload, \"rejected\", \"EDG-UNKNOWNJOB\"\n"
     "        if requiring == required:\n"
     "            return kind, payload, \"rejected\", \"EDG-SELF\"\n",
     "        if requiring == required:\n"
     "            return kind, payload, \"rejected\", \"EDG-SELF\"\n"
     "        if requiring not in model.jobs or required not in model.jobs:\n"
     "            return kind, payload, \"rejected\", \"EDG-UNKNOWNJOB\"\n"),
    ("DFC-23", "src/slwopt/mutate.py",
     "    if kind == \"edge_lodged\":\n"
     "        model.journal[payload[\"edge_id\"]] = {\n"
     "            \"requiring_job\": payload[\"requiring_job\"],\n"
     "            \"required_job\": payload[\"required_job\"],\n"
     "            \"kind\": payload.get(\"kind\", \"hard\"), \"status\": \"active\"}\n"
     "        model.refresh_edges(model.jobs[payload[\"requiring_job\"]][\"precinct\"])\n"
     "        return {\"edge_id\": payload[\"edge_id\"]}\n"
     "    if kind == \"edge_withdrawn\":\n"
     "        row = model.journal[payload[\"edge_id\"]]\n"
     "        back = {\"edge_id\": payload[\"edge_id\"],\n"
     "                \"requiring_job\": row[\"requiring_job\"],\n"
     "                \"required_job\": row[\"required_job\"], \"kind\": row[\"kind\"]}\n"
     "        row[\"status\"] = \"withdrawn\"\n",
     "    if kind == \"edge_lodged\":\n"
     "        back = {\"edge_id\": payload[\"edge_id\"],\n"
     "                \"requiring_job\": payload[\"requiring_job\"],\n"
     "                \"required_job\": payload[\"required_job\"],\n"
     "                \"kind\": payload.get(\"kind\", \"hard\")}\n"
     "        if payload.get(\"undo\"):\n"
     "            del model.journal[payload[\"edge_id\"]]\n"
     "        else:\n"
     "            model.journal[payload[\"edge_id\"]] = {\n"
     "                \"requiring_job\": payload[\"requiring_job\"],\n"
     "                \"required_job\": payload[\"required_job\"],\n"
     "                \"kind\": payload.get(\"kind\", \"hard\"), \"status\": \"active\"}\n"
     "            back[\"undo\"] = True\n"
     "        model.refresh_edges(model.jobs[payload[\"requiring_job\"]][\"precinct\"])\n"
     "        return back\n"
     "    if kind == \"edge_withdrawn\":\n"
     "        row = model.journal[payload[\"edge_id\"]]\n"
     "        back = {\"edge_id\": payload[\"edge_id\"],\n"
     "                \"requiring_job\": row[\"requiring_job\"],\n"
     "                \"required_job\": row[\"required_job\"], \"kind\": row[\"kind\"]}\n"
     "        if payload.get(\"undo\"):\n"
     "            row[\"status\"] = payload[\"undo\"]\n"
     "        else:\n"
     "            back[\"undo\"] = row[\"status\"]\n"
     "            row[\"status\"] = \"withdrawn\"\n"),
    ("DFC-24", "src/slwopt/mutate.py",
     "    seeds = seeds_for(model, kind, payload)\n",
     "    seeds = seeds_for(model, kind, payload)\n"
     "    if not seeds:\n"
     "        record[\"classification\"] = \"inert\"\n"),
    ("DFC-25", "src/slwopt/publish.py",
     "        weighted += Fraction(body[\"weighted_resource\"])\n",
     "        for pool in body[\"usage\"]:\n"
     "            top, bottom = model.params[\"pool_weights\"][pool]\n"
     "            weighted += Fraction(top, bottom) * body[\"usage\"][pool]\n"),
    ("DFC-26", "src/slwopt/publish.py",
     "        \"aliases_active\": len(model.alias),\n",
     "        \"aliases_active\": sum(\n"
     "            1 for row in graph.reading.delimited(\n"
     "                root / \"identifier_crosswalk.tsv\", graph.reading.TAB)\n"
     "            if row[\"status\"] == \"active\"),\n"),
    ("DFC-27", "src/slwopt/reading.py",
     "                            for cell in row.findall(WORD_NS + \"tc\")])\n"
     "    return out\n",
     "                            for cell in row.findall(WORD_NS + \"tc\")])\n"
     "    return out\n"
     "\n"
     "\n"
     "def _declared(reader):\n"
     "    \"\"\"Stop the run, naming the file, when a declared input is missing or\n"
     "    cannot be read in the shape its reader expects.\"\"\"\n"
     "    def guarded(path, *rest):\n"
     "        if not Path(path).is_file():\n"
     "            raise SystemExit(\"a declared input is missing: \" + str(path))\n"
     "        try:\n"
     "            return reader(path, *rest)\n"
     "        except (OSError, ValueError, KeyError, IndexError,\n"
     "                zipfile.BadZipFile, sqlite3.Error, ET.ParseError) as error:\n"
     "            raise SystemExit(\"a declared input is malformed: \" + str(path)\n"
     "                             + \": \" + str(error)) from error\n"
     "    guarded.__name__ = reader.__name__\n"
     "    guarded.__doc__ = reader.__doc__\n"
     "    return guarded\n"
     "\n"
     "\n"
     "text_lines = _declared(text_lines)\n"
     "delimited = _declared(delimited)\n"
     "records = _declared(records)\n"
     "document = _declared(document)\n"
     "xml_nodes = _declared(xml_nodes)\n"
     "table = _declared(table)\n"
     "sheets = _declared(sheets)\n"
     "pdf_lines = _declared(pdf_lines)\n"
     "docx_blocks = _declared(docx_blocks)\n"),
)


def main():
    root = Path(sys.argv[1])
    for code, relative, old, new in REPAIRS:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(code + " matches " + str(text.count(old)) + " times")
        path.write_text(text.replace(old, new), encoding="utf-8")
    print("repaired", len(REPAIRS))


if __name__ == "__main__":
    main()
