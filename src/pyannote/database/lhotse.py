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

"""Lhotse protocol integration for pyannote.database"""

import warnings
from typing import Dict, Iterator, Optional

from pyannote.core import Annotation, Timeline, Segment
from pyannote.database.protocol import SpeakerDiarizationProtocol


try:
    import lhotse
    LHOTSE_IS_AVAILABLE = True
except ImportError:
    LHOTSE_IS_AVAILABLE = False

try:
    import meeteval.io
    from meeteval.io.seglst import SegLST
    MEETEVAL_IS_AVAILABLE = True
except ImportError:
    MEETEVAL_IS_AVAILABLE = False


def supervision_to_annotation(recording_id: str, supervision_set) -> Annotation:
    """Convert Lhotse SupervisionSet to pyannote.core.Annotation

    Parameters
    ----------
    recording_id : str
        Recording identifier (used as uri in Annotation)
    supervision_set : lhotse.SupervisionSet
        Lhotse supervision set containing speaker labels

    Returns
    -------
    annotation : pyannote.core.Annotation
        Speaker diarization annotation
    """
    annotation = Annotation(uri=recording_id)

    for supervision in supervision_set:
        speaker = supervision.speaker
        if speaker is None:
            speaker = "unknown"

        segment = Segment(supervision.start, supervision.end)
        annotation[segment, speaker] = speaker

    return annotation


def supervision_set_to_timeline(supervision_set) -> Timeline:
    """Convert Lhotse SupervisionSet to pyannote.core.Timeline

    Parameters
    ----------
    supervision_set : lhotse.SupervisionSet
        Lhotse supervision set

    Returns
    -------
    timeline : pyannote.core.Timeline
        Timeline of annotated regions
    """
    timeline = Timeline()

    for supervision in supervision_set:
        segment = Segment(supervision.start, supervision.end)
        timeline.add(segment)

    return timeline


def supervisions_to_seglst(recording_id: str, supervision_set) -> Optional["SegLST"]:
    """Convert Lhotse SupervisionSet to meeteval SegLST

    Parameters
    ----------
    recording_id : str
        Recording identifier (used as session_id in SegLST)
    supervision_set : lhotse.SupervisionSet
        Lhotse supervision set containing transcriptions

    Returns
    -------
    seglst : SegLST or None
        Transcription as SegLST, or None if meeteval is not available
    """
    if not MEETEVAL_IS_AVAILABLE:
        return None

    segments = []
    for idx, supervision in enumerate(supervision_set):
        if supervision.text is None:
            continue

        segment = {
            "session_id": recording_id,
            "speaker": supervision.speaker or "unknown",
            "start": supervision.start,
            "end": supervision.end,
            "words": supervision.text,
            "conf": 1.0,
        }
        segments.append(segment)

    if not segments:
        return SegLST([])

    return SegLST(segments)


class LhotseProtocol(SpeakerDiarizationProtocol):
    """Lhotse protocol for pyannote.database

    This protocol integrates Lhotse datasets into pyannote.database, allowing
    Lhotse recordings and supervisions to be accessed through the standard
    pyannote protocol interface.

    Parameters
    ----------
    recording_set : lhotse.RecordingSet
        Lhotse recording set
    supervision_set : lhotse.SupervisionSet
        Lhotse supervision set for the entire dataset
    subset_split : dict, optional
        Mapping of subset names to recording ids
        Example: {"train": ["recording1", "recording2"],
                  "development": ["recording3"],
                  "test": ["recording4"]}
    audio_dir : str, optional
        Path to audio directory (used for preprocessing with preprocessors)
    preprocessors : dict, optional
        Preprocessors for protocol files
    """

    def __init__(
        self,
        recording_set,
        supervision_set,
        subset_split: Optional[Dict[str, list]] = None,
        audio_dir: Optional[str] = None,
        preprocessors: Optional[Dict] = None,
    ):
        super().__init__(preprocessors=preprocessors)

        self.recording_set = recording_set
        self.supervision_set = supervision_set
        self.subset_split = subset_split or {"train": [], "development": [], "test": []}
        self.audio_dir = audio_dir

    def train_iter(self) -> Iterator[Dict]:
        """Iterate over training files"""
        recording_ids = self.subset_split.get("train", [])

        for recording_id in recording_ids:
            if recording_id not in self.recording_set:
                warnings.warn(f"Recording {recording_id} not found in recording set")
                continue

            recording = self.recording_set[recording_id]
            supervisions = self.supervision_set.filter(lambda s: s.recording_id == recording_id)

            # Convert lazy filter to eager to check if empty
            supervisions_list = supervisions.to_eager() if hasattr(supervisions, 'to_eager') else supervisions

            if len(supervisions_list) == 0:
                warnings.warn(f"No supervisions found for recording {recording_id}")
                continue

            yield {
                "uri": recording_id,
                "annotation": supervision_to_annotation(recording_id, supervisions_list),
                "annotated": supervision_set_to_timeline(supervisions_list),
                "recording": recording,
                "supervisions": supervisions_list,
            }

    def development_iter(self) -> Iterator[Dict]:
        """Iterate over development files"""
        recording_ids = self.subset_split.get("development", [])

        for recording_id in recording_ids:
            if recording_id not in self.recording_set:
                warnings.warn(f"Recording {recording_id} not found in recording set")
                continue

            recording = self.recording_set[recording_id]
            supervisions = self.supervision_set.filter(lambda s: s.recording_id == recording_id)

            # Convert lazy filter to eager to check if empty
            supervisions_list = supervisions.to_eager() if hasattr(supervisions, 'to_eager') else supervisions

            if len(supervisions_list) == 0:
                warnings.warn(f"No supervisions found for recording {recording_id}")
                continue

            yield {
                "uri": recording_id,
                "annotation": supervision_to_annotation(recording_id, supervisions_list),
                "annotated": supervision_set_to_timeline(supervisions_list),
                "recording": recording,
                "supervisions": supervisions_list,
            }

    def test_iter(self) -> Iterator[Dict]:
        """Iterate over test files"""
        recording_ids = self.subset_split.get("test", [])

        for recording_id in recording_ids:
            if recording_id not in self.recording_set:
                warnings.warn(f"Recording {recording_id} not found in recording set")
                continue

            recording = self.recording_set[recording_id]
            supervisions = self.supervision_set.filter(lambda s: s.recording_id == recording_id)

            # Convert lazy filter to eager to check if empty
            supervisions_list = supervisions.to_eager() if hasattr(supervisions, 'to_eager') else supervisions

            yield {
                "uri": recording_id,
                "annotated": supervision_set_to_timeline(supervisions_list),
                "recording": recording,
                "supervisions": supervisions_list,
            }
