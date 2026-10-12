
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Generic, TypeVar, get_args

from sqlalchemy import inspect, select

K = TypeVar("K")
V = TypeVar("V")


class AbstractRepository(ABC, Generic[K, V]):

    def __init__(self, session):
        self.session = session
        self.model_class = get_args(
            self.__class__.__orig_bases__[0]
        )[1]

    def add(self, v: V) -> None:
        self._validate(v)

        if v.id is None:
            self.session.add(v)
        else:
            raise ValueError("Not implemented yet!")

    def get(self, id: K) -> V | None:
        return self.session.get(self.model_class, id)

    def get_all(self) -> Iterable[V]:
        return self.session.scalars(
            select(self.model_class)
        ).all()

    def delete(self, k: K) -> None:
        v = self.get(k)

        if v is not None:
            self.session.delete(v)

    def update(self, v: V) -> None:
        self._validate(v)
        status = inspect(v)

        if status.persistent or status.detached:
            self.session.merge(v)

    @abstractmethod
    def _validate(self, v: V) -> None:
        ...