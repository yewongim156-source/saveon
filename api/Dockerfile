# Container image for SAVEON Spring Boot API only (no AI runtime).
# Build context: /api (Render rootDir=api).
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /workspace
COPY . .
RUN chmod +x ./gradlew && ./gradlew bootJar --no-daemon

FROM eclipse-temurin:21-jre-noble
RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg python3-venv \
    && python3 -m venv /opt/saveon-reels \
    && /opt/saveon-reels/bin/pip install --no-cache-dir yt-dlp==2026.10.26 \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/saveon-reels/bin:${PATH}"
WORKDIR /app
COPY --from=builder /workspace/build/libs/*.jar /app/saveon-api.jar
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=55 -XX:ActiveProcessorCount=1"
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/saveon-api.jar"]
