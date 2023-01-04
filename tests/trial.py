from pyannote.database import registry

protocol = registry.get_protocol('MyDatabase.SpeakerVerification.MySpeakerVerification')
for elt in protocol.train_trial():
    print(elt)
    print(elt['file1']['try_with'])
    file1_annotation = elt['file1']['annotation']
    print('annotation : ', file1_annotation)
    file1_annotated  = elt['file1']['annotated']
    print('annotated : ', file1_annotated)