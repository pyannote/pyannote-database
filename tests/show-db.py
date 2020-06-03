# Will show all the databeses and their methods

from pyannote.database import get_databases, get_database, get_protocol
for db_name in get_databases():
	db = get_database(db_name)
	tasks_names = db.get_tasks()
	for task in tasks_names:
		protocols = db.get_protocols(task=task)
		for protocol_name in protocols:
			tmp = '{}.{}.{}'.format(db_name, task, protocol_name)
			protocol = get_protocol(tmp)
			print('#'*10)
			print(tmp)
			print([i for i in dir(protocol) if i in ['dev_iter', 'dev_try_iter', 'development', 'development_trial', 'test', 'test_trial', 'train', 'train_trial', 'trn_iter', 'trn_try_iter', 'tst_iter', 'tst_try_iter', 'xxx_try_iter', 'xxx_iter']])
