from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from typing import Any

from app.core.config import get_settings


class TokenDecodeError(ValueError):
    """Raised when a token is malformed, expired, or invalid."""


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64url_decode(payload: str) -> bytes:
    padding = "=" * ((4 - len(payload) % 4) % 4)
    return base64.urlsafe_b64decode(f"{payload}{padding}".encode("ascii"))


def _json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def hash_password(password: str, *, iterations: int = 390000) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_hex, expected_hex = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations_raw),
    )
    return hmac.compare_digest(derived.hex(), expected_hex)


def create_access_token(*, user_id: int, username: str, role: str, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl_minutes = expires_minutes if expires_minutes is not None else get_settings().jwt_expire_minutes
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64url_encode(_json_dumps(header))}.{_b64url_encode(_json_dumps(payload))}"
    signature = hmac.new(
        get_settings().jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenDecodeError("Malformed access token")

    header_raw, payload_raw, signature_raw = parts
    signing_input = f"{header_raw}.{payload_raw}"
    expected_signature = hmac.new(
        get_settings().jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_raw):
        raise TokenDecodeError("Invalid access token signature")

    try:
        payload = json.loads(_b64url_decode(payload_raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TokenDecodeError("Malformed access token payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise TokenDecodeError("Missing token expiration")
    if exp < int(datetime.now(timezone.utc).timestamp()):
        raise TokenDecodeError("Access token has expired")
    return payload
