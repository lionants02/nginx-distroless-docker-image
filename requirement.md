# Nginx docker distroless image requirement
สร้าง Dockerfile สำหรับ build Nginx แบบ distroless ที่ไม่มี OS และ `non-root` ไม่มี shell/package manager สำหรับใช้งานในระบบ Linux x64 และให้สแกนผลด้วย ด้วย Trivy และ Hadolint

## ข้อกำหนดเพิ่มเติม
- Nginx ให้ใช้เป็นลักษระ docker compose
  - ไฟล์ config nginx ต่างๆ ให้ mount แบบอ่านอย่างเดียว ไว้ที่โฟเดอร์ `./nginx-conf`
    - การใช้งานจะเป็นแบบ git clone ไปใช้ ไม่มี push กลับ
  - ไฟล์ static html ให้ mount แบบอ่านอย่างเดียว ไว้ที่โฟเดอร์ `./static-html`
  - ให้ mount ไฟล์ใน docker nginx ซักที่นึงสำหรับ ssl key แบบอ่านอย่างเดียว ไว้ที่โฟเดอร์ `./ssl`
  - รองรับการใช้งานคำสั่ง `nginx -s reload`
  - log ให้ส่งออกทาง stdout ได้เลย ฉันมี Grafana Alloy ดูด log จาก docker อยู่แล้ว
    - ให้เขียนตัวอย่างวิธีการกำหนด nginx log ให้ส่งออกทาง stdout ไว้ใน README.md ด้วย
  - ให้รองรับการใช้งาน การกำหนด extra_hosts ใน docker compose ด้วย โดยเบื้องต้นให้ใส่ mockup ไว้ 1 รายการ อะไรก็ได้ก่อน
  - log รูปแบบเริ่มต้นให้เป็น `nginx-log-json-no-post-body`
- ใช้ Github action เมื่อมีการ push เข้ามาให้ทำงาน และเก็บ docker image ที่ build แล้วไว้ที่ ghcr.io
  - เขียนวิธีการ pull image จาก ghcr.io ไว้ใน README.md ด้วย
  - เมื่อ push Git tag ให้ใช้ docker tag version เป็นชื่อ tag นั้นโดยตรง และให้อัปเดต `latest` เฉพาะการ push branch `main`
 - ชื่อ branch ที่มี `/` ให้ docker tag version แปลงเป็น `-` เช่น `feature/test` → `feature-test`
- การ scan
  - ตรวจ Dockerfile ทั้งไฟล์ด้วย Trivy/Hadolint และตรวจ final runtime image ด้วย Trivy
  - เก็บผลการ scan ไว้ใน github artifact แล้วบอกใน README.md ว่าเก็บผลไว้ที่ไหน
- ถ้าเป็นไปได้ เขียน AGENTS.md สำหรับ AI ที่จะมาปรับปรุงระบบในอนาคตด้วย
- ให้รันทดสอบ distroless ในเครื่องให้เรียบร้อยก่อน
- เขียน README.md ด้วย
- ตัวแปรดาวน์โหลด binary ควรมี checksum ควบคู่กัน เพื่อตรวจสอบไฟล์ก่อนนำเข้า image
- กำหนดการทดสอบให้ครอบคลุมพฤติกรรมจริง — static HTML, reverse proxy, HTTPS, HTTP/2, HTTP/3, stream, extra_hosts, reload หลังแก้ config และการรัน non-root พร้อม mount อ่านอย่างเดียว
- ทำอะไรไปบ้างให้เขียนไว้ใน TASK.md
- ให้ใส่โครงสร้าง Project ไว้ใน README.md ด้วย


### ตอบคำถาม
- ผลการ scan ให้เก็บไว้ 1 เดือน
- Nginx ให้คอมไพล์ใหม่ 
  - โดยเบื้องต้น source code ให้ใช้เป็น `https://github.com/nginx/nginx/releases/download/release-1.30.7/nginx-1.30.7.tar.gz` checksum `sha256:2565b5c837050e958f70fb0f73c48e2bca4542ad349fd356f46fb0c72610bc6e`
- เฉพาะ branch main ให้เป็น docker tag version เป็น `latest` ส่วน branch อื่นให้ docker tag version เป็นชื่อ branch ตัวเองแทน
- หากผลสแกน พบ HIGH/CRITICAL หรือ Hadolint พบ error ไม่ต้อง push docker
  - ไม่ว่าผล scan จะออกมาแบบไหนต้อง อัปโหลดรายงาน และให้ workflow แสดงผลว่า ผ่านหรือไม่ผ่าน
- ตอบคำถาม ให้ใช้แบบ distroless ที่ยังพอกำหนด ca-certificates, timezone ได้
- Nginx ต้องการ โมดูลพื้นฐาน static HTML, HTTP reverse proxy, HTTPS, HTTP/2, HTTP/3, stream
- กรณีชื่อ tag ชนกันให้เขียนทับได้ แต่ชื่อผิดรูปแบบ หรือ Git tag/branch อื่นพยายามใช้ latest นอกจาก main ให้ workflow แสดง error และหยุด ส่วน scanner ทำงานไม่สำเร็จให้บล็อกการ push พร้อมเก็บบันทึกข้อผิดพลาดเช่นเดียวกัน
  - ฉันไม่ได้ใช้การ deploy จาก github ci อยู่แล้ว ใช้ github ci เฉพาะการ scan และ build image
- หลัง clone ให้เปิดใช้งาน HTTP ทันทีตาม config ในส่วน HTTPS/HTTP/3 ให้เตรียมเป็นตัวอย่างไว้ ยังไม่เปิดใช้งาน
  - เบื้องต้นให้ Publishing ports
    - HTTP 80:8080
    - HTTPS 443:8443
    - HTTP/3 443:8443/udp
- Timezone เบื้องต้นให้เป็น `Asia/Bangkok`
- ในส่วน CA เพิ่มเติม สามารถใช้วิธี mount โฟเดอร์ `./ca` โดยที่ไม่ต้อง rebuild image