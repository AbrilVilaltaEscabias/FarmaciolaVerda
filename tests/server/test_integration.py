"""End to end: raw bytes -> server -> validation -> router -> services ->
real repositories on an in-memory SQLite database -> response."""
import pytest

from src.common.operations import Entity as E, Operation as O
from src.common.protocol import Request, serialize_request
from src.server.infrastructure.db import Base, engine
from src.server.server import Server, build_router

import src.server.domain.model  # noqa: F401  (registers the tables)


@pytest.fixture
def send():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    server = Server(build_router())

    def _send(operation, entity, data=None):
        raw = serialize_request(Request(operation, entity, data or {}))
        return server.process_message(raw)

    return _send


def ok(response):
    assert response.is_ok, response.error
    return response.data


def test_user_lifecycle(send):
    user = ok(send(O.CREATE, E.USER, {
        "user_name": "ana", "email": "a@x.com", "password": "secret",
        "profile": {"country": "ES"}}))
    assert user["id"] == 1 and user["profile"]["country"] == "ES"
    assert "password" not in user

    ok(send(O.UPDATE, E.USER, {"id": 1, "alias": "an"}))
    assert ok(send(O.READ, E.USER, {"id": 1}))["alias"] == "an"

    ok(send(O.DELETE, E.USER, {"id": 1}))
    assert send(O.READ, E.USER, {"id": 1}).error["code"] == "not_found"


def test_duplicated_email_is_a_conflict(send):
    data = {"user_name": "ana", "email": "a@x.com", "password": "secret"}
    ok(send(O.CREATE, E.USER, data))
    assert send(O.CREATE, E.USER, data).error["code"] == "conflict"


def test_invalid_request_never_reaches_the_database(send):
    response = send(O.CREATE, E.USER, {"user_name": "ana"})
    assert response.error["code"] == "validation_error"


def test_recipe_with_ingredients_and_filters(send):
    ok(send(O.CREATE, E.INGREDIENT, {"common_name": "Mint", "type": "herb"}))
    ok(send(O.CREATE, E.RECIPE, {"name": "Tea", "step_by_step": "Boil",
                                 "duration": 10}))
    recipe = ok(send(O.CREATE, E.RECIPE_INGREDIENT, {
        "recipe_id": 1, "ingredient_id": 1, "quantity": "5 g"}))
    assert recipe["ingredients"][0]["ingredient"]["common_name"] == "Mint"
    assert recipe["created_at"] is not None

    short = ok(send(O.LIST, E.RECIPE))
    assert short == [{"id": 1, "name": "Tea", "duration": 10}]

    (found,) = ok(send(O.LIST, E.RECIPE, {"name": "Tea"}))
    assert found["ingredients"][0]["quantity"] == "5 g"
    assert ok(send(O.LIST, E.RECIPE, {"name": "Coffee"})) == []

    ok(send(O.DELETE, E.RECIPE_INGREDIENT,
            {"recipe_id": 1, "ingredient_id": 1}))
    assert ok(send(O.LIST, E.RECIPE_INGREDIENT, {"recipe_id": 1})) == []


def test_deleting_a_recipe_removes_its_ingredient_rows(send):
    ok(send(O.CREATE, E.INGREDIENT, {"common_name": "Mint", "type": "herb"}))
    ok(send(O.CREATE, E.RECIPE, {"name": "Tea", "step_by_step": "Boil"}))
    ok(send(O.CREATE, E.RECIPE_INGREDIENT, {
        "recipe_id": 1, "ingredient_id": 1, "quantity": "5 g"}))
    ok(send(O.DELETE, E.RECIPE, {"id": 1}))
    assert ok(send(O.LIST, E.RECIPE)) == []
    assert ok(send(O.READ, E.INGREDIENT, {"id": 1}))["common_name"] == "Mint"


def test_wish_lists(send):
    ok(send(O.CREATE, E.USER, {
        "user_name": "ana", "email": "a@x.com", "password": "secret"}))
    ok(send(O.CREATE, E.RECIPE, {"name": "Tea", "step_by_step": "Boil"}))
    ok(send(O.CREATE, E.INGREDIENT, {"common_name": "Mint", "type": "herb"}))

    link = {"user_id": 1, "recipe_id": 1}
    ok(send(O.CREATE, E.WISH_LIST_RECIPE, link))
    assert send(O.CREATE, E.WISH_LIST_RECIPE, link).error["code"] == "conflict"
    recipes = ok(send(O.LIST, E.WISH_LIST_RECIPE, {"user_id": 1}))
    assert recipes[0]["name"] == "Tea"

    ok(send(O.CREATE, E.WISH_LIST_INGREDIENT,
            {"user_id": 1, "ingredient_id": 1}))
    plants = ok(send(O.LIST, E.WISH_LIST_INGREDIENT, {"user_id": 1}))
    assert plants[0]["common_name"] == "Mint"

    ok(send(O.DELETE, E.WISH_LIST_RECIPE, link))
    assert ok(send(O.LIST, E.WISH_LIST_RECIPE, {"user_id": 1})) == []
