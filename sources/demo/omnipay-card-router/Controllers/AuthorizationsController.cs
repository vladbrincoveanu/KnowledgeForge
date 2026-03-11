using Microsoft.AspNetCore.Mvc;

namespace OmniPay.CardRouter.Controllers;

/// <summary>
/// Handles card authorization requests from the gateway.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public sealed class AuthorizationsController : ControllerBase
{
    /// <summary>
    /// Submit a demo authorization request to the router.
    /// </summary>
    /// <param name="request">Authorization payload.</param>
    /// <returns>A deterministic authorization response.</returns>
    [HttpPost]
    public IActionResult Create([FromBody] AuthorizationRequest request)
    {
        return Ok(new
        {
            request.CardToken,
            request.Amount,
            Status = "approved",
            Network = request.Network
        });
    }
}

/// <summary>
/// Request payload for demo card authorizations.
/// </summary>
/// <param name="CardToken">Tokenized primary account number.</param>
/// <param name="Amount">Requested authorization amount.</param>
/// <param name="Network">Target card network.</param>
public sealed record AuthorizationRequest(string CardToken, decimal Amount, string Network);
