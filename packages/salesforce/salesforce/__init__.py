"""Salesforce integration: hybrid read-from-local, write-to-Salesforce.

See PRD §7 for the architectural pattern.
"""

from salesforce.auth import JWTBearerAuth, SalesforceCredentials
from salesforce.bulk import BulkClient
from salesforce.pubsub import PubSubConsumer
from salesforce.writer import OutboxWriter

__all__ = [
    "JWTBearerAuth",
    "SalesforceCredentials",
    "BulkClient",
    "PubSubConsumer",
    "OutboxWriter",
]
