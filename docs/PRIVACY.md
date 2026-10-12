# Privacy & Consent

PAIRWISE is designed for consenting adults only.

## Consent

- Adult eligibility confirmation is required at enrollment.
- Explicit consent for agent dating is required.
- Only two information sources are used: the participant’s LinkedIn and Instagram (via permitted/authorized content).

## Data handling

- Source records store submitted URLs, acquisition method, status, and permitted content.
- Analyses, transcripts, evaluations, and rankings are persisted for product functionality.
- Participant deletion removes the participant and cascaded related records.

## Retention

- Local/demo databases may retain synthetic demo data until reseeding or deletion.
- For production deployments, define an organizational retention window (recommended default: delete inactive participant data within 90 days of withdrawal of consent).
- Do not publish real analyses, transcripts, or rankings without explicit authorization.

## Prohibited inferences

The system must not infer or rank on sexual orientation, ethnicity, religion, health, appearance, or other sensitive traits.

## Removal

Participants (or operators acting on their request) can delete records via `DELETE /api/participants/{id}` or the profile UI delete control.
