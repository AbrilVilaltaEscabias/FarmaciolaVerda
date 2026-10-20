"""
Validació de peticions, de punta a punta (router + serveis amb BD falsa).

Cobreix tots els casos d'`INVALID_DATA` i `UNKNOWN_COMMAND` del README.
"""
import pytest

from common import protocol

INVALID = protocol.INVALID_DATA


def assert_error(resp, code, message=None):
    assert resp["status"] == protocol.ERROR
    assert resp["error"] == code
    if message is not None:
        assert resp["message"] == message


# ---------------------------------------------------- sobre del missatge

class TestMalformedEnvelope:
    @pytest.mark.parametrize("line", [
        b"aixo no es json\n",
        b"{not json}\n",
        b'{"command": "LIST"\n',          # JSON truncat
        b"\n",
        b"",
        b"   \n",
        b"\xff\xfe\xfd\n",                 # no és UTF-8
    ])
    def test_not_valid_json(self, send_raw, line):
        assert_error(send_raw(line), INVALID, "Missatge mal format")

    @pytest.mark.parametrize("line", [
        b"[1, 2, 3]\n", b'"LIST"\n', b"42\n", b"null\n", b"true\n",
    ])
    def test_json_that_is_not_an_object(self, send_raw, line):
        assert_error(send_raw(line), INVALID, "Missatge mal format")

    @pytest.mark.parametrize("line", [
        b"{}\n",
        b'{"data": {"resource": "recipe"}}\n',
        b'{"cmd": "LIST"}\n',
        b'{"COMMAND": "LIST"}\n',
    ])
    def test_missing_command_field(self, send_raw, line):
        assert_error(send_raw(line), INVALID, "Missatge mal format")

    @pytest.mark.parametrize("data", ['"text"', "[1, 2]", "42", "true"])
    def test_data_must_be_an_object(self, send_raw, data):
        line = f'{{"command": "LIST", "data": {data}}}\n'.encode()
        assert_error(send_raw(line), INVALID, "Missatge mal format")

    def test_valid_envelope_is_accepted(self, send_raw):
        resp = send_raw(b'{"command": "LIST", "data": {"resource": "recipe"}}\n')
        assert resp["status"] == protocol.OK

    def test_extra_top_level_fields_are_ignored(self, send_raw):
        line = b'{"command": "LIST", "data": {"resource": "recipe"}, "extra": 1}\n'
        assert send_raw(line)["status"] == protocol.OK

    def test_extra_data_fields_are_ignored(self, send):
        resp = send("LIST", {"resource": "recipe", "unexpected": True})
        assert resp["status"] == protocol.OK


# ---------------------------------------------------------- comanda

class TestCommand:
    @pytest.mark.parametrize("command", [
        "DANCE", "list", "Show", "", " LIST", "LIST ", "DROP TABLE", "CREATE_USER",
    ])
    def test_unknown_command(self, send, command):
        assert_error(send(command, {"resource": "recipe"}), protocol.UNKNOWN_COMMAND,
                     f"Comanda desconeguda: {command}")

    @pytest.mark.parametrize("raw", ["null", "123", "true", "[]", '["LIST"]', "{}", '{"a": 1}'])
    def test_non_string_command_is_malformed(self, send_raw, raw):
        """Un `command` que no és text és un missatge mal format.
        (Abans, [] o {} feien caure el servidor amb un TypeError.)"""
        line = f'{{"command": {raw}, "data": {{}}}}\n'.encode()
        assert_error(send_raw(line), INVALID, "Missatge mal format")

# ------------------------------------------------ camps obligatoris de data

class TestMissingDataFields:
    @pytest.mark.parametrize("command, data, field", [
        ("LIST", {}, "resource"),
        ("SHOW", {"id": 1}, "resource"),
        ("SHOW", {"resource": "recipe"}, "id"),
        ("CREATE", {"values": {}}, "resource"),
        ("CREATE", {"resource": "recipe"}, "values"),
        ("UPDATE", {"id": 1, "values": {}}, "resource"),
        ("UPDATE", {"resource": "recipe", "values": {}}, "id"),
        ("UPDATE", {"resource": "recipe", "id": 1}, "values"),
        ("DELETE", {"id": 1}, "resource"),
        ("DELETE", {"resource": "recipe"}, "id"),
    ])
    def test_missing_field(self, send, command, data, field):
        assert_error(send(command, data), INVALID, f"Falta el camp '{field}'")

    @pytest.mark.parametrize("command", ["LIST", "SHOW", "CREATE", "UPDATE", "DELETE"])
    def test_no_data_at_all(self, send, command):
        resp = send(command)
        assert_error(resp, INVALID)
        assert resp["message"].startswith("Falta el camp")

    def test_readme_example(self, send):
        assert send("SHOW", {"resource": "recipe"}) == {
            "status": "ERROR", "error": "INVALID_DATA",
            "message": "Falta el camp 'id'"}

    def test_page_and_filter_are_optional(self, send):
        assert send("LIST", {"resource": "recipe"})["status"] == protocol.OK


