"""Build a SalesforceClient from worker settings.

Thin wrapper over `salesforce.build_salesforce_client` that pulls fields
from `WorkerSettings`. The API has its own equivalent shim (in app.deps)
that pulls from `Settings`.
"""

from __future__ import annotations

# Import under an alias so the public `build_salesforce_client` name in
# this module (the settings-aware shim) doesn't shadow the underlying
# salesforce-package function we delegate to. (An earlier version
# rebound the symbol after the wrapper was defined, causing the wrapper
# to recurse into itself with the wrong kwargs.)
from salesforce import SalesforceClient
from salesforce import build_salesforce_client as _build_sf_client

from worker.config import WorkerSettings


def build_salesforce_client(settings: WorkerSettings) -> SalesforceClient:
    """Construct a SalesforceClient from a WorkerSettings instance.

    The activity layer imports this name. Internally we delegate to the
    salesforce package's primitive builder which accepts individual
    fields.
    """
    return _build_sf_client(
        client_id=settings.sf_client_id,
        client_secret=settings.sf_client_secret or None,
        username=settings.sf_username or None,
        private_key_path=settings.sf_jwt_private_key_path,
        login_url=settings.sf_login_url,
        token_url=settings.sf_token_url,
        api_version=settings.sf_api_version,
    )


# Backwards-compatible alias for older import sites (apps/api/app/deps.py
# may still reference this name).
build_salesforce_client_from_settings = build_salesforce_client
