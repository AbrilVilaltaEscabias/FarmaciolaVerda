"""Blocking TCP client that speaks the JSON protocol."""
import socket
from typing import Optional

from src.common.operations import Entity, Operation
from src.common.protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    Request,
    Response,
    deserialize_response,
    read_message,
    serialize_request,
)


class SocketClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._reader = None

    def connect(self) -> None:
        self._sock = socket.create_connection((self._host, self._port))
        self._reader = self._sock.makefile("rb")

    def close(self) -> None:
        if self._reader:
            self._reader.close()
        if self._sock:
            self._sock.close()
        self._sock = self._reader = None

    def send(self, request: Request) -> Response:
        if self._sock is None:
            raise ConnectionError("Client is not connected")
        self._sock.sendall(serialize_request(request))
        raw = read_message(self._reader)
        if raw is None:
            raise ConnectionError("Server closed the connection")
        return deserialize_response(raw)

    def request(
        self, operation: Operation, entity: Entity, data: Optional[dict] = None
    ) -> Response:
        """Shortcut: build the Request and send it."""
        return self.send(Request(operation, entity, data or {}))

    def __enter__(self) -> "SocketClient":
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()