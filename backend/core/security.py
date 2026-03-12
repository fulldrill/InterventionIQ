"""
Security utilities: Argon2id password hashing, JWT, AES-256-GCM field encryption,
HMAC-based pseudonymization for student PII.
"""
import hashlib
import hmac
import os
import struct
from base64 import b64encode, b64decode
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from core.config import settings

# ── Argon2id Password Hashing ──────────────────────────────────────────────
_ph = PasswordHasher(
    memory_cost=settings.argon2_memory_cost,
    time_cost=settings.argon2_time_cost,
    parallelism=settings.argon2_parallelism,
    hash_len=32,
    salt_len=16,
)

def hash_password(password: str) -> str:
    return _ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def needs_rehash(hashed_password: str) -> bool:
    return _ph.check_needs_rehash(hashed_password)


# ── JWT Tokens ─────────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return token

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None

def hash_token(token: str) -> str:
    """SHA-256 hash of a token for storage. Never store raw tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── AES-256-GCM Field Encryption ──────────────────────────────────────────
def _derive_aes_key() -> bytes:
    """Derive a 256-bit AES key from the SECRET_KEY using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"spip-field-encryption-v1",  # Static salt is acceptable for key derivation
        iterations=100000,
    )
    return kdf.derive(settings.secret_key.encode())

_AES_KEY = _derive_aes_key()

def encrypt_field(plaintext: str) -> bytes:
    """Encrypt a string field with AES-256-GCM. Returns nonce + ciphertext."""
    aesgcm = AESGCM(_AES_KEY)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext  # Store nonce prepended to ciphertext

def decrypt_field(ciphertext_bytes: bytes) -> str:
    """Decrypt a previously encrypted field."""
    aesgcm = AESGCM(_AES_KEY)
    nonce = ciphertext_bytes[:12]
    ciphertext = ciphertext_bytes[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

def hmac_hash_email(email: str) -> str:
    """Deterministic HMAC-SHA256 hash of email for fast lookup without storing plaintext."""
    return hmac.new(
        settings.secret_key.encode(),
        email.lower().encode(),
        hashlib.sha256
    ).hexdigest()


# ── Student Pseudonymization ───────────────────────────────────────────────
def pseudonymize_student(student_xid: str, school_secret_key: bytes) -> str:
    """
    Deterministic pseudonymization of student XID for AI prompts.
    Same input always produces the same pseudonym within a school.
    Output format: Student-XXXX (4-char hex suffix)
    """
    h = hmac.new(school_secret_key, student_xid.encode(), hashlib.sha256).hexdigest()
    return f"Student-{h[:4].upper()}"


# ── HMAC-signed tokens (email verification, password reset) ────────────────
def create_signed_token(payload: dict, expire_hours: int) -> str:
    """Create a time-limited HMAC-signed token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    payload_copy = {**payload, "exp": expire.isoformat()}
    import json
    payload_json = json.dumps(payload_copy, sort_keys=True)
    signature = hmac.new(
        settings.secret_key.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()
    token_data = b64encode(payload_json.encode()).decode() + "." + signature
    return token_data

def verify_signed_token(token: str) -> Optional[dict]:
    """Verify and decode a signed token. Returns None if invalid or expired."""
    import json
    try:
        payload_b64, signature = token.rsplit(".", 1)
        payload_json = b64decode(payload_b64).decode()
        expected_sig = hmac.new(
            settings.secret_key.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(payload_json)
        exp = datetime.fromisoformat(payload["exp"])
        if datetime.now(timezone.utc) > exp:
            return None
        return payload
    except Exception:
        return None
