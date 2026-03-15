namespace OmniPay.SettlementOrchestrator.Models;

/// <summary>
/// Configuration model for RabbitMQ settlement dispatching.
/// </summary>
public sealed class SettlementMessagingOptions
{
    /// <summary>
    /// Configuration section name.
    /// </summary>
    public const string SectionName = "Messaging";

    /// <summary>
    /// RabbitMQ connection string for settlement dispatch.
    /// </summary>
    public string ConnectionString { get; set; } = string.Empty;

    /// <summary>
    /// Exchange name for dispatch fan-out.
    /// </summary>
    public string ExchangeName { get; set; } = string.Empty;

    /// <summary>
    /// Queue name bound by downstream workers.
    /// </summary>
    public string QueueName { get; set; } = string.Empty;

    /// <summary>
    /// Dead-letter exchange for failed dispatch events.
    /// </summary>
    public string DeadLetterExchange { get; set; } = string.Empty;
}
