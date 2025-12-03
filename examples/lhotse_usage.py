#!/usr/bin/env python
# encoding: utf-8

"""
Example: Using pyannote-database with Lhotse

This example demonstrates how to use the LhotseProtocol to integrate
Lhotse datasets into pyannote.database.

Usage:
    python lhotse_usage.py /path/to/ami/directory

Requirements:
    pip install lhotse pyannote.database
"""

import sys
from pathlib import Path

from pyannote.database import LhotseProtocol


def example_basic_usage(ami_dir):
    """Basic usage of LhotseProtocol

    This example shows how to create a protocol from Lhotse data
    and iterate over the files.

    Args:
        ami_dir: Path to the AMI directory containing Lhotse JSONL files
    """
    import lhotse

    ami_path = Path(ami_dir)

    # Load train/dev/test recordings and supervisions from the compressed JSONL files
    # Using ami-ihm subset as an example
    # Map from protocol split names to file names
    split_mapping = {"train": "train", "development": "dev", "test": "test"}
    file_splits = ["train", "dev", "test"]

    # Load all recordings (needed to match supervisions)
    all_recordings = []
    all_supervisions = []

    for file_split in file_splits:
        rec_file = ami_path / f"ami-ihm_recordings_{file_split}.jsonl.gz"
        sup_file = ami_path / f"ami-ihm_supervisions_{file_split}.jsonl.gz"

        if rec_file.exists() and sup_file.exists():
            print(f"  Loading {file_split}: {rec_file.name} and {sup_file.name}...")
            all_recordings.extend(lhotse.load_manifest(str(rec_file)))
            all_supervisions.extend(lhotse.load_manifest(str(sup_file)))
        else:
            print(f"  Skipping {file_split}: files not found")

    if not all_recordings:
        raise FileNotFoundError(f"No ami-ihm recordings files found in {ami_dir}")
    if not all_supervisions:
        raise FileNotFoundError(f"No ami-ihm supervisions files found in {ami_dir}")

    recording_set = lhotse.RecordingSet.from_recordings(all_recordings)
    supervision_set = lhotse.SupervisionSet(all_supervisions)
    print(f"  Loaded {len(recording_set)} recordings and {len(supervision_set)} supervisions")

    # Define train/development/test splits by reading the actual split files
    subset_split = {}
    for protocol_split, file_split in split_mapping.items():
        sup_file = ami_path / f"ami-ihm_supervisions_{file_split}.jsonl.gz"
        if sup_file.exists():
            sups = lhotse.load_manifest(str(sup_file))
            subset_split[protocol_split] = sorted(set(sup.recording_id for sup in sups))

    # Create the protocol
    protocol = LhotseProtocol(
        recording_set=recording_set,
        supervision_set=supervision_set,
        subset_split=subset_split,
    )

    # Iterate over training files
    for file in protocol.train():
        print(f"URI: {file['uri']}")
        print(f"Annotation: {file['annotation']}")
        print(f"Annotated regions: {file['annotated']}")
        # file also contains:
        # - file['recording']: Lhotse Recording object
        # - file['supervisions']: Lhotse SupervisionSet


def example_with_preprocessors(ami_dir):
    """Using preprocessors with LhotseProtocol

    Preprocessors allow you to add custom fields to each file
    that are computed on-the-fly.

    Args:
        ami_dir: Path to the AMI directory containing Lhotse JSONL files
    """
    import lhotse
    from pathlib import Path

    ami_path = Path(ami_dir)

    # Load train/dev/test recordings and supervisions from the compressed JSONL files
    # Map from protocol split names to file names
    split_mapping = {"train": "train", "development": "dev", "test": "test"}
    file_splits = ["train", "dev", "test"]

    # Load all recordings and supervisions
    all_recordings = []
    all_supervisions = []

    for file_split in file_splits:
        rec_file = ami_path / f"ami-ihm_recordings_{file_split}.jsonl.gz"
        sup_file = ami_path / f"ami-ihm_supervisions_{file_split}.jsonl.gz"

        if rec_file.exists() and sup_file.exists():
            print(f"  Loading {file_split}: {rec_file.name} and {sup_file.name}...")
            all_recordings.extend(lhotse.load_manifest(str(rec_file)))
            all_supervisions.extend(lhotse.load_manifest(str(sup_file)))

    recording_set = lhotse.RecordingSet.from_recordings(all_recordings)
    supervision_set = lhotse.SupervisionSet(all_supervisions)
    print(f"  Loaded {len(recording_set)} recordings and {len(supervision_set)} supervisions")

    # Define train/development/test splits by reading the actual split files
    subset_split = {}
    for protocol_split, file_split in split_mapping.items():
        sup_file = ami_path / f"ami-ihm_supervisions_{file_split}.jsonl.gz"
        if sup_file.exists():
            sups = lhotse.load_manifest(str(sup_file))
            subset_split[protocol_split] = sorted(set(sup.recording_id for sup in sups))

    # Define preprocessors (only use callable preprocessors with Lhotse data)
    # Note: Template-based preprocessors should reference keys that exist in the file dict
    preprocessors = {
        "duration": lambda file: file["recording"].duration,
        "num_speakers": lambda file: len(set(
            s.speaker for s in file["supervisions"] if s.speaker is not None
        )),
    }

    protocol = LhotseProtocol(
        recording_set=recording_set,
        supervision_set=supervision_set,
        subset_split=subset_split,
        preprocessors=preprocessors,
    )

    # Now each file also has 'duration' and 'num_speakers' keys
    for file in protocol.train():
        print(f"Duration: {file['duration']}")
        print(f"Num speakers: {file['num_speakers']}")


