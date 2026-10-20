"""
Router (server/router.py): enrutament de comandes i traducció d'errors.

Aquí els SERVEIS estan mockejats: es comprova que el router passa bé els
arguments, empaqueta bé les respostes i tradueix cada excepció al codi
d'error correcte. (La integració router + serveis és a test_validation.py
i al final d'aquest fitxer.)
"""
from unittest.mock import MagicMock, sentinel

import pytest

from common import protocol
from server import router
from server.domain.exceptions import AlreadyExists, NotFound


@pytest.fixture
def services_mock(monkeypatch):
    mock = MagicMock(name="services")
    monkeypatch.setattr(router, "services", mock)
    monkeypatch.setattr(router, "_new_uow", lambda: sentinel.uow)
    return mock


def call(command, data=None):
    return protocol.parse_message(router.handle(protocol.build_request(command, data)))


# ------------------------------------------------------------- dispatch

class TestCommandTable:
    def test_has_the_five_commands(self):
        assert set(router.COMMANDS) == {"LIST", "SHOW", "CREATE", "UPDATE", "DELETE"}

    def test_each_command_maps_to_its_handler(self):
        assert router.COMMANDS[protocol.LIST] is router.handle_list
        assert router.COMMANDS[protocol.SHOW] is router.handle_show
        assert router.COMMANDS[protocol.CREATE] is router.handle_create
        assert router.COMMANDS[protocol.UPDATE] is router.handle_update
        assert router.COMMANDS[protocol.DELETE] is router.handle_delete

    def test_every_handler_is_callable(self):
        assert all(callable(f) for f in router.COMMANDS.values())


class TestHandle:
    def test_returns_bytes(self, services_mock):
        services_mock.list_resources.return_value = []
        assert isinstance(router.handle(b'{"command":"LIST","data":{"resource":"recipe"}}\n'), bytes)

    def test_dispatches_to_the_right_handler(self, services_mock, monkeypatch):
        fake = MagicMock(return_value=protocol.build_ok({"x": 1}))
        monkeypatch.setitem(router.COMMANDS, "SHOW", fake)
        out = call("SHOW", {"resource": "recipe", "id": 1})
        fake.assert_called_once_with({"resource": "recipe", "id": 1})
        assert out == {"status": "OK", "data": {"x": 1}}

    def test_missing_data_is_passed_as_empty_dict(self, monkeypatch):
        fake = MagicMock(return_value=protocol.build_ok())
        monkeypatch.setitem(router.COMMANDS, "LIST", fake)
        router.handle(b'{"command": "LIST"}\n')
        fake.assert_called_once_with({})

    @pytest.mark.parametrize("raw_data", ["null", "0", '""', "{}"])
    def test_falsy_data_is_passed_as_empty_dict(self, monkeypatch, raw_data):
        fake = MagicMock(return_value=protocol.build_ok())
        monkeypatch.setitem(router.COMMANDS, "LIST", fake)
        router.handle(f'{{"command": "LIST", "data": {raw_data}}}\n'.encode())
        fake.assert_called_once_with({})

    def test_command_is_case_sensitive(self, services_mock):
        out = call("list", {"resource": "recipe"})
        assert out["error"] == protocol.UNKNOWN_COMMAND
        services_mock.list_resources.assert_not_called()

    def test_unknown_command_message_names_the_command(self, services_mock):
        out = call("DANCE", {})
        assert out == {"status": "ERROR", "error": "UNKNOWN_COMMAND",
                       "message": "Comanda desconeguda: DANCE"}

    def test_unknown_command_never_reaches_services(self, services_mock):
        call("DANCE", {})
        assert services_mock.mock_calls == []

    def test_create_user_constant_is_not_routed(self, services_mock):
        """CREATE_USER existeix al protocol però no té handler."""
        assert call(protocol.CREATE_USER, {})["error"] == protocol.UNKNOWN_COMMAND


# ------------------------------------------------------------- handlers

