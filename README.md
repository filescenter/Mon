# Mon

مودلات أودو 19 الخاصة بمنصة المنبر. كل مجلد في الجذر مودل مستقل:

- [`ib4tech_minbar`](ib4tech_minbar/README.md): الدليل والمجالس والمكتبة وتطبيق الموبايل `/app`.

## التشغيل على الحاسبة بالدوكر

المطلوب: [Docker Desktop](https://www.docker.com/products/docker-desktop/) و Git.

أول مرة:

```bash
git clone https://github.com/filescenter/Mon.git
```

```bash
cd Mon
```

```bash
git checkout claude/clever-babbage-2i1ive
```

```bash
docker compose up -d
```

```bash
docker compose run --rm odoo odoo -d minbar -i ib4tech_minbar --with-demo --stop-after-init
```

بعدها:

- التطبيق: <http://localhost:8069/app>
- الإدارة: <http://localhost:8069/odoo> (المستخدم `admin` وكلمة المرور `admin`)

## العمل اليومي

| المطلوب | الأمر |
| --- | --- |
| جلب آخر تعديلات من GitHub | `git pull` |
| تشغيل / إيقاف | `docker compose up -d` / `docker compose stop` |
| متابعة السجل | `docker compose logs -f odoo` |
| تحديث المودل بعد تغيير موديل أو صلاحيات أو بيانات | `docker compose run --rm odoo odoo -d minbar -u ib4tech_minbar --stop-after-init` |
| تشغيل الاختبارات | `docker compose run --rm odoo odoo -d minbar -u ib4tech_minbar --test-tags /ib4tech_minbar --stop-after-init` |
| إعادة تشغيل أودو | `docker compose restart odoo` |
| مسح القاعدة والبدء من جديد | `docker compose down -v` |

تعديل ملفات القوالب والواجهة (`views/*.xml` و `static/`) يظهر بتحديث الصفحة.
تعديل ملفات بايثون يعيد تشغيل أودو تلقائياً، وإذا لم يحدث ذلك استخدم أمر إعادة التشغيل.

رفع التعديلات إلى GitHub:

```bash
git add -A
```

```bash
git commit -m "[IMP] ib4tech_minbar: وصف التعديل"
```

```bash
git push
```
