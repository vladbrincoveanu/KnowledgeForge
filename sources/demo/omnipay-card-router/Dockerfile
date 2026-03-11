FROM mcr.microsoft.com/dotnet/aspnet:8.0

WORKDIR /app
COPY publish/ .

EXPOSE 8088

ENTRYPOINT ["dotnet", "OmniPay.CardRouter.dll"]
