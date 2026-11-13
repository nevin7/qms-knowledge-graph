from rdflib import Graph, Namespace

from qmsgraph.cli import run_pipeline
from qmsgraph.graph import QMS, build_graph, load_records
from qmsgraph.queries import run_query
from qmsgraph.validate import validate_graph


def test_pipeline_end_to_end(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    assert summary["records"] == 37
    assert summary["review_pending"] == 1                 # DEV-0016 is left for a person to decide
    assert summary["review_accepted"] == 3 and summary["review_rejected"] == 1
    assert (tmp_path / "graph.ttl").exists() and (tmp_path / "review_queue.csv").exists()


def test_only_confirmed_links_are_in_the_graph(root, tmp_path):
    run_pipeline(root / "data", tmp_path)
    g = Graph().parse(str(tmp_path / "graph.ttl"), format="turtle")
    D = Namespace("http://example.org/qms/data/")
    # the rejected cross-site reference is absent, and the pending suggestion is absent
    assert (D["record/DEV-0017"], QMS.aboutEquipment, D["equipment/EQ-N-CP02"]) not in g
    assert (D["record/DEV-0016"], QMS.aboutEquipment, D["equipment/EQ-S-AI01"]) not in g
    # accepted typo link is present
    assert (D["record/DEV-0010"], QMS.aboutEquipment, D["equipment/EQ-N-TP04"]) in g


def test_shacl_flags_exactly_the_planted_defect(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    assert summary["conforms"] is False
    assert summary["violations"] == [("CAPA-0008", "Every CAPA must point to at least one investigation.")]


def test_shacl_passes_when_the_defect_is_removed(root, vocab, records):
    clean = [r for r in records if r.record_id != "CAPA-0008"]
    g = build_graph(root / "ontology" / "qms.ttl", vocab, clean, links=[],
                    hierarchy_path=root / "data" / "hierarchy.json")
    conforms, violations = validate_graph(g, root / "shapes" / "qms_shapes.ttl")
    assert conforms and violations == []


def test_slang_name_finds_records_at_both_sites(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    header, rows = summary["results"]["cq1_records_by_equipment_term.rq"]
    sites = {row[header.index("site")] for row in rows}
    kinds = {row[header.index("kind")] for row in rows}
    assert sites == {"Plant North", "Plant East"}
    assert kinds == {"Deviation", "Investigation", "CAPA"}      # found through the graph, not just the tag


def test_repeat_equipment_types_across_sites(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    header, rows = summary["results"]["cq2_repeat_equipment_type_across_sites.rq"]
    assert {row[0] for row in rows} == {"Mixing vessel", "Tablet press", "Autoclave"}


def test_deviations_without_capa(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    header, rows = summary["results"]["cq3_deviations_without_capa.rq"]
    ids = {row[0] for row in rows}
    assert "DEV-0007" in ids and "DEV-0001" not in ids     # DEV-0001 has an investigation and CAPA-0001


def test_capa_is_reached_through_the_chain_not_tagged_directly(root, tmp_path):
    summary = run_pipeline(root / "data", tmp_path)
    g = Graph().parse(str(tmp_path / "graph.ttl"), format="turtle")
    D = Namespace("http://example.org/qms/data/")
    # CAPA text names no equipment, so the tagger gives it no direct link ...
    assert list(g.objects(D["record/CAPA-0001"], QMS.aboutEquipment)) == []
    # ... yet a query on the slang name still finds it, by following the chain from the deviation
    header, rows = summary["results"]["cq1_records_by_equipment_term.rq"]
    assert "CAPA-0001" in {row[header.index("recordId")] for row in rows}
    # investigations do name the equipment in their text, so they carry their own direct tag
    assert (D["record/INV-0001"], QMS.aboutEquipment, D["equipment/EQ-N-TP04"]) in g
