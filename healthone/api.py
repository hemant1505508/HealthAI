from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .access.catalogue import CatalogueError, RbacCatalogue
from .access.models import AccessRequest, AccessRequestCreate, ApprovalTask, RoleProfile
from .access.service import AccessRequestError, AccessRequestService


def create_app(service: AccessRequestService | None = None) -> FastAPI:
    app = FastAPI(title="HealthOne onboarding API")
    svc = service or AccessRequestService(RbacCatalogue.load())

    def get_service() -> AccessRequestService:
        return svc

    @app.get("/role-profiles", response_model=RoleProfile)
    def role_profile(job_role: str, department: str, s: AccessRequestService = Depends(get_service)):
        try:
            return s.role_profile(job_role, department)
        except CatalogueError as e:
            raise HTTPException(404, str(e))

    @app.post("/access-requests", response_model=AccessRequest, status_code=201)
    def submit(body: AccessRequestCreate, s: AccessRequestService = Depends(get_service)):
        try:
            return s.submit(body)
        except (CatalogueError, AccessRequestError) as e:
            raise HTTPException(422, str(e))

    @app.get("/access-requests/{request_id}", response_model=AccessRequest)
    def get_request(request_id: str, s: AccessRequestService = Depends(get_service)):
        found = s.get_request(request_id)
        if found is None:
            raise HTTPException(404, "access request not found")
        return found

    @app.get("/starters/{starter_id}/approval-tasks", response_model=list[ApprovalTask])
    def starter_tasks(starter_id: str, s: AccessRequestService = Depends(get_service)):
        return s.tasks_for_starter(starter_id)

    return app


app = create_app()
