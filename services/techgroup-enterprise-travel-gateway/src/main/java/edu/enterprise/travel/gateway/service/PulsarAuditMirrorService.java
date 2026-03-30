package edu.enterprise.travel.gateway.service;

import org.apache.pulsar.client.api.ClientBuilder;
import org.apache.pulsar.client.api.CompressionType;
import org.apache.pulsar.client.api.MessageRoutingMode;
import org.apache.pulsar.client.api.Producer;
import org.apache.pulsar.client.api.PulsarClient;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Optional audit mirror to Pulsar for recommendation request/response traces.
 */
@Service
public class PulsarAuditMirrorService {

    private final boolean enabled;
    private final PulsarClient client;
    private final Producer<byte[]> producer;

    public PulsarAuditMirrorService() {
        this.enabled = System.getenv().getOrDefault("TRAVEL_GATEWAY_PULSAR_AUDIT_ENABLED", "false").equalsIgnoreCase("true");
        if (!enabled) {
            this.client = null;
            this.producer = null;
            return;
        }

        PulsarClient localClient = null;
        Producer<byte[]> localProducer = null;
        try {
            String serviceUrl = System.getenv().getOrDefault("PULSAR_SERVICE_URL", "pulsar://127.0.0.1:6650");
            String topic = System.getenv().getOrDefault("TRAVEL_GATEWAY_PULSAR_AUDIT_TOPIC", "persistent://public/default/travel-gateway.audit");
            int batchDelayMs = Integer.parseInt(System.getenv().getOrDefault("TRAVEL_GATEWAY_PULSAR_BATCH_DELAY_MS", "10"));
            int maxPending = Integer.parseInt(System.getenv().getOrDefault("TRAVEL_GATEWAY_PULSAR_MAX_PENDING", "1000"));

            ClientBuilder builder = PulsarClient.builder().serviceUrl(serviceUrl);
            localClient = builder.build();
            localProducer = localClient.newProducer()
                    .topic(topic)
                    .enableBatching(true)
                    .batchingMaxPublishDelay(batchDelayMs, TimeUnit.MILLISECONDS)
                    .maxPendingMessages(maxPending)
                    .compressionType(CompressionType.LZ4)
                    .messageRoutingMode(MessageRoutingMode.RoundRobinPartition)
                    .create();
        } catch (Exception error) {
            System.out.println("[gateway-audit] pulsar init failed: " + error.getMessage());
            localClient = null;
            localProducer = null;
        }
        this.client = localClient;
        this.producer = localProducer;
    }

    /**
     * Testing constructor.
     */
    PulsarAuditMirrorService(boolean enabled, Producer<byte[]> producer) {
        this.enabled = enabled;
        this.producer = producer;
        this.client = null;
    }

    /**
     * Sends an audit event asynchronously; best-effort and never blocks business flow.
     */
    public void publishAsync(String traceId, String city, String tenantId, Map<String, Object> payload) {
        if (!enabled || producer == null) {
            return;
        }
        try {
            String body = "{\"traceId\":\"" + safe(traceId) + "\",\"tenantId\":\"" + safe(tenantId)
                    + "\",\"city\":\"" + safe(city) + "\",\"payload\":" + payload.toString() + "}";
            producer.newMessage()
                    .key(safe(traceId))
                    .value(body.getBytes(StandardCharsets.UTF_8))
                    .sendAsync();
        } catch (Exception ignored) {
        }
    }

    private String safe(String value) {
        return value == null ? "" : value.replace("\"", "");
    }
}
