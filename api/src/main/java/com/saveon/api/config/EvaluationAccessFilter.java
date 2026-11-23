package com.saveon.api.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Temporary shared evaluation-room access gate.
 *
 * Protects every /api/v1 route on Render, including reads and AI operations.
 * This is NOT per-student data isolation. Every admitted student sees the same
 * disposable evaluation database. Do not store personal or confidential media.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class EvaluationAccessFilter extends OncePerRequestFilter {

    private final String accessKey;
    private final String allowedOrigin;

    public EvaluationAccessFilter(
            @Value("${SAVEON_EVALUATION_ACCESS_KEY:}") String accessKey,
            @Value("${SAVEON_EVALUATION_ALLOWED_ORIGIN:https://saveon-mobile.vercel.app}") String allowedOrigin
    ) {
        this.accessKey = accessKey.trim();
        this.allowedOrigin = allowedOrigin.trim();
    }

    private boolean required() {
        return System.getenv("RENDER_SERVICE_ID") != null
                || System.getenv("RENDER") != null
                || System.getenv("PORT") != null
                || "true".equalsIgnoreCase(System.getenv("SAVEON_EVALUATION_REQUIRE_KEY"));
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !("/api/v1".equals(path) || path.startsWith("/api/v1/"));
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain chain
    ) throws ServletException, IOException {
        if (!required()) {
            chain.doFilter(request, response);
            return;
        }

        String origin = request.getHeader("Origin");
        if (origin != null && !allowedOrigin.equals(origin)) {
            response.sendError(HttpServletResponse.SC_FORBIDDEN, "Origin not allowed");
            return;
        }
        if (origin != null) {
            response.setHeader("Access-Control-Allow-Origin", allowedOrigin);
            response.setHeader("Vary", "Origin");
            response.setHeader("Access-Control-Allow-Headers",
                    "Content-Type, X-Saveon-Evaluation-Code");
            response.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
            response.setHeader("Access-Control-Max-Age", "600");
        }
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            response.setStatus(HttpServletResponse.SC_NO_CONTENT);
            return;
        }

        // Fail closed when hosted but the secret has not yet been configured.
        if (accessKey.isBlank()) {
            response.sendError(HttpServletResponse.SC_SERVICE_UNAVAILABLE,
                    "Evaluation access has not been configured");
            return;
        }

        String supplied = request.getHeader("X-Saveon-Evaluation-Code");
        byte[] expectedBytes = accessKey.getBytes(StandardCharsets.UTF_8);
        byte[] suppliedBytes = supplied == null
                ? new byte[0] : supplied.getBytes(StandardCharsets.UTF_8);
        if (!MessageDigest.isEqual(expectedBytes, suppliedBytes)) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED,
                    "Invalid evaluation access code");
            return;
        }
        chain.doFilter(request, response);
    }
}
