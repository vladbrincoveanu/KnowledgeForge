using Microsoft.AspNetCore.Diagnostics.HealthChecks;

namespace OmniPay.EventProjections;

/// <summary>
/// Bootstraps the event-projection API.
/// </summary>
public static class Program
{
    /// <summary>
    /// Builds and runs the event-projection host.
    /// </summary>
    /// <param name="args">Application startup arguments.</param>
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        builder.Services.AddControllers();
        builder.Services.Configure<ProjectionInfrastructureOptions>(
            builder.Configuration.GetSection("ProjectionInfrastructure"));
        builder.Services.AddHealthChecks();

        var app = builder.Build();

        app.MapControllers();
        app.MapHealthChecks("/health", new HealthCheckOptions());

        app.Run();
    }
}

/// <summary>
/// Configures downstream projection infrastructure.
/// </summary>
public sealed class ProjectionInfrastructureOptions
{
    /// <summary>
    /// Gets or sets the Kafka bootstrap endpoint.
    /// </summary>
    public string KafkaBootstrapServers { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the Kafka topic used for projection input.
    /// </summary>
    public string ProjectionTopic { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the MongoDB connection string for read models.
    /// </summary>
    public string MongoDbUrl { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the Redis connection string for projection checkpoints.
    /// </summary>
    public string RedisUrl { get; set; } = string.Empty;
}
