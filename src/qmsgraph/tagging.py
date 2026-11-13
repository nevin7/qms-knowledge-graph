"""Tag suggestions: find mentions of products and equipment in free text.

Two taggers share one output type (Suggestion):

* RuleBasedTagger: exact alias matches plus fuzzy matches for typos. Deterministic and fully tested.
* ClaudeTagger: optional. Asks an LLM for mentions and maps them to vocabulary IDs. Its parsing is
  tested with a stub client, but it has NOT been run against the live API in this repository.

Suggestions are only suggestions. The review step decides what enters the graph.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .vocab import Entity, Vocabulary, normalize


@dataclass
class Suggestion:
    record_id: str
    entity_id: str
    kind: str
    mention: str
    confidence: float
    method: str          # 'exact', 'fuzzy', or 'llm'
    note: str = ""


class RuleBasedTagger:
    """Exact and fuzzy alias matching, using the record's site to resolve ambiguous equipment names."""

    FUZZY_MIN_RATIO = 0.85
    FUZZY_MIN_CHARS = 5
    MAX_NGRAM = 5

    def __init__(self, vocab: Vocabulary):
        self.vocab = vocab
        self.index = vocab.alias_index()
        self.by_words: dict[int, list[str]] = {}
        for name in self.index:
            self.by_words.setdefault(len(name.split()), []).append(name)

    def suggest(self, record_id: str, site_id: str, text: str) -> list[Suggestion]:
        tokens = normalize(text).split()
        best: dict[str, Suggestion] = {}

        def keep(s: Suggestion) -> None:
            current = best.get(s.entity_id)
            if current is None or s.confidence > current.confidence:
                best[s.entity_id] = s

        for n in range(1, self.MAX_NGRAM + 1):
            for i in range(len(tokens) - n + 1):
                gram = " ".join(tokens[i:i + n])
                if gram in self.index:
                    for s in self._exact(record_id, site_id, gram, self.index[gram]):
                        keep(s)
                elif n <= 4 and len(gram) >= self.FUZZY_MIN_CHARS:
                    for s in self._fuzzy(record_id, site_id, gram, n):
                        keep(s)
        return sorted(best.values(), key=lambda s: (-s.confidence, s.entity_id))

    # -- exact -----------------------------------------------------------
    def _exact(self, record_id, site_id, gram, entities):
        out = []
        ambiguous = len(entities) > 1
        for e in entities:
            if e.kind == "product":
                out.append(Suggestion(record_id, e.id, e.kind, gram, 0.95, "exact", "unique name match"))
            elif e.site == site_id:
                note = "name is shared across sites; resolved by the record's site" if ambiguous else "unique name match"
                out.append(Suggestion(record_id, e.id, e.kind, gram, 0.95 if not ambiguous else 0.92, "exact", note))
            elif not ambiguous:
                out.append(Suggestion(record_id, e.id, e.kind, gram, 0.70, "exact",
                                      "equipment is at a different site than the record; confirm"))
            else:
                out.append(Suggestion(record_id, e.id, e.kind, gram, 0.45, "exact",
                                      "name is shared across sites and this one is at another site"))
        return out

    # -- fuzzy -----------------------------------------------------------
    def _fuzzy(self, record_id, site_id, gram, n):
        out = []
        for name in self.by_words.get(n, []):
            ratio = SequenceMatcher(None, gram, name).ratio()
            if ratio < self.FUZZY_MIN_RATIO:
                continue
            for e in self.index[name]:
                if e.kind == "equipment" and e.site != site_id and len(self.index[name]) > 1:
                    continue
                confidence = min(0.89, round(ratio * 0.95, 2))
                out.append(Suggestion(record_id, e.id, e.kind, gram, confidence, "fuzzy",
                                      f"close spelling to '{name}' (similarity {ratio:.2f})"))
        return out


class ClaudeTagger:
    """Optional LLM tagger. Never auto-accepted: its suggestions always go to review.

    `client` is an Anthropic client (anthropic.Anthropic()). Not exercised against the live API here.
    """

    CONFIDENCE = 0.70

    def __init__(self, client, vocab: Vocabulary, model: str = "claude-haiku-4-5-20251001"):
        self.client = client
        self.vocab = vocab
        self.model = model

    def prompt(self, text: str) -> str:
        lines = [f"{e.id}: {e.label} (also: {', '.join(e.aliases)})" for e in self.vocab.entities]
        return (
            "Find mentions of products and equipment in the quality record below. "
            "Match each mention to exactly one ID from the vocabulary, or skip it if unsure. "
            "Reply with only a JSON list of objects with keys 'mention' and 'entity_id'.\n\n"
            "Vocabulary:\n" + "\n".join(lines) + "\n\nRecord:\n" + text
        )

    def suggest(self, record_id: str, site_id: str, text: str) -> list[Suggestion]:
        response = self.client.messages.create(
            model=self.model, max_tokens=500,
            messages=[{"role": "user", "content": self.prompt(text)}],
        )
        return self.parse(record_id, "".join(getattr(b, "text", "") for b in response.content))

    def parse(self, record_id: str, raw: str) -> list[Suggestion]:
        match = re.search(r"\[.*\]", raw, flags=re.S)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        known = {e.id: e for e in self.vocab.entities}
        out = []
        for item in items:
            entity = known.get(item.get("entity_id")) if isinstance(item, dict) else None
            if entity is None:
                continue   # ignore IDs that are not in the controlled vocabulary
            out.append(Suggestion(record_id, entity.id, entity.kind, str(item.get("mention", "")),
                                  self.CONFIDENCE, "llm", "suggested by an LLM; needs human review"))
        return out
