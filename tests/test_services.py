"""Lògica de la capa de serveis (server/service_layer/services.py)."""
import hashlib
from datetime import datetime

import pytest

from common import protocol
from server.domain import Category, Ingredient, Recipe, User
from server.domain.exceptions import AlreadyExists, NotFound
from server.service_layer import services
from tests.fakes import FakeUnitOfWork


# ------------------------------------------------------------------ helpers

def seed(db, table, *objs):
    """Insereix objectes directament a la BD falsa i els hi assigna id."""
    for o in objs:
        o.id = db.next_id[table]
        db.next_id[table] += 1
        db.tables[table][o.id] = o
    return objs


def make_recipe(name="Camamilla", **kw):
    kw.setdefault("step_by_step", "Bullir aigua")
    return Recipe(name, **kw)


def fresh(db):
    """Un UoW nou sobre la mateixa BD (com una petició nova)."""
    return FakeUnitOfWork(db)


# --------------------------------------------------------------- auxiliars

class TestConfig:
    @pytest.mark.parametrize("resource", ["recipe", "ingredient", "category", "user"])
    def test_known_resources(self, resource):
        assert services._config(resource) is services.RESOURCES[resource]

    @pytest.mark.parametrize("resource", ["", "recipes", "Recipe", "wishlist", None])
    def test_unknown_resource_raises_valueerror(self, resource):
        with pytest.raises(ValueError, match="Recurs desconegut"):
            services._config(resource)

    def test_password_is_never_in_returned_fields(self):
        for cfg in services.RESOURCES.values():
            assert "password" not in cfg["fields"]

    def test_editable_and_required_are_subsets_of_model_args(self):
        # Coherència interna: no es pot demanar un camp que el model no accepta.
        for name, cfg in services.RESOURCES.items():
            sample = {f: "x" for f in set(cfg["required"]) | set(cfg["editable"])}
            cfg["model"](**sample)  # no ha de fallar


class TestToDict:
    def test_only_requested_fields(self):
        r = make_recipe(duration=10)
        r.id = 1
        assert set(services._to_dict(r, ["id", "name"])) == {"id", "name"}

    def test_datetime_becomes_iso_string(self):
        r = make_recipe(created_at=datetime(2026, 10, 20, 9, 31, 10, 557495))
        out = services._to_dict(r, ["created_at"])
        assert out["created_at"] == "2026-10-20T09:31:10.557495"

    def test_none_is_preserved(self):
        assert services._to_dict(make_recipe(), ["note"]) == {"note": None}

    def test_result_is_serializable_by_the_protocol(self):
        r = make_recipe(created_at=datetime(2026, 1, 2, 3, 4, 5), duration=5)
        r.id = 9
        out = services._to_dict(r, services.RESOURCES["recipe"]["fields"])
        parsed = protocol.parse_message(protocol.build_ok(out))
        assert parsed["data"]["created_at"] == "2026-01-02T03:04:05"
        assert parsed["data"]["id"] == 9


class TestHashPassword:
    def test_format_is_salt_dollar_digest(self):
        salt, digest = services._hash_password("1234").split("$")
        assert len(bytes.fromhex(salt)) == 16
        assert len(bytes.fromhex(digest)) == 32       # sha256

    def test_hash_is_verifiable_with_pbkdf2(self):
        salt, digest = services._hash_password("secret").split("$")
        expected = hashlib.pbkdf2_hmac(
            "sha256", b"secret", bytes.fromhex(salt), 100_000).hex()
        assert digest == expected

    def test_plain_password_not_in_output(self):
        assert "secret" not in services._hash_password("secret")

    def test_same_password_gets_different_salts(self):
        assert services._hash_password("x") != services._hash_password("x")

    def test_deterministic_with_fixed_salt(self, monkeypatch):
        monkeypatch.setattr(services.os, "urandom", lambda n: b"\x01" * n)
        assert services._hash_password("x") == services._hash_password("x")


