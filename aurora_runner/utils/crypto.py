import base64
from typing import Optional

try:
    from cryptography.fernet import Fernet  # type: ignore
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    _CRYPTO_AVAILABLE = False


def generate_key() -> str:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography is not installed. pip install cryptography")
    return Fernet.generate_key().decode()


def encrypt_text(plaintext: str, key: str) -> str:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography is not installed. pip install cryptography")
    f = Fernet(key.encode())
    token = f.encrypt(plaintext.encode())
    return base64.urlsafe_b64encode(token).decode()


def decrypt_text(ciphertext_b64: str, key: str) -> str:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography is not installed. pip install cryptography")
    token = base64.urlsafe_b64decode(ciphertext_b64.encode())
    f = Fernet(key.encode())
    return f.decrypt(token).decode()