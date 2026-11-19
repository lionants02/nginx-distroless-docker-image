# Nginx distroless Docker image

Nginx 1.30.7 คอมไพล์จาก source สำหรับ `linux/amd64` บน Debian 13 distroless ทำงานด้วย UID/GID `65532:65532` ไม่มี shell, package manager หรือ compiler ใน final image รองรับ static HTML, HTTP reverse proxy, HTTPS, HTTP/2, HTTP/3 และ stream (TCP/UDP)

Distroless ยังมี Linux userspace libraries และข้อมูลระบบที่จำเป็น เช่น glibc, public CA และ timezone data โดยใช้ kernel ของ host ไม่ใช่ระบบที่ปราศจากส่วนประกอบของ OS ทั้งหมด

## เริ่มใช้งาน

ต้องมี Docker Engine และ Docker Compose บน Linux x64 หรือ Docker ภายใน WSL Ubuntu คำสั่งต่อไปนี้ใช้ Bash และรันจาก root ของ repository

```bash
git clone https://github.com/lionants02/nginx-distroless-docker-image.git
cd nginx-distroless-docker-image
docker compose pull
docker compose up -d
curl http://localhost/
```

ต้องมี image ที่ workflow publish สำเร็จก่อน หากยังไม่มี ให้ build ในเครื่องตามหัวข้อถัดไป ค่าเริ่มต้นเปิดเฉพาะ HTTP `80:8080` ไม่มีการเปิด HTTPS หรือ HTTP/3 และใช้ timezone `Asia/Bangkok`

```bash
# Pull โดยตรง หรือเปลี่ยนเป็น tag ของ branch/release
docker pull ghcr.io/lionants02/nginx-distroless-docker-image:latest
NGINX_IMAGE=ghcr.io/lionants02/nginx-distroless-docker-image:v1.0.0 docker compose up -d
```

หาก GHCR package เป็น private ให้ login ด้วยบัญชีที่เข้าถึง package ได้และ PAT ที่มี `read:packages` ก่อน pull:

```bash
read -rsp 'GHCR token: ' GHCR_TOKEN; printf '\n'
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
unset GHCR_TOKEN
docker compose pull
```

เจ้าของ repository สามารถเปลี่ยน package visibility เป็น public ใน GitHub Packages เพื่อให้ pull โดยไม่ต้อง login ได้ Workflow ใช้ `GITHUB_TOKEN` พร้อม `packages: write` โดยไม่ต้องเพิ่ม PAT สำหรับ publish; หาก package มีอยู่ก่อน ต้องให้ repository นี้มีสิทธิ์เขียน package ด้วย

## Build และทดสอบในเครื่อง

```bash
mkdir -p reports
docker build --platform linux/amd64 --progress plain -t nginx-distroless:local .
NGINX_IMAGE=nginx-distroless:local docker compose up -d --pull never
docker compose exec -T nginx /usr/sbin/nginx -V

# Helpers อยู่แยกจาก application image
docker build -f tests/Dockerfile -t nginx-distroless-test-tools:local .
python3 tests/runtime.py nginx-distroless:local
python3 -m unittest discover -s tests -p 'test_ci.py' -v
bash ci/scan.sh nginx-distroless:local
```

Integration tests สร้าง network, containers และ certificate ชั่วคราวของตัวเอง ทดสอบ HTTP, private-CA HTTPS upstream, HTTP/2, HTTP/3 จริงโดยไม่มี protocol fallback, TCP stream, extra_hosts, reload, JSON stdout, timezone, non-root, read-only mounts และการไม่มี shell/package manager เมื่อจบจะหยุดเฉพาะ test containers และลบ network/keys ชั่วคราวของการทดสอบนั้น โดยไม่ยุ่งกับ Compose service ที่ผู้ใช้เปิดไว้

