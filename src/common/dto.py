"""Data Transfer Objects exchanged between client and server.

Plain dataclasses: no SQLAlchemy, no persistence concerns. Relations go in
ONE direction only (parent -> children) to avoid circular references.
Sensitive data (password) is never part of an output DTO.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional


class DictMixin:
    """Conversion to/from plain dictionaries, shared by all DTOs."""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


def _build_list(dto_class, items: Optional[list]) -> list:
    return [dto_class.from_dict(item) for item in items or []]


# ------------------------------------------------------------ simple DTOs
@dataclass(frozen=True)
class CategoryDTO(DictMixin):
    id: int
    name: str
    description: Optional[str] = None


@dataclass(frozen=True)
class PropertyDTO(DictMixin):
    id: int
    name: str
    description: Optional[str] = None


@dataclass(frozen=True)
class UserProfileDTO(DictMixin):
    bio: Optional[str] = None
    img: Optional[str] = None
    country: Optional[str] = None


# -------------------------------------------------------- summary DTOs
@dataclass(frozen=True)
class RecipeSummaryDTO(DictMixin):
    id: int
    name: str
    duration: Optional[int] = None


@dataclass(frozen=True)
class IngredientSummaryDTO(DictMixin):
    id: int
    common_name: str
    type: str


# ------------------------------------------------------------ full DTOs
@dataclass(frozen=True)
class ListIngredientDTO(DictMixin):
    """An ingredient inside a recipe, with its extra fields."""

    id: int
    ingredient: IngredientSummaryDTO
    quantity: Optional[str] = None
    is_optional: bool = False
    is_checked: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ListIngredientDTO":
        return cls(
            id=data["id"],
            ingredient=IngredientSummaryDTO.from_dict(data["ingredient"]),
            quantity=data.get("quantity"),
            is_optional=data.get("is_optional", False),
            is_checked=data.get("is_checked", False),
        )


@dataclass(frozen=True)
class RecipeDTO(DictMixin):
    id: int
    name: str
    step_by_step: str
    duration: Optional[int] = None
    sub_name: Optional[str] = None
    note: Optional[str] = None
    dosage: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None  # ISO 8601
    categories: list[CategoryDTO] = field(default_factory=list)
    ingredients: list[ListIngredientDTO] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "RecipeDTO":
        nested = {"categories", "ingredients"}
        flat = {k: v for k, v in data.items() if k not in nested}
        return cls(
            **flat,
            categories=_build_list(CategoryDTO, data.get("categories")),
            ingredients=_build_list(ListIngredientDTO, data.get("ingredients")),
        )


@dataclass(frozen=True)
class IngredientDTO(DictMixin):
    id: int
    common_name: str
    type: str
    scientific_name: Optional[str] = None
    family: Optional[str] = None
    description: Optional[str] = None
    country_origin: Optional[str] = None
    image_url: Optional[str] = None
    properties: list[PropertyDTO] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "IngredientDTO":
        flat = {k: v for k, v in data.items() if k != "properties"}
        return cls(
            **flat,
            properties=_build_list(PropertyDTO, data.get("properties")),
        )


@dataclass(frozen=True)
class UserDTO(DictMixin):
    """Output DTO. It deliberately has NO password field."""

    id: int
    user_name: str
    email: str
    alias: Optional[str] = None
    phone: Optional[str] = None
    profile: Optional[UserProfileDTO] = None
    wish_list_recipes: list[RecipeSummaryDTO] = field(default_factory=list)
    wish_list_ingredients: list[IngredientSummaryDTO] = field(
        default_factory=list
    )

    @classmethod
    def from_dict(cls, data: dict) -> "UserDTO":
        nested = {"profile", "wish_list_recipes", "wish_list_ingredients"}
        flat = {k: v for k, v in data.items() if k not in nested}
        profile = data.get("profile")
        return cls(
            **flat,
            profile=UserProfileDTO.from_dict(profile) if profile else None,
            wish_list_recipes=_build_list(
                RecipeSummaryDTO, data.get("wish_list_recipes")
            ),
            wish_list_ingredients=_build_list(
                IngredientSummaryDTO, data.get("wish_list_ingredients")
            ),
        )