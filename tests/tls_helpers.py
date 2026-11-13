"""
Utilitats compartides pels tests de seguretat: clients TLS reals que fan
l'intercanvi de la clau de sessió igual que ho fa client/client.py.

Els tests s'han d'executar des de l'arrel del projecte (com el servidor),
perquè els certificats es carreguen amb rutes relatives a `certs/`.
"""
import asyncio
import base64
import datetime
import ssl
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from common import protocol
from server import server

CERTS = Path("certs")
CA_FILE = CERTS / "ca.crt"


def client_paths(name: str) -> tuple[Path, Path]:
    return CERTS / name / f"{name}.crt", CERTS / name / f"{name}.key"


def make_client_context(cert: Path, key: Path,
                        cafile: Path = CA_FILE) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(cafile))
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))
    return context


def decrypt_session_key(encrypted_b64: bytes, key_file: Path) -> bytes:
    """Fa el mateix que ServerConnection.__init__ al client."""
    private_key = serialization.load_pem_private_key(
        key_file.read_bytes(), password=None
    )
    return private_key.decrypt(
        base64.b64decode(encrypted_b64.strip()),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


@dataclass
class Session:
    """Connexió ja autenticada, amb la clau de sessió desxifrada."""
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    cipher: Fernet
    session_key: bytes

    async def ask(self, payload: bytes, timeout: float = 3) -> bytes:
        """Envia `payload` xifrat i retorna la resposta ja desxifrada."""
        self.writer.write(self.cipher.encrypt(payload) + b"\n")
        await self.writer.drain()
        line = await asyncio.wait_for(self.reader.readline(), timeout)
        return self.cipher.decrypt(line.strip())

    async def close(self) -> None:
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError, ssl.SSLError):
            pass


async def start_server() -> tuple[asyncio.AbstractServer, int]:
    """Servidor real amb el context TLS de producció, en un port lliure."""
    srv = await asyncio.start_server(
        server.handle_client, "127.0.0.1", 0, ssl=server.context
    )
    return srv, srv.sockets[0].getsockname()[1]


async def connect(port: int, name: str = "client1") -> Session:
    """Connecta amb el certificat de `name` i fa l'intercanvi de clau."""
    cert, key = client_paths(name)
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", port,
        ssl=make_client_context(cert, key),
        server_hostname="localhost",
    )
    encrypted_key = await asyncio.wait_for(reader.readline(), 3)
    session_key = decrypt_session_key(encrypted_key, key)
    return Session(reader, writer, Fernet(session_key), session_key)


async def wait_until(condition, timeout: float = 2.0) -> bool:
    """Espera (sense bloquejar el bucle) que `condition()` sigui certa."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition():
            return True
        await asyncio.sleep(0.02)
    return condition()


def request(command: str, data: dict | None = None) -> bytes:
    return protocol.build_request(command, data)


# --- Certificats no fiables, generats al vol per als tests de rebuig -------

def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _builder(subject: x509.Name, issuer: x509.Name, public_key):
    now = datetime.datetime.now(datetime.timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
    )


def _write(path: Path, cert: x509.Certificate, key) -> tuple[Path, Path]:
    cert_path = path.with_suffix(".crt")
    key_path = path.with_suffix(".key")
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    return cert_path, key_path


def make_self_signed(path: Path, common_name: str) -> tuple[Path, Path]:
    """Certificat autosignat (no el signa la nostra CA)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = _name(common_name)
    cert = _builder(name, name, key.public_key()).sign(key, hashes.SHA256())
    return _write(path, cert, key)


def make_rogue_ca_client(path: Path) -> tuple[Path, Path]:
    """Certificat de client signat per una CA que el servidor no coneix."""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = _name("MiCA")  # mateix nom que la CA vàlida, però altra clau
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = _builder(
        _name("client1"), ca_name, client_key.public_key()
    ).sign(ca_key, hashes.SHA256())
    return _write(path, cert, client_key)
