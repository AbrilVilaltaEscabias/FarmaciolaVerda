"""JSON protocol: message objects, serialization and framing.

Framing: every message is one JSON document on a single line,
terminated by a newline ("\\n"). TCP is a byte stream, so the
delimiter is what tells us where a message ends.
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, BinaryIO, Optional

from src.common.operations import Entity, Operation

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000

ENCODING = "utf-8"
DELIMITER = b"\n"
MAX_MESSAGE_SIZE = 64 * 1024  # bytes

STATUS_OK = "ok"
STATUS_ERROR = "error"


class ErrorCode(str, Enum):
    BAD_REQUEST = "bad_request"
    UNKNOWN_OPERATION = "unknown_operation"
    UNKNOWN_ENTITY = "unknown_entity"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"


class ProtocolError(Exception):
    """The received bytes do not follow the protocol."""

    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Request:
    operation: Operation
    entity: Entity
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    status: str
    data: Any = None
    error: Optional[dict] = None

    @property
    def is_ok(self) -> bool:
        return self.status == STATUS_OK

    @classmethod
    def ok(cls, data: Any = None) -> "Response":
        return cls(status=STATUS_OK, data=data)

    @classmethod
    def failure(cls, code: ErrorCode, message: str) -> "Response":
        return cls(
            status=STATUS_ERROR,
            error={"code": code.value, "message": message},
        )


# --------------------------------------------------------------- encoding
def _encode(payload: dict) -> bytes:
    return json.dumps(payload).encode(ENCODING) + DELIMITER


def _decode(raw: bytes) -> dict:
    try:
        payload = json.loads(raw.decode(ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(
            ErrorCode.BAD_REQUEST, f"Invalid JSON message: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProtocolError(
            ErrorCode.BAD_REQUEST, "Message must be a JSON object"
        )
    return payload


def serialize_request(request: Request) -> bytes:
    return _encode(
        {
            "operation": request.operation.value,
            "entity": request.entity.value,
            "data": request.data,
        }
    )


def deserialize_request(raw: bytes) -> Request:
    payload = _decode(raw)

    try:
        operation = Operation(payload.get("operation"))
    except ValueError as exc:
        raise ProtocolError(
            ErrorCode.UNKNOWN_OPERATION,
            f"Unknown operation: {payload.get('operation')!r}",
        ) from exc

    try:
        entity = Entity(payload.get("entity"))
    except ValueError as exc:
        raise ProtocolError(
            ErrorCode.UNKNOWN_ENTITY,
            f"Unknown entity: {payload.get('entity')!r}",
        ) from exc

    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise ProtocolError(ErrorCode.BAD_REQUEST, "'data' must be an object")

    return Request(operation=operation, entity=entity, data=data)


def serialize_response(response: Response) -> bytes:
    return _encode(
        {
            "status": response.status,
            "data": response.data,
            "error": response.error,
        }
    )


def deserialize_response(raw: bytes) -> Response:
    payload = _decode(raw)
    status = payload.get("status")
    if status not in (STATUS_OK, STATUS_ERROR):
        raise ProtocolError(ErrorCode.BAD_REQUEST, "Invalid 'status' field")
    return Response(
        status=status,
        data=payload.get("data"),
        error=payload.get("error"),
    )


# ---------------------------------------------------------------- framing
def read_message(stream: BinaryIO) -> Optional[bytes]:
    """Read one framed message. Return None if the peer closed the stream."""
    line = stream.readline(MAX_MESSAGE_SIZE + 1)
    if not line:
        return None
    if len(line) > MAX_MESSAGE_SIZE or not line.endswith(DELIMITER):
        raise ProtocolError(
            ErrorCode.BAD_REQUEST, "Message too large or not terminated"
        )
    return line