class TestHandleList:
    def test_passes_all_arguments(self, services_mock):
        services_mock.list_resources.return_value = []
        call("LIST", {"resource": "recipe", "filter": {"category": "Tisanes"},
                      "page": 2, "page_size": 5})
        services_mock.list_resources.assert_called_once_with(
            sentinel.uow, "recipe", {"category": "Tisanes"}, 2, 5)

    def test_defaults(self, services_mock):
        services_mock.list_resources.return_value = []
        call("LIST", {"resource": "recipe"})
        services_mock.list_resources.assert_called_once_with(
            sentinel.uow, "recipe", None, None, 10)

    def test_wraps_result_in_items(self, services_mock):
        services_mock.list_resources.return_value = [{"id": 1}, {"id": 2}]
        assert call("LIST", {"resource": "recipe"}) == {
            "status": "OK", "data": {"items": [{"id": 1}, {"id": 2}]}}

    def test_empty_list_is_still_items(self, services_mock):
        services_mock.list_resources.return_value = []
        assert call("LIST", {"resource": "recipe"})["data"] == {"items": []}


class TestHandleShow:
    def test_passes_arguments_and_returns_item(self, services_mock):
        services_mock.show_resource.return_value = {"id": 3, "name": "A"}
        out = call("SHOW", {"resource": "recipe", "id": 3})
        services_mock.show_resource.assert_called_once_with(sentinel.uow, "recipe", 3)
        assert out == {"status": "OK", "data": {"id": 3, "name": "A"}}


class TestHandleCreate:
    def test_passes_arguments_and_returns_item(self, services_mock):
        services_mock.create_resource.return_value = {"id": 1, "name": "T"}
        out = call("CREATE", {"resource": "category", "values": {"name": "T"}})
        services_mock.create_resource.assert_called_once_with(
            sentinel.uow, "category", {"name": "T"})
        assert out == {"status": "OK", "data": {"id": 1, "name": "T"}}


class TestHandleUpdate:
    def test_passes_arguments_and_returns_item(self, services_mock):
        services_mock.update_resource.return_value = {"id": 1, "duration": 15}
        out = call("UPDATE", {"resource": "recipe", "id": 1, "values": {"duration": 15}})
        services_mock.update_resource.assert_called_once_with(
            sentinel.uow, "recipe", 1, {"duration": 15})
        assert out == {"status": "OK", "data": {"id": 1, "duration": 15}}


class TestHandleDelete:
    def test_passes_arguments_and_returns_empty_data(self, services_mock):
        out = call("DELETE", {"resource": "recipe", "id": 1})
        services_mock.delete_resource.assert_called_once_with(sentinel.uow, "recipe", 1)
        assert out == {"status": "OK", "data": {}}


class TestUowPerRequest:
    def test_a_new_uow_is_created_for_every_request(self, monkeypatch):
        created = []
        monkeypatch.setattr(router, "_new_uow", lambda: created.append(1) or object())
        monkeypatch.setattr(router, "services", MagicMock(list_resources=lambda *a: []))
        for _ in range(3):
            call("LIST", {"resource": "recipe"})
        assert len(created) == 3

    def test_new_uow_builds_a_sqlalchemy_uow(self):
        from server.service_layer.unit_of_work import SqlAlchemyUnitOfWork
        assert isinstance(router._new_uow(), SqlAlchemyUnitOfWork)


# ------------------------------------------------- traducció d'excepcions

