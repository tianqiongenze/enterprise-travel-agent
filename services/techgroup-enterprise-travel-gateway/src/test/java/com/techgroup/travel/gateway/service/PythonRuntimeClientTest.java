package com.techgroup.travel.gateway.service;

import com.techgroup.travel.gateway.api.dto.TravelRecommendRequest;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class PythonRuntimeClientTest {

    @Test
    void recommendShouldAttachInternalHeadersAndReturnBody() {
        RestTemplate restTemplate = new RestTemplate(new SimpleClientHttpRequestFactory());
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        InternalTokenService tokenService = new InternalTokenService("secret-test", "");
        PythonRuntimeClient client = new PythonRuntimeClient(restTemplate, "http://localhost:8000", "gateway-a", tokenService);

        server.expect(requestTo("http://localhost:8000/runtime/recommend"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Trace-Id", "trace-001"))
                .andExpect(header("X-Internal-Client-Id", "gateway-a"))
                .andExpect(header("X-Internal-Signature", tokenService.sign("idem-1", "gateway-a")))
                .andRespond(withSuccess("{\"hotel_options\":[],\"transport_options\":[]}", MediaType.APPLICATION_JSON));

        Map<String, Object> response = client.recommend(sampleRequest(), "trace-001");

        Assertions.assertTrue(response.containsKey("hotel_options"));
        server.verify();
    }

    @Test
    void recommendShouldFailWhenBodyIsEmpty() {
        RestTemplate restTemplate = new RestTemplate(new SimpleClientHttpRequestFactory());
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        InternalTokenService tokenService = new InternalTokenService("secret-test", "");
        PythonRuntimeClient client = new PythonRuntimeClient(restTemplate, "http://localhost:8000", "gateway-a", tokenService);

        server.expect(requestTo("http://localhost:8000/runtime/recommend"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withSuccess("", MediaType.APPLICATION_JSON));

        Assertions.assertThrows(IllegalStateException.class, () -> client.recommend(sampleRequest(), "trace-001"));
    }

    private TravelRecommendRequest sampleRequest() {
        return new TravelRecommendRequest(
                "tenant-a", "user-a", "policy-default", "conv-1", "idem-1",
                "beijing", 3, 3000.0, 2, "basic", List.of("family"),
                10, 10, List.of("search_hotels", "search_transports", "search_attractions")
        );
    }
}

