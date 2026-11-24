# ADR 0001: Add a knowledge layer for the ferry's cancellations

- Status: accepted
- Date: 2026-11-24
- Deciders: the operator's operations manager, the data team
- Session: ARI3217 Session 7, Practice Exercise (Stages 16 and 17)

## Context

The operator wants to ask an assistant questions about its cancelled crossings. The log
(data/gozo_operations_2025.csv) holds 77 cancellations of 2025, with the date, the time, the vessel, the
port of departure and the reason, written by staff on duty. It has no identifier, and nothing in it says
what an entry means: the two ports are written ten ways and the reasons fourteen ways, and no entry says
"weather" or "technical".

Asked through the log alone, every question goes wrong (gozo-ask questions --route keyword):

- "How many crossings from Mġarr were cancelled?" A search for "Mgarr" finds 22, a search for "Mġarr" finds
  12, and the answer is 34: each search misses the spellings of the other.
- "How many cancellations did the weather cause?" A search for "weather" finds 0; the answer is 61, worded
  as gale warnings, swell, rough sea, gusts and fog.
- "Which vessel had the most technical cancellations?" A search for "technical" finds no entry, so no
  vessel; the answer is MV Ramla, with 5 of the 10.

The model of Sessions 2 to 6 is unaffected: it predicts from the daily wind in data/gozo_ferry.csv, which
this log does not change. The problem is meaning, not quality.

## Options considered

1. Do nothing, and improve the assistant's prompt. Rejected: a prompt might guess that "Mgarr Harbour" is
   Mġarr, but it cannot be tested, and it cannot know the operator's decisions, such as that a gale warning
   counts as a wind cancellation.
2. Clean the log: add a port column and a reason-category column, filled in once. Cheapest, and enough for
   all three questions today. Rejected: every new entry would need cleaning by hand at the moment it is
   written, one category column cannot hold "sea state, which is weather" for a question about either, and
   the decisions behind the cleaning would live nowhere.
3. Vector retrieval over the reasons. Rejected: "steering alarm" is no closer to "technical" in wording than
   to "operational"; similarity cannot apply the operator's decisions.
4. A knowledge layer: the ports with every spelling, a taxonomy of reasons with every wording, and the vessels,
   as reviewed files with a schema, with every log entry linked to a port, a vessel and a reason. Chosen.

## Decision

Keep the ferry's knowledge in kg/ as a versioned release of reviewed files, written against an explicit schema
(kg/schema.yaml): the ports and their spellings, the reasons as a taxonomy (weather above wind, sea state and
visibility; technical; operational) with their wordings, and the vessels. Release v1.0 covers the 2025 log. From
Stage 17, build it into an RDF graph (RDF, SKOS, SPARQL): the reasons as a SKOS concept scheme, every spelling and
wording as an alternative label. The log stays as written; the knowledge links to it.

The log has no identifier, so the key of a cancellation is the date, the time and the port of departure, and each
cancellation's IRI is minted from it. The date and time alone are not enough: on 26 January at 07:30 and on 23
December at 18:45, crossings from both ports were cancelled. The vessel is not part of the key, because a crossing
is scheduled by port and time and the vessel assigned to it can change; date, time and vessel would also be unique
today, but would name the same crossing twice if a vessel were swapped. The time is normalised to two digits for
the hour, so "7:30" and "07:30" give the same key.

## Consequences

- A new spelling or wording stops the build until it is added to kg/ports.yaml or kg/reasons.yaml: an entry is
  never dropped or guessed. The operations manager decides whether it is a spelling of a known port or reason, or
  something new.
- Some entries are decisions about meaning, recorded as comments where they are made: a gale warning is a wind
  cancellation although no gust was measured; swell at the harbour entrance is sea state, not a port operation; a
  steering alarm is technical even if no fault is found. Changing one changes answers, so it goes through review.
- One more artefact to build, version and check; the graph is derived from the files and the log and is rebuilt.
- A perfect score shows that the routes apply these decisions, not that the decisions are right: the expected
  answers were worked out by the same person who wrote the labels.
- Revisit this decision if the log stays one file a year, written by one team, with no new spellings: cleaning the
  columns (option 2) would then be enough. Revisit it in the other direction if a second source arrives (the
  harbour authority's log, or the vessels' own logs, with their own names), or if passengers ask the assistant
  directly: each makes the case stronger.
