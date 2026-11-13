import re
import secrets

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tools import email_normalize

ENTITY_TYPES = [
    ("husseiniya", "Husseiniya"),
    ("mawkib", "Mawkib"),
    ("radood", "Radood"),
    ("khatib", "Khatib"),
]

# Fields that only the administration may set; owners never write them directly.
PROTECTED_FIELDS = frozenset({
    "state", "is_verified", "owner_user_id", "active", "reject_reason",
    "contact_name", "contact_phone", "contact_email",
})


class MinbarEntity(models.Model):
    _name = "ib4tech.minbar.entity"
    _description = "Minbar Directory Page"
    _inherit = ["mail.thread", "image.mixin"]
    _order = "is_verified desc, name"

    name = fields.Char(required=True, index="trigram", tracking=True)
    entity_type = fields.Selection(
        ENTITY_TYPES, string="Type", required=True, default="husseiniya", index=True, tracking=True)
    tagline = fields.Char(help="Short line shown under the name.")
    description = fields.Text()
    cover_image = fields.Image("Cover", max_width=1600, max_height=900)
    has_image = fields.Boolean(compute="_compute_has_image", store=True)
    has_cover = fields.Boolean(compute="_compute_has_image", store=True)

    city_id = fields.Many2one("ib4tech.minbar.city", string="City", index=True, tracking=True)
    address = fields.Char()
    latitude = fields.Float(digits=(10, 6))
    longitude = fields.Float(digits=(10, 6))

    phone = fields.Char()
    whatsapp = fields.Char()
    telegram = fields.Char()
    instagram = fields.Char()
    facebook = fields.Char()
    youtube = fields.Char()
    website_url = fields.Char(string="Website")

    service_ids = fields.Many2many(
        "ib4tech.minbar.service", "ib4tech_minbar_entity_service_rel",
        "entity_id", "service_id", string="Services")
    founded_year = fields.Integer()

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Waiting Review"),
            ("published", "Published"),
            ("rejected", "Rejected"),
        ],
        string="Status", required=True, default="draft", index=True, tracking=True, copy=False,
    )
    reject_reason = fields.Text(copy=False)
    is_verified = fields.Boolean(string="Verified", tracking=True, copy=False)
    active = fields.Boolean(default=True)

    owner_user_id = fields.Many2one(
        "res.users", string="Owner Account", index=True, tracking=True, copy=False,
        help="Portal account allowed to edit this page and publish its majalis.")
    contact_name = fields.Char(groups="ib4tech_minbar.group_minbar_editor", copy=False)
    contact_phone = fields.Char(groups="ib4tech_minbar.group_minbar_editor", copy=False)
    contact_email = fields.Char(groups="ib4tech_minbar.group_minbar_editor", copy=False)

    majlis_ids = fields.One2many("ib4tech.minbar.majlis", "entity_id", string="Majalis")
    majlis_count = fields.Integer(compute="_compute_majlis_count")

    @api.depends("image_1920", "cover_image")
    def _compute_has_image(self):
        for entity in self:
            entity.has_image = bool(entity.image_1920)
            entity.has_cover = bool(entity.cover_image)

    def _compute_majlis_count(self):
        counts = dict(self.env["ib4tech.minbar.majlis"]._read_group(
            [("entity_id", "in", self.ids)], ["entity_id"], ["__count"]))
        for entity in self:
            entity.majlis_count = counts.get(entity, 0)

    # ------------------------------------------------------------------
    # Access helpers
    # ------------------------------------------------------------------
    def _is_minbar_editor(self):
        return self.env.su or self.env.user.has_group("ib4tech_minbar.group_minbar_editor")

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_minbar_editor():
            # Pages created by owners always start in the review queue, owned by their creator.
            for vals in vals_list:
                for field_name in PROTECTED_FIELDS:
                    vals.pop(field_name, None)
                vals.update(owner_user_id=self.env.uid, state="pending")
        return super().create(vals_list)

    def write(self, vals):
        if not self._is_minbar_editor() and PROTECTED_FIELDS & vals.keys():
            raise AccessError(_("Only the administration can change the status or the owner of a page."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        """Send a draft or rejected page to the review queue (owner or editor)."""
        self.check_access("write")
        if any(entity.state not in ("draft", "rejected") for entity in self):
            raise UserError(_("Only draft or rejected pages can be sent for review."))
        self.sudo().write({"state": "pending", "reject_reason": False})

    def action_publish(self):
        self.write({"state": "published", "reject_reason": False})
        self._notify_owner(_("Your page has been approved and is now visible in the app."))

    def action_reject(self):
        self.write({"state": "rejected"})
        for entity in self:
            reason = entity.reject_reason or _("No reason given.")
            entity._notify_owner(_("Your page was not approved. Reason: %s", reason))

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_toggle_verified(self):
        for entity in self:
            entity.is_verified = not entity.is_verified

    def _notify_owner(self, body):
        for entity in self.filtered("owner_user_id"):
            entity.message_post(
                body=body,
                partner_ids=entity.owner_user_id.partner_id.ids,
                subtype_xmlid="mail.mt_comment",
            )

    def action_view_majalis(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Majalis"),
            "res_model": "ib4tech.minbar.majlis",
            "view_mode": "list,calendar,form",
            "domain": [("entity_id", "=", self.id)],
            "context": {"default_entity_id": self.id},
        }

    def action_open_app_page(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": "/app/e/%d" % self.id, "target": "new"}

    # ------------------------------------------------------------------
    # Owner portal account
    # ------------------------------------------------------------------
    def action_grant_portal_access(self):
        """Create (or link) a free portal account for the owner of this page.

        With an email the standard portal invitation is sent. Without one the phone
        number becomes the login and a temporary password is shown once to the manager,
        to be handed over by phone or WhatsApp.
        """
        self.ensure_one()
        if not self.env.user.has_group("ib4tech_minbar.group_minbar_manager"):
            raise AccessError(_("Only Minbar managers can grant owner accounts."))
        if self.owner_user_id:
            raise UserError(_("This page already has an owner account."))

        email = email_normalize(self.contact_email or "")
        phone_login = re.sub(r"[^0-9+]", "", self.contact_phone or "")
        login = email or phone_login
        if not login:
            raise UserError(_("Fill in the contact email or phone of the owner first."))

        Users = self.env["res.users"].sudo().with_context(active_test=False)
        user = Users.search([("login", "=", login)], limit=1)
        password = False
        if user and not user.active:
            raise UserError(_("The account %s exists but is archived.", login))
        if not user:
            partner = self.env["res.partner"].sudo().create({
                "name": self.contact_name or self.name,
                "email": email or False,
                "phone": self.contact_phone or False,
            })
            if email:
                wizard = self.env["portal.wizard"].sudo().create(
                    {"partner_ids": [Command.set(partner.ids)]})
                wizard.user_ids.action_grant_access()
                user = Users.search([("partner_id", "=", partner.id)], limit=1)
            else:
                password = secrets.token_urlsafe(8)
                user = Users.with_context(no_reset_password=True)._create_user_from_template({
                    "login": login,
                    "partner_id": partner.id,
                    "password": password,
                })
        self.sudo().owner_user_id = user

        if password:
            message = _(
                "Login: %(login)s — temporary password: %(password)s. "
                "It is shown only once, send it to the owner now.",
                login=login, password=password)
        elif email:
            message = _("The account %s is linked. An invitation email is sent to new owners.", login)
        else:
            message = _("The existing account %s is now the owner of this page.", login)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Owner account ready"),
                "message": message,
                "type": "success",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
