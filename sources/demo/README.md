# OmniPay Demo Repositories

OmniPay is a curated demo workspace for KnowledgeForge.

It models a payment platform with six services that exercise the main
detectors in the app:

- `omnipay-ledger` owned by Iulia
- `omnipay-fraud-ml` owned by Vlas
- `omnipay-gateway` owned by Vlad
- `omnipay-notifier` owned by Iulia
- `omnipay-infra` owned by Iulia
- `omnipay-card-router` owned by Vlad

Each service now lives in its own top-level folder under `sources/demo/`, so it
can be pushed into its own git repository later without another reshuffle. The
contents are intentionally compact, but each folder still includes enough code
and configuration to demonstrate architecture extraction, ownership metadata,
container detection, dependency mapping, and framework-aware component parsing.
