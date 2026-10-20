"""Serialització i deserialització del protocol (common/protocol.py)."""
import json
from datetime import datetime

import pytest

from common import protocol


# ---------------------------------------------------------------- constants

class TestConstants:
    def test_default_address(self):
        assert protocol.HOST == "127.0.0.1"
        assert protocol.PORT == 5000

    def test_separator_is_newline(self):
        assert protocol.SEPARATOR == "\n"

    def test_status_values(self):
        assert protocol.OK == "OK"
        assert protocol.ERROR == "ERROR"

    def test_error_codes_are_stable(self):
        assert {
            protocol.INVALID_DATA, protocol.UNKNOWN_COMMAND, protocol.NOT_FOUND,
            protocol.ALREADY_EXISTS, protocol.SERVER_ERROR,
        } == {"INVALID_DATA", "UNKNOWN_COMMAND", "NOT_FOUND",
              "ALREADY_EXISTS", "SERVER_ERROR"}

    def test_crud_commands(self):
        assert (protocol.LIST, protocol.SHOW, protocol.CREATE,
                protocol.UPDATE, protocol.DELETE) == (
            "LIST", "SHOW", "CREATE", "UPDATE", "DELETE")


# ------------------------------------------------------------ build_request

class TestBuildRequest:
    def test_returns_bytes(self):
        assert isinstance(protocol.build_request(protocol.LIST), bytes)

    def test_ends_with_exactly_one_newline(self):
        raw = protocol.build_request(protocol.SHOW, {"resource": "recipe", "id": 3})
        assert raw.endswith(b"\n")
        assert raw.count(b"\n") == 1

    def test_structure_matches_readme(self):
        raw = protocol.build_request(protocol.SHOW, {"resource": "recipe", "id": 3})
        assert json.loads(raw) == {
            "command": "SHOW",
            "data": {"resource": "recipe", "id": 3},
        }

    @pytest.mark.parametrize("data", [None, {}])
    def test_missing_or_empty_data_becomes_empty_object(self, data):
        assert json.loads(protocol.build_request(protocol.LIST, data))["data"] == {}

    def test_data_defaults_to_empty_object(self):
        assert json.loads(protocol.build_request(protocol.LIST))["data"] == {}

    def test_non_serializable_data_raises(self):
        with pytest.raises(TypeError):
            protocol.build_request(protocol.CREATE, {"when": datetime.now()})


# ----------------------------------------------------------------- build_ok

class TestBuildOk:
    def test_structure(self):
        raw = protocol.build_ok({"id": 7, "name": "Camamilla"})
        assert json.loads(raw) == {"status": "OK",
                                   "data": {"id": 7, "name": "Camamilla"}}

    def test_single_line_bytes(self):
        raw = protocol.build_ok({"a": 1})
        assert isinstance(raw, bytes)
        assert raw.endswith(b"\n") and raw.count(b"\n") == 1

    @pytest.mark.parametrize("data", [None, {}])
    def test_no_data_gives_empty_object(self, data):
        assert json.loads(protocol.build_ok(data)) == {"status": "OK", "data": {}}

    def test_no_args(self):
        assert json.loads(protocol.build_ok()) == {"status": "OK", "data": {}}

    def test_list_payload_under_items(self):
        raw = protocol.build_ok({"items": [{"id": 1}, {"id": 2}]})
        assert json.loads(raw)["data"]["items"] == [{"id": 1}, {"id": 2}]

    def test_none_values_become_null(self):
        raw = protocol.build_ok({"note": None})
        assert b'"note": null' in raw
        assert json.loads(raw)["data"]["note"] is None


# -------------------------------------------------------------- build_error

class TestBuildError:
    def test_structure_matches_readme(self):
        raw = protocol.build_error(protocol.NOT_FOUND, "recipe amb id 99 no existeix")
        assert json.loads(raw) == {
            "status": "ERROR",
            "error": "NOT_FOUND",
            "message": "recipe amb id 99 no existeix",
        }

    def test_message_defaults_to_empty_string(self):
        assert json.loads(protocol.build_error(protocol.SERVER_ERROR))["message"] == ""

    def test_has_no_data_field(self):
        assert "data" not in json.loads(protocol.build_error(protocol.INVALID_DATA, "x"))

    def test_single_line_bytes(self):
        raw = protocol.build_error(protocol.INVALID_DATA, "x")
        assert isinstance(raw, bytes)
        assert raw.endswith(b"\n") and raw.count(b"\n") == 1


