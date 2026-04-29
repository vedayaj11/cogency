"""Build a SalesforceClient from worker settings.

Thin wrapper over `salesforce.build_salesforce_client` that pulls fields
from `WorkerSettings`. The API has its own equivalent shim (in app.deps)
that pulls from `Settings`.
"""

from __future__ import annotations

from salesforce import SalesforceClient, build_salesforce_client

from worker.config import WorkerSettings


def build_salesforce_client_from_settings(settings: WorkerSettings) -> SalesforceClient:
    return build_salesforce_client(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret or None,
        username=settings.sf_username or None,
        private_key_path=settings.sf_jwt_private_key_path,
        login_url=settings.sf_login_url,
        token_url=settings.sf_token_url,
        api_version=settings.sf_api_version,
    )


# Backwards-compatible alias used by existing activities.
build_salesforce_client = build_salesforce_client_from_settings  # type: ignore[assignment]
