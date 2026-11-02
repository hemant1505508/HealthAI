from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

MIN_JUSTIFICATION_LENGTH = 20


class AccessItem(BaseModel):
    system: str
    permission: str


class RoleProfile(BaseModel):
    job_role: str
    department: str
    access: list[AccessItem]


class ExtraAccessItem(AccessItem):
    justification: str = Field(
        description="Business reason for access beyond the role profile; required for every extra item (AC2)."
    )

    @field_validator("justification")
    @classmethod
    def _justification_given(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_JUSTIFICATION_LENGTH:
            raise ValueError(f"a business justification of at least {MIN_JUSTIFICATION_LENGTH} characters is required")
        return v


class AccessRequestCreate(BaseModel):
    starter_id: str = Field(min_length=1, description="Onboarding record id of the starter, not their name.")
    requested_by: str = Field(min_length=1, description="User id of the Hiring Manager.")
    job_role: str
    department: str
    extra_access: list[ExtraAccessItem] = Field(default_factory=list)


class TaskKind(str, Enum):
    SYSTEM_OWNER = "system_owner"
    ADDITIONAL = "additional_approval"


class TaskStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestedItem(AccessItem):
    extra: bool = False
    justification: str | None = None


class ApprovalTask(BaseModel):
    id: str
    request_id: str
    starter_id: str
    kind: TaskKind
    approver: str
    items: list[RequestedItem]
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime


class AccessRequest(BaseModel):
    id: str
    starter_id: str
    requested_by: str
    job_role: str
    department: str
    items: list[RequestedItem]
    approval_task_ids: list[str]
    created_at: datetime
