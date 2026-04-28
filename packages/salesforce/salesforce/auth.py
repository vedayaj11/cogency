"""JWT Bearer OAuth flow for Salesforce.

PRD §7.4: dedicated integration user, JWT Bearer per org, access tokens cached
~2h, never request more than one per 20 min per Salesforce guidance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jwt
from pydantic import BaseModel


class SalesforceCredentials(BaseModel):
    client_id: str
    username: str
    private_key_path: Path
    login_url: str = "https://login.salesforce.com"


@dataclass
class CachedToken:
    access_token: str
    instance_url: str
    issued_at: float
    expires_at: float


@dataclass
class JWTBearerAuth:
    """Mints + caches a Salesforce access token via the JWT Bearer flow.

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
        assertion = self._sign_assertion()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.creds.login_url}/services/oauth2/token",
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
