using Microsoft.EntityFrameworkCore;
using OmniPay.CardRouter.Data;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddDbContext<CardRouterDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("CardRouter")));

var app = builder.Build();

app.MapControllers();

app.Run();
