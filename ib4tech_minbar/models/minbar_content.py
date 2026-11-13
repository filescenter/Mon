from odoo import api, fields, models

WEEKDAYS = [
    ("6", "Sunday"),
    ("0", "Monday"),
    ("1", "Tuesday"),
    ("2", "Wednesday"),
    ("3", "Thursday"),
    ("4", "Friday"),
    ("5", "Saturday"),
]


class MinbarContentCategory(models.Model):
    _name = "ib4tech.minbar.content.category"
    _description = "Minbar Library Section"
    _order = "sequence, name"

    name = fields.Char(required=True)
    description = fields.Char()
    icon = fields.Selection(
        [
            ("dua", "Dua"),
            ("ziyarah", "Ziyarah"),
            ("taqib", "Taqibat"),
            ("munajat", "Munajat"),
            ("dhikr", "Dhikr"),
            ("book", "Book"),
        ],
        required=True, default="dua",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    content_ids = fields.One2many("ib4tech.minbar.content", "category_id", string="Texts")
    content_count = fields.Integer(compute="_compute_content_count")

    @api.depends("content_ids.is_published")
    def _compute_content_count(self):
        counts = dict(self.env["ib4tech.minbar.content"]._read_group(
            [("category_id", "in", self.ids), ("is_published", "=", True)],
            ["category_id"], ["__count"]))
        for category in self:
            category.content_count = counts.get(category, 0)


class MinbarContent(models.Model):
    _name = "ib4tech.minbar.content"
    _description = "Minbar Library Text"
    _order = "sequence, name"

    name = fields.Char(string="Title", required=True, index="trigram")
    category_id = fields.Many2one(
        "ib4tech.minbar.content.category", string="Section", required=True, index=True,
        ondelete="restrict")
    intro = fields.Text(string="Introduction", help="Merit, timing or how to recite it.")
    body = fields.Html(string="Text", sanitize=True)
    source = fields.Char(help="Reference of the text, e.g. the book it is taken from.")
    audio_url = fields.Char(string="Audio Link")
    occasion_id = fields.Many2one("ib4tech.minbar.occasion", string="Occasion")
    weekday = fields.Selection(
        WEEKDAYS, string="Day of the Week", help="Shown on the home page on that day.")
    is_featured = fields.Boolean(string="Featured")
    is_published = fields.Boolean(string="Published", default=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
