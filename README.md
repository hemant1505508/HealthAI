# HealthAI: HealthOne workforce onboarding

HealthOne replaces paper- and e-mail-driven NHS workforce onboarding with one digital platform: pre-employment checks,
role-based access requests and approvals, and account set-up across ESR, Entra ID and CIS2.

This repository is connected to the Workbench project **HealthOne** with `adlc.mjs`
(`node adlc.mjs pull` brings policies and tasks up to date; see `.workbench/README.md`).

## Run

```
pip install -e ".[dev]"
python -m pytest --cov=healthone
uvicorn healthone.api:app --reload      # http://127.0.0.1:8000/docs
```

## What is built

| Story | What | Code |
|---|---|---|
| US-08 | Role-based access request by role profile | `healthone/access/`, `healthone/api.py` |

### US-08 API

- `GET /role-profiles?job_role=&department=`: the default systems and permission levels from the RBAC catalogue (AC1).
- `POST /access-requests`: submit the starter's access. Extra access needs a business justification and gets an
  additional approval task for Information Governance (AC2). One approval task is created per system owner (AC3).
- `GET /access-requests/{id}` and `GET /starters/{starter_id}/approval-tasks`: track the request and its tasks.

The RBAC catalogue in `healthone/data/rbac_catalogue.json` is sample data until the real catalogue is supplied.
Storage is in memory for now.

## Workbench reporting

- **Commits:** run `node adlc.mjs hooks install` once, then `node adlc.mjs task start <story>` before you work.
  Each commit gets the task trailers and is reported to the Workbench (id and counts only, never the message or code).
- **Pull requests:** `.github/workflows/adlc.yml` runs the tests and `node adlc.mjs evaluate` on every pull request to
  `main`. To send the result to the Workbench's CI evidence, add the repository secret `ADLC_CI_TOKEN` (a CI token from
  the Workbench) and the variable `ADLC_SERVER` (`http://98.70.60.86`).
