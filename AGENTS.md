# Maintenance instructions

- Read `requirement.md`, `README.md` and `TASK.md` before changing behavior. Preserve the user's requirement edits.
- Production target is Linux amd64. Runtime must remain distroless, UID/GID 65532:65532, with no shell/package manager/compiler. Do not switch to a debug image to make tests pass.
- Keep builder/runtime on the same Debian major version. Keep real package metadata for copied shared libraries; never copy the whole builder package database into runtime.
- Change Nginx version, source URL and SHA256 together. Verify a new release/checksum before updating. Pin base/tool images by digest and Actions by commit SHA.
- Defaults: HTTP only (host 80 → container 8080), Asia/Bangkok, stdout logs using nginx-log-json-no-post-body. HTTPS/HTTP3 stay opt-in examples. Config, HTML, certificates and CA mounts remain read-only. Runtime writes belong in /tmp.
- Keep Git tags verbatim; only branch slashes become hyphens. Only refs/heads/main may publish latest. Invalid/reserved names fail; collisions may overwrite.
- Security gate must fail closed on HIGH/CRITICAL, Hadolint errors, scanner/report failures, build/test failures. Do not add ignore-unfixed, CVE exclusions or success overrides to get a green run. Always attempt report uploads; retention is 30 days.
- Trivy may miss source-built Nginx. Preserve the documented limitation and build-info inventory; do not present an empty scan as proof that Nginx is vulnerability-free.
- Run `python3 -m unittest discover -s tests -p 'test_ci.py' -v`, Compose validation, build, `tests/runtime.py` and `ci/scan.sh` for changes affecting image/CI/runtime behavior. The test-tools image must be built separately. See README for commands.
- On this Windows workspace, use the run-wsl skill and Docker in WSL Ubuntu. Scope test fixtures/containers to the unique integration-test run. Do not alter unrelated containers or volumes.
- Never commit certificates, private keys, tokens, .env, reports or generated test fixtures. Do not push images manually while scans fail.
- Record implementation changes, actual validation results and unresolved limitations in TASK.md. Never mark an unexecuted check as passed.
