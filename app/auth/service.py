from __future__ import annotations

from app.db.repositories import authenticate_user, create_user


def register_user(username: str, email: str, password: str):
    return create_user(username=username, email=email, password=password)


def login_user(identifier: str, password: str):
    return authenticate_user(identifier, password)

