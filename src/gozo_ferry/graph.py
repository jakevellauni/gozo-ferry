"""The ferry's knowledge layer as an RDF graph (Session 7, Stage 17, Practice Exercise).

    gozo-kg load    add the knowledge files and the cancellation log to the graph store, kg/build/gozo.nt
    gozo-kg count   triples in the store, instances of each class, uses of each property, and the store's SHA-256
    gozo-kg ask     answer the operator's questions in SPARQL and check them, as gozo-ask does
    gozo-kg check   what make ci runs: build the store from nothing, load it again, require the same SHA-256, and
                    answer every question from the store as written

The store is a file of N-Triples, one triple per line, written in sorted order: the same content always gives the
same file, and so the same SHA-256. Loading adds to what the store already holds, as loading into any triple store
does. It is idempotent because every resource is named by an IRI minted from its key, and a graph is a set of
triples: adding a triple the graph already holds changes nothing.
"""
import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace
from rdflib.namespace import OWL, SKOS

from gozo_ferry.knowledge import link_log, load_knowledge, load_log, load_questions, load_schema
from gozo_ferry.logging_setup import setup_logging

logger = logging.getLogger(__name__)

STORE_PATH = Path("kg/build/gozo.nt")

# Every IRI the operator mints starts here. example.org is reserved for examples, so it can never clash with a real
# site.
GOZO = Namespace("https://ari3217.example.org/gozo/")
REASONS = GOZO["scheme/reasons"]
# The graph says which release of the knowledge it was built from, so any answer can be traced to a release.
RELEASE = GOZO["knowledge"]


# One function per kind of resource: the IRI is the key, so the same thing always gets the same name.
def port_iri(port_id):
    return GOZO[f"port/{port_id}"]


def reason_iri(reason_id):
    return GOZO[f"reason/{reason_id}"]


def vessel_iri(vessel_id):
    return GOZO[f"vessel/{vessel_id}"]


def cancellation_iri(row):
    """Minted from the key chosen in ADR 0001: the date, the time and the port of departure. cancellation_id holds the
    same key, with the time already normalised to two digits for the hour."""
    date, time, port = row["cancellation_id"].split("|")
    return GOZO[f"cancellation/{date}/{time.replace(':', '-')}/{port}"]


def add_knowledge(g, kg, linked, version=None):
    """Add the knowledge files and the linked log to the graph g, as triples."""
    g.bind("gozo", GOZO)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.add((RELEASE, RDF.type, GOZO.KnowledgeRelease))
    g.add((RELEASE, OWL.versionInfo, Literal(version or load_schema()["version"])))
    # The reasons are a SKOS concept scheme. skos:broader says "is a kind of"; every wording is an alternative label.
    g.add((REASONS, RDF.type, SKOS.ConceptScheme))
    g.add((REASONS, SKOS.prefLabel, Literal("Reasons for cancelling a crossing", lang="en")))
    for rid, r in kg.reasons.items():
        node = reason_iri(rid)
        g.add((node, RDF.type, SKOS.Concept))
        g.add((node, RDF.type, GOZO.Reason))
        g.add((node, SKOS.prefLabel, Literal(r["name"], lang="en")))
        g.add((node, SKOS.inScheme, REASONS))
        if r.get("is_a"):
            g.add((node, SKOS.broader, reason_iri(r["is_a"])))
        else:
            g.add((node, SKOS.topConceptOf, REASONS))
        for label in r["labels"]:
            g.add((node, SKOS.altLabel, Literal(label, lang="en")))
    # A port's official name in Maltese, and every spelling staff wrote, exactly as written, with no language tag:
    # "Mgarr Harbour" and "CIRKEWWA" are spellings of a name, not words of a language.
    for pid, p in kg.ports.items():
        node = port_iri(pid)
        g.add((node, RDF.type, GOZO.Port))
        g.add((node, GOZO.portId, Literal(pid)))
        g.add((node, SKOS.prefLabel, Literal(p["name"], lang="mt")))
        for label in p["labels"]:
            g.add((node, SKOS.altLabel, Literal(label)))
    for vid, v in kg.vessels.items():
        node = vessel_iri(vid)
        g.add((node, RDF.type, GOZO.Vessel))
        g.add((node, GOZO.vesselId, Literal(vid)))
        g.add((node, RDFS.label, Literal(v["name"])))
    for row in linked.to_dict("records"):
        node = cancellation_iri(row)
        date, time, _ = row["cancellation_id"].split("|")
        g.add((node, RDF.type, GOZO.Cancellation))
        g.add((node, GOZO.onDate, Literal(date, datatype=XSD.date)))
        g.add((node, GOZO.atTime, Literal(f"{time}:00", datatype=XSD.time)))
        g.add((node, GOZO.departsFrom, port_iri(row["port_id"])))
        g.add((node, GOZO.onVessel, vessel_iri(row["vessel_id"])))
        g.add((node, GOZO.forReason, reason_iri(row["reason_id"])))
        # What staff wrote is kept beside what it means, so any link can be checked against the log.
        g.add((node, GOZO.recordedDeparture, Literal(row["departure"])))
        g.add((node, GOZO.recordedReason, Literal(row["reason"], lang="en")))
    return g


def open_store(path=STORE_PATH):
    g = Graph()
    g.bind("gozo", GOZO)
    g.bind("skos", SKOS)
    if path.exists():
        g.parse(path, format="nt")
    return g


