### Version 1.5.5 (2018-11-30)

  - fix: fix Collection.files when progress=True

### Version 1.5.4 (2018-11-14)

  - fix: skip files with no "uri" entry in FileFinder.protocol_file_iter

### Version 1.5.3 (2018-11-08)

  - fix: fix broken SpeakerVerificationProtocol

### Version 1.5.1 (2018-10-16)

  - fix: fix support for string preprocessors

### Version 1.5 (2018-09-25)

  - BREAKING: simplify SpeakerVerificationProtocol with {subset}_trial methods

### Version 1.4 (2018-07-13)

  - feat: add raw collection protocol

### Version 1.3.2 (2018-05-16)

  - fix: fix regression introduced in 1.3.1

### Version 1.3.1 (2018-05-11)

  - fix: fix bug in `FileFinder.protocol_file_iter` with empty iterators

### Version 1.3 (2018-02-04)

  - feat: add `extra_keys` parameter to `{protocol | current}_file_iter`

### Version 1.2.1 (2018-02-03)

  - setup: drop support for Python 2
  - feat: add `protocol_file_iter` and `current_file_iter` to FileFinder
  - feat: add `get_label_identifier` utility function
  - fix: fix "get_unique_identifier" when "database" or "channel" is None

### Version 1.1 (2017-10-13)

  - feat: add speaker identification protocol
  - feat: add speaker verification protocols
  - feat: add support for list of uris in FileFinder

### Version 1.0 (2017-10-02)

  - feat: add support for "meta" protocols
  - feat: add speaker spotting protocol
  - setup: switch to pyannote.core 1.1

### Version 0.12 (2017-06-28)

  - feat: add utility functions at package root
  - doc: improve documentation
  - doc: add link to pyannote-db-template repository

### Version 0.11.2 (2017-03-15)

  - fix: fix a bug with string template preprocessors
  - doc: improve documentation

### Version 0.11.1 (2017-01_16)

  - feat: add 'get_protocol' helper function

### Version 0.11 (2017-01-11)

  - feat: add support for validation on training set to speaker recognition protocols
  - feat: add 'get_annotated' helper function

### Version 0.10.2 (2017-01-04)

  - fix: fix bug in FileFinder

### Version 0.10.1 (2016-12-17)

  - improve: change signature of preprocessor.__call__

### Version 0.9 (2016-12-14)

  - feat: add "get_unique_identifier" utility function

### Version 0.8.1 (2016-12-12)

  - fix: fix progress bar support

### Version 0.8 (2016-12-06)

  - feat: add progress bar support

### Version 0.7.1 (2016-12-03)

  - fix: add 'yield_name' parameter to speaker recognition generators

### Version 0.7 (2016-12-02)

  - feat: add speaker recognition protocol

### Version 0.6.1 (2016-12-02)

  - feat: add FileFinder utility class
  - fix: fix SpeakerDiarizationProtocol.stats()

### Version 0.5 (2016-12-01)

  - BREAKING: replace 'medium_template' by (more generic) 'preprocessors'

### Version 0.4.1 (2016-11-17)

  - fix: rename 'speakers' to 'labels' in statistics dictionary

### Version 0.4 (2016-10-27)

  - feat: add a method providing global statistics about a subset

### Version 0.3 (2016-09-22)

  - feat: add support for multiple media

### Version 0.2 (2016-09-21)

  - feat: add support for 'medium_template' attribute

### Version 0.1 (2016-09-20)

  - first public version
