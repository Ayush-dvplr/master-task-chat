"""Stages p03, p04 and p07. The per job layers and the rule layer.

The norm layer holds what the register says about a job once the units are
put right and the licence and the round window are tested. The charge layer
holds the class scaled charge and the deferral penalty. The rule layer holds
one conditional charge rule with its amount put into whole mills.
"""
from fractions import Fraction

from . import normalise

REGISTER_FIELDS = ["base_charge_mills", "berth_quantity", "berth_unit",
                   "class", "crane_lifts", "crew_quantity", "crew_unit",
                   "deferral_weight", "earliest_round", "job_id",
                   "latest_round", "licence_code", "precinct", "standing"]

RULE_FIELDS = ["amount_text", "anchor_job", "class", "first_job", "kind",
               "pool", "precinct", "rebate_bp", "rule_id", "second_job",
               "state", "threshold"]

PRESENTATION_FIELDS = ["display_order", "note", "owner", "title"]


def norm_inputs(model, name):
    job = model.jobs[name]
    licence = model.params["licences"].get(job["licence_code"], {})
    held = dict(model.meta.get(name, {}))
    held.update({field: job[field] for field in REGISTER_FIELDS})
    return [held,
            model.params["shift_minutes"].get(job["precinct"]),
            [licence.get("state"), licence.get("valid_from_round"),
             licence.get("valid_to_round")],
            model.params["round_index"]]


def norm(model, name):
    job = model.jobs[name]
    params = model.params
    shift = int(params["shift_minutes"][job["precinct"]])
    crew = int(job["crew_quantity"])
    if job["crew_unit"] == "shift":
        crew = crew * shift
    berth = int(job["berth_quantity"])
    if job["berth_unit"] == "day":
        berth = berth * 4
    licence = params["licences"].get(job["licence_code"])
    index = params["round_index"]
    admissible = True
    reason = ""
    if (licence is None or licence["state"] != "valid"
            or not (int(licence["valid_from_round"]) <= index
                    <= int(licence["valid_to_round"]))):
        admissible = False
        reason = "JOB-LICENCE"
    elif not (int(job["earliest_round"]) <= index <= int(job["latest_round"])):
        admissible = False
        reason = "JOB-OUTOFROUND"
    return {"job_id": name, "precinct": job["precinct"], "class": job["class"],
            "standing": job["standing"],
            "base_charge_mills": int(job["base_charge_mills"]),
            "berth_quarter_days": berth, "crane_lifts": int(job["crane_lifts"]),
            "crew_minutes": crew,
            "deferral_weight": int(job["deferral_weight"]),
            "admissible": admissible, "admission_reason": reason}


def charge_inputs(model, name, seen):
    klass = seen["norm|" + name]["value"]["class"]
    return [seen["norm|" + name]["digest"],
            model.params["class_bp"].get(klass),
            model.params["deferral_rate"].get(klass)]


def charge(model, name, seen):
    held = seen["norm|" + name]["value"]
    params = model.params
    points = int(params["class_bp"][held["class"]])
    scaled = normalise.half_up(
        Fraction(int(held["base_charge_mills"]) * points, 10000))
    penalty = (int(params["deferral_rate"][held["class"]])
               * int(held["deferral_weight"]))
    return {"job_id": name, "scaled_charge_mills": scaled,
            "deferral_penalty_mills": penalty, "multiplier_bp": points,
            "implausible": scaled > int(params["ceiling"])}


def rule_inputs(model, name):
    record = model.rules[name]
    return {field: record.get(field) for field in RULE_FIELDS}


def rule(model, name):
    record = model.rules[name]
    out = {"rule_id": name, "precinct": record["precinct"],
           "kind": record["kind"]}
    if record["kind"] == "pair_surcharge":
        out["first_job"] = record["first_job"]
        out["second_job"] = record["second_job"]
        out["amount_mills"] = normalise.amount(record["amount_text"])
    elif record["kind"] == "threshold_surcharge":
        out["pool"] = record["pool"]
        out["threshold"] = int(record["threshold"])
        out["class"] = record["class"]
        out["amount_mills"] = normalise.amount(record["amount_text"])
    else:
        out["anchor_job"] = record["anchor_job"]
        out["rebate_bp"] = int(record["rebate_bp"])
    return out


def group_inputs(model, name, seen):
    entry = model.groups[name]
    members = sorted(m for m in entry["members"] if m in model.jobs)
    return [members, entry["precedence"], entry["precinct"],
            [seen["norm|" + m]["digest"] for m in members]]


def group(model, name, seen):
    entry = model.groups[name]
    members = sorted(m for m in entry["members"] if m in model.jobs)
    return {"group_id": name, "precinct": entry["precinct"],
            "precedence": entry["precedence"], "members": members,
            "binding": len(members) >= 2}