def save_store(g, path=STORE_PATH):
    """Write the graph as sorted N-Triples, so that the same graph always gives the same file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted(line for line in g.serialize(format="nt").splitlines() if line.strip())
    path.write_text("\n".join(lines) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_inputs():
    kg = load_knowledge()
    return kg, link_log(load_log(), kg)


def load():
    kg, linked = build_inputs()
    g = open_store()
    before = len(g)
    add_knowledge(g, kg, linked)
    fingerprint = save_store(g)
    logger.info("Store %s: %d triples before, %d after", STORE_PATH, before, len(g))
    print(f"triples before {before}, after {len(g)}; sha256 {fingerprint[:16]}")


PREFIXES = """
PREFIX gozo: <https://ari3217.example.org/gozo/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

COUNT_CLASSES = PREFIXES + """
SELECT ?class (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?class }
GROUP BY ?class ORDER BY ?class
"""

COUNT_PROPERTIES = PREFIXES + """
SELECT ?property (COUNT(*) AS ?n) WHERE { ?s ?property ?o }
GROUP BY ?property ORDER BY ?property
"""


def count(g):
    print(f"{'triples':<24} {len(g):>6}")
    for row in g.query(COUNT_CLASSES):
        print(f"{g.qname(row['class']):<24} {int(row['n']):>6}")
    for row in g.query(COUNT_PROPERTIES):
        print(f"{g.qname(row['property']):<24} {int(row['n']):>6}")
    for version in sorted(str(v) for v in g.objects(RELEASE, OWL.versionInfo)):
        print(f"{'release':<24} {version:>6}")
    if STORE_PATH.exists():
        print(f"{'sha256':<24} {hashlib.sha256(STORE_PATH.read_bytes()).hexdigest()[:16]}")


# The cancellations a question's words cover. The word is looked up as an alternative label: of a port, reached by
# gozo:departsFrom; or of a reason, reached from the cancellation's reason by zero or more skos:broader steps, so that
# "weather" covers wind, sea state and visibility. skos:broader* is transitivity written into the query.
COVERS = {
    "port": """
  VALUES ?term { %(terms)s }
  ?port a gozo:Port ; skos:altLabel ?term .
  ?cancellation gozo:departsFrom ?port .
""",
    "reason": """
  VALUES ?term { %(terms)s }
  ?reason a gozo:Reason ; skos:altLabel ?term .
  ?cancellation gozo:forReason/skos:broader* ?reason .
""",
}

COUNT = PREFIXES + """
SELECT (COUNT(DISTINCT ?cancellation) AS ?n) WHERE {
%(covers)s}
"""

# The vessels, by how many of the covered cancellations each had, most first.
BY_VESSEL = PREFIXES + """
SELECT ?id (COUNT(DISTINCT ?cancellation) AS ?n) WHERE {
%(covers)s  ?cancellation gozo:onVessel ?vessel .
  ?vessel gozo:vesselId ?id .
}
GROUP BY ?id ORDER BY DESC(?n) ?id
"""


def terms_of(question):
    """The question's words as SPARQL literals. Reason labels are English; port spellings carry no language tag.
    The words come from kg/questions.yaml, a reviewed file, never from a user: a user's words would be bound as
    variables, with initBindings, never pasted into the text of a query."""
    lang = "en" if question["about"] == "reason" else None
    return " ".join(Literal(t, lang=lang).n3() for t in question["terms"])


def answer(g, question):
    covers = COVERS[question["about"]] % {"terms": terms_of(question)}
    if question["ask"] == "count":
        return int(next(iter(g.query(COUNT % {"covers": covers})))["n"])
    rows = [(str(r["id"]), int(r["n"])) for r in g.query(BY_VESSEL % {"covers": covers})]
    if not rows:
        return None
    top = [vid for vid, n in rows if n == rows[0][1]]
    return top[0] if len(top) == 1 else sorted(top)  # a tie is reported as a tie


def ask(g):
    print(f"{'question':<10} {'route':<10} {'answer':>8} {'expected':>8} {'right':>6}")
    failures = 0
    for q in load_questions():
        found = answer(g, q)
        right = found == q["expected"]
        failures += not right
        print(f"{q['id']:<10} {'graph':<10} {str(found):>8} {str(q['expected']):>8} {'yes' if right else 'no':>6}")
    return 1 if failures else 0


def check():
    """Build the store from nothing, load the same release again, and require that the store does not change; then
    answer every question from the store as it was written to disk, so that what is checked is the artefact."""
    kg, linked = build_inputs()
    STORE_PATH.unlink(missing_ok=True)
    g = open_store()
    add_knowledge(g, kg, linked)
    first, size = save_store(g), len(g)
    g = open_store()
    add_knowledge(g, kg, linked)
    second = save_store(g)
    version = load_schema()["version"]
    print(f"release {version}: {size} triples, {len(g)} after a second load; sha256 {first[:16]}, then {second[:16]}")
    if second != first:
        print("The second load changed the store: some resource is not named by its key.", file=sys.stderr)
        return 1
    return ask(open_store())


def main(argv=None):
    parser = argparse.ArgumentParser(description="The ferry's knowledge layer as an RDF graph.")
    parser.add_argument("command", choices=["load", "count", "ask", "check"])
    args = parser.parse_args(argv)
    setup_logging(os.environ.get("LOG_LEVEL", "WARNING"))
    try:
        if args.command == "load":
            load()
            return 0
        if args.command == "check":
            return check()
    except ValueError as err:
        logger.error("%s", err)
        return 1
    if not STORE_PATH.exists():
        print(f"No graph store yet at {STORE_PATH}: run make kg-load first.", file=sys.stderr)
        return 1
    g = open_store()
    if args.command == "count":
        count(g)
        return 0
    return ask(g)


if __name__ == "__main__":
    sys.exit(main())
