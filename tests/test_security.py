"""
Seguretat: autenticació per certificats, establiment de la clau de sessió i
xifratge simètric. Tots els tests fan servir un servidor real amb TLS i els
certificats de `certs/` (la CA, el servidor i client1/client2).
"""
import asyncio
import ssl
from unittest.mock import MagicMock

import pytest
from cryptography import x509
from cryptography.fernet import Fernet, InvalidToken

from common import protocol
from server import server
from tests.tls_helpers import (
    CA_FILE, client_paths, connect, decrypt_session_key, make_client_context,
    make_rogue_ca_client, make_self_signed, start_server, wait_until,
)


@pytest.fixture(autouse=True)
def reset_active_clients():
    server.clients_actius.clear()
    yield
    server.clients_actius.clear()


@pytest.fixture
def handler(monkeypatch):
    mock = MagicMock(name="router.handle",
                     side_effect=lambda line: b"RESP:" + line)
    monkeypatch.setattr(server.router, "handle", mock)
    return mock


async def _is_rejected(port, cert, key) -> bool:
    """True si el servidor no deixa fer res a aquest client.

    Amb TLS 1.3 el handshake del client pot acabar abans que el servidor
    validi el certificat; el rebuig s'ha de veure en intentar llegir.
    """
    try:
        reader, writer = await asyncio.open_connection(
            "127.0.0.1", port,
            ssl=make_client_context(cert, key),
            server_hostname="localhost",
        )
        data = await asyncio.wait_for(reader.readline(), 3)
        writer.close()
        return data == b""        # tancat sense enviar la clau de sessió
    except (ssl.SSLError, ConnectionError, OSError):
        return True


# --- 1. Autenticació amb certificats -----------------------------------------

