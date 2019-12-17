import pytest

from pyannote.database import get_databases

def test_dummy():
    assert isinstance(get_databases(), list)
