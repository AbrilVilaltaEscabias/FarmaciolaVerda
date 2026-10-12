from unittest.mock import MagicMock

import pytest

from src.common.operations import Entity as E, Operation as O
from src.common.protocol import Request
from src.server.router import Router
from src.server.routes import (
    register_ingredient_routes,
    register_recipe_routes,
    register_user_routes,
)


@pytest.fixture
def service():
    return MagicMock()


class TestUserRoutes:
    @pytest.fixture
    def router(self, service):
        router = Router()
        register_user_routes(router, service)
        return router

    def test_create_maps_fields_to_service(self, router, service):
        data = {"user_name": "ana", "email": "a@x.com", "password": "pw"}
        router.handle(Request(O.CREATE, E.USER, data))
        service.create.assert_called_once_with(
            user_name="ana", email="a@x.com", password="pw",
            alias=None, phone=None,
        )

    def test_create_passes_the_profile(self, router, service):
        data = {"user_name": "ana", "email": "a@x.com", "password": "pw",
                "profile": {"bio": "hi"}}
        router.handle(Request(O.CREATE, E.USER, data))
        assert service.create.call_args.kwargs["profile"] == {"bio": "hi"}

    def test_update_only_sends_provided_fields(self, router, service):
        router.handle(Request(O.UPDATE, E.USER, {"id": 1, "alias": "an"}))
        service.update.assert_called_once_with(1, alias="an")

    def test_read_delete_and_list(self, router, service):
        router.handle(Request(O.READ, E.USER, {"id": 3}))
        router.handle(Request(O.DELETE, E.USER, {"id": 3}))
        router.handle(Request(O.LIST, E.USER, {}))
        service.get.assert_called_once_with(3)
        service.delete.assert_called_once_with(3)
        service.list_all.assert_called_once_with()

    def test_wish_list_add_calls_service(self, router, service):
        data = {"user_id": 1, "recipe_id": 5}
        router.handle(Request(O.CREATE, E.WISH_LIST_RECIPE, data))
        service.add_wish_recipe.assert_called_once_with(1, 5)

    def test_ingredient_wish_list_routes(self, router, service):
        data = {"user_id": 1, "ingredient_id": 2}
        router.handle(Request(O.DELETE, E.WISH_LIST_INGREDIENT, data))
        router.handle(Request(O.LIST, E.WISH_LIST_INGREDIENT, {"user_id": 1}))
        service.remove_wish_ingredient.assert_called_once_with(1, 2)
        service.list_wish_ingredients.assert_called_once_with(1)

    def test_service_result_is_sent_as_a_dict(self, router, service):
        service.get.return_value = MagicMock(to_dict=lambda: {"id": 3})
        response = router.handle(Request(O.READ, E.USER, {"id": 3}))
        assert response.data == {"id": 3}


class TestRecipeRoutes:
    @pytest.fixture
    def router(self, service):
        router = Router()
        register_recipe_routes(router, service)
        return router

    def test_create(self, router, service):
        data = {"name": "Tea", "step_by_step": "Boil", "duration": None}
        router.handle(Request(O.CREATE, E.RECIPE, data))
        service.create.assert_called_once_with(name="Tea", step_by_step="Boil")

    def test_list_without_filters_gives_the_short_list(self, router, service):
        router.handle(Request(O.LIST, E.RECIPE, {}))
        service.list_all.assert_called_once_with()
        service.search.assert_not_called()

    def test_list_with_filters_searches(self, router, service):
        router.handle(Request(O.LIST, E.RECIPE, {"category": "Infusion"}))
        service.search.assert_called_once_with(category="Infusion")
        service.list_all.assert_not_called()

    def test_add_ingredient_to_recipe(self, router, service):
        data = {"recipe_id": 1, "ingredient_id": 2, "quantity": "5 g"}
        router.handle(Request(O.CREATE, E.RECIPE_INGREDIENT, data))
        service.add_ingredient.assert_called_once_with(
            1, 2, "5 g", is_optional=False, is_checked=False)

    def test_remove_and_list_recipe_ingredients(self, router, service):
        pair = {"recipe_id": 1, "ingredient_id": 2}
        router.handle(Request(O.DELETE, E.RECIPE_INGREDIENT, pair))
        router.handle(Request(O.LIST, E.RECIPE_INGREDIENT, {"recipe_id": 1}))
        service.remove_ingredient.assert_called_once_with(1, 2)
        service.list_ingredients.assert_called_once_with(1)


class TestIngredientRoutes:
    def test_crud_is_registered(self, service):
        router = Router()
        register_ingredient_routes(router, service)
        data = {"id": 2, "family": "F"}
        router.handle(Request(O.UPDATE, E.INGREDIENT, data))
        service.update.assert_called_once_with(2, family="F")

    def test_other_entities_are_not_supported(self, service):
        router = Router()
        register_ingredient_routes(router, service)
        response = router.handle(Request(O.LIST, E.CATEGORY, {}))
        assert not response.is_ok
