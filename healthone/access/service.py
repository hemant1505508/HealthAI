from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .catalogue import CatalogueError, RbacCatalogue
from .models import (
    AccessRequest,
    AccessRequestCreate,
    ApprovalTask,
    RequestedItem,
    RoleProfile,
    TaskKind,
)

# POL-CA-01 v1.2 (Audit Logging): every request and approval task is recorded.
# POL-SP-01 v2.0 (PII): audit entries carry ids and system names only, never names or justification text.
audit_log = logging.getLogger("healthone.audit")


class AccessRequestError(ValueError):
    pass


class AccessRequestService:
    def __init__(self, catalogue: RbacCatalogue):
        self.catalogue = catalogue
        self._requests: dict[str, AccessRequest] = {}
        self._tasks: dict[str, ApprovalTask] = {}

    def role_profile(self, job_role: str, department: str) -> RoleProfile:
        return self.catalogue.profile(job_role, department)

    def submit(self, req: AccessRequestCreate) -> AccessRequest:
        profile = self.catalogue.profile(req.job_role, req.department)
        items = [RequestedItem(system=a.system, permission=a.permission) for a in profile.access]
        defaults = {(a.system, a.permission) for a in profile.access}

        seen: set[tuple[str, str]] = set()
        for extra in req.extra_access:
            self.catalogue.check_item(extra)
            key = (extra.system, extra.permission)
            if key in defaults:
                raise AccessRequestError(f"{extra.system} '{extra.permission}' is already in the role profile")
            if key in seen:
                raise AccessRequestError(f"{extra.system} '{extra.permission}' is requested twice")
            seen.add(key)
            items.append(RequestedItem(system=extra.system, permission=extra.permission, extra=True,
                                       justification=extra.justification))

        now = datetime.now(timezone.utc)
        request_id = f"AR-{uuid.uuid4().hex[:10]}"

        # AC3: one approval task per system owner, holding every item that owner must grant.
        by_owner: dict[str, list[RequestedItem]] = {}
        for item in items:
            by_owner.setdefault(self.catalogue.owner_of(item.system), []).append(item)
        tasks = [self._new_task(request_id, req.starter_id, TaskKind.SYSTEM_OWNER, owner, owner_items, now)
                 for owner, owner_items in by_owner.items()]

        # AC2: access beyond the profile is routed for additional approval as well.
        extras = [i for i in items if i.extra]
        if extras:
            tasks.append(self._new_task(request_id, req.starter_id, TaskKind.ADDITIONAL,
                                        self.catalogue.additional_approver, extras, now))

        request = AccessRequest(id=request_id, starter_id=req.starter_id, requested_by=req.requested_by,
                                job_role=profile.job_role, department=profile.department, items=items,
                                approval_task_ids=[t.id for t in tasks], created_at=now)
        self._requests[request_id] = request
        for t in tasks:
            self._tasks[t.id] = t

        audit_log.info("access_request_submitted", extra={"audit": {
            "request_id": request_id, "starter_id": req.starter_id, "requested_by": req.requested_by,
            "items": len(items), "extra_items": len(extras), "approval_tasks": [t.id for t in tasks]}})
        return request

    def get_request(self, request_id: str) -> AccessRequest | None:
        return self._requests.get(request_id)

    def tasks_for_starter(self, starter_id: str) -> list[ApprovalTask]:
        return [t for t in self._tasks.values() if t.starter_id == starter_id]

    def _new_task(self, request_id, starter_id, kind, approver, items, now) -> ApprovalTask:
        task = ApprovalTask(id=f"AT-{uuid.uuid4().hex[:10]}", request_id=request_id, starter_id=starter_id,
                            kind=kind, approver=approver, items=items, created_at=now)
        audit_log.info("approval_task_created", extra={"audit": {
            "task_id": task.id, "request_id": request_id, "starter_id": starter_id, "kind": kind.value,
            "systems": sorted({i.system for i in items})}})
        return task


__all__ = ["AccessRequestError", "AccessRequestService", "CatalogueError"]
