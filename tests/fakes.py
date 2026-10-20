"""
Dobles de prova: un Unit of Work i uns repositoris en memòria.

Imiten el comportament que els serveis necessiten del real:
  * `add` no assigna l'id fins que es fa `session.flush()`.
  * En sortir del `with`: commit si tot va bé, rollback si hi ha excepció.
  * El rollback desfà TOTS els canvis de la petició (inclosos els fets en
    objectes ja existents, com un `setattr` d'un update).
"""
import copy

from server.service_layer.unit_of_work import AbstractUnitOfWork

TABLES = ("recipes", "users", "categories", "ingredients")


class FakeDatabase:
    """Emmagatzematge compartit entre UoW (com ho seria una BD real)."""

    def __init__(self):
        self.tables = {name: {} for name in TABLES}
        self.next_id = {name: 1 for name in TABLES}

    def snapshot(self):
        return copy.deepcopy((self.tables, self.next_id))

    def restore(self, snap):
        self.tables, self.next_id = snap


class FakeRepository:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._pending = []
        self.added = []            # per poder inspeccionar què s'ha afegit

    @property
    def _rows(self):
        return self._db.tables[self._table]

    def add(self, v):
        self._pending.append(v)
        self.added.append(v)

    def flush(self):
        for v in self._pending:
            v.id = self._db.next_id[self._table]
            self._db.next_id[self._table] += 1
            self._rows[v.id] = v
        self._pending = []

    def get(self, id):
        return self._rows.get(id)

    def get_all(self):
        return list(self._rows.values())

    def delete(self, k):
        del self._rows[k]

    def update(self, v):  # pragma: no cover - els serveis no el fan servir
        self._rows[v.id] = v


class FakeRecipeRepository(FakeRepository):
    def get_by_name(self, name):
        return [r for r in self.get_all() if r.name == name]

    def get_by_category(self, category):
        return [r for r in self.get_all()
                if any(c.name == category for c in r.categories)]

    def get_paginated(self, page, page_size):
        ordered = sorted(self.get_all(), key=lambda r: r.name)
        start = (page - 1) * page_size
        return ordered[start:start + page_size]

    def add_ingredient(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


class FakeSession:
    def __init__(self, repos):
        self._repos = repos
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1
        for repo in self._repos:
            repo.flush()


class FakeUnitOfWork(AbstractUnitOfWork):
    def __init__(self, db):
        self.db = db
        self.recipes = FakeRecipeRepository(db, "recipes")
        self.users = FakeRepository(db, "users")
        self.categories = FakeRepository(db, "categories")
        self.ingredients = FakeRepository(db, "ingredients")
        self.session = FakeSession(
            [self.recipes, self.users, self.categories, self.ingredients]
        )
        self.committed = False
        self.rolled_back = False
        self._snapshot = None

    def __enter__(self):
        self._snapshot = self.db.snapshot()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        return False               # mai empassa l'excepció

    def flush(self):
        self.session.flush()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True
        self.db.restore(self._snapshot)
