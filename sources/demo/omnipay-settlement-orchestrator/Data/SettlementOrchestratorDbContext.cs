using Microsoft.EntityFrameworkCore;
using OmniPay.SettlementOrchestrator.Models;

namespace OmniPay.SettlementOrchestrator.Data;

/// <summary>
/// Entity Framework database context for settlement orchestration records.
/// </summary>
public sealed class SettlementOrchestratorDbContext(
    DbContextOptions<SettlementOrchestratorDbContext> options) : DbContext(options)
{
    /// <summary>
    /// Stored settlement-batch records.
    /// </summary>
    public DbSet<SettlementBatch> SettlementBatches => Set<SettlementBatch>();

    /// <summary>
    /// Configure entity mappings for the settlement data model.
    /// </summary>
    /// <param name="modelBuilder">Entity model builder.</param>
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<SettlementBatch>(entity =>
        {
            entity.ToTable("SettlementBatches");
            entity.HasKey(item => item.Id);
            entity.Property(item => item.MerchantId).HasMaxLength(64);
            entity.Property(item => item.ClearingWindow).HasMaxLength(32);
            entity.Property(item => item.Currency).HasMaxLength(8);
            entity.Property(item => item.Status).HasMaxLength(32);
            entity.Property(item => item.RabbitMqExchange).HasMaxLength(128);
        });
    }
}
