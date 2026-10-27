"""
Capa de sockets (server/server.py::handle_client) amb la connexió mockejada.
No s'obre cap socket real ni es toca la xarxa.
"""
import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock
 
import pytest
 
from common import protocol
from server import server
 
 
def make_writer(addr=("h", 1)):
    """Writer fals: write() és síncron; drain() i wait_closed() són awaitables."""
    writer = MagicMock(name="writer")
    writer.get_extra_info.return_value = addr
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
 
 
def sent(writer):
    return [c.args[0] for c in writer.write.call_args_list]
 
 
@pytest.fixture
def handler(monkeypatch):
    mock = MagicMock(name="router.handle", side_effect=lambda line: b"RESP:" + line)
    monkeypatch.setattr(server.router, "handle", mock)
    return mock
 
 
# --- Un client, amb el reader/writer simulats --------------------------------
 
def test_each_line_gets_exactly_one_response(handler):
    writer = run_client(b"uno\n", b"dos\n", b"tres\n")
    assert sent(writer) == [b"RESP:uno\n", b"RESP:dos\n", b"RESP:tres\n"]
 
 
def test_lines_are_passed_to_router_in_order_with_their_newline(handler):
    run_client(b"a\n", b"b\n")
    assert [c.args[0] for c in handler.call_args_list] == [b"a\n", b"b\n"]
 
 
def test_every_response_is_drained(handler):
    writer = run_client(b"a\n", b"b\n")
    assert writer.drain.await_count == 2
 
 
def test_no_messages_means_no_responses(handler):
    writer = run_client()
    handler.assert_not_called()
    writer.write.assert_not_called()
 
 
def test_connection_is_closed_at_the_end(handler):
    writer = run_client(b"a\n")
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()
 
 
def test_a_message_without_final_newline_is_still_answered(handler):
    writer = run_client(b"last")
    assert sent(writer) == [b"RESP:last"]
 
 
@pytest.mark.parametrize("exc", [ConnectionResetError, BrokenPipeError, OSError])
def test_network_errors_are_handled_and_logged(handler, capsys, exc):
    writer = make_writer(("1.2.3.4", 99))
    writer.drain.side_effect = exc("boom")
    run_client(b"a\n", b"b\n", writer=writer)        # no ha de propagar
    out = capsys.readouterr().out
    assert "Connexió perduda" in out and "1.2.3.4" in out
    writer.close.assert_called_once()                # i tanca igualment
 
 
def test_network_error_stops_processing_that_client(handler):
    writer = make_writer()
    writer.drain.side_effect = ConnectionResetError
    run_client(b"a\n", b"b\n", writer=writer)
    assert handler.call_count == 1
 
 
def test_error_while_closing_is_ignored(handler):
    writer = make_writer()
    writer.wait_closed.side_effect = ConnectionResetError
    run_client(b"a\n", writer=writer)                # no ha de propagar
 
 
def test_logs_connect_and_disconnect(handler, capsys):
    run_client(b"a\n", writer=make_writer(("9.9.9.9", 7)))
    out = capsys.readouterr().out
    assert "Client connectat" in out and "Client desconnectat" in out
 
 
def test_oversized_line_gets_an_error_and_the_connection_is_closed(handler):
    writer = run_client(b"x" * 100_000 + b"\n")
    handler.assert_not_called()
    response = protocol.parse_message(sent(writer)[0])
    assert response["status"] == protocol.ERROR
    assert response["error"] == protocol.INVALID_DATA
    writer.close.assert_called_once()
 
 
def test_real_router_over_the_fake_streams(wired_router, monkeypatch):
    """Cua completa: línies del 'socket' -> router real -> serveis -> bytes."""
    monkeypatch.setattr(server.router, "handle", wired_router.handle)
    writer = run_client(
        protocol.build_request("CREATE", {"resource": "category", "values": {"name": "T"}}),
        protocol.build_request("SHOW", {"resource": "category", "id": 1}),
        protocol.build_request("SHOW", {"resource": "category", "id": 2}),
        b"basura\n",
        protocol.build_request("LIST", {"resource": "category"}),
    )
    responses = [protocol.parse_message(r) for r in sent(writer)]
 
    assert [r["status"] for r in responses] == ["OK", "OK", "ERROR", "ERROR", "OK"]
    assert responses[2]["error"] == protocol.NOT_FOUND
    assert responses[3]["error"] == protocol.INVALID_DATA
    # Un error no tanca la connexió: la darrera petició encara es respon.
    assert responses[4]["data"]["items"][0]["name"] == "T"
    # Cada resposta és una sola línia acabada en \n.
    assert all(r.endswith(b"\n") and r.count(b"\n") == 1 for r in sent(writer))
 
 
# --- Diversos clients alhora, amb un servidor real ---------------------------
 
async def _start():
    """Servidor real a 127.0.0.1 en un port lliure (port=0)."""
    srv = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    return srv, srv.sockets[0].getsockname()[1]
 
 
async def _ask(reader, writer, line, timeout=3):
    writer.write(line)
    await writer.drain()
    return await asyncio.wait_for(reader.readline(), timeout)
 
 
def test_an_idle_client_does_not_block_another_one(handler):
    """Amb el servidor antic (un client a la vegada) això es quedava penjat."""
    async def go():
        srv, port = await _start()
        async with srv:
            ra, wa = await asyncio.open_connection("127.0.0.1", port)  # A: connectat i callat
            rb, wb = await asyncio.open_connection("127.0.0.1", port)  # B
 
            assert await _ask(rb, wb, b"from-b\n") == b"RESP:from-b\n"   # B no espera A
            assert await _ask(ra, wa, b"from-a\n") == b"RESP:from-a\n"   # A encara funciona
 
            for w in (wa, wb):
                w.close()
                await w.wait_closed()
    asyncio.run(go())
 
 
def test_many_clients_at_once(handler):
    async def one(port, i):
        r, w = await asyncio.open_connection("127.0.0.1", port)
        try:
            return await _ask(r, w, f"c{i}\n".encode())
        finally:
            w.close()
            await w.wait_closed()
 
    async def go():
        srv, port = await _start()
        async with srv:
            return await asyncio.gather(*(one(port, i) for i in range(20)))
 
    results = asyncio.run(go())
    assert results == [f"RESP:c{i}\n".encode() for i in range(20)]
 
 
def test_a_slow_request_does_not_freeze_the_event_loop(monkeypatch):
    """
    La petició 'slow' espera (en un fil) fins que una altra petició la desbloqueja.
    Si el router bloquegés el bucle d'events, 'fast' mai arribaria a executar-se
    i 'slow' acabaria per timeout.
    """
    released = threading.Event()
 
    def fake_handle(line):
        if line == b"slow\n":
            ok = released.wait(timeout=3)
            return b"slow:released\n" if ok else b"slow:timeout\n"
        released.set()
        return b"fast\n"
 
    monkeypatch.setattr(server.router, "handle", fake_handle)
 
    async def go():
        srv, port = await _start()
        async with srv:
            ra, wa = await asyncio.open_connection("127.0.0.1", port)
            rb, wb = await asyncio.open_connection("127.0.0.1", port)
 
            wa.write(b"slow\n")
            await wa.drain()
            await asyncio.sleep(0.1)                       # que 'slow' ja estigui en marxa
 
            fast = await _ask(rb, wb, b"fast\n")
            slow = await asyncio.wait_for(ra.readline(), 3)
 
            for w in (wa, wb):
                w.close()
                await w.wait_closed()
            return fast, slow
 
    assert asyncio.run(go()) == (b"fast\n", b"slow:released\n")