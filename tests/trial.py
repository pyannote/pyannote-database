from pyannote.database import get_protocol

protocol = get_protocol('MyDatabase.SpeakerVerification.MySpeakerVerification')
for elt in protocol.train_trial():
    print(elt)