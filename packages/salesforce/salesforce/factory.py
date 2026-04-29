"""Convenience builder so apps don't have to thread Auth + Credentials by hand.

Both the API (for inbox-approve re-fire) and the worker (for backfill +
CDC) need a client; settings shapes differ slightly so we accept individual
fields rather than a Settings object.
"""

from __future__ import annotations

from pathlib import Path

from salesforce.auth import SalesforceCredentials, auth_from_credentials
from salesforce.client import SalesforceClient


def build_salesforce_client(
    *,
    client_id: str,
    client_secret: str | None = None,
    username: str | None = None,
    private_key_path: str | None = None,
    login_url: str = "https://login.salesforce.com",
    token_url: str = "https://login.salesforce.com/services/oauth2/token",
    api_version: str = "62.0",
) -> SalesforceClient:
    key_path: Path | None = None
    if private_key_path:
        candidate = Path(private_key_path)
        if candidate.exists():
            key_path = candidate

    creds = SalesforceCredentials(
        client_id=client_id,
        client_secret=client_secret or None,
        username=username or None,
        private_key_path=key_path,
        login_url=login_url,
        token_url=token_url,
    )
    auth = auth_from_credentials(creds)
    return SalesforceClient(auth=auth, api_version=api_version)
