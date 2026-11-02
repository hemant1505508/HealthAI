import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from healthone.access.catalogue import CatalogueError, RbacCatalogue
from healthone.access.models import AccessRequestCreate, TaskKind
from healthone.access.service import AccessRequestError, AccessRequestService
from healthone.api import create_app

JUSTIFICATION = "Covers the pharmacy dispensary on weekend rotas"


@pytest.fixture
def service():
    return AccessRequestService(RbacCatalogue.load())


@pytest.fixture
def client(service):
    return TestClient(create_app(service))


def nurse_request(**overrides):
    body = {"starter_id": "ST-1001", "requested_by": "HM-42", "job_role": "Staff Nurse",
            "department": "Emergency Department"}
    body.update(overrides)
    return AccessRequestCreate.model_validate(body)


# AC1: selecting a job role and department shows the default systems and permission levels

def test_profile_lists_default_systems_and_permissions(service):
    profile = service.role_profile("Staff Nurse", "Emergency Department")
    assert {(a.system, a.permission) for a in profile.access} == {
        ("Entra ID", "Standard User"), ("ESR", "Self-service"),
        ("CIS2 Smartcard", "Registered Nurse"), ("EPR", "Clinical Read/Write")}


def test_profile_lookup_ignores_case_and_spaces(service):
    assert service.role_profile("  pharmacist ", "PHARMACY").job_role == "Pharmacist"


def test_unknown_profile_is_refused(service):
    with pytest.raises(CatalogueError):
        service.role_profile("Astronaut", "Emergency Department")


def test_profile_endpoint(client):
    r = client.get("/role-profiles", params={"job_role": "Pharmacist", "department": "Pharmacy"})
    assert r.status_code == 200
    assert {"system": "Pharmacy System", "permission": "Dispensing"} in r.json()["access"]
    assert client.get("/role-profiles", params={"job_role": "x", "department": "y"}).status_code == 404


# AC2: extra access requires a business justification and is routed for additional approval

def test_extra_access_without_justification_is_rejected():
    with pytest.raises(ValidationError):
        nurse_request(extra_access=[{"system": "Pharmacy System", "permission": "Read Only", "justification": "  "}])


def test_short_justification_is_rejected():
    with pytest.raises(ValidationError):
        nurse_request(extra_access=[{"system": "Pharmacy System", "permission": "Read Only", "justification": "needed"}])


def test_extra_access_is_routed_for_additional_approval(service):
    req = service.submit(nurse_request(extra_access=[
        {"system": "Pharmacy System", "permission": "Read Only", "justification": JUSTIFICATION}]))
    tasks = service.tasks_for_starter("ST-1001")
    additional = [t for t in tasks if t.kind is TaskKind.ADDITIONAL]
    assert len(additional) == 1
    assert additional[0].approver == "Information Governance"
    assert [(i.system, i.permission, i.justification) for i in additional[0].items] == [
        ("Pharmacy System", "Read Only", JUSTIFICATION)]
    assert [i for i in req.items if i.extra][0].justification == JUSTIFICATION


def test_no_additional_approval_without_extra_access(service):
    service.submit(nurse_request())
    assert all(t.kind is TaskKind.SYSTEM_OWNER for t in service.tasks_for_starter("ST-1001"))


@pytest.mark.parametrize("extra, message", [
    ({"system": "EPR", "permission": "Clinical Read/Write"}, "already in the role profile"),
    ({"system": "Payroll", "permission": "Admin"}, "unknown system"),
    ({"system": "EPR", "permission": "Superuser"}, "not a permission level"),
])
def test_invalid_extra_access_is_refused(service, extra, message):
    with pytest.raises((AccessRequestError, CatalogueError), match=message):
        service.submit(nurse_request(extra_access=[{**extra, "justification": JUSTIFICATION}]))


def test_duplicate_extra_access_is_refused(service):
    extra = {"system": "Pharmacy System", "permission": "Read Only", "justification": JUSTIFICATION}
    with pytest.raises(AccessRequestError, match="requested twice"):
        service.submit(nurse_request(extra_access=[extra, extra]))


