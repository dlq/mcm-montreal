from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime
from typing import Any

from flask import Flask, Response, current_app, g, request, session
from itsdangerous import BadSignature, URLSafeSerializer

ANONYMOUS_COOKIE_NAME = "mcm_anonymous_id"
ANONYMOUS_COOKIE_MAX_AGE = 60 * 60 * 24 * 400
ANONYMOUS_COOKIE_SALT = "mcm-anonymous-identity"


def load_anonymous_identity(app: Flask, db: sqlite3.Connection) -> None:
    token = read_identity_token(app)
    if not token:
        token = secrets.token_urlsafe(32)
        g.anonymous_identity_cookie = token
    owner_key = owner_key_for_token(token)
    now = datetime.now(UTC).isoformat()
    db.execute(
        """
        INSERT INTO anonymous_identities (owner_key, created_at, last_seen_at)
        VALUES (?, ?, ?)
        ON CONFLICT(owner_key) DO UPDATE SET last_seen_at = excluded.last_seen_at
        """,
        (owner_key, now, now),
    )
    db.commit()
    g.anonymous_owner_key = owner_key
    migrate_session_favourites(db, owner_key)


def persist_anonymous_identity(response: Response) -> Response:
    token = getattr(g, "anonymous_identity_cookie", "")
    if token:
        response.set_cookie(
            ANONYMOUS_COOKIE_NAME,
            sign_identity_token(token),
            max_age=ANONYMOUS_COOKIE_MAX_AGE,
            httponly=True,
            secure=request.is_secure or bool(current_app.config.get("D1_BRIDGE_URL")),
            samesite="Lax",
        )
    return response


def current_owner_key() -> str:
    return str(getattr(g, "anonymous_owner_key", ""))


def read_identity_token(app: Flask) -> str:
    signed_token = request.cookies.get(ANONYMOUS_COOKIE_NAME, "")
    if not signed_token:
        return ""
    serializer = URLSafeSerializer(app.config["SECRET_KEY"], salt=ANONYMOUS_COOKIE_SALT)
    try:
        token = serializer.loads(signed_token)
    except BadSignature:
        return ""
    return token if isinstance(token, str) and token else ""


def sign_identity_token(token: str) -> str:
    serializer = URLSafeSerializer(current_app.config["SECRET_KEY"], salt=ANONYMOUS_COOKIE_SALT)
    return serializer.dumps(token)


def owner_key_for_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def migrate_session_favourites(db: sqlite3.Connection, owner_key: str) -> None:
    listing_ids = clean_int_values(session.get("favourite_listing_ids", []))
    shop_ids = clean_int_values(session.get("favourite_shop_ids", []))
    for listing_id in listing_ids:
        db.execute(
            """
            INSERT OR IGNORE INTO anonymous_favourite_listings (owner_key, listing_id, created_at)
            VALUES (?, ?, ?)
            """,
            (owner_key, listing_id, datetime.now(UTC).isoformat()),
        )
    for shop_id in shop_ids:
        db.execute(
            """
            INSERT OR IGNORE INTO anonymous_favourite_shops (owner_key, shop_id, created_at)
            VALUES (?, ?, ?)
            """,
            (owner_key, shop_id, datetime.now(UTC).isoformat()),
        )
    if listing_ids or shop_ids:
        session.pop("favourite_listing_ids", None)
        session.pop("favourite_shop_ids", None)
        session.modified = True
        db.commit()


def clean_int_values(values: Any) -> list[int]:
    cleaned: list[int] = []
    for value in values if isinstance(values, list) else []:
        try:
            cleaned.append(int(value))
        except (TypeError, ValueError):
            continue
    return cleaned