# ------------------------------------------------------------ parse_message

class TestParseMessage:
    def test_parses_line_with_newline(self):
        assert protocol.parse_message(b'{"command": "LIST"}\n') == {"command": "LIST"}

    def test_parses_line_without_newline(self):
        assert protocol.parse_message(b'{"a": 1}') == {"a": 1}

    def test_tolerates_crlf_and_surrounding_whitespace(self):
        assert protocol.parse_message(b'  {"a": 1}\r\n') == {"a": 1}

    def test_invalid_json_raises_jsondecodeerror(self):
        with pytest.raises(json.JSONDecodeError):
            protocol.parse_message(b"aixo no es json\n")

    @pytest.mark.parametrize("line", [b"", b"\n", b"   \n"])
    def test_empty_line_raises_jsondecodeerror(self, line):
        with pytest.raises(json.JSONDecodeError):
            protocol.parse_message(line)

    def test_invalid_utf8_raises_unicodedecodeerror(self):
        with pytest.raises(UnicodeDecodeError):
            protocol.parse_message(b"\xff\xfe\n")

    @pytest.mark.parametrize("line, expected", [
        (b"[1, 2]", [1, 2]),
        (b'"text"', "text"),
        (b"42", 42),
        (b"null", None),
    ])
    def test_non_object_json_is_returned_as_is(self, line, expected):
        # parse_message no valida l'estructura: ho fa el router.
        assert protocol.parse_message(line) == expected


# --------------------------------------------------------------- round trip

class TestRoundTrip:
    @pytest.mark.parametrize("command, data", [
        (protocol.LIST, {"resource": "recipe"}),
        (protocol.LIST, {"resource": "recipe", "filter": {"category": "Tisanes"},
                         "page": 2, "page_size": 5}),
        (protocol.SHOW, {"resource": "ingredient", "id": 1}),
        (protocol.CREATE, {"resource": "user", "values": {
            "user_name": "anna", "email": "anna@mail.com", "password": "1234"}}),
        (protocol.UPDATE, {"resource": "recipe", "id": 1, "values": {"duration": 15}}),
        (protocol.DELETE, {"resource": "recipe", "id": 1}),
    ])
    def test_request(self, command, data):
        parsed = protocol.parse_message(protocol.build_request(command, data))
        assert parsed == {"command": command, "data": data}

    def test_ok_response(self):
        data = {"id": 1, "duration": 10, "note": None, "active": True, "ratio": 1.5}
        assert protocol.parse_message(protocol.build_ok(data)) == {
            "status": "OK", "data": data}

    def test_error_response(self):
        parsed = protocol.parse_message(protocol.build_error(protocol.NOT_FOUND, "x"))
        assert parsed == {"status": "ERROR", "error": "NOT_FOUND", "message": "x"}

    def test_catalan_and_unicode_text(self):
        text = "Infusió de camamilla: àèéíòóúç·l l ñ 日本語 🌿"
        parsed = protocol.parse_message(protocol.build_ok({"description": text}))
        assert parsed["data"]["description"] == text

    def test_newlines_inside_text_do_not_break_framing(self):
        """Un salt de línia dins d'un text no pot partir el missatge en dos."""
        text = "pas 1\npas 2\r\npas 3"
        raw = protocol.build_ok({"step_by_step": text})
        assert raw.count(b"\n") == 1           # només el delimitador final
        assert protocol.parse_message(raw)["data"]["step_by_step"] == text

    def test_quotes_and_backslashes(self):
        text = 'digues "hola" \\ adéu'
        parsed = protocol.parse_message(protocol.build_ok({"note": text}))
        assert parsed["data"]["note"] == text

    def test_multiple_messages_split_by_separator(self):
        """Simula el flux TCP: diversos missatges enganxats es separen pel \\n."""
        stream = (protocol.build_request(protocol.LIST, {"resource": "recipe"})
                  + protocol.build_request(protocol.SHOW, {"resource": "recipe", "id": 1}))
        lines = stream.split(protocol.SEPARATOR.encode())
        assert lines[-1] == b""
        commands = [protocol.parse_message(l)["command"] for l in lines[:-1]]
        assert commands == ["LIST", "SHOW"]
