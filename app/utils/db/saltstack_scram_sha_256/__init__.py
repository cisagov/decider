import base64
import hashlib
import hmac
from secrets import token_bytes
from typing import Optional


def scram_sha_256(password: str, salt_bytes: Optional[bytes] = None, iterations: int = 4096) -> str:
    """
    Build a SCRAM-SHA-256 password verifier.

    Ported from https://doxygen.postgresql.org/scram-common_8c.html
    """
    if salt_bytes is None:
        salt_bytes = token_bytes(16)
    password = password.encode("utf-8", "strict")
    salted_password = hashlib.pbkdf2_hmac("sha256", password, salt_bytes, iterations)
    stored_key = hmac.new(salted_password, b"Client Key", "sha256").digest()
    stored_key = hashlib.sha256(stored_key).digest()
    server_key = hmac.new(salted_password, b"Server Key", "sha256").digest()
    return "SCRAM-SHA-256${}:{}${}:{}".format(
        iterations,
        base64.b64encode(salt_bytes).decode("ascii"),
        base64.b64encode(stored_key).decode("ascii"),
        base64.b64encode(server_key).decode("ascii"),
    )