# AC3: on submit, one approval task per system owner is created and tracked against the starter

def test_one_task_per_system_owner(service):
    req = service.submit(nurse_request())
    tasks = service.tasks_for_starter("ST-1001")
    owners = [t.approver for t in tasks]
    assert sorted(owners) == sorted({"IT Identity Team", "ESR Systems Team", "Registration Authority",
                                     "Clinical Systems Team"})
    assert len(owners) == len(set(owners))
    assert {t.id for t in tasks} == set(req.approval_task_ids)
    assert all(t.status.value == "pending" and t.request_id == req.id for t in tasks)


def test_owner_of_several_systems_gets_one_task(service):
    # Clinical Systems Team owns both EPR and the Pharmacy System.
    service.submit(nurse_request(extra_access=[
        {"system": "Pharmacy System", "permission": "Read Only", "justification": JUSTIFICATION}]))
    clinical = [t for t in service.tasks_for_starter("ST-1001")
                if t.kind is TaskKind.SYSTEM_OWNER and t.approver == "Clinical Systems Team"]
    assert len(clinical) == 1
    assert {i.system for i in clinical[0].items} == {"EPR", "Pharmacy System"}


def test_tasks_are_tracked_per_starter(service):
    service.submit(nurse_request())
    service.submit(nurse_request(starter_id="ST-2002", job_role="HR Onboarding Officer",
                                 department="Human Resources"))
    assert {t.starter_id for t in service.tasks_for_starter("ST-2002")} == {"ST-2002"}
    assert len(service.tasks_for_starter("ST-2002")) == 2
    assert service.tasks_for_starter("ST-9999") == []


def test_submit_and_track_over_api(client):
    body = {"starter_id": "ST-1001", "requested_by": "HM-42", "job_role": "Pharmacist", "department": "Pharmacy",
            "extra_access": [{"system": "ESR", "permission": "Manager Self-service", "justification": JUSTIFICATION}]}
    r = client.post("/access-requests", json=body)
    assert r.status_code == 201
    req = r.json()
    assert client.get(f"/access-requests/{req['id']}").json()["id"] == req["id"]
    tasks = client.get("/starters/ST-1001/approval-tasks").json()
    assert {t["id"] for t in tasks} == set(req["approval_task_ids"])
    assert sum(t["kind"] == "additional_approval" for t in tasks) == 1


def test_api_rejects_bad_requests(client):
    base = {"starter_id": "ST-1", "requested_by": "HM-1", "job_role": "Staff Nurse",
            "department": "Emergency Department"}
    assert client.post("/access-requests", json={**base, "job_role": "Astronaut"}).status_code == 422
    no_reason = {**base, "extra_access": [{"system": "EPR", "permission": "Prescriber", "justification": ""}]}
    assert client.post("/access-requests", json=no_reason).status_code == 422
    assert client.get("/access-requests/AR-missing").status_code == 404


# POL-CA-01 / POL-SP-01: audit entries are written and hold ids, not justification text

def test_audit_log_records_ids_only(service, caplog):
    with caplog.at_level(logging.INFO, logger="healthone.audit"):
        req = service.submit(nurse_request(extra_access=[
            {"system": "Pharmacy System", "permission": "Read Only", "justification": JUSTIFICATION}]))
    events = [r for r in caplog.records if r.name == "healthone.audit"]
    assert [e.getMessage() for e in events].count("approval_task_created") == len(req.approval_task_ids)
    submitted = [e for e in events if e.getMessage() == "access_request_submitted"][0]
    assert submitted.audit["request_id"] == req.id
    assert all(JUSTIFICATION not in repr(e.audit) for e in events)


def test_catalogue_rejects_profile_with_unknown_system(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"additional_approver": "IG", "systems": {}, "role_profiles": [{"job_role": "A", '
                   '"department": "B", "access": [{"system": "ESR", "permission": "Self-service"}]}]}')
    with pytest.raises(CatalogueError):
        RbacCatalogue.load(bad)
