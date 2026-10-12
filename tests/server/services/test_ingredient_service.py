import pytest

from src.common.dto import IngredientDTO
from src.server.domain.exceptions import NotFoundError
from src.server.domain.model import Ingredient
from src.server.services.ingredient_service import IngredientService


def make_ingredient(**overrides) -> Ingredient:
    fields = {"id": 2, "common_name": "Mint", "type": "herb"}
    return Ingredient(**{**fields, **overrides})


@pytest.fixture
def service(uow_factory):
    return IngredientService(uow_factory)


def test_create_adds_the_ingredient_and_returns_a_dto(service, uow):
    result = service.create(
        common_name="Mint", type="herb", family="Lamiaceae")

    added = uow.ingredients.add.call_args.args[0]
    assert added.common_name == "Mint"
    uow.flush.assert_called_once()
    assert isinstance(result, IngredientDTO)
    assert result.family == "Lamiaceae"


def test_get_returns_a_dto(service, uow):
    uow.ingredients.get.return_value = make_ingredient()
    assert service.get(2).common_name == "Mint"


def test_get_unknown_ingredient_fails(service, uow):
    uow.ingredients.get.return_value = None
    with pytest.raises(NotFoundError):
        service.get(99)


def test_update_changes_only_the_given_fields(service, uow):
    ingredient = make_ingredient(family="Old")
    uow.ingredients.get.return_value = ingredient

    result = service.update(2, family="Lamiaceae")

    assert result.family == "Lamiaceae"
    assert result.common_name == "Mint"
    uow.ingredients.update.assert_called_once_with(ingredient)


def test_delete_unknown_ingredient_fails(service, uow):
    uow.ingredients.get.return_value = None
    with pytest.raises(NotFoundError):
        service.delete(99)
    uow.ingredients.delete.assert_not_called()


def test_delete_removes_it(service, uow):
    uow.ingredients.get.return_value = make_ingredient()
    service.delete(2)
    uow.ingredients.delete.assert_called_once_with(2)


def test_list_all_returns_full_dtos(service, uow):
    uow.ingredients.get_all.return_value = [make_ingredient(id=1),
                                            make_ingredient(id=2)]
    assert [i.id for i in service.list_all()] == [1, 2]
