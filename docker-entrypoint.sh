#!/bin/bash
set -e

# Generate the configuration file
gomplate -f /app/config.tmpl > /tmp/application-docker.yml

# Start the application
exec java -jar /esup-signature.war --spring.config.location=file:/tmp/application-docker.yml 