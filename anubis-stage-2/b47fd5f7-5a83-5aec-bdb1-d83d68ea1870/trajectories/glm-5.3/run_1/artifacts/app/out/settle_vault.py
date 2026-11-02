#!/usr/bin/env python3
"""Settle an Emberforge crafting season.

Usage: settle_vault.py [data_dir] [out_dir]

Reads the twelve tables and documents that record a season, settles the ledger
under the rulebooks and the council's drawn conventions, and writes the
settled season's records into the output directory.
"""

import csv
import json
import os
import sys
from collections import deque

DEFAULT_DATA_DIR = '/app/data'
DEFAULT_OUT_DIR = '/app/out'

REQUIRED_FILES = (
    'patch_calendar.csv',
    'reagent_registry.csv',
    'artifact_catalogue.csv',
    'recipe_editions.csv',
    'workshop_registry.csv',
    'smith_identity_events.csv',
    'crafting_ledger.csv',
    'reagent_acquisitions.csv',
    'vault_opening.csv',
    'requisitions.json',
    'season_charter.json',
    'council_rulings.json',
)

# Register of season conventions: the tables the council may draw from.

RETURN_SCHEDULES = {
    'RS-A': {1: 40, 2: 50, 3: 60},
    'RS-B': {1: 45, 2: 55, 3: 65},
    'RS-C': {1: 50, 2: 60, 3: 70},
    'RS-D': {1: 35, 2: 50, 3: 65},
    'RS-E': {1: 55, 2: 55, 3: 55},
    'RS-F': {1: 30, 2: 45, 3: 60},
    'RS-G': {1: 60, 2: 50, 3: 40},
}
REDUCTIONS = ('floor', 'ceil', 'half-up', 'half-down', 'half-even')
OPERATOR_ORDERS = ('FGS', 'FSG', 'GFS', 'GSF', 'SFG', 'SGF')
SCARCITY_REFERENCES = ('opening', 'opening-plus-acquired', 'consumed', 'acquired')


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def reduce_whole(convention, numerator, denominator):
    """Reduce numerator/denominator to a whole number under a convention."""
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if convention == 'floor':
        return numerator // denominator
    if convention == 'ceil':
        return -((-numerator) // denominator)
    whole, rest = divmod(numerator, denominator)
    rest *= 2
    if rest > denominator:
        return whole + 1
    if rest < denominator:
        return whole
    if convention == 'half-up':
        return whole + 1
    if convention == 'half-down':
        return whole
    return whole if whole % 2 == 0 else whole + 1


def as_int(value, default=0):
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError:
            return default
        if number != number or number in (float('inf'), float('-inf')):
            return default
        return int(round(number)) if abs(number - round(number)) < 1e-9 else default


def as_bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in ('1', 'true', 'yes', 'y', 't', 'on', 'x')


def truthy_text(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'y', 't', 'on', 'x', 'recalled')


def read_rows(path):
    with open(path, 'r', newline='', encoding='utf-8-sig') as handle:
        rows = []
        for row in csv.DictReader(handle):
            clean = {}
            for key, value in row.items():
                if key is None:
                    continue
                clean[key.strip()] = (value or '').strip()
            rows.append(clean)
        return rows


def read_json(path):
    with open(path, 'r', encoding='utf-8-sig') as handle:
        return json.load(handle)


def chart_lookup(table, key):
    """Look a charter table up by either its string or whole-number key."""
    if not isinstance(table, dict):
        return None
    if key in table:
        return table[key]
    text = str(key)
    if text in table:
        return table[text]
    for candidate, value in table.items():
        if str(candidate) == text:
            return value
    return None


# --------------------------------------------------------------------------- #
# the council's draw
# --------------------------------------------------------------------------- #

def infer_draw(rulings):
    """Return the one draw of the register that every ruling of the year agrees with."""
    charge_rulings = rulings.get('charge_rulings') or []
    return_rulings = rulings.get('return_rulings') or []
    scarcity_rulings = rulings.get('scarcity_rulings') or []
    consistent = []
    for schedule_name in sorted(RETURN_SCHEDULES):
        schedule = RETURN_SCHEDULES[schedule_name]
        for convention in REDUCTIONS:
            for order in OPERATOR_ORDERS:
                for reference in SCARCITY_REFERENCES:
                    agreed = True
                    for ruling in charge_rulings:
                        value = as_int(ruling.get('base_value'))
                        percents = {
                            'F': as_int(ruling.get('family_percent')),
                            'G': as_int(ruling.get('grade_percent')),
                            'S': as_int(ruling.get('scarcity_percent')),
                        }
                        for operator in order:
                            value = reduce_whole(
                                convention, value * percents[operator], 100)
                        if value != as_int(ruling.get('charge_ember')):
                            agreed = False
                            break
                    if not agreed:
                        continue
                    for ruling in return_rulings:
                        tier = as_int(ruling.get('tier'))
                        committed = as_int(ruling.get('committed_units'))
                        rate = chart_lookup(schedule, tier)
                        if rate is None:
                            rate = 0
                        returned = reduce_whole(
                            convention, committed * rate, 100)
                        if returned != as_int(ruling.get('returned_units')):
                            agreed = False
                            break
                    if not agreed:
                        continue
                    for ruling in scarcity_rulings:
                        opening = as_int(ruling.get('opening_units'))
                        acquired = as_int(ruling.get('acquired_units'))
                        called_for = as_int(ruling.get('called_for_units'))
                        consumed = as_int(ruling.get('consumed_units'))
                        ceiling = as_int(ruling.get('scarcity_ceiling'))
                        if reference == 'opening':
                            base = opening
                        elif reference == 'opening-plus-acquired':
                            base = opening + acquired
                        elif reference == 'consumed':
                            base = called_for
                        else:
                            base = acquired
                        if base <= 0:
                            index = 0
                        else:
                            index = reduce_whole(convention, consumed * 100, base)
                            if index > ceiling:
                                index = ceiling
                        if index != as_int(ruling.get('scarcity_index')):
                            agreed = False
                            break
                    if agreed:
                        consistent.append((schedule_name, convention, order, reference))
    if not consistent:
        # No draw agrees with the rulings; fall back on the register's first entry.
        return ('RS-A', 'floor', 'FGS', 'opening')
    return consistent[0]


# --------------------------------------------------------------------------- #
# smith identity
# --------------------------------------------------------------------------- #

class SmithIdentity:
    """Handles, renames, merges, retirements and reinstatements (rulebook I)."""

    def __init__(self, event_rows):
        events = []
        for row in event_rows:
            day = as_int(row.get('day'))
            kind = (row.get('kind') or '').strip().lower()
            from_ref = (row.get('from_ref') or '').strip()
            to_ref = (row.get('to_ref') or '').strip()
            event_id = row.get('event_id') or ''
            events.append((day, event_id, kind, from_ref, to_ref))
        events.sort(key=lambda item: (item[0], item[1]))
        self.events = events
        self.follow_events = {}
        for day, _event_id, kind, from_ref, to_ref in events:
            if kind in ('rename', 'merge') and from_ref:
                self.follow_events.setdefault(from_ref, []).append((day, to_ref))
        self.canon_cache = {}
        self.retired_from = {}
        self.reinstated_at = {}
        self.registered_on = {}
        for day, _event_id, kind, from_ref, _to_ref in events:
            if kind == 'retire' and from_ref:
                identity = self.canonical(from_ref, day)
                known = self.retired_from.get(identity)
                if known is None or day < known:
                    self.retired_from[identity] = day
            elif kind == 'register' and from_ref:
                identity = self.canonical(from_ref, day)
                known = self.registered_on.get(identity)
                if known is None or day < known:
                    self.registered_on[identity] = day
        for day, _event_id, kind, from_ref, _to_ref in events:
            if kind == 'register' and from_ref:
                identity = self.canonical(from_ref, day)
                retired = self.retired_from.get(identity)
                if retired is not None and day > retired:
                    known = self.reinstated_at.get(identity)
                    if known is None or day < known:
                        self.reinstated_at[identity] = day

    def canonical(self, handle, day):
        """The canonical identity a handle resolves to on a day (I2, I3)."""
        cache_key = (handle, day)
        cached = self.canon_cache.get(cache_key)
        if cached is not None:
            return cached
        current = handle
        seen = set()
        for _ in range(len(self.events) + 2):
            nxt = None
            for event_day, to_ref in self.follow_events.get(current, ()):
                if event_day <= day:
                    nxt = to_ref
                else:
                    break
            if nxt is None or nxt == current or nxt in seen:
                break
            seen.add(current)
            current = nxt
        self.canon_cache[cache_key] = current
        return current

    def is_retired(self, identity, day):
        """True when a canonical identity is retired as of a day (I4, I6)."""
        retired = self.retired_from.get(identity)
        if retired is None or day < retired:
            return False
        reinstated = self.reinstated_at.get(identity)
        if reinstated is not None and day >= reinstated:
            return False
        return True


# --------------------------------------------------------------------------- #
# the season's tables
# --------------------------------------------------------------------------- #

class Season:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.patch_calendar = read_rows(os.path.join(data_dir, 'patch_calendar.csv'))
        self.reagent_rows = read_rows(os.path.join(data_dir, 'reagent_registry.csv'))
        self.artifact_rows = read_rows(os.path.join(data_dir, 'artifact_catalogue.csv'))
        self.edition_rows = read_rows(os.path.join(data_dir, 'recipe_editions.csv'))
        self.workshop_rows = read_rows(os.path.join(data_dir, 'workshop_registry.csv'))
        self.identity_rows = read_rows(os.path.join(data_dir, 'smith_identity_events.csv'))
        self.ledger_rows = read_rows(os.path.join(data_dir, 'crafting_ledger.csv'))
        self.acquisition_rows = read_rows(os.path.join(data_dir, 'reagent_acquisitions.csv'))
        self.opening_rows = read_rows(os.path.join(data_dir, 'vault_opening.csv'))
        self.requisition_doc = read_json(os.path.join(data_dir, 'requisitions.json'))
        self.charter = read_json(os.path.join(data_dir, 'season_charter.json'))
        self.rulings = read_json(os.path.join(data_dir, 'council_rulings.json'))
        self.identity = SmithIdentity(self.identity_rows)
        self._load_patches()
        self._load_reagents()
        self._load_artifacts()
        self._load_editions()
        self._load_workshops()
        self._load_ledger()
        self._load_acquisitions()
        self._load_requisitions()

    # -- patches ------------------------------------------------------------

    def _load_patches(self):
        patches = []
        for row in self.patch_calendar:
            patch_id = row.get('patch_id')
            if not patch_id:
                continue
            patches.append({
                'patch_id': patch_id,
                'opens_day': as_int(row.get('opens_day')),
                'closes_day': as_int(row.get('closes_day')),
                'ordinal': as_int(row.get('ordinal')),
            })
        patches.sort(key=lambda item: (item['ordinal'], item['patch_id']))
        self.patches = patches
        self.patch_by_id = {item['patch_id']: item for item in patches}
        self.patch_of_day = {}
        for item in patches:
            for day in range(item['opens_day'], item['closes_day'] + 1):
                self.patch_of_day[day] = item
        self.patch_count = len(patches)
        self.first_day = min((item['opens_day'] for item in patches), default=0)
        self.last_day = max((item['closes_day'] for item in patches), default=0)

    # -- reagents -----------------------------------------------------------

    def _load_reagents(self):
        self.reagents = {}
        self.reagent_ids = []
        for row in self.reagent_rows:
            reagent_id = row.get('reagent_id')
            if not reagent_id:
                continue
            if reagent_id in self.reagents:
                continue
            retired_patch = (row.get('retired_patch') or '').strip()
            retired_day = None
            if retired_patch and retired_patch in self.patch_by_id:
                retired_day = self.patch_by_id[retired_patch]['opens_day']
            self.reagents[reagent_id] = {
                'reagent_id': reagent_id,
                'grade': as_int(row.get('grade')),
                'family': row.get('family') or '',
                'scarce': as_bool(row.get('scarce')),
                'retired_patch': retired_patch,
                'retired_day': retired_day,
            }
            self.reagent_ids.append(reagent_id)
        self.reagent_ids.sort()
        self.scarce_ids = [rid for rid in self.reagent_ids if self.reagents[rid]['scarce']]
        self.opening = {}
        for row in self.opening_rows:
            reagent_id = row.get('reagent_id')
            if not reagent_id:
                continue
            self.opening[reagent_id] = as_int(row.get('opening_units'))
        for reagent_id in self.reagent_ids:
            self.opening.setdefault(reagent_id, 0)

    # -- artifacts ----------------------------------------------------------

    def _load_artifacts(self):
        self.artifacts = {}
        for row in self.artifact_rows:
            artifact_id = row.get('artifact_id')
            if not artifact_id or artifact_id in self.artifacts:
                continue
            self.artifacts[artifact_id] = {
                'artifact_id': artifact_id,
                'family': row.get('family') or '',
                'tier': as_int(row.get('tier')),
                'base_charge': as_int(row.get('base_charge')),
                'introduced_patch': row.get('introduced_patch') or '',
            }

    # -- recipe editions ----------------------------------------------------

    def _load_editions(self):
        groups = {}
        for row in self.edition_rows:
            artifact_id = row.get('artifact_id')
            if not artifact_id:
                continue
            edition_key = row.get('edition') or ''
            from_patch = row.get('from_patch') or ''
            try:
                edition_number = int(edition_key)
            except ValueError:
                edition_number = 0
            recalled = truthy_text(row.get('recalled'))
            group = groups.setdefault(artifact_id, {})
            key = (from_patch, edition_number, edition_key)
            edition = group.get(key)
            if edition is None:
                from_ordinal = None
                patch = self.patch_by_id.get(from_patch)
                if patch is not None:
                    from_ordinal = patch['ordinal']
                edition = {
                    'artifact_id': artifact_id,
                    'edition': edition_number,
                    'from_patch': from_patch,
                    'from_ordinal': from_ordinal,
                    'recalled': recalled,
                    'lines': [],
                }
                group[key] = edition
            elif recalled:
                edition['recalled'] = True
            reagent_id = row.get('reagent_id')
            units = as_int(row.get('units_per_craft'))
            if reagent_id:
                edition['lines'].append((reagent_id, units))
        self.editions_by_artifact = {}
        for artifact_id, group in groups.items():
            editions = [edition for edition in group.values() if not edition['recalled']]
            editions = [edition for edition in editions if edition['from_ordinal'] is not None]
            for edition in editions:
                edition['lines'].sort(key=lambda line: line[0])
                grades = [self.reagents[line[0]]['grade']
                          for line in edition['lines'] if line[0] in self.reagents]
                edition['max_grade'] = max(grades) if grades else 0
            editions.sort(key=lambda item: (item['from_ordinal'], item['edition'], item['from_patch']))
            self.editions_by_artifact[artifact_id] = editions

    def edition_for(self, artifact_id, day):
        """The edition in force for an artifact on a day, or None (E1, E2, E4)."""
        if artifact_id not in self.artifacts:
            return None
        patch = self.patch_of_day.get(day)
        if patch is None:
            return None
        ordinal = patch['ordinal']
        editions = self.editions_by_artifact.get(artifact_id)
        if not editions:
            return None
        chosen = None
        for edition in editions:
            if edition['from_ordinal'] <= ordinal:
                chosen = edition
            else:
                break
        return chosen

    # -- workshops ----------------------------------------------------------

    def _load_workshops(self):
        self.workshops = {}
        for row in self.workshop_rows:
            workshop_id = row.get('workshop_id')
            if not workshop_id or workshop_id in self.workshops:
                continue
            closed_text = (row.get('closed_day') or '').strip()
            self.workshops[workshop_id] = {
                'workshop_id': workshop_id,
                'charter_id': row.get('charter_id') or '',
                'guild_id': row.get('guild_id') or '',
                'opened_day': as_int(row.get('opened_day')),
                'closed_day': as_int(closed_text) if closed_text else None,
                'charter_tier': as_int(row.get('charter_tier')),
                'provisional': as_bool(row.get('provisional'))
                or as_bool(row.get('provisional_charter'))
                or truthy_text(row.get('provisional_flag')),
            }
        self.charge_caps = {}
        tier_caps = {}
        table = self.charter.get('tier_charge_cap') if isinstance(self.charter, dict) else None
        if isinstance(table, dict):
            for key, value in table.items():
                tier_caps[key] = as_int(value)
        extension_patch = None
        for key in ('extension_patch', 'extension_patch_id', 'extension'):
            value = self.charter.get(key) if isinstance(self.charter, dict) else None
            if isinstance(value, str) and value in self.patch_by_id:
                extension_patch = value
                break
        if extension_patch is not None:
            allowance = None
            for key in ('tier_extension_allowance', 'tier_extension', 'extension_allowance'):
                candidate = self.charter.get(key) if isinstance(self.charter, dict) else None
                if isinstance(candidate, dict):
                    allowance = candidate
                    break
            if isinstance(allowance, dict):
                for key in list(tier_caps):
                    value = chart_lookup(allowance, key)
                    if value is not None:
                        tier_caps[key] = tier_caps[key] + as_int(value)
        for workshop in self.workshops.values():
            tier = workshop['charter_tier']
            cap = chart_lookup(tier_caps, tier)
            if cap is None:
                cap = 0
            cap = as_int(cap)
            if workshop['provisional']:
                cap = cap // 2
            self.charge_caps[workshop['workshop_id']] = cap
        self.scope = {}
        for workshop_id, workshop in self.workshops.items():
            in_scope = (
                workshop['opened_day'] <= self.first_day
                and (workshop['closed_day'] is None or workshop['closed_day'] >= self.last_day)
                and workshop['charter_tier'] >= 2
            )
            self.scope[workshop_id] = in_scope
        self.scope_ids = sorted([wid for wid, ok in self.scope.items() if ok])
        self.guild_of = {wid: self.workshops[wid]['guild_id'] for wid in self.workshops}
        guilds = []
        for wid in self.scope_ids:
            guild_id = self.guild_of[wid]
            if guild_id and guild_id not in guilds:
                guilds.append(guild_id)
        self.guild_ids = sorted(guilds)
        self.guild_workshops = {}
        for guild_id in self.guild_ids:
            self.guild_workshops[guild_id] = [
                wid for wid in self.scope_ids if self.guild_of[wid] == guild_id]

    def workshop_in_scope(self, workshop_id):
        return bool(self.scope.get(workshop_id))

    # -- ledger -------------------------------------------------------------

    def _load_ledger(self):
        entries = []
        for row in self.ledger_rows:
            entry_id = row.get('entry_id') or ''
            op = (row.get('op') or '').strip().lower()
            if op != 'salvage':
                op = 'forge'
            entries.append({
                'entry_id': entry_id,
                'patch_id': row.get('patch_id') or '',
                'day': as_int(row.get('day')),
                'workshop_id': row.get('workshop_id') or '',
                'smith_ref': row.get('smith_ref') or '',
                'op': op,
                'artifact_id': row.get('artifact_id') or '',
                'units': as_int(row.get('units')),
                'forge_ref': row.get('forge_ref') or '',
            })
        entries.sort(key=lambda item: (item['day'], item['entry_id']))
        self.entries = entries
        self.entry_by_id = {item['entry_id']: item for item in entries}
        self.patch_of_entry = {}
        for entry in entries:
            self.patch_of_entry[entry['entry_id']] = self.patch_of_day.get(entry['day'])

    # -- acquisitions -------------------------------------------------------

    def _load_acquisitions(self):
        acquisitions = []
        for row in self.acquisition_rows:
            day = as_int(row.get('day'))
            units = as_int(row.get('units'))
            reagent_id = row.get('reagent_id') or ''
            if reagent_id not in self.reagents:
                continue
            patch = self.patch_of_day.get(day)
            if patch is None or units <= 0:
                continue
            acquisitions.append({
                'acq_id': row.get('acq_id') or '',
                'patch_id': patch['patch_id'],
                'day': day,
                'reagent_id': reagent_id,
                'units': units,
                'workshop_id': row.get('workshop_id') or '',
            })
        acquisitions.sort(key=lambda item: (item['day'], item['acq_id']))
        self.acquisitions = acquisitions

    # -- requisitions -------------------------------------------------------

    def _load_requisitions(self):
        raw = []
        doc = self.requisition_doc
        if isinstance(doc, dict):
            for key in ('requisitions', 'list', 'items'):
                if isinstance(doc.get(key), list):
                    raw = doc[key]
                    break
        elif isinstance(doc, list):
            raw = doc
        requisitions = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            requisitions.append({
                'req_id': str(item.get('req_id') or '').strip(),
                'workshop_id': str(item.get('workshop_id') or '').strip(),
                'reagent_id': str(item.get('reagent_id') or '').strip(),
                'priority': as_int(item.get('priority')),
                'min_units': as_int(item.get('min_units')),
                'units_requested': as_int(item.get('units_requested')),
            })
        requisitions.sort(key=lambda item: item['req_id'])
        self.requisitions = requisitions


# --------------------------------------------------------------------------- #
# settlement
# --------------------------------------------------------------------------- #

class Settlement:
    """One settled state of a season, under one assignment of scarcity indices."""

    def __init__(self, season, conventions, indices):
        self.season = season
        self.conventions = conventions
        self.indices = indices
        self._prepare()
        self._run()

    # -- preparation --------------------------------------------------------

    def _prepare(self):
        season = self.season
        identity = season.identity
        self.return_schedule = conventions_return(self.conventions)
        self.reduction = conventions_reduction(self.conventions)
        self.operator_order = conventions_order(self.conventions)
        self.reference = conventions_reference(self.conventions)
        self.grade_step = as_int(season.charter.get('grade_step')) \
            if isinstance(season.charter, dict) else 0
        self.family_multiplier = {}
        if isinstance(season.charter, dict):
            table = season.charter.get('family_multiplier')
            if isinstance(table, dict):
                self.family_multiplier = table
        # acquisitions credited by day
        self.acq_by_day = {}
        for acquisition in season.acquisitions:
            self.acq_by_day.setdefault(acquisition['day'], []).append(acquisition)
        # per entry preparation: canonical smith, early findings, governing edition
        self.prepared = []
        for entry in season.entries:
            record = dict(entry)
            day = entry['day']
            smith = identity.canonical(entry['smith_ref'], day)
            record['canonical_smith'] = smith
            findings = []
            if not season.workshop_in_scope(entry['workshop_id']):
                findings.append(('OUT_OF_SCOPE_WORKSHOP', entry['workshop_id']))
            if identity.is_retired(smith, day):
                findings.append(('RETIRED_SMITH', smith))
            source = None
            if entry['op'] == 'salvage':
                referenced = season.entry_by_id.get(entry['forge_ref'])
                if referenced is None or referenced.get('op') != 'forge':
                    findings.append(('MISSING_FORGE_REF', entry['forge_ref']))
                else:
                    source = referenced
            edition = None
            if entry['op'] == 'forge':
                edition = season.edition_for(entry['artifact_id'], day)
                if edition is None:
                    findings.append(('UNRESOLVED_EDITION', entry['artifact_id']))
            else:
                if entry['artifact_id'] not in season.artifacts:
                    findings.append(('UNRESOLVED_EDITION', entry['artifact_id']))
                elif source is not None:
                    edition = season.edition_for(source['artifact_id'], source['day'])
                    if edition is None:
                        findings.append(('UNRESOLVED_EDITION', entry['artifact_id']))
                else:
                    findings.append(('UNRESOLVED_EDITION', entry['artifact_id']))
            record['edition'] = edition
            record['source'] = source
            record['early_findings'] = findings
            record['retired_reagents'] = []
            record['draw'] = {}
            record['returns'] = {}
            record['charge'] = 0
            if edition is not None:
                retired = []
                for reagent_id, units_per_craft in edition['lines']:
                    reagent = season.reagents.get(reagent_id)
                    if reagent is None:
                        continue
                    retired_day = reagent['retired_day']
                    if retired_day is not None and day >= retired_day:
                        retired.append(reagent_id)
                record['retired_reagents'] = sorted(retired)
                if entry['op'] == 'forge':
                    draw = {}
                    for reagent_id, units_per_craft in edition['lines']:
                        if reagent_id not in season.reagents:
                            continue
                        draw[reagent_id] = units_per_craft * entry['units']
                    record['draw'] = draw
                else:
                    returns = {}
                    if source is not None:
                        artifact = season.artifacts.get(source['artifact_id'])
                        tier = artifact['tier'] if artifact else 0
                        rate = chart_lookup(self.return_schedule, tier)
                        if rate is None:
                            rate = 0
                        for reagent_id, units_per_craft in edition['lines']:
                            if reagent_id not in season.reagents:
                                continue
                            committed = units_per_craft * source['units']
                            returns[reagent_id] = reduce_whole(
                                self.reduction, committed * rate, 100)
                    record['returns'] = returns
            record['artifact_family'] = ''
            record['artifact_tier'] = 0
            governing_artifact = entry['artifact_id'] if entry['op'] == 'forge' else (
                source['artifact_id'] if source is not None else entry['artifact_id'])
            artifact = season.artifacts.get(governing_artifact)
            if artifact is not None:
                record['artifact_family'] = artifact['family']
                record['artifact_tier'] = artifact['tier']
            if entry['op'] == 'salvage' and source is not None:
                smith_of_source = identity.canonical(source['smith_ref'], source['day'])
                record['source_smith'] = smith_of_source
            else:
                record['source_smith'] = None
            record['relief'] = False
            if entry['op'] == 'forge' and edition is not None:
                registered = identity.registered_on.get(smith)
                if registered is not None:
                    patch = season.patch_of_day.get(registered)
                    entry_patch = season.patch_of_day.get(day)
                    if patch is not None and entry_patch is not None \
                            and patch['patch_id'] == entry_patch['patch_id']:
                        record['relief'] = True
            self.prepared.append(record)

    # -- charge -------------------------------------------------------------

    def charge_of(self, record):
        season = self.season
        edition = record['edition']
        artifact = season.artifacts.get(record['artifact_id'])
        if artifact is None or edition is None:
            return 0
        value = artifact['base_charge']
        family_percent = as_int(chart_lookup(self.family_multiplier, artifact['family']) or 0)
        grade_percent = 100 + self.grade_step * edition['max_grade']
        scarcity_percent = 100
        for reagent_id, _units in edition['lines']:
            reagent = season.reagents.get(reagent_id)
            if reagent is not None and reagent['scarce']:
                scarcity_percent += self.indices.get(reagent_id, 0)
        percents = {'F': family_percent, 'G': grade_percent, 'S': scarcity_percent}
        for operator in self.operator_order:
            value = reduce_whole(self.reduction, value * percents[operator], 100)
        charge = value * record['units']
        if record['relief']:
            charge = reduce_whole(self.reduction, charge * 80, 100)
        return charge

    # -- the settlement pass ------------------------------------------------

    def _run(self):
        season = self.season
        reagent_ids = season.reagent_ids
        self.vault = dict(season.opening)
        self.findings = []
        self.settled = {}
        self.accrued = {wid: 0 for wid in season.workshops}
        self.closed = {wid: False for wid in season.workshops}
        self.workshop_stats = {}
        for wid in season.scope_ids:
            self.workshop_stats[wid] = {
                'entries_admitted': 0,
                'entries_rejected': 0,
                'charge_ember': 0,
                'cap_reached': False,
                'smiths': {},
                'flow': {},
            }
        self.smiths_by_workshop = {}
        for record in self.prepared:
            wid = record['workshop_id']
            if season.workshop_in_scope(wid):
                self.smiths_by_workshop.setdefault(wid, set()).add(record['canonical_smith'])
        patch_index = {patch['patch_id']: position
                       for position, patch in enumerate(season.patches)}
        self.patch_flow = [{} for _ in season.patches]
        self.patch_residual = [0] * len(season.patches)
        self.total_acquired = {rid: 0 for rid in reagent_ids}
        self.total_returned = {rid: 0 for rid in reagent_ids}
        self.total_consumed = {rid: 0 for rid in reagent_ids}
        self.called_for = {rid: 0 for rid in reagent_ids}
        self.live = {}
        self.credited_forges = {}
        self.charge_of_entry = {}
        acquisition_days = sorted(self.acq_by_day)
        acquisition_cursor = [0]
        vault = self.vault

        def credit_acquisitions(day):
            while acquisition_cursor[0] < len(acquisition_days) \
                    and acquisition_days[acquisition_cursor[0]] <= day:
                for acquisition in self.acq_by_day[acquisition_days[acquisition_cursor[0]]]:
                    reagent_id = acquisition['reagent_id']
                    vault[reagent_id] = vault.get(reagent_id, 0) + acquisition['units']
                    self.total_acquired[reagent_id] += acquisition['units']
                    position = patch_index[acquisition['patch_id']]
                    flow = self.patch_flow[position]
                    cell = flow.get(reagent_id)
                    if cell is None:
                        cell = [0, 0, 0]
                        flow[reagent_id] = cell
                    cell[0] += acquisition['units']
                acquisition_cursor[0] += 1

        credit_acquisitions(season.first_day)
        for record in self.prepared:
            wid = record['workshop_id']
            entry_id = record['entry_id']
            patch = season.patch_of_day.get(record['day'])
            position = patch_index[patch['patch_id']] if patch is not None else None
            if acquisition_days and record['day'] > season.first_day:
                credit_acquisitions(record['day'])
            if record['early_findings']:
                for code, detail in record['early_findings']:
                    self.findings.append((entry_id, code, detail))
                self.settled[entry_id] = False
                if wid in self.workshop_stats:
                    self.workshop_stats[wid]['entries_rejected'] += 1
                continue
            if record['op'] == 'forge':
                stats = self.workshop_stats.get(wid)
                findings = []
                charge = self.charge_of(record)
                cap = self.season.charge_caps.get(wid, 0)
                if self.closed.get(wid) or self.accrued.get(wid, 0) + charge > cap:
                    findings.append(('CAP_REACHED', wid))
                    if not self.closed.get(wid):
                        self.closed[wid] = True
                        if stats is not None:
                            stats['cap_reached'] = True
                if record['retired_reagents']:
                    findings.append(('RETIRED_REAGENT', record['retired_reagents'][0]))
                draw = record['draw']
                for reagent_id, units in draw.items():
                    self.called_for[reagent_id] += units
                floor_reagent = None
                for reagent_id in sorted(draw):
                    if vault.get(reagent_id, 0) - draw[reagent_id] < 0:
                        floor_reagent = reagent_id
                        break
                if floor_reagent is not None:
                    findings.append(('STOCK_FLOOR', floor_reagent))
                if findings:
                    for code, detail in findings:
                        self.findings.append((entry_id, code, detail))
                    self.settled[entry_id] = False
                    if stats is not None:
                        stats['entries_rejected'] += 1
                    continue
                # settle the forge
                for reagent_id, units in draw.items():
                    vault[reagent_id] = vault.get(reagent_id, 0) - units
                    self.total_consumed[reagent_id] += units
                    if position is not None:
                        cell = self.patch_flow[position].get(reagent_id)
                        if cell is None:
                            cell = [0, 0, 0]
                            self.patch_flow[position][reagent_id] = cell
                        cell[2] += units
                self.accrued[wid] = self.accrued.get(wid, 0) + charge
                self.charge_of_entry[entry_id] = charge
                record['charge'] = charge
                self.settled[entry_id] = True
                if stats is not None:
                    stats['entries_admitted'] += 1
                    stats['charge_ember'] += charge
                    smith = record['canonical_smith']
                    smith_row = stats['smiths'].get(smith)
                    if smith_row is None:
                        smith_row = {'admitted_forges': 0, 'credited_salvages': 0,
                                     'charge_ember': 0}
                        stats['smiths'][smith] = smith_row
                    smith_row['admitted_forges'] += 1
                    smith_row['charge_ember'] += charge
                    for reagent_id, units in draw.items():
                        cell = stats['flow'].get(reagent_id)
                        if cell is None:
                            cell = {'consumed_units': 0, 'returned_units': 0}
                            stats['flow'][reagent_id] = cell
                        cell['consumed_units'] += units
                self.live.setdefault((record['canonical_smith'], record['artifact_family']),
                                     []).append(record)
            else:
                source = record['source']
                stats = self.workshop_stats.get(wid)
                if source is None:
                    # unreachable: a missing source is an early finding
                    self.settled[entry_id] = False
                    if stats is not None:
                        stats['entries_rejected'] += 1
                    continue
                if source['entry_id'] in self.credited_forges:
                    self.findings.append((entry_id, 'SALVAGE_ALREADY_CREDITED',
                                          source['entry_id']))
                    self.settled[entry_id] = False
                    if stats is not None:
                        stats['entries_rejected'] += 1
                    continue
                window = self.live.get((record['canonical_smith'], record['artifact_family']),
                                        [])
                in_window = False
                count = 0
                for candidate in reversed(window):
                    if candidate['day'] >= record['day']:
                        continue
                    if candidate['entry_id'] == source['entry_id']:
                        in_window = True
                        break
                    count += 1
                    if count >= 3:
                        break
                if not in_window:
                    self.findings.append((entry_id, 'UNCREDITED_SALVAGE', source['entry_id']))
                    self.settled[entry_id] = False
                    if stats is not None:
                        stats['entries_rejected'] += 1
                    continue
                returns = record['returns']
                for reagent_id, units in returns.items():
                    if units <= 0:
                        continue
                    vault[reagent_id] = vault.get(reagent_id, 0) + units
                    self.total_returned[reagent_id] += units
                    if position is not None:
                        cell = self.patch_flow[position].get(reagent_id)
                        if cell is None:
                            cell = [0, 0, 0]
                            self.patch_flow[position][reagent_id] = cell
                        cell[1] += units
                self.credited_forges[source['entry_id']] = entry_id
                self.settled[entry_id] = True
                source_charge = self.charge_of_entry.get(source['entry_id'], 0)
                source_workshop = source['workshop_id']
                self.accrued[source_workshop] = self.accrued.get(source_workshop, 0) - source_charge
                source_key = (record['source_smith'], record['artifact_family'])
                source_list = self.live.get(source_key)
                if source_list is not None:
                    self.live[source_key] = [item for item in source_list
                                             if item['entry_id'] != source['entry_id']]
                if stats is not None:
                    stats['entries_admitted'] += 1
                    smith = record['canonical_smith']
                    smith_row = stats['smiths'].get(smith)
                    if smith_row is None:
                        smith_row = {'admitted_forges': 0, 'credited_salvages': 0,
                                     'charge_ember': 0}
                        stats['smiths'][smith] = smith_row
                    smith_row['credited_salvages'] += 1
                    for reagent_id, units in returns.items():
                        if units <= 0:
                            continue
                        cell = stats['flow'].get(reagent_id)
                        if cell is None:
                            cell = {'consumed_units': 0, 'returned_units': 0}
                            stats['flow'][reagent_id] = cell
                        cell['returned_units'] += units
        # any acquisition recorded after the last entry still belongs to the vault
        if acquisition_days:
            credit_acquisitions(season.last_day)

    # -- derived figures ----------------------------------------------------

    def scarcity_indices(self):
        """The indices this settled state gives its scarce reagents (V5)."""
        season = self.season
        ceiling = 0
        if isinstance(season.charter, dict):
            ceiling = as_int(season.charter.get('scarcity_ceiling'))
        indices = {}
        for reagent_id in season.scarce_ids:
            consumed = self.total_consumed.get(reagent_id, 0)
            if self.reference == 'opening':
                base = season.opening.get(reagent_id, 0)
            elif self.reference == 'opening-plus-acquired':
                base = season.opening.get(reagent_id, 0) \
                    + self.total_acquired.get(reagent_id, 0)
            elif self.reference == 'consumed':
                base = self.called_for.get(reagent_id, 0)
            else:
                base = self.total_acquired.get(reagent_id, 0)
            if base <= 0:
                indices[reagent_id] = 0
                continue
            index = reduce_whole(self.reduction, consumed * 100, base)
            if index > ceiling:
                index = ceiling
            if index < 0:
                index = 0
            indices[reagent_id] = index
        return indices

    def closing(self):
        return {reagent_id: self.season.opening.get(reagent_id, 0)
                + self.total_acquired.get(reagent_id, 0)
                + self.total_returned.get(reagent_id, 0)
                - self.total_consumed.get(reagent_id, 0)
                for reagent_id in self.season.reagent_ids}


def conventions_return(conventions):
    return RETURN_SCHEDULES[conventions[0]]


def conventions_reduction(conventions):
    return conventions[1]


def conventions_order(conventions):
    return conventions[2]


def conventions_reference(conventions):
    return conventions[3]


def settle_season(season, conventions):
    """Settle the season at the one assignment of indices that reproduces itself (V8).

    The indices a settled state gives its scarce reagents fall as the indices it
    was settled at rise, so the assignment is read off by climbing the two
    subsequences of the climb from the bottom of the lattice, which bracket any
    fixed point, and searching the bracket should the climb not settle.
    """
    count = len(season.scarce_ids)
    ceiling = 0
    if isinstance(season.charter, dict):
        ceiling = as_int(season.charter.get('scarcity_ceiling'))
    bottom = tuple(0 for _ in range(count))

    def assignment(vector):
        return {reagent_id: value
                for reagent_id, value in zip(season.scarce_ids, vector)}

    def climb(start, limit):
        current = start
        for _ in range(limit):
            result = Settlement(season, conventions, assignment(current))
            nxt = tuple(result.scarcity_indices().get(reagent_id, 0)
                        for reagent_id in season.scarce_ids)
            if nxt == current:
                return result, True
            current = nxt
        return Settlement(season, conventions, assignment(current)), False

    result, settled = climb(bottom, 2 * (count * (ceiling + 1) + 1) + 4)
    if settled:
        return result
    # the climb turned on itself: the fixed point lies between the even and odd
    # limits, so collect the states the climb visited and search that bracket.
    visited = []
    current = bottom
    seen = set()
    for _ in range(2 * (count * (ceiling + 1) + 1) + 4):
        if current in seen:
            break
        seen.add(current)
        visited.append(current)
        result = Settlement(season, conventions, assignment(current))
        nxt = tuple(result.scarcity_indices().get(reagent_id, 0)
                    for reagent_id in season.scarce_ids)
        if nxt == current:
            return result
        current = nxt
    lower = list(bottom)
    upper = [ceiling] * count
    for position in range(count):
        values = [vector[position] for vector in visited]
        lower[position] = max(lower[position], min(values))
        upper[position] = min(upper[position], max(values))
    for vector in sorted(set(seen)):
        result = Settlement(season, conventions, assignment(vector))
        nxt = tuple(result.scarcity_indices().get(reagent_id, 0)
                    for reagent_id in season.scarce_ids)
        if nxt == vector:
            return result
    span = 1
    for position in range(count):
        span *= (upper[position] - lower[position] + 1)
    if span > 300000:
        return result
    indexes = list(lower)
    while True:
        candidate = tuple(indexes)
        if candidate not in seen:
            probe = Settlement(season, conventions, assignment(candidate))
            nxt = tuple(probe.scarcity_indices().get(reagent_id, 0)
                        for reagent_id in season.scarce_ids)
            if nxt == candidate:
                return probe
        position = count - 1
        while position >= 0:
            indexes[position] += 1
            if indexes[position] <= upper[position]:
                break
            indexes[position] = lower[position]
            position -= 1
        if position < 0:
            break
    return result


# --------------------------------------------------------------------------- #
# requisitions
# --------------------------------------------------------------------------- #

def geometric_series(bound, stride):
    """A bitmask of every position whose coordinate is at most bound, at a stride."""
    if bound < 0:
        return 0
    if stride <= 0:
        stride = 1
    return ((1 << ((bound + 1) * stride)) - 1) // ((1 << stride) - 1)


def range_shift_union(base, count, stride):
    """The union of base shifted by 0..count-1 steps of stride."""
    if count <= 0:
        return 0
    powers = [base]
    size = 1
    while size < count:
        size *= 2
        powers.append(powers[-1] | (powers[-1] << ((size // 2) * stride)))
    merged = 0
    offset = 0
    remaining = count
    bit = 0
    while remaining:
        if remaining & 1:
            merged |= powers[bit] << (offset * stride)
            offset += (1 << bit)
        remaining >>= 1
        bit += 1
    return merged


class RequisitionAllocator:
    """Grants reagent units against the season's requisitions (rulebook Q)."""

    def __init__(self, season, settlement):
        self.season = season
        self.settlement = settlement
        charter = season.charter if isinstance(season.charter, dict) else {}
        self.pool = positive_int(charter.get('season_pool_units'))
        self.guild_caps = {}
        table = charter.get('guild_cap_units')
        if isinstance(table, dict):
            self.guild_caps = {str(key): as_int(value) for key, value in table.items()}
        self.tier_caps = {}
        table = charter.get('tier_unit_cap')
        if isinstance(table, dict):
            self.tier_caps = table
        self.closing = settlement.closing()
        self._collect()
        self._layout()

    # -- what may be funded -------------------------------------------------

    def _collect(self):
        season = self.season
        self.reqs = []
        for req in season.requisitions:
            record = dict(req)
            workshop = season.workshops.get(req['workshop_id'])
            tier_cap = 0
            if workshop is not None:
                value = chart_lookup(self.tier_caps, workshop['charter_tier'])
                if value is not None:
                    tier_cap = as_int(value)
            guild_cap = None
            if workshop is not None and workshop['guild_id'] in self.guild_caps:
                guild_cap = self.guild_caps[workshop['guild_id']]
            reagent = season.reagents.get(req['reagent_id'])
            vault_cap = None
            if reagent is not None and reagent['scarce']:
                vault_cap = self.closing.get(req['reagent_id'], 0)
            upper = tier_cap
            for limit in (req['units_requested'], guild_cap, vault_cap, self.pool):
                if limit is not None:
                    upper = min(upper, as_int(limit))
            lower = max(as_int(req['min_units']), 1)
            record['min'] = lower
            record['max'] = upper
            record['fundable'] = (
                workshop is not None
                and season.workshop_in_scope(req['workshop_id'])
                and lower <= upper
                and upper > 0
            )
            record['charter'] = workshop['charter_id'] if workshop else ''
            record['guild'] = workshop['guild_id'] if workshop else ''
            record['scarce_reagent'] = req['reagent_id'] \
                if (reagent is not None and reagent['scarce']) else None
            self.reqs.append(record)
        self.by_id = {record['req_id']: record for record in self.reqs}
        self.order = sorted(self.reqs,
                            key=lambda record: (record['priority'], record['req_id']))
        self.groups = {}
        for record in self.reqs:
            if record['fundable']:
                self.groups.setdefault(record['charter'], []).append(record['req_id'])

    # -- the dimensions the plan is constrained along -----------------------

    def _layout(self):
        fundable = [record for record in self.reqs if record['fundable']]
        guild_totals = {}
        reagent_totals = {}
        for record in fundable:
            guild_totals[record['guild']] = guild_totals.get(record['guild'], 0) \
                + record['max']
            if record['scarce_reagent']:
                reagent_totals[record['scarce_reagent']] = \
                    reagent_totals.get(record['scarce_reagent'], 0) + record['max']
        charter_totals = {}
        for record in fundable:
            charter = record['charter']
            known = charter_totals.get(charter)
            if known is None or record['max'] > known:
                charter_totals[charter] = record['max']
        self.guild_dims = []
        for guild in sorted(guild_totals):
            cap = self.guild_caps.get(guild)
            if cap is not None and guild_totals[guild] > cap:
                self.guild_dims.append(guild)
        self.reagent_dims = []
        for reagent in sorted(reagent_totals):
            balance = self.closing.get(reagent, 0)
            if reagent_totals[reagent] > balance:
                self.reagent_dims.append(reagent)
        # the greatest total any plan could reach, and the bounds of the
        # dimensions the plan is constrained along.
        guild_ceiling = 0
        for guild in sorted(guild_totals):
            reach = guild_totals[guild]
            cap = self.guild_caps.get(guild)
            if cap is not None:
                reach = min(reach, cap)
            guild_ceiling += reach
        charter_ceiling = sum(charter_totals.values())
        pool_bound = min(self.pool, charter_ceiling, guild_ceiling)
        if pool_bound < 0:
            pool_bound = 0
        bounds = []
        for guild in self.guild_dims:
            bounds.append(max(0, min(self.guild_caps[guild], guild_totals[guild])))
        for reagent in self.reagent_dims:
            bounds.append(max(0, min(self.closing.get(reagent, 0),
                                     reagent_totals[reagent])))
        bounds.append(pool_bound)
        self.bounds = bounds
        # a dimension's field must hold its own coordinate and the furthest a
        # grant could carry it; the pool, as the highest field, needs no spare.
        reach = []
        for record in fundable:
            reach.append((record['guild'], record['scarce_reagent'], record['max']))
        widths = []
        for position in range(len(bounds) - 1):
            if position < len(self.guild_dims):
                key = self.guild_dims[position]
            else:
                key = self.reagent_dims[position - len(self.guild_dims)]
            furthest = 0
            for guild, reagent, amount in reach:
                touches = (guild == key) if position < len(self.guild_dims) \
                    else (reagent == key)
                if touches and amount > furthest:
                    furthest = amount
            widths.append(bounds[position] + min(furthest, bounds[position]) + 2)
        widths.append(bounds[-1] + 1)
        self.strides = []
        stride = 1
        for width in widths:
            self.strides.append(stride)
            stride *= width
        self.total_bits = stride
        # the pool is the last dimension, so the highest reachable position
        # gives the greatest total directly.
        self.guild_slot = {}
        for position, guild in enumerate(self.guild_dims):
            self.guild_slot[guild] = position
        self.reagent_slot = {}
        for position, reagent in enumerate(self.reagent_dims):
            self.reagent_slot[reagent] = position + len(self.guild_dims)
        self.guild_reach = {}
        for guild, total in guild_totals.items():
            reach = total
            cap = self.guild_caps.get(guild)
            if cap is not None:
                reach = min(reach, cap)
            self.guild_reach[guild] = reach
        self.reagent_reach = {}
        for reagent, total in reagent_totals.items():
            self.reagent_reach[reagent] = min(total, self.closing.get(reagent, 0))
        for record in self.reqs:
            record['slot'] = self._slot(record)

    def _slot(self, record):
        """The stride multiplier a grant to this requisition shifts the state by."""
        multiplier = self.strides[-1]
        if record['guild'] in self.guild_slot:
            multiplier += self.strides[self.guild_slot[record['guild']]]
        if record['scarce_reagent'] is not None and record['scarce_reagent'] in self.reagent_slot:
            multiplier += self.strides[self.reagent_slot[record['scarce_reagent']]]
        return multiplier

    def _positions(self, record):
        """The dimensions a grant to this requisition draws on."""
        positions = []
        if record['guild'] in self.guild_slot:
            positions.append(self.guild_slot[record['guild']])
        if record['scarce_reagent'] is not None and record['scarce_reagent'] in self.reagent_slot:
            positions.append(self.reagent_slot[record['scarce_reagent']])
        positions.append(len(self.bounds) - 1)
        return positions

    # -- the greatest total a set of options can grant ----------------------

    def max_total(self, groups, caps):
        """The greatest number of units those charters can grant (Q7)."""
        if not groups:
            return 0
        if self.upper_bound(groups, caps) == 0:
            return 0
        mask = 1
        for position, bound in enumerate(caps):
            mask *= geometric_series(bound, self.strides[position])
        state = 1
        for group in groups:
            # a charter funds at most one requisition, so every option is
            # read against the state the charters held before it.
            reached = state
            for record in group:
                lower = record['min']
                upper = record['max']
                if upper < lower:
                    continue
                stride = record['slot']
                reached |= range_shift_union(state << (lower * stride),
                                            upper - lower + 1, stride)
            state = reached & mask
            if not state:
                return 0
        return (state.bit_length() - 1) // self.strides[-1]

    def upper_bound(self, groups, caps):
        """A cheap bound above anything those charters can grant."""
        ceiling = 0
        for group in groups:
            best = 0
            for record in group:
                if record['max'] > best:
                    best = record['max']
            ceiling += best
        if ceiling > caps[-1]:
            ceiling = caps[-1]
        for position, guild in enumerate(self.guild_dims):
            spare = caps[position]
            for other in self.guild_dims:
                if other != guild:
                    spare += min(self.guild_reach[other],
                                 caps[self.guild_slot[other]])
            if spare < ceiling:
                ceiling = spare
        for reagent in self.reagent_dims:
            spare = caps[self.reagent_slot[reagent]]
            for other in self.reagent_dims:
                if other != reagent:
                    spare += self.reagent_reach[other]
            if spare < ceiling:
                ceiling = spare
        return max(0, ceiling)

    def _option_groups(self, excluded_ids, excluded_charters):
        groups = []
        for charter in sorted(self.groups):
            if charter in excluded_charters:
                continue
            options = []
            for req_id in self.groups[charter]:
                if req_id in excluded_ids:
                    continue
                options.append(self.by_id[req_id])
            if options:
                groups.append(options)
        return groups

    # -- the plan -----------------------------------------------------------

    def solve(self):
        grants = {record['req_id']: 0 for record in self.reqs}
        if self.total_bits > (1 << 28):
            # a season whose bounds outrun the packing: grant what the bounds
            # leave room for, charters first in the order the charter prefers.
            return self._greedy_plan(grants)
        current = list(self.bounds)
        target = self.max_total(self._option_groups(set(), set()), current)
        # a plan that grants every requisition the most its bounds leave room
        # for, taken in the charter's own order, already reaches the greatest
        # total the charters can grant, and so is the plan the charter prefers.
        reached = self._greedy_plan(dict(grants))
        if sum(reached.values()) == target:
            return reached
        used = 0
        decided = set()
        spent_charters = set()
        for record in self.order:
            req_id = record['req_id']
            charter = record['charter']
            if not record['fundable'] or charter in spent_charters:
                decided.add(req_id)
                continue
            positions = self._positions(record)
            reachable_max = min(record['max'],
                                *[current[position] for position in positions])
            chosen = 0
            if reachable_max >= record['min']:
                for grant in range(reachable_max, record['min'] - 1, -1):
                    trial = list(current)
                    for position in positions:
                        trial[position] -= grant
                    excluded_ids = set(decided)
                    excluded_ids.add(req_id)
                    excluded_charters = set(spent_charters)
                    if grant > 0:
                        excluded_charters.add(charter)
                    groups = self._option_groups(excluded_ids, excluded_charters)
                    if self.max_total(groups, trial) >= target - used - grant:
                        chosen = grant
                        break
            if chosen > 0:
                grants[req_id] = chosen
                used += chosen
                for position in positions:
                    current[position] -= chosen
                spent_charters.add(charter)
            decided.add(req_id)
        return grants

    def _greedy_plan(self, grants):
        """Grant every requisition the most its bounds leave room for."""
        current = list(self.bounds)
        spent = set()
        for record in self.order:
            if not record['fundable'] or record['charter'] in spent:
                continue
            positions = self._positions(record)
            grant = min(record['max'], *[current[position] for position in positions])
            if grant >= record['min']:
                grants[record['req_id']] = grant
                for position in positions:
                    current[position] -= grant
                spent.add(record['charter'])
        return grants


def positive_int(value):
    if value is None:
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #

def write_record(path, document):
    text = json.dumps(document, indent=2, ensure_ascii=False) + '\n'
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def build_summary(season, settlement, allocation, allocation_total):
    admitted = 0
    rejected = 0
    credited = 0
    for record in settlement.prepared:
        if settlement.settled[record['entry_id']]:
            admitted += 1
            if record['op'] == 'salvage':
                credited += 1
        else:
            rejected += 1
    uncredited = 0
    for _entry_id, code, _detail in settlement.findings:
        if code == 'UNCREDITED_SALVAGE':
            uncredited += 1
    residual = 0
    for reagent_id in season.reagent_ids:
        identity = (season.opening.get(reagent_id, 0)
                    + settlement.total_acquired.get(reagent_id, 0)
                    + settlement.total_returned.get(reagent_id, 0)
                    - settlement.total_consumed.get(reagent_id, 0)
                    - settlement.closing().get(reagent_id, 0))
        residual += abs(identity)
    return {
        'season': {
            'first_day': season.first_day,
            'last_day': season.last_day,
            'patch_count': season.patch_count,
        },
        'workshops_in_scope': list(season.scope_ids),
        'guilds_in_scope': list(season.guild_ids),
        'entries_total': len(settlement.prepared),
        'entries_admitted': admitted,
        'entries_rejected': rejected,
        'credited_salvages': credited,
        'uncredited_salvages': uncredited,
        'scarcity_index': {reagent_id: settlement.indices.get(reagent_id, 0)
                           for reagent_id in season.scarce_ids},
        'season_charge_ember': season_charge(season, settlement),
        'allocated_units_total': allocation_total,
        'conservation_residual': residual,
    }


def season_charge(season, settlement):
    total = 0
    for workshop_id in season.scope_ids:
        total += settlement.workshop_stats[workshop_id]['charge_ember']
    return total


def build_vault_audit(season, settlement):
    closing = settlement.closing()
    rows = []
    for reagent_id in season.reagent_ids:
        reagent = season.reagents[reagent_id]
        rows.append({
            'reagent_id': reagent_id,
            'grade': reagent['grade'],
            'scarce': bool(reagent['scarce']),
            'opening_units': season.opening.get(reagent_id, 0),
            'acquired_units': settlement.total_acquired.get(reagent_id, 0),
            'returned_units': settlement.total_returned.get(reagent_id, 0),
            'consumed_units': settlement.total_consumed.get(reagent_id, 0),
            'closing_units': closing.get(reagent_id, 0),
            'scarcity_index': settlement.indices.get(reagent_id, 0)
            if reagent['scarce'] else 0,
        })
    return {'reagents': rows}


def build_reconciliation(season, settlement):
    patches = []
    season_residual = 0
    opening = dict(season.opening)
    for position, patch in enumerate(season.patches):
        flow = settlement.patch_flow[position]
        rows = []
        patch_residual = 0
        for reagent_id in season.reagent_ids:
            acquired, returned, consumed = flow.get(reagent_id, (0, 0, 0))
            closing = opening.get(reagent_id, 0) + acquired + returned - consumed
            residual = closing - (opening.get(reagent_id, 0) + acquired + returned - consumed)
            patch_residual += abs(residual)
            rows.append({
                'reagent_id': reagent_id,
                'opening_units': opening.get(reagent_id, 0),
                'acquired_units': acquired,
                'returned_units': returned,
                'consumed_units': consumed,
                'closing_units': closing,
                'residual': residual,
            })
            opening[reagent_id] = closing
        season_residual += patch_residual
        patches.append({
            'patch_id': patch['patch_id'],
            'ordinal': patch['ordinal'],
            'reagents': rows,
            'residual': patch_residual,
        })
    charge_by_workshop = {}
    for workshop_id in season.scope_ids:
        charge_by_workshop[workshop_id] = \
            settlement.workshop_stats[workshop_id]['charge_ember']
    charge_by_guild = {}
    for guild_id in season.guild_ids:
        total = 0
        for workshop_id in season.guild_workshops[guild_id]:
            total += settlement.workshop_stats[workshop_id]['charge_ember']
        charge_by_guild[guild_id] = total
    return {
        'patches': patches,
        'season_residual': season_residual,
        'charge_by_workshop': charge_by_workshop,
        'charge_by_guild': charge_by_guild,
        'charge_total': season_charge(season, settlement),
    }


def build_data_quality(settlement):
    findings = [
        {'entry_id': entry_id, 'code': code, 'detail': detail}
        for entry_id, code, detail in settlement.findings
    ]
    findings.sort(key=lambda row: (row['entry_id'], row['code']))
    counts = {}
    for row in findings:
        counts[row['code']] = counts.get(row['code'], 0) + 1
    return {
        'findings': findings,
        'counts': {code: counts[code] for code in sorted(counts)},
    }


def build_allocation(season, allocation, allocation_total):
    assignments = []
    for req in season.requisitions:
        grant = allocation.get(req['req_id'], 0)
        assignments.append({
            'req_id': req['req_id'],
            'workshop_id': req['workshop_id'],
            'reagent_id': req['reagent_id'],
            'allocated_units': grant,
            'served': grant > 0,
        })
    return {
        'pool_units': positive_int(
            (season.charter or {}).get('season_pool_units')
            if isinstance(season.charter, dict) else None),
        'assignments': assignments,
        'allocated_total': allocation_total,
    }


def build_workshop_report(season, settlement, workshop_id, grants_by_workshop):
    workshop = season.workshops[workshop_id]
    stats = settlement.workshop_stats[workshop_id]
    smiths = settlement.smiths_by_workshop.get(workshop_id, set())
    smith_rows = []
    for canonical in sorted(smiths):
        row = stats['smiths'].get(canonical)
        if row is None:
            row = {'admitted_forges': 0, 'credited_salvages': 0, 'charge_ember': 0}
        smith_rows.append({
            'canonical_smith': canonical,
            'admitted_forges': row['admitted_forges'],
            'credited_salvages': row['credited_salvages'],
            'charge_ember': row['charge_ember'],
        })
    flow_rows = []
    for reagent_id in sorted(stats['flow']):
        cell = stats['flow'][reagent_id]
        flow_rows.append({
            'reagent_id': reagent_id,
            'consumed_units': cell['consumed_units'],
            'returned_units': cell['returned_units'],
            'net_units': cell['consumed_units'] - cell['returned_units'],
        })
    return {
        'workshop_id': workshop_id,
        'guild_id': workshop['guild_id'],
        'charter_id': workshop['charter_id'],
        'charter_tier': workshop['charter_tier'],
        'entries_admitted': stats['entries_admitted'],
        'entries_rejected': stats['entries_rejected'],
        'charge_ember': stats['charge_ember'],
        'cap_ember': season.charge_caps.get(workshop_id, 0),
        'cap_reached': bool(stats['cap_reached']),
        'allocated_units': grants_by_workshop.get(workshop_id, 0),
        'smiths': smith_rows,
        'reagent_flow': flow_rows,
    }


def build_guild_report(season, settlement, guild_id, grants_by_workshop):
    workshops = season.guild_workshops[guild_id]
    entries_admitted = 0
    charge = 0
    allocated = 0
    flow = {}
    for workshop_id in workshops:
        stats = settlement.workshop_stats[workshop_id]
        entries_admitted += stats['entries_admitted']
        charge += stats['charge_ember']
        allocated += grants_by_workshop.get(workshop_id, 0)
        for reagent_id, cell in stats['flow'].items():
            merged = flow.get(reagent_id)
            if merged is None:
                merged = {'consumed_units': 0, 'returned_units': 0}
                flow[reagent_id] = merged
            merged['consumed_units'] += cell['consumed_units']
            merged['returned_units'] += cell['returned_units']
    flow_rows = []
    for reagent_id in sorted(flow):
        cell = flow[reagent_id]
        flow_rows.append({
            'reagent_id': reagent_id,
            'consumed_units': cell['consumed_units'],
            'returned_units': cell['returned_units'],
            'net_units': cell['consumed_units'] - cell['returned_units'],
        })
    return {
        'guild_id': guild_id,
        'workshops': list(workshops),
        'entries_admitted': entries_admitted,
        'charge_ember': charge,
        'allocated_units': allocated,
        'reagent_flow': flow_rows,
    }


# --------------------------------------------------------------------------- #
# entry
# --------------------------------------------------------------------------- #

def settle(data_dir, out_dir):
    missing = [name for name in REQUIRED_FILES
               if not os.path.isfile(os.path.join(data_dir, name))]
    if missing:
        for name in missing:
            message = 'missing file: %s' % name
            sys.stderr.write(message + '\n')
            sys.stdout.write(message + '\n')
        sys.stdout.flush()
        sys.stderr.flush()
        raise SystemExit(2)
    season = Season(data_dir)
    conventions = infer_draw(season.rulings if isinstance(season.rulings, dict) else {})
    settlement = settle_season(season, conventions)
    allocator = RequisitionAllocator(season, settlement)
    grants = allocator.solve()
    allocation_total = 0
    grants_by_workshop = {}
    for record in allocator.reqs:
        grant = grants.get(record['req_id'], 0)
        allocation_total += grant
        grants_by_workshop[record['workshop_id']] = \
            grants_by_workshop.get(record['workshop_id'], 0) + grant
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    write_record(os.path.join(out_dir, 'summary.json'),
                 build_summary(season, settlement, grants, allocation_total))
    write_record(os.path.join(out_dir, 'vault_audit.json'),
                 build_vault_audit(season, settlement))
    write_record(os.path.join(out_dir, 'reconciliation.json'),
                 build_reconciliation(season, settlement))
    write_record(os.path.join(out_dir, 'data_quality.json'),
                 build_data_quality(settlement))
    write_record(os.path.join(out_dir, 'allocation.json'),
                 build_allocation(season, grants, allocation_total))
    for workshop_id in season.scope_ids:
        report = build_workshop_report(season, settlement, workshop_id, grants_by_workshop)
        write_record(os.path.join(out_dir, 'workshop_%s.json' % workshop_id), report)
    for guild_id in season.guild_ids:
        report = build_guild_report(season, settlement, guild_id, grants_by_workshop)
        write_record(os.path.join(out_dir, 'guild_%s.json' % guild_id), report)


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else DEFAULT_DATA_DIR
    out_dir = argv[2] if len(argv) > 2 else DEFAULT_OUT_DIR
    settle(data_dir, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
