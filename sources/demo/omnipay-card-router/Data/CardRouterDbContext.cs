using Microsoft.EntityFrameworkCore;

namespace OmniPay.CardRouter.Data;

/// <summary>
/// Entity Framework database context for card routing records.
/// </summary>
public sealed class CardRouterDbContext : DbContext
{
    /// <summary>
    /// Initializes a new database context.
    /// </summary>
    /// <param name="options">Entity Framework options.</param>
    public CardRouterDbContext(DbContextOptions<CardRouterDbContext> options)
        : base(options)
    {
    }

    /// <summary>
    /// Stored authorization attempts.
    /// </summary>
    public DbSet<AuthorizationRecord> Authorizations => Set<AuthorizationRecord>();
}

/// <summary>
/// Demo authorization entity.
/// </summary>
public sealed class AuthorizationRecord
{
    /// <summary>
    /// Primary key.
    /// </summary>
    public int Id { get; set; }

    /// <summary>
    /// Tokenized card reference.
    /// </summary>
    public string CardToken { get; set; } = string.Empty;

    /// <summary>
    /// Authorized amount.
    /// </summary>
    public decimal Amount { get; set; }

    /// <summary>
    /// Downstream network name.
    /// </summary>
    public string Network { get; set; } = string.Empty;
}
