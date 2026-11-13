import json
import logging
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import http
from odoo.http import request
from odoo.modules.module import Manifest
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MODULE = "ib4tech_minbar"
PAGE_SIZE = 40

# Arabic labels of the public app. The app is Arabic-only, so they live with the
# controllers instead of the translation tables used by the back office.
ENTITY_TYPES = {
    "husseiniya": {"label": "حسينية", "plural": "الحسينيات", "icon": "i-dome"},
    "mawkib": {"label": "موكب", "plural": "المواكب", "icon": "i-flag"},
    "radood": {"label": "رادود", "plural": "الرواديد", "icon": "i-mic"},
    "khatib": {"label": "خطيب", "plural": "الخطباء", "icon": "i-minbar"},
}
AUDIENCES = {"all": "للجميع", "men": "للرجال", "women": "للنساء"}
STATES = {
    "draft": "مسودة",
    "pending": "بانتظار المراجعة",
    "published": "منشور",
    "rejected": "مرفوض",
    "cancelled": "ملغى",
}
# Indexed like datetime.weekday(): Monday is 0.
WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = [
    "كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران",
    "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول",
]
IMAGE_FIELDS = {"image_128", "image_256", "image_512", "image_1024", "cover_image"}


def app_version():
    manifest = Manifest.for_addon(MODULE, display_warning=False)
    return manifest.version if manifest else "0"


def get_param(key, default=None):
    return request.env["ir.config_parameter"].sudo().get_param("%s.%s" % (MODULE, key), default)


def app_tz():
    try:
        return pytz.timezone(get_param("tz") or "Asia/Baghdad")
    except pytz.UnknownTimeZoneError:
        return pytz.timezone("Asia/Baghdad")


def to_local(value, tz):
    return pytz.utc.localize(value).astimezone(tz)


def to_utc_naive(value, tz):
    return tz.localize(value).astimezone(pytz.utc).replace(tzinfo=None)


def day_start_utc(tz, offset_days=0):
    """UTC naive datetime of local midnight, ``offset_days`` days from today."""
    day = datetime.now(tz).date() + timedelta(days=offset_days)
    return to_utc_naive(datetime.combine(day, time.min), tz)


def format_time(value):
    hour = value.hour % 12 or 12
    return "%d:%02d %s" % (hour, value.minute, "ص" if value.hour < 12 else "م")


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_ids(value, limit=100):
    return [int(part) for part in re.findall(r"\d+", value or "")][:limit]


def published_entity_domain():
    return [("state", "=", "published")]


def published_majlis_domain():
    return [("state", "=", "published"), ("entity_id.state", "=", "published")]


def entity_links(entity):
    """Contact buttons of a directory page, built from whatever the owner typed."""
    def handle(value):
        return (value or "").strip().rstrip("/").rsplit("/", 1)[-1].lstrip("@")

    def http_url(value):
        value = (value or "").strip()
        return value if value.lower().startswith(("http://", "https://")) else ""

    whatsapp = re.sub(r"\D", "", entity.whatsapp or "")
    if whatsapp.startswith("0"):
        whatsapp = "964" + whatsapp[1:]  # local Iraqi number typed without the country code
    candidates = [
        ("i-phone", "اتصال", "tel:%s" % re.sub(r"[^0-9+]", "", entity.phone) if entity.phone else "", False),
        ("i-chat", "واتساب", "https://wa.me/%s" % whatsapp if whatsapp else "", True),
        ("i-send", "تلغرام", "https://t.me/%s" % handle(entity.telegram) if entity.telegram else "", True),
        ("i-camera", "إنستغرام",
         "https://instagram.com/%s" % handle(entity.instagram) if entity.instagram else "", True),
        ("i-play", "يوتيوب", http_url(entity.youtube), True),
        ("i-users", "فيسبوك", http_url(entity.facebook), True),
        ("i-globe", "الموقع", http_url(entity.website_url), True),
    ]
    if entity.latitude or entity.longitude:
        candidates.append(("i-pin", "الخريطة", "https://www.google.com/maps/search/?api=1&query=%s,%s" % (
            entity.latitude, entity.longitude), True))
    return [
        {"icon": icon, "label": label, "url": url, "external": external}
        for icon, label, url, external in candidates if url
    ]


