import socket
from unittest.mock import MagicMock

from src.common.operations import Entity as E, Operation as O
from src.common.protocol import (
    ErrorCode,
    Request,
    deserialize_response,
    read_message,
    serialize_request,
)
from src.server.router import Router
from src.server.server import Server


def make_server(handler=None) -> Server:
    router = Router()
    router.register(E.USER, O.READ, handler or (lambda data: {"id": 1}))
    return Server(router)


def raw(operation, entity, data) -> bytes:
    return serialize_request(Request(operation, entity, data))


class TestProcessMessage:
    def test_valid_request_reaches_the_router(self):
        response = make_server().process_message(raw(O.READ, E.USER, {"id": 1}))
        assert response.is_ok and response.data == {"id": 1}

    def test_invalid_json_gives_bad_request(self):
        response = make_server().process_message(b"garbage\n")
        assert response.error["code"] == ErrorCode.BAD_REQUEST.value

    def test_unknown_entity_gives_unknown_entity(self):
        response = make_server().process_message(
            b'{"operation": "read", "entity": "banana"}\n'
        )
        assert response.error["code"] == ErrorCode.UNKNOWN_ENTITY.value

    def test_validation_runs_before_the_router(self):
        handler = MagicMock()
        response = make_server(handler).process_message(
            raw(O.READ, E.USER, {"id": -1})
        )
        assert response.error["code"] == ErrorCode.VALIDATION_ERROR.value
        handler.assert_not_called()

    def test_unexpected_error_gives_internal_error(self):
        server = make_server(MagicMock(side_effect=RuntimeError("boom")))
        response = server.process_message(raw(O.READ, E.USER, {"id": 1}))
        assert response.error["code"] == ErrorCode.INTERNAL_ERROR.value
        assert "boom" not in response.error["message"]  # no leaks


class TestClientSession:
    def test_serves_several_requests_then_stops_on_close(self):
        server_side, client_side = socket.socketpair()
        with server_side, client_side:
            client_side.sendall(
                raw(O.READ, E.USER, {"id": 1}) + raw(O.READ, E.USER, {"id": 0})
            )
            client_side.shutdown(socket.SHUT_WR)

            make_server()._serve_client(server_side)
            server_side.close()  # the real server closes it after the session

            reader = client_side.makefile("rb")
            first = deserialize_response(read_message(reader))
            second = deserialize_response(read_message(reader))
            assert first.is_ok
            assert second.error["code"] == ErrorCode.VALIDATION_ERROR.value
            assert read_message(reader) is None