สำหรับ Windows ให้เรียก Docker ภายใน Ubuntu เช่น:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/o/github/nginx-distroless-docker-image && docker compose config --quiet'
```

## Mounts และสิทธิ์ไฟล์

| Host | Container | การใช้งาน |
| --- | --- | --- |
| `./nginx-conf` | `/etc/nginx` | config แบบอ่านอย่างเดียว |
| `./static-html` | `/usr/share/nginx/html` | static files แบบอ่านอย่างเดียว |
| `./ssl` | `/etc/nginx/ssl` | server certificate/key แบบอ่านอย่างเดียว |
| `./ca` | `/etc/nginx/ca` | CA สำหรับ upstream แบบอ่านอย่างเดียว |
| tmpfs | `/tmp` | PID และ temporary files; ค่าเริ่มต้น 64 MiB |

Root filesystem เป็น read-only, drop capabilities ทั้งหมด และเปิด `no-new-privileges` ให้ UID/GID 65532 อ่าน config, HTML และ certificates ได้ และ traverse ทุก directory ได้ เช่น directory `0755`, public files `0644`; private key ใช้ group `65532` และ permission `0640` บน Linux ไม่ต้องทำ key ให้ world-readable หากรับ upload หรือใช้ proxy buffering ขนาดใหญ่ ให้ปรับขนาด tmpfs ตามงาน

`extra_hosts` มี mock `mock-upstream.example:192.0.2.10` ซึ่งเป็นตัวอย่างเท่านั้น เปลี่ยน hostname/IP ให้ตรง upstream จริงก่อนใช้ ไม่มีการเชื่อมต่อ mock นี้ใน default config

เก็บ directory ว่าง `nginx-conf/ssl` และ `nginx-conf/ca` ไว้เป็น mountpoints เพราะ config directory ถูก mount แบบ read-only ให้วาง certificate/CA จริงใน `./ssl` และ `./ca` ที่ root ของโครงการ

## แก้ config และ reload

แก้ไฟล์บน host แล้วตรวจ config ก่อน reload โดยเรียก binary โดยตรง:

```bash
docker compose exec -T nginx /usr/sbin/nginx -t
docker compose exec -T nginx /usr/sbin/nginx -s reload
```

PID อยู่ที่ `/tmp/nginx.pid` จึงไม่ต้องเขียนเข้า directory config หาก config ใหม่ผิด Nginx จะเก็บ workers/config เดิมไว้ คำสั่งส่ง signal สำเร็จไม่ได้ยืนยันว่า master รับ config ใหม่สำเร็จเสมอ ให้ตรวจ log และพฤติกรรมหลัง reload ด้วย

ไม่มี shell สำหรับ `docker compose exec nginx sh` และไม่มี script ที่แทน environment variables ใน config อัตโนมัติ ปรับ config ที่ mount จาก host โดยตรงได้

Healthcheck ใช้ `nginx -t` เพื่อตรวจ syntax/การอ่านไฟล์ เป็นการตรวจ config เท่านั้น การตรวจ HTTP จากภายนอกควรทำผ่าน monitoring ของระบบ

## stdout logs และ Grafana Alloy

ค่าเริ่มต้นอยู่ใน `nginx-conf/nginx.conf`:

```nginx
error_log /dev/stdout notice;

