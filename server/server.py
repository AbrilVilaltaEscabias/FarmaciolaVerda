import asyncio
import ssl
from cryptography.fernet import Fernet, InvalidToken
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes

import base64
import hashlib

from common import protocol
from server import router
from server.db import Base, engine
from server.adapters import orm

clients_actius: set[str] = set()

# 1. Context TLS del servidor
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile="certs/servidor/server.crt",
                        keyfile="certs/servidor/server.key"
                        )
context.load_verify_locations(cafile="certs/ca.crt")
context.verify_mode = ssl.CERT_REQUIRED


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Atén un client autenticat per certificat."""
    ssl_obj = writer.get_extra_info("ssl_object")

    # Certificat del client (ja validat contra la CA durant el handshake TLS)
    client_cert = ssl_obj.getpeercert(binary_form=True)
    certificate = x509.load_der_x509_certificate(client_cert)
    subject = certificate.subject.rfc4514_string()   # p. ex. "CN=client1"
    fingerprint = hashlib.sha256(client_cert).hexdigest()

    print(f"Client autenticat: {subject}")

    # Rebutjar si aquest certificat ja està connectat
    if fingerprint in clients_actius:
        print(f"[!] Connexió rebutjada ({subject}): certificat ja connectat.")
        writer.close()
        await writer.wait_closed()
        return

    clients_actius.add(fingerprint)

    try:
        # Clau AES de sessió, xifrada amb la clau pública del client
        public_key = certificate.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            print(f"[!] Connexió rebutjada ({subject}): el certificat no és RSA.")
            return
        session_key = Fernet.generate_key()
        encrypted_key = public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        writer.write(base64.b64encode(encrypted_key) + b"\n")
        await writer.drain()

        cipher = Fernet(session_key)

        while encrypted_line := await reader.readline():
            line = cipher.decrypt(encrypted_line.strip())
            response = await asyncio.to_thread(router.handle, line)
            writer.write(cipher.encrypt(response) + b"\n")
            await writer.drain()

    except ValueError:
        print(f"[!] Missatge massa llarg de {subject}")
        error = protocol.build_error(protocol.INVALID_DATA, "Missatge massa llarg")
        writer.write(cipher.encrypt(error) + b"\n")
        await writer.drain()
    except InvalidToken:
        print(f"[!] Error d'integritat/xifratge: missatge no vàlid de {subject}")
    except (ConnectionError, OSError) as e:
        print(f"[!] Connexió perduda amb {subject}: {e}")
    finally:
        writer.close()
        clients_actius.discard(fingerprint)
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass

    print(f"[-] Client desconnectat: {subject}")


async def main() -> None:

    # 1. Enllaçar les classes del domini amb les taules
    orm.start_mappers()

    # 2. Crear les taules si no existeixen
    orm.metadata.create_all(engine)

    # 3. Crear les taules si no existeixen
    Base.metadata.create_all(engine)

    # 4. Arrencar el servidor: crea el socket, fa bind/listen i, per cada nova
    #    connexió, llança handle_client(reader, writer) com una Task nova.
    server = await asyncio.start_server(handle_client, protocol.HOST, protocol.PORT, ssl=context)
    addresses = [s.getsockname() for s in server.sockets]
    print(f"Servidor escoltant a {addresses}")

    # 5. Servir fins que es cancel·li (Ctrl+C)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor aturat")
