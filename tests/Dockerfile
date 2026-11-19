FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
# Test helpers only; none of these programs enter the application image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl openssl python3 python3-aioquic \
    && rm -rf /var/lib/apt/lists/*
COPY tests/backend.py tests/http3_client.py /tests/
