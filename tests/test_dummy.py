import pytest

from pyannote.database import registry

def test_dummy():
    assert isinstance(registry.get_databases(), list)
