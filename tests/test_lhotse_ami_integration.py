#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2025- pyannoteAI

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Samuele Cornell

"""Integration tests with real AMI data using Lhotse protocol"""

import pytest
from pathlib import Path
from pyannote.core import Annotation, Timeline
from pyannote.database.lhotse import LhotseProtocol


# Path to AMI dataset
AMI_DATA_PATH = Path("/Users/samco/datasets/AMI")


@pytest.fixture(scope="module")
def ami_data_available():
    """Check if AMI data is available"""
    if not AMI_DATA_PATH.exists():
        pytest.skip(f"AMI dataset not found at {AMI_DATA_PATH}")
    return AMI_DATA_PATH


@pytest.fixture
def ami_ihm_lhotse_protocol(ami_data_available):
    """Create LhotseProtocol for AMI IHM (Individual Headset Microphone)"""
    try:
        import lhotse
    except ImportError:
        pytest.skip("lhotse package not installed")

    # Load AMI IHM data using the predefined train/dev/test splits
    # Map from protocol split names to file names
    split_mapping = {"train": "train", "development": "dev", "test": "test"}
    file_splits = ["train", "dev", "test"]
    all_recordings = []
    all_supervisions = []

    for file_split in file_splits:
        rec_file = ami_data_available / f"ami-ihm_recordings_{file_split}.jsonl.gz"
        sup_file = ami_data_available / f"ami-ihm_supervisions_{file_split}.jsonl.gz"

        if rec_file.exists() and sup_file.exists():
            all_recordings.extend(lhotse.load_manifest(str(rec_file)))
            all_supervisions.extend(lhotse.load_manifest(str(sup_file)))

    recordings = lhotse.RecordingSet.from_recordings(all_recordings)
    supervisions = lhotse.SupervisionSet(all_supervisions)

    # Define subset_split using the actual split files
    subset_split = {}
    for protocol_split, file_split in split_mapping.items():
        sup_file = ami_data_available / f"ami-ihm_supervisions_{file_split}.jsonl.gz"
        if sup_file.exists():
            sups = lhotse.load_manifest(str(sup_file))
            subset_split[protocol_split] = sorted(set(sup.recording_id for sup in sups))

    protocol = LhotseProtocol(
        recording_set=recordings,
        supervision_set=supervisions,
        subset_split=subset_split,
    )

    return protocol


@pytest.fixture
def ami_mdm_lhotse_protocol(ami_data_available):
    """Create LhotseProtocol for AMI MDM (Multiple Distant Microphone) with multi-channel support"""
    try:
        import lhotse
    except ImportError:
        raise ImportError("lhotse package not installed")

    # Load AMI MDM data using the predefined train/dev/test splits
    # Map from protocol split names to file names
    split_mapping = {"train": "train", "development": "dev", "test": "test"}
    file_splits = ["train", "dev", "test"]
    all_recordings = []
    all_supervisions = []

    for file_split in file_splits:
        rec_file = ami_data_available / f"ami-mdm_recordings_{file_split}.jsonl.gz"
        sup_file = ami_data_available / f"ami-mdm_supervisions_{file_split}.jsonl.gz"

        if rec_file.exists() and sup_file.exists():
            all_recordings.extend(lhotse.load_manifest(str(rec_file)))
            all_supervisions.extend(lhotse.load_manifest(str(sup_file)))

    supervisions = lhotse.SupervisionSet(all_supervisions)
    recordings = lhotse.RecordingSet.from_recordings(all_recordings)

    # Define subset_split using the actual split files
    subset_split = {}
    for protocol_split, file_split in split_mapping.items():
        sup_file = ami_data_available / f"ami-mdm_supervisions_{file_split}.jsonl.gz"
        if sup_file.exists():
            sups = lhotse.load_manifest(str(sup_file))
            subset_split[protocol_split] = sorted(set(s.recording_id for s in sups))

    protocol = LhotseProtocol(
        recording_set=recordings,
        supervision_set=supervisions,
        subset_split=subset_split,
    )

    return protocol


