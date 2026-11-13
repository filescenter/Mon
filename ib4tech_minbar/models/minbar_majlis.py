from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

PROTECTED_FIELDS = frozenset({"state", "reject_reason"})


class MinbarMajlis(models.Model):
    _name = "ib4tech.minbar.majlis"
    _description = "Minbar Majlis"
    _inherit = ["mail.thread"]
    _order = "date_start, id"

    name = fields.Char(string="Title", required=True, tracking=True)
    entity_id = fields.Many2one(
        "ib4tech.minbar.entity", string="Organizer", required=True, index=True,
        ondelete="cascade", tracking=True)
    participant_ids = fields.Many2many(
        "ib4tech.minbar.entity", "ib4tech_minbar_majlis_participant_rel",
        "majlis_id", "entity_id", string="Radoods and Khatibs",
        domain="[('entity_type', 'in', ('radood', 'khatib')), ('state', '=', 'published')]")
    guest_names = fields.Char(
        string="Other Participants",
        help="Names of radoods or khatibs who have no page in the directory.")
    city_id = fields.Many2one(
        "ib4tech.minbar.city", string="City", index=True,
        compute="_compute_city_id", store=True, readonly=False, precompute=True)
    location = fields.Char(help="Venue or address if different from the organizer's address.")
    date_start = fields.Datetime(string="Starts At", required=True, index=True, tracking=True)
    date_end = fields.Datetime(string="Ends At")
    occasion_id = fields.Many2one("ib4tech.minbar.occasion", string="Occasion")
    audience = fields.Selection(
        [("all", "Everyone"), ("men", "Men"), ("women", "Women")],
        required=True, default="all")
    live_url = fields.Char(string="Live Stream Link")
    description = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Waiting Review"),
            ("published", "Published"),
            ("cancelled", "Cancelled"),
            ("rejected", "Rejected"),
        ],
        string="Status", required=True, default="draft", index=True, tracking=True, copy=False,
    )
    reject_reason = fields.Text(copy=False)
    owner_user_id = fields.Many2one(
        related="entity_id.owner_user_id", string="Owner Account", store=True, index=True)

    _check_dates = models.Constraint(
        "CHECK (date_end IS NULL OR date_end >= date_start)",
        "The majlis cannot end before it starts.",
    )

    @api.depends("entity_id")
    def _compute_city_id(self):
        for majlis in self:
            if not majlis.city_id:
                majlis.city_id = majlis.entity_id.city_id

    def _is_minbar_editor(self):
        return self.env.su or self.env.user.has_group("ib4tech_minbar.group_minbar_editor")

    @api.model_create_multi
    def create(self, vals_list):
        if not self._is_minbar_editor():
            auto_publish = self.env["ir.config_parameter"].sudo().get_param(
                "ib4tech_minbar.auto_publish_verified")
            Entity = self.env["ib4tech.minbar.entity"].sudo()
            for vals in vals_list:
                for field_name in PROTECTED_FIELDS:
                    vals.pop(field_name, None)
                entity = Entity.browse(vals.get("entity_id"))
                trusted = auto_publish and entity.is_verified and entity.state == "published"
                vals["state"] = "published" if trusted else "pending"
        return super().create(vals_list)

    def write(self, vals):
        is_editor = self._is_minbar_editor()
        if not is_editor and PROTECTED_FIELDS & vals.keys():
            raise AccessError(_("Only the administration can change the status of a majlis."))
        result = super().write(vals)
        if not is_editor and "entity_id" in vals:
            # Record rules are evaluated before a write only: check again so that an
            # owner cannot move a majlis onto a page that belongs to someone else.
            self.check_access("write")
        return result

    @api.constrains("participant_ids")
    def _check_participants(self):
        for majlis in self:
            if any(p.entity_type not in ("radood", "khatib") for p in majlis.participant_ids):
                raise ValidationError(_("Participants must be radoods or khatibs."))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_publish(self):
        self.write({"state": "published", "reject_reason": False})

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        """Cancel a majlis (owner or editor)."""
        self.check_access("write")
        self.sudo().write({"state": "cancelled"})

    def action_repeat_daily(self, days):
        """Copy this majlis on each of the following ``days`` days (e.g. the ten nights of Muharram)."""
        self.ensure_one()
        if not 1 <= days <= 60:
            raise UserError(_("The number of extra days must be between 1 and 60."))
        copies = self.browse()
        for offset in range(1, days + 1):
            shift = timedelta(days=offset)
            copies += self.copy({
                "name": self.name,
                "date_start": self.date_start + shift,
                "date_end": self.date_end + shift if self.date_end else False,
                "state": self.state,
            })
        return copies
