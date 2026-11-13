from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def vocab(root):
    from qmsgraph.vocab import load_vocabulary
    return load_vocabulary(root / "data" / "vocab.json")


@pytest.fixture
def records(root):
    from qmsgraph.graph import load_records
    return load_records(root / "data" / "records.csv")
