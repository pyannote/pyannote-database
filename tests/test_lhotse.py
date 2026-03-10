#!/usr/bin/env python
# encoding: utf-8

"""Test Lhotse protocol integration"""

import pytest
from unittest.mock import MagicMock, patch
from pyannote.core import Annotation, Timeline, Segment
from pyannote.database.lhotse import (
    LhotseProtocol,
    supervision_to_annotation,
    supervision_set_to_timeline,
)


@pytest.fixture
def mock_recording_set():
    """Create a mock Lhotse RecordingSet"""
    recording_set = MagicMock()
    recording_set.__contains__ = lambda self, key: key in ["rec1", "rec2", "rec3"]
    recording_set.__getitem__ = lambda self, key: MagicMock(id=key)
    return recording_set


@pytest.fixture
def mock_supervision_set():
    """Create a mock Lhotse SupervisionSet"""
    supervision_set = MagicMock()

    # Mock supervisions for rec1
    sup1_1 = MagicMock(
        recording_id="rec1",
        speaker="spk1",
        start=0.0,
        end=5.0,
        text="hello world",
    )
    sup1_2 = MagicMock(
        recording_id="rec1",
        speaker="spk2",
        start=5.0,
        end=10.0,
        text="goodbye",
    )

    # Mock supervisions for rec2
    sup2_1 = MagicMock(
        recording_id="rec2",
        speaker="spk1",
        start=0.0,
        end=3.0,
        text="test",
    )

    # Mock supervisions for rec3
    sup3_1 = MagicMock(
        recording_id="rec3",
        speaker="spk3",
        start=0.0,
        end=2.0,
        text="audio",
    )

    def filter_by_recording(filter_fn):
        """Mock filter function that actually filters by recording_id"""
        supervisions_by_recording = {
            "rec1": [sup1_1, sup1_2],
            "rec2": [sup2_1],
            "rec3": [sup3_1],
        }

        # Apply the filter function to determine which supervisions to return
        filtered = []
        for rec_id, supervisions in supervisions_by_recording.items():
            for sup in supervisions:
                if filter_fn(sup):
                    filtered.append(sup)

        mock = MagicMock()
        mock.__iter__ = lambda self: iter(filtered)
        mock.__len__ = lambda self: len(filtered)
        mock.to_eager = lambda: mock  # to_eager() returns self for this mock
        return mock

    supervision_set.filter = filter_by_recording
    supervision_set.__iter__ = lambda self: iter([sup1_1, sup1_2, sup2_1, sup3_1])
    supervision_set.__len__ = lambda self: 4

    return supervision_set


class TestSupervisionConversion:
    """Test conversion functions"""

    def test_supervision_to_annotation(self, mock_supervision_set):
        """Test converting Lhotse SupervisionSet to pyannote Annotation"""
        supervisions = list(mock_supervision_set)[:2]
        supervision_set = MagicMock()
        supervision_set.__iter__ = lambda self: iter(supervisions)

        annotation = supervision_to_annotation("rec1", supervision_set)

        assert isinstance(annotation, Annotation)
        assert annotation.uri == "rec1"
        assert len(annotation) > 0

    def test_supervision_set_to_timeline(self, mock_supervision_set):
        """Test converting Lhotse SupervisionSet to pyannote Timeline"""
        supervisions = list(mock_supervision_set)[:2]
        supervision_set = MagicMock()
        supervision_set.__iter__ = lambda self: iter(supervisions)

        timeline = supervision_set_to_timeline(supervision_set)

        assert isinstance(timeline, Timeline)
        assert len(timeline) == 2


class TestLhotseProtocol:
    """Test LhotseProtocol"""

    def test_protocol_initialization(self, mock_recording_set, mock_supervision_set):
        """Test protocol initialization"""
        subset_split = {
            "train": ["rec1"],
            "development": ["rec2"],
            "test": ["rec3"],
        }

        protocol = LhotseProtocol(
            recording_set=mock_recording_set,
            supervision_set=mock_supervision_set,
            subset_split=subset_split,
        )

        assert protocol.recording_set is mock_recording_set
        assert protocol.supervision_set is mock_supervision_set
        assert protocol.subset_split == subset_split

    def test_train_iter(self, mock_recording_set, mock_supervision_set):
        """Test train_iter method"""
        subset_split = {
            "train": ["rec1"],
            "development": [],
            "test": [],
        }

        protocol = LhotseProtocol(
            recording_set=mock_recording_set,
            supervision_set=mock_supervision_set,
            subset_split=subset_split,
        )

        files = list(protocol.train_iter())
        assert len(files) == 1
        assert files[0]["uri"] == "rec1"
        assert "annotation" in files[0]
        assert "annotated" in files[0]
        # Verify supervisions are correctly filtered for rec1
        assert len(files[0]["supervisions"]) == 2

    def test_development_iter(self, mock_recording_set, mock_supervision_set):
        """Test development_iter method"""
        subset_split = {
            "train": [],
            "development": ["rec2"],
            "test": [],
        }

        protocol = LhotseProtocol(
            recording_set=mock_recording_set,
            supervision_set=mock_supervision_set,
            subset_split=subset_split,
        )

        files = list(protocol.development_iter())
        assert len(files) == 1
        assert files[0]["uri"] == "rec2"
        # Verify supervisions are correctly filtered for rec2
        assert len(files[0]["supervisions"]) == 1

    def test_test_iter(self, mock_recording_set, mock_supervision_set):
        """Test test_iter method"""
        subset_split = {
            "train": [],
            "development": [],
            "test": ["rec3"],
        }

        protocol = LhotseProtocol(
            recording_set=mock_recording_set,
            supervision_set=mock_supervision_set,
            subset_split=subset_split,
        )

        files = list(protocol.test_iter())
        assert len(files) == 1
        assert files[0]["uri"] == "rec3"
        # Verify supervisions are correctly filtered for rec3
        assert len(files[0]["supervisions"]) == 1

    def test_public_methods(self, mock_recording_set, mock_supervision_set):
        """Test public protocol methods (train, development, test)"""
        subset_split = {
            "train": ["rec1"],
            "development": ["rec2"],
            "test": ["rec3"],
        }

        protocol = LhotseProtocol(
            recording_set=mock_recording_set,
            supervision_set=mock_supervision_set,
            subset_split=subset_split,
        )

        # Test that public methods return iterators
        train_files = list(protocol.train())
        assert len(train_files) == 1

        dev_files = list(protocol.development())
        assert len(dev_files) == 1

        test_files = list(protocol.test())
        assert len(test_files) == 1


class TestLhotseProtocolEdgeCases:
    """Test edge cases"""

    def test_missing_recording(self, mock_supervision_set):
        """Test handling of missing recordings"""
        recording_set = MagicMock()
        recording_set.__contains__ = lambda self, key: False

        subset_split = {
            "train": ["nonexistent"],
            "development": [],
            "test": [],
        }

        protocol = LhotseProtocol(
            recording_set=recording_set,
            supervision_set=mock_supervision_set,
            subset_split=subset_split,
        )

        # Should emit warning and skip
        with pytest.warns(UserWarning, match="not found in recording set"):
            files = list(protocol.train_iter())
        assert len(files) == 0

    def test_empty_subset_split(self, mock_recording_set, mock_supervision_set):
        """Test with empty subset split"""
        protocol = LhotseProtocol(
            recording_set=mock_recording_set,
            supervision_set=mock_supervision_set,
            subset_split={},
        )

        assert list(protocol.train_iter()) == []
        assert list(protocol.development_iter()) == []
        assert list(protocol.test_iter()) == []
