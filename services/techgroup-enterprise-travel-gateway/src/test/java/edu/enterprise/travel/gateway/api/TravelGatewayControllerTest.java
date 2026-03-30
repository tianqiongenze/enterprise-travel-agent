package edu.enterprise.travel.gateway.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import edu.enterprise.travel.gateway.service.PolicyGuardService;
import edu.enterprise.travel.gateway.service.PulsarAuditMirrorService;
import edu.enterprise.travel.gateway.service.PythonRuntimeClient;
import edu.enterprise.travel.gateway.service.SpringAiAlibabaAdvisorService;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;
import java.util.HashMap;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.hamcrest.Matchers.containsString;

@WebMvcTest(controllers = TravelGatewayController.class)
class TravelGatewayControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private PolicyGuardService policyGuardService;

    @MockitoBean
    private PythonRuntimeClient pythonRuntimeClient;

    @MockitoBean
    private SpringAiAlibabaAdvisorService springAiAlibabaAdvisorService;

    @MockitoBean
    private PulsarAuditMirrorService pulsarAuditMirrorService;

    @Test
    void recommendShouldReturnOk() throws Exception {
        Mockito.when(pythonRuntimeClient.recommend(Mockito.any(), Mockito.anyString())).thenReturn(Map.of(
                "hotel_options", List.of(),
                "transport_options", List.of(),
                "itinerary", List.of(),
                "audit_logs", List.of(),
                "a2a_logs", List.of()
        ));
        Mockito.when(springAiAlibabaAdvisorService.buildRationale(Mockito.any())).thenReturn("mock ai rationale");

        Map<String, Object> req = validRequest();

        mockMvc.perform(post("/api/v1/travel/recommend")
                        .header("X-Trace-Id", "trace-test-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.traceId").value("trace-test-001"));

        Mockito.verify(pythonRuntimeClient).recommend(any(), anyString());
    }

    @Test
    void recommendShouldReturnPolicyViolationErrorContract() throws Exception {
        Mockito.doThrow(new IllegalArgumentException("allowedTools contains unsupported tool"))
                .when(policyGuardService)
                .validate(Mockito.any());

        mockMvc.perform(post("/api/v1/travel/recommend")
                        .header("X-Trace-Id", "trace-policy-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(validRequest())))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("POLICY_VIOLATION"))
                .andExpect(jsonPath("$.traceId").value("trace-policy-001"))
                .andExpect(jsonPath("$.path").value("/api/v1/travel/recommend"))
                .andExpect(jsonPath("$.suggestion", containsString("allowedTools")));
    }

    @Test
    void recommendShouldReturnValidationErrorContract() throws Exception {
        Map<String, Object> req = validRequest();
        req.remove("allowedTools");

        mockMvc.perform(post("/api/v1/travel/recommend")
                        .header("X-Trace-Id", "trace-validation-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.traceId").value("trace-validation-001"))
                .andExpect(jsonPath("$.path").value("/api/v1/travel/recommend"));
    }

    private Map<String, Object> validRequest() {
        Map<String, Object> req = new HashMap<>();
        req.put("tenantId", "tenant-a");
        req.put("userId", "user-a");
        req.put("policyId", "policy-default");
        req.put("conversationId", "conv-1");
        req.put("idempotencyKey", "idem-1");
        req.put("city", "北京");
        req.put("days", 3);
        req.put("budget", 3000);
        req.put("travelers", 2);
        req.put("membershipTier", "basic");
        req.put("preferences", List.of("family"));
        req.put("maxAgentSteps", 10);
        req.put("maxToolCalls", 10);
        req.put("allowedTools", List.of("search_hotels", "search_transports", "search_attractions"));
        return req;
    }
}
