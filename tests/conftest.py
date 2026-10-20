"""
Configuració compartida dels tests.

IMPORTANT: aquest bloc s'ha d'executar abans que qualsevol `import server...`.
`server/db.py` crea l'engine en importar-se, i `.env` apunta a una BD real.
Forcem un entorn de test amb SQLite en memòria (no es connecta mai en crear
l'engine) perquè els tests no toquin mai la base de dades real.
"""
import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DB_URL_TEST"] = "sqlite://"

import pytest  # noqa: E402

from common import protocol  # noqa: E402
from server import router  # noqa: E402
from tests.fakes import FakeDatabase, FakeUnitOfWork  # noqa: E402


@pytest.fixture
def db():
    """Una 'base de dades' en memòria buida."""
    return FakeDatabase()


@pytest.fixture
def uow(db):
    """Un Unit of Work fals, per fer servir directament amb els serveis."""
    return FakeUnitOfWork(db)


@pytest.fixture
def wired_router(monkeypatch, db):
    """
    Router connectat a la BD falsa: cada petició rep un UoW nou (com en
    producció) però tots comparteixen les mateixes dades.
    """
    monkeypatch.setattr(router, "_new_uow", lambda: FakeUnitOfWork(db))
    return router


@pytest.fixture
def send(wired_router):
    """send(command, data) -> resposta ja interpretada (dict)."""
    def _send(command, data=None):
        raw = wired_router.handle(protocol.build_request(command, data))
        return protocol.parse_message(raw)
    return _send


@pytest.fixture
def send_raw(wired_router):
    """send_raw(bytes) -> resposta interpretada. Per a línies mal formades."""
    def _send(line):
        return protocol.parse_message(wired_router.handle(line))
    return _send
