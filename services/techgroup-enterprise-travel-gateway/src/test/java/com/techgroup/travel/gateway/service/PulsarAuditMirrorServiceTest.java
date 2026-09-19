package com.techgroup.travel.gateway.service;

import org.apache.pulsar.client.api.MessageId;
import org.apache.pulsar.client.api.Producer;
import org.apache.pulsar.client.api.TypedMessageBuilder;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import static org.mockito.ArgumentMatchers.any;

class PulsarAuditMirrorServiceTest {

    @Test
    void publishAsyncShouldSkipWhenDisabled() {
        @SuppressWarnings("unchecked")
        Producer<byte[]> producer = Mockito.mock(Producer.class);
        PulsarAuditMirrorService service = new PulsarAuditMirrorService(false, producer);

        service.publishAsync("trace-1", "beijing", "tenant-a", Map.of("ok", true));

        Mockito.verifyNoInteractions(producer);
    }

    @Test
    void publishAsyncShouldPublishSanitizedPayloadWhenEnabled() {
        @SuppressWarnings("unchecked")
        Producer<byte[]> producer = Mockito.mock(Producer.class);
        @SuppressWarnings("unchecked")
        TypedMessageBuilder<byte[]> builder = Mockito.mock(TypedMessageBuilder.class);
        Mockito.when(producer.newMessage()).thenReturn(builder);
        Mockito.when(builder.key(any())).thenReturn(builder);
        Mockito.when(builder.value(any())).thenReturn(builder);
        Mockito.when(builder.sendAsync()).thenReturn(CompletableFuture.completedFuture(MessageId.earliest));

        PulsarAuditMirrorService service = new PulsarAuditMirrorService(true, producer);
        service.publishAsync("trace\"-01", "shanghai", "tenant\"-a", Map.of("k", "v"));

        Mockito.verify(builder).key("trace-01");
        ArgumentCaptor<byte[]> bodyCaptor = ArgumentCaptor.forClass(byte[].class);
        Mockito.verify(builder).value(bodyCaptor.capture());
        String payload = new String(bodyCaptor.getValue(), StandardCharsets.UTF_8);
        Assertions.assertTrue(payload.contains("\"traceId\":\"trace-01\""));
        Assertions.assertTrue(payload.contains("\"tenantId\":\"tenant-a\""));
        Assertions.assertTrue(payload.contains("\"city\":\"shanghai\""));
    }
}