def example_with_registry(ami_dir):
    """Programmatic protocol registration

    You can also register LhotseProtocol instances with the registry
    for use with existing pyannote tools and workflows.

    Args:
        ami_dir: Path to the AMI directory containing Lhotse JSONL files
    """
    import lhotse
    from pathlib import Path
    from pyannote.database import registry, Database

    ami_path = Path(ami_dir)

    # Load train/dev/test recordings and supervisions from the compressed JSONL files
    # Map from protocol split names to file names
    split_mapping = {"train": "train", "development": "dev", "test": "test"}
    file_splits = ["train", "dev", "test"]

    # Load all recordings and supervisions
    all_recordings = []
    all_supervisions = []

    for file_split in file_splits:
        rec_file = ami_path / f"ami-ihm_recordings_{file_split}.jsonl.gz"
        sup_file = ami_path / f"ami-ihm_supervisions_{file_split}.jsonl.gz"

        if rec_file.exists() and sup_file.exists():
            print(f"  Loading {file_split}: {rec_file.name} and {sup_file.name}...")
            all_recordings.extend(lhotse.load_manifest(str(rec_file)))
            all_supervisions.extend(lhotse.load_manifest(str(sup_file)))

    recording_set = lhotse.RecordingSet.from_recordings(all_recordings)
    supervision_set = lhotse.SupervisionSet(all_supervisions)
    print(f"  Loaded {len(recording_set)} recordings and {len(supervision_set)} supervisions")

    # Define train/development/test splits by reading the actual split files
    subset_split = {}
    for protocol_split, file_split in split_mapping.items():
        sup_file = ami_path / f"ami-ihm_supervisions_{file_split}.jsonl.gz"
        if sup_file.exists():
            sups = lhotse.load_manifest(str(sup_file))
            subset_split[protocol_split] = sorted(set(sup.recording_id for sup in sups))

    # Create the protocol
    protocol = LhotseProtocol(
        recording_set=recording_set,
        supervision_set=supervision_set,
        subset_split=subset_split,
    )

    # Create a custom Database class and register protocols
    class LhotseAMIDatabase(Database):
        def __init__(self):
            super().__init__()
            self.register_protocol(
                "SpeakerDiarization",
                "Benchmark",
                lambda preprocessors=None: LhotseProtocol(
                    recording_set=recording_set,
                    supervision_set=supervision_set,
                    subset_split=subset_split,
                    preprocessors=preprocessors,
                ),
            )

    # Register the database
    registry.databases["LhotseAMI"] = LhotseAMIDatabase

    # Now you can access it like any other protocol
    protocol = registry.get_protocol("LhotseAMI.SpeakerDiarization.Benchmark")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lhotse_usage.py /path/to/ami/directory")
        print()
        print("Example:")
        print("  python lhotse_usage.py /Users/samco/datasets/AMI")
        sys.exit(1)

    ami_dir = sys.argv[1]
    ami_path = Path(ami_dir)

    if not ami_path.exists():
        print(f"Error: Directory does not exist: {ami_dir}")
        sys.exit(1)

    print(f"Loading AMI data from: {ami_dir}")
    print()

    print("Example 1: Basic usage")
    print("=" * 50)
    try:
        example_basic_usage(ami_dir)
    except Exception as e:
        print(f"Error: {e}")

    print("\nExample 2: With preprocessors")
    print("=" * 50)
    try:
        example_with_preprocessors(ami_dir)
    except Exception as e:
        print(f"Error: {e}")

    print("\nExample 3: With registry")
    print("=" * 50)
    try:
        example_with_registry(ami_dir)
    except Exception as e:
        print(f"Error: {e}")
