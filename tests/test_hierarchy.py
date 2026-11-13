from rdflib import Graph, Namespace

from qmsgraph.cli import run_pipeline
from qmsgraph.graph import QMS, build_graph
from qmsgraph.validate import validate_graph

D = Namespace("http://example.org/qms/data/")


def _graph(root, vocab, records, with_hierarchy=True):
    path = root / "data" / "hierarchy.json" if with_hierarchy else None
    return build_graph(root / "ontology" / "qms.ttl", vocab, [r for r in records if r.record_id != "CAPA-0008"],
                       links=[], hierarchy_path=path)


def test_direct_partof_links_are_stored(root, vocab, records):
    g = _graph(root, vocab, records)
    assert (D["equipment/EQ-N-TP04"], QMS.partOf, D["hierarchy/LINE-N-CMP1"]) in g
    assert (D["hierarchy/LINE-N-CMP1"], QMS.partOf, D["hierarchy/AREA-N-SD"]) in g
    assert (D["hierarchy/AREA-N-SD"], QMS.partOf, D["site/SITE-N"]) in g
    # only direct parents are stored; the chain is followed by queries, not copied into the graph
    assert (D["equipment/EQ-N-TP04"], QMS.partOf, D["hierarchy/AREA-N-SD"]) not in g


def test_equipment_can_sit_directly_under_an_area(root, vocab, records):
    g = _graph(root, vocab, records)
    assert (D["equipment/EQ-E-AC07"], QMS.partOf, D["hierarchy/AREA-E-ST"]) in g


def test_graph_with_hierarchy_conforms(root, vocab, records):
    conforms, violations = validate_graph(_graph(root, vocab, records), root / "shapes" / "qms_shapes.ttl")
    assert conforms and violations == []


def test_equipment_without_a_parent_is_flagged(root, vocab, records):
    g = _graph(root, vocab, records, with_hierarchy=False)
    conforms, violations = validate_graph(g, root / "shapes" / "qms_shapes.ttl")
    assert not conforms
    assert {focus for focus, _ in violations} == {e.id for e in vocab.entities if e.kind == "equipment"}


def test_equipment_with_two_parents_is_flagged(root, vocab, records):
    g = _graph(root, vocab, records)
    g.add((D["equipment/EQ-N-TP04"], QMS.partOf, D["hierarchy/LINE-N-CT1"]))
    conforms, violations = validate_graph(g, root / "shapes" / "qms_shapes.ttl")
    assert not conforms and [focus for focus, _ in violations] == ["EQ-N-TP04"]


def test_line_must_sit_under_an_area_not_a_site(root, vocab, records):
    g = _graph(root, vocab, records)
    g.remove((D["hierarchy/LINE-N-CMP1"], QMS.partOf, D["hierarchy/AREA-N-SD"]))
    g.add((D["hierarchy/LINE-N-CMP1"], QMS.partOf, D["site/SITE-N"]))
    conforms, violations = validate_graph(g, root / "shapes" / "qms_shapes.ttl")
    assert not conforms and [focus for focus, _ in violations] == ["LINE-N-CMP1"]


def test_area_query_finds_deviations_through_the_chain(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    header, rows = summary["results"]["cq5_deviations_under_area.rq"]
    assert header == ["unit", "site", "equipment", "recordId"]
    by_site = {}
    for unit, site, equipment, record_id in rows:
        by_site.setdefault(site, set()).add(record_id)
    # same area name at two plants, kept apart by site
    assert set(by_site) == {"Plant North", "Plant East"}
    # North: press TP-04 sits under Compression Line 1, coating pan CP-02 under Coating Line 1,
    # both inside the Solid Dose Area. Neither deviation text names the area.
    assert {"DEV-0001", "DEV-0010"} <= by_site["Plant North"]
    assert "DEV-0003" in by_site["Plant North"]
    assert {"DEV-0002", "DEV-0013"} <= by_site["Plant East"]
    # equipment from other areas is not included
    assert "DEV-0004" not in by_site["Plant North"]          # mixer 11 is in the Semi-Solids Area
    assert "DEV-0007" not in by_site["Plant East"]           # autoclave 7 is in the Sterilization Area


def test_pipeline_still_flags_only_the_planted_defect(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    assert summary["violations"] == [("CAPA-0008", "Every CAPA must point to at least one investigation.")]
