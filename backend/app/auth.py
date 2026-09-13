"""Authentication: hashed passwords and bearer tokens.

**What this protects.** NextLane holds someone's job search — which roles they
want, what they were rejected for, what they are quietly learning to escape
their current job. That is the most sensitive data in the product, so every data
endpoint requires a token. Only logging in is public.

**What this is not.** It is not multi-tenancy. `_docs/specs.md` §33 rules out
multi-user collaboration and §26 notes the first user is the developer, so there
is one workspace and authentication decides who may open it — it does not
partition the data per user. If that changes, it changes in `store.py`, by
scoping cards to an owner.

Two deliberate choices:

* **`hashlib.scrypt`, from the standard library**, rather than adding bcrypt or
  passlib. scrypt is memory-hard, is what `hashlib` recommends for passwords,
  and needs no dependency. Each password gets its own 16-byte salt, and
  verification is a constant-time comparison.
* **Opaque random tokens held server-side**, rather than JWTs. A JWT cannot be
  revoked without building the very same server-side list, and hand-rolled JWT
  signing is a classic way to get this wrong. `secrets.token_urlsafe(32)` is 256
  bits from the OS CSPRNG; logging out deletes it and it is dead immediately.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dependencies import get_store
from app.domain import new_id, now
from app.errors import Unauthorized
from app.models import User
from app.store import Store

#: scrypt parameters. n=2**14 keeps a login around a few milliseconds while
#: making a brute-force attempt over a stolen store expensive.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

TOKEN_TTL = timedelta(days=14)


# ------------------------------------------------------------------ passwords


def hash_password(password: str) -> str:
    """Return `scrypt$<salt-hex>$<hash-hex>`. The salt is per password."""
    if not password:
        raise ValueError("a password is required")

    salt = secrets.token_bytes(SALT_BYTES)
    derived = _derive(password, salt)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check. Never raises on a malformed hash — it just fails."""
    try:
        scheme, salt_hex, expected_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (ValueError, AttributeError):
        return False

    return hmac.compare_digest(_derive(password, salt), expected)


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
    )


# --------------------------------------------------------------------- tokens


def issue_token(store: Store, user: User) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = now() + TOKEN_TTL
    store.save_token(token, user.id, expires_at)
    return token, expires_at


def revoke_token(store: Store, token: str) -> None:
    store.delete_token(token)


def authenticate(store: Store, email: str, password: str) -> User:
    """A wrong email and a wrong password fail identically, on purpose: telling
    them apart tells an attacker which addresses have accounts."""
    user = store.get_user_by_email(email.strip().lower())

    if user is None:
        # Still do the work, so a missing account is not faster than a wrong
        # password and cannot be spotted by timing.
        _derive("timing-equaliser", b"0" * SALT_BYTES)
        raise Unauthorized("Those details don't match an account.")

    if not verify_password(password, user.password_hash):
        raise Unauthorized("Those details don't match an account.")

    return user


# ---------------------------------------------------------------- dependency

bearer_scheme = HTTPBearer(auto_error=False, description="The token from POST /api/auth/login")

StoreDep = Annotated[Store, Depends(get_store)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def current_user(credentials: CredentialsDep, store: StoreDep) -> User:
    """The dependency every protected endpoint carries."""
    if credentials is None or not credentials.credentials:
        raise Unauthorized("Sign in to see your board.")

    if credentials.scheme.lower() != "bearer":
        raise Unauthorized("Use a bearer token.")

    session = store.get_token(credentials.credentials)
    if session is None:
        raise Unauthorized("That session is no longer valid. Sign in again.")

    if session.expires_at <= now():
        store.delete_token(credentials.credentials)
        raise Unauthorized("That session has expired. Sign in again.")

    user = store.get_user(session.user_id)
    if user is None:
        store.delete_token(credentials.credentials)
        raise Unauthorized("That session is no longer valid. Sign in again.")

    return user


CurrentUser = Annotated[User, Depends(current_user)]


# ------------------------------------------------------------------- seeding


def build_demo_user() -> User:
    """The account the seeded store ships with, so a fresh clone can sign in.

    A development convenience and nothing more — see `backend/README.md`.
    """
    return User(
        id=new_id("user"),
        email="researcher@example.com",
        display_name="Researcher",
        password_hash=hash_password("nextlane"),
        created_at=now(),
    )
