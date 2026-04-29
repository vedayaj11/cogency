"""Built-in tool catalog for Cogency.

Tools are grouped by surface:
- `sf_cases.py`         core case write tools (existing): lookup_case, add_case_comment, update_case_status
- `sf_contacts.py`      contact reads + identity verification
- `refund.py`           refund proposal (no side effects)
- `cases_read.py`       case-centric reads: list, search, comments, emails, history, related, metrics
- `entities.py`         entity reads: contact-cases, account, account-cases, account-health
- `cases_write.py`      case-centric writes: create, update field/priority/category/SLA/owner, close, archive, link
- `emails.py`           draft + send email reply
- `tasks.py`            follow-up tasks, callbacks, queue routing, escalations
- `analyze.py`          LLM-backed: classify, sentiment, summarize, similar-search, duplicate detection

Apps call `build_default_registry()` to get a Registry pre-populated with
the full catalog. AOPs control which subset is exposed to the model via
`granted_scopes`.
"""

from tools.builtin.analyze import (
    CLASSIFY_CASE,
    DETECT_DUPLICATE_CASES,
    EXTRACT_SENTIMENT,
    SEARCH_SIMILAR_CASES,
    SUMMARIZE_CASE,
)
from tools.builtin.cases_read import (
    GET_CASE_HISTORY,
    GET_CASE_METRICS,
    LIST_CASE_COMMENTS,
    LIST_CASE_EMAILS,
    LIST_CASES,
    LIST_RELATED_CASES,
    SEARCH_CASES,
)
from tools.builtin.cases_write import (
    ARCHIVE_CASE,
    ASSIGN_CASE,
    CLOSE_CASE,
    CREATE_CASE,
    LINK_CASE_AS_DUPLICATE,
    LINK_CASES_PARENT_CHILD,
    SET_SLA_TARGET,
    UPDATE_CASE_CATEGORY,
    UPDATE_CASE_FIELD,
    UPDATE_CASE_PRIORITY,
)
from tools.builtin.emails import DRAFT_EMAIL_REPLY, SEND_EMAIL_REPLY
from tools.builtin.entities import (
    GET_ACCOUNT,
    GET_ACCOUNT_HEALTH,
    LIST_ACCOUNT_CASES,
    LIST_CONTACT_CASES,
)
from tools.builtin.refund import PROPOSE_REFUND
from tools.builtin.sf_cases import ADD_CASE_COMMENT, LOOKUP_CASE, UPDATE_CASE_STATUS
from tools.builtin.sf_contacts import LOOKUP_CONTACT, VERIFY_CUSTOMER_IDENTITY
from tools.builtin.tasks import (
    ASSIGN_TO_QUEUE,
    ATTACH_FILE_TO_CASE,
    CREATE_ESCALATION,
    CREATE_FOLLOWUP_TASK,
    SCHEDULE_CALLBACK,
)
from tools.registry import Registry


_ALL_TOOLS = [
    # Reads — existing
    LOOKUP_CASE,
    LOOKUP_CONTACT,
    VERIFY_CUSTOMER_IDENTITY,
    # Reads — case-centric
    LIST_CASES,
    SEARCH_CASES,
    LIST_CASE_COMMENTS,
    LIST_CASE_EMAILS,
    GET_CASE_HISTORY,
    LIST_RELATED_CASES,
    GET_CASE_METRICS,
    # Reads — entities
    LIST_CONTACT_CASES,
    GET_ACCOUNT,
    LIST_ACCOUNT_CASES,
    GET_ACCOUNT_HEALTH,
    # Writes — case
    ADD_CASE_COMMENT,
    UPDATE_CASE_STATUS,
    CREATE_CASE,
    UPDATE_CASE_FIELD,
    ASSIGN_CASE,
    UPDATE_CASE_PRIORITY,
    UPDATE_CASE_CATEGORY,
    SET_SLA_TARGET,
    CLOSE_CASE,
    ARCHIVE_CASE,
    LINK_CASE_AS_DUPLICATE,
    LINK_CASES_PARENT_CHILD,
    # Writes — email
    DRAFT_EMAIL_REPLY,
    SEND_EMAIL_REPLY,
    # Writes — tasks / coordination
    CREATE_FOLLOWUP_TASK,
    SCHEDULE_CALLBACK,
    ASSIGN_TO_QUEUE,
    CREATE_ESCALATION,
    ATTACH_FILE_TO_CASE,
    # Analyze
    PROPOSE_REFUND,
    CLASSIFY_CASE,
    EXTRACT_SENTIMENT,
    SUMMARIZE_CASE,
    SEARCH_SIMILAR_CASES,
    DETECT_DUPLICATE_CASES,
]


__all__ = [
    "build_default_registry",
    # also re-export the constants for callers that want them by name
    *(t.name.upper() for t in _ALL_TOOLS),
]


def build_default_registry() -> Registry:
    return Registry().extend(_ALL_TOOLS)