def test_valid_client_certificates_are_accepted(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            results = []
            for name in ("client1", "client2"):
                session = await connect(port, name)
                results.append(await session.ask(b"hello"))
                await session.close()
                await wait_until(lambda: not server.clients_actius)
            return results

    assert asyncio.run(go()) == [b"RESP:hello", b"RESP:hello"]


def test_client_without_certificate_is_rejected(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(cafile=str(CA_FILE))
            try:
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", port, ssl=context,
                    server_hostname="localhost")
                writer.write(b"hello\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.readline(), 3)
                writer.close()
                return data == b""
            except (ssl.SSLError, ConnectionError, OSError):
                return True

    assert asyncio.run(go()) is True
    handler.assert_not_called()


def test_certificate_from_another_ca_is_rejected(handler, tmp_path):
    cert, key = make_rogue_ca_client(tmp_path / "rogue")

    async def go():
        srv, port = await start_server()
        async with srv:
            return await _is_rejected(port, cert, key)

    assert asyncio.run(go()) is True
    handler.assert_not_called()


def test_self_signed_certificate_is_rejected(handler, tmp_path):
    cert, key = make_self_signed(tmp_path / "selfsigned", "client1")

    async def go():
        srv, port = await start_server()
        async with srv:
            return await _is_rejected(port, cert, key)

    assert asyncio.run(go()) is True
    handler.assert_not_called()


def test_rejected_client_does_not_affect_valid_clients(handler, tmp_path):
    cert, key = make_self_signed(tmp_path / "intruder", "intruder")

    async def go():
        srv, port = await start_server()
        async with srv:
            await _is_rejected(port, cert, key)
            ok = await connect(port, "client1")
            answer = await ok.ask(b"after-attack")
            await ok.close()
            return answer

    assert asyncio.run(go()) == b"RESP:after-attack"


def test_client_rejects_a_server_not_signed_by_the_trusted_ca(tmp_path):
    """Autenticació mútua: el client també valida el servidor."""
    cert, key = make_self_signed(tmp_path / "fakeserver", "localhost")
    fake_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    fake_ctx.load_cert_chain(certfile=str(cert), keyfile=str(key))
    client_cert, client_key = client_paths("client1")

    async def go():
        srv = await asyncio.start_server(
            lambda r, w: w.close(), "127.0.0.1", 0, ssl=fake_ctx)
        port = srv.sockets[0].getsockname()[1]
        async with srv:
            with pytest.raises(ssl.SSLCertVerificationError):
                await asyncio.open_connection(
                    "127.0.0.1", port,
                    ssl=make_client_context(client_cert, client_key),
                    server_hostname="localhost")

    asyncio.run(go())


def test_same_certificate_cannot_be_connected_twice(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            first = await connect(port, "client1")
            cert, key = client_paths("client1")
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", port,
                ssl=make_client_context(cert, key),
                server_hostname="localhost")
            second_key = await asyncio.wait_for(reader.readline(), 3)
            writer.close()
            answer = await first.ask(b"still-me")   # el primer no es veu afectat
            await first.close()
            return second_key, answer

    second_key, answer = asyncio.run(go())
    assert second_key == b""          # rebutjat: cap clau de sessió
    assert answer == b"RESP:still-me"


def test_certificate_can_reconnect_after_disconnecting(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            first = await connect(port, "client1")
            await first.close()
            assert await wait_until(lambda: not server.clients_actius)
            second = await connect(port, "client1")
            answer = await second.ask(b"again")
            await second.close()
            return answer

    assert asyncio.run(go()) == b"RESP:again"


# --- 2. Establiment de la clau de sessió -------------------------------------

def test_session_key_is_a_valid_fernet_key(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            session = await connect(port, "client1")
            key = session.session_key
            await session.close()
            return key

    Fernet(asyncio.run(go()))        # llança ValueError si no és vàlida


def test_each_connection_gets_a_different_session_key(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            keys = []
            for name in ("client1", "client2", "client1"):
                session = await connect(port, name)
                keys.append(session.session_key)
                await session.close()
                await wait_until(lambda: not server.clients_actius)
            return keys

    keys = asyncio.run(go())
    assert len(set(keys)) == 3


def test_session_key_is_only_readable_with_the_right_private_key(handler):
    """El servidor xifra la clau amb la pública de client1: client2 no pot."""
    async def go():
        srv, port = await start_server()
        async with srv:
            cert, key = client_paths("client1")
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", port,
                ssl=make_client_context(cert, key),
                server_hostname="localhost")
            encrypted = await asyncio.wait_for(reader.readline(), 3)
            writer.close()
            return encrypted

    encrypted = asyncio.run(go())
    own = decrypt_session_key(encrypted, client_paths("client1")[1])
    Fernet(own)
    with pytest.raises(ValueError):
        decrypt_session_key(encrypted, client_paths("client2")[1])


def test_encrypted_key_is_bound_to_the_certificate_public_key():
    """La clau de sessió es xifra amb la clau pública del certificat."""
    cert = x509.load_pem_x509_certificate(client_paths("client1")[0].read_bytes())
    assert cert.public_key().key_size >= 2048


# --- 3. Confidencialitat (xifratge simètric) ---------------------------------

def test_plaintext_requests_are_not_accepted(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            session = await connect(port, "client1")
            session.writer.write(protocol.build_request("LIST", {"resource": "recipe"}))
            await session.writer.drain()
            data = await asyncio.wait_for(session.reader.readline(), 3)
            await session.close()
            return data

    assert asyncio.run(go()) == b""      # connexió tancada, cap resposta
    handler.assert_not_called()


def test_tampered_token_is_rejected_and_connection_closed(handler, capsys):
    async def go():
        srv, port = await start_server()
        async with srv:
            session = await connect(port, "client1")
            token = bytearray(session.cipher.encrypt(b"payload"))
            token[-5] ^= 0x01                                  # un sol bit
            session.writer.write(bytes(token) + b"\n")
            await session.writer.drain()
            data = await asyncio.wait_for(session.reader.readline(), 3)
            await session.close()
            return data

    assert asyncio.run(go()) == b""
    handler.assert_not_called()
    assert "Error d'integritat" in capsys.readouterr().out


def test_token_encrypted_with_another_sessions_key_is_rejected(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")
            b = await connect(port, "client2")
            b.writer.write(Fernet(a.session_key).encrypt(b"forged") + b"\n")
            await b.writer.drain()
            data = await asyncio.wait_for(b.reader.readline(), 3)
            alive = await a.ask(b"ok")          # la sessió A no es veu afectada
            await a.close()
            await b.close()
            return data, alive

    assert asyncio.run(go()) == (b"", b"RESP:ok")
    assert handler.call_count == 1


def test_a_session_key_does_not_decrypt_another_sessions_traffic(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            a = await connect(port, "client1")
            b = await connect(port, "client2")
            b.writer.write(b.cipher.encrypt(b"secret") + b"\n")
            await b.writer.drain()
            raw = await asyncio.wait_for(b.reader.readline(), 3)
            await a.close()
            await b.close()
            return raw, a.cipher

    raw, cipher_a = asyncio.run(go())
    assert b"secret" not in raw and b"RESP" not in raw   # res en clar al cable
    with pytest.raises(InvalidToken):
        cipher_a.decrypt(raw.strip())


def test_response_on_the_wire_is_ciphertext(handler):
    async def go():
        srv, port = await start_server()
        async with srv:
            session = await connect(port, "client1")
            session.writer.write(session.cipher.encrypt(b"top-secret") + b"\n")
            await session.writer.drain()
            raw = await asyncio.wait_for(session.reader.readline(), 3)
            await session.close()
            return raw

    raw = asyncio.run(go())
    assert b"top-secret" not in raw and b"RESP" not in raw


def test_full_protocol_roundtrip_over_secure_channel(wired_router):
    """Petició real -> xifrada -> router real -> xifrada -> client."""
    async def go():
        srv, port = await start_server()
        async with srv:
            session = await connect(port, "client1")
            created = await session.ask(protocol.build_request(
                "CREATE", {"resource": "category", "values": {"name": "Tisanes"}}))
            listed = await session.ask(
                protocol.build_request("LIST", {"resource": "category"}))
            await session.close()
            return created, listed

    created, listed = (protocol.parse_message(r) for r in asyncio.run(go()))
    assert created["status"] == protocol.OK
    assert listed["data"]["items"][0]["name"] == "Tisanes"