def visitor_city():
    """City the visitor picked in the app (kept in a cookie), else the default city.

    Visitors who use the position of their phone instead get no city at all.
    """
    picked = request.httprequest.cookies.get("minbar_city")
    if picked == "gps":
        return request.env["ib4tech.minbar.city"]
    wanted = to_int(picked) or to_int(get_param("default_city_id"))
    return request.env["ib4tech.minbar.city"].sudo().browse(wanted).exists()


def group_cities(cities):
    """Cities grouped by governorate, keeping the configured order."""
    groups = {}
    for city in cities:
        groups.setdefault(city.governorate or "", []).append(city)
    return [{"name": name, "cities": members} for name, members in groups.items()]


def majlis_card(majlis, tz, now=None):
    """Display values of a majlis in the app timezone."""
    now = now or datetime.now(tz)
    start = to_local(majlis.date_start, tz)
    end = to_local(majlis.date_end, tz) if majlis.date_end else start + timedelta(hours=2)
    delta = (start.date() - now.date()).days
    names = majlis.participant_ids.mapped("name")
    if majlis.guest_names:
        names.append(majlis.guest_names)
    return {
        "rec": majlis,
        "day_key": start.date().isoformat(),
        "day_label": {0: "اليوم", 1: "غداً", -1: "أمس"}.get(delta) or WEEKDAYS[start.weekday()],
        "date_label": "%d %s" % (start.day, MONTHS[start.month - 1]),
        "full_date": "%s %d %s %d" % (
            WEEKDAYS[start.weekday()], start.day, MONTHS[start.month - 1], start.year),
        "day_number": start.day,
        "month_label": MONTHS[start.month - 1],
        "time_label": format_time(start),
        "end_label": format_time(end) if majlis.date_end else "",
        "is_live": majlis.state == "published" and start <= now <= end,
        "is_past": end < now,
        "participants": "، ".join(names),
        "place": majlis.location or majlis.entity_id.address or "",
    }


def group_by_day(cards):
    groups = []
    for card in cards:
        if not groups or groups[-1]["key"] != card["day_key"]:
            groups.append({
                "key": card["day_key"],
                "label": card["day_label"],
                "date": card["date_label"],
                "cards": [],
            })
        groups[-1]["cards"].append(card)
    return groups


def render_app(template, values=None, tab="home", title=None, status=200):
    """Render an app page with the values every page needs."""
    env = request.env
    app_name = get_param("app_name") or "الصدّيقة"
    cities = env["ib4tech.minbar.city"].sudo().search([])
    occasions = env["ib4tech.minbar.occasion"].sudo().search([])
    app_data = {
        "appName": app_name,
        "version": app_version(),
        "hijriOffset": to_int(get_param("hijri_offset")),
        "mourningTheme": get_param("mourning_theme") in ("True", "1", "true"),
        "defaultCityId": to_int(get_param("default_city_id")) or cities[:1].id,
        "cities": [
            {"id": c.id, "name": c.name, "gov": c.governorate or "",
             "lat": c.latitude, "lng": c.longitude, "tz": c.tz}
            for c in cities
        ],
        "occasions": [
            {"name": o.name, "m": o.hijri_month_number, "d": o.hijri_day, "t": o.occasion_type}
            for o in occasions
        ],
    }
    base_url = request.httprequest.host_url.rstrip("/")
    context = {
        "app_name": app_name,
        "base_url": base_url,
        "og_image": "%s/%s/static/src/app/icons/icon-512.png" % (base_url, MODULE),
        "og_description": "مواعيد المجالس، دليل الحسينيات والمواكب والرواديد، الأدعية والزيارات وأوقات الصلاة.",
        "city_groups": group_cities(cities),
        "title": title,
        "tab": tab,
        "app_data": json.dumps(app_data, ensure_ascii=False),
        "asset_version": app_version(),
        "entity_types": ENTITY_TYPES,
        "audiences": AUDIENCES,
        "states": STATES,
        "cities": cities,
        "is_logged": not env.user._is_public(),
    }
    context.update(values or {})
    response = request.render(template, context)
    response.status_code = status
    return response


def not_found():
    return render_app("%s.app_not_found" % MODULE, title="غير موجود", status=404)


