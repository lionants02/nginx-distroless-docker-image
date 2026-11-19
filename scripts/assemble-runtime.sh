#!/bin/sh
set -eu

output=$1
version=$2
source_url=$3
source_sha256=$4
install -D -m 0755 objs/nginx "$output/usr/sbin/nginx"
install -D -m 0644 LICENSE "$output/usr/share/licenses/nginx/LICENSE"
mkdir -p "$output/var/lib/dpkg/status.d" "$output/usr/share/nginx"

# Derive the complete transitive closure: OpenSSL can gain dependencies such as
# libzstd between Debian updates. The matching distroless base supplies glibc/ld.
ldd objs/nginx > /tmp/nginx-linked-libraries.txt
awk '/=> \// {print $3} /^[[:space:]]*\// {print $1}' /tmp/nginx-linked-libraries.txt > /tmp/nginx-library-paths.txt
: > /tmp/nginx-runtime-packages.txt
while IFS= read -r library; do
    case "${library##*/}" in
        libc.so.6|ld-linux-*.so.*) continue ;;
    esac
    ownership=$(dpkg-query -S "$(readlink -f "$library")")
    printf '%s\n' "${ownership%%:*}" >> /tmp/nginx-runtime-packages.txt
done < /tmp/nginx-library-paths.txt
sort -u /tmp/nginx-runtime-packages.txt > /tmp/nginx-runtime-packages.sorted
test -s /tmp/nginx-runtime-packages.sorted

# Preserve metadata for the exact libraries copied, not the whole builder database.
while IFS= read -r package; do
    dpkg-query -s "$package" > "$output/var/lib/dpkg/status.d/$package"
    dpkg-query -L "$package" | while IFS= read -r path; do
        case "$path" in
            /usr/lib/*/*.so*|/usr/lib/*/ossl-modules/*|/usr/share/doc/*/copyright)
                if [ -f "$path" ] || [ -L "$path" ]; then
                    cp -a --parents "$path" "$output"
                fi
                ;;
        esac
    done
done < /tmp/nginx-runtime-packages.sorted

{
    printf 'Nginx version: %s\nSource URL: %s\nSource SHA256: %s\n' "$version" "$source_url" "$source_sha256"
    printf '\nRuntime packages copied from the builder:\n'
    while IFS= read -r package; do
        dpkg-query -W -f='${binary:Package}\t${Version}\n' "$package"
    done < /tmp/nginx-runtime-packages.sorted
    printf '\nBuild configuration:\n'
    objs/nginx -V 2>&1
    printf '\nLinked libraries (builder paths):\n'
    ldd objs/nginx
} > "$output/usr/share/nginx/build-info.txt"
