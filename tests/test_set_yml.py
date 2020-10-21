import os

from pyannote.database import set_database_yml, get_protocol
from pyannote.database.config import DATABASE_YML

def test_set_yml():
    set_database_yml("./tests/data/alternative_database.yml")
    get_protocol('MyDatabase.Protocol.MyProtocol')

