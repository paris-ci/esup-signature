# ---- Build Stage ----
FROM maven:3.9.6-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

# ---- Runtime Stage ----
FROM debian:latest
RUN apt update && apt upgrade -y && \
    apt install -y openjdk-17-jdk-headless ghostscript curl && \
    curl -L https://github.com/hairyhenderson/gomplate/releases/download/v3.11.5/gomplate_linux-amd64 -o /usr/local/bin/gomplate && \
    chmod +x /usr/local/bin/gomplate

WORKDIR /app
COPY --from=builder /build/target/esup-signature.war /esup-signature.war
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY config.tmpl /app/config.tmpl
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
