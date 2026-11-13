"""SHACL validation of the graph."""

from __future__ import annotations

from pathlib import Path

from pyshacl import validate as shacl_validate
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import SH


def validate_graph(data: Graph, shapes_path: Path | str):
    """Return (conforms, violations) where violations is a list of (focus node, message)."""
    shapes = Graph().parse(str(shapes_path), format="turtle")
    conforms, report_graph, _ = shacl_validate(data, shacl_graph=shapes, inference="none")
    violations = []
    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        focus = report_graph.value(result, SH.focusNode)
        message = report_graph.value(result, SH.resultMessage)
        violations.append((str(focus).rsplit("/", 1)[-1], str(message)))
    return bool(conforms), sorted(violations)
