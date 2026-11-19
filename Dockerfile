# syntax=docker/dockerfile:1
FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 AS build

ARG NGINX_VERSION=1.30.7
ARG NGINX_URL=https://github.com/nginx/nginx/releases/download/release-1.30.7/nginx-1.30.7.tar.gz
ARG NGINX_SHA256=2565b5c837050e958f70fb0f73c48e2bca4542ad349fd356f46fb0c72610bc6e

# Debian's signed repositories supply current security fixes; resolved versions
# are recorded in build-info.txt. Keep builder and runtime on Debian 13.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential ca-certificates curl libpcre2-dev libssl-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN curl --fail --show-error --location --proto '=https' --tlsv1.2 \
        --retry 3 --output nginx.tar.gz "${NGINX_URL}" \
    && printf '%s  nginx.tar.gz\n' "${NGINX_SHA256}" > nginx.sha256 \
    && sha256sum --check --strict nginx.sha256 \
    && tar -xzf nginx.tar.gz \
    && test -d "nginx-${NGINX_VERSION}"

WORKDIR /src/nginx-${NGINX_VERSION}
RUN ./configure \
      --prefix=/etc/nginx \
      --sbin-path=/usr/sbin/nginx \
      --conf-path=/etc/nginx/nginx.conf \
      --pid-path=/tmp/nginx.pid \
      --lock-path=/tmp/nginx.lock \
      --error-log-path=/dev/stdout \
      --http-log-path=/dev/stdout \
      --http-client-body-temp-path=/tmp/client_temp \
      --http-proxy-temp-path=/tmp/proxy_temp \
      --http-fastcgi-temp-path=/tmp/fastcgi_temp \
      --http-uwsgi-temp-path=/tmp/uwsgi_temp \
      --http-scgi-temp-path=/tmp/scgi_temp \
      --with-cc-opt='-O2 -fstack-protector-strong -fPIE -D_FORTIFY_SOURCE=2' \
      --with-ld-opt='-Wl,-z,relro,-z,now -pie' \
      --with-http_ssl_module --with-http_v2_module --with-http_v3_module \
      --with-http_realip_module --with-http_stub_status_module \
      --with-stream --with-stream_ssl_module --with-stream_ssl_preread_module \
      --with-threads --with-file-aio \
    && make -j"$(nproc)"

COPY scripts/assemble-runtime.sh /usr/local/bin/assemble-runtime
RUN sh /usr/local/bin/assemble-runtime /out "${NGINX_VERSION}" "${NGINX_URL}" "${NGINX_SHA256}"

FROM gcr.io/distroless/base-nossl-debian13:nonroot@sha256:89815d620ac01d8de13cdaf04d19ed874447ca2296d4985b14b818f6e5e47854 AS runtime
COPY --from=build /out/ /
COPY nginx-conf/ /etc/nginx/
COPY static-html/ /usr/share/nginx/html/

ENV TZ=Asia/Bangkok
LABEL org.opencontainers.image.title="Nginx distroless" \
      org.opencontainers.image.source="https://github.com/lionants02/nginx-distroless-docker-image" \
      org.opencontainers.image.description="Source-built Nginx with HTTP/2, HTTP/3 and stream; non-root Debian distroless runtime"

WORKDIR /
USER 65532:65532
EXPOSE 8080 8443 8443/udp
STOPSIGNAL SIGQUIT
# Syntax/readability check only; actual HTTP/protocol checks run outside the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["/usr/sbin/nginx", "-t"]
ENTRYPOINT ["/usr/sbin/nginx"]
CMD ["-g", "daemon off;"]
