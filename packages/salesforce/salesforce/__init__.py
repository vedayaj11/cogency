"""Salesforce integration: hybrid read-from-local, write-to-Salesforce.

See PRD §7 for the architectural pattern.
"""

from salesforce.auth import (
    AuthStrategy,
    ClientCredentialsAuth,
    JWTBearerAuth,
    SalesforceCredentials,
    auth_from_credentials,
)
from salesforce.bulk import parse_csv_chunk, parse_csv_stream
from salesforce.client import (
    ConflictError,
    RateLimitInfo,
    SalesforceAPIError,
    SalesforceClient,
)
from salesforce.factory import build_salesforce_client
from salesforce.pubsub import PubSubConsumer
from salesforce.writer import OutboxWriter, WriteOutcome

__all__ = [
    "AuthStrategy",
    "JWTBearerAuth",
    "ClientCredentialsAuth",
    "SalesforceCredentials",
    "auth_from_credentials",
    "SalesforceClient",
    "SalesforceAPIError",
    "ConflictError",
    "RateLimitInfo",
    "OutboxWriter",
    "WriteOutcome",
    "PubSubConsumer",
    "build_salesforce_client",
    "parse_csv_chunk",
    "parse_csv_stream",
]
