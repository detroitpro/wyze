"""Credentials, the cached Wyze session, and retrying a call once the access token expires.

Wyze rate-limits logins, so a session is reused: the access token (valid ~2 days) and refresh
token (~30 days) are cached in a private file. An expired access token is refreshed; a dead
refresh token falls back to a fresh login. Tokens and credentials are never printed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError, WyzeClientError

T = TypeVar("T")

ENV = {
    "email": "WYZE_EMAIL",
    "password": "WYZE_PASSWORD",
    "key_id": "WYZE_KEY_ID",
    "api_key": "WYZE_API_KEY",
}
TOTP_ENV = "WYZE_TOTP_KEY"


class ConfigError(RuntimeError):
    """Missing or unusable configuration."""


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str
    key_id: str
    api_key: str
    totp_key: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Credentials:
        env = os.environ if env is None else env
        missing = [name for name in ENV.values() if not env.get(name)]
        if missing:
            raise ConfigError("missing " + ", ".join(missing))
        return cls(
            **{field: env[name] for field, name in ENV.items()},
            totp_key=env.get(TOTP_ENV) or None,
        )

    def __repr__(self) -> str:
        return f"Credentials(email=<{len(self.email)} chars>, ...)"


def default_cache_path() -> Path:
    if path := os.environ.get("WYZECTL_CACHE"):
        return Path(path)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "wyzectl" / "session.json"


def token_expired(error: WyzeApiError) -> bool:
    data = error.response if isinstance(error.response, dict) else {}
    code = str(data.get("code", data.get("errorCode", "")))
    return code == "2001" or data.get("msg") == "AccessTokenError"


class Session:
    """A logged-in Wyze client that keeps its tokens fresh."""

    def __init__(
        self,
        credentials: Callable[[], Credentials] = Credentials.from_env,
        cache_path: Path | None = None,
        client_factory: Callable[..., Any] = Client,
    ):
        self._credentials = credentials
        self._cache = cache_path or default_cache_path()
        self._factory = client_factory
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            cached = self._read_cache()
            if cached:
                self._client = self._factory(
                    token=cached["access_token"], refresh_token=cached["refresh_token"]
                )
            else:
                self._login()
        return self._client

    def call(self, fn: Callable[[Any], T]) -> T:
        """Run ``fn(client)``, refreshing or re-logging in once if the token has expired."""
        try:
            return fn(self.client)
        except WyzeApiError as error:
            if not token_expired(error):
                raise
        self._renew()
        return fn(self._client)

    def _renew(self) -> None:
        try:
            self._client.refresh_token()
            self._save()
        except WyzeClientError:
            self._client = None
            self._login()

    def _login(self) -> None:
        c = self._credentials()
        self._client = self._factory(
            email=c.email,
            password=c.password,
            key_id=c.key_id,
            api_key=c.api_key,
            totp_key=c.totp_key,
        )
        self._save()

    def _read_cache(self) -> dict | None:
        try:
            data = json.loads(self._cache.read_text())
        except (OSError, ValueError):
            return None
        if data.get("access_token") and data.get("refresh_token"):
            return data
        return None

    def _save(self) -> None:
        client = self._client
        data = {"access_token": client._token, "refresh_token": client._refresh_token}
        self._cache.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = self._cache.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, self._cache)

    def forget(self) -> None:
        """Drop the cached session (the next call logs in again)."""
        self._client = None
        self._cache.unlink(missing_ok=True)
