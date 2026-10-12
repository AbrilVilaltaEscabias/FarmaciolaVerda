import pytest

from src.common.operations import Entity as E, Operation as O
from src.common.protocol import Request
from src.server.validation import ValidationError, validate_request

VALID_USER = {"user_name": "ana", "email": "a@x.com", "password": "secret"}
VALID_RECIPE = {"name": "Tea", "step_by_step": "Boil water"}


@pytest.mark.parametrize(
    "entity, operation, data",
    [
        (E.USER, O.CREATE, VALID_USER),
        (E.USER, O.CREATE, {**VALID_USER, "profile": {"bio": "hi"}}),
        (E.USER, O.READ, {"id": 1}),
        (E.USER, O.UPDATE, {"id": 1, "profile": {"country": "ES"}}),
        (E.USER, O.LIST, {}),
        (E.RECIPE, O.CREATE, {**VALID_RECIPE, "duration": 10}),
        (E.RECIPE, O.LIST, {"category": "Infusion"}),
        (E.INGREDIENT, O.UPDATE, {"id": 2, "family": "Lamiaceae"}),
        (E.WISH_LIST_RECIPE, O.CREATE, {"user_id": 1, "recipe_id": 2}),
        (E.WISH_LIST_INGREDIENT, O.LIST, {"user_id": 1}),
        (E.RECIPE_INGREDIENT, O.CREATE,
         {"recipe_id": 1, "ingredient_id": 2, "quantity": "5 g"}),
        (E.CATEGORY, O.DELETE, {"anything": 1}),  # no spec: router decides
    ],
)
def test_valid_requests_pass(entity, operation, data):
    validate_request(Request(operation, entity, data))


@pytest.mark.parametrize(
    "entity, operation, data, message",
    [
        (E.USER, O.CREATE, {"user_name": "ana"}, "'email' is required"),
        (E.USER, O.CREATE, {**VALID_USER, "email": "nope"}, "valid email"),
        (E.USER, O.CREATE, {**VALID_USER, "password": "  "}, "non-empty"),
        (E.USER, O.CREATE, {**VALID_USER, "id": 5}, "Unknown fields"),
        (E.USER, O.CREATE, {**VALID_USER, "profile": {"hack": "x"}},
         "Unknown profile"),
        (E.USER, O.READ, {}, "'id' is required"),
        (E.USER, O.READ, {"id": 0}, "positive integer"),
        (E.USER, O.READ, {"id": True}, "positive integer"),
        (E.USER, O.READ, {"id": "1"}, "positive integer"),
        (E.USER, O.UPDATE, {"id": 1}, "Nothing to update"),
        (E.RECIPE, O.CREATE, {**VALID_RECIPE, "duration": -5}, "positive"),
        (E.RECIPE, O.CREATE, {"name": "Tea"}, "'step_by_step' is required"),
        (E.RECIPE, O.LIST, {"colour": "red"}, "Unknown fields"),
        (E.WISH_LIST_RECIPE, O.CREATE, {"user_id": 1}, "'recipe_id'"),
        (E.WISH_LIST_INGREDIENT, O.LIST, {}, "'user_id' is required"),
        (E.RECIPE_INGREDIENT, O.CREATE,
         {"recipe_id": 1, "ingredient_id": 2, "quantity": ""}, "non-empty"),
        (E.RECIPE_INGREDIENT, O.CREATE,
         {"recipe_id": 1, "ingredient_id": 2, "quantity": "1",
          "is_optional": "yes"}, "boolean"),
    ],
)
def test_invalid_requests_are_rejected(entity, operation, data, message):
    with pytest.raises(ValidationError, match=message):
        validate_request(Request(operation, entity, data))


def test_none_optional_values_are_ignored():
    validate_request(
        Request(O.CREATE, E.USER, {**VALID_USER, "alias": None})
    )