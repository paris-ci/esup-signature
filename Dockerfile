# ---- Build Stage ----
FROM maven:3.9.12-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
COPY src ./src
RUN --mount=type=cache,target=/root/.m2/repository \
    --mount=type=cache,target=/root/.m2/.m2 \
    mvn clean package -DskipTests

# ---- Runtime Stage ----
FROM eclipse-temurin:17 AS runtime
RUN apt update && apt upgrade -y && \
    apt install -y ghostscript curl python3 python3-pip git && \
    apt clean && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages 'pyyaml==6.0.3' 'tqdm==4.67.1'

WORKDIR /app
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY config-generator.py /config-generator.py
COPY src/main/resources/application.yml /application.yml
RUN chmod +x /docker-entrypoint.sh

COPY --from=builder /build/target/esup-signature.war /esup-signature.war

ENTRYPOINT ["/docker-entrypoint.sh"]