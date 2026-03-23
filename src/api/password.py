"""密碼雜湊工具 — PBKDF2-SHA256 + random salt（標準庫，零依賴）。"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 600_000  # OWASP 2024 建議值
_MIN_PASSWORD_LENGTH = 8
_PASSWORD_PATTERN = r"^[a-zA-Z0-9]+$"


def validate_password(password: str) -> str | None:
    """驗證密碼強度，回傳錯誤訊息或 None。"""
    import re
    if len(password) < _MIN_PASSWORD_LENGTH:
        return f"Password must be at least {_MIN_PASSWORD_LENGTH} characters"
    if not re.match(_PASSWORD_PATTERN, password):
        return "Password must contain only letters and numbers"
    if password.isalpha():
        return "Password must contain at least one number"
    if password.isdigit():
        return "Password must contain at least one letter"
    return None


def hash_password(password: str) -> tuple[str, str]:
    """回傳 (password_hash_hex, salt_hex)。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return dk.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """常數時間比較密碼。"""
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(stored_salt), _ITERATIONS
    )
    return hmac.compare_digest(dk.hex(), stored_hash)
