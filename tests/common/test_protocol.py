import io
import json

import pytest

from src.common.operations import Entity, Operation
from src.common.protocol import (
    MAX_MESSAGE_SIZE,
    ErrorCode,
    ProtocolError,
    Request,
    Response,
    deserialize_request,
    deserialize_response,
    read_message,
    serialize_request,
    serialize_response,
)


def make_request() -> Request:
    return Request(Operation.CREATE, Entity.USER, {"user_name": "ana"})


class TestRequestSerialization:
    def test_roundtrip(self):
        request = make_request()
        assert deserialize_request(serialize_request(request)) == request

    def test_message_is_one_json_line(self):
        raw = serialize_request(make_request())
        assert raw.endswith(b"\n") and raw.count(b"\n") == 1
        assert json.loads(raw) == {
            "operation": "create",
            "entity": "user",
            "data": {"user_name": "ana"},
        }

    def test_data_defaults_to_empty_dict(self):
        raw = b'{"operation": "list", "entity": "recipe"}\n'
        assert deserialize_request(raw).data == {}

    @pytest.mark.parametrize(
        "raw, code",
        [
            (b"not json\n", ErrorCode.BAD_REQUEST),
            (b"\xff\xfe\n", ErrorCode.BAD_REQUEST),
            (b"[1, 2]\n", ErrorCode.BAD_REQUEST),
            (b'{"operation": "fly", "entity": "user"}\n',
             ErrorCode.UNKNOWN_OPERATION),
            (b'{"entity": "user"}\n', ErrorCode.UNKNOWN_OPERATION),
            (b'{"operation": "list", "entity": "banana"}\n',
             ErrorCode.UNKNOWN_ENTITY),
            (b'{"operation": "list"}\n', ErrorCode.UNKNOWN_ENTITY),
            (b'{"operation": "list", "entity": "user", "data": [1]}\n',
             ErrorCode.BAD_REQUEST),
        ],
    )
    def test_invalid_requests_are_rejected(self, raw, code):
        with pytest.raises(ProtocolError) as error:
            deserialize_request(raw)
        assert error.value.code == code


class TestResponseSerialization:
    def test_ok_roundtrip(self):
        response = Response.ok({"id": 1})
        decoded = deserialize_response(serialize_response(response))
        assert decoded == response and decoded.is_ok

    def test_error_roundtrip(self):
        response = Response.failure(ErrorCode.NOT_FOUND, "missing")
        decoded = deserialize_response(serialize_response(response))
        assert not decoded.is_ok
        assert decoded.error == {"code": "not_found", "message": "missing"}

    def test_invalid_status_is_rejected(self):
        with pytest.raises(ProtocolError):
            deserialize_response(b'{"status": "maybe"}\n')


class TestFraming:
    def test_reads_messages_one_by_one(self):
        stream = io.BytesIO(b'{"a": 1}\n{"b": 2}\n')
        assert read_message(stream) == b'{"a": 1}\n'
        assert read_message(stream) == b'{"b": 2}\n'

    def test_returns_none_when_peer_closed(self):
        assert read_message(io.BytesIO(b"")) is None

    def test_rejects_message_without_delimiter(self):
        with pytest.raises(ProtocolError):
            read_message(io.BytesIO(b'{"a": 1}'))

    def test_rejects_oversized_message(self):
        stream = io.BytesIO(b"x" * (MAX_MESSAGE_SIZE + 10) + b"\n")
        with pytest.raises(ProtocolError):
            read_message(stream)