class TestGetOrFail:
    def test_returns_object(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe())
        assert services._get_or_fail(uow.recipes, "recipe", r.id) is r

    def test_missing_raises_notfound_with_message(self, uow):
        with pytest.raises(NotFound, match="recipe amb id 99 no existeix"):
            services._get_or_fail(uow.recipes, "recipe", 99)


# ----------------------------------------------------------- list_resources

class TestListResources:
    def test_empty(self, uow):
        assert services.list_resources(uow, "recipe") == []

    def test_returns_dicts_with_configured_fields(self, db, uow):
        seed(db, "recipes", make_recipe("A", duration=5))
        (item,) = services.list_resources(uow, "recipe")
        assert set(item) == set(services.RESOURCES["recipe"]["fields"])
        assert item["name"] == "A" and item["duration"] == 5

    @pytest.mark.parametrize("resource, table, obj", [
        ("ingredient", "ingredients", lambda: Ingredient("Menta", "leaf")),
        ("category", "categories", lambda: Category("Tisanes")),
        ("user", "users", lambda: User("anna", "a@x.com", "hash")),
    ])
    def test_other_resources(self, db, uow, resource, table, obj):
        seed(db, table, obj())
        items = services.list_resources(uow, resource)
        assert len(items) == 1
        assert set(items[0]) == set(services.RESOURCES[resource]["fields"])

    def test_users_never_expose_password(self, db, uow):
        seed(db, "users", User("anna", "a@x.com", "SECRET-HASH"))
        (item,) = services.list_resources(uow, "user")
        assert "password" not in item
        assert "SECRET-HASH" not in str(item)

    def test_filter_by_category(self, db, uow):
        tea = Category("Tisanes")
        a, b, c = make_recipe("A"), make_recipe("B"), make_recipe("C")
        a.categories.append(tea)
        b.categories.append(tea)
        seed(db, "recipes", a, b, c)
        items = services.list_resources(uow, "recipe", {"category": "Tisanes"})
        assert {i["name"] for i in items} == {"A", "B"}

    def test_filter_by_name(self, db, uow):
        seed(db, "recipes", make_recipe("A"), make_recipe("B"))
        items = services.list_resources(uow, "recipe", {"name": "B"})
        assert [i["name"] for i in items] == ["B"]

    def test_filter_without_matches_is_empty_list(self, db, uow):
        seed(db, "recipes", make_recipe("A"))
        assert services.list_resources(uow, "recipe", {"name": "zzz"}) == []

    def test_category_filter_has_priority_over_name(self, db, uow):
        tea = Category("Tisanes")
        a, b = make_recipe("A"), make_recipe("B")
        a.categories.append(tea)
        seed(db, "recipes", a, b)
        items = services.list_resources(
            uow, "recipe", {"category": "Tisanes", "name": "B"})
        assert [i["name"] for i in items] == ["A"]

    def test_pagination(self, db, uow):
        seed(db, "recipes", *[make_recipe(f"R{i}") for i in range(5)])
        p1 = services.list_resources(uow, "recipe", page=1, page_size=2)
        p2 = services.list_resources(fresh(db), "recipe", page=2, page_size=2)
        p3 = services.list_resources(fresh(db), "recipe", page=3, page_size=2)
        assert [i["name"] for i in p1] == ["R0", "R1"]
        assert [i["name"] for i in p2] == ["R2", "R3"]
        assert [i["name"] for i in p3] == ["R4"]

    def test_pagination_default_page_size_is_10(self, db, uow):
        seed(db, "recipes", *[make_recipe(f"R{i:02}") for i in range(12)])
        assert len(services.list_resources(uow, "recipe", page=1)) == 10

    def test_page_beyond_the_end_is_empty(self, db, uow):
        seed(db, "recipes", make_recipe("A"))
        assert services.list_resources(uow, "recipe", page=5, page_size=10) == []

    def test_filter_disables_pagination(self, db, uow):
        seed(db, "recipes", *[make_recipe("same") for _ in range(4)])
        items = services.list_resources(
            uow, "recipe", {"name": "same"}, page=1, page_size=2)
        assert len(items) == 4

    def test_without_page_returns_everything(self, db, uow):
        seed(db, "recipes", *[make_recipe(f"R{i}") for i in range(15)])
        assert len(services.list_resources(uow, "recipe", page_size=2)) == 15

    def test_filter_and_page_are_ignored_for_other_resources(self, db, uow):
        seed(db, "categories", Category("A"), Category("B"), Category("C"))
        items = services.list_resources(
            uow, "category", {"name": "A"}, page=1, page_size=1)
        assert len(items) == 3

    def test_unknown_resource(self, uow):
        with pytest.raises(ValueError):
            services.list_resources(uow, "nope")

    def test_commits_and_does_not_roll_back(self, uow):
        services.list_resources(uow, "recipe")
        assert uow.committed and not uow.rolled_back


