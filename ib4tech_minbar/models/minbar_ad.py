from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MinbarAd(models.Model):
    _name = "ib4tech.minbar.ad"
    _description = "Minbar Announcement"
    _order = "sequence, id desc"

    name = fields.Char(required=True, help="Internal title, also read out by screen readers.")
    image = fields.Image("Poster", max_width=1600, max_height=2000, required=True)
    majlis_id = fields.Many2one(
        "ib4tech.minbar.majlis", string="Opens Majlis", ondelete="set null",
        help="Tapping the poster opens this majlis.")
    entity_id = fields.Many2one(
        "ib4tech.minbar.entity", string="Opens Page", ondelete="set null",
        help="Tapping the poster opens this directory page.")
    url = fields.Char(string="Opens Link", help="Used when no majlis or page is chosen.")
    date_start = fields.Datetime(string="Show From")
    date_end = fields.Datetime(string="Show Until")
    city_ids = fields.Many2many(
        "ib4tech.minbar.city", "ib4tech_minbar_ad_city_rel", "ad_id", "city_id",
        string="Only in Cities", help="Leave empty to show the announcement everywhere.")
    countdown = fields.Integer(
        string="Seconds Before Closing", default=3,
        help="The close button appears after this many seconds.")
    frequency = fields.Selection(
        [
            ("session", "Every time the app is opened"),
            ("daily", "Once a day"),
            ("once", "Once only"),
        ],
        string="Shown", required=True, default="session",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    view_count = fields.Integer(string="Views", readonly=True, copy=False)
    click_count = fields.Integer(string="Taps", readonly=True, copy=False)

    _check_dates = models.Constraint(
        "CHECK (date_end IS NULL OR date_start IS NULL OR date_end >= date_start)",
        "The announcement cannot end before it starts.",
    )

    @api.constrains("countdown")
    def _check_countdown(self):
        for ad in self:
            if not 0 <= ad.countdown <= 15:
                raise ValidationError(_("The countdown must be between 0 and 15 seconds."))

    @api.model
    def _get_running(self, city=None, limit=5):
        """Announcements to show now to a visitor of ``city`` (None: no city known)."""
        now = fields.Datetime.now()
        domain = [
            "|", ("date_start", "=", False), ("date_start", "<=", now),
            "|", ("date_end", "=", False), ("date_end", ">=", now),
        ]
        if city:
            domain += ["|", ("city_ids", "=", False), ("city_ids", "in", city.ids)]
        else:
            domain += [("city_ids", "=", False)]
        return self.search(domain, limit=limit)

    def _is_running(self):
        self.ensure_one()
        now = fields.Datetime.now()
        return (self.active
                and (not self.date_start or self.date_start <= now)
                and (not self.date_end or self.date_end >= now))

    def _target_url(self):
        """Where a tap on the poster leads, or an empty string."""
        self.ensure_one()
        majlis = self.majlis_id
        if majlis and majlis.state == "published" and majlis.entity_id.state == "published":
            return "/app/majlis/%d" % majlis.id
        if self.entity_id.state == "published":
            return "/app/e/%d" % self.entity_id.id
        url = (self.url or "").strip()
        return url if url.lower().startswith(("http://", "https://", "/app")) else ""

    def _count_hit(self, kind):
        """Add one view or tap without touching the rest of the record."""
        column = {"view": "view_count", "click": "click_count"}.get(kind)
        if column and self:
            self.env.cr.execute(
                "UPDATE ib4tech_minbar_ad SET %s = COALESCE(%s, 0) + 1 WHERE id IN %%s" % (column, column),
                (tuple(self.ids),))
            self.invalidate_recordset([column])
