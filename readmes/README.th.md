<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# AutoDocs โดย Sita

ทำเอกสารอัตโนมัติสำหรับทุกรีโพได้อย่างง่ายดาย: เราจะไล่ผ่านโค้ดของคุณ แยกวิเคราะห์ AST สร้างกราฟการพึ่งพา และเดินตามกราฟนั้นเพื่อสร้างเอกสารที่ถูกต้องและมีประโยชน์ เซิร์ฟเวอร์ MCP ในตัวช่วยให้ค้นหาเชิงลึกผ่าน HTTP ได้

จุดปลายหลัก (Endpoints)

- เว็บ UI: http://localhost:3000
- API (FastAPI): http://localhost:8000
- เซิร์ฟเวอร์ MCP: http://localhost:3000/api/mcp

## สิ่งที่รีโพนี้ทำ

- ใช้ tree‑sitter เพื่อสร้าง AST
- สร้างกราฟการพึ่งพา (ไฟล์ คำจำกัดความ การเรียกใช้ การนำเข้า) และตรวจจับวงวน
- เดินตามกราฟเพื่อสร้างเอกสารและสรุปที่ตระหนักถึงการพึ่งพา
- ให้บริการ FastAPI สำหรับ ingestion/การค้นหา และ Next.js Web UI สำหรับการสำรวจ
- ให้บริการ MCP ที่ `/api/mcp` สำหรับการค้นหาเชิงลึก

---

## การอัปเดตเอกสาร (สำคัญ)

ขณะนี้ หากต้องการรีเฟรชเอกสารหลังแก้ไขโค้ด ให้ลบรีโพและทำ ingestion ใหม่ (เวิร์กโฟลว์ชั่วคราว):

- ใน UI: ลบรีโพออกจาก Workspace แล้วเพิ่มกลับอีกครั้ง (ingestion จะเริ่มอัตโนมัติ)
- ผ่าน API: ลบข้อมูลในเครื่อง (DB + โคลน) แล้วคิวงาน ingestion ใหม่

```bash
# ลบข้อมูลวิเคราะห์ในเครื่อง (DB + clone)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# คิวงาน ingestion ใหม่
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

เรากำลังเพิ่มปุ่ม “Reingest” แบบคลิกเดียวใน UI และตามด้วย ingestion อัตโนมัติเป็นระยะ เร็วๆ นี้

## เริ่มต้นอย่างรวดเร็ว

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

การย้ายฐานข้อมูล (ทำครั้งเดียวในเครื่อง):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## เซิร์ฟเวอร์ MCP

- URL: `http://localhost:3000/api/mcp`
- เพิ่มส่วนหัว `x-repo-id`

## โครงสร้างโปรเจกต์

- `ingestion/` — FastAPI, การแยกวิเคราะห์ AST, กราฟ, embeddings, การค้นหา
- `webview/` — แอป Next.js และแพ็กเกจ TS ที่ใช้ร่วมกัน
- `docker-compose.yml` — Postgres, API และ Web ภายในเครื่อง

## ลิขสิทธิ์

MIT หากมีข้อความไม่ตรงกัน โปรดดู ../README.md (ภาษาอังกฤษ)

## ปัญหาที่ทราบ

- โค้ดของคุณต้องอยู่ที่ระดับรากของรีโพ ไม่ใช่อยู่ในโฟลเดอร์ซ้อน
- ปัจจุบันรองรับเฉพาะ TS, JS และ Python; จะขยายไปยัง Java และ Kotlin จากนั้นเป็น Go และ Rust
- ยังไม่รองรับหลายภาษา (หลายภาษาในรีโพเดียวกัน) แต่กำลังดำเนินการอยู่
