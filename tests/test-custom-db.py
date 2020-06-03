from pyannote.database import  get_protocol

protocol = get_protocol('MyVoxCeleb.SpeakerVerification.VoxCeleb2')

# print('[Loading test set]')
# for i, c_file in enumerate(protocol.test()):
#     print(c_file['uri'])
#     if i >= 10: break

# print(['Loading train set'])
# for i, c_file in enumerate(protocol.train()):
#     print(c_file)
#     if i >= 10: break

print('[tst_try_iter]')
for i, c_trial in enumerate(protocol.tst_try_iter()):
    print(c_trial)
    if i >= 10: break

print('[test_trial]')
for i, c_trial in enumerate(protocol.test_trial()):
    print(c_trial)
    if i >= 10: break

print("[train_trials, shouldn't do anything]")
for i, c_trial in enumerate(protocol.train_trial()):
    pritn(c_trial['file1'])
    if i >= 10: break
