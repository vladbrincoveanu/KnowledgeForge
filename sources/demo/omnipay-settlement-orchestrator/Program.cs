using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.EntityFrameworkCore;
using OmniPay.SettlementOrchestrator.Data;
using OmniPay.SettlementOrchestrator.Models;
using StackExchange.Redis;

namespace OmniPay.SettlementOrchestrator;

/// <summary>
/// Bootstraps the settlement orchestration API.
/// </summary>
public static class Program
{
    /// <summary>
    /// Builds and runs the settlement orchestration host.
    /// </summary>
    /// <param name="args">Application startup arguments.</param>
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        var sqlConnection = builder.Configuration.GetConnectionString("SettlementSqlServer")
            ?? "Server=localhost;Database=SettlementOps;";
        var redisUrl = builder.Configuration["SettlementInfrastructure:RedisUrl"]
            ?? "redis://localhost:6379/4";

        builder.Services.AddControllers();
        builder.Services.AddDbContext<SettlementOrchestratorDbContext>(
            options => options.UseSqlServer(sqlConnection));
        builder.Services.Configure<SettlementInfrastructureOptions>(
            builder.Configuration.GetSection("SettlementInfrastructure"));
        builder.Services.Configure<SettlementMessagingOptions>(
            builder.Configuration.GetSection(SettlementMessagingOptions.SectionName));
        builder.Services.AddSingleton<IConnectionMultiplexer>(
            _ => ConnectionMultiplexer.Connect(redisUrl));
        builder.Services.AddHealthChecks()
            .AddSqlServer(sqlConnection)
            .AddRedis(redisUrl);

        var app = builder.Build();

        app.MapControllers();
        app.MapHealthChecks("/health", new HealthCheckOptions());

        app.Run();
    }
}

/// <summary>
/// Configures downstream settlement infrastructure integrations.
/// </summary>
public sealed class SettlementInfrastructureOptions
{
    /// <summary>
    /// Gets or sets the settlement RabbitMQ URL.
    /// </summary>
    public string RabbitMqUrl { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the settlement Redis URL.
    /// </summary>
    public string RedisUrl { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the settlement release topic or exchange name.
    /// </summary>
    public string ReleaseTopic { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the release-window TTL in seconds.
    /// </summary>
    public int ReleaseWindowSeconds { get; set; }
}
