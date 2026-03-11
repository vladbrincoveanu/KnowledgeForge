FROM eclipse-temurin:21-jre

WORKDIR /app
COPY target/omnipay-ledger.jar /app/omnipay-ledger.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/omnipay-ledger.jar"]
