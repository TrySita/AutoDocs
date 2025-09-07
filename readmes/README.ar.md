<p align="center">
  <img src="../webview/apps/webapp/public/favicon.svg" alt="OpenDocs by Sita" width="96" height="96" />
</p>

# ‎AutoDocs من Sita‎

أتمتة توثيق أي مستودع: نقوم بزيارة الشفرة، تحليل ‎AST‎، وبناء مخطط التبعيات ثم السير عليه لإنتاج توثيق دقيق وعالي الفائدة. خادم ‎MCP‎ المدمج يتيح لوكلاء البرمجة البحث العميق عبر ‎HTTP‎.

نقاط الوصول الرئيسية

- واجهة الويب: http://localhost:3000
- ‏API (FastAPI): http://localhost:8000
- خادم MCP: http://localhost:3000/api/mcp

## ما يقدمه هذا المستودع

- تحليل المستودع باستخدام ‎tree‑sitter‎ لبناء ‎AST‎.
- إنشاء مخطط تبعيات (ملفات، تعريفات، استدعاءات، واردات) وكشف الدورات.
- السير على المخطط لإنتاج توثيق وملخصات واعية بالتبعيات.
- ‏FastAPI للابتلاع/البحث وواجهة ‎Next.js‎ للاستكشاف.
- خادم ‎MCP‎ على ‎`/api/mcp`‎ للاستعلامات العميقة.

---

## تحديث التوثيق (مهم)

حالياً، لتحديث التوثيق بعد تغييرات الشفرة: احذف المستودع ثم أعد ابتلاعه (تدفق مؤقت):

- عبر الواجهة: احذف المستودع من مساحة العمل ثم أضفه مجدداً (سيبدأ الابتلاع تلقائياً).
- عبر الـ API: احذف البيانات المحلية (قاعدة البيانات + النسخة المستنسخة) ثم أعد جدولة مهمة ابتلاع:

```bash
# حذف بيانات التحليل المحلية (قاعدة البيانات + الاستنساخ)
curl -X POST http://localhost:8000/repo/delete \
  -H 'Content-Type: application/json' \
  -d '{"repo_slug":"my-repo"}'

# جدولة ابتلاع جديد
curl -X POST http://localhost:8000/ingest/github \
  -H 'Content-Type: application/json' \
  -d '{"github_url":"https://github.com/org/repo","repo_slug":"my-repo","force_full":false}'
```

نعمل على إضافة زر “إعادة الابتلاع” بنقرة واحدة، ثم ابتلاعاً دورياً تلقائياً. قريباً جداً.

## البدء السريع

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

ترحيل قاعدة البيانات (مرة محلياً):

```bash
cd webview && pnpm install
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## خادم MCP

- العنوان: `http://localhost:3000/api/mcp`
- أضف ترويسة `x-repo-id`.

## بنية المشروع

- `ingestion/` — ‏FastAPI، تحليل AST، مخطط، تضمينات وبحث.
- `webview/` — تطبيق ‎Next.js‎ وحزم TS مشتركة.
- `docker-compose.yml` — ‏Postgres، ‏API، الويب محلياً.

## الترخيص

‏MIT. في حال التعارض، يُرجى الرجوع إلى ‎../README.md‎ (بالإنجليزية).

## المشكلات المعروفة

- يجب أن يكون الكود في جذر المستودع وليس داخل مجلد متداخل.
- ندعم حالياً TS وJS وPython فقط؛ سنوسع الدعم إلى Java وKotlin ثم إلى Go وRust.
- لا ندعم المستودعات متعددة اللغات حالياً، لكننا نعمل على ذلك أيضاً.
