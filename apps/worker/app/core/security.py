import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import get_settings


def get_fernet() -> Fernet:
    settings = get_settings()
    key_bytes = settings.ENCRYPTION_KEY.encode()
    key_hash = hashlib.sha256(key_bytes).digest()
    b64_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(b64_key)


def encrypt_api_key(plain_key: str) -> str:
    f = get_fernet()
    return f.encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    f = get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]
