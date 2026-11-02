#!/usr/bin/env python3
"""reserving.py - IBNR reserving with excess-of-loss reinsurance treaty settlements.

Reads --data <dir>, writes nine JSON documents and this program itself into
--out <dir>. Stdlib only, offline, byte-identical across reruns.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone

LOBS = ["wc", "cal", "gl", "cp", "spec"]
ACCIDENT_YEARS = list(range(2023, 2033))
CYCLES = ["H%02d" % i for i in range(1, 27)]
CYCLE_IDX = {c: i for i, c in enumerate(CYCLES)}
LAYERS = ["retention", "working_excess", "cat_excess"]
LONG_TAIL_LOBS = {"wc", "cal", "gl"}


def _half_up(x: float, ndigits: int) -> float:
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(10) ** (-ndigits)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def _half_up_int(x: float) -> int:
    from decimal import Decimal, ROUND_HALF_UP
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def load_counterfactual_parameters(data: pathlib.Path) -> dict:
    """Read the three declared counterfactual parameters from counterfactual_parameters.md."""
    path = data / "counterfactual_parameters.md"
    text = must_read(path)
    patterns = {
        "extra_tenor_years": r"added tenor is `([0-9]+)` years",
        "extra_tenor_increment": r"plus a fixed increment of `([0-9.]+)` percentage",
        "retro_multiplier": r"multiplied by `([0-9.]+)` before",
    }
    params = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, text)
        if not m:
            raise ValueError("%s does not declare %s" % (path, key))
        params[key] = int(m.group(1)) if key == "extra_tenor_years" else float(m.group(1))
    return params


def must_read(path: pathlib.Path) -> str:
    if not path.is_file():
        raise FileNotFoundError("missing source: %s" % path)
    return path.read_text()


def parse_csv(path: pathlib.Path) -> list[dict]:
    text = must_read(path)
    reader = csv.reader(text.splitlines())
    header = None
    first_cols: list[int] = []
    seen: set[str] = set()
    rows: list[dict] = []
    for row in reader:
        if not row or (row and row[0].startswith("#")):
            continue
        if header is None:
            header = row
            for i, title in enumerate(header):
                if title not in seen:
                    seen.add(title)
                    first_cols.append(i)
            continue
        record: dict[str, str] = {}
        for i in first_cols:
            if i >= len(header):
                continue
            record[header[i]] = row[i] if i < len(row) else ""
        rows.append(record)
    return rows


def parse_csv_positional(path: pathlib.Path) -> tuple[list[str], list[list[str]]]:
    text = must_read(path)
    reader = csv.reader(text.splitlines())
    header = None
    rows: list[list[str]] = []
    for row in reader:
        if not row or (row and row[0].startswith("#")):
            continue
        if header is None:
            header = row
            continue
        rows.append(row)
    if header is None:
        raise ValueError("empty CSV: %s" % path)
    return header, rows


def parse_tsv(path: pathlib.Path) -> list[dict]:
    text = must_read(path)
    reader = csv.reader(text.splitlines(), delimiter="\t")
    header = None
    rows: list[dict] = []
    for row in reader:
        if not row or (row and row[0].startswith("#")):
            continue
        if header is None:
            header = row
            continue
        rows.append({header[i]: row[i] if i < len(row) else "" for i in range(len(header))})
    return rows


def parse_jsonl(path: pathlib.Path) -> list[dict]:
    text = must_read(path)
    out: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(json.loads(stripped))
    return out


def parse_fixed_width(path: pathlib.Path, widths: list[tuple[str, int, int]]) -> list[dict]:
    text = must_read(path)
    out: list[dict] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        row = {name: line[s:e].strip() for name, s, e in widths}
        out.append(row)
    return out


def _dollars(text: str) -> int:
    """Whole dollars; a parenthesised amount such as (1,234) is negative (unit_declarations.ini)."""
    stripped = text.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        return -int(stripped[1:-1].replace(",", ""))
    return int(stripped.replace(",", ""))


def parse_claim_tx_by_position(path: pathlib.Path) -> list[dict]:
    """Read claim transaction logs by COLUMN POSITION.

    Columns in the generated corpus:
      0: claim_ref
      1: reinsurer_id
      2: lob
      3: accident_year (e.g. "AY2028")
      4: paid_to_date (GOVERNING; first paid_to_date column)
      5: incurred (confusingly titled paid_to_date too)
      6: recorded_instant
      7: paid_to_date_restated (TRAP; a dict reader keeping the last header
         occurrence would silently pick this instead of column 4).
    """
    _header, rows = parse_csv_positional(path)
    out: list[dict] = []
    for row in rows:
        if len(row) < 7:
            raise ValueError("truncated claim tx row in %s: %r" % (path, row))
        ay_text = row[3]
        ay = int(ay_text[2:]) if ay_text.startswith("AY") else int(ay_text)
        out.append({
            "claim_ref": row[0],
            "reinsurer_raw": row[1],
            "lob": row[2],
            "ay": ay,
            "paid_to_date": int(row[4]),
            "incurred": int(row[5]),
            "recorded_instant": row[6],
            "paid_to_date_restated": _dollars(row[7]) if len(row) >= 8 and row[7] else int(row[4]),
            "_source": path.name,
        })
    return out


def _parse_instant(text: str) -> datetime:
    stripped = (text or "").strip()
    if stripped.endswith("Z"):
        stripped = stripped[:-1] + "+00:00"
    return datetime.fromisoformat(stripped).astimezone(timezone.utc)


def fit_alae_fraction(obs: list[tuple[int, int, int, str]]) -> float | None:
    """Return the pro-rata fraction every observation fits within one dollar.

    Each row bounds the fraction to an interval; the fraction is the value
    with the fewest decimal places inside the intersection, and it must be
    the only such value at that precision. None when no value fits.
    """
    from decimal import Decimal
    if not obs or any(settled <= 0 for _gross, _alae, settled, _layer in obs):
        return None
    lo = max(Decimal(alae - 1.5) / settled for _g, alae, settled, _l in obs)
    hi = min(Decimal(alae + 1.5) / settled for _g, alae, settled, _l in obs)
    if lo > hi:
        return None
    for places in range(1, 7):
        scale = 10 ** places
        first = int(lo * scale) - 1
        last = int(hi * scale) + 1
        fits = []
        for k in range(max(first, 0), last + 1):
            frac = k / scale
            if all(abs(alae - _half_up_int(frac * settled)) <= 1 for _g, alae, settled, _l in obs):
                fits.append(frac)
        if len(fits) == 1:
            return fits[0]
        if len(fits) > 1:
            return None
    return None


def settle_alae_convention(data: pathlib.Path) -> tuple[str, float]:
    """Settle by arithmetic consistency across every observation.

    pro_rata fits iff one fraction of settled reproduces every row's alae
    within one dollar, regardless of layer. excess_only fits iff
    retention-layer rows carry zero alae and excess-layer rows carry
    positive alae. A reading that fits only some rows is rejected. Returns
    the surviving convention and the fitted fraction.
    """
    text = must_read(data / "claim_adjustment_log.log")
    obs = []
    pattern = re.compile(
        r"CLM-\d+\s+gross=(\d+)\s+alae=(\d+)\s+settled=(\d+)\s+layer=(\S+)"
    )
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = pattern.search(line)
        if m:
            obs.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)))
    if not obs:
        raise RuntimeError("claim_adjustment_log.log carries no observations")
    frac = fit_alae_fraction(obs)
    pro_rata_fits = frac is not None
    excess_only_fits = all(
        (alae == 0) if layer == "retention" else (alae > 0)
        for _gross, alae, _settled, layer in obs
    )
    surviving = [
        name for name, fit in (
            ("pro_rata", pro_rata_fits),
            ("excess_only", excess_only_fits),
        ) if fit
    ]
    if len(surviving) != 1:
        raise RuntimeError(
            "ALAE ambiguous: pro_rata=%s excess_only=%s obs=%d"
            % (pro_rata_fits, excess_only_fits, len(obs))
        )
    if frac is None:
        raise RuntimeError("claim_adjustment_log.log fits no single ALAE fraction")
    return surviving[0], frac


def settle_discount_curve(data: pathlib.Path) -> str:
    """Settle by matching observed pv_factor to each candidate's prediction.

    flat_10y predicts pv_factor = (1 + curve[10]/100)^(-tenor) regardless
    of row's tenor. duration_matched predicts pv_factor = (1 + observed/100)^(-tenor)
    row by row. Keep the candidate whose prediction matches every row.
    """
    text = must_read(data / "treasury_curve_observations.log")
    curve = {}
    for row in parse_csv(data / "curve_marks.csv"):
        curve[int(row["tenor_years"])] = float(row["yield_pct"])
    pattern = re.compile(
        r"tenor=(\d+)y\s+observed=([\d.]+)\s+pv_factor=([\d.]+)"
    )
    obs = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = pattern.search(line)
        if m:
            obs.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
    if not obs:
        raise RuntimeError("treasury_curve_observations.log carries no observations")
    flat_10 = curve.get(10, 4.0) / 100.0
    flat_fits = all(
        abs(pv - (1.0 + flat_10) ** (-tenor)) <= 0.005
        for tenor, _obs, pv in obs
    )
    duration_fits = all(
        abs(pv - (1.0 + observed / 100.0) ** (-tenor)) <= 0.005
        for tenor, observed, pv in obs
    )
    surviving = [
        name for name, fit in (
            ("flat_10y", flat_fits),
            ("duration_matched", duration_fits),
        ) if fit
    ]
    if len(surviving) != 1:
        raise RuntimeError(
            "discount ambiguous: flat=%s duration=%s obs=%d"
            % (flat_fits, duration_fits, len(obs))
        )
    return surviving[0]


def _declared(text: str, key: str, path: pathlib.Path) -> str:
    m = re.search(r"^\s*%s\s*=\s*(\S+)\s*$" % re.escape(key), text, re.MULTILINE)
    if not m:
        raise ValueError("%s does not declare %s" % (path, key))
    return m.group(1)


def _precedence_ranks(listing: str) -> dict[str, int]:
    names = [n.strip() for n in listing.split(",") if n.strip()]
    return {name: len(names) - i for i, name in enumerate(names)}


def load_declarations(data: pathlib.Path) -> dict:
    policy_path = data / "derivation_policy.ini"
    policy = must_read(policy_path)
    must_read(data / "unit_declarations.ini")
    sources_path = data / "source_declarations.properties"
    sources = must_read(sources_path)
    reasons = json.loads(must_read(data / "reason_codes.json"))
    widths = []
    for part in _declared(sources, "fixed_width_intake.offsets", sources_path).split(","):
        name, start, end = part.split(":")
        widths.append((name, int(start), int(end)))
    return {
        "admission": _declared(policy, "valuation_instant", policy_path),
        "cutover": _parse_instant(_declared(policy, "cutover_instant", policy_path)),
        "precedence_pre": _precedence_ranks(_declared(policy, "pre_cutover", policy_path)),
        "precedence_post": _precedence_ranks(_declared(policy, "post_cutover", policy_path)),
        "fw_widths": widths,
        "reasons": reasons,
    }


def load_cycle_marks(data: pathlib.Path) -> list[tuple[str, datetime, datetime]]:
    out: list[tuple[str, datetime, datetime]] = []
    for row in parse_csv(data / "cycle_marks.csv"):
        out.append((row["cycle"], _parse_instant(row["start_instant"]), _parse_instant(row["end_instant"])))
    out.sort(key=lambda t: CYCLE_IDX.get(t[0], 999))
    return out


def instant_to_cycle(instant: datetime, cycle_marks) -> str | None:
    for cycle, start, end in cycle_marks:
        if start <= instant <= end:
            return cycle
    return None


def place_in_cycle(instant: datetime, cycle_marks) -> tuple[str | None, bool]:
    """Return (cycle, shifted). An instant inside no declared window falls in
    the gap before the next window to open, and is placed in that cycle."""
    cycle = instant_to_cycle(instant, cycle_marks)
    if cycle:
        return cycle, False
    later = [(start, c) for c, start, _end in cycle_marks if start > instant]
    if later:
        return min(later)[1], True
    return None, False


def load_curve_marks(data: pathlib.Path) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in parse_csv(data / "curve_marks.csv"):
        out[int(row["tenor_years"])] = float(row["yield_pct"])
    return out


def load_layer_capacity(data: pathlib.Path) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for row in parse_csv(data / "layer_capacity_declarations.csv"):
        out[(row["lob"], row["cycle"])] = int(row["capacity_dollars"])
    return out


def load_ceilings(data: pathlib.Path) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for row in parse_csv(data / "ceiling_register.csv"):
        out[(row["lob"], row["cycle"])] = int(row["ceiling_dollars"])
    return out


def load_reinsurer_master(data: pathlib.Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in parse_csv(data / "reinsurer_master.csv"):
        rid = row["reinsurer_id"]
        boundary = row.get("epoch_boundary", "") or ""
        out[rid] = {"name": row.get("canonical_name", rid), "epoch_boundary": boundary.strip() or None}
    return out


def load_reinsurer_alias_map(data: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in parse_csv(data / "reinsurer_alias_map.csv"):
        out[row["alias"]] = row["canonical_id"]
    return out


def load_commitments(data: pathlib.Path) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for row in parse_csv(data / "commitment_agreements.csv"):
        out[(row["reinsurer_id"], row["lob"])] = int(row["minimum_dollars"])
    return out


def load_commitment_exceptions(data: pathlib.Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for row in parse_csv(data / "commitment_exceptions.csv"):
        out.add((row["reinsurer_id"], row["lob"], row["cycle"]))
    return out


def load_priority(data: pathlib.Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in parse_csv(data / "priority_register.csv"):
        out[row["lob"]] = int(row["priority_order"])
    return out


def load_authority_roles(data: pathlib.Path) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for row in parse_csv(data / "authority_roles.csv"):
        out[(row["underwriter_id"], row["lob"])] = row["effective_start"]
    return out


def load_retractions(data: pathlib.Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in parse_csv(data / "retraction_notices.csv"):
        out[row["claim_ref"]] = {"instant": row["retraction_instant"], "reason": row["reason"]}
    return out


def load_claim_master(data: pathlib.Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in parse_csv(data / "claim_master.csv"):
        out[row["claim_id"]] = {
            "booked_lob": row["booked_lob"],
            "accident_year": int(row["accident_year"]),
            "event_id": row["event_id"],
            "segment": row["segment"],
        }
    return out


def load_endorsement_circulars(data: pathlib.Path) -> list[dict]:
    out: list[dict] = []
    for name in ("endorsement_circulars_p1.jsonl", "endorsement_circulars_p2.jsonl", "endorsement_circulars_p3.jsonl"):
        out.extend(parse_jsonl(data / name))
    return out


def load_endorsement_audit(data: pathlib.Path) -> set[str]:
    out: set[str] = set()
    pattern = re.compile(r"ENDORSE\s+claim=(\S+)")
    for name in ("endorsement_audit.log", "endorsement_audit.log.1", "endorsement_audit.log.2"):
        text = must_read(data / name)
        for line in text.splitlines():
            m = pattern.search(line)
            if m:
                out.add(m.group(1))
    return out


def load_reserve_events(data: pathlib.Path) -> list[dict]:
    out: list[dict] = []
    for name in ("reserve_events_p1.jsonl", "reserve_events_p2.jsonl", "reserve_events_p3.jsonl",
                 "reserve_events_p4.jsonl", "reserve_events_p5.jsonl"):
        out.extend(parse_jsonl(data / name))
    return out


def load_cessions(data: pathlib.Path, cycle_marks) -> list[dict]:
    out: list[dict] = []
    for name in ("cession_q1.tsv", "cession_q2.tsv", "cession_q3.tsv", "cession_q4.tsv"):
        rows = parse_tsv(data / name)
        for row in rows:
            instant = _parse_instant(row["recorded_instant"])
            cycle = instant_to_cycle(instant, cycle_marks)
            out.append({
                "claim_ref": row["claim_ref"],
                "reinsurer_raw": row["reinsurer_id"],
                "lob": row["lob"],
                "ceded_dollars": int(row["ceded_dollars"]),
                "recorded_instant": row["recorded_instant"],
                "cycle": cycle,
                "_source": name,
            })
    return out


def load_fixed_width_intake(data: pathlib.Path, widths: list[tuple[str, int, int]]) -> list[dict]:
    out: list[dict] = []
    for name in ("fixed_width_intake_h1.txt", "fixed_width_intake_h2.txt"):
        for row in parse_fixed_width(data / name, widths):
            ay_text = row["accident_year"]
            ay = int(ay_text[2:]) if ay_text.startswith("AY") else int(ay_text) if ay_text else 2023
            out.append({
                "claim_ref": row["claim_ref"],
                "lob": row["lob"],
                "ay": ay,
                "paid_to_date": int(row["paid_to_date"]) if row["paid_to_date"] else 0,
                "recorded_instant": row["recorded_instant"],
                "_source": name,
            })
    return out


def load_claim_adjustments(data: pathlib.Path) -> list[dict]:
    text = must_read(data / "claim_adjustment_log.log")
    out: list[dict] = []
    pattern = re.compile(
        r"(\S+)\s+(CLM-\d+)\s+gross=(\d+)\s+alae=(\d+)\s+settled=(\d+)\s+layer=(\S+)"
    )
    for line in text.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        out.append({
            "recorded_instant": m.group(1),
            "claim_ref": m.group(2),
            "gross": int(m.group(3)),
            "alae": int(m.group(4)),
            "settled": int(m.group(5)),
            "layer": m.group(6),
        })
    return out


def load_claim_tx(data: pathlib.Path) -> list[dict]:
    files = sorted(p for p in data.iterdir()
                   if p.name.startswith("claim_tx_") and p.suffix == ".csv")
    if not files:
        raise FileNotFoundError("no claim_tx_*.csv in %s" % data)
    rows: list[dict] = []
    for p in files:
        rows.extend(parse_claim_tx_by_position(p))
    return rows


def resolve_reinsurer_identity(
    raw_name: str, recorded_instant: str, alias_map: dict, master: dict
) -> str | None:
    stripped = (raw_name or "").strip()
    rid = alias_map.get(stripped)
    if rid is None:
        if stripped in master:
            rid = stripped
        else:
            return None
    try:
        instant = _parse_instant(recorded_instant)
    except (ValueError, AttributeError):
        return None
    info = master.get(rid, {})
    boundary = info.get("epoch_boundary")
    if boundary:
        bound_dt = _parse_instant(boundary)
        return "%s#%d" % (rid, 2 if instant >= bound_dt else 1)
    return "%s#1" % rid


def filter_admitted(rows: list[dict], admission_instant: str) -> tuple[list[dict], int]:
    bar = _parse_instant(admission_instant)
    kept: list[dict] = []
    dropped = 0
    for row in rows:
        text = row.get("recorded_instant", "")
        if not text:
            kept.append(row)
            continue
        try:
            if _parse_instant(text) > bar:
                dropped += 1
                continue
        except ValueError:
            row["_timestamp_unparseable"] = True
        kept.append(row)
    return kept, dropped


def _source_tag(name: str) -> str:
    if name.startswith("claim_tx"):
        return "claim_tx"
    if name.startswith("cession"):
        return "cession"
    if name.startswith("fixed_width_intake"):
        return "fixed_width_intake"
    return name


def collapse_cross_source(all_rows: list[dict], cutover: datetime,
                          precedence_pre: dict[str, int],
                          precedence_post: dict[str, int]) -> tuple[dict[str, dict], int, int]:
    """Group rows across all sources by claim_ref. One governing paid_to_date
    per claim selected by the precedence derivation_policy.ini declares for
    each row's side of the cutover instant. Returns:
      governing: claim_ref -> {paid_to_date, lob, ay, recorded_instant, source_tag}
      collapsed_count: number of claims with >1 source row
      disambiguated: number of claims where sources disagreed on paid_to_date
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        groups[row["claim_ref"]].append(row)
    governing: dict[str, dict] = {}
    collapsed_count = 0
    disambiguated = 0
    for ref in sorted(groups.keys()):
        g = groups[ref]
        if len(g) > 1:
            collapsed_count += 1
        best_rank = -1
        best_instant = None
        best = None
        values = set()
        for row in g:
            tag = _source_tag(row.get("_source", ""))
            try:
                inst = _parse_instant(row.get("recorded_instant", ""))
            except (ValueError, AttributeError):
                inst = None
            table = precedence_post if inst and inst >= cutover else precedence_pre
            rank = table.get(tag, 0)
            ptd = row.get("paid_to_date")
            if ptd is not None:
                values.add(ptd)
            if (rank > best_rank
                or (rank == best_rank and best_instant is not None and inst is not None and inst > best_instant)):
                best_rank = rank
                best_instant = inst
                best = row
        if len(values) > 1:
            disambiguated += 1
        if best is None:
            continue
        governing[ref] = {
            "claim_ref": ref,
            "paid_to_date": best.get("paid_to_date", 0) or 0,
            "incurred": best.get("incurred", best.get("paid_to_date", 0)) or 0,
            "lob": best.get("lob", ""),
            "reinsurer_raw": best.get("reinsurer_raw", ""),
            "recorded_instant": best.get("recorded_instant", ""),
            "source_tag": _source_tag(best.get("_source", "")),
        }
    return governing, collapsed_count, disambiguated


