"""Command line: run the whole pipeline end to end.

    qmsgraph run --data data --out out
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter
from pathlib import Path

from .graph import build_graph, load_records
from .queries import run_query
from .review import apply_decisions, read_decisions, triage, write_queue
from .tagging import RuleBasedTagger
from .validate import validate_graph
from .vocab import load_vocabulary

log = logging.getLogger("qmsgraph")
ROOT = Path(__file__).resolve().parents[2]

# (file, human description, bound term or None)
QUERIES = [
    ("cq1_records_by_equipment_term.rq", "Everything linked to 'press 4' (slang name), via deviation, investigation, CAPA", "press 4"),
    ("cq2_repeat_equipment_type_across_sites.rq", "Equipment types with deviations at more than one site", None),
    ("cq3_deviations_without_capa.rq", "Deviations with no CAPA yet", None),
    ("cq4_product_history.rq", "Everything linked to the product 'cardiostat 20'", "cardiostat 20"),
    ("cq5_deviations_under_area.rq", "Deviations anywhere under the 'Solid Dose Area' (equipment hierarchy)", "Solid Dose Area"),
]


def write_rows(path: Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def run_pipeline(data_dir: Path, out_dir: Path, auto: float = 0.90, review: float = 0.50) -> dict:
    vocab = load_vocabulary(data_dir / "vocab.json")
    records = load_records(data_dir / "records.csv")
    tagger = RuleBasedTagger(vocab)

    suggestions = []
    for r in records:
        suggestions.extend(tagger.suggest(r.record_id, r.site_id, r.text))
    auto_accepted, queue, discarded = triage(suggestions, auto=auto, review=review)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_queue(queue, out_dir / "review_queue.csv")
    decisions = read_decisions(data_dir / "decisions.csv")
    accepted, rejected, pending = apply_decisions(queue, decisions)

    links = auto_accepted + accepted
    hierarchy_file = data_dir / "hierarchy.json"
    graph = build_graph(ROOT / "ontology" / "qms.ttl", vocab, records, links,
                        hierarchy_path=hierarchy_file if hierarchy_file.exists() else None)
    graph.serialize(out_dir / "graph.ttl", format="turtle")

    conforms, violations = validate_graph(graph, ROOT / "shapes" / "qms_shapes.ttl")
    (out_dir / "validation_report.txt").write_text(
        "Conforms: %s\n%s\n" % (conforms, "\n".join(f"- {focus}: {msg}" for focus, msg in violations)),
        encoding="utf-8")

    results = {}
    for filename, _desc, term in QUERIES:
        header, rows = run_query(graph, ROOT / "queries" / filename, term)
        write_rows(out_dir / "results" / filename.replace(".rq", ".csv"), header, rows)
        results[filename] = (header, rows)

    return {
        "records": len(records), "suggestions": len(suggestions),
        "auto_accepted": len(auto_accepted), "queued": len(queue), "discarded": len(discarded),
        "review_accepted": len(accepted), "review_rejected": len(rejected), "review_pending": len(pending),
        "links_in_graph": len(links), "triples": len(graph),
        "conforms": conforms, "violations": violations, "results": results,
        "by_kind": dict(Counter(s.kind for s in links)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qmsgraph", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Tag, review, build the graph, validate, and query.")
    run.add_argument("--data", type=Path, default=ROOT / "data")
    run.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    summary = run_pipeline(args.data, args.out)
    log.info("Records: %d | tag suggestions: %d", summary["records"], summary["suggestions"])
    log.info("Auto-accepted: %d | sent to review: %d | discarded: %d",
             summary["auto_accepted"], summary["queued"], summary["discarded"])
    log.info("Review outcome: %d accepted, %d rejected, %d still pending (pending items are NOT in the graph)",
             summary["review_accepted"], summary["review_rejected"], summary["review_pending"])
    log.info("Graph: %d confirmed links, %d triples", summary["links_in_graph"], summary["triples"])
    log.info("SHACL conforms: %s", summary["conforms"])
    for focus, message in summary["violations"]:
        log.info("  violation at %s: %s", focus, message)
    for filename, desc, _term in QUERIES:
        header, rows = summary["results"][filename]
        log.info("\n%s (%d rows)", desc, len(rows))
        for row in rows[:8]:
            log.info("  " + " | ".join(row))
    log.info("\nFiles written to %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