http {
    include /etc/nginx/nginx-log-json-no-post-body.conf;
    access_log /dev/stdout nginx-log-json-no-post-body;
    # ...
}
```

Access log เป็น JSON แบบ `nginx-log-json-no-post-body` ส่วน error log เป็นข้อความปกติ ทั้งสองส่ง stdout ให้ Docker/Alloy เก็บได้ จึงควรให้ parser รองรับทั้งสองรูปแบบ ดู log ได้ด้วย `docker compose logs -f nginx` ไม่มี log files ที่ต้อง rotate ใน container

ไฟล์รูปแบบที่มี request body ยังเก็บไว้เพื่อเลือกใช้ แต่ไม่ได้เปิดเป็นค่าเริ่มต้น

## HTTPS และ HTTP/2 (เลือกเปิด)

วาง certificate chain ที่ `ssl/fullchain.pem` และ private key ที่ `ssl/privkey.pem` โดยจัด permission ให้ non-root อ่านได้ แล้ว:

```bash
cp examples/https.conf.example nginx-conf/conf.d/https.local.conf
docker compose -f compose.yml -f examples/compose.tls.yml config --quiet
docker compose -f compose.yml -f examples/compose.tls.yml up -d
```

ตัวอย่างเปิด HTTPS/HTTP/2 ที่ container 8443 และ publish TCP `443:8443` หาก container ทำงานอยู่แล้วและเปลี่ยนเฉพาะ config ให้ตรวจและ reload ด้วยคำสั่งข้างต้นหลังปรับ port mapping แล้ว การเปลี่ยน Compose ports ต้อง recreate container

## HTTP/3 (ตัวอย่างที่ยังไม่เปิด)

ใช้ `examples/http3.conf.example` แทน HTTPS example เพื่อไม่ให้ประกาศ listener ซ้ำ:

```bash
# หากเปิด HTTPS example อยู่ ให้เปลี่ยนนามสกุลเพื่อหยุด include ก่อน
# mv nginx-conf/conf.d/https.local.conf nginx-conf/conf.d/https.local.conf.disabled
cp examples/http3.conf.example nginx-conf/conf.d/http3.local.conf
```

เปิดบรรทัด `443:8443/udp` ใน `examples/compose.tls.yml` เพิ่มจาก TCP แล้วใช้ Compose override เดิม Firewall/load balancer ต้องส่ง UDP 443 ถึง container ด้วย `Alt-Svc` ในตัวอย่างประกาศ public port 443

HTTP/3 ของ Nginx ยังระบุเป็น experimental; ชุดทดสอบใช้ QUIC client ของ aioquic ตรวจ response จริง ไม่ใช้เพียง `nginx -V` เป็นหลักฐาน [เอกสาร Nginx HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)

## Reverse proxy, private CA และ stream

ตัวอย่าง reverse proxy อยู่ที่ `examples/reverse-proxy.conf.example` และ stream อยู่ที่ `examples/stream.conf.example` คัดลอกไป `nginx-conf/conf.d/*.local.conf` และ `nginx-conf/stream.d/*.local.conf` ตามลำดับ เปลี่ยน hostname/port และ publish port ของ stream เพิ่มใน Compose ตามต้องการ

สำหรับ HTTPS upstream ที่ใช้ private CA ให้วาง PEM bundle ที่ `ca/ca-bundle.pem` แล้วกำหนดใน context ของ upstream นั้น:

```nginx
proxy_ssl_trusted_certificate /etc/nginx/ca/ca-bundle.pem;
proxy_ssl_verify on;
proxy_ssl_server_name on;
# หากชื่อใน proxy_pass ต่างจากชื่อใน certificate ให้กำหนด proxy_ssl_name ด้วย
```

Mount CA อย่างเดียวไม่ทำให้ Nginx เชื่อถือโดยอัตโนมัติ ต้องอ้างอิงไฟล์และเปิด verification หากต้องเชื่อถือทั้ง public/private CA ให้เตรียม PEM bundle รวมบน host หรือใช้ `/etc/ssl/certs/ca-certificates.crt` สำหรับ public CA เท่านั้น สำหรับ certificate chain หลายชั้นให้กำหนด `proxy_ssl_verify_depth` ให้เหมาะสม เปลี่ยน CA โดยเขียนไฟล์บน host แล้วตรวจ config และ reload ได้ ไม่ต้อง rebuild image [เอกสาร upstream TLS](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_ssl_trusted_certificate)

วิธีนี้กำหนด trust ให้ Nginx ตาม config ไม่ได้แก้ system trust store ให้ทุกโปรแกรมใน container ส่วน `./ssl` ใช้เก็บ certificate/key ที่ Nginx แสดงต่อ client เป็นคนละหน้าที่กับ upstream CA

## GitHub Actions และกติกาการ publish

Workflow `.github/workflows/build.yml` ทำงานเมื่อ push ทุก branch/ทุก Git tag และเรียกด้วยมือได้ โดย build `linux/amd64` ครั้งเดียว ตรวจ Dockerfile ทั้งไฟล์ด้วย Hadolint/Trivy ตรวจ final runtime image ด้วย Trivy และทดสอบ runtime ก่อน tag/push image เดิมไป GHCR ไม่มีขั้น deploy

| Git ref | Docker tag |
| --- | --- |
| branch `main` | `latest` เท่านั้น |
| branch `feature/test` | `feature-test` |
| Git tag `v1.0.0` | `v1.0.0` ตามตัวอักษรเดิม |

ชื่อ Git tag ไม่ถูก sanitize; branch แปลงเฉพาะ `/` เป็น `-` ชื่อผิดรูปแบบ/ยาวเกิน 128 ตัวอักษร หรือ Git tag/branch อื่นใช้ `latest` จะ fail ชื่อชนกันเขียนทับได้ ชื่อ image owner/repository ใช้ตัวพิมพ์เล็ก

บล็อก push เมื่อ Trivy พบ HIGH/CRITICAL ทั้ง vulnerabilities และ misconfigurations รวมถึงรายการที่ยังไม่มี fix, Hadolint พบ error, scanner/report ผิดพลาด, build หรือ runtime test ไม่ผ่าน ไม่มี `ignore-unfixed` และไม่มีการซ่อนผลด้วย `continue-on-error`

ทุก scanner พยายามทำงานให้ครบแม้อีกตัวล้มเหลว จากนั้นรวมผลเป็น gate และอัปโหลดรายงานด้วย `if: always()` พร้อม workflow summary หาก build ล้มเหลวจะยังเก็บ build log และพยายามรัน scanner เพื่อบันทึกสิ่งที่ตรวจได้; การที่ runner ถูกยุติ/ระบบ GitHub ขัดข้องอาจทำให้อัปโหลดไม่ได้

## รายงานสแกนและขอบเขต Trivy

เปิด **GitHub → Actions → Build, scan and publish → เลือก run → Artifacts → `security-reports-<run_id>`** เก็บ 30 วัน (1 เดือนตามข้อตกลง) ผลสรุป PASS/FAIL แสดงในหน้า Summary ด้วย การรันในเครื่องเก็บที่ `reports/` ซึ่งไม่เข้า Git

รายงานหลัก: `hadolint.json`, `trivy-config.json`, `trivy-image.json`, `sbom.cdx.json`, `scan-summary.json`, `scan-summary.md` และ `.log`/`.exit` ของแต่ละเครื่องมือ รวมถึง build/test logs และ `build-info.txt` เมื่อทดสอบถึงขั้นนั้น

- **Trivy config** ตรวจ misconfiguration ของ Dockerfile ทั้งไฟล์ ไม่ใช่การวิเคราะห์ช่องโหว่ใน C source code
- **Trivy image** ตรวจช่องโหว่ของ packages ที่ระบุได้จาก final runtime image และฐานข้อมูลขณะสแกน ไม่รวม compiler/build tools ที่อยู่เฉพาะ builder stage
- **Hadolint** ตรวจ syntax และ best practices ของ Dockerfile ไม่ตรวจ CVE ของ Nginx
- **SBOM** เป็นรายการส่วนประกอบที่ scanner ตรวจพบ ไม่ใช่หลักฐานว่าตรวจครบทุก component หรือปลอดช่องโหว่

Nginx ถูกคอมไพล์เองและไม่ได้ติดตั้งผ่าน Debian package manager จึงอาจไม่ถูก Trivy ระบุเป็น package และตรวจ CVE ของตัว Nginx ได้ แม้สแกน image แล้วไม่มี HIGH/CRITICAL ก็ไม่ยืนยันว่า Nginx ไม่มีช่องโหว่ การตรวจ C/C++ ของ Trivy มีข้อจำกัดตามรูปแบบ metadata ที่รองรับ [Trivy language coverage](https://trivy.dev/docs/latest/coverage/language/), [Trivy misconfiguration scanner](https://trivy.dev/docs/latest/scanner/misconfiguration/)

OpenSSL, PCRE2, zlib, libcrypt และ dependencies ต่อเนื่อง เช่น libzstd ใช้ shared libraries จาก Debian โดยหา dependencies จาก `ldd` ขณะ build และคัดลอก metadata เฉพาะ packages ที่อยู่ใน runtime ไป `/var/lib/dpkg/status.d/` เพื่อช่วยตรวจเวอร์ชันได้ โดยไม่ยกฐานข้อมูล compiler/build dependencies ทั้งชุดมาอ้างว่าอยู่ใน final image ส่วน glibc/loader ใช้จาก distroless base

เก็บ source URL, SHA256, configure flags และเวอร์ชัน runtime dependencies ไว้ใน image ที่ `/usr/share/nginx/build-info.txt` และใน artifact จาก integration test ใช้ข้อมูลนี้ตรวจ [Nginx security advisories](https://nginx.org/en/security_advisories.html) และ advisory ของ dependencies ควบคู่ การตรวจ advisory ของ Nginx เองยังเป็นงานทบทวนโดยผู้ดูแล ไม่ใช่ automated gate เพิ่มเติมใน workflow นี้

## การอัปเดต dependencies

เปลี่ยน `NGINX_VERSION`, `NGINX_URL` และ `NGINX_SHA256` คู่กันจาก release ที่ตรวจสอบได้ build จะตรวจ SHA256 ก่อนแตก archive และคอมไพล์ Base images และ scanner images pin ด้วย digest; GitHub Actions pin ด้วย commit SHA

Debian packages ใน builder ดึงจาก signed repositories ณ เวลา build เพื่อรับ security updates จึงไม่ได้รับประกัน byte-for-byte reproducibility ระหว่างวัน รายการเวอร์ชันที่ใช้จริงอยู่ใน build-info ควรอัปเดต base digest และทดสอบใหม่เป็นระยะ การ pin digest ไม่ได้รับ security update อัตโนมัติ

## โครงสร้างโครงการ

```text
.
├── Dockerfile                  # build Nginx + distroless runtime
├── compose.yml                 # HTTP default, mounts, non-root restrictions
├── .github/workflows/build.yml # build → scan/test → GHCR + reports
├── ci/                         # pinned scanners, tag rules, fail-closed scan gate
├── scripts/assemble-runtime.sh # copy binary/shared libs/package metadata
├── nginx-conf/
│   ├── nginx.conf              # stdout logs, /tmp runtime paths
│   ├── conf.d/default.conf     # HTTP server
│   ├── stream.d/               # optional stream configs
│   └── nginx-log-json-*.conf   # existing JSON log formats
├── static-html/                # mounted static content
├── ssl/                        # local cert/key; Git ignores contents
├── ca/                         # local CA bundles; Git ignores contents
├── examples/                   # HTTPS, HTTP/3, proxy, stream, Compose override
├── tests/                      # protocol integration + CI gate tests
├── AGENTS.md                   # maintenance instructions
├── TASK.md                     # implementation/test record
└── requirement.md              # agreed requirements
```
