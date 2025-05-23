# ---- Build Stage ----
FROM maven:3.9.6-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
# Cache Maven dependencies
RUN --mount=type=cache,target=/root/.m2/repository \
    --mount=type=cache,target=/root/.m2/.m2 \
    mvn dependency:go-offline

COPY src ./src
RUN --mount=type=cache,target=/root/.m2/repository \
    --mount=type=cache,target=/root/.m2/.m2 \
    mvn clean package -DskipTests

# ---- Runtime Stage ----
FROM debian:latest
RUN apt update && apt upgrade -y && \
    apt install -y openjdk-17-jdk-headless ghostscript curl

COPY --from=hairyhenderson/gomplate:stable /gomplate /usr/local/bin/gomplate

WORKDIR /app
COPY --from=builder /build/target/esup-signature.war /esup-signature.war
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY config.tmpl /app/config.tmpl
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
