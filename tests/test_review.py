import pytest

from qmsgraph.review import apply_decisions, read_decisions, triage
from qmsgraph.tagging import Suggestion


def s(entity, conf, method="exact"):
    return Suggestion("R1", entity, "equipment", "x", conf, method)


def test_triage_thresholds():
    accepted, queue, discarded = triage([s("A", 0.95), s("B", 0.7), s("C", 0.4)])
    assert [x.entity_id for x in accepted] == ["A"]
    assert [x.entity_id for x in queue] == ["B"]
    assert [x.entity_id for x in discarded] == ["C"]


def test_llm_suggestions_are_never_auto_accepted():
    accepted, queue, _ = triage([s("A", 0.99, method="llm")])
    assert accepted == [] and len(queue) == 1


def test_decisions_split_the_queue():
    queue = [s("A", 0.7), s("B", 0.7), s("C", 0.7)]
    decisions = {("R1", "A"): "accept", ("R1", "B"): "reject"}
    accepted, rejected, pending = apply_decisions(queue, decisions)
    assert [x.entity_id for x in accepted] == ["A"]
    assert [x.entity_id for x in rejected] == ["B"]
    assert [x.entity_id for x in pending] == ["C"]


def test_bad_decision_value_is_rejected(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("record_id,entity_id,decision,reviewer_note\nR1,A,maybe,\n")
    with pytest.raises(ValueError):
        read_decisions(path)
