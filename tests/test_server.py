"""
Capa de sockets (server/server.py::handle_client).

Hi ha dos blocs:
  * connexió simulada (mocks): comportament del bucle de lectura/resposta;
  * servidor real amb TLS: diversos clients alhora (concurrència AsyncIO).

El router es substitueix per un mock perquè aquí només es prova el servidor.
Les respostes viatgen xifrades amb la clau de sessió (Fernet), així que els
tests la fixen o la desxifren igual que faria un client real.
"""
import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from common import protocol
from server import server
from tests.tls_helpers import (
    client_paths, connect, make_client_context, start_server, wait_until,
)

SESSION_KEY = Fernet.generate_key()
CIPHER = Fernet(SESSION_KEY)


@pytest.fixture(autouse=True)
def reset_active_clients():
    server.clients_actius.clear()
    yield
    server.clients_actius.clear()


@pytest.fixture
def fixed_session_key(monkeypatch):
    """Clau de sessió coneguda, per poder xifrar les peticions simulades."""
    monkeypatch.setattr(server.Fernet, "generate_key",
                        staticmethod(lambda: SESSION_KEY))


@pytest.fixture
def handler(monkeypatch):
    mock = MagicMock(name="router.handle",
                     side_effect=lambda line: b"RESP:" + line)
    monkeypatch.setattr(server.router, "handle", mock)
    return mock


def make_writer():
    """Writer fals amb un ssl_object que retorna el certificat de client1."""
    cert_file, _ = client_paths("client1")
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    der = x509.load_pem_x509_certificate(
        cert_file.read_bytes()).public_bytes(Encoding.DER)
    ssl_obj = MagicMock(name="ssl_object")
    ssl_obj.getpeercert.return_value = der
    writer = MagicMock(name="writer")
    writer.get_extra_info.return_value = ssl_obj
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return writer


def run_client(*lines, writer=None):
    """Executa handle_client amb un lector que conté `lines` i després EOF."""
    writer = writer or make_writer()

    async def go():
        reader = asyncio.StreamReader()
        reader.feed_data(b"".join(lines))
        reader.feed_eof()
        await server.handle_client(reader, writer)

    asyncio.run(go())
    return writer


def enc(payload: bytes) -> bytes:
    """Línia tal com la envia un client: token Fernet + salt de línia."""
    return CIPHER.encrypt(payload) + b"\n"


def responses(writer):
    """Respostes enviades al client, ja desxifrades (sense la clau inicial)."""
    sent = [c.args[0] for c in writer.write.call_args_list]
    return [CIPHER.decrypt(line.strip()) for line in sent[1:]]


# --- Un client, amb el reader/writer simulats --------------------------------

def test_first_message_is_the_encrypted_session_key(handler, fixed_session_key):
    writer = run_client(enc(b"a"))
    first = writer.write.call_args_list[0].args[0]
    assert first.endswith(b"\n") and first.count(b"\n") == 1
    assert SESSION_KEY not in first      # mai en clar


def test_each_line_gets_exactly_one_response(handler, fixed_session_key):
    writer = run_client(enc(b"uno"), enc(b"dos"), enc(b"tres"))
    assert responses(writer) == [b"RESP:uno", b"RESP:dos", b"RESP:tres"]


def test_router_receives_decrypted_lines_in_order(handler, fixed_session_key):
    run_client(enc(b"a"), enc(b"b"))
    assert [c.args[0] for c in handler.call_args_list] == [b"a", b"b"]


def test_every_response_is_drained(handler, fixed_session_key):
    writer = run_client(enc(b"a"), enc(b"b"))
    assert writer.drain.await_count == 3   # clau de sessió + 2 respostes


def test_no_messages_means_no_responses(handler, fixed_session_key):
    writer = run_client()
    handler.assert_not_called()
    assert responses(writer) == []


def test_connection_is_closed_at_the_end(handler, fixed_session_key):
    writer = run_client(enc(b"a"))
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.parametrize("exc", [ConnectionResetError, BrokenPipeError, OSError])
def test_network_errors_are_handled_and_logged(
        handler, fixed_session_key, capsys, exc):
    writer = make_writer()
    writer.drain.side_effect = [None, exc("boom")]   # falla a la 1a resposta
    run_client(enc(b"a"), enc(b"b"), writer=writer)  # no ha de propagar
    assert "Connexió perduda" in capsys.readouterr().out
    writer.close.assert_called_once()


def test_network_error_stops_processing_that_client(handler, fixed_session_key):
    writer = make_writer()
    writer.drain.side_effect = [None, ConnectionResetError]
    run_client(enc(b"a"), enc(b"b"), writer=writer)
    assert handler.call_count == 1


