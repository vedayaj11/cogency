"""Build a SalesforceClient from worker settings.

For MVP we use a single global integration credential per worker process. In
production, per-tenant creds will live in the `salesforce_connections` table
and we'll resolve at activity start.
"""

from __future__ import annotations

from pathlib import Path

from salesforce import (
    SalesforceClient,
    SalesforceCredentials,
    auth_from_credentials,
)

from worker.config import WorkerSettings


def build_salesforce_client(settings: WorkerSettings) -> SalesforceClient:
    private_key_path: Path | None = None
    if settings.sf_jwt_private_key_path:
        candidate = Path(settings.sf_jwt_private_key_path)
        if candidate.exists():
            private_key_path = candidate

    creds = SalesforceCredentials(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret or None,
        username=settings.sf_username or None,
        private_key_path=private_key_path,
        login_url=settings.sf_login_url,
        token_url=settings.sf_token_url,
    )
    auth = auth_from_credentials(creds)
    return SalesforceClient(auth=auth, api_version=settings.sf_api_version)
