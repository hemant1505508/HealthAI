# HealthAI: agent context (to publish in the Workbench)

Project: HealthAI. Domain: Healthcare. Region: UK. Users: a UK GP practice (patients and clinicians).
Test data only: no real patient data in any environment.

## AGT-001 Patient Help Assistant

- **Purpose:** answer practice questions and manage appointments for patients.
- **Users:** patients registered with the practice.
- **Can:** read the approved practice knowledge base; call the appointment service (mock API for now).
- **Cannot:** diagnose, advise on symptoms or medication, or read medical records.
- **Must:** cite a source for every answer; send red-flag symptoms to 999 or NHS 111; mask personal data before logging; use plain English.
- **Done when:** stories TS-001 to TS-004 pass their acceptance criteria and tests.

## AGT-002 Clinical Note Summariser

- **Purpose:** turn consultation notes into a structured summary for the GP.
- **Users:** GPs and nurses.
- **Can:** read the consultation note passed to it; write a draft summary.
- **Cannot:** save anything without a clinician's approval; add facts that are not in the note.
- **Must:** link each summary line to its source; mark missing sections as "Not recorded"; audit every action (no clinical text in logs); record the model version and policy version.
- **Done when:** stories TS-005 to TS-008 pass their acceptance criteria and tests.

## AGT-003 Referral Letter Drafter

- **Purpose:** draft referral letters and a plain-language patient copy.
- **Users:** GPs; patients receive the copy.
- **Can:** read the approved summary and the practice letter template.
- **Cannot:** send or export a letter before clinician sign-off.
- **Must:** fill fields only from the approved summary; patient copy at reading age 11 or below; accessible export meeting WCAG 2.2 AA.
- **Done when:** stories TS-009 to TS-012 pass their acceptance criteria and tests.

## Technical choices (Tech Lead to confirm)

- Model: a pinned Claude model version (for example `claude-sonnet-5-5`), recorded with each output.
- Language: Python 3.12 with pytest, or TypeScript with Vitest.
- External systems (appointments, records) are mocked for this test project.
