package edu.enterprise.travel.gateway.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

@Service
public class InternalTokenService {

    private final String sharedSecret;

    public InternalTokenService(@Value("${travel.internal.shared-secret}") String sharedSecret) {
        this.sharedSecret = sharedSecret;
    }

    public String sign(String payload) {
        String raw = payload + "." + sharedSecret;
        return sha256(raw);
    }

    private String sha256(String value) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("sha256 unavailable", e);
        }
    }
}
