package com.techgroup.travel.gateway.service;

import com.techgroup.travel.gateway.api.dto.TravelRecommendRequest;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

@Service
public class SpringAiAlibabaAdvisorService {

    private final ObjectProvider<ChatClient.Builder> chatClientBuilderProvider;

    public SpringAiAlibabaAdvisorService(ObjectProvider<ChatClient.Builder> chatClientBuilderProvider) {
        this.chatClientBuilderProvider = chatClientBuilderProvider;
    }

    public String buildRationale(TravelRecommendRequest request) {
        ChatClient.Builder builder = chatClientBuilderProvider.getIfAvailable();
        if (builder == null) {
            return fallbackRationale(request);
        }
        try {
            ChatClient chatClient = builder.build();
            String prompt = "请为旅游推荐生成简短建议，城市=" + request.city() + "，偏好=" + request.preferences() + "，预算=" + request.budget();
            String content = chatClient.prompt().user(prompt).call().content();
            if (content == null || content.isBlank()) {
                return fallbackRationale(request);
            }
            return content;
        } catch (Exception ignored) {
            return fallbackRationale(request);
        }
    }

    private String fallbackRationale(TravelRecommendRequest request) {
        return "已按策略为" + request.city() + "生成推荐，优先考虑偏好" + request.preferences() + "与预算约束。";
    }
}
