# OmniPay Risk Streams

Owner: Vlas

This service runs a Kafka Streams topology that enriches card-authorization
events with merchant and velocity risk hints before forwarding them to risk
operations topics.

## Technology

- Java 21
- Apache Kafka Streams
- Kafka topics for authorization and risk alert pipelines

## Dependencies

- org.apache.kafka:kafka-streams
- org.slf4j:slf4j-simple

## Environment Variables

- `KAFKA_BOOTSTRAP_SERVERS`
- `INPUT_TOPIC`
- `OUTPUT_TOPIC`
