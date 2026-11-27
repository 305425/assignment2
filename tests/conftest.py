import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.build_dataset import build_fact  # noqa: E402
from analysis.load import load_source  # noqa: E402


@pytest.fixture(scope="session")
def source():
    return load_source()


@pytest.fixture(scope="session")
def fact(source):
    return build_fact(source)
