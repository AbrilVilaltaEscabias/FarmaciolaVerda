import io
from unittest.mock import MagicMock, patch

import pytest

from src.client.socket_client import SocketClient
from src.common.operations import Entity, Operation
from src.common.protocol import Request, Response, serialize_request
from src.common.protocol import serialize_response


@pytest.fixture
def fake_socket():
    sock = MagicMock()
    with patch("src.client.socket_client.socket.create_connection",
               return_value=sock):
        yield sock


def test_request_sends_message_and_returns_response(fake_socket):
    fake_socket.makefile.return_value = io.BytesIO(
        serialize_response(Response.ok({"id": 1}))
    )
    with SocketClient() as client:
        response = client.request(Operation.READ, Entity.USER, {"id": 1})

    fake_socket.sendall.assert_called_once_with(
        serialize_request(Request(Operation.READ, Entity.USER, {"id": 1}))
    )
    assert response.is_ok and response.data == {"id": 1}


def test_raises_if_server_closes_connection(fake_socket):
    fake_socket.makefile.return_value = io.BytesIO(b"")
    with SocketClient() as client:
        with pytest.raises(ConnectionError):
            client.request(Operation.LIST, Entity.USER)


def test_raises_if_not_connected():
    with pytest.raises(ConnectionError):
        SocketClient().request(Operation.LIST, Entity.USER)


def test_close_releases_the_socket(fake_socket):
    fake_socket.makefile.return_value = io.BytesIO(b"")
    client = SocketClient()
    client.connect()
    client.close()
    fake_socket.close.assert_called_once()