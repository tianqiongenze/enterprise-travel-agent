package com.techgroup.travel.gateway.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.jwt.JwtDecoders;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

/**
 * OIDC resource-server security (Keycloak).
 *
 * <p>Activated with {@code travel.security.mode=oauth2} (set in the dev,
 * staging and prod env templates). When the mode is not {@code oauth2} — unit
 * tests and bare local runs — no filter chain is installed and the fallback
 * mode is logged loudly so the go-live gate can reject it outside local dev.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private static final Logger log = LoggerFactory.getLogger(SecurityConfig.class);

    @Bean
    @ConditionalOnProperty(name = "travel.security.mode", havingValue = "oauth2")
    public JwtDecoder jwtDecoder(
            @Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String issuerUri
    ) {
        return JwtDecoders.fromIssuerLocation(issuerUri);
    }

    @Bean
    @ConditionalOnProperty(name = "travel.security.mode", havingValue = "oauth2")
    public SecurityFilterChain oauth2SecurityFilterChain(
            HttpSecurity http,
            @Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String issuerUri
    ) throws Exception {
        log.info("gateway security: OAuth2 resource server enabled (issuer={})", issuerUri);
        http
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/api/v1/travel/health",
                                "/actuator/health",
                                "/actuator/info"
                        ).permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> jwt.decoder(jwtDecoder(issuerUri))));
        return http.build();
    }

    /**
     * Explicit fallback chain so the oauth2 starter on the classpath does not
     * silently activate Boot's generated-password security in local dev and
     * tests. Rejected by the go-live gate outside local environments.
     */
    @Bean
    @ConditionalOnProperty(name = "travel.security.mode", havingValue = "off", matchIfMissing = true)
    public SecurityFilterChain permitAllSecurityFilterChain(HttpSecurity http) throws Exception {
        log.warn("gateway security: PERMIT-ALL fallback active (travel.security.mode=off) - local dev only");
        http
                .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                .csrf(csrf -> csrf.disable());
        return http.build();
    }
}
