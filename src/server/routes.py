"""Registers the routes: which service method answers each request.

Requests reach these handlers already validated (see validation.py), so
the handlers only translate request data into service calls.
"""
from typing import Any, Callable, Dict, Tuple

from src.common.operations import Entity, Operation
from src.server.router import Router

Handler = Callable[[dict], Any]
Routes = Dict[Tuple[Entity, Operation], Handler]


def _fields(data: dict) -> dict:
    """The request fields that carry a value (no id, no None)."""
    return {k: v for k, v in data.items() if k != "id" and v is not None}


def _register(router: Router, routes: Routes) -> None:
    for (entity, operation), handler in routes.items():
        router.register(entity, operation, handler)


def _crud_routes(entity: Entity, service: Any) -> Routes:
    """The five standard operations of a main entity."""
    return {
        (entity, Operation.CREATE):
            lambda d: service.create(**_fields(d)),
        (entity, Operation.READ):
            lambda d: service.get(d["id"]),
        (entity, Operation.UPDATE):
            lambda d: service.update(d["id"], **_fields(d)),
        (entity, Operation.DELETE):
            lambda d: service.delete(d["id"]),
        (entity, Operation.LIST):
            lambda d: service.list_all(),
    }


def register_user_routes(router: Router, service: Any) -> None:
    """Users and their wish lists (recipes and ingredients)."""

    def create_user(data: dict) -> Any:
        return service.create(
            user_name=data["user_name"],
            email=data["email"],
            password=data["password"],
            alias=data.get("alias"),
            phone=data.get("phone"),
            **{k: data[k] for k in ("profile",) if data.get(k) is not None},
        )

    routes = _crud_routes(Entity.USER, service)
    routes[(Entity.USER, Operation.CREATE)] = create_user
    routes.update({
        (Entity.WISH_LIST_RECIPE, Operation.CREATE):
            lambda d: service.add_wish_recipe(d["user_id"], d["recipe_id"]),
        (Entity.WISH_LIST_RECIPE, Operation.DELETE):
            lambda d: service.remove_wish_recipe(d["user_id"], d["recipe_id"]),
        (Entity.WISH_LIST_RECIPE, Operation.LIST):
            lambda d: service.list_wish_recipes(d["user_id"]),
        (Entity.WISH_LIST_INGREDIENT, Operation.CREATE):
            lambda d: service.add_wish_ingredient(
                d["user_id"], d["ingredient_id"]),
        (Entity.WISH_LIST_INGREDIENT, Operation.DELETE):
            lambda d: service.remove_wish_ingredient(
                d["user_id"], d["ingredient_id"]),
        (Entity.WISH_LIST_INGREDIENT, Operation.LIST):
            lambda d: service.list_wish_ingredients(d["user_id"]),
    })
    _register(router, routes)


def register_recipe_routes(router: Router, service: Any) -> None:
    """Recipes and the ingredients they contain."""

    def list_recipes(data: dict) -> Any:
        filters = _fields(data)
        return service.search(**filters) if filters else service.list_all()

    routes = _crud_routes(Entity.RECIPE, service)
    routes[(Entity.RECIPE, Operation.LIST)] = list_recipes
    routes.update({
        (Entity.RECIPE_INGREDIENT, Operation.CREATE):
            lambda d: service.add_ingredient(
                d["recipe_id"],
                d["ingredient_id"],
                d["quantity"],
                is_optional=d.get("is_optional", False),
                is_checked=d.get("is_checked", False),
        ),
        (Entity.RECIPE_INGREDIENT, Operation.DELETE):
            lambda d: service.remove_ingredient(
                d["recipe_id"], d["ingredient_id"]),
        (Entity.RECIPE_INGREDIENT, Operation.LIST):
            lambda d: service.list_ingredients(d["recipe_id"]),
    })
    _register(router, routes)


def register_ingredient_routes(router: Router, service: Any) -> None:
    _register(router, _crud_routes(Entity.INGREDIENT, service))
