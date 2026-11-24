"""The ferry's knowledge layer as an RDF graph (Session 7, Stage 17). These tests need no server: the graph is built
in memory from the same files and log that make kg-load uses."""
import pytest
from rdflib import Graph
from rdflib.namespace import OWL

from gozo_ferry.graph import RELEASE, add_knowledge, answer, build_inputs, cancellation_iri, save_store
from gozo_ferry.knowledge import load_questions, load_schema


@pytest.fixture(scope="module")
def inputs():
    return build_inputs()


@pytest.fixture(scope="module")
def graph(inputs):
    return add_knowledge(Graph(), *inputs)


def test_every_cancellation_gets_a_unique_iri(inputs):
    _, linked = inputs
    iris = [cancellation_iri(row) for row in linked.to_dict("records")]
    assert len(iris) == len(set(iris)) == 77


def test_loading_twice_changes_nothing(inputs):
    g = add_knowledge(Graph(), *inputs)
    once = len(g)
    add_knowledge(g, *inputs)
    assert len(g) == once


def test_the_same_graph_always_gives_the_same_store(inputs, tmp_path):
    first = save_store(add_knowledge(Graph(), *inputs), tmp_path / "a.nt")
    second = save_store(add_knowledge(Graph(), *inputs), tmp_path / "b.nt")
    assert first == second


def test_sparql_gives_the_expected_answers(graph):
    for q in load_questions():
        assert answer(graph, q) == q["expected"], q["id"]


def test_either_spelling_finds_every_crossing_from_mgarr(graph):
    """A keyword search for Mgarr and one for Mġarr give different answers; through the labels, both give 34."""
    for spelling in ("Mgarr", "Mġarr", "MGARR"):
        q = {"ask": "count", "about": "port", "terms": [spelling]}
        assert answer(graph, q) == 34, spelling


def test_the_graph_states_the_release_it_was_built_from(graph):
    assert [str(v) for v in graph.objects(RELEASE, OWL.versionInfo)] == [load_schema()["version"]]
