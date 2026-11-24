"""The ferry operator's knowledge, read from the files in kg/ (Session 7, Stage 16, Practice Exercise).

The files of Gozo ferry knowledge v1.0 hold what the cancellation log alone cannot say:
    kg/schema.yaml      the classes, properties and relationships, with cardinalities; the files conform to it
    kg/ports.yaml       the two ports, each with every spelling staff have written
    kg/reasons.yaml     a taxonomy of reasons (weather above wind, sea and visibility; technical; operational),
                        each with the words and log wordings that mean it
    kg/vessels.yaml     the fleet
    kg/questions.yaml   the competency questions, with the answers worked out by hand

data/gozo_operations_2025.csv is the log: 77 cancelled crossings of 2025, as staff on duty wrote them. It is
transactional data and is never edited; the knowledge files are reference data that say what each entry means.
"""
import logging
from dataclasses import dataclass

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

LOG_PATH = "data/gozo_operations_2025.csv"
SCHEMA_PATH = "kg/schema.yaml"
PORTS_PATH = "kg/ports.yaml"
REASONS_PATH = "kg/reasons.yaml"
VESSELS_PATH = "kg/vessels.yaml"
QUESTIONS_PATH = "kg/questions.yaml"


@dataclass
class Knowledge:
    """Everything the operator knows about ports, reasons and vessels, read once from kg/."""
    ports: dict
    reasons: dict
    vessels: dict


def _read_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_schema(path=SCHEMA_PATH):
    return _read_yaml(path)


def load_questions(path=QUESTIONS_PATH):
    return _read_yaml(path)["questions"]


def load_knowledge():
    return Knowledge(ports={p["id"]: p for p in _read_yaml(PORTS_PATH)["ports"]},
                     reasons={r["id"]: r for r in _read_yaml(REASONS_PATH)["reasons"]},
                     vessels={v["id"]: v for v in _read_yaml(VESSELS_PATH)["vessels"]})


def load_log(path=LOG_PATH):
    """The cancellation log, every value as text, exactly as written."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def labels(things):
    """Every label of every port or reason, mapped to the thing it means."""
    return {label: thing_id for thing_id, thing in things.items() for label in thing["labels"]}


def narrower(hierarchy, broad_id):
    """The reason and every reason that is a kind of it, at any depth."""
    found = {broad_id}
    changed = True
    while changed:
        changed = False
        for item_id, item in hierarchy.items():
            if item.get("is_a") in found and item_id not in found:
                found.add(item_id)
                changed = True
    return found


def cancellation_key(date, time, port_id):
    """A cancellation is one crossing from one port, on one day, at one time. The log has no identifier, and the date
    and time alone are not enough: on 26 January and 23 December crossings from both ports were cancelled at the same
    time. The time is written with two digits for the hour, so 7:30 and 07:30 give the same key."""
    hour, minute = time.split(":")
    return f"{date}|{int(hour):02d}:{minute}|{port_id}"


def link_log(log, kg):
    """Attach a port, a vessel and a reason to every row of the log, through the labels. A row that cannot be linked
    is an error: it is reported and stops the build, rather than being dropped."""
    port_of, reason_of = labels(kg.ports), labels(kg.reasons)
    vessel_of = {v["name"]: vid for vid, v in kg.vessels.items()}
    linked = log.assign(port_id=log["departure"].map(port_of), reason_id=log["reason"].map(reason_of),
                        vessel_id=log["vessel"].map(vessel_of))
    problems = []
    for column, target, path in (("departure", "port_id", PORTS_PATH), ("reason", "reason_id", REASONS_PATH),
                                 ("vessel", "vessel_id", VESSELS_PATH)):
        unmatched = sorted(linked.loc[linked[target].isna(), column].unique())
        if unmatched:
            problems.append(f"log entries with no match in {path}: {unmatched}")
    if problems:
        raise ValueError("; ".join(problems))
    linked["cancellation_id"] = [cancellation_key(*r) for r in linked[["date", "time", "port_id"]].values]
    return linked


def concept_for(term, kg, about):
    """The port or reason a question word means, through the labels."""
    things = kg.ports if about == "port" else kg.reasons
    return labels(things).get(term)


def cancellations_for(question, linked, kg):
    """The rows of the log a question's words cover: every crossing from the port, or every crossing cancelled for
    the reason or any narrower one."""
    keep = pd.Series(False, index=linked.index)
    for term in question["terms"]:
        concept = concept_for(term, kg, question["about"])
        if concept is None:
            continue
        if question["about"] == "port":
            keep |= linked["port_id"] == concept
        else:
            keep |= linked["reason_id"].isin(narrower(kg.reasons, concept))
    return linked[keep]


def instances(kg, linked=None):
    """The instances of each class in the schema, by key."""
    inst = {"Port": set(kg.ports), "Vessel": set(kg.vessels), "Reason": set(kg.reasons),
            "Label": set(labels(kg.ports)) | set(labels(kg.reasons))}
    inst["Cancellation"] = set(linked["cancellation_id"]) if linked is not None else set()
    return inst


def relationships(kg, linked=None):
    """Every relationship the knowledge files and the linked log state, as (name, from, to) triples of keys. A label
    written for both a port and a reason appears twice, so the schema check sees it."""
    rels = [("BROADER", r, v["is_a"]) for r, v in kg.reasons.items() if v.get("is_a")]
    rels += [("MEANS", label, pid) for pid, p in kg.ports.items() for label in p["labels"]]
    rels += [("MEANS", label, rid) for rid, r in kg.reasons.items() for label in r["labels"]]
    if linked is not None:
        for r in linked.itertuples():
            rels += [("DEPARTS_FROM", r.cancellation_id, r.port_id), ("ON_VESSEL", r.cancellation_id, r.vessel_id),
                     ("FOR_REASON", r.cancellation_id, r.reason_id)]
    return rels


def check_against_schema(kg, linked=None, schema=None):
    """Check every relationship against the schema: the class at each end, and how many each instance has. Returns a
    list of violations, empty when the files and the log conform."""
    schema = schema or load_schema()
    inst = instances(kg, linked)
    rels = relationships(kg, linked)
    violations = []
    for spec in schema["relationships"]:
        allowed = set().union(*(inst[c] for c in spec["to"]))
        found = [(a, b) for name, a, b in rels if name == spec["name"] and a in inst[spec["from"]]]
        for a, b in found:
            if b not in allowed:
                violations.append(f"{spec['name']} from {a} to {b}: {b} is not a {' or '.join(spec['to'])}")
        counts = pd.Series([a for a, b in found if b in allowed], dtype=object).value_counts()
        for a in sorted(inst[spec["from"]]):
            n = int(counts.get(a, 0))
            if n < spec["min"] or (spec["max"] is not None and n > spec["max"]):
                bounds = f"{spec['min']}..{spec['max'] if spec['max'] is not None else '*'}"
                violations.append(f"{spec['from']} {a} has {n} {spec['name']}, expected {bounds}")
    return violations
