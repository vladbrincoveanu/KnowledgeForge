namespace OmniPay.SettlementOrchestrator.Models;

/// <summary>
/// Request contract for creating a settlement batch.
/// </summary>
public sealed class CreateSettlementBatchRequest
{
    /// <summary>
    /// Merchant identifier associated with the batch.
    /// </summary>
    public string MerchantId { get; set; } = string.Empty;

    /// <summary>
    /// Settlement window label supplied by operations.
    /// </summary>
    public string ClearingWindow { get; set; } = string.Empty;

    /// <summary>
    /// ISO currency for the batch.
    /// </summary>
    public string Currency { get; set; } = "USD";

    /// <summary>
    /// Total amount assigned to the batch.
    /// </summary>
    public decimal TotalAmount { get; set; }
}

/// <summary>
/// Response contract for settlement-batch reads.
/// </summary>
public sealed class SettlementBatchResponse
{
    /// <summary>
    /// Batch identifier.
    /// </summary>
    public Guid BatchId { get; set; }

    /// <summary>
    /// Merchant identifier.
    /// </summary>
    public string MerchantId { get; set; } = string.Empty;

    /// <summary>
    /// Settlement window label.
    /// </summary>
    public string ClearingWindow { get; set; } = string.Empty;

    /// <summary>
    /// ISO currency.
    /// </summary>
    public string Currency { get; set; } = string.Empty;

    /// <summary>
    /// Total batch amount.
    /// </summary>
    public decimal TotalAmount { get; set; }

    /// <summary>
    /// Current workflow status.
    /// </summary>
    public string Status { get; set; } = string.Empty;

    /// <summary>
    /// RabbitMQ exchange earmarked for dispatch.
    /// </summary>
    public string RabbitMqExchange { get; set; } = string.Empty;

    /// <summary>
    /// Creation timestamp in UTC.
    /// </summary>
    public DateTime CreatedAtUtc { get; set; }
}

/// <summary>
/// Response contract for dispatching a settlement batch.
/// </summary>
public sealed class DispatchSettlementBatchResponse
{
    /// <summary>
    /// Batch identifier.
    /// </summary>
    public Guid BatchId { get; set; }

    /// <summary>
    /// Updated workflow status.
    /// </summary>
    public string Status { get; set; } = string.Empty;

    /// <summary>
    /// RabbitMQ exchange used for dispatch.
    /// </summary>
    public string ExchangeName { get; set; } = string.Empty;

    /// <summary>
    /// Queue name subscribed by the settlement worker.
    /// </summary>
    public string QueueName { get; set; } = string.Empty;

    /// <summary>
    /// Dead-letter exchange for failed dispatch attempts.
    /// </summary>
    public string DeadLetterExchange { get; set; } = string.Empty;
}
