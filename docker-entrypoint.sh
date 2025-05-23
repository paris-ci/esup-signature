#!/bin/bash
set -e

python3 /config-generator.py

# Start the application
exec java -jar /esup-signature.war --spring.config.location=file:/tmp/application-docker.yml
