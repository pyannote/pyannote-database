from pyannote.database import get_databases
from pyannote.database import get_tasks
from pyannote.database import get_database
from pyannote.database import get_protocol

assert "MyDatabase" in get_databases()

tasks = get_tasks()
assert "Collection" in tasks
assert "Protocol" in tasks
assert "SpeakerDiarization" in tasks
assert "SpeakerVerification" in tasks

database = get_database("MyDatabase")
tasks = database.get_tasks()
assert "Collection" in tasks
assert "Protocol" in tasks
assert "SpeakerDiarization" in tasks
assert "SpeakerVerification" in tasks

assert "MyCollection" in database.get_protocols("Collection")
assert "MyProtocol" in database.get_protocols("Protocol")
assert "MySpeakerDiarization" in database.get_protocols("SpeakerDiarization")
assert "MySpeakerVerification" in database.get_protocols("SpeakerVerification")


collection = get_protocol("MyDatabase.Collection.MyCollection")
protocol = get_protocol("MyDatabase.Protocol.MyProtocol")
speaker_diarization = get_protocol("MyDatabase.SpeakerDiarization.MySpeakerDiarization")
speaker_verification = get_protocol(
    "MyDatabase.SpeakerVerification.MySpeakerVerification"
)


files = list(collection.files())
assert len(files) == 2
files = list(protocol.files())
assert len(files) == 2
files = list(speaker_diarization.files())
assert len(files) == 2
files = list(speaker_verification.files())
assert len(files) == 2
