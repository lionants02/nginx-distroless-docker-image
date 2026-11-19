#!/usr/bin/env bash
# Run every scanner, even after another scanner fails. Return the combined gate.
set -uo pipefail
cd "$(dirname "$0")/.."
source ci/tools.env
image=${1:?Usage: bash ci/scan.sh IMAGE [REPORT_DIRECTORY]}
reports=$(realpath -m "${2:-reports}")
mkdir -p "$reports" .test-work/trivy-cache
cache=$(realpath .test-work/trivy-cache)
archive_dir=$(mktemp -d "$(pwd)/.test-work/scan-XXXXXXXX")
trap 'rm -f "$archive_dir/image.tar"; rmdir "$archive_dir"' EXIT

# A previous local run must never supply a successful status for an incomplete run.
for name in image-save hadolint trivy-config trivy-image sbom; do
    printf '125\n' > "$reports/$name.exit"
done

# Persist the exact local runtime image; do not scan a tag fetched from a registry.
docker image save --output "$archive_dir/image.tar" "$image" > "$reports/image-save.log" 2>&1
printf '%s\n' "$?" > "$reports/image-save.exit"

docker run --rm -i "$HADOLINT_IMAGE" hadolint \
    --failure-threshold error --format json - \
    < Dockerfile > "$reports/hadolint.json" 2> "$reports/hadolint.log"
printf '%s\n' "$?" > "$reports/hadolint.exit"

trivy() {
    docker run --rm --user "$(id -u):$(id -g)" \
        --mount "type=bind,src=$(pwd),dst=/work,readonly" \
        --mount "type=bind,src=$reports,dst=/reports" \
        --mount "type=bind,src=$archive_dir,dst=/image,readonly" \
        --mount "type=bind,src=$cache,dst=/cache" \
        -e TRIVY_CACHE_DIR=/cache "$TRIVY_IMAGE" "$@"
}
trivy config --format json --output /reports/trivy-config.json \
    /work/Dockerfile > "$reports/trivy-config.log" 2>&1
printf '%s\n' "$?" > "$reports/trivy-config.exit"

trivy image --input /image/image.tar --scanners vuln --list-all-pkgs \
    --format json --output /reports/trivy-image.json \
    > "$reports/trivy-image.log" 2>&1
printf '%s\n' "$?" > "$reports/trivy-image.exit"

trivy image --input /image/image.tar --format cyclonedx \
    --output /reports/sbom.cdx.json > "$reports/sbom.log" 2>&1
printf '%s\n' "$?" > "$reports/sbom.exit"

python3 ci/scan_gate.py "$reports"
