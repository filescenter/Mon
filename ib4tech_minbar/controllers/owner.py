import base64
import logging
from datetime import datetime, timedelta

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .main import (
    ENTITY_TYPES, MODULE, app_tz, majlis_card, not_found, render_app, to_int, to_local,
    to_utc_naive,
)

_logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 8 * 1024 * 1024
ENTITY_TEXT_FIELDS = {
    "name": 120, "tagline": 160, "description": 5000, "address": 200, "phone": 40,
    "whatsapp": 40, "telegram": 80, "instagram": 80, "facebook": 160, "youtube": 160,
    "website_url": 200,
}
MAJLIS_TEXT_FIELDS = {
    "name": 160, "guest_names": 200, "location": 200, "live_url": 300, "description": 3000,
}


class MinbarOwner(http.Controller):
    """Pages for the owner of a husseiniya, mawkib or radood page (portal account).

    Records are read and written with the rights of the logged in user, so the
    record rules of the module decide what an owner may touch.
    """

    def _own_entities(self):
        return request.env["ib4tech.minbar.entity"].search(
            [("owner_user_id", "=", request.env.uid)])

    def _read_upload(self, name):
        upload = request.httprequest.files.get(name)
        if not upload or not upload.filename:
            return None
        data = upload.read(MAX_IMAGE_SIZE + 1)
        if len(data) > MAX_IMAGE_SIZE:
            raise UserError("حجم الصورة أكبر من 8 ميغابايت.")
        return base64.b64encode(data)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @http.route("/app/my", type="http", auth="user")
    def my(self, **kw):
        env = request.env
        tz = app_tz()
        entities = self._own_entities()
        majalis = env["ib4tech.minbar.majlis"].search([
            ("entity_id", "in", entities.ids),
            ("date_start", ">=", datetime.utcnow() - timedelta(days=1)),
        ], order="date_start, id", limit=100)
        return render_app("%s.app_my" % MODULE, {
            "entities": entities.sudo(),
            "majalis": [majlis_card(m, tz) for m in majalis.sudo()],
            "saved": kw.get("saved"),
            "user_name": env.user.name,
        }, tab="more", title="لوحة صاحب الصفحة")

    # ------------------------------------------------------------------
    # Page form
    # ------------------------------------------------------------------
    @http.route(["/app/my/entity/new", "/app/my/entity/<int:entity_id>"],
                type="http", auth="user", methods=["GET", "POST"])
    def entity_form(self, entity_id=None, **post):
        env = request.env
        Entity = env["ib4tech.minbar.entity"]
        entity = Entity
        if entity_id:
            entity = Entity.search([("id", "=", entity_id), ("owner_user_id", "=", env.uid)])
            if not entity:
                return not_found()
        error = ""
        form = {}
        if request.httprequest.method == "POST":
            form = post
            vals = {key: (post.get(key) or "").strip()[:size] for key, size in ENTITY_TEXT_FIELDS.items()}
            vals["city_id"] = to_int(post.get("city_id")) or False
            vals["founded_year"] = to_int(post.get("founded_year"))
            vals["service_ids"] = [(6, 0, [to_int(v) for v in request.httprequest.form.getlist("service_ids")])]
            if not entity:
                vals["entity_type"] = post.get("entity_type")
            if not vals["name"]:
                error = "يرجى إدخال الاسم."
            elif not entity and vals["entity_type"] not in ENTITY_TYPES:
                error = "يرجى اختيار نوع الصفحة."
            else:
                try:
                    with env.cr.savepoint():
                        image = self._read_upload("image")
                        cover = self._read_upload("cover")
                        if image:
                            vals["image_1920"] = image
                        if cover:
                            vals["cover_image"] = cover
                        if entity:
                            entity.write(vals)
                            if entity.state == "rejected":
                                entity.action_submit()
                        else:
                            entity = Entity.create(vals)
                    return request.redirect("/app/my?saved=entity")
                except AccessError:
                    error = "ليست لديك صلاحية لتعديل هذه الصفحة."
                except (UserError, ValidationError) as exc:
                    error = str(exc.args[0]) if exc.args else "تعذر حفظ الصفحة."
                except ValueError:
                    error = "تعذر قراءة الصورة، جرّب صورة أخرى."
        return render_app("%s.app_my_entity_form" % MODULE, {
            "entity": entity.sudo(),
            "form": form,
            "error": error,
            "services": env["ib4tech.minbar.service"].sudo().search([]),
        }, tab="more", title="تعديل الصفحة" if entity else "صفحة جديدة")

    # ------------------------------------------------------------------
    # Majlis form
    # ------------------------------------------------------------------
    @http.route(["/app/my/majlis/new", "/app/my/majlis/<int:majlis_id>"],
                type="http", auth="user", methods=["GET", "POST"])
    def majlis_form(self, majlis_id=None, **post):
        env = request.env
        tz = app_tz()
        Majlis = env["ib4tech.minbar.majlis"]
        entities = self._own_entities()
        if not entities:
            return request.redirect("/app/my")
        majlis = Majlis
        if majlis_id:
            majlis = Majlis.search([("id", "=", majlis_id), ("entity_id", "in", entities.ids)])
            if not majlis:
                return not_found()
        error = ""
        form = {}
        if request.httprequest.method == "POST":
            form = post
            vals = {key: (post.get(key) or "").strip()[:size] for key, size in MAJLIS_TEXT_FIELDS.items()}
            vals["entity_id"] = to_int(post.get("entity_id"))
            vals["city_id"] = to_int(post.get("city_id")) or False
            vals["occasion_id"] = to_int(post.get("occasion_id")) or False
            vals["audience"] = post.get("audience") if post.get("audience") in ("all", "men", "women") else "all"
            vals["participant_ids"] = [
                (6, 0, [to_int(v) for v in request.httprequest.form.getlist("participant_ids")])]
            repeat_days = min(max(to_int(post.get("repeat_days")), 0), 30)
            try:
                start = datetime.strptime(
                    "%s %s" % (post.get("date"), post.get("time_start")), "%Y-%m-%d %H:%M")
                vals["date_start"] = to_utc_naive(start, tz)
                vals["date_end"] = False
                if post.get("time_end"):
                    end = datetime.strptime(
                        "%s %s" % (post.get("date"), post.get("time_end")), "%Y-%m-%d %H:%M")
                    if end <= start:
                        end += timedelta(days=1)  # the majlis runs past midnight
                    vals["date_end"] = to_utc_naive(end, tz)
            except (TypeError, ValueError):
                error = "يرجى إدخال التاريخ ووقت البداية."
            if not error and not vals["name"]:
                error = "يرجى إدخال عنوان المجلس."
            if not error and vals["entity_id"] not in entities.ids:
                error = "يرجى اختيار الصفحة المنظِّمة."
            if not error:
                try:
                    with env.cr.savepoint():
                        poster = self._read_upload("poster")
                        if poster:
                            vals["poster"] = poster
                        if majlis:
                            majlis.write(vals)
                        else:
                            majlis = Majlis.create(vals)
                            if repeat_days:
                                majlis.action_repeat_daily(repeat_days)
                    return request.redirect("/app/my?saved=majlis")
                except AccessError:
                    error = "ليست لديك صلاحية لنشر مجلس على هذه الصفحة."
                except (UserError, ValidationError) as exc:
                    error = str(exc.args[0]) if exc.args else "تعذر حفظ المجلس."
                except ValueError:
                    error = "تعذر قراءة صورة الإعلان، جرّب صورة أخرى."
        local = {}
        if majlis:
            start = to_local(majlis.date_start, tz)
            local = {
                "date": start.strftime("%Y-%m-%d"),
                "time_start": start.strftime("%H:%M"),
                "time_end": to_local(majlis.date_end, tz).strftime("%H:%M") if majlis.date_end else "",
            }
        return render_app("%s.app_my_majlis_form" % MODULE, {
            "majlis": majlis.sudo(),
            "local": local,
            "form": form,
            "error": error,
            "entities": entities.sudo(),
            "default_entity": to_int(post.get("entity")) or entities[:1].id,
            "participants": env["ib4tech.minbar.entity"].sudo().search(
                [("state", "=", "published"), ("entity_type", "in", ("radood", "khatib"))], limit=500),
            "occasions": env["ib4tech.minbar.occasion"].sudo().search([]),
        }, tab="more", title="تعديل المجلس" if majlis else "مجلس جديد")

    @http.route("/app/my/majlis/<int:majlis_id>/cancel", type="http", auth="user", methods=["POST"])
    def majlis_cancel(self, majlis_id, **post):
        env = request.env
        majlis = env["ib4tech.minbar.majlis"].search(
            [("id", "=", majlis_id), ("entity_id.owner_user_id", "=", env.uid)])
        if not majlis:
            return not_found()
        majlis.action_cancel()
        return request.redirect("/app/my?saved=cancel")
