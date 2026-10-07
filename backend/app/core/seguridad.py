"""Hash de claves, tokens y cifrado de credenciales."""
import base64
import hashlib
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from .config import ajustes
from .util import ahora

_hasher = PasswordHasher()


def hash_clave(clave: str) -> str:
    return _hasher.hash(clave)


def verificar_clave(clave: str, hash_: str) -> bool:
    try:
        return _hasher.verify(hash_, clave)
    except (VerifyMismatchError, Exception):
        return False


def validar_fortaleza(clave: str) -> str | None:
    if len(clave) < 8:
        return "La clave debe tener al menos 8 caracteres."
    if clave.isdigit() or clave.isalpha():
        return "La clave debe combinar letras y numeros."
    return None


def crear_token_acceso(usuario_id: int, sesion_id: int) -> str:
    a = ajustes()
    carga = {"sub": str(usuario_id), "sid": sesion_id, "exp": ahora() + timedelta(minutes=a.minutos_token_acceso)}
    return jwt.encode(carga, a.secreto, algorithm="HS256")


def leer_token_acceso(token: str) -> dict | None:
    try:
        return jwt.decode(token, ajustes().secreto, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def token_aleatorio(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_qr() -> str:
    """128 bits aleatorios en base32 sin relleno: no secuencial ni adivinable."""
    return base64.b32encode(secrets.token_bytes(16)).decode().rstrip("=")


def huella(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def _fernet() -> Fernet:
    clave = hashlib.sha256(("cifrado:" + ajustes().secreto).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(cifrado: str) -> str:
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("No fue posible descifrar: la clave secreta cambio.") from e
