import json

from qmsgraph.tagging import ClaudeTagger, RuleBasedTagger
from qmsgraph.vocab import normalize


def by_entity(suggestions):
    return {s.entity_id: s for s in suggestions}


def test_normalize_makes_punctuation_irrelevant():
    assert normalize("TP-04") == normalize("tp 04") == "tp 04"


def test_exact_alias_match_for_product(vocab):
    tagger = RuleBasedTagger(vocab)
    found = by_entity(tagger.suggest("R1", "SITE-N", "Weight drift for CST-20 today"))
    assert found["PRD-001"].confidence >= 0.9 and found["PRD-001"].method == "exact"


def test_shared_name_is_resolved_by_site(vocab):
    tagger = RuleBasedTagger(vocab)
    north = by_entity(tagger.suggest("R1", "SITE-N", "Problem on press 4"))
    east = by_entity(tagger.suggest("R2", "SITE-E", "Problem on press 4"))
    assert north["EQ-N-TP04"].confidence >= 0.9
    assert east["EQ-E-TP04"].confidence >= 0.9
    # the other site's press shares the name but is not suggested at a usable confidence
    assert "EQ-E-TP04" not in {k for k, v in north.items() if v.confidence >= 0.5}


def test_typo_gets_a_fuzzy_match_that_needs_review(vocab):
    tagger = RuleBasedTagger(vocab)
    found = by_entity(tagger.suggest("R1", "SITE-N", "Issue on tablet pres 4 overnight"))
    s = found["EQ-N-TP04"]
    assert s.method == "fuzzy" and 0.5 <= s.confidence < 0.9


def test_equipment_at_another_site_needs_review(vocab):
    tagger = RuleBasedTagger(vocab)
    found = by_entity(tagger.suggest("R1", "SITE-E", "Seen earlier on coat pan 2"))
    assert found["EQ-N-CP02"].confidence == 0.70


def test_unrelated_text_produces_nothing(vocab):
    assert RuleBasedTagger(vocab).suggest("R1", "SITE-N", "Gloves were out of stock in the gowning room") == []


class StubClient:
    """Stands in for the Anthropic client so the parser can be tested without the network."""
    def __init__(self, text):
        self.messages = self
        self._text = text

    def create(self, **kwargs):
        class Block:  # mimics a text content block
            text = self._text
        class Response:
            content = [Block()]
        return Response()


def test_llm_tagger_parses_json_and_ignores_unknown_ids(vocab):
    reply = 'Here you go: ' + json.dumps([
        {"mention": "press 4", "entity_id": "EQ-N-TP04"},
        {"mention": "mystery machine", "entity_id": "EQ-NOT-REAL"},
    ])
    tagger = ClaudeTagger(StubClient(reply), vocab)
    out = tagger.suggest("R1", "SITE-N", "text")
    assert [s.entity_id for s in out] == ["EQ-N-TP04"]
    assert out[0].method == "llm"


def test_llm_tagger_survives_bad_output(vocab):
    assert ClaudeTagger(StubClient("sorry, no JSON here"), vocab).suggest("R1", "SITE-N", "text") == []
