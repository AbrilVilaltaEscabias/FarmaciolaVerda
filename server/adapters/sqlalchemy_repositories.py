"""
Implementació dels repositoris amb SQLAlchemy. Aquí (i a orm.py / unit_of_work.py)
és l'únic lloc on es parla de sessions i consultes.
"""
from abc import abstractmethod
from collections.abc import Iterable

from sqlalchemy import inspect, select

from server.domain import Category, Ingredient, ListIngredients, Recipe, User
from .abstract_repositories import (
    AbstractCategoryRepository,
    AbstractIngredientRepository,
    AbstractRecipeRepository,
    AbstractRepository,
    AbstractUserRepository,
)


class SqlAlchemyRepository(AbstractRepository):
    model_class = None     # cada repositori concret indica el seu model

    def __init__(self, session):
        self.session = session

    def add(self, v):
        self._validate(v)
        if v.id is None:
            self.session.add(v)
        else:
            raise ValueError("Not implemented yet!!")

    def get(self, id):
        return self.session.get(self.model_class, id)

    def get_all(self) -> Iterable:
        return self.session.scalars(select(self.model_class)).all()

    def delete(self, k):
        v = self.get(k)
        self.session.delete(v)

    def update(self, v):
        self._validate(v)
        status = inspect(v)
        # persistent (s'ha fet el commit) o detached (s'ha tancat la sessió)
        if status.persistent or status.detached:
            self.session.merge(v)    # copia els atributs de v sobre l'objecte de la sessió

    @abstractmethod
    def _validate(self, v) -> None: ...


class UserRepository(SqlAlchemyRepository, AbstractUserRepository):
    model_class = User

    def _validate(self, user: User) -> None:
        if user.user_name is None:
            raise ValueError("User name attribute is mandatory")
        if user.alias is None:
            user.alias = user.user_name
        if user.email is None:
            raise ValueError("Email attribute is mandatory")
        if user.password is None:
            raise ValueError("Password attribute is mandatory")


class CategoryRepository(SqlAlchemyRepository, AbstractCategoryRepository):
    model_class = Category

    def _validate(self, category: Category) -> None:
        if category.name is None:
            raise ValueError("Name attribute is mandatory")


class IngredientRepository(SqlAlchemyRepository, AbstractIngredientRepository):
    model_class = Ingredient

    def _validate(self, ingredient: Ingredient) -> None:
        if ingredient.common_name is None:
            raise ValueError("Name attribute is mandatory")
        if ingredient.type is None:
            raise ValueError("Type attribute is mandatory")


class RecipeRepository(SqlAlchemyRepository, AbstractRecipeRepository):
    model_class = Recipe

    def _validate(self, recipe: Recipe) -> None:
        if recipe.name is None:
            raise ValueError("Name attribute is mandatory")
        if recipe.step_by_step is None:
            raise ValueError("Step_by_step attribute is mandatory")

    # ··· CONSULTES ESPECÍFIQUES ···

    def get_by_name(self, name: str):
        stmt = select(Recipe).where(Recipe.name == name)
        return self.session.scalars(stmt).all()

    def get_by_category(self, category: str):
        stmt = select(Recipe).where(Recipe.categories.any(Category.name == category))
        return self.session.scalars(stmt).all()

    # ··· OPERACIONS DE DOMINI ···

    def add_ingredient(self, recipe_id: int, ingredient_id: int, quantity: str,
                       isoptional: bool = False, ischecked: bool = False):
        existing = self.session.scalars(
            select(ListIngredients)
            .where(ListIngredients.id_recipe == recipe_id)
            .where(ListIngredients.id_plant == ingredient_id)
        ).first()

        if existing:
            existing.quantity = quantity
        else:
            self.session.add(ListIngredients(
                id_recipe=recipe_id,
                id_plant=ingredient_id,
                quantity=quantity,
                isoptional=isoptional,
                is_checked=ischecked,
            ))

    # ··· PAGINACIÓ ···

    def get_paginated(self, page: int, page_size: int):
        stmt = (
            select(Recipe)
            .order_by(Recipe.name)
            .limit(page_size)
            .offset((page - 1) * page_size)   # salta els registres de les pàgines anteriors
        )
        return self.session.scalars(stmt).all()
