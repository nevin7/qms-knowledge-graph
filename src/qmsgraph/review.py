"""Human-in-the-loop review: only confirmed links enter the graph.

Triage rules (thresholds are adjustable):
    confidence >= auto      -> accepted automatically
    review <= conf < auto   -> goes to the review queue for a person to accept or reject
    confidence < review     -> discarded
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from .tagging import Suggestion

QUEUE_FIELDS = ["record_id", "entity_id", "kind", "mention", "confidence", "method", "note"]
DECISION_FIELDS = ["record_id", "entity_id", "decision", "reviewer_note"]


def triage(suggestions: list[Suggestion], auto: float = 0.90, review: float = 0.50):
    accepted, queue, discarded = [], [], []
    for s in suggestions:
        if s.method == "llm":
            (queue if s.confidence >= review else discarded).append(s)   # LLM output is never auto-accepted
        elif s.confidence >= auto:
            accepted.append(s)
        elif s.confidence >= review:
            queue.append(s)
        else:
            discarded.append(s)
    return accepted, queue, discarded


def write_queue(queue: list[Suggestion], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUEUE_FIELDS)
        writer.writeheader()
        for s in queue:
            writer.writerow({k: v for k, v in asdict(s).items() if k in QUEUE_FIELDS})


def read_decisions(path: Path | str) -> dict[tuple[str, str], str]:
    path = Path(path)
    if not path.exists():
        return {}
    decisions: dict[tuple[str, str], str] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            decision = row["decision"].strip().lower()
            if decision not in {"accept", "reject"}:
                raise ValueError(f"Decision must be 'accept' or 'reject' (got {row['decision']!r}) for {row['record_id']}")
            decisions[(row["record_id"], row["entity_id"])] = decision
    return decisions


def apply_decisions(queue: list[Suggestion], decisions: dict[tuple[str, str], str]):
    """Split the queue into accepted, rejected, and still-pending suggestions."""
    accepted, rejected, pending = [], [], []
    for s in queue:
        decision = decisions.get((s.record_id, s.entity_id))
        if decision == "accept":
            accepted.append(s)
        elif decision == "reject":
            rejected.append(s)
        else:
            pending.append(s)
    return accepted, rejected, pending
