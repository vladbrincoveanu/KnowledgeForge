namespace OmniPay.SettlementOrchestrator.Models;

/// <summary>
/// Represents a settlement batch persisted to SQL Server.
/// </summary>
public sealed class SettlementBatch
{
    /// <summary>
    /// Primary key for the settlement batch.
    /// </summary>
    public Guid Id { get; set; } = Guid.NewGuid();

    /// <summary>
    /// Merchant identifier tied to the batch.
    /// </summary>
    public string MerchantId { get; set; } = string.Empty;

    /// <summary>
    /// Logical settlement window, such as T+1-AM.
    /// </summary>
    public string ClearingWindow { get; set; } = string.Empty;

    /// <summary>
    /// ISO currency for the batch amount.
    /// </summary>
    public string Currency { get; set; } = "USD";

    /// <summary>
    /// Aggregated amount queued for settlement.
    /// </summary>
    public decimal TotalAmount { get; set; }

    /// <summary>
    /// Workflow status tracked by operations.
    /// </summary>
    public string Status { get; set; } = string.Empty;

    /// <summary>
    /// Exchange name used when dispatching RabbitMQ messages.
    /// </summary>
    public string RabbitMqExchange { get; set; } = string.Empty;

    /// <summary>
    /// Creation timestamp in UTC.
    /// </summary>
    public DateTime CreatedAtUtc { get; set; }
}
