"""Password hashing (standard library only)."""
import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


def _derive(password: str, salt: str, iterations: int) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    )
    return raw.hex()


def hash_password(password: str) -> str:
    """Return 'algorithm$iterations$salt$digest' (never the plain text)."""
    salt = secrets.token_hex(_SALT_BYTES)
    digest = _derive(password, salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        expected = _derive(password, salt, int(iterations))
    except ValueError:
        return False
    return algorithm == _ALGORITHM and hmac.compare_digest(expected, digest)
