"""Write tools — case-centric. Most route through OutboxWriter (PRD §7.5).

Tiered authority:
- `requires_approval=True` for terminal/external-facing actions: close_case,
  archive_case, link_case_as_duplicate, link_cases_parent_child.
- `requires_approval=False` for incremental field updates: assign_case,
  update_case_priority, update_case_category, set_sla_target,
  update_case_field. AOPs can override per-call via guardrails.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from salesforce import OutboxWriter

from tools.registry import Tool, ToolContext


# ---------- create_case ----------

class CreateCaseInput(BaseModel):
    subject: str
    description: str | None = None
    contact_id: str | None = None
    account_id: str | None = None
    priority: str = "Medium"
    origin: str | None = None
    status: str = "New"


class CreateCaseOutput(BaseModel):
    succeeded: bool
    case_id: str | None = None
    error: str | None = None


async def create_case(ctx: ToolContext, p: CreateCaseInput) -> CreateCaseOutput:
    if ctx.sf_client is None:
        return CreateCaseOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    fields = {
        "Subject": p.subject,
        "Description": p.description,
        "ContactId": p.contact_id,
        "AccountId": p.account_id,
        "Priority": p.priority,
        "Origin": p.origin,
        "Status": p.status,
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    outcomes = await writer.composite_upsert("Case", [fields])
    if not outcomes:
        return CreateCaseOutput(succeeded=False, error="empty outcome")
    out = outcomes[0]
    return CreateCaseOutput(
        succeeded=out.succeeded, case_id=out.record_id or None, error=out.error
    )


CREATE_CASE = Tool(
    name="create_case",
    description="Create a new Case in Salesforce. Use when intake produces a structured ticket and the source case doesn't already exist.",
    required_scopes=["case.create"],
    input_schema=CreateCaseInput,
    output_schema=CreateCaseOutput,
    func=create_case,
)


# ---------- update_case_field ----------

# Allowed field names for the general updater. Lock-down: arbitrary field
# writes are dangerous; whitelist the ones an executive would touch.
_UPDATABLE_FIELDS = {
    "Subject",
    "Description",
    "Priority",
    "Status",
    "Origin",
    "Type",
    "Reason",
    "OwnerId",
    "ContactId",
    "AccountId",
}


class UpdateCaseFieldInput(BaseModel):
    case_id: str
    field: str = Field(description="Salesforce field API name (whitelisted).")
    value: str | int | float | bool | None


class UpdateCaseFieldOutput(BaseModel):
    succeeded: bool
    conflict: bool = False
    error: str | None = None


async def update_case_field(
    ctx: ToolContext, p: UpdateCaseFieldInput
) -> UpdateCaseFieldOutput:
    if p.field not in _UPDATABLE_FIELDS:
        return UpdateCaseFieldOutput(
            succeeded=False,
            error=f"field '{p.field}' is not in the writable allowlist {sorted(_UPDATABLE_FIELDS)}",
        )
    if ctx.sf_client is None:
        return UpdateCaseFieldOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record("Case", p.case_id, {p.field: p.value})
    return UpdateCaseFieldOutput(
        succeeded=out.succeeded, conflict=out.conflict, error=out.error
    )


UPDATE_CASE_FIELD = Tool(
    name="update_case_field",
    description="Set a single Case field by API name (whitelisted: Subject, Description, Priority, Status, Origin, Type, Reason, OwnerId, ContactId, AccountId).",
    required_scopes=["case.update"],
    input_schema=UpdateCaseFieldInput,
    output_schema=UpdateCaseFieldOutput,
    func=update_case_field,
)


# ---------- assign_case ----------

class AssignCaseInput(BaseModel):
    case_id: str
    owner_id: str = Field(description="Salesforce User Id or Queue Id.")


class AssignCaseOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def assign_case(ctx: ToolContext, p: AssignCaseInput) -> AssignCaseOutput:
    if ctx.sf_client is None:
        return AssignCaseOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record("Case", p.case_id, {"OwnerId": p.owner_id})
    return AssignCaseOutput(succeeded=out.succeeded, error=out.error)


ASSIGN_CASE = Tool(
    name="assign_case",
    description="Reassign a Case to a User or Queue by setting OwnerId.",
    required_scopes=["case.update"],
    input_schema=AssignCaseInput,
    output_schema=AssignCaseOutput,
    func=assign_case,
)


# ---------- update_case_priority ----------

class UpdateCasePriorityInput(BaseModel):
    case_id: str
    priority: str = Field(description="Picklist value, e.g. Low / Medium / High / Critical.")


class UpdateCasePriorityOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def update_case_priority(
    ctx: ToolContext, p: UpdateCasePriorityInput
) -> UpdateCasePriorityOutput:
    if ctx.sf_client is None:
        return UpdateCasePriorityOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record("Case", p.case_id, {"Priority": p.priority})
    return UpdateCasePriorityOutput(succeeded=out.succeeded, error=out.error)


UPDATE_CASE_PRIORITY = Tool(
    name="update_case_priority",
    description="Set Case.Priority. Use when triage or evidence shifts urgency.",
    required_scopes=["case.update"],
    input_schema=UpdateCasePriorityInput,
    output_schema=UpdateCasePriorityOutput,
    func=update_case_priority,
)


# ---------- update_case_category (Type) ----------

class UpdateCaseCategoryInput(BaseModel):
    case_id: str
    type: str = Field(description="Salesforce Case.Type picklist value.")


class UpdateCaseCategoryOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def update_case_category(
    ctx: ToolContext, p: UpdateCaseCategoryInput
) -> UpdateCaseCategoryOutput:
    if ctx.sf_client is None:
        return UpdateCaseCategoryOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record("Case", p.case_id, {"Type": p.type})
    return UpdateCaseCategoryOutput(succeeded=out.succeeded, error=out.error)


UPDATE_CASE_CATEGORY = Tool(
    name="update_case_category",
    description="Set Case.Type — the structured category (Question, Problem, Feature Request, …).",
    required_scopes=["case.update"],
    input_schema=UpdateCaseCategoryInput,
    output_schema=UpdateCaseCategoryOutput,
    func=update_case_category,
)


# ---------- set_sla_target ----------

class SetSLATargetInput(BaseModel):
    case_id: str
    target_iso: str = Field(description="ISO-8601 datetime; will be written to a custom SLA target field if configured.")


class SetSLATargetOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def set_sla_target(
    ctx: ToolContext, p: SetSLATargetInput
) -> SetSLATargetOutput:
    if ctx.sf_client is None:
        return SetSLATargetOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    # Convention: tenants store SLA target on Case.SLA_Target__c. Surface
    # error clearly if the field doesn't exist on this org.
    out = await writer.patch_record(
        "Case", p.case_id, {"SLA_Target__c": p.target_iso}
    )
    return SetSLATargetOutput(succeeded=out.succeeded, error=out.error)


SET_SLA_TARGET = Tool(
    name="set_sla_target",
    description="Set the SLA target on a Case (tenant-specific custom field SLA_Target__c).",
    required_scopes=["case.update"],
    input_schema=SetSLATargetInput,
    output_schema=SetSLATargetOutput,
    func=set_sla_target,
)


# ---------- close_case ----------

class CloseCaseInput(BaseModel):
    case_id: str
    resolution_summary: str = Field(
        description="Short reason for closure; written to Case.Description as a closure note."
    )


class CloseCaseOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def close_case(ctx: ToolContext, p: CloseCaseInput) -> CloseCaseOutput:
    if ctx.sf_client is None:
        return CloseCaseOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record(
        "Case",
        p.case_id,
        {"Status": "Closed", "Description": p.resolution_summary},
    )
    return CloseCaseOutput(succeeded=out.succeeded, error=out.error)


CLOSE_CASE = Tool(
    name="close_case",
    description="Mark a Case as Closed with a resolution summary. High-stakes — gated by default; an inbox approval re-fires the action.",
    required_scopes=["case.update"],
    input_schema=CloseCaseInput,
    output_schema=CloseCaseOutput,
    func=close_case,
    requires_approval=True,
)


# ---------- archive_case ----------

class ArchiveCaseInput(BaseModel):
    case_id: str
    reason: str


class ArchiveCaseOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def archive_case(ctx: ToolContext, p: ArchiveCaseInput) -> ArchiveCaseOutput:
    if ctx.sf_client is None:
        return ArchiveCaseOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    # Convention: Archived__c custom flag. Falls through to caller's audit log.
    out = await writer.patch_record(
        "Case",
        p.case_id,
        {"Status": "Closed", "Archived__c": True, "Description": p.reason},
    )
    return ArchiveCaseOutput(succeeded=out.succeeded, error=out.error)


ARCHIVE_CASE = Tool(
    name="archive_case",
    description="Archive a Case (closed + Archived__c=true). Soft delete. Gated.",
    required_scopes=["case.update"],
    input_schema=ArchiveCaseInput,
    output_schema=ArchiveCaseOutput,
    func=archive_case,
    requires_approval=True,
)


# ---------- link_case_as_duplicate ----------

class LinkDuplicateInput(BaseModel):
    case_id: str
    duplicate_of_case_id: str


class LinkDuplicateOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def link_case_as_duplicate(
    ctx: ToolContext, p: LinkDuplicateInput
) -> LinkDuplicateOutput:
    if ctx.sf_client is None:
        return LinkDuplicateOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    # Convention: store the canonical ID in DuplicateOf__c custom field.
    out = await writer.patch_record(
        "Case",
        p.case_id,
        {"DuplicateOf__c": p.duplicate_of_case_id, "Status": "Closed"},
    )
    return LinkDuplicateOutput(succeeded=out.succeeded, error=out.error)


LINK_CASE_AS_DUPLICATE = Tool(
    name="link_case_as_duplicate",
    description="Mark a Case as a duplicate of another and close it. Gated.",
    required_scopes=["case.update"],
    input_schema=LinkDuplicateInput,
    output_schema=LinkDuplicateOutput,
    func=link_case_as_duplicate,
    requires_approval=True,
)


# ---------- link_cases_parent_child ----------

class LinkParentChildInput(BaseModel):
    parent_case_id: str
    child_case_id: str


class LinkParentChildOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def link_cases_parent_child(
    ctx: ToolContext, p: LinkParentChildInput
) -> LinkParentChildOutput:
    if ctx.sf_client is None:
        return LinkParentChildOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record(
        "Case", p.child_case_id, {"ParentId": p.parent_case_id}
    )
    return LinkParentChildOutput(succeeded=out.succeeded, error=out.error)


LINK_CASES_PARENT_CHILD = Tool(
    name="link_cases_parent_child",
    description="Establish a parent-child relationship between two Cases (sets ParentId on the child).",
    required_scopes=["case.update"],
    input_schema=LinkParentChildInput,
    output_schema=LinkParentChildOutput,
    func=link_cases_parent_child,
)


__all__ = [
    "CREATE_CASE",
    "UPDATE_CASE_FIELD",
    "ASSIGN_CASE",
    "UPDATE_CASE_PRIORITY",
    "UPDATE_CASE_CATEGORY",
    "SET_SLA_TARGET",
    "CLOSE_CASE",
    "ARCHIVE_CASE",
    "LINK_CASE_AS_DUPLICATE",
    "LINK_CASES_PARENT_CHILD",
]
