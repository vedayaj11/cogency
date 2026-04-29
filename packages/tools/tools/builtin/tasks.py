"""Tasks + coordination tools.

`create_followup_task` and `schedule_callback` create Tasks tied to a Case.
`assign_to_queue` reassigns a Case (alias of assign_case but semantically
clearer for queue routing).
`create_escalation` creates a Task tagged as escalation and reassigns.
`attach_file_to_case` is a placeholder pending real ContentVersion handling.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from salesforce import OutboxWriter

from tools.registry import Tool, ToolContext


# ---------- create_followup_task ----------

class CreateFollowupTaskInput(BaseModel):
    case_id: str
    subject: str
    description: str | None = None
    activity_date: str | None = Field(
        default=None,
        description="Due date in YYYY-MM-DD format.",
    )
    priority: str = "Normal"
    owner_id: str | None = None


class CreateFollowupTaskOutput(BaseModel):
    succeeded: bool
    task_id: str | None = None
    error: str | None = None


async def create_followup_task(
    ctx: ToolContext, p: CreateFollowupTaskInput
) -> CreateFollowupTaskOutput:
    if ctx.sf_client is None:
        return CreateFollowupTaskOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    fields = {
        "WhatId": p.case_id,
        "Subject": p.subject,
        "Description": p.description,
        "ActivityDate": p.activity_date,
        "Priority": p.priority,
        "Status": "Not Started",
        "Type": "Other",
    }
    if p.owner_id:
        fields["OwnerId"] = p.owner_id
    fields = {k: v for k, v in fields.items() if v is not None}
    outcomes = await writer.composite_upsert("Task", [fields])
    if not outcomes:
        return CreateFollowupTaskOutput(succeeded=False, error="empty outcome")
    out = outcomes[0]
    return CreateFollowupTaskOutput(
        succeeded=out.succeeded, task_id=out.record_id or None, error=out.error
    )


CREATE_FOLLOWUP_TASK = Tool(
    name="create_followup_task",
    description="Create a follow-up Task tied to a Case (with optional due date + owner).",
    required_scopes=["task.create"],
    input_schema=CreateFollowupTaskInput,
    output_schema=CreateFollowupTaskOutput,
    func=create_followup_task,
)


# ---------- schedule_callback ----------

class ScheduleCallbackInput(BaseModel):
    case_id: str
    callback_date: str = Field(description="YYYY-MM-DD")
    note: str | None = None
    owner_id: str | None = None


class ScheduleCallbackOutput(BaseModel):
    succeeded: bool
    task_id: str | None = None
    error: str | None = None


async def schedule_callback(
    ctx: ToolContext, p: ScheduleCallbackInput
) -> ScheduleCallbackOutput:
    """Specialization of create_followup_task with Type=Call."""
    if ctx.sf_client is None:
        return ScheduleCallbackOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    fields = {
        "WhatId": p.case_id,
        "Subject": "Customer callback",
        "Description": p.note,
        "ActivityDate": p.callback_date,
        "Priority": "High",
        "Status": "Not Started",
        "Type": "Call",
    }
    if p.owner_id:
        fields["OwnerId"] = p.owner_id
    fields = {k: v for k, v in fields.items() if v is not None}
    outcomes = await writer.composite_upsert("Task", [fields])
    if not outcomes:
        return ScheduleCallbackOutput(succeeded=False, error="empty outcome")
    out = outcomes[0]
    return ScheduleCallbackOutput(
        succeeded=out.succeeded, task_id=out.record_id or None, error=out.error
    )


SCHEDULE_CALLBACK = Tool(
    name="schedule_callback",
    description="Schedule a customer callback by creating a Task of Type=Call with a due date.",
    required_scopes=["task.create"],
    input_schema=ScheduleCallbackInput,
    output_schema=ScheduleCallbackOutput,
    func=schedule_callback,
)


# ---------- assign_to_queue ----------

class AssignToQueueInput(BaseModel):
    case_id: str
    queue_id: str = Field(description="Salesforce Group (Queue) Id.")


class AssignToQueueOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def assign_to_queue(
    ctx: ToolContext, p: AssignToQueueInput
) -> AssignToQueueOutput:
    if ctx.sf_client is None:
        return AssignToQueueOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)
    out = await writer.patch_record("Case", p.case_id, {"OwnerId": p.queue_id})
    return AssignToQueueOutput(succeeded=out.succeeded, error=out.error)


ASSIGN_TO_QUEUE = Tool(
    name="assign_to_queue",
    description="Reassign a Case to a Salesforce Queue (Group). Used for specialist routing (legal, billing, security).",
    required_scopes=["case.update"],
    input_schema=AssignToQueueInput,
    output_schema=AssignToQueueOutput,
    func=assign_to_queue,
)


# ---------- create_escalation ----------

class CreateEscalationInput(BaseModel):
    case_id: str
    target_owner_id: str = Field(description="User or Queue Id receiving the escalation.")
    reason: str
    new_priority: str | None = "High"


class CreateEscalationOutput(BaseModel):
    succeeded: bool
    task_id: str | None = None
    error: str | None = None


async def create_escalation(
    ctx: ToolContext, p: CreateEscalationInput
) -> CreateEscalationOutput:
    """Two-step: create a 'Case escalated' Task and reassign the Case.
    Gated by default — an executive should approve every escalation."""
    if ctx.sf_client is None:
        return CreateEscalationOutput(succeeded=False, error="no Salesforce client")
    writer = OutboxWriter(client=ctx.sf_client)

    task_outcomes = await writer.composite_upsert(
        "Task",
        [
            {
                "WhatId": p.case_id,
                "Subject": "Case escalated",
                "Description": p.reason,
                "Priority": "High",
                "Status": "Not Started",
                "Type": "Other",
                "OwnerId": p.target_owner_id,
            }
        ],
    )
    task_id = task_outcomes[0].record_id if task_outcomes else None

    case_fields: dict[str, str | None] = {"OwnerId": p.target_owner_id}
    if p.new_priority:
        case_fields["Priority"] = p.new_priority
    out = await writer.patch_record("Case", p.case_id, case_fields)

    return CreateEscalationOutput(
        succeeded=bool(task_id) and out.succeeded,
        task_id=task_id,
        error=out.error,
    )


CREATE_ESCALATION = Tool(
    name="create_escalation",
    description="Escalate a Case: create an escalation Task + reassign owner + bump priority. Gated by default.",
    required_scopes=["case.update", "task.create"],
    input_schema=CreateEscalationInput,
    output_schema=CreateEscalationOutput,
    func=create_escalation,
    requires_approval=True,
)


# ---------- attach_file_to_case (placeholder) ----------

class AttachFileInput(BaseModel):
    case_id: str
    file_url: str = Field(description="Pre-uploaded ContentVersion or external URL.")
    label: str | None = None


class AttachFileOutput(BaseModel):
    succeeded: bool
    error: str | None = None


async def attach_file_to_case(
    ctx: ToolContext, p: AttachFileInput
) -> AttachFileOutput:
    """Placeholder: real ContentDocumentLink wiring lands when intake supports
    multi-modal uploads (PRD §6.1 v3). For now, we record a ContentVersion
    pointing at the URL is left to the operator; this tool just no-ops with
    a clear message so the agent doesn't hallucinate success."""
    return AttachFileOutput(
        succeeded=False,
        error="attach_file_to_case is not yet implemented; use add_case_comment with a link to the file.",
    )


ATTACH_FILE_TO_CASE = Tool(
    name="attach_file_to_case",
    description="Attach a file to a Case (NOT YET IMPLEMENTED — planned for milestone 8 with ContentVersion ingestion). Returns succeeded=false with explanation.",
    required_scopes=["case.update"],
    input_schema=AttachFileInput,
    output_schema=AttachFileOutput,
    func=attach_file_to_case,
)


__all__ = [
    "CREATE_FOLLOWUP_TASK",
    "SCHEDULE_CALLBACK",
    "ASSIGN_TO_QUEUE",
    "CREATE_ESCALATION",
    "ATTACH_FILE_TO_CASE",
]
