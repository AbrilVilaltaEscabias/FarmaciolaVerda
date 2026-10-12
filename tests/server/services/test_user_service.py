import pytest

from src.common.dto import UserDTO
from src.server.domain.exceptions import AlreadyExistsError, NotFoundError
from src.server.domain.model import Ingredient, Recipe, User, UserProfile
from src.server.services.security import verify_password
from src.server.services.user_service import UserService


def make_user(user_id=1, **overrides) -> User:
    fields = {"id": user_id, "user_name": "ana", "email": "a@x.com",
              "password": "hash"}
    return User(**{**fields, **overrides})


@pytest.fixture
def service(uow_factory):
    return UserService(uow_factory)


class TestCreate:
    def test_password_is_hashed_and_never_returned(self, service, uow):
        uow.users.get_by_email.return_value = None

        result = service.create("ana", "a@x.com", "secret")

        stored = uow.users.add.call_args.args[0]
        assert stored.password != "secret"
        assert verify_password("secret", stored.password)
        assert isinstance(result, UserDTO)
        assert "password" not in result.to_dict()

    def test_profile_is_created_with_the_user(self, service, uow):
        uow.users.get_by_email.return_value = None
        result = service.create("ana", "a@x.com", "pw",
                                profile={"bio": "hi", "country": "ES"})
        assert result.profile.bio == "hi" and result.profile.country == "ES"

    def test_duplicated_email_is_a_conflict(self, service, uow):
        uow.users.get_by_email.return_value = make_user()
        with pytest.raises(AlreadyExistsError):
            service.create("bob", "a@x.com", "pw")
        uow.users.add.assert_not_called()


class TestReadUpdateDelete:
    def test_get_unknown_user_fails(self, service, uow):
        uow.users.get.return_value = None
        with pytest.raises(NotFoundError, match="User 5"):
            service.get(5)

    def test_update_only_changes_the_given_fields(self, service, uow):
        uow.users.get.return_value = make_user(alias="old")
        result = service.update(1, alias="new")
        assert result.alias == "new" and result.user_name == "ana"

    def test_update_hashes_a_new_password(self, service, uow):
        user = make_user()
        uow.users.get.return_value = user
        service.update(1, password="new-secret")
        assert verify_password("new-secret", user.password)

    def test_update_creates_the_profile_if_missing(self, service, uow):
        uow.users.get.return_value = make_user()
        result = service.update(1, profile={"country": "ES"})
        assert result.profile.country == "ES"

    def test_update_changes_the_existing_profile(self, service, uow):
        uow.users.get.return_value = make_user(
            profile=UserProfile(bio="hi", country="FR"))
        result = service.update(1, profile={"country": "ES"})
        assert result.profile.country == "ES" and result.profile.bio == "hi"

    def test_update_to_the_email_of_another_user_fails(self, service, uow):
        uow.users.get.return_value = make_user(1)
        uow.users.get_by_email.return_value = make_user(2, email="b@x.com")
        with pytest.raises(AlreadyExistsError):
            service.update(1, email="b@x.com")

    def test_update_keeping_the_own_email_is_fine(self, service, uow):
        uow.users.get.return_value = make_user(1)
        uow.users.get_by_email.return_value = make_user(1)
        assert service.update(1, email="a@x.com").email == "a@x.com"

    def test_delete_unknown_user_fails(self, service, uow):
        uow.users.get.return_value = None
        with pytest.raises(NotFoundError):
            service.delete(5)
        uow.users.delete.assert_not_called()

    def test_list_all(self, service, uow):
        uow.users.get_all.return_value = [make_user(1), make_user(2)]
        assert [u.id for u in service.list_all()] == [1, 2]


class TestWishLists:
    @pytest.fixture
    def user(self, uow):
        user = make_user()
        uow.users.get.return_value = user
        return user

    def test_add_recipe(self, service, uow, user):
        recipe = Recipe(id=5, name="Tea", step_by_step="Boil")
        uow.recipes.get.return_value = recipe
        service.add_wish_recipe(1, 5)
        assert user.recipes == [recipe]

    def test_add_recipe_twice_is_a_conflict(self, service, uow, user):
        recipe = Recipe(id=5, name="Tea", step_by_step="Boil")
        user.recipes.append(recipe)
        uow.recipes.get.return_value = recipe
        with pytest.raises(AlreadyExistsError):
            service.add_wish_recipe(1, 5)

    def test_add_unknown_recipe_fails(self, service, uow, user):
        uow.recipes.get.return_value = None
        with pytest.raises(NotFoundError, match="Recipe 5"):
            service.add_wish_recipe(1, 5)

    def test_add_recipe_for_unknown_user_fails(self, service, uow):
        uow.users.get.return_value = None
        with pytest.raises(NotFoundError, match="User 1"):
            service.add_wish_recipe(1, 5)

    def test_remove_recipe(self, service, user):
        user.recipes.append(Recipe(id=5, name="Tea", step_by_step="Boil"))
        service.remove_wish_recipe(1, 5)
        assert user.recipes == []

    def test_remove_recipe_not_in_the_list_fails(self, service, user):
        with pytest.raises(NotFoundError):
            service.remove_wish_recipe(1, 5)

    def test_list_recipes_returns_summaries(self, service, user):
        user.recipes.append(Recipe(id=5, name="Tea", step_by_step="Boil",
                                   duration=10))
        (item,) = service.list_wish_recipes(1)
        assert item.to_dict() == {"id": 5, "name": "Tea", "duration": 10}

    def test_ingredient_wish_list_works_the_same_way(self, service, uow, user):
        mint = Ingredient(id=2, common_name="Mint", type="herb")
        uow.ingredients.get.return_value = mint
        service.add_wish_ingredient(1, 2)
        names = [i.common_name for i in service.list_wish_ingredients(1)]
        assert names == ["Mint"]
        service.remove_wish_ingredient(1, 2)
        assert user.plants == []
