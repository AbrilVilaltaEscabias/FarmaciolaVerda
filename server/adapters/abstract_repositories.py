"""
Interfícies dels repositoris. Cap import de SQLAlchemy: només diuen QUÈ es pot
fer, no COM. La implementació concreta és a sqlalchemy_repositories.py.
"""
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Generic, TypeVar

from server.domain import Category, Ingredient, Recipe, User

K = TypeVar("K")   # tipus de la clau primària (int...)
V = TypeVar("V")   # tipus del model (User, Recipe...)


class AbstractRepository(ABC, Generic[K, V]):
    @abstractmethod
    def add(self, v: V) -> None: ...

    @abstractmethod
    def get(self, id: K) -> V | None: ...

    @abstractmethod
    def get_all(self) -> Iterable[V]: ...

    @abstractmethod
    def delete(self, k: K) -> None: ...

    @abstractmethod
    def update(self, v: V) -> None: ...


class AbstractUserRepository(AbstractRepository[int, User]):
    pass


class AbstractCategoryRepository(AbstractRepository[int, Category]):
    pass


class AbstractIngredientRepository(AbstractRepository[int, Ingredient]):
    pass


class AbstractRecipeRepository(AbstractRepository[int, Recipe]):
    @abstractmethod
    def get_by_name(self, name: str) -> Iterable[Recipe]: ...

    @abstractmethod
    def get_by_category(self, category: str) -> Iterable[Recipe]: ...

    @abstractmethod
    def add_ingredient(self, recipe_id: int, ingredient_id: int, quantity: str,
                       isoptional: bool = False, ischecked: bool = False) -> None: ...

    @abstractmethod
    def get_paginated(self, page: int, page_size: int) -> Iterable[Recipe]: ...
