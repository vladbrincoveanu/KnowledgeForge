# OmniPay Event Projections

Owner: Iulia

This service builds read models for OmniPay operations teams. It consumes Kafka
payment events, projects settlement and dispute snapshots into MongoDB, and
keeps hot projection checkpoints in Redis for fast replay and backfill control.

## Technology

- .NET 8 with ASP.NET Core Web API
- Kafka for event ingestion and replay
- MongoDB for projection storage
- Redis for projection checkpoints and replay windows

## Dependencies

- Confluent.Kafka
- MongoDB.Driver
- StackExchange.Redis

## Environment Variables

- `KAFKA_BOOTSTRAP_SERVERS`
- `MONGODB_URI`
- `REDIS_URL`