class MinbarApp(http.Controller):

    # ------------------------------------------------------------------
    # Home
    # ------------------------------------------------------------------
    @http.route(["/app", "/app/"], type="http", auth="public", readonly=True)
    def home(self, **kw):
        env = request.env
        tz = app_tz()
        now = datetime.now(tz)
        now_utc = datetime.utcnow()
        city = visitor_city()
        Majlis = env["ib4tech.minbar.majlis"].sudo()
        upcoming = published_majlis_domain() + [("date_start", ">=", now_utc - timedelta(hours=2))]
        majalis = Majlis
        if city:
            majalis = Majlis.search(upcoming + [("city_id", "=", city.id)], order="date_start, id", limit=6)
        majalis_city = city if majalis else city.browse()
        if not majalis:
            majalis = Majlis.search(upcoming, order="date_start, id", limit=6)
        Content = env["ib4tech.minbar.content"].sudo()
        featured = Content.search(
            [("is_published", "=", True), ("weekday", "=", str(now.weekday()))], limit=2)
        featured |= Content.search(
            [("is_published", "=", True), ("is_featured", "=", True)], limit=4)
        Entity = env["ib4tech.minbar.entity"].sudo()
        newest = "is_verified desc, create_date desc"
        entities = Entity
        if city:
            entities = Entity.search(
                published_entity_domain() + [("city_id", "=", city.id)], order=newest, limit=6)
        if len(entities) < 6:
            entities |= Entity.search(
                published_entity_domain() + [("id", "not in", entities.ids)],
                order=newest, limit=6 - len(entities))
        ads = [
            {
                "id": ad.id,
                "title": ad.name,
                "image": "/app/image/ad/%d/poster?u=%d" % (ad.id, int(ad.write_date.timestamp())),
                "url": ad._target_url(),
                "seconds": ad.countdown,
                "frequency": ad.frequency,
            }
            for ad in env["ib4tech.minbar.ad"].sudo()._get_running(city)
        ]
        return render_app("%s.app_home" % MODULE, {
            "ads": json.dumps(ads, ensure_ascii=False) if ads else "",
            "majalis": [majlis_card(m, tz, now) for m in majalis],
            "majalis_city": majalis_city,
            "featured": featured[:4],
            "entities": entities,
        }, tab="home")

    # ------------------------------------------------------------------
    # Majalis
    # ------------------------------------------------------------------
    @http.route("/app/majalis", type="http", auth="public", readonly=True)
    def majalis(self, city=None, when="all", q="", audience="", offset=0, **kw):
        env = request.env
        tz = app_tz()
        q = (q or "").strip()[:80]
        # First visit (no filter chosen yet): start from the visitor's own city.
        city_id = visitor_city().id if city is None and not q else to_int(city)
        offset = max(to_int(offset), 0)
        domain = published_majlis_domain()
        if when == "today":
            domain += [("date_start", ">=", day_start_utc(tz)), ("date_start", "<", day_start_utc(tz, 1))]
        elif when == "tomorrow":
            domain += [("date_start", ">=", day_start_utc(tz, 1)), ("date_start", "<", day_start_utc(tz, 2))]
        elif when == "week":
            domain += [("date_start", ">=", day_start_utc(tz)), ("date_start", "<", day_start_utc(tz, 7))]
        else:
            when = "all"
            domain += [("date_start", ">=", datetime.utcnow() - timedelta(hours=3))]
        if city_id:
            domain += [("city_id", "=", city_id)]
        if audience in ("men", "women"):
            domain += [("audience", "in", (audience, "all"))]
        else:
            audience = ""
        if q:
            domain += ["|", "|", "|",
                       ("name", "ilike", q), ("entity_id.name", "ilike", q),
                       ("participant_ids.name", "ilike", q), ("guest_names", "ilike", q)]
        Majlis = env["ib4tech.minbar.majlis"].sudo()
        records = Majlis.search(domain, order="date_start, id", limit=PAGE_SIZE + 1, offset=offset)
        has_more = len(records) > PAGE_SIZE
        cards = [majlis_card(m, tz) for m in records[:PAGE_SIZE]]
        return render_app("%s.app_majalis" % MODULE, {
            "groups": group_by_day(cards),
            "filters": {"city": city_id, "when": when, "q": q, "audience": audience},
            "next_offset": offset + PAGE_SIZE if has_more else 0,
        }, tab="majalis", title="مواعيد المجالس")

    def _get_public_majlis(self, majlis_id):
        majlis = request.env["ib4tech.minbar.majlis"].sudo().browse(majlis_id).exists()
        if (not majlis or majlis.state not in ("published", "cancelled")
                or majlis.entity_id.state != "published"):
            return None
        return majlis

    @http.route("/app/majlis/<int:majlis_id>", type="http", auth="public", readonly=True)
    def majlis_detail(self, majlis_id, **kw):
        majlis = self._get_public_majlis(majlis_id)
        if not majlis:
            return not_found()
        card = majlis_card(majlis, app_tz())
        host = request.httprequest.host_url.rstrip("/")
        values = {
            "card": card,
            "majlis": majlis,
            "share_url": "%s/app/majlis/%d" % (host, majlis.id),
            "og_description": " · ".join(filter(None, [
                card["full_date"], card["time_label"], majlis.entity_id.name, majlis.city_id.name])),
        }
        if majlis.has_poster:
            values["og_image"] = "%s/app/image/majlis/%d/poster" % (host, majlis.id)
        return render_app("%s.app_majlis" % MODULE, values, tab="majalis", title=majlis.name)

    @http.route("/app/majlis/<int:majlis_id>/calendar.ics", type="http", auth="public", readonly=True)
    def majlis_ics(self, majlis_id, **kw):
        majlis = self._get_public_majlis(majlis_id)
        if not majlis:
            raise request.not_found()

        def esc(text):
            return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

        end = majlis.date_end or majlis.date_start + timedelta(hours=2)
        stamp = "%Y%m%dT%H%M%SZ"
        host = request.httprequest.host_url.rstrip("/")
        place = "، ".join(filter(None, [
            majlis.entity_id.name, majlis.location or majlis.entity_id.address, majlis.city_id.name]))
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//IB4Tech//Minbar//AR",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            "UID:minbar-majlis-%d@%s" % (majlis.id, request.httprequest.host),
            "DTSTAMP:%s" % datetime.utcnow().strftime(stamp),
            "DTSTART:%s" % majlis.date_start.strftime(stamp),
            "DTEND:%s" % end.strftime(stamp),
            "SUMMARY:%s" % esc(majlis.name),
            "LOCATION:%s" % esc(place),
            "DESCRIPTION:%s" % esc(majlis.description),
            "URL:%s/app/majlis/%d" % (host, majlis.id),
            "BEGIN:VALARM",
            "TRIGGER:-PT30M",
            "ACTION:DISPLAY",
            "DESCRIPTION:%s" % esc(majlis.name),
            "END:VALARM",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return request.make_response("\r\n".join(lines) + "\r\n", headers=[
            ("Content-Type", "text/calendar; charset=utf-8"),
            ("Content-Disposition", 'attachment; filename="majlis-%d.ics"' % majlis.id),
        ])

    # ------------------------------------------------------------------
    # Directory
    # ------------------------------------------------------------------
    @http.route("/app/directory", type="http", auth="public", readonly=True)
    def directory(self, q="", **kw):
        Entity = request.env["ib4tech.minbar.entity"].sudo()
        q = (q or "").strip()[:80]
        counts = dict(Entity._read_group(published_entity_domain(), ["entity_type"], ["__count"]))
        results = Entity
        if q:
            results = Entity.search(published_entity_domain() + [("name", "ilike", q)], limit=PAGE_SIZE)
        return render_app("%s.app_directory" % MODULE, {
            "counts": counts,
            "q": q,
            "results": results,
        }, tab="directory", title="الدليل")

    @http.route("/app/directory/<string:etype>", type="http", auth="public", readonly=True)
    def directory_type(self, etype, city=None, q="", service=None, offset=0, **kw):
        if etype not in ENTITY_TYPES:
            return not_found()
        env = request.env
        city_id = to_int(city)
        service_id = to_int(service)
        offset = max(to_int(offset), 0)
        q = (q or "").strip()[:80]
        domain = published_entity_domain() + [("entity_type", "=", etype)]
        if city_id:
            domain += [("city_id", "=", city_id)]
        if service_id:
            domain += [("service_ids", "in", service_id)]
        if q:
            domain += ["|", ("name", "ilike", q), ("tagline", "ilike", q)]
        records = env["ib4tech.minbar.entity"].sudo().search(
            domain, limit=PAGE_SIZE + 1, offset=offset)
        has_more = len(records) > PAGE_SIZE
        return render_app("%s.app_directory_type" % MODULE, {
            "etype": etype,
            "meta": ENTITY_TYPES[etype],
            "entities": records[:PAGE_SIZE],
            "services": env["ib4tech.minbar.service"].sudo().search([]) if etype == "mawkib" else [],
            "filters": {"city": city_id, "q": q, "service": service_id},
            "next_offset": offset + PAGE_SIZE if has_more else 0,
        }, tab="directory", title=ENTITY_TYPES[etype]["plural"])

    @http.route("/app/e/<int:entity_id>", type="http", auth="public", readonly=True)
    def entity(self, entity_id, **kw):
        env = request.env
        entity = env["ib4tech.minbar.entity"].sudo().browse(entity_id).exists()
        is_owner = bool(entity) and not env.user._is_public() and entity.owner_user_id == env.user
        if not entity or (entity.state != "published" and not is_owner):
            return not_found()
        tz = app_tz()
        majalis = env["ib4tech.minbar.majlis"].sudo().search(
            published_majlis_domain() + [
                ("date_start", ">=", datetime.utcnow() - timedelta(hours=3)),
                "|", ("entity_id", "=", entity.id), ("participant_ids", "in", entity.id),
            ], order="date_start, id", limit=30)
        values = {}
        if entity.has_image:
            values["og_image"] = "%s/app/image/entity/%d/image_512" % (
                request.httprequest.host_url.rstrip("/"), entity.id)
        if entity.tagline:
            values["og_description"] = entity.tagline
        return render_app("%s.app_entity" % MODULE, dict(values, **{
            "entity": entity,
            "meta": ENTITY_TYPES[entity.entity_type],
            "links": entity_links(entity),
            "is_owner": is_owner,
            "majalis": [majlis_card(m, tz) for m in majalis],
            "share_url": "%s/app/e/%d" % (request.httprequest.host_url.rstrip("/"), entity.id),
        }), tab="directory", title=entity.name)

    @http.route("/app/image/entity/<int:entity_id>/<string:field>", type="http", auth="public", readonly=True)
    def entity_image(self, entity_id, field, **kw):
        if field not in IMAGE_FIELDS:
            raise request.not_found()
        env = request.env
        entity = env["ib4tech.minbar.entity"].sudo().browse(entity_id).exists()
        if not entity or (entity.state != "published" and entity.owner_user_id != env.user):
            raise request.not_found()
        stream = env["ir.binary"]._get_image_stream_from(entity, field)
        return stream.get_response(max_age=http.STATIC_CACHE_LONG if kw.get("u") else 3600)

    @http.route("/app/image/majlis/<int:majlis_id>/poster", type="http", auth="public", readonly=True)
    def majlis_poster(self, majlis_id, size="", **kw):
        env = request.env
        majlis = self._get_public_majlis(majlis_id)
        if not majlis:
            # The owner may look at the poster of a majlis that is still in review.
            majlis = env["ib4tech.minbar.majlis"].sudo().browse(majlis_id).exists()
            if not majlis or env.user._is_public() or majlis.owner_user_id != env.user:
                raise request.not_found()
        if not majlis.has_poster:
            raise request.not_found()
        options = {"width": 192, "height": 192, "crop": True} if size == "thumb" else {}
        stream = env["ir.binary"]._get_image_stream_from(majlis, "poster", **options)
        return stream.get_response(max_age=http.STATIC_CACHE_LONG if kw.get("u") else 3600)

    @http.route("/app/image/ad/<int:ad_id>/poster", type="http", auth="public", readonly=True)
    def ad_poster(self, ad_id, **kw):
        ad = request.env["ib4tech.minbar.ad"].sudo().browse(ad_id).exists()
        if not ad or not ad._is_running():
            raise request.not_found()
        stream = request.env["ir.binary"]._get_image_stream_from(ad, "image")
        return stream.get_response(max_age=http.STATIC_CACHE_LONG if kw.get("u") else 3600)

    @http.route("/app/ad/<int:ad_id>/hit", type="http", auth="public", methods=["POST"], csrf=False)
    def ad_hit(self, ad_id, kind="view", **kw):
        """Counts one view or one tap of an announcement; called by the app in the background."""
        ad = request.env["ib4tech.minbar.ad"].sudo().browse(ad_id).exists()
        if ad and ad._is_running():
            ad._count_hit(kind)
        return request.make_response("", status=204)

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------
    @http.route("/app/library", type="http", auth="public", readonly=True)
    def library(self, q="", **kw):
        env = request.env
        q = (q or "").strip()[:80]
        Content = env["ib4tech.minbar.content"].sudo()
        results = Content
        if q:
            results = Content.search([("is_published", "=", True), ("name", "ilike", q)], limit=PAGE_SIZE)
        return render_app("%s.app_library" % MODULE, {
            "categories": env["ib4tech.minbar.content.category"].sudo().search([]),
            "featured": Content.search([("is_published", "=", True), ("is_featured", "=", True)], limit=8),
            "q": q,
            "results": results,
        }, tab="library", title="المكتبة")

    @http.route("/app/library/<int:category_id>", type="http", auth="public", readonly=True)
    def library_category(self, category_id, **kw):
        env = request.env
        category = env["ib4tech.minbar.content.category"].sudo().browse(category_id).exists()
        if not category:
            return not_found()
        contents = env["ib4tech.minbar.content"].sudo().search(
            [("category_id", "=", category.id), ("is_published", "=", True)])
        return render_app("%s.app_library_category" % MODULE, {
            "category": category,
            "contents": contents,
        }, tab="library", title=category.name)

    @http.route("/app/read/<int:content_id>", type="http", auth="public", readonly=True)
    def read(self, content_id, **kw):
        content = request.env["ib4tech.minbar.content"].sudo().browse(content_id).exists()
        if not content or not content.is_published:
            return not_found()
        siblings = request.env["ib4tech.minbar.content"].sudo().search(
            [("category_id", "=", content.category_id.id), ("is_published", "=", True)])
        position = siblings.ids.index(content.id)
        return render_app("%s.app_read" % MODULE, {
            "content": content,
            "previous_content": siblings[position - 1] if position else siblings.browse(),
            "next_content": siblings[position + 1:position + 2],
            "share_url": "%s/app/read/%d" % (request.httprequest.host_url.rstrip("/"), content.id),
        }, tab="library", title=content.name)

    # ------------------------------------------------------------------
    # Tools (computed in the browser from the data embedded in the page)
    # ------------------------------------------------------------------
    @http.route("/app/prayer", type="http", auth="public", readonly=True)
    def prayer(self, **kw):
        return render_app("%s.app_prayer" % MODULE, tab="more", title="أوقات الصلاة")

    @http.route("/app/qibla", type="http", auth="public", readonly=True)
    def qibla(self, **kw):
        return render_app("%s.app_qibla" % MODULE, tab="more", title="اتجاه القبلة")

    @http.route("/app/tasbih", type="http", auth="public", readonly=True)
    def tasbih(self, **kw):
        return render_app("%s.app_tasbih" % MODULE, tab="more", title="المسبحة")

    @http.route("/app/occasions", type="http", auth="public", readonly=True)
    def occasions(self, **kw):
        return render_app("%s.app_occasions" % MODULE, tab="more", title="المناسبات")

    @http.route("/app/more", type="http", auth="public", readonly=True)
    def more(self, **kw):
        return render_app("%s.app_more" % MODULE, tab="more", title="المزيد")

    @http.route("/app/favorites", type="http", auth="public", readonly=True)
    def favorites(self, **kw):
        return render_app("%s.app_favorites" % MODULE, tab="more", title="المفضلة")

    @http.route("/app/favorites/cards", type="http", auth="public", readonly=True)
    def favorites_cards(self, e="", m="", **kw):
        """HTML fragment with the cards of the favourites kept in the browser."""
        env = request.env
        tz = app_tz()
        entities = env["ib4tech.minbar.entity"].sudo().search(
            published_entity_domain() + [("id", "in", parse_ids(e))])
        majalis = env["ib4tech.minbar.majlis"].sudo().search(
            published_majlis_domain() + [
                ("id", "in", parse_ids(m)),
                ("date_start", ">=", datetime.utcnow() - timedelta(hours=3)),
            ], order="date_start, id")
        return request.render("%s.app_favorites_cards" % MODULE, {
            "entities": entities,
            "majalis": [majlis_card(x, tz) for x in majalis],
            "entity_types": ENTITY_TYPES,
            "audiences": AUDIENCES,
        })

    # ------------------------------------------------------------------
    # Join request (no account needed)
    # ------------------------------------------------------------------
    @http.route("/app/join", type="http", auth="public", methods=["GET", "POST"])
    def join(self, **post):
        env = request.env
        values = {"error": "", "form": {}, "done": False}
        if request.httprequest.method == "POST":
            form = {key: (post.get(key) or "").strip() for key in (
                "name", "entity_type", "city_id", "address", "phone",
                "contact_name", "contact_phone", "contact_email", "description")}
            values["form"] = form
            Entity = env["ib4tech.minbar.entity"].sudo()
            if post.get("nickname"):
                # Honeypot field: humans never see it, so pretend the request went through.
                values["done"] = True
            elif not form["name"] or form["entity_type"] not in ENTITY_TYPES:
                values["error"] = "يرجى إدخال الاسم واختيار النوع."
            elif not form["contact_name"] or not form["contact_phone"]:
                values["error"] = "يرجى إدخال اسم المسؤول ورقم هاتفه حتى نتواصل معك."
            elif Entity.search_count([
                    ("state", "=", "pending"), ("contact_phone", "=", form["contact_phone"])]) >= 3:
                values["error"] = "لديك طلبات قيد المراجعة، سنتواصل معك قريباً."
            else:
                entity = Entity.with_context(mail_create_nosubscribe=True).create({
                    "name": form["name"][:120],
                    "entity_type": form["entity_type"],
                    "city_id": to_int(form["city_id"]) or False,
                    "address": form["address"][:200],
                    "phone": form["phone"][:40],
                    "description": form["description"][:3000],
                    "contact_name": form["contact_name"][:120],
                    "contact_phone": form["contact_phone"][:40],
                    "contact_email": form["contact_email"][:120],
                    "state": "pending",
                    "owner_user_id": False if env.user._is_public() else env.user.id,
                })
                _logger.info("Minbar join request %s created", entity.id)
                values["done"] = True
        return render_app("%s.app_join" % MODULE, values, tab="more", title="سجّل جهتك")

    # ------------------------------------------------------------------
    # Progressive web app plumbing
    # ------------------------------------------------------------------
    @http.route("/app/manifest.webmanifest", type="http", auth="public", readonly=True)
    def manifest(self, **kw):
        app_name = get_param("app_name") or "الصدّيقة"
        icons = "/%s/static/src/app/icons" % MODULE
        manifest = {
            "id": "/app",
            "name": app_name,
            "short_name": app_name,
            "description": "مواعيد المجالس، دليل الحسينيات والمواكب والرواديد، الأدعية والزيارات وأوقات الصلاة",
            "lang": "ar",
            "dir": "rtl",
            "start_url": "/app",
            "scope": "/app",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#f6f3ec",
            "theme_color": "#0f5a4c",
            "icons": [
                {"src": icons + "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": icons + "/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {"src": icons + "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png",
                 "purpose": "maskable"},
            ],
            "shortcuts": [
                {"name": "مواعيد المجالس", "url": "/app/majalis"},
                {"name": "أوقات الصلاة", "url": "/app/prayer"},
                {"name": "المكتبة", "url": "/app/library"},
            ],
        }
        return request.make_response(json.dumps(manifest, ensure_ascii=False), headers=[
            ("Content-Type", "application/manifest+json; charset=utf-8"),
            ("Cache-Control", "public, max-age=3600"),
        ])

    @http.route("/app/sw.js", type="http", auth="public", readonly=True)
    def service_worker(self, **kw):
        with file_open("%s/static/src/app/sw.js" % MODULE, "r") as handle:
            body = handle.read().replace("__VERSION__", app_version())
        return request.make_response(body, headers=[
            ("Content-Type", "application/javascript; charset=utf-8"),
            ("Service-Worker-Allowed", "/app"),
            ("Cache-Control", "no-cache"),
        ])

    @http.route("/app/offline", type="http", auth="public", readonly=True)
    def offline(self, **kw):
        return render_app("%s.app_offline" % MODULE, tab="", title="بدون اتصال")

    @http.route("/app/offline/urls", type="http", auth="public", readonly=True)
    def offline_urls(self, **kw):
        """URLs the app stores on the device so the library can be read without a connection."""
        env = request.env
        urls = ["/app", "/app/library", "/app/prayer", "/app/qibla", "/app/tasbih",
                "/app/occasions", "/app/more", "/app/offline"]
        urls += ["/app/library/%d" % cid for cid in env["ib4tech.minbar.content.category"].sudo().search([]).ids]
        urls += ["/app/read/%d" % cid for cid in env["ib4tech.minbar.content"].sudo().search(
            [("is_published", "=", True)], limit=1000).ids]
        return request.make_response(json.dumps(urls), headers=[
            ("Content-Type", "application/json"), ("Cache-Control", "no-cache")])
