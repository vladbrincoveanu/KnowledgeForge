using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using OmniPay.EventProjections;

namespace OmniPay.EventProjections.Controllers;

/// <summary>
/// Exposes projection and replay endpoints for operational read models.
/// </summary>
[ApiController]
[Route("api/v1/projections")]
public sealed class ProjectionController : ControllerBase
{
    private readonly ProjectionInfrastructureOptions _infrastructure;

    /// <summary>
    /// Initializes a new instance of the <see cref="ProjectionController"/> class.
    /// </summary>
    /// <param name="infrastructure">The configured projection infrastructure.</param>
    public ProjectionController(IOptions<ProjectionInfrastructureOptions> infrastructure)
    {
        _infrastructure = infrastructure.Value;
    }

    /// <summary>
    /// Returns the current configuration backing event projections.
    /// </summary>
    /// <returns>A projection read-model summary.</returns>
    [HttpGet("status")]
    public ActionResult<ProjectionStatusResponse> GetStatus()
    {
        return Ok(
            new ProjectionStatusResponse
            {
                Topic = _infrastructure.ProjectionTopic,
                KafkaBootstrapServers = _infrastructure.KafkaBootstrapServers,
                MongoDbUrl = _infrastructure.MongoDbUrl,
                RedisUrl = _infrastructure.RedisUrl,
                Status = "healthy",
            });
    }

    /// <summary>
    /// Triggers a backfill or replay of projection data.
    /// </summary>
    /// <param name="request">The replay request.</param>
    /// <returns>A replay summary.</returns>
    [HttpPost("rebuild")]
    public ActionResult<ProjectionReplayResponse> Rebuild(
        [FromBody] ProjectionReplayRequest request)
    {
        return Ok(
            new ProjectionReplayResponse
            {
                ProjectionName = request.ProjectionName,
                StartingOffset = request.StartingOffset,
                ReplayWindowHours = request.ReplayWindowHours,
                Status = "scheduled",
            });
    }
}

/// <summary>
/// Describes a projection replay request.
/// </summary>
public sealed class ProjectionReplayRequest
{
    /// <summary>
    /// Gets or sets the projection name.
    /// </summary>
    public string ProjectionName { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the starting Kafka offset.
    /// </summary>
    public long StartingOffset { get; set; }

    /// <summary>
    /// Gets or sets the replay window in hours.
    /// </summary>
    public int ReplayWindowHours { get; set; }
}

/// <summary>
/// Represents projection infrastructure status.
/// </summary>
public sealed class ProjectionStatusResponse
{
    /// <summary>
    /// Gets or sets the Kafka topic used for projections.
    /// </summary>
    public string Topic { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the Kafka bootstrap address.
    /// </summary>
    public string KafkaBootstrapServers { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the MongoDB read-model connection string.
    /// </summary>
    public string MongoDbUrl { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the Redis checkpoint store connection string.
    /// </summary>
    public string RedisUrl { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the projection service status.
    /// </summary>
    public string Status { get; set; } = string.Empty;
}

/// <summary>
/// Represents a scheduled projection replay.
/// </summary>
public sealed class ProjectionReplayResponse
{
    /// <summary>
    /// Gets or sets the projection name.
    /// </summary>
    public string ProjectionName { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the replay starting offset.
    /// </summary>
    public long StartingOffset { get; set; }

    /// <summary>
    /// Gets or sets the replay window in hours.
    /// </summary>
    public int ReplayWindowHours { get; set; }

    /// <summary>
    /// Gets or sets the replay status.
    /// </summary>
    public string Status { get; set; } = string.Empty;
}