class TestLhotseAMIIntegration:
    """Integration tests with real AMI data"""

    def test_ami_ihm_train_iteration(self, ami_ihm_lhotse_protocol):
        """Test iterating over AMI IHM training files"""
        files = list(ami_ihm_lhotse_protocol.train())

        assert len(files) > 0, "No training files found"

        # Check first file structure
        file = files[0]
        assert "uri" in file
        assert "annotation" in file
        assert "annotated" in file
        assert "recording" in file
        assert "supervisions" in file

        # Verify annotation is pyannote Annotation
        assert isinstance(file["annotation"], Annotation)
        assert file["annotation"].uri == file["uri"]

        # Verify annotated is pyannote Timeline
        assert isinstance(file["annotated"], Timeline)

    def test_ami_ihm_development_iteration(self, ami_ihm_lhotse_protocol):
        """Test iterating over AMI IHM development files"""
        files = list(ami_ihm_lhotse_protocol.development())

        # May be empty depending on split, but should not fail
        for file in files:
            assert "uri" in file
            assert "annotation" in file
            assert isinstance(file["annotation"], Annotation)

    def test_ami_ihm_test_iteration(self, ami_ihm_lhotse_protocol):
        """Test iterating over AMI IHM test files"""
        files = list(ami_ihm_lhotse_protocol.test())

        # May be empty depending on split, but should not fail
        for file in files:
            assert "uri" in file
            assert "annotation" in file
            # Annotation may be None if there are no supervisions for this file
            if file["annotation"] is not None:
                assert isinstance(file["annotation"], Annotation)

    def test_ami_ihm_supervisions_have_speakers(self, ami_ihm_lhotse_protocol):
        """Test that supervisions contain speaker information"""
        files = list(ami_ihm_lhotse_protocol.train())

        if len(files) > 0:
            file = files[0]
            supervisions = file["supervisions"]
            # IHM supervisions should have speaker field
            for sup in supervisions:
                assert hasattr(sup, "speaker")
                assert sup.speaker is not None

    def test_ami_mdm_train_iteration_multi_channel(self, ami_mdm_lhotse_protocol):
        """Test iterating over AMI MDM training files with multi-channel support"""
        files = list(ami_mdm_lhotse_protocol.train())

        assert len(files) > 0, "No training files found"

        # Check first file structure
        file = files[0]
        assert "uri" in file
        assert "annotation" in file
        assert "annotated" in file
        assert "recording" in file
        assert "supervisions" in file

        # Verify annotation is pyannote Annotation (if available)
        if file["annotation"] is not None:
            assert isinstance(file["annotation"], Annotation)

    def test_ami_mdm_supervisions_multi_channel(self, ami_mdm_lhotse_protocol):
        """Test that MDM supervisions include multi-channel data"""
        files = list(ami_mdm_lhotse_protocol.train())

        if len(files) > 0:
            file = files[0]
            supervisions = file["supervisions"]
            # All supervisions should have channel information (channel is a list in MDM)
            for sup in supervisions:
                assert hasattr(sup, "channel")
                assert isinstance(sup.channel, list)
                assert len(sup.channel) > 0

    def test_ami_ihm_annotation_content(self, ami_ihm_lhotse_protocol):
        """Test that annotations contain actual speaker diarization content"""
        files = list(ami_ihm_lhotse_protocol.train())

        if len(files) > 0:
            file = files[0]
            annotation = file["annotation"]

            # Annotation may be None if there are no supervisions - only test if available
            if annotation is not None:
                # Annotation should have segments
                assert len(annotation) > 0, "Annotation is empty"

                # Each segment should have a speaker label
                for segment, track, label in annotation.itertracks(yield_label=True):
                    assert segment.start < segment.end
                    assert label is not None  # Speaker label should exist

    def test_ami_ihm_annotated_regions(self, ami_ihm_lhotse_protocol):
        """Test that annotated regions (timeline) are correct"""
        files = list(ami_ihm_lhotse_protocol.train())

        if len(files) > 0:
            file = files[0]
            annotated = file["annotated"]

            # Annotated should be a timeline
            assert isinstance(annotated, Timeline)

            # Should have segments
            assert len(annotated) > 0, "Annotated timeline is empty"

            # All segments should have valid time ranges
            for segment in annotated:
                assert segment.start >= 0
                assert segment.start < segment.end


class TestLhotseAMIPreprocessors:
    """Test using preprocessors with real AMI data"""

    def test_ami_ihm_with_audio_path_preprocessor(self, ami_ihm_lhotse_protocol):
        """Test using a preprocessor to add audio paths"""
        # Create protocol with preprocessors
        protocol = LhotseProtocol(
            recording_set=ami_ihm_lhotse_protocol.recording_set,
            supervision_set=ami_ihm_lhotse_protocol.supervision_set,
            subset_split=ami_ihm_lhotse_protocol.subset_split,
            preprocessors={
                # Return audio path from recording
                "audio_path": lambda file: str(file["recording"].sources[0].source)
                if file["recording"].sources
                else None,
            },
        )

        files = list(protocol.train())
        if len(files) > 0:
            file = files[0]
            assert "audio_path" in file
            assert file["audio_path"] is not None

    def test_ami_ihm_with_duration_preprocessor(self, ami_ihm_lhotse_protocol):
        """Test using a preprocessor to add duration"""
        protocol = LhotseProtocol(
            recording_set=ami_ihm_lhotse_protocol.recording_set,
            supervision_set=ami_ihm_lhotse_protocol.supervision_set,
            subset_split=ami_ihm_lhotse_protocol.subset_split,
            preprocessors={
                "duration": lambda file: file["recording"].duration,
            },
        )

        files = list(protocol.train())
        if len(files) > 0:
            file = files[0]
            assert "duration" in file
            assert file["duration"] > 0
