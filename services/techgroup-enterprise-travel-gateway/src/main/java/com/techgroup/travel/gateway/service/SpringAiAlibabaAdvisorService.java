package com.techgroup.travel.gateway.service;

import com.techgroup.travel.gateway.api.dto.TravelRecommendRequest;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/**
 * Spring AI Alibaba advisor: generates the natural-language rationale for
 * recommendations. Calls the DashScope chat model when configured and enabled;
 * any failure (missing builder, blank content, timeout, exception) degrades to
 * the deterministic fallback rationale instead of failing the request.
 */
@Service
public class SpringAiAlibabaAdvisorService {

    private final ObjectProvider<ChatClient.Builder> chatClientBuilderProvider;
    private final boolean enabled;
    private final long timeoutSeconds;
    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "spring-ai-advisor");
        t.setDaemon(true);
        return t;
    });

    public SpringAiAlibabaAdvisorService(
            ObjectProvider<ChatClient.Builder> chatClientBuilderProvider,
            @Value("${travel.ai.advisor.enabled:true}") boolean enabled,
            @Value("${travel.ai.advisor.timeout-seconds:5}") long timeoutSeconds
    ) {
        this.chatClientBuilderProvider = chatClientBuilderProvider;
        this.enabled = enabled;
        this.timeoutSeconds = timeoutSeconds;
    }

    /**
     * Returns the advisor result plus degraded flag; never throws.
     */
    public AdvisorResult advise(TravelRecommendRequest request, String instruction) {
        if (!enabled) {
            return new AdvisorResult(fallbackRationale(request, instruction), true, "advisor-disabled");
        }
        ChatClient.Builder builder = chatClientBuilderProvider.getIfAvailable();
        if (builder == null) {
            return new AdvisorResult(fallbackRationale(request, instruction), true, "chat-client-unavailable");
        }
        Future<String> future = executor.submit(() -> callModel(builder, request, instruction));
        try {
            String content = future.get(timeoutSeconds, TimeUnit.SECONDS);
            if (content == null || content.isBlank()) {
                return new AdvisorResult(fallbackRationale(request, instruction), true, "blank-content");
            }
            return new AdvisorResult(content.trim(), false, null);
        } catch (Exception e) {
            future.cancel(true);
            return new AdvisorResult(fallbackRationale(request, instruction), true, "advisor-error");
        }
    }

    /**
     * Backward-compatible entry point used by /recommend.
     */
    public String buildRationale(TravelRecommendRequest request) {
        return advise(request, null).rationale();
    }

    private String callModel(ChatClient.Builder builder, TravelRecommendRequest request, String instruction) {
        ChatClient chatClient = builder.build();
        String context = "城市=" + request.city() + "，偏好=" + request.preferences() + "，预算=" + request.budget();
        String prompt = (instruction == null || instruction.isBlank())
                ? "请为旅游推荐生成简短建议，" + context
                : instruction + "\n\n上下文：" + context;
        String content = chatClient.prompt().user(prompt).call().content();
        return content == null ? "" : content;
    }

    private String fallbackRationale(TravelRecommendRequest request, String instruction) {
        if (instruction != null && !instruction.isBlank()) {
            return "已根据需求为" + request.city() + "生成建议，优先考虑偏好" + request.preferences() + "与预算约束。";
        }
        return "已按策略为" + request.city() + "生成推荐，优先考虑偏好" + request.preferences() + "与预算约束。";
    }

    /**
     * Advisor outcome with degradation metadata.
     */
    public record AdvisorResult(String rationale, boolean degraded, String reason) {
    }
}