def test_error_while_closing_is_ignored(handler, fixed_session_key):
    writer = make_writer()
    writer.wait_closed.side_effect = ConnectionResetError
    run_client(enc(b"a"), writer=writer)             # no ha de propagar


def test_logs_authentication_and_disconnect(handler, fixed_session_key, capsys):
    run_client(enc(b"a"))
    out = capsys.readouterr().out
    assert "Client autenticat: CN=client1" in out
    assert "Client desconnectat: CN=client1" in out


def test_oversized_line_gets_an_encrypted_error_and_is_closed(
        handler, fixed_session_key):
    writer = run_client(b"x" * 100_000 + b"\n")
    handler.assert_not_called()
    response = protocol.parse_message(responses(writer)[0])
    assert response["status"] == protocol.ERROR
    assert response["error"] == protocol.INVALID_DATA
    writer.close.assert_called_once()


def test_certificate_is_released_after_disconnect(handler, fixed_session_key):
    run_client(enc(b"a"))
    assert server.clients_actius == set()


def test_real_router_over_the_fake_streams(wired_router, fixed_session_key):
    """Cua completa: línies xifrades -> router real -> serveis -> bytes."""
    writer = run_client(
        enc(protocol.build_request(
            "CREATE", {"resource": "category", "values": {"name": "T"}})),
        enc(protocol.build_request("SHOW", {"resource": "category", "id": 1})),
        enc(protocol.build_request("SHOW", {"resource": "category", "id": 2})),
        enc(b"basura"),
        enc(protocol.build_request("LIST", {"resource": "category"})),
    )
    parsed = [protocol.parse_message(r) for r in responses(writer)]

    assert [r["status"] for r in parsed] == ["OK", "OK", "ERROR", "ERROR", "OK"]
    assert parsed[2]["error"] == protocol.NOT_FOUND
    assert parsed[3]["error"] == protocol.INVALID_DATA
    # Un error no tanca la connexió: l'última petició encara es respon.
    assert parsed[4]["data"]["items"][0]["name"] == "T"
    assert all(r.endswith(b"\n") and r.count(b"\n") == 1
               for r in responses(writer))


# --- Diversos clients alhora, amb un servidor real (TLS) ---------------------

def test_an_idle_client_does_not_block_another_one(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")   # connectat i callat
            b = await connect(port, "client2")
            assert await b.ask(b"from-b") == b"RESP:from-b"   # B no espera A
            assert await a.ask(b"from-a") == b"RESP:from-a"
            await a.close()
            await b.close()
    asyncio.run(go())


def test_many_requests_from_two_clients_at_once(handler):
    async def burst(session, tag):
        return [await session.ask(f"{tag}{i}".encode()) for i in range(20)]

    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")
            b = await connect(port, "client2")
            ra, rb = await asyncio.gather(burst(a, "a"), burst(b, "b"))
            await a.close()
            await b.close()
            return ra, rb

    ra, rb = asyncio.run(go())
    assert ra == [f"RESP:a{i}".encode() for i in range(20)]
    assert rb == [f"RESP:b{i}".encode() for i in range(20)]


def test_both_clients_are_registered_at_the_same_time(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")
            b = await connect(port, "client2")
            await a.ask(b"x")
            await b.ask(b"x")
            both = len(server.clients_actius)
            await a.close()
            await b.close()
            return both

    assert asyncio.run(go()) == 2


def test_a_slow_request_does_not_freeze_the_event_loop(monkeypatch):
    """
    'slow' espera (en un fil) que una altra petició la desbloquegi. Si el
    router bloquegés el bucle d'events, 'fast' no s'executaria mai.
    """
    released = threading.Event()

    def fake_handle(line):
        if line == b"slow":
            ok = released.wait(timeout=3)
            return b"slow:released" if ok else b"slow:timeout"
        released.set()
        return b"fast"

    monkeypatch.setattr(server.router, "handle", fake_handle)

    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")
            b = await connect(port, "client2")
            slow = asyncio.create_task(a.ask(b"slow"))
            await asyncio.sleep(0.1)          # que 'slow' ja estigui en marxa
            fast = await b.ask(b"fast")
            result = await slow
            await a.close()
            await b.close()
            return fast, result

    assert asyncio.run(go()) == (b"fast", b"slow:released")


def test_server_keeps_working_after_a_client_leaves_abruptly(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")
            a.writer.transport.abort()                 # tall brusc
            assert await wait_until(lambda: not server.clients_actius)
            b = await connect(port, "client2")
            answer = await b.ask(b"still-alive")
            await b.close()
            return answer

    assert asyncio.run(go()) == b"RESP:still-alive"


def test_make_client_context_requires_a_valid_ca_file():
    cert, key = client_paths("client1")
    context = make_client_context(cert, key)
    assert context.verify_mode.name == "CERT_REQUIRED"
