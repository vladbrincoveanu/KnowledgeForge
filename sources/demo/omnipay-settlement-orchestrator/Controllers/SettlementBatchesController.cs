using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using OmniPay.SettlementOrchestrator.Data;
using OmniPay.SettlementOrchestrator.Models;
using StackExchange.Redis;

namespace OmniPay.SettlementOrchestrator.Controllers;

/// <summary>
/// Manages settlement-batch creation and dispatch planning.
/// </summary>
[ApiController]
[Route("api/v1/settlement-batches")]
public sealed class SettlementBatchesController(
    SettlementOrchestratorDbContext dbContext,
    IConnectionMultiplexer redisConnection,
    IOptions<SettlementMessagingOptions> messagingOptions) : ControllerBase
{
    /// <summary>
    /// Create a new settlement batch for a clearing window.
    /// </summary>
    /// <param name="request">Batch creation payload.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The newly created settlement batch.</returns>
    [HttpPost]
    public async Task<ActionResult<SettlementBatchResponse>> CreateBatch(
        [FromBody] CreateSettlementBatchRequest request,
        CancellationToken cancellationToken)
    {
        var batch = new SettlementBatch
        {
            MerchantId = request.MerchantId,
            ClearingWindow = request.ClearingWindow,
            Currency = request.Currency,
            TotalAmount = request.TotalAmount,
            Status = "pending-review",
            RabbitMqExchange = messagingOptions.Value.ExchangeName,
            CreatedAtUtc = DateTime.UtcNow
        };

        dbContext.SettlementBatches.Add(batch);
        await dbContext.SaveChangesAsync(cancellationToken);

        var cache = redisConnection.GetDatabase();
        await cache.StringSetAsync(
            $"settlement-batch:{batch.Id}",
            $"status={batch.Status};amount={batch.TotalAmount};currency={batch.Currency}"
        );

        return Ok(ToResponse(batch));
    }

    /// <summary>
    /// Retrieve the latest status of a settlement batch.
    /// </summary>
    /// <param name="batchId">Batch identifier.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The batch summary if found.</returns>
    [HttpGet("{batchId:guid}")]
    public async Task<ActionResult<SettlementBatchResponse>> GetBatch(
        Guid batchId,
        CancellationToken cancellationToken)
    {
        var batch = await dbContext.SettlementBatches
            .AsNoTracking()
            .SingleOrDefaultAsync(item => item.Id == batchId, cancellationToken);

        if (batch is null)
        {
            return NotFound();
        }

        return Ok(ToResponse(batch));
    }

    /// <summary>
    /// Prepare a batch for downstream dispatch over RabbitMQ.
    /// </summary>
    /// <param name="batchId">Batch identifier.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>A dispatch plan with queue metadata.</returns>
    [HttpPost("{batchId:guid}/dispatch")]
    public async Task<ActionResult<DispatchSettlementBatchResponse>> DispatchBatch(
        Guid batchId,
        CancellationToken cancellationToken)
    {
        var batch = await dbContext.SettlementBatches
            .SingleOrDefaultAsync(item => item.Id == batchId, cancellationToken);

        if (batch is null)
        {
            return NotFound();
        }

        batch.Status = "queued-for-dispatch";
        await dbContext.SaveChangesAsync(cancellationToken);

        var response = new DispatchSettlementBatchResponse
        {
            BatchId = batch.Id,
            Status = batch.Status,
            ExchangeName = messagingOptions.Value.ExchangeName,
            QueueName = messagingOptions.Value.QueueName,
            DeadLetterExchange = messagingOptions.Value.DeadLetterExchange
        };

        var cache = redisConnection.GetDatabase();
        await cache.StringSetAsync(
            $"settlement-dispatch:{batch.Id}",
            $"{response.ExchangeName}:{response.QueueName}:{response.Status}"
        );

        return Ok(response);
    }

    /// <summary>
    /// Convert the entity into an API response model.
    /// </summary>
    /// <param name="batch">Settlement entity.</param>
    /// <returns>External response contract.</returns>
    private static SettlementBatchResponse ToResponse(SettlementBatch batch)
    {
        return new SettlementBatchResponse
        {
            BatchId = batch.Id,
            MerchantId = batch.MerchantId,
            ClearingWindow = batch.ClearingWindow,
            Currency = batch.Currency,
            TotalAmount = batch.TotalAmount,
            Status = batch.Status,
            RabbitMqExchange = batch.RabbitMqExchange,
            CreatedAtUtc = batch.CreatedAtUtc
        };
    }
}
