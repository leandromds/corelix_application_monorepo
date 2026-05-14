"""
Criptografia de credenciais em repouso usando Fernet (AES-128-CBC + HMAC-SHA256).

Usado para armazenar access tokens do WhatsApp Business API de forma segura
no banco de dados. Descriptografia ocorre apenas no momento de uso.

Chave configurada via settings.ENCRYPTION_KEY — deve ser gerada com:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet

from core.config import settings


def encrypt_credentials(plaintext: str) -> bytes:
    """
    Cifra uma string de credencial usando Fernet simétrico.

    Args:
        plaintext: Credencial em texto plano (ex: access token do WhatsApp).

    Returns:
        Bytes cifrados — armazenar em coluna BYTEA do PostgreSQL.
    """
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.encrypt(plaintext.encode())


def decrypt_credentials(ciphertext: bytes) -> str:
    """
    Decifra bytes armazenados no banco de volta para a credencial original.

    Args:
        ciphertext: Bytes cifrados retornados por encrypt_credentials().

    Returns:
        Credencial em texto plano.

    Raises:
        cryptography.fernet.InvalidToken: Se a chave estiver errada, o token
            tiver sido adulterado, ou o ciphertext estiver corrompido.
    """
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.decrypt(ciphertext).decode()
