# OmniPay Fraud ML

Owner: Vlas

This FastAPI service scores transactions for suspicious behavior in real time.
It is intentionally modeled as a critical Tier 1 service with a bus factor of 1
to highlight risk metadata in KnowledgeForge.

## Fraud Analyst

Reviews flagged transactions, tunes thresholds, and feeds labels back into the
fraud models after manual investigation.

## Compliance Screening

The team is piloting LedgerShield for sanctions and merchant onboarding checks.
The integration is still exploratory and should require human review before the
dependency is accepted as a context-level external business system.
