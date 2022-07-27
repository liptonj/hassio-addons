#!/bin/sh

docker build \
  -f /Users/jolipton/apps/hassio-addons/ngrok/Dockerfile \
  --build-arg BUILD_FROM="homeassistant/amd64-base:latest" \
  --build-arg BUILD_ARCH="amd64" \
  --no-cache \
  -t local/ngrok-addon \
  .
