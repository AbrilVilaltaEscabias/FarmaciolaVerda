from datetime import datetime

import pytest

from src.common.dto import RecipeDTO, RecipeSummaryDTO
from src.server.domain.exceptions import NotFoundError
from src.server.domain.model import Ingredient, ListIngredients, Recipe
from src.server.services.recipe_service import RecipeService


def make_recipe(recipe_id=1, **overrides) -> Recipe:
    fields = {"id": recipe_id, "name": "Tea", "step_by_step": "Boil water",
              "duration": 10}
    return Recipe(**{**fields, **overrides})


@pytest.fixture
def service(uow_factory):
    return RecipeService(uow_factory)


class TestCrud:
    def test_create_returns_a_full_dto(self, service, uow):
        result = service.create(name="Tea", step_by_step="Boil water")
        uow.recipes.add.assert_called_once()
        uow.flush.assert_called_once()
        assert isinstance(result, RecipeDTO) and result.name == "Tea"

    def test_get_unknown_recipe_fails(self, service, uow):
        uow.recipes.get.return_value = None
        with pytest.raises(NotFoundError, match="Recipe 9"):
            service.get(9)

    def test_dates_are_sent_as_iso_strings(self, service, uow):
        uow.recipes.get.return_value = make_recipe(
            created_at=datetime(2026, 1, 2, 3, 4, 5))
        assert service.get(1).created_at == "2026-01-02T03:04:05"

    def test_update_changes_only_the_given_fields(self, service, uow):
        uow.recipes.get.return_value = make_recipe()
        result = service.update(1, duration=20)
        assert result.duration == 20 and result.name == "Tea"

    def test_plain_list_returns_summaries(self, service, uow):
        uow.recipes.get_all.return_value = [make_recipe(1), make_recipe(2)]
        result = service.list_all()
        assert all(isinstance(r, RecipeSummaryDTO) for r in result)
        assert [r.id for r in result] == [1, 2]

    def test_delete_unknown_recipe_fails(self, service, uow):
        uow.recipes.get.return_value = None
        with pytest.raises(NotFoundError):
            service.delete(9)
        uow.recipes.delete.assert_not_called()


class TestSearch:
    def test_by_name(self, service, uow):
        uow.recipes.get_by_name.return_value = [make_recipe(1)]
        result = service.search(name="Tea")
        uow.recipes.get_by_name.assert_called_once_with("Tea")
        assert isinstance(result[0], RecipeDTO)

    def test_by_category(self, service, uow):
        uow.recipes.get_by_category.return_value = [make_recipe(1)]
        assert len(service.search(category="Infusion")) == 1

    def test_both_filters_must_match(self, service, uow):
        uow.recipes.get_by_name.return_value = [make_recipe(1), make_recipe(2)]
        uow.recipes.get_by_category.return_value = [make_recipe(2)]
        result = service.search(name="Tea", category="Infusion")
        assert [r.id for r in result] == [2]

    def test_no_match_gives_an_empty_list(self, service, uow):
        uow.recipes.get_by_name.return_value = []
        assert service.search(name="nothing") == []


class TestIngredients:
    def test_add_ingredient_delegates_to_the_repository(self, service, uow):
        uow.recipes.get.return_value = make_recipe()
        uow.ingredients.get.return_value = Ingredient(
            id=2, common_name="Mint", type="herb")

        service.add_ingredient(1, 2, "5 g", is_optional=True)

        uow.recipes.add_ingredient.assert_called_once_with(
            1, 2, "5 g", isoptional=True, ischecked=False)

    def test_add_ingredient_to_unknown_recipe_fails(self, service, uow):
        uow.recipes.get.return_value = None
        with pytest.raises(NotFoundError, match="Recipe"):
            service.add_ingredient(1, 2, "5 g")
        uow.recipes.add_ingredient.assert_not_called()

    def test_add_unknown_ingredient_fails(self, service, uow):
        uow.recipes.get.return_value = make_recipe()
        uow.ingredients.get.return_value = None
        with pytest.raises(NotFoundError, match="Ingredient"):
            service.add_ingredient(1, 2, "5 g")
        uow.recipes.add_ingredient.assert_not_called()

    def test_remove_ingredient_that_is_not_there_fails(self, service, uow):
        uow.recipes.get.return_value = make_recipe()
        uow.recipes.remove_ingredient.return_value = False
        with pytest.raises(NotFoundError):
            service.remove_ingredient(1, 2)

    def test_remove_ingredient(self, service, uow):
        uow.recipes.get.return_value = make_recipe()
        uow.recipes.remove_ingredient.return_value = True
        service.remove_ingredient(1, 2)
        uow.recipes.remove_ingredient.assert_called_once_with(1, 2)

    def test_list_ingredients_maps_quantities(self, service, uow):
        recipe = make_recipe()
        recipe.list_ingredients = [ListIngredients(
            id=7, quantity="5 g", isoptional=True, is_checked=False,
            plant=Ingredient(id=2, common_name="Mint", type="herb"))]
        uow.recipes.get.return_value = recipe

        (entry,) = service.list_ingredients(1)

        assert entry.ingredient.common_name == "Mint"
        assert entry.quantity == "5 g" and entry.is_optional
