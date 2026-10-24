package com.techgroup.travel.gateway.service;

import com.techgroup.travel.gateway.api.dto.TravelRecommendRequest;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.ObjectProvider;

import java.util.List;

/**
 * Unit tests for the Spring AI Alibaba advisor degradation contract.
 * The ChatClient.Builder is stubbed with Mockito so no DashScope key or
 * network access is required.
 */
class SpringAiAlibabaAdvisorServiceTest {

    private TravelRecommendRequest request() {
        return new TravelRecommendRequest(
                "tenant-a", "user-a", "policy-default", "conv-1", "idem-1",
                "北京", 3, 3000.0, 2, "basic", List.of("family"), 10, 10,
                List.of("search_hotels"));
    }

    @Test
    void disabledAdvisorDegrades() {
        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(
                Mockito.mock(ObjectProvider.class), false, 5);
        SpringAiAlibabaAdvisorService.AdvisorResult result = service.advise(request(), "润色这段话");
        Assertions.assertTrue(result.degraded());
        Assertions.assertEquals("advisor-disabled", result.reason());
        Assertions.assertFalse(result.rationale().isBlank());
    }

    @Test
    void missingChatClientBuilderDegrades() {
        @SuppressWarnings("unchecked")
        ObjectProvider<ChatClient.Builder> provider = Mockito.mock(ObjectProvider.class);
        Mockito.when(provider.getIfAvailable()).thenReturn(null);
        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(provider, true, 5);
        SpringAiAlibabaAdvisorService.AdvisorResult result = service.advise(request(), null);
        Assertions.assertTrue(result.degraded());
        Assertions.assertEquals("chat-client-unavailable", result.reason());
    }

    @Test
    void blankModelContentDegrades() {
        @SuppressWarnings("unchecked")
        ObjectProvider<ChatClient.Builder> provider = Mockito.mock(ObjectProvider.class);
        ChatClient.Builder builder = Mockito.mock(ChatClient.Builder.class, Mockito.RETURNS_DEEP_STUBS);
        Mockito.when(builder.build().prompt().user(Mockito.anyString()).call().content()).thenReturn("  ");
        Mockito.when(provider.getIfAvailable()).thenReturn(builder);

        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(provider, true, 5);
        SpringAiAlibabaAdvisorService.AdvisorResult result = service.advise(request(), null);
        Assertions.assertTrue(result.degraded());
        Assertions.assertEquals("blank-content", result.reason());
    }

    @Test
    void healthyModelCallReturnsContent() {
        @SuppressWarnings("unchecked")
        ObjectProvider<ChatClient.Builder> provider = Mockito.mock(ObjectProvider.class);
        ChatClient.Builder builder = Mockito.mock(ChatClient.Builder.class, Mockito.RETURNS_DEEP_STUBS);
        Mockito.when(builder.build().prompt().user(Mockito.anyString()).call().content())
                .thenReturn("  建议优先选择家庭房型，控制预算。  ");
        Mockito.when(provider.getIfAvailable()).thenReturn(builder);

        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(provider, true, 5);
        SpringAiAlibabaAdvisorService.AdvisorResult result = service.advise(request(), null);
        Assertions.assertFalse(result.degraded());
        Assertions.assertEquals("建议优先选择家庭房型，控制预算。", result.rationale());
    }

    @Test
    void modelExceptionDegrades() {
        @SuppressWarnings("unchecked")
        ObjectProvider<ChatClient.Builder> provider = Mockito.mock(ObjectProvider.class);
        ChatClient.Builder builder = Mockito.mock(ChatClient.Builder.class, Mockito.RETURNS_DEEP_STUBS);
        Mockito.when(builder.build().prompt().user(Mockito.anyString()).call().content())
                .thenThrow(new RuntimeException("dashscope down"));
        Mockito.when(provider.getIfAvailable()).thenReturn(builder);

        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(provider, true, 5);
        SpringAiAlibabaAdvisorService.AdvisorResult result = service.advise(request(), null);
        Assertions.assertTrue(result.degraded());
        Assertions.assertEquals("advisor-error", result.reason());
    }

    @Test
    void slowModelCallTimesOutAndDegrades() {
        @SuppressWarnings("unchecked")
        ObjectProvider<ChatClient.Builder> provider = Mockito.mock(ObjectProvider.class);
        ChatClient.Builder builder = Mockito.mock(ChatClient.Builder.class, Mockito.RETURNS_DEEP_STUBS);
        Mockito.when(builder.build().prompt().user(Mockito.anyString()).call().content())
                .thenAnswer(invocation -> {
                    Thread.sleep(3000);
                    return "late";
                });
        Mockito.when(provider.getIfAvailable()).thenReturn(builder);

        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(provider, true, 1);
        SpringAiAlibabaAdvisorService.AdvisorResult result = service.advise(request(), null);
        Assertions.assertTrue(result.degraded());
        Assertions.assertEquals("advisor-error", result.reason());
    }

    @Test
    void buildRationaleRemainsBackwardCompatible() {
        SpringAiAlibabaAdvisorService service = new SpringAiAlibabaAdvisorService(
                Mockito.mock(ObjectProvider.class), false, 5);
        String rationale = service.buildRationale(request());
        Assertions.assertTrue(rationale.contains("北京"));
    }
}
