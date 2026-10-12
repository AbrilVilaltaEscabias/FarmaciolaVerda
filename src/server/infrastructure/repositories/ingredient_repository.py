
from ..abstract_repositories import AbstractRepository
from ...domain.model.ingredient import Ingredient


class IngredientRepository(AbstractRepository[str, Ingredient]):

    def _validate(self, ingredient: Ingredient) -> None:
        if ingredient.common_name is None:
            raise ValueError("Name attribute is mandatory")

        if ingredient.type is None:
            raise ValueError("Type attribute is mandatory")
