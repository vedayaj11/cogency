"""SQLAlchemy async session + ORM models.

Models are split by schema (`sf` mirror, `cogency` native). Migrations live in
`/db/migrations`; this package mirrors them as ORM types for app code.
"""

from db.models import (
    AOP,
    AgentInboxItem,
    AOPRun,
    AOPStep,
    AOPVersion,
    AuditEvent,
    KnowledgeChunk,
    KnowledgeSource,
    SfAccount,
    SfCase,
    SfCaseComment,
    SfContact,
    SfEmailMessage,
    SfKnowledgeArticleVersion,
    SfSyncState,
    SfTask,
    SfUser,
    Tenant,
)
from db.repositories import (
    AOPRepository,
    AOPRunRepository,
    CaseCommentRepository,
    CaseRepository,
    EmailMessageRepository,
    InboxRepository,
    KnowledgeRepository,
    SyncStateRepository,
    TaskRepository,
)
from db.session import Base, async_session, dispose_engine, get_engine, get_sessionmaker

__all__ = [
    "Base",
    "async_session",
    "dispose_engine",
    "get_engine",
    "get_sessionmaker",
    "CaseRepository",
    "EmailMessageRepository",
    "CaseCommentRepository",
    "TaskRepository",
    "KnowledgeRepository",
    "SyncStateRepository",
    "AOPRepository",
    "AOPRunRepository",
    "InboxRepository",
    "SfCase",
    "SfContact",
    "SfAccount",
    "SfUser",
    "SfEmailMessage",
    "SfCaseComment",
    "SfTask",
    "SfKnowledgeArticleVersion",
    "SfSyncState",
    "Tenant",
    "AOP",
    "AOPVersion",
    "AOPRun",
    "AOPStep",
    "AgentInboxItem",
    "AuditEvent",
    "KnowledgeSource",
    "KnowledgeChunk",
]
