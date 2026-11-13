"""Controlled vocabulary: products, equipment, and sites, each with preferred labels and aliases.

The alias index is what lets 'press 4', 'TP-04', and 'Tablet Press TP-04' all point to the same
equipment, which is the terminology problem this demo is about.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


def normalize(text: str) -> str:
    """Lowercase and collapse punctuation so 'TP-04' and 'tp 04' compare equal."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


@dataclass
class Entity:
    id: str
    label: str
    kind: str                      # 'product' or 'equipment'
    aliases: list[str] = field(default_factory=list)
    site: str | None = None        # equipment only
    type: str | None = None        # equipment only, e.g. 'Tablet press'

    @property
    def all_names(self) -> list[str]:
        return [self.label] + list(self.aliases)


@dataclass
class Vocabulary:
    sites: dict[str, str]
    entities: list[Entity]

    def by_id(self, entity_id: str) -> Entity:
        for e in self.entities:
            if e.id == entity_id:
                return e
        raise KeyError(entity_id)

    def alias_index(self) -> dict[str, list[Entity]]:
        """Normalized name -> entities that use it. More than one entity means the name is ambiguous."""
        index: dict[str, list[Entity]] = {}
        for entity in self.entities:
            for name in entity.all_names:
                bucket = index.setdefault(normalize(name), [])
                if entity not in bucket:
                    bucket.append(entity)
        return index


def load_vocabulary(path: Path | str) -> Vocabulary:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entities = [
        Entity(id=p["id"], label=p["label"], kind="product", aliases=p.get("aliases", []))
        for p in data["products"]
    ]
    entities += [
        Entity(id=e["id"], label=e["label"], kind="equipment", aliases=e.get("aliases", []),
               site=e["site"], type=e["type"])
        for e in data["equipment"]
    ]
    sites = {s["id"]: s["label"] for s in data["sites"]}
    return Vocabulary(sites=sites, entities=entities)
