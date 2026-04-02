import hashlib
import hmac
import secrets
from datetime import datetime, timedelta


PBKDF2_ITERATIONS = 390000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations, salt_hex, hash_hex = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(hash_hex)
        salt = bytes.fromhex(salt_hex)
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(computed, expected)
    except Exception:
        return False


def create_token(ttl_hours: int = 24) -> tuple[str, str, datetime]:
    plain_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(plain_token.encode("utf-8")).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    return plain_token, token_hash, expires_at


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