def apply_endorsed_circulars(
    circulars: list[dict], audit: set[str], authority: dict
) -> list[dict]:
    kept: list[dict] = []
    for c in circulars:
        if c["claim_ref"] not in audit:
            continue
        if (c["underwriter"], c["lob"]) not in authority:
            continue
        kept.append(c)
    return kept


def replay_reserve_state(events: list[dict]) -> dict[str, str]:
    state: dict[str, dict] = {}
    for ev in events:
        ref = ev["claim_ref"]
        v = ev.get("version", 0)
        if ref not in state or v > state[ref]["version"]:
            state[ref] = {"state": ev.get("state", "NOTED"), "version": v,
                          "recorded_instant": ev.get("recorded_instant", "")}
    return {ref: s["state"] for ref, s in state.items()}


def develop_chain_ladder(
    governing: dict[str, dict], claim_master: dict[str, dict], tx_rows: list[dict]
) -> tuple[dict[int, float], dict[str, int]]:
    """Volume-weighted age-to-ultimate factor per development year.

    dev_year = recorded_instant.year - accident_year. Within each development
    year, factor = sum_LOBs(incurred) / sum_LOBs(paid_to_date), bounded
    to [1.0, 2.5]. Per-claim ultimate = paid_to_date * factor[dev_year],
    where the claim's accident year is its claim_master.csv accident_year.
    """
    paid_by_dev: dict[int, int] = defaultdict(int)
    incurred_by_dev: dict[int, int] = defaultdict(int)
    for row in tx_rows:
        try:
            inst = _parse_instant(row.get("recorded_instant", ""))
            dev_year = inst.year - row.get("ay", inst.year)
        except (ValueError, AttributeError):
            dev_year = 0
        if dev_year < 0:
            dev_year = 0
        paid_by_dev[dev_year] += row.get("paid_to_date", 0)
        incurred_by_dev[dev_year] += row.get("incurred", 0)
    factors: dict[int, float] = {}
    for dev, p in sorted(paid_by_dev.items()):
        inc = incurred_by_dev.get(dev, p)
        if p <= 0:
            factors[dev] = 1.0
            continue
        f = max(1.0, min(2.5, inc / p))
        factors[dev] = _half_up(f, 6)
    ultimate: dict[str, int] = {}
    for ref, g in sorted(governing.items()):
        try:
            inst = _parse_instant(g.get("recorded_instant", ""))
            dev_year = max(0, inst.year - claim_master[ref]["accident_year"])
        except (ValueError, AttributeError):
            dev_year = 0
        f = factors.get(dev_year, 1.0)
        ultimate[ref] = _half_up_int(g.get("paid_to_date", 0) * f)
    return factors, ultimate


