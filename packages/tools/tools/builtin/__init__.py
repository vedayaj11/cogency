"""Built-in tool catalog.

Tools split by surface:
- sf_cases: read/write Cases via local mirror + SF outbox writer.
- sf_contacts: read Contacts; verify customer identity.
- refund: structured refund proposal (no side effects).

Apps call `build_default_registry()` to get a Registry pre-populated with
every built-in tool.
"""

from tools.builtin.refund import PROPOSE_REFUND
from tools.builtin.sf_cases import ADD_CASE_COMMENT, LOOKUP_CASE, UPDATE_CASE_STATUS
from tools.builtin.sf_contacts import LOOKUP_CONTACT, VERIFY_CUSTOMER_IDENTITY
from tools.registry import Registry

__all__ = [
    "build_default_registry",
    "LOOKUP_CASE",
    "ADD_CASE_COMMENT",
    "UPDATE_CASE_STATUS",
    "LOOKUP_CONTACT",
    "VERIFY_CUSTOMER_IDENTITY",
    "PROPOSE_REFUND",
]


def build_default_registry() -> Registry:
    return Registry().extend(
        [
            LOOKUP_CASE,
            ADD_CASE_COMMENT,
            UPDATE_CASE_STATUS,
            LOOKUP_CONTACT,
            VERIFY_CUSTOMER_IDENTITY,
            PROPOSE_REFUND,
        ]
    )
