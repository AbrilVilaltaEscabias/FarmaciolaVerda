"""
Capa de sockets (server/server.py::handle_client) amb la connexió mockejada.
No s'obre cap socket real ni es toca la xarxa.
"""
import io
from unittest.mock import MagicMock

import pytest

from common import protocol
from server import server


def make_conn(*lines):
    """Connexió falsa: `makefile('rb')` retorna un lector amb les línies donades."""
    conn = MagicMock(name="conn")
    reader = io.BytesIO(b"".join(lines))
    conn.makefile.return_value.__enter__.return_value = reader
    return conn


@pytest.fixture
def handler(monkeypatch):
    mock = MagicMock(name="router.handle", side_effect=lambda line: b"RESP:" + line)
    monkeypatch.setattr(server.router, "handle", mock)
    return mock


def sent(conn):
    return [c.args[0] for c in conn.sendall.call_args_list]


def test_each_line_gets_exactly_one_response(handler):
    conn = make_conn(b"uno\n", b"dos\n", b"tres\n")
    server.handle_client(conn, ("127.0.0.1", 1234))
    assert sent(conn) == [b"RESP:uno\n", b"RESP:dos\n", b"RESP:tres\n"]


def test_lines_are_passed_to_router_in_order_with_their_newline(handler):
    conn = make_conn(b"a\n", b"b\n")
    server.handle_client(conn, ("h", 1))
    assert [c.args[0] for c in handler.call_args_list] == [b"a\n", b"b\n"]


def test_opens_the_reader_in_binary_mode(handler):
    conn = make_conn(b"a\n")
    server.handle_client(conn, ("h", 1))
    conn.makefile.assert_called_once_with("rb")


def test_no_messages_means_no_responses(handler):
    conn = make_conn()
    server.handle_client(conn, ("h", 1))
    handler.assert_not_called()
    conn.sendall.assert_not_called()


def test_connection_is_closed_at_the_end(handler):
    conn = make_conn(b"a\n")
    server.handle_client(conn, ("h", 1))
    conn.__exit__.assert_called()


def test_a_message_without_final_newline_is_still_answered(handler):
    conn = make_conn(b"last")
    server.handle_client(conn, ("h", 1))
    assert sent(conn) == [b"RESP:last"]


@pytest.mark.parametrize("exc", [ConnectionResetError, BrokenPipeError, OSError])
def test_network_errors_are_handled_and_logged(handler, capsys, exc):
    conn = make_conn(b"a\n", b"b\n")
    conn.sendall.side_effect = exc("boom")
    server.handle_client(conn, ("1.2.3.4", 99))        # no ha de propagar
    out = capsys.readouterr().out
    assert "Connexió perduda" in out and "1.2.3.4" in out


def test_network_error_stops_processing_that_client(handler):
    conn = make_conn(b"a\n", b"b\n")
    conn.sendall.side_effect = ConnectionResetError
    server.handle_client(conn, ("h", 1))
    assert handler.call_count == 1


def test_logs_connect_and_disconnect(handler, capsys):
    server.handle_client(make_conn(b"a\n"), ("9.9.9.9", 7))
    out = capsys.readouterr().out
    assert "Client connectat" in out and "Client desconnectat" in out


def test_real_router_over_the_fake_socket(wired_router, monkeypatch):
    """Cua completa: línies del 'socket' -> router real -> serveis -> bytes."""
    monkeypatch.setattr(server.router, "handle", wired_router.handle)
    conn = make_conn(
        protocol.build_request("CREATE", {"resource": "category", "values": {"name": "T"}}),
        protocol.build_request("SHOW", {"resource": "category", "id": 1}),
        protocol.build_request("SHOW", {"resource": "category", "id": 2}),
        b"basura\n",
        protocol.build_request("LIST", {"resource": "category"}),
    )
    server.handle_client(conn, ("h", 1))
    responses = [protocol.parse_message(r) for r in sent(conn)]

    assert [r["status"] for r in responses] == ["OK", "OK", "ERROR", "ERROR", "OK"]
    assert responses[2]["error"] == protocol.NOT_FOUND
    assert responses[3]["error"] == protocol.INVALID_DATA
    # Un error no tanca la connexió: la darrera petició encara es respon.
    assert responses[4]["data"]["items"][0]["name"] == "T"
    # Cada resposta és una sola línia acabada en \n.
    assert all(r.endswith(b"\n") and r.count(b"\n") == 1 for r in sent(conn))
