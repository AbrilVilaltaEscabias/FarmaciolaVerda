"""Business logic for users, their profile and their wish lists."""
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.common.dto import IngredientDTO, RecipeSummaryDTO, UserDTO
from src.server.domain.exceptions import AlreadyExistsError, NotFoundError
from src.server.domain.model import User, UserProfile
from src.server.services.crud_service import CrudService, get_or_raise
from src.server.services.mappers import (
    to_ingredient,
    to_recipe_summary,
    to_user,
)
from src.server.services.security import hash_password


@dataclass(frozen=True)
class _WishList:
    """Where a kind of wish list lives, so recipes and plants share code."""

    repository: str  # attribute of the unit of work
    collection: str  # attribute of User
    label: str
    to_dto: Callable[[Any], Any]


_RECIPES = _WishList("recipes", "recipes", "Recipe", to_recipe_summary)
_INGREDIENTS = _WishList("ingredients", "plants", "Ingredient", to_ingredient)


class UserService(CrudService):
    _label = "User"
    _repository = "users"
    _model = User
    _to_dto = staticmethod(to_user)
    _to_list_dto = staticmethod(to_user)

    # ---------------------------------------------------------------- CRUD
    def create(
        self,
        user_name: str,
        email: str,
        password: str,
        alias: Optional[str] = None,
        phone: Optional[str] = None,
        profile: Optional[dict] = None,
    ) -> UserDTO:
        with self._uow_factory() as uow:
            self._ensure_email_is_free(uow, email)
            user = User(
                user_name=user_name,
                email=email,
                password=hash_password(password),
                alias=alias,
                phone=phone,
            )
            if profile:
                user.profile = UserProfile(**profile)
            uow.users.add(user)
            uow.flush()
            return to_user(user)

    def _apply_changes(self, uow: Any, user: User, changes: dict) -> None:
        changes = dict(changes)
        profile = changes.pop("profile", None)
        if "email" in changes:
            self._ensure_email_is_free(uow, changes["email"], user.id)
        if "password" in changes:
            changes["password"] = hash_password(changes["password"])
        super()._apply_changes(uow, user, changes)
        if profile:
            self._update_profile(user, profile)

    @staticmethod
    def _update_profile(user: User, profile: dict) -> None:
        if user.profile is None:
            user.profile = UserProfile(**profile)
            return
        for name, value in profile.items():
            setattr(user.profile, name, value)

    @staticmethod
    def _ensure_email_is_free(
        uow: Any, email: str, own_id: Optional[int] = None
    ) -> None:
        other = uow.users.get_by_email(email)
        if other is not None and other.id != own_id:
            raise AlreadyExistsError(
                f"A user with email '{email}' already exists"
            )

    # ----------------------------------------------------------- wish lists
    def add_wish_recipe(self, user_id: int, recipe_id: int) -> None:
        self._add_to_wish_list(_RECIPES, user_id, recipe_id)

    def remove_wish_recipe(self, user_id: int, recipe_id: int) -> None:
        self._remove_from_wish_list(_RECIPES, user_id, recipe_id)

    def list_wish_recipes(self, user_id: int) -> list[RecipeSummaryDTO]:
        return self._list_wish_list(_RECIPES, user_id)

    def add_wish_ingredient(self, user_id: int, ingredient_id: int) -> None:
        self._add_to_wish_list(_INGREDIENTS, user_id, ingredient_id)

    def remove_wish_ingredient(self, user_id: int, ingredient_id: int) -> None:
        self._remove_from_wish_list(_INGREDIENTS, user_id, ingredient_id)

    def list_wish_ingredients(self, user_id: int) -> list[IngredientDTO]:
        return self._list_wish_list(_INGREDIENTS, user_id)

    def _add_to_wish_list(
        self, wish_list: _WishList, user_id: int, item_id: int
    ) -> None:
        with self._uow_factory() as uow:
            user = self._find(uow, user_id)
            repository = getattr(uow, wish_list.repository)
            item = get_or_raise(repository, item_id, wish_list.label)
            items = getattr(user, wish_list.collection)
            if item in items:
                raise AlreadyExistsError(
                    f"{wish_list.label} {item_id} is already in the "
                    f"wish list of user {user_id}"
                )
            items.append(item)

    def _remove_from_wish_list(
        self, wish_list: _WishList, user_id: int, item_id: int
    ) -> None:
        with self._uow_factory() as uow:
            user = self._find(uow, user_id)
            items = getattr(user, wish_list.collection)
            item = next((i for i in items if i.id == item_id), None)
            if item is None:
                raise NotFoundError(
                    f"{wish_list.label} {item_id} is not in the "
                    f"wish list of user {user_id}"
                )
            items.remove(item)

    def _list_wish_list(self, wish_list: _WishList, user_id: int) -> list:
        with self._uow_factory() as uow:
            user = self._find(uow, user_id)
            items = getattr(user, wish_list.collection)
            return [wish_list.to_dto(i) for i in items]
