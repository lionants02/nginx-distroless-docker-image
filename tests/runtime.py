#!/usr/bin/env python3
"""Exercise the built image with isolated fixtures; never touch deployment services."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TOOLS = "nginx-distroless-test-tools:local"
IMAGE = sys.argv[1] if len(sys.argv) > 1 else "nginx-distroless:local"
RUN = f"nginx-test-{uuid.uuid4().hex[:10]}"
WORK = ROOT / ".test-work" / RUN
REPORTS = ROOT / "reports"
CONTAINERS = []


def command(*args, check=True, env=None):
    result = subprocess.run([str(arg) for arg in args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and result.returncode:
        raise RuntimeError(f"Command failed: {' '.join(map(str, args))}\n{result.stdout}\n{result.stderr}")
    return result


def docker(*args, **kwargs):
    return command("docker", *args, **kwargs)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}", flush=True)


def helper(*args, namespace=None):
    options = ["run", "--rm", "--mount", f"type=bind,src={WORK / 'certs'},dst=/certs,readonly"]
    if namespace:
        options += ["--network", f"container:{namespace}"]
    return docker(*options, TOOLS, *args).stdout


def request(path="/", *options):
    return helper("curl", "--fail", "--silent", "--show-error", "--max-time", "15", *options, path, namespace=RUN)


def copy_file(container, path):
    result = subprocess.run(["docker", "cp", f"{container}:{path}", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        member = next(item for item in archive.getmembers() if item.isfile())
        return archive.extractfile(member).read().decode()


def main():
    REPORTS.mkdir(exist_ok=True)
    (WORK / "certs").mkdir(parents=True)
    shutil.copytree(ROOT / "nginx-conf", WORK / "conf")
    shutil.copytree(ROOT / "static-html", WORK / "html")
    config = WORK / "conf" / "nginx.conf"
    config.write_text(config.read_text().replace("worker_processes auto;", "worker_processes 1;"))
    (WORK / "conf/conf.d/tls.conf").write_text((ROOT / "examples/http3.conf.example").read_text())
    (WORK / "conf/conf.d/proxy.conf").write_text("""server {
    listen 8080;
    server_name proxy.example;
    location / {
        proxy_pass https://backend.example:9443;
        proxy_ssl_trusted_certificate /etc/nginx/ca/ca-bundle.pem;
        proxy_ssl_verify on;
        proxy_ssl_server_name on;
    }
}
""")
    (WORK / "conf/stream.d/echo.conf").write_text("server { listen 9000; proxy_pass backend.example:9001; }\n")
    cert_mount = f"type=bind,src={WORK / 'certs'},dst=/certs"

    def openssl(*args):
        docker("run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "--mount", cert_mount, TOOLS, "openssl", *args)

    openssl("req", "-x509", "-newkey", "rsa:2048", "-noenc", "-days", "1", "-subj", "/CN=Integration-Test-CA", "-keyout", "/certs/ca.key", "-out", "/certs/ca-bundle.pem")
    openssl("req", "-newkey", "rsa:2048", "-noenc", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,DNS:backend.example,IP:127.0.0.1", "-keyout", "/certs/privkey.pem", "-out", "/certs/server.csr")
    openssl("x509", "-req", "-in", "/certs/server.csr", "-CA", "/certs/ca-bundle.pem", "-CAkey", "/certs/ca.key", "-CAcreateserial", "-days", "1", "-copy_extensions", "copy", "-out", "/certs/fullchain.pem")
    (WORK / "certs/privkey.pem").chmod(0o644)  # disposable fixture only

    docker("network", "create", RUN)
    try:
        compose_env = {**os.environ, "NGINX_IMAGE": IMAGE, "TZ": "Asia/Bangkok"}
        compose = ("docker", "compose", "-f", ROOT / "compose.yml", "--project-name", RUN)
        resolved = json.loads(command(*compose, "config", "--format", "json", env=compose_env).stdout)
        ports = resolved["services"]["nginx"]["ports"]
        check(len(ports) == 1 and ports[0]["target"] == 8080 and str(ports[0]["published"]) == "80", "default Compose publishes HTTP 80:8080 only")
        command(*compose, "run", "--rm", "-T", "--no-deps", "--pull", "never", "nginx", "-t", env=compose_env)
        check(True, "actual default Compose mounts and configuration pass nginx -t")
        backend = RUN + "-backend"
        docker("run", "--rm", "-d", "--name", backend, "--network", RUN, "--mount", cert_mount + ",readonly", TOOLS, "python3", "/tests/backend.py")
        CONTAINERS.append(backend)
        backend_ip = json.loads(docker("inspect", backend).stdout)[0]["NetworkSettings"]["Networks"][RUN]["IPAddress"]
        docker("run", "--rm", "-d", "--name", RUN, "--network", RUN,
               "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
               "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
               "--add-host", f"backend.example:{backend_ip}",
               "--mount", f"type=bind,src={WORK / 'conf'},dst=/etc/nginx,readonly",
               "--mount", f"type=bind,src={WORK / 'html'},dst=/usr/share/nginx/html,readonly",
               "--mount", cert_mount.replace("dst=/certs", "dst=/etc/nginx/ssl") + ",readonly",
               "--mount", cert_mount.replace("dst=/certs", "dst=/etc/nginx/ca") + ",readonly", IMAGE)
        CONTAINERS.append(RUN)
        for attempt in range(30):
            state = json.loads(docker("inspect", RUN).stdout)[0]["State"]
            if not state["Running"]:
                raise RuntimeError(docker("logs", RUN, check=False).stdout)
            if docker("exec", RUN, "/usr/sbin/nginx", "-t", check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Nginx did not become ready")

        info = json.loads(docker("inspect", RUN).stdout)[0]
        check(info["Config"]["User"] == "65532:65532", "runtime UID/GID is non-root 65532:65532")
        check(info["HostConfig"]["ReadonlyRootfs"] and all(not mount["RW"] for mount in info["Mounts"] if mount["Type"] == "bind"), "root filesystem and all bind mounts are read-only")
        status = docker("run", "--rm", "--pid", f"container:{RUN}", "--cap-drop=ALL", TOOLS,
                        "python3", "-c", "from pathlib import Path; print(Path('/proc/1/status').read_text())").stdout
        check("Uid:\t65532\t65532\t65532\t65532" in status, "PID 1 actually runs as non-root")
        check("CapEff:\t0000000000000000" in status, "process has no effective capabilities")
        for executable in ("/bin/sh", "/bin/bash", "/bin/busybox", "/usr/bin/apt", "/usr/bin/dpkg", "/sbin/apk"):
            result = docker("exec", RUN, executable, "--version", check=False)
            error = (result.stdout + result.stderr).lower()
            check(result.returncode != 0 and ("no such file" in error or "not found" in error), f"runtime has no {executable}")
        check("Nginx distroless is running" in request("http://127.0.0.1:8080/"), "static HTML served over HTTP")
        check("verified-private-ca-upstream" in request("http://127.0.0.1:8080/", "-H", "Host: proxy.example"), "reverse proxy resolves extra_hosts and verifies private-CA upstream")
        check("Nginx distroless is running" in request("https://localhost:8443/", "--cacert", "/certs/ca-bundle.pem", "--http1.1"), "HTTPS certificate verified")
        check(request("https://localhost:8443/", "--cacert", "/certs/ca-bundle.pem", "--http2", "-o", "/dev/null", "-w", "%{http_version}") == "2", "HTTP/2 negotiated (no HTTP/1.1 fallback)")
        print(helper("python3", "/tests/http3_client.py", namespace=RUN).strip(), flush=True)
        echo = helper("python3", "-c", "import socket; s=socket.create_connection(('127.0.0.1',9000),5); s.sendall(b'stream-echo'); print(s.recv(100).decode())", namespace=RUN)
        check(echo.strip() == "stream-echo", "stream TCP proxy exchanges real data")
        build_info = copy_file(RUN, "/usr/share/nginx/build-info.txt")
        (REPORTS / "build-info.txt").write_text(build_info)
        check("Nginx version: 1.30.7" in build_info, "build metadata records source version, checksum and dependencies")
        check(copy_file(RUN, "/etc/hosts").find("backend.example") >= 0, "extra_hosts entry exists inside Nginx container")

        # Negative trust test: replacing the mounted CA must reject the upstream.
        original_ca = (WORK / "certs/ca-bundle.pem").read_bytes()
        openssl("req", "-x509", "-newkey", "rsa:2048", "-noenc", "-days", "1", "-subj", "/CN=Untrusted-CA", "-keyout", "/certs/wrong.key", "-out", "/certs/ca-bundle.pem")
        docker("exec", RUN, "/usr/sbin/nginx", "-s", "reload")
        for _ in range(30):
            code = helper("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", "-H", "Host: proxy.example", "http://127.0.0.1:8080/", namespace=RUN)
            if code == "502":
                break
            time.sleep(0.1)
        check(code == "502", "untrusted upstream certificate is rejected")
        (WORK / "certs/ca-bundle.pem").write_bytes(original_ca)
        (WORK / "conf/conf.d/reload.conf").write_text("server { listen 8081; location / { return 200 'reload-success'; } }\n")
        docker("exec", RUN, "/usr/sbin/nginx", "-t")
        docker("exec", RUN, "/usr/sbin/nginx", "-s", "reload")
        for _ in range(30):
            result = docker("run", "--rm", "--network", f"container:{RUN}", TOOLS, "curl", "-fsS", "--max-time", "2", "http://127.0.0.1:8081/", check=False)
            if result.stdout == "reload-success":
                break
            time.sleep(0.1)
        check(result.stdout == "reload-success", "nginx -s reload applies mounted config without restart")
        check("verified-private-ca-upstream" in request("http://127.0.0.1:8080/", "-H", "Host: proxy.example"), "restoring mounted CA works after reload without rebuild")
        logs = docker("logs", RUN).stdout
        (REPORTS / "nginx-test.log").write_text(logs)
        access_lines = [json.loads(line) for line in logs.splitlines() if line.startswith("{ ")]
        check(bool(access_lines), "stdout contains parseable JSON access logs")
        check(all("body" not in item["message"]["nginx"]["bytes"] for item in access_lines), "default access logs exclude request body")
        check(any(item["message"]["nginx"]["time"]["iso8601"].endswith("+07:00") for item in access_lines), "Asia/Bangkok timezone is effective")
        check(json.loads(docker("inspect", RUN).stdout)[0]["State"]["Running"], "Nginx remains running after all protocol tests")
    finally:
        for name in reversed(CONTAINERS):
            if name == RUN:
                log = docker("logs", name, check=False)
                (REPORTS / "nginx-test.log").write_text(log.stdout + log.stderr)
            docker("stop", "--time", "5", name, check=False)
        docker("network", "rm", RUN, check=False)
        docker("network", "rm", RUN + "_default", check=False)
        # Remove only disposable private key fixtures; keep configs for diagnosis.
        for path in (WORK / "certs").glob("*"):
            if path.is_file():
                path.unlink()


if __name__ == "__main__":
    main()
