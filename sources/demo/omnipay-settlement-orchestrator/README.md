# OmniPay Settlement Orchestrator

Owner: Vlad

This service coordinates settlement-batch creation and release workflows for
OmniPay. It keeps the settlement ledger in SQL Server, publishes release events
through RabbitMQ, and caches release windows in Redis so operations teams can
retry partner bank cutovers safely.

## Technology

- .NET 8 with ASP.NET Core Web API
- SQL Server for settlement batch storage
- RabbitMQ for settlement release events
- Redis for release-window caching

## Dependencies

- Microsoft.EntityFrameworkCore.SqlServer
- Microsoft.Data.SqlClient
- RabbitMQ.Client
- StackExchange.Redis
- AspNetCore.HealthChecks.SqlServer
- AspNetCore.HealthChecks.Redis

## Environment Variables

- `SETTLEMENT_SQLSERVER_CONNECTION`
- `RABBITMQ_URL`
- `REDIS_URL`
