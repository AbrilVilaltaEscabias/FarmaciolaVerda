
from collections.abc import Iterable

from sqlalchemy import select

from ..abstract_repositories import AbstractRepository
from ...domain.model.recipe import Recipe
from ...domain.model.category import Category
from ...domain.model.list_ingredients import ListIngredients


class RecipeRepository(AbstractRepository[str, Recipe]):

    def _validate(self, recipe: Recipe) -> None:
        if recipe.name is None:
            raise ValueError("Name attribute is mandatory")

        if recipe.step_by_step is None:
            raise ValueError("Step_by_step attribute is mandatory")

    def get_by_name(self, name: str) -> list[Recipe]:
        stmt = select(Recipe).where(Recipe.name == name)
        return self.session.scalars(stmt).all()

    def get_by_category(self, category: str) -> list[Recipe]:
        stmt = select(Recipe).where(
            Recipe.categories.any(Category.name == category)
        )
        return self.session.scalars(stmt).all()

    def add_ingredient(
        self,
        recipe_id: int,
        ingredient_id: int,
        quantity: str,
        isoptional: bool = False,
        ischecked: bool = False,
    ) -> None:
        stmt = select(ListIngredients).where(
            ListIngredients.id_recipe == recipe_id,
            ListIngredients.id_plant == ingredient_id,
        )

        existing = self.session.scalars(stmt).first()

        if existing:
            existing.quantity = quantity
            existing.isoptional = isoptional
            existing.is_checked = ischecked
        else:
            list_ingredient = ListIngredients(
                id_recipe=recipe_id,
                id_plant=ingredient_id,
                quantity=quantity,
                isoptional=isoptional,
                is_checked=ischecked,
            )
            self.session.add(list_ingredient)

    def remove_ingredient(self, recipe_id: int, ingredient_id: int) -> bool:
        """Remove an ingredient from a recipe. False if it was not there."""
        stmt = select(ListIngredients).where(
            ListIngredients.id_recipe == recipe_id,
            ListIngredients.id_plant == ingredient_id,
        )
        existing = self.session.scalars(stmt).first()
        if existing is None:
            return False
        self.session.delete(existing)
        return True

    def get_paginated(
        self,
        page: int,
        page_size: int,
    ) -> Iterable[Recipe]:
        if page < 1 or page_size < 1:
            raise ValueError("Page and page_size must be positive")

        stmt = (
            select(Recipe)
            .order_by(Recipe.name)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        return self.session.scalars(stmt).all()
