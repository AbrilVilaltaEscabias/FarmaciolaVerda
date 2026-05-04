from sqlalchemy.orm import Session
from .model import (
    User,
    Recipe,
    Category,
    Ingredient,
    recipe_category_table,
    ListIngredients

)
from typing import Generic, TypeVar
from sqlalchemy import select, inspect
from collections.abc import Iterable
from abc import ABC, abstractmethod
from typing import get_args

K = TypeVar("K") # Tipus de la clau primària (str, int...)
V = TypeVar("V") # Tipus del model (User, Recipe...)

class AbstractRepository(ABC, Generic[K, V]):
    def __init__(self, session):
        self.session = session
        # Obté la classe del model (User, Recipe...) a partir del tipus genèric V
        # que s'ha definit a la classe filla (ex: AbstractRepository[str, User]).
        self.model_class = get_args(self.__class__.__orig_bases__[0])[1]

    def add(self, v:V): 
        self._validate(v)
        if v.id == None:
            self.session.add(v)
        else:
            raise ValueError("Not implemented yet!!")
    
    def get(self, id: K) -> V:
        return self.session.get(self.model_class, id)
    
    def get_all(self) -> Iterable[V]:
        return self.session.scalars(select(self.model_class)).all()
    
    def delete(self, k: K):
        v = self.get(k)
        self.session.delete(v)
    
    def update(self, v: V):
        self._validate(v)
        status = inspect(v)
        # persistent (s'ha fet el commit) detached (s'ha tancat la sessio)
        if status.persistent or status.detached:
            # copia els atributs de v sobre l'objecte de la sessió
            self.session.merge(v)

    @abstractmethod 
    def _validate(self, v:V) -> None:
        ...

class UserRepository(AbstractRepository[str, User]):
    def _validate(self, user: User) -> None:
        if user.user_name is None:
            raise ValueError("User name attribute is mandatory")
        if user.alias is None:
            user.alias = user.user_name
        if user.email is None:
            raise ValueError("Email attribute is mandatory")
        if user.password is None:
            raise ValueError("Password attribute is mandatory")

class RecipeRepository(AbstractRepository[str, Recipe]):
    def _validate(self, recipe: Recipe) -> None:
        if recipe.name is None:
            raise ValueError("Name attribute is mandatory")
        if recipe.step_by_step is None:
            raise ValueError("Step_by_step attribute is mandatory")
    
    """ ··· SPECIFIC GET OR FILTER QUERIES ················································· """

    def get_by_name(self, name: str):
        stmt = (
            select(Recipe)
            .where(Recipe.name == name)
        )
        return self.session.scalars(stmt).all()
    
    def get_by_category(self, category: str):
        stmt = (
            select(Recipe)
            .where(Recipe.categories.any(Category.name == category))
        )
        return self.session.scalars(stmt).all()
    
    """ ··· CONCRETE DOMAIN OPERATIONS ····················································· """

    def add_ingredient(self, recipe_id: int, ingredient_id: int, quantity: str, isoptional: bool = False, ischecked: bool = False ):
        existing = self.session.scalars(
            select(ListIngredients)
            .where(ListIngredients.id_recipe == recipe_id)
            .where(ListIngredients.id_plant == ingredient_id)
        ).first()

        if existing:
            existing.quantity = quantity
        else:
            list_ingredient = ListIngredients(
                id_recipe=recipe_id,
                id_plant=ingredient_id,
                quantity=quantity,
                isoptional = isoptional,
                is_checked = ischecked
            )
            self.session.add(list_ingredient)
    
    """ ··· PAGINATION FOR THE ENTITY ······················································ """

    def get_paginated(self, page: int, page_size: int) -> Iterable[Recipe]:
        stmt = (
            select(Recipe)
            .order_by(Recipe.name)
            .limit(page_size)
            .offset((page - 1) * page_size) #  li diu a la BD quants registres ha de saltar abans de començar a retornar dades.
        ) # query de l'entitat per ordenar i limita les dades a mostrar
        return self.session.scalars(stmt).all() # retorna el resultat


class CategoryRepository(AbstractRepository[str, Category]):
    def _validate(self, category: Category) -> None:
        if category.name is None:
            raise ValueError("Name attribute is mandatory")

class IngredientRepository(AbstractRepository[str, Ingredient]):
    def _validate(self, ingredient: Ingredient) -> None:
        if ingredient.common_name is None:
            raise ValueError("Name attribute is mandatory")
        if ingredient.type is None:
            raise ValueError("Type attribute is mandatory")