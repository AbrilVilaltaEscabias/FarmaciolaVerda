"""Maps (entity, operation) pairs to the handler that executes them."""
from typing import Any, Callable, Dict, Tuple

from src.common.operations import Entity, Operation
from src.common.protocol import ErrorCode, Request, Response
from src.server.domain.exceptions import AlreadyExistsError, NotFoundError

Handler = Callable[[dict], Any]
RouteKey = Tuple[Entity, Operation]
E, O = Entity, Operation


def _to_payload(result: Any) -> Any:
    """Turn what a service returns (DTOs) into JSON-friendly structures."""
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if isinstance(result, (list, tuple)):
        return [_to_payload(item) for item in result]
    return result


class Router:
    """Receives a validated Request and returns a Response.

    The router knows nothing about services or the database: routes are
    registered from outside (see routes.py), so adding an entity never
    requires touching this class.
    """

    def __init__(self) -> None:
        self._handlers: Dict[RouteKey, Handler] = {}

    def register(
        self, entity: Entity, operation: Operation, handler: Handler
    ) -> None:
        key = (entity, operation)
        if key in self._handlers:
            raise ValueError(
                f"Route already registered: {entity.value}/{operation.value}"
            )
        self._handlers[key] = handler

    def handle(self, request: Request) -> Response:
        handler = self._handlers.get((request.entity, request.operation))
        if handler is None:
            return Response.failure(
                ErrorCode.UNKNOWN_OPERATION,
                f"Operation '{request.operation.value}' is not supported "
                f"for entity '{request.entity.value}'",
            )
        try:
            return Response.ok(_to_payload(handler(request.data)))
        except NotFoundError as exc:
            return Response.failure(ErrorCode.NOT_FOUND, str(exc))
        except AlreadyExistsError as exc:
            return Response.failure(ErrorCode.CONFLICT, str(exc))


# ------------------------------------------------------------ registration
def _pick(data: dict, *keys: str) -> dict:
    """The given keys that are present in data (and not None)."""
    return {k: data[k] for k in keys if data.get(k) is not None}


USER_FIELDS = ("user_name", "email", "password", "alias", "phone", "profile")


def register_user_routes(router: Router, service: Any) -> None:
    """Routes for users and their wish lists.

    `service` is expected to offer: create, get, update, delete, list_all,
    add_wish_recipe, remove_wish_recipe, list_wish_recipes,
    add_wish_ingredient, remove_wish_ingredient, list_wish_ingredients.
    """

    def create(data: dict) -> Any:
        return service.create(
            user_name=data["user_name"],
            email=data["email"],
            password=data["password"],
            alias=data.get("alias"),
            phone=data.get("phone"),
            **_pick(data, "profile"),
        )

    def update(data: dict) -> Any:
        return service.update(data["id"], **_pick(data, *USER_FIELDS))

    routes = {
        (E.USER, O.CREATE): create,
        (E.USER, O.READ): lambda d: service.get(d["id"]),
        (E.USER, O.UPDATE): update,
        (E.USER, O.DELETE): lambda d: service.delete(d["id"]),
        (E.USER, O.LIST): lambda d: service.list_all(),
        (E.WISH_LIST_RECIPE, O.CREATE):
            lambda d: service.add_wish_recipe(d["user_id"], d["recipe_id"]),
        (E.WISH_LIST_RECIPE, O.DELETE):
            lambda d: service.remove_wish_recipe(d["user_id"], d["recipe_id"]),
        (E.WISH_LIST_RECIPE, O.LIST):
            lambda d: service.list_wish_recipes(d["user_id"]),
        (E.WISH_LIST_INGREDIENT, O.CREATE):
            lambda d: service.add_wish_ingredient(
                d["user_id"], d["ingredient_id"]),
        (E.WISH_LIST_INGREDIENT, O.DELETE):
            lambda d: service.remove_wish_ingredient(
                d["user_id"], d["ingredient_id"]),
        (E.WISH_LIST_INGREDIENT, O.LIST):
            lambda d: service.list_wish_ingredients(d["user_id"]),
    }
    for (entity, operation), handler in routes.items():
        router.register(entity, operation, handler)