"""Answer the operator's questions two ways, and check each against the answer worked out by hand (Session 7).

    gozo-ask questions                  both routes, one line per question and route
    gozo-ask questions --route keyword  the keyword route only
    gozo-ask questions --show           also show which log entries each route counted
    gozo-ask profile                    the log as written: how many ways each port is written, how reasons are worded

The keyword route is what a simple assistant does with the log alone: keep the rows whose departure or reason
contains a word from the question. The knowledge route looks the word up in the labels of kg/ports.yaml or
kg/reasons.yaml, follows it to a port or a reason, and from a reason down the taxonomy to every narrower one.
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from gozo_ferry.knowledge import (cancellations_for, labels, link_log, load_knowledge, load_log, load_questions)
from gozo_ferry.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def keyword_rows(question, log):
    """Rows whose departure (for a port) or reason (for a reason) contains any of the question's words, ignoring
    case, as a search box would."""
    column = "departure" if question["about"] == "port" else "reason"
    pattern = "|".join(question["terms"])
    return log[log[column].str.contains(pattern, case=False, regex=True)]


def knowledge_rows(question, linked, kg):
    return cancellations_for(question, linked, kg)


def answer_from(rows, question, vessel_ids):
    """Turn the rows a route found into the answer the question asks for. vessel_ids maps each row to a vessel."""
    if question["ask"] == "count":
        return len(rows)
    if rows.empty:
        return None  # no row matched: the route cannot name a vessel
    counts = vessel_ids.loc[rows.index].value_counts()
    top = counts[counts == counts.max()].index
    return top[0] if len(top) == 1 else sorted(top)  # a tie is reported as a tie, never decided silently


def run_routes(question, log, linked, kg):
    """The answer of each route, with the rows each counted."""
    keyword = keyword_rows(question, log)
    knowledge = knowledge_rows(question, linked, kg)
    vessel_ids = linked["vessel_id"]
    return {"keyword": (answer_from(keyword, question, vessel_ids), keyword),
            "knowledge": (answer_from(knowledge, question, vessel_ids), knowledge)}


def show(value):
    return "(none)" if value is None else str(value)


def questions(args):
    kg = load_knowledge()
    log = load_log()
    linked = link_log(log, kg)
    routes = ["keyword", "knowledge"] if args.route == "both" else [args.route]
    print(f"{'question':<10} {'route':<10} {'answer':>8} {'expected':>8} {'right':>6}")
    for q in load_questions():
        results = run_routes(q, log, linked, kg)
        for route in routes:
            found, rows = results[route]
            right = found == q["expected"]
            print(f"{q['id']:<10} {route:<10} {show(found):>8} {show(q['expected']):>8} {'yes' if right else 'no':>6}")
            if args.show:
                written = rows["departure" if q["about"] == "port" else "reason"].value_counts()
                for text, n in written.items():
                    print(f"{'':<22}{n:>3}  {text}")
    return 0


def profile():
    kg = load_knowledge()
    log = load_log()
    linked = link_log(log, kg)
    print(f"cancellations in the log        {len(log)}")
    print(f"distinct departure spellings    {log['departure'].nunique()}")
    for pid, port in kg.ports.items():
        written = log.loc[linked["port_id"] == pid, "departure"].value_counts()
        detail = ", ".join(f"{text} {n}" for text, n in written.items())
        print(f"  {port['name']:<10} {len(written)} ways, {int(written.sum())} cancellations: {detail}")
    print(f"distinct reason wordings        {log['reason'].nunique()}")
    reason_names = {rid: r["name"] for rid, r in kg.reasons.items()}
    for rid, group in linked.groupby("reason_id"):
        written = group["reason"].value_counts()
        detail = ", ".join(f"{text} {n}" for text, n in written.items())
        print(f"  {reason_names[rid]:<12} {len(group):>3}: {detail}")
    print(f"vessels                         {log['vessel'].nunique()}: "
          + ", ".join(f"{v} {n}" for v, n in log['vessel'].value_counts().items()))
    print(f"labels in the knowledge files   {len(labels(kg.ports)) + len(labels(kg.reasons))}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Answer the operator's questions and check the answers.")
    sub = parser.add_subparsers(dest="command", required=True)
    q = sub.add_parser("questions")
    q.add_argument("--route", choices=["keyword", "knowledge", "both"], default="both")
    q.add_argument("--show", action="store_true")
    sub.add_parser("profile")
    args = parser.parse_args(argv)

    load_dotenv()
    setup_logging(os.environ.get("LOG_LEVEL", "WARNING"))
    try:
        if args.command == "questions":
            sys.exit(questions(args))
        sys.exit(profile())
    except ValueError as err:
        logger.error("%s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
