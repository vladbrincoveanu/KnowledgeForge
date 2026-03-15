package com.omnipay.riskstreams;

import java.util.Properties;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.kstream.KStream;

/**
 * Builds the OmniPay Kafka Streams topology used for risk enrichment.
 */
public final class RiskStreamsApplication {

    private RiskStreamsApplication() {
    }

    /**
     * Starts the Kafka Streams application.
     *
     * @param args startup arguments
     */
    public static void main(String[] args) {
        final String bootstrapServers =
            System.getenv().getOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092");
        final String inputTopic =
            System.getenv().getOrDefault("INPUT_TOPIC", "payments.authorized.v1");
        final String outputTopic =
            System.getenv().getOrDefault("OUTPUT_TOPIC", "risk.enriched.v1");

        final Properties properties = new Properties();
        properties.put(StreamsConfig.APPLICATION_ID_CONFIG, "omnipay-risk-streams");
        properties.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        properties.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
        properties.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);

        final StreamsBuilder builder = new StreamsBuilder();
        final KStream<String, String> authorizations = builder.stream(inputTopic);

        authorizations
            .mapValues(RiskStreamsApplication::appendRiskEnvelope)
            .to(outputTopic);

        final KafkaStreams streams = new KafkaStreams(builder.build(), properties);
        Runtime.getRuntime().addShutdownHook(new Thread(streams::close));
        streams.start();
    }

    private static String appendRiskEnvelope(String payload) {
        return payload + "|riskSignals=velocity,merchant_profile,device";
    }
}
