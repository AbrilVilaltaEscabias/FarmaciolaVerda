"""Business logic for recipes and their ingredients."""
from typing import Optional

from src.common.dto import ListIngredientDTO, RecipeDTO
from src.server.domain.exceptions import NotFoundError
from src.server.domain.model import Recipe
from src.server.services.crud_service import CrudService, get_or_raise
from src.server.services.mappers import (
    to_list_ingredient,
    to_recipe,
    to_recipe_summary,
)


class RecipeService(CrudService):
    _label = "Recipe"
    _repository = "recipes"
    _model = Recipe
    _to_dto = staticmethod(to_recipe)
    _to_list_dto = staticmethod(to_recipe_summary)  # the plain list is short

    def search(
        self, name: Optional[str] = None, category: Optional[str] = None
    ) -> list[RecipeDTO]:
        """Full recipes matching ALL the given filters."""
        with self._uow_factory() as uow:
            matches = None
            if name is not None:
                matches = {r.id: r for r in uow.recipes.get_by_name(name)}
            if category is not None:
                by_category = {
                    r.id: r for r in uow.recipes.get_by_category(category)
                }
                matches = (
                    by_category
                    if matches is None
                    else {i: r for i, r in matches.items() if i in by_category}
                )
            return [to_recipe(r) for r in (matches or {}).values()]

    def add_ingredient(
        self,
        recipe_id: int,
        ingredient_id: int,
        quantity: str,
        is_optional: bool = False,
        is_checked: bool = False,
    ) -> RecipeDTO:
        """Add an ingredient to a recipe (or update its quantity)."""
        with self._uow_factory() as uow:
            recipe = self._find(uow, recipe_id)
            get_or_raise(uow.ingredients, ingredient_id, "Ingredient")
            uow.recipes.add_ingredient(
                recipe_id,
                ingredient_id,
                quantity,
                isoptional=is_optional,
                ischecked=is_checked,
            )
            uow.flush()
            return to_recipe(recipe)

    def remove_ingredient(self, recipe_id: int, ingredient_id: int) -> None:
        with self._uow_factory() as uow:
            self._find(uow, recipe_id)
            if not uow.recipes.remove_ingredient(recipe_id, ingredient_id):
                raise NotFoundError(
                    f"Ingredient {ingredient_id} is not in recipe {recipe_id}"
                )

    def list_ingredients(self, recipe_id: int) -> list[ListIngredientDTO]:
        with self._uow_factory() as uow:
            recipe = self._find(uow, recipe_id)
            return [to_list_ingredient(i) for i in recipe.list_ingredients]
