# OmniPay K8s Ops

Owner: Iulia

This workspace models the Kubernetes operating layer for OmniPay's eventing and
data platform. It ships Helm metadata plus Kustomize overlays for deployments,
stateful services, ingress, and supporting Kafka, RabbitMQ, MongoDB, Redis, and
SQL Server workloads.

## Technology

- Helm metadata for platform release packaging
- Kustomize overlays for Kubernetes workloads
- Deployments, StatefulSets, Services, and Ingress resources

## Workloads

- `settlement-orchestrator`
- `event-projections`
- `risk-streams`
- `kafka`
- `rabbitmq`
- `mongodb`
- `redis`
- `sqlserver`
