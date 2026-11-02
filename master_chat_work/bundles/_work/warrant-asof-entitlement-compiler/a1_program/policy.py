"""Layered configuration resolution (defaults < profiles < site < journal)."""

from __future__ import annotations

import wtime

JOURNAL_SRC = "policy_change_journal.jsonl"


def flat_keys(schema: dict) -> dict[str, tuple[str, dict]]:
    out: dict[str, tuple[str, dict]] = {}
    for key, spec in schema["keys"].items():
        if spec["scope"] == "global":
            out[key] = (key, spec)
        else:
            for prof in schema["profiles"]:
                out[f"{prof}.{key}"] = (key, spec)
    return out


def _typed(spec: dict, value, from_text: bool):
    kind = spec["type"]
    if from_text:
        if kind == "int":
            text = value.strip()
            if not (text.lstrip("-").isdigit() and text.count("-") <= 1):
                raise ValueError(value)
            value = int(text)
        elif kind == "bool":
            if value.strip() not in ("true", "false"):
                raise ValueError(value)
            value = value.strip() == "true"
        else:
            value = value.strip()
    if kind == "int":
        if type(value) is not int or not spec["min"] <= value <= spec["max"]:
            raise ValueError(value)
    elif kind == "bool":
        if type(value) is not bool:
            raise ValueError(value)
    elif kind == "enum":
        if value not in spec["values"]:
            raise ValueError(value)
    return value


def anchors(corpus) -> tuple[int, int]:
    sec = corpus.site["anchor"]
    return wtime.parse_instant(sec["as_of"]), wtime.parse_instant(sec["recorded_cutoff"])


def resolve(corpus, anchor: tuple[int, int] | None = None) -> tuple[dict, list, dict]:
    schema = corpus.schema
    keys = flat_keys(schema)
    as_of, cutoff = anchor if anchor is not None else anchors(corpus)
    layers: dict[str, list] = {name: [] for name in keys}

    def put(flat: str, value, from_text: bool) -> None:
        spec = keys[flat][1]
        layers[flat].append(_typed(spec, value, from_text))

    for base, value in corpus.defaults["values"].items():
        spec = schema["keys"].get(base)
        if spec is None:
            continue
        if spec["scope"] == "global":
            put(base, value, False)
        else:
            for prof in schema["profiles"]:
                put(f"{prof}.{base}", value, False)
    for prof in schema["profiles"]:
        for base, value in corpus.profiles.get(prof, {}).items():
            if f"{prof}.{base}" in keys:
                put(f"{prof}.{base}", value, False)
    for section, values in corpus.site.items():
        if section == "anchor":
            continue
        for base, value in values.items():
            flat = base if section == "global" else f"{section}.{base}"
            if flat in keys:
                put(flat, value, True)

    rejects = []
    stats = {"records": 0, "invisible": 0, "rejected": 0, "unresolved": 0, "collapsed": 0,
             "accepted": 0, "applied": 0, "cancelled": 0, "late": 0}
    entries = []
    for row in corpus.journal:
        rid = str(row.get("seq"))
        stats["records"] += 1
        try:
            rec = wtime.parse_instant(row.get("recorded_at"))
        except wtime.BadTime:
            rejects.append((JOURNAL_SRC, rid, "bad_timestamp"))
            stats["rejected"] += 1
            continue
        if rec > cutoff:
            stats["invisible"] += 1
            continue
        reason = None
        eff = None
        try:
            eff = wtime.parse_instant(row.get("effective_at"))
        except wtime.BadTime:
            reason = "bad_timestamp"
        key = row.get("key")
        if reason is None and "value" not in row:
            reason = "missing_field"
        if reason is None and key in schema["anchor_keys"]:
            reason = "anchor_key"
        if reason is None and key not in keys:
            reason = "unknown_key"
        if reason is None and row["value"] is not None:
            try:
                _typed(keys[key][1], row["value"], False)
            except ValueError:
                reason = "out_of_bounds"
        if reason is not None:
            rejects.append((JOURNAL_SRC, rid, reason))
            stats["rejected"] += 1
            continue
        stats["accepted"] += 1
        entries.append((eff, int(row["seq"]), key, row["value"]))
    entries.sort(key=lambda item: (item[0], item[1]))
    journal: dict[str, list] = {name: [] for name in keys}
    for eff, seq, key, value in entries:
        if eff > as_of:
            stats["late"] += 1
            continue
        stats["applied"] += 1
        if value is None:
            stats["cancelled"] += 1
            journal[key] = []
        else:
            journal[key].append(value)

    config: dict = {"as_of": wtime.fmt(as_of), "recorded_cutoff": wtime.fmt(cutoff)}
    for flat, (base, spec) in keys.items():
        standing = journal[flat]
        values = layers[flat] + standing
        if not values:
            continue
        if spec["class"] == "ceiling":
            config[flat] = min(values)
        else:
            config[flat] = standing[-1] if standing else layers[flat][-1]
    return config, rejects, stats
