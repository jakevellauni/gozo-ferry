"""The ferry's knowledge files must conform to their schema, link every row of the log, and answer the competency
questions (Session 7, Stage 16, Practice Exercise)."""
import hashlib

import pytest

from gozo_ferry.ask import run_routes
from gozo_ferry.knowledge import (check_against_schema, labels, link_log, load_knowledge, load_log, load_questions)

# The data of the earlier sessions must not change: the model, the gate and the monitoring depend on them. The log is
# new in Session 7 and is pinned too: the expected answers were worked out from exactly this file.
DATA_SHA256 = {
    "data/gozo_ferry.csv": "ebd606dde638a982a5d3be651e8e2a38af81222217a229d4d558b02d8d0f74ba",
    "data/holdout.csv": "fa8745708256b933415deaca764ce549328e69344b15280cccc7fa06dfc3d91d",
    "data/gozo_operations_2025.csv": "04ad294553946908ca87bcd9d2a28e35898b71c45b626ca251fd893b563f06af",
}


@pytest.fixture(scope="module")
def kg():
    return load_knowledge()


@pytest.fixture(scope="module")
def log():
    return load_log()


@pytest.fixture(scope="module")
def linked(log, kg):
    return link_log(log, kg)  # raises if a port, a reason or a vessel has no match


@pytest.mark.parametrize("path", sorted(DATA_SHA256))
def test_the_data_is_unchanged(path):
    with open(path, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == DATA_SHA256[path]


def test_the_knowledge_and_the_log_conform_to_the_schema(kg, linked):
    assert check_against_schema(kg, linked) == []


def test_every_cancellation_gets_a_unique_key(linked):
    assert linked["cancellation_id"].is_unique


def test_no_label_means_two_things(kg):
    port_labels, reason_labels = labels(kg.ports), labels(kg.reasons)
    for things in (kg.ports, kg.reasons):
        written = [label for t in things.values() for label in t["labels"]]
        assert len(written) == len(set(written))
    assert not set(port_labels) & set(reason_labels)


def test_the_reason_taxonomy_has_no_cycles(kg):
    for start in kg.reasons:
        seen, current = set(), start
        while current is not None:
            assert current not in seen, f"cycle through {current}"
            seen.add(current)
            current = kg.reasons[current].get("is_a")


def test_an_unknown_spelling_stops_the_build(kg, log):
    changed = log.copy()
    changed.loc[0, "departure"] = "Mgarr port"
    with pytest.raises(ValueError, match="Mgarr port"):
        link_log(changed, kg)


def test_the_knowledge_route_gives_the_expected_answers(kg, log, linked):
    for q in load_questions():
        found, _ = run_routes(q, log, linked, kg)["knowledge"]
        assert found == q["expected"], q["id"]


def test_the_keyword_route_does_not(kg, log, linked):
    """The gap between the routes is the result: a search over the log as written misses spellings and wordings."""
    for q in load_questions():
        found, _ = run_routes(q, log, linked, kg)["keyword"]
        assert found != q["expected"], q["id"]