# ------------------------------------------------------------ show_resource

class TestShowResource:
    def test_returns_item(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe("A", note="n"))
        out = services.show_resource(uow, "recipe", r.id)
        assert out["id"] == r.id and out["name"] == "A" and out["note"] == "n"

    def test_not_found(self, uow):
        with pytest.raises(NotFound, match="recipe amb id 99 no existeix"):
            services.show_resource(uow, "recipe", 99)

    def test_not_found_rolls_back(self, uow):
        with pytest.raises(NotFound):
            services.show_resource(uow, "recipe", 1)
        assert uow.rolled_back and not uow.committed

    def test_unknown_resource(self, uow):
        with pytest.raises(ValueError):
            services.show_resource(uow, "nope", 1)

    def test_user_hides_password(self, db, uow):
        (u,) = seed(db, "users", User("anna", "a@x.com", "HASH"))
        assert "password" not in services.show_resource(uow, "user", u.id)

    def test_resources_do_not_leak_between_tables(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe())
        with pytest.raises(NotFound):
            services.show_resource(uow, "category", r.id)


# ---------------------------------------------------------- create_resource

class TestCreateResource:
    def test_recipe_gets_id_and_is_stored(self, db, uow):
        out = services.create_resource(
            uow, "recipe", {"name": "Camamilla", "step_by_step": "Bullir"})
        assert out["id"] == 1
        assert out["name"] == "Camamilla"
        assert 1 in db.tables["recipes"]

    def test_commits(self, uow):
        services.create_resource(uow, "category", {"name": "Tisanes"})
        assert uow.committed and not uow.rolled_back

    def test_flush_is_called_so_the_id_is_available(self, uow):
        services.create_resource(uow, "category", {"name": "Tisanes"})
        assert uow.session.flush_count == 1

    def test_ids_increment(self, db):
        a = services.create_resource(fresh(db), "category", {"name": "A"})
        b = services.create_resource(fresh(db), "category", {"name": "B"})
        assert (a["id"], b["id"]) == (1, 2)

    def test_recipe_created_at_is_set_by_server(self, uow):
        before = datetime.now()
        out = services.create_resource(
            uow, "recipe", {"name": "A", "step_by_step": "x"})
        created = datetime.fromisoformat(out["created_at"])
        assert before <= created <= datetime.now()

    def test_client_cannot_set_created_at(self, uow):
        out = services.create_resource(uow, "recipe", {
            "name": "A", "step_by_step": "x", "created_at": "1999-01-01T00:00:00"})
        assert not out["created_at"].startswith("1999")

    def test_client_cannot_set_id(self, uow):
        out = services.create_resource(uow, "category", {"name": "A", "id": 500})
        assert out["id"] == 1

    def test_unknown_keys_are_ignored(self, uow):
        out = services.create_resource(
            uow, "category", {"name": "A", "hacker": "yes", "recipes": [1]})
        assert out == {"id": 1, "name": "A", "description": None}

    def test_optional_fields_are_stored(self, uow):
        out = services.create_resource(uow, "ingredient", {
            "common_name": "Camamilla", "type": "flower", "family": "Asteraceae"})
        assert out["family"] == "Asteraceae" and out["image_url"] is None

    @pytest.mark.parametrize("resource, values, missing", [
        ("recipe", {"name": "A"}, "step_by_step"),
        ("recipe", {"step_by_step": "x"}, "name"),
        ("ingredient", {"common_name": "A"}, "type"),
        ("ingredient", {"type": "leaf"}, "common_name"),
        ("category", {}, "name"),
        ("category", {"description": "d"}, "name"),
        ("user", {"user_name": "a", "email": "e"}, "password"),
        ("user", {"user_name": "a", "password": "p"}, "email"),
        ("user", {"email": "e", "password": "p"}, "user_name"),
    ])
    def test_missing_required_field(self, uow, resource, values, missing):
        with pytest.raises(ValueError, match=f"Falten camps obligatoris: .*{missing}"):
            services.create_resource(uow, resource, values)

    @pytest.mark.parametrize("empty", [None, ""])
    def test_empty_required_field_counts_as_missing(self, uow, empty):
        with pytest.raises(ValueError, match="name"):
            services.create_resource(uow, "category", {"name": empty})

    def test_all_missing_fields_are_listed(self, uow):
        with pytest.raises(ValueError) as exc:
            services.create_resource(uow, "user", {})
        assert str(exc.value) == (
            "Falten camps obligatoris: user_name, email, password")

    def test_validation_failure_stores_nothing(self, db, uow):
        with pytest.raises(ValueError):
            services.create_resource(uow, "recipe", {"name": "A"})
        assert db.tables["recipes"] == {}

    def test_unknown_resource(self, uow):
        with pytest.raises(ValueError, match="Recurs desconegut"):
            services.create_resource(uow, "nope", {"name": "x"})

    # -- usuaris

    USER = {"user_name": "anna", "email": "anna@mail.com", "password": "1234"}

    def test_user_response_has_no_password(self, uow):
        out = services.create_resource(uow, "user", dict(self.USER))
        assert "password" not in out
        assert out["email"] == "anna@mail.com"

    def test_user_password_is_hashed_in_storage(self, db, uow):
        services.create_resource(uow, "user", dict(self.USER))
        stored = db.tables["users"][1].password
        assert stored != "1234"
        assert "$" in stored

    def test_user_does_not_mutate_callers_values(self, uow):
        values = dict(self.USER)
        services.create_resource(uow, "user", values)
        assert values["password"] == "1234"

    def test_duplicate_email_raises_already_exists(self, db):
        services.create_resource(fresh(db), "user", dict(self.USER))
        with pytest.raises(AlreadyExists, match="Aquest email ja existeix"):
            services.create_resource(
                fresh(db), "user", {**self.USER, "user_name": "altre"})
        assert len(db.tables["users"]) == 1

    def test_duplicate_email_rolls_back(self, db):
        services.create_resource(fresh(db), "user", dict(self.USER))
        uow2 = fresh(db)
        with pytest.raises(AlreadyExists):
            services.create_resource(uow2, "user", dict(self.USER))
        assert uow2.rolled_back and not uow2.committed

    def test_different_emails_are_allowed(self, db):
        services.create_resource(fresh(db), "user", dict(self.USER))
        services.create_resource(
            fresh(db), "user", {**self.USER, "email": "b@mail.com"})
        assert len(db.tables["users"]) == 2

    def test_same_user_name_is_allowed(self, db):
        """Només l'email ha de ser únic."""
        services.create_resource(fresh(db), "user", dict(self.USER))
        services.create_resource(
            fresh(db), "user", {**self.USER, "email": "b@mail.com"})
        assert len(db.tables["users"]) == 2


