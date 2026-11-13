"""Run the SPARQL competency queries."""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Literal


def run_query(graph: Graph, path: Path | str, term: str | None = None):
    """Run a .rq file. If `term` is given it is bound to the ?term variable."""
    text = Path(path).read_text(encoding="utf-8")
    bindings = {"term": Literal(term)} if term is not None else None
    result = graph.query(text, initBindings=bindings)
    header = [str(v) for v in result.vars]
    rows = [[("" if cell is None else str(cell)) for cell in row] for row in result]
    return header, rows
