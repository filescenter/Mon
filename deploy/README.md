# تشغيل تطبيق الصدّيقة على خادم (VPS)

ثلاث حاويات: أودو 19 Community، PostgreSQL، و Caddy الذي يجلب شهادة HTTPS ويجددها تلقائياً.

> إعدادات أودو في هذا المجلد مجرَّبة محلياً خلف ترويسات وسيط (HTTPS والعاملان وحجب مدير
> القواعد). ملفا `docker-compose.yml` و `Caddyfile` لم يُشغَّلا من بيئة التطوير لعدم توفر
> Docker فيها، فأول تشغيل على الخادم هو الفحص الحقيقي لهما.

## المطلوب

| المطلوب | ملاحظة |
| --- | --- |
| خادم Ubuntu 24.04 | 2 vCPU و 4 GB RAM كحد أدنى للفترة التجريبية |
| دومين | سجل A يشير إلى عنوان الخادم قبل التشغيل |
| المنفذان 80 و 443 مفتوحان | لشهادة HTTPS |

## أول تشغيل

1. تثبيت Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

2. جلب الكود:

```bash
sudo git clone https://github.com/filescenter/Mon.git /opt/Mon
```

```bash
cd /opt/Mon/deploy
```

3. الإعدادات:

```bash
sudo cp .env.example .env
```

   عدّل `.env`: ضع الدومين في `DOMAIN` وكلمة مرور طويلة في `DB_PASSWORD`.
   ثم ضع قيمة عشوائية طويلة مكان `CHANGE-ME` في `odoo.conf`.

4. إنشاء قاعدة البيانات وتنصيب المودل:

```bash
sudo docker compose run --rm odoo odoo -d siddiqa -i ib4tech_minbar --load-language=ar_001 --stop-after-init
```

5. **غيّر كلمة مرور المدير قبل فتح الموقع** (الافتراضية `admin`). ضع كلمتك مكان `NEW-PASSWORD`:

```bash
echo "env['res.users'].browse(2).password = 'NEW-PASSWORD'; env.cr.commit()" | sudo docker compose run --rm -T odoo odoo shell -d siddiqa --no-http
```

6. التشغيل:

```bash
sudo docker compose up -d
```

افتح `https://DOMAIN` فيحوّلك إلى التطبيق، ولوحة الإدارة على `https://DOMAIN/odoo`.

## بعد التشغيل

- من لوحة الإدارة: أضف وسيلة التواصل في صفحة سياسة الخصوصية، وراجع المناسبات والمدن.
- لنشر Google Play أكمل من [`../android/README.md`](../android/README.md).

## التحديث

```bash
cd /opt/Mon && sudo git pull
```

```bash
cd /opt/Mon/deploy && sudo docker compose run --rm odoo odoo -d siddiqa -u ib4tech_minbar --stop-after-init
```

```bash
sudo docker compose restart odoo
```

## النسخ الاحتياطي

`backup.sh` يحفظ نسخة من القاعدة والملفات المرفوعة في `/var/backups/siddiqa` ويحذف ما مضى عليه 14 يوماً.
للتشغيل اليومي الساعة 3:15 فجراً أضف هذا السطر عبر `sudo crontab -e`:

```
15 3 * * * /opt/Mon/deploy/backup.sh >> /var/log/siddiqa-backup.log 2>&1
```

النسخ تبقى على نفس الخادم. انسخها إلى مكان آخر دورياً، فتعطل الخادم يذهب بها معه.

## ملاحظات

- مدير قواعد البيانات معطل ومحجوب، والخادم يخدم قاعدة واحدة اسمها `siddiqa`.
- عدد العاملين (`workers`) في `odoo.conf` مضبوط على 2. ارفعه مع ترقية الخادم قبل مواسم الزيارة.
- السجلات: `sudo docker compose logs -f odoo`.