def pv_factor(cycle: str, curve: dict[int, float], mode: str) -> float:
    """Discount factor by cycle index. Mode duration_matched walks tenor
    marks and interpolates; flat_10y uses the 10y rate uniformly."""
    idx = CYCLE_IDX.get(cycle, 0)
    years = max(0.5, idx / 2.0 + 0.5)
    if mode == "flat_10y":
        rate = curve.get(10, 4.0) / 100.0
        return round((1.0 + rate) ** (-years), 6)
    tenors = sorted(curve.keys())
    lo = tenors[0]
    hi = tenors[-1]
    for t in tenors:
        if t <= years:
            lo = t
        if t >= years and hi == tenors[-1]:
            hi = t
            break
    if lo == hi:
        rate = curve[lo] / 100.0
    else:
        span = hi - lo
        w = (years - lo) / span if span else 0.0
        rate = (curve[lo] * (1.0 - w) + curve[hi] * w) / 100.0
    return round((1.0 + rate) ** (-years), 6)


def allocate_lob_cycle(
    ledger_rows: list[dict],
    capacity: dict[tuple[str, str], int],
    commitments: dict[tuple[str, str], int],
    exceptions: set[tuple[str, str, str]],
    ceilings: dict[tuple[str, str], int],
) -> tuple[list[dict], dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    """Allocate ceded_hours per claim within (lob, cycle) capacity.

    Steps per (lob, cycle):
      1. Pay minimums (commitments) first, up to each claim's unmet amount.
      2. Raise a shared fill level up to the greatest whole-dollar capacity.
      3. Hand out indivisible remainder one dollar at a time by sorted key.

    Returns (ledger_rows_with_ceded, remainder_dollars_per_cell,
             remainder_cycles_count_per_lob).
    """
    cell_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in ledger_rows:
        if row.get("_retracted"):
            continue
        key = (row["lob"], row["cycle"])
        cell_rows[key].append(row)
    remainder_dollars: dict[tuple[str, str], int] = {}
    for key, rows in sorted(cell_rows.items()):
        lob, cycle = key
        cap = capacity.get(key, 0)
        if False:
            for r in rows:
                r["ceded_hours"] = 0
                r["outcome"] = "ZERO"
                r["reason"] = "CAP_ZERO"
            remainder_dollars[key] = 0
            continue
        rows.sort(key=lambda r: (r["claim_ref"], r["reinsurer_canonical"] or ""))
        unmet = {r["claim_ref"]: r.get("want", 0) for r in rows}
        grant = {r["claim_ref"]: 0 for r in rows}
        pool = cap
        # 1. Honour minimums
        for r in rows:
            rid_canon = r["reinsurer_canonical"] or ""
            rid_base = rid_canon.split("#", 1)[0] if rid_canon else ""
            minimum = commitments.get((rid_base, lob), 0) if rid_base else 0
            if (rid_base, lob, cycle) in exceptions:
                minimum = 0
            share = min(minimum, unmet[r["claim_ref"]], pool)
            if share > 0:
                grant[r["claim_ref"]] += share
                unmet[r["claim_ref"]] -= share
                pool -= share
        # 2. Shared fill level
        if pool > 0 and any(u > 0 for u in unmet.values()):
            still_want = sum(u for u in unmet.values())
            if still_want > 0:
                level_floor = pool // max(1, sum(1 for u in unmet.values() if u > 0))
                for ref, u in unmet.items():
                    if u <= 0:
                        continue
                    give = min(u, level_floor)
                    grant[ref] += give
                    unmet[ref] -= give
                    pool -= give
        # 3. Indivisible remainder step, tie-break by (unmet desc, instant, reinsurer, claim_ref)
        remainder = 0
        order = sorted(rows, key=lambda r: (
            -unmet.get(r["claim_ref"], 0),
            r.get("recorded_instant", ""),
            r["reinsurer_canonical"] or "",
            r["claim_ref"],
        ))
        while pool > 0:
            progressed = False
            for r in order:
                ref = r["claim_ref"]
                if unmet[ref] > 0:
                    grant[ref] += 1
                    unmet[ref] -= 1
                    pool -= 1
                    remainder += 1
                    progressed = True
                    if pool <= 0:
                        break
            if not progressed:
                break
        remainder_dollars[key] = remainder
        for r in rows:
            r["ceded_hours"] = grant[r["claim_ref"]]
            r["outcome"] = ("FULL" if unmet[r["claim_ref"]] == 0 and r.get("want", 0) > 0
                            else "PARTIAL" if grant[r["claim_ref"]] > 0 else "ZERO")
            if r["outcome"] == "ZERO":
                r["reason"] = "NO_QUALIFIED_LAYER"
            else:
                r["reason"] = "NONE"
    remainder_cycles_count: dict[tuple[str, str], int] = defaultdict(int)
    for (lob, cycle), rem in remainder_dollars.items():
        if rem > 0:
            remainder_cycles_count[(lob, cycle)] = 1
    return ledger_rows, remainder_dollars, remainder_cycles_count


def _sha_short(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]


def build_ledger(
    governing: dict[str, dict],
    ultimate: dict[str, int],
    adjustments: list[dict],
    alae_convention: str,
    retractions: dict[str, dict],
    reinsurer_master: dict,
    alias_map: dict,
    cycle_marks: list,
    attachment_factors: dict[str, float],
    endorsements_claim_set: set[str],
    cf_params: dict,
    claim_master: dict[str, dict] | None = None,
) -> list[dict]:
    alae_by_claim: dict[str, int] = {}
    layer_by_claim: dict[str, str] = {}
    for a in adjustments:
        ref = a["claim_ref"]
        alae_by_claim[ref] = a["alae"]
        layer_by_claim[ref] = a["layer"]
    event_retention_consumed: dict[str, bool] = {}
    ledger: list[dict] = []
    for ref in sorted(governing.keys()):
        g = governing[ref]
        if ref in retractions:
            canonical = resolve_reinsurer_identity(g["reinsurer_raw"], g["recorded_instant"], alias_map, reinsurer_master)
            cycle, shifted = place_in_cycle(_parse_instant(g["recorded_instant"]), cycle_marks) if g["recorded_instant"] else (None, False)
            ledger.append({
                "claim_ref": ref, "lob": g["lob"], "cycle": cycle or "H01",
                "reinsurer_canonical": canonical, "paid_to_date": g["paid_to_date"],
                "incurred": g["incurred"],
                "ultimate": ultimate.get(ref, g["paid_to_date"]),
                "alae": 0, "layer": "retention", "want": 0,
                "recorded_instant": g["recorded_instant"],
                "outcome": "RETRACTED", "reason": "RETRACTED",
                "ceded_hours": 0,
                "_retracted": True,
                "_gap_shifted": shifted,
            })
            continue
        canonical = resolve_reinsurer_identity(g["reinsurer_raw"], g["recorded_instant"], alias_map, reinsurer_master)
        try:
            cycle, shifted = place_in_cycle(_parse_instant(g["recorded_instant"]), cycle_marks)
        except (ValueError, AttributeError):
            cycle, shifted = None, False
        if not cycle:
            cycle = "H01"
        if canonical is None:
            ledger.append({
                "claim_ref": ref, "lob": g["lob"], "cycle": cycle,
                "reinsurer_canonical": None, "paid_to_date": g["paid_to_date"],
                "incurred": g["incurred"], "ultimate": g["paid_to_date"],
                "alae": 0, "layer": "retention", "want": 0,
                "recorded_instant": g["recorded_instant"],
                "outcome": "EXCLUDED", "reason": "UNRESOLVABLE_CHAIN",
                "ceded_hours": 0,
                "_retracted": True,
                "_gap_shifted": shifted,
            })
            continue
        alae = alae_by_claim.get(ref, _half_up_int(cf_params["alae_fraction"] * g["paid_to_date"]))
        if alae_convention == "excess_only" and layer_by_claim.get(ref, "retention") == "retention":
            alae = 0
        ult = ultimate.get(ref, g["paid_to_date"])
        # Clash-cover per errata_2032-04.md: within one event, only the first
        # claim consumes the shared retention; the rest start at working_excess.
        booked_layer = layer_by_claim.get(ref, "retention")
        event_id = (claim_master or {}).get(ref, {}).get("event_id", ref)
        if booked_layer == "retention":
            if event_retention_consumed.get(event_id, False):
                booked_layer = "working_excess"
            else:
                event_retention_consumed[event_id] = True
        want = max(0, ult + alae - g["paid_to_date"])
        ledger.append({
            "claim_ref": ref,
            "lob": g["lob"],
            "cycle": cycle,
            "reinsurer_canonical": canonical,
            "paid_to_date": g["paid_to_date"],
            "incurred": g["incurred"],
            "ultimate": ult,
            "alae": alae,
            "layer": booked_layer,
            "want": want,
            "recorded_instant": g["recorded_instant"],
            "_gap_shifted": shifted,
        })
    return ledger


def compute_counterfactuals(
    governing: dict[str, dict],
    ultimate: dict[str, int],
    adjustments: list[dict],
    _claim_master: dict,
    reinsurer_master: dict,
    alias_map: dict,
    cycle_marks: list,
    attachment_factors: dict[str, float],
    retractions: dict[str, dict],
    endorsements: list[dict],
    endorsement_audit: set[str],
    authority: dict,
    curve: dict[int, float],
    discount_curve_mode: str,
    capacity: dict,
    commitments: dict,
    exceptions: set,
    ceilings: dict,
    tx_dropped_by_admission: list[dict],
    remainder_dollars: dict,
    cf_params: dict,
) -> dict:
    cf: dict = {}
    endorsed_refs = {c["claim_ref"] for c in apply_endorsed_circulars(endorsements, endorsement_audit, authority)}

    base_ledger = build_ledger(governing, ultimate, adjustments, "pro_rata",
                                retractions, reinsurer_master, alias_map, cycle_marks,
                                attachment_factors, endorsed_refs, cf_params, _claim_master)
    base_want = {r["claim_ref"]: r["want"] for r in base_ledger}
    base_alae = {r["claim_ref"]: r["alae"] for r in base_ledger}

    # R1/R2: carried-IBNR-zero. Ultimate collapses to paid_to_date, so want
    # shrinks to alae: R1 sums alae, R2 counts rows whose want exceeds alae.
    r1_total_ceded = sum(base_alae.get(ref, 0) for ref in governing if ref not in retractions)
    r1_rows_changed = sum(1 for ref, w in base_want.items()
                          if w > base_alae.get(ref, 0))
    cf["ibnr_zero_total_ceded"] = r1_total_ceded
    cf["ibnr_zero_rows_changed"] = r1_rows_changed

    # R3/R4: rival ALAE convention (excess_only ledger rebuilt).
    rival_ledger = build_ledger(governing, ultimate, adjustments, "excess_only",
                                 retractions, reinsurer_master, alias_map, cycle_marks,
                                 attachment_factors, endorsed_refs, cf_params, _claim_master)
    rival_want = {r["claim_ref"]: r["want"] for r in rival_ledger}
    r2_claims_changed = sum(1 for ref in base_want if base_want[ref] != rival_want.get(ref, 0))
    r2_total = sum(rival_want.values())
    cf["rival_alae_claims_changed"] = r2_claims_changed
    cf["rival_alae_total_ceded"] = r2_total

    # R5/R6: discount curve extended by one tenor point.
    curve_ext = dict(curve)
    curve_ext[cf_params["extra_tenor_years"]] = max(curve.values()) + cf_params["extra_tenor_increment"]
    settlements_differ = 0
    pv_ibnr_h26 = 0
    for ref in governing:
        if ref in retractions:
            continue
        g = governing[ref]
        try:
            inst = _parse_instant(g["recorded_instant"])
            cycle = place_in_cycle(inst, cycle_marks)[0] or "H01"
        except (ValueError, AttributeError):
            cycle = "H01"
        base_pv = pv_factor(cycle, curve, discount_curve_mode)
        ext_pv = pv_factor(cycle, curve_ext, discount_curve_mode)
        if base_pv != ext_pv:
            settlements_differ += 1
        pv_ibnr_h26 += int(round(base_want.get(ref, 0) * pv_factor("H26", curve, discount_curve_mode)))
    cf["tenor_extended_settlements_differ"] = settlements_differ
    cf["tenor_extended_pv_ibnr_h26"] = pv_ibnr_h26

    # R7/R8: retro offset never applied. Claims whose first adjustment-log
    # line is cat_excess get want times the retro multiplier.
    retro_offset_rows = 0
    total_year_end_ibnr = 0
    for ref, g in sorted(governing.items()):
        if ref in retractions:
            continue
        want = base_want.get(ref, 0)
        layer = next((a["layer"] for a in adjustments if a["claim_ref"] == ref), "retention")
        if layer == "cat_excess":
            retro_offset_rows += 1
            want = _half_up_int(want * cf_params["retro_multiplier"])
        total_year_end_ibnr += want
    cf["retro_never_total_ibnr"] = total_year_end_ibnr
    cf["retro_never_rows_changed"] = retro_offset_rows

    # R9/R10: remainder step observation (not a counterfactual).
    cf["remainder_dollars"] = sum(remainder_dollars.values())
    cf["remainder_cycles"] = sum(1 for v in remainder_dollars.values() if v > 0)

    # R11/R12: admission instant lifted for the claim transaction logs.
    unique_refs = sorted({r["claim_ref"] for r in tx_dropped_by_admission})
    cf["admission_lifted_claims"] = len(unique_refs)
    cf["admission_lifted_total"] = sum(r.get("paid_to_date", 0) for r in tx_dropped_by_admission)

    # R13/R14: unendorsed amendments honoured. Each dropped circular raises
    # its claim's alae; count those claims and the (lob, cycle) cells they hold.
    unendorsed_claims = {c["claim_ref"] for c in endorsements if c["claim_ref"] not in endorsed_refs}
    affected_alae = len(unendorsed_claims & set(base_alae.keys()))
    affected_cycles = set()
    for r in base_ledger:
        if r["claim_ref"] in unendorsed_claims:
            affected_cycles.add((r["lob"], r["cycle"]))
    cf["unendorsed_honoured_alae_differs"] = affected_alae
    cf["unendorsed_honoured_fill_cycles"] = len(affected_cycles)

    return cf


def write_json(out: pathlib.Path, name: str, obj: dict) -> None:
    text = json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False)
    (out / name).write_text(text + "\n")


