# OmniPay Demo Repositories

OmniPay is a curated demo workspace for KnowledgeForge.

It models a payment platform with multiple services that exercise the main
detectors in the app, including dictionary-based extraction, LLM enrichment,
and human review workflows.

## Core Services

- `omnipay-ledger` owned by Iulia
- `omnipay-fraud-ml` owned by Vlas
- `omnipay-gateway` owned by Vlad
- `omnipay-notifier` owned by Iulia
- `omnipay-infra` owned by Iulia
- `omnipay-card-router` owned by Vlad

## Dictionary Trigger Services (Phase 1)

These services test dictionary-based extraction by triggering specific providers:

- `omnipay-payment-processor` - Triggers Stripe provider via `package: stripe`, `env: STRIPE_*`
- `omnipay-analytics` - Triggers Mixpanel provider via `package: mixpanel`, `env: MIXPANEL_*`
- `omnipay-auth` - Triggers Auth0 provider via `package: @auth0/auth0-spa-js`, `env: AUTH0_*`
- `omnipay-database` - Triggers PostgreSQL/Redis via docker-compose, `env: POSTGRES_*`, `env: REDIS_*`

## LLM Enrichment Services (Phase 2)

These services require LLM inference for business domain/technology detection:

- `omnipay-billing-llm` - Complex billing logic requiring business domain inference
- `omnipay-ml-pipeline` - Non-standard config (Hydra YAML) requiring technology inference

## Human Review Services (Phase 3)

These services trigger review workflows:

- `omnipay-disputes` - Ambiguous ownership (conflicting CODEOWNERS entries)

## Platform Integration Services (Phase 4)

These services expand the demo into deeper infrastructure and eventing use cases:

- `omnipay-settlement-orchestrator` - .NET service using SQL Server, RabbitMQ, and Redis
- `omnipay-event-projections` - .NET service using Kafka, MongoDB, and Redis
- `omnipay-risk-streams` - Java Kafka Streams application for event enrichment
- `omnipay-k8s-ops` - Helm and Kustomize workspace with Deployments, StatefulSets, and Ingress

Each service now lives in its own top-level folder under `sources/demo/`, so it
can be pushed into its own git repository later without another reshuffle. The
contents are intentionally compact, but each folder still includes enough code
and configuration to demonstrate architecture extraction, ownership metadata,
container detection, dependency mapping, and framework-aware component parsing.
