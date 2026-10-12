"""Business-level validation of already-parsed requests.

Unknown operations/entities are already rejected by the protocol layer.

Each (entity, operation) pair that needs checking has a Spec describing its
fields. Pairs without a spec are not validated here: the router decides
whether they are supported.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from src.common.operations import Entity, Operation
from src.common.protocol import Request


class ValidationError(Exception):
    """The request is well-formed but its content is not valid."""


# ---------------------------------------------------------------- checkers
Checker = Callable[[str, object], None]


def _string(key: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{key}' must be a non-empty string")


def _email(key: str, value: object) -> None:
    _string(key, value)
    if "@" not in value:
        raise ValidationError(f"'{key}' is not a valid email address")


def _positive_int(key: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(f"'{key}' must be a positive integer")


def _boolean(key: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValidationError(f"'{key}' must be a boolean")


PROFILE_FIELDS = ("bio", "img", "country")


def _profile(key: str, value: object) -> None:
    if not isinstance(value, dict):
        raise ValidationError(f"'{key}' must be an object")
    unknown = sorted(set(value) - set(PROFILE_FIELDS))
    if unknown:
        raise ValidationError(f"Unknown profile fields: {', '.join(unknown)}")
    for name, item in value.items():
        if item is not None:
            _string(name, item)


# -------------------------------------------------------------------- spec
@dataclass(frozen=True)
class Spec:
    required: Dict[str, Checker] = field(default_factory=dict)
    optional: Dict[str, Checker] = field(default_factory=dict)
    needs_id: bool = False
    at_least_one_optional: bool = False  # updates must change something

    def validate(self, data: dict) -> None:
        # None means "not provided" for optional fields.
        data = {k: v for k, v in data.items()
                if v is not None or k in self.required or k == "id"}

        allowed = set(self.required) | set(self.optional)
        if self.needs_id:
            allowed.add("id")
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValidationError(f"Unknown fields: {', '.join(unknown)}")

        if self.needs_id:
            if "id" not in data:
                raise ValidationError("'id' is required")
            _positive_int("id", data["id"])

        for key, check in self.required.items():
            if key not in data or data[key] is None:
                raise ValidationError(f"'{key}' is required")
            check(key, data[key])

        provided = [k for k in self.optional if k in data]
        if self.at_least_one_optional and not provided:
            names = ", ".join(f"'{k}'" for k in self.optional)
            raise ValidationError(
                f"Nothing to update: provide at least one of {names}"
            )
        for key in provided:
            self.optional[key](key, data[key])


# ------------------------------------------------------------ field tables
_USER = {
    "user_name": _string, "alias": _string, "email": _email,
    "phone": _string, "password": _string, "profile": _profile,
}
_RECIPE = {
    "name": _string, "step_by_step": _string, "duration": _positive_int,
    "sub_name": _string, "note": _string, "dosage": _string,
    "description": _string,
}
_INGREDIENT = {
    "common_name": _string, "type": _string, "scientific_name": _string,
    "family": _string, "description": _string, "country_origin": _string,
    "image_url": _string,
}


def _only(table: dict, *keys: str) -> dict:
    return {k: table[k] for k in keys}


def _without(table: dict, *keys: str) -> dict:
    return {k: v for k, v in table.items() if k not in keys}


def _crud(table: dict, required: tuple, list_filters: dict) -> dict:
    """Standard CRUD specs for a main entity."""
    return {
        Operation.CREATE: Spec(
            required=_only(table, *required),
            optional=_without(table, *required),
        ),
        Operation.READ: Spec(needs_id=True),
        Operation.UPDATE: Spec(
            needs_id=True, optional=table, at_least_one_optional=True
        ),
        Operation.DELETE: Spec(needs_id=True),
        Operation.LIST: Spec(optional=list_filters),
    }


def _relation(
    left: str,
    right: str,
    create_required: Optional[dict] = None,
    create_optional: Optional[dict] = None,
) -> dict:
    """Specs for a relation: create/delete by pair, list by `left`."""
    pair = {left: _positive_int, right: _positive_int}
    return {
        Operation.CREATE: Spec(
            required={**pair, **(create_required or {})},
            optional=create_optional or {},
        ),
        Operation.DELETE: Spec(required=pair),
        Operation.LIST: Spec(required={left: _positive_int}),
    }


_SPECS_BY_ENTITY: Dict[Entity, Dict[Operation, Spec]] = {
    Entity.USER: _crud(_USER, ("user_name", "email", "password"), {}),
    Entity.RECIPE: _crud(
        _RECIPE,
        ("name", "step_by_step"),
        {"name": _string, "category": _string},
    ),
    Entity.INGREDIENT: _crud(
        _INGREDIENT,
        ("common_name", "type"),
        _only(_INGREDIENT, "common_name", "type"),
    ),
    Entity.WISH_LIST_RECIPE: _relation("user_id", "recipe_id"),
    Entity.WISH_LIST_INGREDIENT: _relation("user_id", "ingredient_id"),
    Entity.RECIPE_INGREDIENT: _relation(
        "recipe_id",
        "ingredient_id",
        create_required={"quantity": _string},
        create_optional={"is_optional": _boolean, "is_checked": _boolean},
    ),
}

_SPECS: Dict[Tuple[Entity, Operation], Spec] = {
    (entity, operation): spec
    for entity, specs in _SPECS_BY_ENTITY.items()
    for operation, spec in specs.items()
}


def validate_request(request: Request) -> None:
    """Raise ValidationError if the request content is not acceptable."""
    spec = _SPECS.get((request.entity, request.operation))
    if spec is not None:
        spec.validate(request.data)
