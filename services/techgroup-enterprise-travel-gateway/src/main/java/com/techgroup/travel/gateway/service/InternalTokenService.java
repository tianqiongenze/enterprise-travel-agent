package com.techgroup.travel.gateway.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;

/**
 * Signs gateway-to-runtime internal requests.
 *
 * <p>Signature is HMAC-SHA256 over "{payload}.{clientId}" with the shared
 * secret as the MAC key, matching the runtime's
 * {@code travel_agent.security.make_internal_signature}. The client id is
 * bound into the message so captured signatures cannot be replayed by another
 * caller; HMAC protects the secret itself against extension/forgery analysis.
 */
@Service
public class InternalTokenService {

    private final String sharedSecret;

    public InternalTokenService(@Value("${travel.internal.shared-secret}") String sharedSecret) {
        this.sharedSecret = sharedSecret;
    }

    public String sign(String payload, String clientId) {
        String message = payload + "." + clientId;
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(sharedSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal(message.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException | InvalidKeyException e) {
            throw new IllegalStateException("HMAC-SHA256 unavailable", e);
        }
    }
}
