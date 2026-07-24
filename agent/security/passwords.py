"""Password normalization, validation, and hashing helpers."""

from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("not-a-real-user-password-2026")


class PasswordPolicyViolation(ValueError):
    """Raised when a password violates the shared registration policy."""


def normalize_email(value: str) -> str:
    """Normalize an email address for identity comparisons."""
    return value.strip().casefold()


def validate_password_policy(password: str) -> str:
    """Validate the minimum password policy and return the supplied password."""
    if not 8 <= len(password) <= 128:
        raise PasswordPolicyViolation("密码长度必须为 8 至 128 个字符")
    if len(password.encode("utf-8")) > 256:
        raise PasswordPolicyViolation("密码编码后不能超过 256 字节")
    if not any(character.isalpha() for character in password):
        raise PasswordPolicyViolation("密码必须包含字母")
    if not any(character.isdigit() for character in password):
        raise PasswordPolicyViolation("密码必须包含数字")
    return password


def hash_password(password: str) -> str:
    """Validate and hash a password with the configured Argon2id scheme."""
    return _password_hash.hash(validate_password_policy(password))


def verify_password(
    password: str,
    encoded_hash: str,
) -> tuple[bool, str | None]:
    """Verify a password and return a replacement hash when recommended."""
    return _password_hash.verify_and_update(password, encoded_hash)
