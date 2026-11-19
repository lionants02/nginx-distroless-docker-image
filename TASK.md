# Development record

## 2026-11-19 — implementation

- Added source-compiled Nginx 1.30.7 with the required SHA256 verification, hardened compiler/linker flags, HTTP/2, HTTP/3, HTTPS and stream modules.
- Added pinned Debian 13 builder/distroless nonroot runtime, shared-library package metadata, licenses and build-info inventory.
- Added Compose with HTTP 80:8080, four read-only bind mounts, read-only root filesystem, tmpfs, dropped capabilities, extra_hosts and Asia/Bangkok timezone.
- Adapted existing Nginx config for non-root paths and JSON stdout logs without request body; retained both original log formats.
- Added opt-in HTTPS/HTTP3, reverse proxy/private CA and stream examples, GHCR pull/run documentation and project tree.
- Added push-triggered GitHub Actions workflow with strict tag validation, build-once scan/test/publish ordering, reports retained 30 days and failure summaries/uploads.
- Added pinned scanners, fail-closed gate, CycloneDX SBOM, CI edge-case tests and isolated protocol integration tests including negative CA verification.
- Documented Trivy coverage limitations and maintenance instructions in AGENTS.md.

## Validation

Completed locally on 2026-11-19 using Docker Engine 29.8.0 / Compose v5.5.1 in WSL Ubuntu (Linux amd64).

| Check | Actual result |
| --- | --- |
| Build/source SHA256 | PASS; Nginx 1.30.7, OpenSSL 3.5.7, source checksum matched |
| Runtime integration | PASS; all 27 checks in `reports/runtime-tests.log` |
| HTTP/HTTPS/HTTP2/HTTP3 | PASS; real requests, verified TLS, no protocol fallback |
| Reverse proxy/extra_hosts/private CA | PASS; trusted CA accepted, wrong CA rejected, restored CA applied by reload |
| TCP stream | PASS; real echo payload forwarded |
| Reload | PASS; mounted config adds a new listener without restarting container |
| Runtime restrictions/logs/timezone | PASS; actual PID 1 UID 65532, zero effective capabilities, no tested shells/package managers, read-only root/mounts, JSON stdout without body, +07:00 |
| Default Compose | PASS; actual `compose run ... nginx -t` and HTTP-only 80:8080 mapping |
| TLS Compose override | PASS; `docker compose ... config --quiet` |
| CI tag/scan gate unit tests | PASS; 11 tests, including reserved/invalid tags, missing reports/tool failures, empty scans, missing metadata and HIGH/CRITICAL blocking |
| Hadolint v2.15.1 | PASS; empty findings array (no errors or warnings) |
| Trivy v0.76.2 Dockerfile | PASS; 27 checks, zero failures |
| Trivy final image | PASS under required gate; HIGH 0, CRITICAL 0; MEDIUM 23, LOW 9, UNKNOWN 4 remain in the complete report |
| Runtime package inventory | PASS; Trivy identifies libcrypt1, PCRE2, OpenSSL, libzstd and zlib, plus distroless base packages |
| CycloneDX SBOM | PASS; generated `reports/sbom.cdx.json` |
| Workflow static validation | PASS; pinned actionlint, workflow text only via stdin, networking disabled |
| Shell syntax / Python compile / diff whitespace | PASS |

Tested/scanned local image: `nginx-distroless:local`, image ID
`sha256:8289129669686ead46947b1917ae69a830057bb81ce993ef6024de9455845164`;
reported image size 50,326,553 bytes (approximately 50.3 MB).

The initial runtime trials exposed missing libcrypt/libzstd dependencies and missing nested mountpoints under the read-only config directory. Fixed the assembly to derive transitive library dependencies from `ldd`, retain their package metadata, and keep empty CA/SSL mountpoint directories. Rebuilt, rescanned and reran the complete integration suite successfully afterward.

All integration-test containers stopped and their temporary networks/keys were removed by the test harness. No application deployment was left running. Local images/build cache and ignored reports remain for review. Files have not been committed or pushed; GitHub-hosted execution/GHCR publication are not claimed as tested.

## Known limitations

- Trivy may not identify the source-built Nginx binary as a vulnerable package. Review Nginx advisories using the recorded source version/checksum; the workflow does not automate that extra advisory review.
- Debian package versions are resolved from signed repositories at build time; builds on different dates are not guaranteed byte-identical.
- GHCR publication and GitHub-hosted workflow execution require pushing the files to GitHub; they are not executed by the local implementation task.
