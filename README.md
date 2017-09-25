# pyannote-database

This package provides a common interface to multimedia databases and associated
experimental protocol.

## Table of contents
- [Installation](#installation)
- [Usage](#usage)
  - [Databases](#databases)
  - [Tasks](#tasks)
  - [Protocols](#protocols)
  - [Preprocessors](#preprocessors)
- [Defining your own database](#defining-your-own-database)
- [Meta-protocols](#meta-protocols)

## Installation

```bash
$ pip install pyannote.database
```

On its own, `pyannote.database` is not very useful.
You should install actual database plugins to really take advantage of it.
For instance, the ETAPE database plugin can be installed like that:

```bash
$ pip install pyannote.db.etape
```

A bunch of `pyannote.database` plugins are already available (search for `pyannote.db` on [pypi](https://pypi.python.org/pypi?%3Aaction=search&term=pyannote.db&submit=search))
However, you might want to add (and contribute) one for your favorite databases.
See [Defining your own database](#defining-your-own-database) for details.


## Usage
([↑up to table of contents](#table-of-contents))

### Databases

Installed database plugins can be discovered using `get_databases`:

```python
>>> from pyannote.database import get_databases
>>> get_databases()
['Etape']
```

Any installed database plugin can then be imported using one of the following:

```python
# programmatically using "get_database"
>>> from pyannote.database import get_database
>>> database = get_database('Etape')
```

```python
# directly using "import"
>>> from pyannote.database import Etape
>>> database = Etape()
```

Databases usually provide high level description when printed.

```
>>> print(database)
ETAPE corpus

Reference
---------
"The ETAPE corpus for the evaluation of speech-based TV content processing in the French language"
Guillaume Gravier, Gilles Adda, Niklas Paulson, Matthieu Carré, Aude Giraudel, Olivier Galibert.
Eighth International Conference on Language Resources and Evaluation, 2012.

Citation
--------
@inproceedings{ETAPE,
  title = {{The ETAPE Corpus for the Evaluation of Speech-based TV Content Processing in the French Language}},
  author = {Gravier, Guillaume and Adda, Gilles and Paulson, Niklas and Carr{'e}, Matthieu and Giraudel, Aude and Galibert, Olivier},
  booktitle = {{LREC - Eighth international conference on Language Resources and Evaluation}},
  address = {Turkey},
  year = {2012},
}

Website
-------
http://www.afcp-parole.org/etape-en.html
```

You can also use `help` to get the list of available methods.

```
>>> help(database)
```

### Tasks
([↑up to table of contents](#table-of-contents))

Some databases (especially multimodal ones) may be used for several tasks.
One can get a list of tasks using `get_tasks` method:

```python
>>> database.get_tasks()
['SpeakerDiarization']
```

One can also get the overall list of tasks, as well as the list of databases
that implement at least one protocol for a specific task.

```python
>>> from pyannote.database import get_tasks
>>> get_tasks()
['SpeakerDiarization']
>>> get_databases(task='SpeakerDiarization')
['Etape']
```

This might come handy in case you want to automatically benchmark a particular
approach on every database for a given task.

### Protocols
([↑up to table of contents](#table-of-contents))

Once you have settled with a task, a database may implement several
experimental protocols for this task. `get_protocols` can be used to get their
list:

```python
>>> database.get_protocols('SpeakerDiarization')
['Full', 'Radio', 'TV']
```

In this example, three speaker diarization protocols are available: one using
the complete set of data, one using only TV data, one using only Radio data.

```python
>>> protocol = database.get_protocol('SpeakerDiarization', 'TV')
```

Protocols usually provide high level description when printed.

```python
>>> print(protocol)
Speaker diarization protocol using TV subset of ETAPE
```

You can also use `help` to get the list of available methods.

```python
>>> help(protocol)
```

A shortcut `get_protocol` function is available if you already know which database, task, and protocol you want to use:

```python
>>> from pyannote.database import get_protocol
>>> protocol = get_protocol('Etape.SpeakerDiarization.TV')
```

#### Speaker diarization protocols
([↑up to table of contents](#table-of-contents))

Speaker diarization protocols implement three methods: `train`, `development` and `test` that provide an iterator over the corresponding subset.

Those methods yield dictionaries (one per file/item) that can be used in the following way:

```python
>>> from pyannote.database import get_annotated
>>> from pyannote.database import get_unique_identifier
>>> for item in protocol.train():
...
...     # get a unique identifier for the current item
...     uri = get_unique_identifier(item)
...
...     # get the reference annotation (who speaks when)
...     # as a pyannote.core.Annotation instance
...     reference = item['annotation']
...
...     # sometimes, only partial annotations are available
...     # get the annotated region as a pyannote.core.Timeline instance
...     annotated = get_annotated(item)
```


### Preprocessors
([↑up to table of contents](#table-of-contents))

You may have noticed that the path to the audio file is not provided.
This is because those files are not provided by the `pyannote.database` packages. You have to acquire them, copy them on your hard drive, and tell `pyannote.database` where to find them.

To do that, create a file `db.yml` that describes how your system is setup:

```bash
$ cat db.yml
Etape: /path/where/your/stored/Etape/database/{uri}.wav
```

`{uri}` is a placeholder telling `pyannote.database` to replace it by `item[uri]` before looking for the current file.


```python
>>> from pyannote.database.util import FileFinder
>>> preprocessors = {'audio': FileFinder(config_yml='db.yml')}
>>> protocol = get_protocol('Etape.SpeakerDiarization.TV', preprocessors=preprocessors)
>>> for item in protocol.train():
...     # now, `item` contains a `wav` key providing the path to the wav file
...     wav = item['audio']
```

`config_yml` parameters defaults to `~/.pyannote/db.yml`, so you can conveniently use this file to provide information about all the available databases, once and for all:

```bash
$ cat ~/.pyannote/db.yml
Etape: /path/where/you/stored/Etape/database/{uri}.wav
REPERE:
  - /path/where/you/store/REPERE/database/phase1/{uri}.wav
  - /path/where/you/store/REPERE/database/phase2/{uri}.wav
```

```python
>>> preprocessors = {'audio': FileFinder()}
```

More generally, preprocessors can be used to augment/modify the yielded dictionaries on the fly:

```python
>>> # function that takes a protocol item as input and returns whatever you want/need
>>> def my_preprocessor_func(item):
...     return len(item['uri'])
>>> preprocessors = {'uri_length': my_preprocessor_func}
>>> protocol = get_protocol('Etape.SpeakerDiarization.TV', preprocessors=preprocessors)
>>> for item in protocol.train():
...     # a new key 'uri_length' has been added to the current dictionary
...     assert item['uri_length'] == len(item['uri'])
```

## Defining your own database
([↑up to table of contents](#table-of-contents))

See [`http://github.com/pyannote/pyannote-db-template`](http://github.com/pyannote/pyannote-db-template).

## Meta-protocols
([↑up to table of contents](#table-of-contents))

`pyannote.database` provides a way to combine several protocols (possibly
from different databases) into one.

This is achieved by defining those "meta-protocols" into `~/.pyannote/meta.yml`.

```yaml
# ~/.pyannote/meta.yml
MyMetaProtocol:
  task: SpeakerDiarization
  subset:
    train:
      Etape.SpeakerDiarization.TV:
        subset: [train]
      REPERE.SpeakerDiarization.Phase1:
        subset: [train, development]
      REPERE.SpeakerDiarization.Phase2:
        subset: [train, development]
    development:
      Etape.SpeakerDiarization.TV:
        subset: [development]
    test:
      Etape.SpeakerDiarization.TV:
        subset: [test]
```

This defines a new speaker diarization protocol called `MyMetaProtocol` that is
very similar to the existing `Etape.SpeakerDiarization.TV` protocol except its
training set is augmented with (training and development) data from the
`REPERE` corpus. Obviously, both `ETAPE` and `REPERE` packages need to be
installed first:

```bash
$ pip install pyannote.db.etape
$ pip install pyannote.db.repere
```

Then, this new "meta-protocol" can be used like any other protocol of the
(fake) `X` database:

```python
>>> from pyannote.database import get_protocol
>>> protocol = get_protocol('X.SpeakerDiarization.MyMetaProtocol')
>>> for current_file in protocol.train():
...     pass
```