# ---------------------------------------------------------- update_resource

class TestUpdateResource:
    def test_updates_given_fields_only(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe("A", duration=5, note="keep"))
        out = services.update_resource(uow, "recipe", r.id, {"duration": 15})
        assert out["duration"] == 15
        assert out["name"] == "A" and out["note"] == "keep"

    def test_change_is_persisted(self, db):
        (r,) = seed(db, "recipes", make_recipe("A"))
        services.update_resource(fresh(db), "recipe", r.id, {"name": "B"})
        assert db.tables["recipes"][r.id].name == "B"

    def test_commits(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe())
        services.update_resource(uow, "recipe", r.id, {"name": "B"})
        assert uow.committed

    def test_can_set_field_to_none(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe(note="x"))
        out = services.update_resource(uow, "recipe", r.id, {"note": None})
        assert out["note"] is None

    @pytest.mark.parametrize("field, value", [
        ("id", 999), ("created_at", datetime(1999, 1, 1)), ("hacker", 1),
    ])
    def test_non_editable_recipe_fields_are_ignored(self, db, uow, field, value):
        (r,) = seed(db, "recipes", make_recipe("A", created_at=datetime(2026, 1, 1)))
        out = services.update_resource(uow, "recipe", r.id, {field: value, "name": "B"})
        assert out["id"] == r.id
        assert out["created_at"] == "2026-01-01T00:00:00"
        assert out["name"] == "B"                    # la resta sí s'aplica
        assert not hasattr(r, "hacker")

    def test_user_password_cannot_be_changed_through_update(self, db, uow):
        (u,) = seed(db, "users", User("anna", "a@x.com", "HASH"))
        services.update_resource(
            uow, "user", u.id, {"password": "new", "alias": "ann"})
        assert u.password == "HASH"
        assert u.alias == "ann"

    def test_empty_values_changes_nothing(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe("A"))
        out = services.update_resource(uow, "recipe", r.id, {})
        assert out["name"] == "A"

    def test_not_found(self, uow):
        with pytest.raises(NotFound, match="recipe amb id 5 no existeix"):
            services.update_resource(uow, "recipe", 5, {"name": "x"})

    def test_not_found_rolls_back(self, uow):
        with pytest.raises(NotFound):
            services.update_resource(uow, "recipe", 5, {"name": "x"})
        assert uow.rolled_back

    def test_unknown_resource(self, uow):
        with pytest.raises(ValueError):
            services.update_resource(uow, "nope", 1, {})

    def test_failure_midway_rolls_back_earlier_changes(self, db):
        """Si una petició falla, no queden canvis a mig fer."""
        (r,) = seed(db, "recipes", make_recipe("A"))

        class Values(dict):
            def items(self):
                yield "name", "CHANGED"
                raise RuntimeError("boom")

        uow = fresh(db)
        with pytest.raises(RuntimeError):
            services.update_resource(uow, "recipe", r.id, Values())
        assert uow.rolled_back
        assert db.tables["recipes"][r.id].name == "A"