class TestErrorMapping:
    @pytest.mark.parametrize("exc, code, message", [
        (NotFound("recipe amb id 99 no existeix"),
         protocol.NOT_FOUND, "recipe amb id 99 no existeix"),
        (AlreadyExists("Aquest email ja existeix"),
         protocol.ALREADY_EXISTS, "Aquest email ja existeix"),
        (ValueError("Recurs desconegut: x"),
         protocol.INVALID_DATA, "Recurs desconegut: x"),
        (KeyError("id"), protocol.INVALID_DATA, "Falta el camp 'id'"),
    ])
    def test_known_exceptions(self, services_mock, exc, code, message):
        services_mock.show_resource.side_effect = exc
        assert call("SHOW", {"resource": "recipe", "id": 1}) == {
            "status": "ERROR", "error": code, "message": message}

    @pytest.mark.parametrize("command, data, service", [
        ("LIST", {"resource": "recipe"}, "list_resources"),
        ("SHOW", {"resource": "recipe", "id": 1}, "show_resource"),
        ("CREATE", {"resource": "recipe", "values": {}}, "create_resource"),
        ("UPDATE", {"resource": "recipe", "id": 1, "values": {}}, "update_resource"),
        ("DELETE", {"resource": "recipe", "id": 1}, "delete_resource"),
    ])
    def test_every_command_translates_domain_errors(
            self, services_mock, command, data, service):
        getattr(services_mock, service).side_effect = NotFound("nope")
        out = call(command, data)
        assert out["error"] == protocol.NOT_FOUND and out["message"] == "nope"

    def test_unexpected_exception_becomes_server_error(self, services_mock):
        services_mock.show_resource.side_effect = RuntimeError("db exploded")
        out = call("SHOW", {"resource": "recipe", "id": 1})
        assert out["status"] == "ERROR"
        assert out["error"] == protocol.SERVER_ERROR

    def test_internal_details_are_not_leaked_to_client(self, services_mock):
        services_mock.show_resource.side_effect = RuntimeError("password=hunter2 @ db-host")
        raw = router.handle(protocol.build_request("SHOW", {"resource": "r", "id": 1}))
        assert b"hunter2" not in raw and b"db-host" not in raw
        assert protocol.parse_message(raw)["message"] == "Error intern del servidor"

    def test_unexpected_exception_is_logged_on_the_server(self, services_mock, capsys):
        services_mock.show_resource.side_effect = RuntimeError("detall intern")
        call("SHOW", {"resource": "recipe", "id": 1})
        assert "detall intern" in capsys.readouterr().out

    def test_the_router_survives_an_error_and_keeps_working(self, services_mock):
        services_mock.show_resource.side_effect = [RuntimeError("x"), {"id": 1}]
        assert call("SHOW", {"resource": "r", "id": 1})["error"] == protocol.SERVER_ERROR
        assert call("SHOW", {"resource": "r", "id": 1})["status"] == protocol.OK

    def test_a_non_serializable_result_becomes_server_error(self, services_mock):
        services_mock.show_resource.return_value = {"when": object()}
        assert call("SHOW", {"resource": "r", "id": 1})["error"] == protocol.SERVER_ERROR


# ------------------------------- integració router + serveis (BD falsa)

class TestEndToEndWithFakeDb:
    """Cicle de vida complet per la ruta real router -> serveis -> UoW fals."""

    def test_crud_lifecycle(self, send):
        created = send("CREATE", {"resource": "recipe", "values": {
            "name": "Camamilla", "step_by_step": "Bullir aigua", "duration": 10}})
        assert created["status"] == "OK"
        rid = created["data"]["id"]

        assert send("SHOW", {"resource": "recipe", "id": rid})["data"]["name"] == "Camamilla"

        upd = send("UPDATE", {"resource": "recipe", "id": rid, "values": {"duration": 15}})
        assert upd["data"]["duration"] == 15 and upd["data"]["name"] == "Camamilla"

        listed = send("LIST", {"resource": "recipe"})
        assert [i["id"] for i in listed["data"]["items"]] == [rid]

        assert send("DELETE", {"resource": "recipe", "id": rid}) == {"status": "OK", "data": {}}
        assert send("SHOW", {"resource": "recipe", "id": rid})["error"] == protocol.NOT_FOUND
        assert send("LIST", {"resource": "recipe"})["data"] == {"items": []}

    def test_not_found_message_matches_readme(self, send):
        assert send("SHOW", {"resource": "recipe", "id": 99}) == {
            "status": "ERROR", "error": "NOT_FOUND",
            "message": "recipe amb id 99 no existeix"}

    def test_duplicate_email_message_matches_readme(self, send):
        user = {"resource": "user", "values": {
            "user_name": "anna", "email": "anna@mail.com", "password": "1234"}}
        assert send("CREATE", user)["status"] == "OK"
        assert send("CREATE", user) == {
            "status": "ERROR", "error": "ALREADY_EXISTS",
            "message": "Aquest email ja existeix"}

    def test_created_user_matches_readme_and_hides_password(self, send):
        out = send("CREATE", {"resource": "user", "values": {
            "user_name": "anna", "email": "anna@mail.com", "password": "1234"}})
        assert set(out["data"]) == {"id", "user_name", "alias", "email", "phone"}

    def test_dates_travel_as_iso_strings(self, send):
        out = send("CREATE", {"resource": "recipe", "values": {
            "name": "A", "step_by_step": "x"}})
        from datetime import datetime
        datetime.fromisoformat(out["data"]["created_at"])   # no ha de fallar

    def test_failed_request_leaves_no_changes(self, send, db):
        send("CREATE", {"resource": "recipe", "values": {"name": "sense passos"}})
        assert db.tables["recipes"] == {}

    def test_error_does_not_break_following_requests(self, send):
        assert send("SHOW", {"resource": "recipe", "id": 1})["status"] == "ERROR"
        assert send("CREATE", {"resource": "category", "values": {"name": "T"}})["status"] == "OK"
