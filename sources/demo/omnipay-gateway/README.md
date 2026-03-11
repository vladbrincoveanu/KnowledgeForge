# OmniPay Gateway

Owner: Vlad

The gateway is the NestJS backend-for-frontend for the mobile clients. It
orchestrates calls to the ledger, fraud, and card-router services and uses
Redis for short-lived decision caching.

## Risk Operations Manager

Reviews provider onboarding tradeoffs and resolves low-confidence external
dependency classifications before they are accepted into the context diagram.

## External Partners

- Auth0 handles customer login and session management for the mobile clients.
- SignalForge is being evaluated for merchant-risk orchestration, but the team
  has not yet decided whether it should be modeled as a core external business
  system or as a lower-level technical integration.
