"""密碼雜湊工具 — PBKDF2-SHA256 + random salt（標準庫，零依賴）。"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 600_000  # OWASP 2024 建議值


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
