"""Build the RDF knowledge graph from the ontology, vocabulary, records, and confirmed links."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import SKOS, XSD

from .tagging import Suggestion
from .vocab import Vocabulary

QMS = Namespace("http://example.org/qms#")
DATA = Namespace("http://example.org/qms/data/")

RECORD_CLASS = {"Deviation": QMS.Deviation, "Investigation": QMS.Investigation, "CAPA": QMS.CAPA}


@dataclass
class Record:
    record_id: str
    record_type: str
    site_id: str
    opened_on: str
    title: str
    description: str
    parent_id: str

    @property
    def text(self) -> str:
        return f"{self.title}. {self.description}"


def load_records(path: Path | str) -> list[Record]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [Record(**{k: (v or "") for k, v in row.items()}) for row in csv.DictReader(handle)]


def _iri(prefix: str, ident: str) -> URIRef:
    return URIRef(f"{DATA}{prefix}/{ident}")


def add_hierarchy(g: Graph, hierarchy_path: Path | str, site_ids: set[str]) -> None:
    """Add areas, lines, and direct partOf links from data/hierarchy.json.

    Only the direct parent of each item is stored. Queries follow the chain with a property path.
    """
    data = json.loads(Path(hierarchy_path).read_text(encoding="utf-8"))
    kind_class = {"Area": QMS.Area, "Line": QMS.Line}
    for node in data["nodes"]:
        iri = _iri("hierarchy", node["id"])
        g.add((iri, RDF.type, kind_class[node["kind"]]))
        g.add((iri, RDFS.label, Literal(node["label"])))
        parent = node["parent"]
        parent_iri = _iri("site", parent) if parent in site_ids else _iri("hierarchy", parent)
        g.add((iri, QMS.partOf, parent_iri))
    for equipment_id, parent_id in data["equipment_parent"].items():
        g.add((_iri("equipment", equipment_id), QMS.partOf, _iri("hierarchy", parent_id)))


def build_graph(ontology_path: Path | str, vocab: Vocabulary, records: list[Record],
                links: list[Suggestion], hierarchy_path: Path | str | None = None) -> Graph:
    g = Graph()
    g.bind("qms", QMS)
    g.bind("skos", SKOS)
    g.parse(str(ontology_path), format="turtle")

    for site_id, label in vocab.sites.items():
        site = _iri("site", site_id)
        g.add((site, RDF.type, QMS.Site))
        g.add((site, RDFS.label, Literal(label)))

    for entity in vocab.entities:
        node = _iri(entity.kind, entity.id)
        g.add((node, RDF.type, QMS.Product if entity.kind == "product" else QMS.Equipment))
        g.add((node, RDF.type, SKOS.Concept))
        g.add((node, SKOS.prefLabel, Literal(entity.label)))
        for alias in entity.aliases:
            g.add((node, SKOS.altLabel, Literal(alias)))
        if entity.kind == "equipment":
            g.add((node, QMS.equipmentType, Literal(entity.type)))
            g.add((node, QMS.equipmentAt, _iri("site", entity.site)))

    known_ids = {r.record_id for r in records}
    for r in records:
        node = _iri("record", r.record_id)
        g.add((node, RDF.type, RECORD_CLASS[r.record_type]))
        g.add((node, QMS.recordId, Literal(r.record_id)))
        g.add((node, QMS.openedOn, Literal(date.fromisoformat(r.opened_on), datatype=XSD.date)))
        g.add((node, QMS.description, Literal(r.text)))
        g.add((node, QMS.occurredAt, _iri("site", r.site_id)))
        if r.parent_id and r.parent_id in known_ids:     # a missing parent is left out so SHACL can flag it
            parent = _iri("record", r.parent_id)
            predicate = QMS.investigates if r.record_type == "Investigation" else QMS.correctiveActionFor
            g.add((node, predicate, parent))

    for link in links:
        predicate = QMS.aboutProduct if link.kind == "product" else QMS.aboutEquipment
        g.add((_iri("record", link.record_id), predicate, _iri(link.kind, link.entity_id)))
    if hierarchy_path is not None:
        add_hierarchy(g, hierarchy_path, set(vocab.sites))
    return g