# ----------------------------------------------------------- recurs

class TestResource:
    @pytest.mark.parametrize("resource", [
        "nope", "", "Recipe", "RECIPE", "recipes", "wishlist", "user_profile",
    ])
    @pytest.mark.parametrize("command, extra", [
        ("LIST", {}),
        ("SHOW", {"id": 1}),
        ("CREATE", {"values": {"name": "x"}}),
        ("UPDATE", {"id": 1, "values": {}}),
        ("DELETE", {"id": 1}),
    ])
    def test_unknown_resource_in_every_command(self, send, command, extra, resource):
        assert_error(send(command, {"resource": resource, **extra}), INVALID,
                     f"Recurs desconegut: {resource}")

    @pytest.mark.parametrize("resource", ["recipe", "ingredient", "category", "user"])
    def test_known_resources_are_accepted(self, send, resource):
        assert send("LIST", {"resource": resource})["status"] == protocol.OK

    def test_non_string_resource_is_rejected_not_crashed(self, send):
        # Un `resource` numèric o null no és un recurs conegut.
        assert_error(send("LIST", {"resource": 5}), INVALID)
        assert_error(send("LIST", {"resource": None}), INVALID)


# --------------------------------------- camps obligatoris en CREATE

class TestCreateRequiredFields:
    @pytest.mark.parametrize("resource, required", [
        ("recipe", ["name", "step_by_step"]),
        ("ingredient", ["common_name", "type"]),
        ("category", ["name"]),
        ("user", ["user_name", "email", "password"]),
    ])
    def test_nothing_provided_lists_all_required(self, send, resource, required):
        resp = send("CREATE", {"resource": resource, "values": {}})
        assert_error(resp, INVALID, "Falten camps obligatoris: " + ", ".join(required))

    def test_readme_example(self, send):
        assert send("CREATE", {"resource": "recipe",
                               "values": {"name": "Sense passos"}}) == {
            "status": "ERROR", "error": "INVALID_DATA",
            "message": "Falten camps obligatoris: step_by_step"}

    @pytest.mark.parametrize("empty", [None, ""])
    def test_empty_values_count_as_missing(self, send, empty):
        resp = send("CREATE", {"resource": "recipe",
                               "values": {"name": "A", "step_by_step": empty}})
        assert_error(resp, INVALID, "Falten camps obligatoris: step_by_step")

    def test_optional_fields_alone_are_not_enough(self, send):
        resp = send("CREATE", {"resource": "recipe", "values": {"duration": 5}})
        assert_error(resp, INVALID)

    def test_valid_values_are_accepted(self, send):
        resp = send("CREATE", {"resource": "recipe",
                               "values": {"name": "A", "step_by_step": "x"}})
        assert resp["status"] == protocol.OK

    def test_unknown_keys_do_not_satisfy_required_fields(self, send):
        resp = send("CREATE", {"resource": "category", "values": {"nom": "A"}})
        assert_error(resp, INVALID)

    def test_validation_error_creates_nothing(self, send, db):
        send("CREATE", {"resource": "user", "values": {"user_name": "a"}})
        assert db.tables["users"] == {}


# -------------------------------------------------- ids inexistents

class TestIdsThatDoNotExist:
    @pytest.mark.parametrize("command, extra", [
        ("SHOW", {}), ("UPDATE", {"values": {"name": "x"}}), ("DELETE", {}),
    ])
    def test_not_found(self, send, command, extra):
        resp = send(command, {"resource": "category", "id": 42, **extra})
        assert_error(resp, protocol.NOT_FOUND, "category amb id 42 no existeix")


# -------------------------------- UPDATE: camps editables / ignorats

class TestUpdateValidation:
    def test_non_editable_fields_are_silently_ignored(self, send):
        rid = send("CREATE", {"resource": "recipe", "values": {
            "name": "A", "step_by_step": "x"}})["data"]["id"]
        resp = send("UPDATE", {"resource": "recipe", "id": rid, "values": {
            "id": 999, "created_at": "1999-01-01T00:00:00", "name": "B"}})
        assert resp["status"] == protocol.OK
        assert resp["data"]["id"] == rid
        assert resp["data"]["name"] == "B"
        assert not resp["data"]["created_at"].startswith("1999")


# ------------------------------------------- BUGS CONEGUTS (xfail strict)

class TestValuesMustBeAnObject:
    """`values` ha de ser un objecte JSON; altrament, INVALID_DATA."""

    @pytest.mark.parametrize("values", ["text", [1, 2], 42])
    def test_create(self, send, values):
        resp = send("CREATE", {"resource": "category", "values": values})
        assert_error(resp, INVALID, "values ha de ser un objecte")

    @pytest.mark.parametrize("values", ["text", [1, 2], 42])
    def test_update(self, send, values):
        cid = send("CREATE", {"resource": "category",
                              "values": {"name": "A"}})["data"]["id"]
        resp = send("UPDATE", {"resource": "category", "id": cid, "values": values})
        assert_error(resp, INVALID, "values ha de ser un objecte")
