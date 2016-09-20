# pyannote-database

This package provides a common interface to multimedia databases and associated
experimental protocol.


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

## Usage

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

```python
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

Among other things, a protocol usually implements `train`, `dev` and `test`.

```python
>>> help(protocol.train)
Help on method train in module pyannote.database.protocol.speaker_diarization:

train(self) method of Etape.TV instance
    Iterate over the training set

    * uri: str
      uniform (or unique) resource identifier
    * annotated: pyannote.core.Timeline
      parts of the resource that were manually annotated
    * annotation: pyannote.core.Annotation
      actual annotations

    Usage
    -----
    >>> for item in protocol.train():
    ...     uri = item['uri']
    ...     annotated = item['annotated']
    ...     annotation = item['annotation']
```
