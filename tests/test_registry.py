import warnings
import pytest

from pyannote.database.registry import OverrideType, _merge_protocols_inplace

def test_override_merging_disjoint():
    protocols1 = {
        ("Task1", "Protocol1"): None,
    }
    protocols2 = {
        ("OtherTask", "Protocol1"): 42,
    }

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # expect no warning
        _merge_protocols_inplace(protocols1, protocols2, OverrideType.WARN_KEEP, "", "")
    assert ("Task1", "Protocol1",) in protocols1
    assert ("OtherTask", "Protocol1",) in protocols1
    assert len(protocols1) == 2



def test_override_merging_identical():
    protocols2 = {
        ("Task1", "Protocol1"): None,
    }   # the "old" protocols dict. KEEP override options will keep these entries.

    # Expect protocols1 to become protocols2 (keep old value)
    protocols1 = {
        ("Task1", "Protocol1"): 42,
    }
    _merge_protocols_inplace(protocols1, protocols2, OverrideType.KEEP, "", "")
    assert ("Task1", "Protocol1") in protocols1
    assert protocols1[("Task1", "Protocol1")] == None
    assert len(protocols1) == 1

    # Expect warning and protocols1 to become protocols2 (keep old value)
    protocols1 = {
        ("Task1", "Protocol1"): 42,
    }
    with pytest.warns(Warning) as w:
        _merge_protocols_inplace(protocols1, protocols2, OverrideType.WARN_KEEP, "", "")
        assert ("Task1", "Protocol1") in protocols1
        assert protocols1[("Task1", "Protocol1")] == None
        assert len(protocols1) == 1
    
    # Expect warning and protocols1 to keep its value (use new value)
    protocols1 = {
        ("Task1", "Protocol1"): 42,
    }
    with pytest.warns(Warning) as w:
        _merge_protocols_inplace(protocols1, protocols2, OverrideType.WARN_OVERRIDE, "", "")
        assert ("Task1", "Protocol1") in protocols1
        assert protocols1[("Task1", "Protocol1")] == 42
        assert len(protocols1) == 1
    

    # expect protocols1 to keep its value (use new value)
    protocols1 = {
        ("Task1", "Protocol1"): 42,
    }
    _merge_protocols_inplace(protocols1, protocols2, OverrideType.OVERRIDE, "", "")
    assert ("Task1", "Protocol1") in protocols1
    assert protocols1[("Task1", "Protocol1")] == 42
    assert len(protocols1) == 1