def write_artifacts(
    out: pathlib.Path,
    run_meta: dict,
    totals: dict,
    data_quality: dict,
    methodology: dict,
    ledger: list[dict],
    capacity: dict,
    ceilings: dict,
    remainder_dollars: dict,
    cf_summary: dict,
) -> None:
    out.mkdir(parents=True, exist_ok=True)

    lob_totals: dict[str, dict] = {}
    for lob in LOBS:
        rows = [r for r in ledger if r["lob"] == lob]
        lob_totals[lob] = {
            "claims": len(rows),
            "total_paid_to_date": sum(r["paid_to_date"] for r in rows),
            "total_ultimate": sum(r["ultimate"] for r in rows),
            "total_ceded": sum(r.get("ceded_hours", 0) for r in rows),
            "total_alae": sum(r["alae"] for r in rows),
        }
    summary = {
        "run": run_meta,
        "totals": totals,
        "lobs": lob_totals,
    }
    write_json(out, "summary.json", summary)

    write_json(out, "data_quality.json", data_quality)

    write_json(out, "methodology_audit.json", methodology)

    for lob in LOBS:
        rows = [r for r in ledger if r["lob"] == lob]
        rows_sorted = sorted(rows, key=lambda r: (r["cycle"], r["reinsurer_canonical"] or "", r["claim_ref"]))
        chain = defaultdict(int)
        for r in rows_sorted:
            chain[r["cycle"]] += r["ultimate"] - r["paid_to_date"]
        lob_doc = {
            "lob": lob,
            "capacity_per_cycle": {cycle: capacity.get((lob, cycle), 0) for cycle in CYCLES},
            "ceiling_per_cycle": {cycle: ceilings.get((lob, cycle), 0) for cycle in CYCLES},
            "chain_ladder_development": {cycle: int(chain.get(cycle, 0)) for cycle in CYCLES},
            "remainder_dollars_per_cycle": {
                cycle: remainder_dollars.get((lob, cycle), 0) for cycle in CYCLES
            },
            "ledger": [
                {
                    "claim_ref": r["claim_ref"],
                    "cycle": r["cycle"],
                    "reinsurer_canonical": r["reinsurer_canonical"],
                    "paid_to_date": r["paid_to_date"],
                    "ultimate": r["ultimate"],
                    "alae": r["alae"],
                    "ceded_hours": r.get("ceded_hours", 0),
                    "layer": r["layer"],
                    "outcome": r.get("outcome", "ACTIVE"),
                    "reason": r.get("reason", "NONE"),
                }
                for r in rows_sorted
            ],
        }
        write_json(out, "lob_%s.json" % lob, lob_doc)

    ceded_by_lob = {lob: lob_totals[lob]["total_ceded"] for lob in LOBS}
    ceded_by_reinsurer: dict[str, int] = defaultdict(int)
    layer_breakdown: dict[str, int] = defaultdict(int)
    for r in ledger:
        rid = r["reinsurer_canonical"]
        if rid is None:
            continue
        ceded_by_reinsurer[rid] += r.get("ceded_hours", 0)
        layer_breakdown[r["layer"]] += r.get("ceded_hours", 0)
    treaty_doc = {
        "ceded_total": sum(ceded_by_lob.values()),
        "ceded_by_lob": ceded_by_lob,
        "ceded_by_reinsurer_canonical": dict(sorted(ceded_by_reinsurer.items())),
        "layer_breakdown": {k: layer_breakdown.get(k, 0) for k in LAYERS},
    }
    write_json(out, "treaty_working.json", treaty_doc)

    me = pathlib.Path(__file__).resolve()
    target = out / "reserving.py"
    if not (target.exists() and target.resolve() == me):
        shutil.copy(me, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="IBNR reserving with treaty settlements")
    parser.add_argument("--data", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    data: pathlib.Path = args.data
    out: pathlib.Path = args.out
    if not data.is_dir():
        raise FileNotFoundError("data directory is missing: %s" % data)
    out.mkdir(parents=True, exist_ok=True)

    policy = load_declarations(data)
    admission = policy["admission"]

    alae_convention, alae_fraction = settle_alae_convention(data)
    discount_curve_mode = settle_discount_curve(data)

    cycle_marks = load_cycle_marks(data)
    curve = load_curve_marks(data)
    capacity = load_layer_capacity(data)
    ceilings = load_ceilings(data)
    reinsurer_master = load_reinsurer_master(data)
    alias_map = load_reinsurer_alias_map(data)
    commitments = load_commitments(data)
    exceptions = load_commitment_exceptions(data)
    priority = load_priority(data)
    authority = load_authority_roles(data)
    retractions = load_retractions(data)
    claim_master = load_claim_master(data)
    attachment_factors = {"retention": 1.0}
    for row in parse_csv(data / "attachment_factors.csv"):
        attachment_factors[row["to_layer"]] = float(row["factor"])

    tx_rows = load_claim_tx(data)
    cessions = load_cessions(data, cycle_marks)
    fw_rows = load_fixed_width_intake(data, policy["fw_widths"])

    all_source_rows: list[dict] = []
    for row in tx_rows:
        all_source_rows.append({**row, "_source": row["_source"]})
    for row in cessions:
        all_source_rows.append({
            "claim_ref": row["claim_ref"],
            "reinsurer_raw": row["reinsurer_raw"],
            "lob": row["lob"],
            "paid_to_date": row["ceded_dollars"],
            "incurred": row["ceded_dollars"],
            "recorded_instant": row["recorded_instant"],
            "_source": row["_source"],
        })
    for row in fw_rows:
        all_source_rows.append({
            "claim_ref": row["claim_ref"],
            "reinsurer_raw": "",
            "lob": row["lob"],
            "ay": row["ay"],
            "paid_to_date": row["paid_to_date"],
            "incurred": row["paid_to_date"],
            "recorded_instant": row["recorded_instant"],
            "_source": row["_source"],
        })

    admitted_rows, dropped_count = filter_admitted(all_source_rows, admission)

    tx_dropped = [r for r in all_source_rows if r not in admitted_rows]

    governing, collapsed_count, disambiguated = collapse_cross_source(
        admitted_rows, policy["cutover"], policy["precedence_pre"], policy["precedence_post"])

    circulars = load_endorsement_circulars(data)
    audit = load_endorsement_audit(data)
    endorsed_circulars = apply_endorsed_circulars(circulars, audit, authority)

    reserve_events = load_reserve_events(data)
    state_by_claim = replay_reserve_state(reserve_events)

    adjustments = load_claim_adjustments(data)
    tx_dropped_claim_rows = [r for r in tx_dropped if r["_source"].startswith("claim_tx")]

    admitted_tx_rows = [r for r in tx_rows if r in admitted_rows]
    _factors, ultimate = develop_chain_ladder(governing, claim_master, admitted_tx_rows)

    cf_params = load_counterfactual_parameters(data)
    cf_params["alae_fraction"] = alae_fraction

    endorsed_refs = {c["claim_ref"] for c in endorsed_circulars}
    ledger = build_ledger(
        governing, ultimate, adjustments, alae_convention,
        retractions, reinsurer_master, alias_map, cycle_marks,
        attachment_factors, endorsed_refs, cf_params, claim_master,
    )

    ledger, remainder_dollars, _rc_count = allocate_lob_cycle(
        ledger, capacity, commitments, exceptions, ceilings,
    )

    cf_summary = compute_counterfactuals(
        governing, ultimate, adjustments, claim_master,
        reinsurer_master, alias_map, cycle_marks, attachment_factors,
        retractions, circulars, audit, authority,
        curve, discount_curve_mode,
        capacity, commitments, exceptions, ceilings,
        tx_dropped_claim_rows, remainder_dollars, cf_params,
    )

    unresolved = sum(1 for r in ledger if r["reinsurer_canonical"] is None)
    retracted_count = sum(1 for r in ledger if r.get("outcome") == "RETRACTED")
    totals = {
        "claims_admitted": len(ledger),
        "claims_dropped_late": dropped_count,
        "claims_retracted": retracted_count,
        "unresolved_reinsurer": unresolved,
        "cross_source_collapsed": collapsed_count,
        "fold_disambiguated": disambiguated,
        "total_paid_to_date": sum(r["paid_to_date"] for r in ledger),
        "total_incurred": sum(r["incurred"] for r in ledger),
        "total_ultimate": sum(r["ultimate"] for r in ledger),
        "total_alae": sum(r["alae"] for r in ledger),
        "total_ceded": sum(r.get("ceded_hours", 0) for r in ledger),
        "total_ibnr": sum(r["ultimate"] - r["paid_to_date"] for r in ledger),
    }
    log_continuations = sum(
        1 for name in ("endorsement_audit.log.1", "endorsement_audit.log.2")
        if (data / name).is_file()
    )
    paren_negatives = 0
    import re as _re
    _paren_num = _re.compile(r"\(\d[\d,]*\)")
    for name in sorted(data.iterdir()):
        if name.suffix in {".csv", ".tsv"}:
            paren_negatives += sum(1 for line in name.read_text().splitlines()
                                     if _paren_num.search(line))
    block_unit_rows = sum(
        1 for r in fw_rows if r.get("paid_to_date", 0) > 0 and r["paid_to_date"] % 1000 == 0
    )
    data_quality = {
        "late_recorded": dropped_count,
        "duplicate_identical": max(0, collapsed_count - disambiguated),
        "duplicate_conflicting": disambiguated,
        "cross_source_collapsed": collapsed_count,
        "fold_disambiguated": disambiguated,
        "gap_shifted": sum(1 for r in ledger if r.get("_gap_shifted")),
        "log_continuations": log_continuations,
        "unknown_reinsurer_rows": unresolved,
        "out_of_horizon_rows": dropped_count,
        "block_unit_rows": block_unit_rows,
        "paren_negatives": paren_negatives,
        "restatement_gaps": sum(1 for r in tx_rows if r["paid_to_date"] != r["paid_to_date_restated"]),
    }
    methodology = {
        "settlement": {
            "alae_convention": alae_convention,
            "discount_curve": discount_curve_mode,
        },
        "attachment": {
            "authority_file": "errata_2032-04.md",
            "attachment_rule": "clash_cover_per_event",
        },
        "endorsements": {
            "circulars_total": len(circulars),
            "circulars_endorsed": len(endorsed_circulars),
            "audit_entries": len(audit),
        },
        "reserve_state": {
            "events_total": len(reserve_events),
            "claims_with_state": len(state_by_claim),
        },
        "chain_ladder": {
            "factors_bounded": "[1.0, 2.5]",
            "development_cells_total": len({(r["lob"], r["cycle"]) for r in ledger}),
        },
        "allocation": {
            "priority_order": priority,
            "exceptions_count": len(exceptions),
        },
    }
    run_meta = {
        "admission_instant": admission,
        "alae_convention": alae_convention,
        "discount_curve": discount_curve_mode,
        "lobs": LOBS,
        "cycles_total": len(CYCLES),
        "attachment_authority": "errata_2032-04.md",
    }

    write_artifacts(
        out, run_meta, totals, data_quality, methodology,
        ledger, capacity, ceilings, remainder_dollars, cf_summary,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
