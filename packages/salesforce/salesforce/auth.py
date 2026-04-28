"""Salesforce OAuth flows.

PRD §7.4 chooses JWT Bearer per org as the production path. We also expose
ClientCredentials for dev/test convenience when the org has it enabled — it
avoids the need to upload a private key to Salesforce.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jwt
from pydantic import BaseModel


class SalesforceCredentials(BaseModel):
    """Tenant-level OAuth credentials.

    `private_key_path` is required for JWT Bearer; `client_secret` is required
    for ClientCredentials. `username` is the integration user for JWT.
    """

    client_id: str
    username: str | None = None
    client_secret: str | None = None
    private_key_path: Path | None = None
    login_url: str = "https://login.salesforce.com"
    token_url: str = "https://login.salesforce.com/services/oauth2/token"


@dataclass
class CachedToken:
    access_token: str
    instance_url: str
    issued_at: float
    expires_at: float


class AuthStrategy(ABC):
    @abstractmethod
    async def access_token(self) -> CachedToken: ...


@dataclass
class JWTBearerAuth(AuthStrategy):
    """Mints + caches a Salesforce access token via JWT Bearer.

    Salesforce caps token issuance to once per 20 minutes per integration user;
    we cache for ~110 min and refresh on demand.
    """

    creds: SalesforceCredentials
    _cached: CachedToken | None = field(default=None, init=False, repr=False)

    async def access_token(self) -> CachedToken:
        now = time.time()
        if self._cached and now < self._cached.expires_at - 60:
            return self._cached
        return await self._mint()

    async def _mint(self) -> CachedToken:
        if not (self.creds.private_key_path and self.creds.username):
            raise ValueError("JWTBearerAuth requires private_key_path and username")
        assertion = self._sign_assertion()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self.creds.token_url,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            payload = resp.json()
        token = CachedToken(
            access_token=payload["access_token"],
            instance_url=payload["instance_url"],
            issued_at=time.time(),
            expires_at=time.time() + 110 * 60,
        )
        self._cached = token
        return token

    def _sign_assertion(self) -> str:
        assert self.creds.private_key_path and self.creds.username
        private_key = self.creds.private_key_path.read_text()
        now = datetime.now(tz=UTC).timestamp()
        return jwt.encode(
            {
                "iss": self.creds.client_id,
                "sub": self.creds.username,
                "aud": self.creds.login_url,
                "exp": int(now) + 180,
            },
            private_key,
            algorithm="RS256",
        )


@dataclass
class ClientCredentialsAuth(AuthStrategy):
    """OAuth 2.0 Client Credentials flow.

    Available when the connected app has "Enable Client Credentials Flow" set
    and a Run As user assigned. Useful for dev/test; for production prefer
    JWT Bearer (per PRD §7.4).
    """

    creds: SalesforceCredentials
    _cached: CachedToken | None = field(default=None, init=False, repr=False)

    async def access_token(self) -> CachedToken:
        now = time.time()
        if self._cached and now < self._cached.expires_at - 60:
            return self._cached
        return await self._mint()

    async def _mint(self) -> CachedToken:
        if not (self.creds.client_secret and self.creds.client_id):
            raise ValueError("ClientCredentialsAuth requires client_id and client_secret")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self.creds.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.creds.client_id,
                    "client_secret": self.creds.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            payload = resp.json()
        token = CachedToken(
            access_token=payload["access_token"],
            instance_url=payload["instance_url"],
            issued_at=time.time(),
            expires_at=time.time() + 110 * 60,
        )
        self._cached = token
        return token


def auth_from_credentials(creds: SalesforceCredentials) -> AuthStrategy:
    """Pick a flow based on what's populated.

    JWT preferred; falls back to ClientCredentials if no key path is set.
    """
    if creds.private_key_path and creds.username and Path(creds.private_key_path).exists():
        return JWTBearerAuth(creds)
    if creds.client_secret:
        return ClientCredentialsAuth(creds)
    raise ValueError(
        "No usable Salesforce auth: provide either (private_key_path + username) "
        "for JWT Bearer or client_secret for Client Credentials."
    )