# ---------------------------------------------------------- delete_resource

class TestDeleteResource:
    def test_deletes(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe())
        services.delete_resource(uow, "recipe", r.id)
        assert db.tables["recipes"] == {}

    def test_returns_none(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe())
        assert services.delete_resource(uow, "recipe", r.id) is None

    def test_commits(self, db, uow):
        (r,) = seed(db, "recipes", make_recipe())
        services.delete_resource(uow, "recipe", r.id)
        assert uow.committed

    def test_only_target_is_deleted(self, db, uow):
        a, b = seed(db, "recipes", make_recipe("A"), make_recipe("B"))
        services.delete_resource(uow, "recipe", a.id)
        assert list(db.tables["recipes"]) == [b.id]

    def test_not_found(self, uow):
        with pytest.raises(NotFound, match="recipe amb id 1 no existeix"):
            services.delete_resource(uow, "recipe", 1)

    def test_not_found_rolls_back(self, uow):
        with pytest.raises(NotFound):
            services.delete_resource(uow, "recipe", 1)
        assert uow.rolled_back

    def test_unknown_resource(self, uow):
        with pytest.raises(ValueError):
            services.delete_resource(uow, "nope", 1)

    def test_deleting_twice_fails_second_time(self, db):
        (r,) = seed(db, "recipes", make_recipe())
        services.delete_resource(fresh(db), "recipe", r.id)
        with pytest.raises(NotFound):
            services.delete_resource(fresh(db), "recipe", r.id)
