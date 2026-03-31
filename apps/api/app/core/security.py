from cryptography.fernet import Fernet
from app.core.config import get_settings


def get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.ENCRYPTION_KEY.encode()
    if len(key) < 32:
        key = key.ljust(32, b"0")[:32]
    import base64
    b64_key = base64.urlsafe_b64encode(key)
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
