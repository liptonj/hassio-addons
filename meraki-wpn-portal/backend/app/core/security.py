"""Security utilities for password hashing and JWT token handling."""

import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import get_settings

# Lazy-loaded cipher for passphrase encryption
_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    """Get or create the Fernet cipher for encryption."""
    global _cipher
    if _cipher is None:
        settings = get_settings()
        _cipher = Fernet(settings.settings_encryption_key)
    return _cipher


def encrypt_passphrase(passphrase: str) -> str:
    """Encrypt a passphrase for storage.

    Args:
        passphrase: Plain text passphrase

    Returns:
        Encrypted passphrase string (base64)
    """
    cipher = _get_cipher()
    return cipher.encrypt(passphrase.encode()).decode()


def decrypt_passphrase(encrypted: str) -> str:
    """Decrypt a stored passphrase.

    Args:
        encrypted: Encrypted passphrase string

    Returns:
        Decrypted passphrase
    """
    cipher = _get_cipher()
    return cipher.decrypt(encrypted.encode()).decode()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    # bcrypt has a 72-byte limit, truncate if needed
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    # bcrypt has a 72-byte limit, truncate if needed
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def verify_token(token: str) -> dict | None:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError:
        return None


def generate_passphrase(length: int = 12, simple: bool = True) -> str:
    """Generate a random passphrase.

    Args:
        length: Length hint for the passphrase (default 12)
        simple: If True, generate easy-to-type word-based passphrase

    Returns:
        Random passphrase string
    """
    if simple:
        # Generate simple word-based passphrase like "blue-cat-42"
        words = [
            "red", "blue", "green", "sun", "moon", "star",
            "cat", "dog", "bird", "fish", "tree", "lake",
            "home", "park", "cafe", "wifi", "net", "web",
            "fast", "cool", "best", "top", "pro", "go",
        ]
        word1 = secrets.choice(words)
        word2 = secrets.choice(words)
        num = secrets.randbelow(100)
        return f"{word1}-{word2}-{num:02d}"

    if length < 8:
        length = 8
    if length > 32:
        length = 32

    # Use a mix of letters and digits, avoiding ambiguous characters
    # Removed: 0, O, l, 1, I to avoid confusion
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    # Ensure at least one uppercase, one lowercase, and one digit
    passphrase = [
        secrets.choice(string.ascii_uppercase.replace("O", "").replace("I", "")),
        secrets.choice(string.ascii_lowercase.replace("l", "")),
        secrets.choice("23456789"),
    ]

    # Fill the rest randomly
    remaining = length - 3
    passphrase.extend(secrets.choice(alphabet) for _ in range(remaining))

    # Shuffle the passphrase
    passphrase_list = list(passphrase)
    secrets.SystemRandom().shuffle(passphrase_list)

    return "".join(passphrase_list)


def generate_invite_code(length: int = 8) -> str:
    """Generate a random invite code.

    Args:
        length: Length of the code (default 8)

    Returns:
        Random uppercase alphanumeric code
    """
    # Use only uppercase letters and digits, no ambiguous characters
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_verification_code(length: int = 6) -> str:
    """Generate a numeric verification code.

    Args:
        length: Length of the code (default 6)

    Returns:
        Random numeric code
    """
    return "".join(secrets.choice("0123456789") for _ in range(length))
