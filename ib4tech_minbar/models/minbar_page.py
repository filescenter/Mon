from odoo import fields, models


class MinbarPage(models.Model):
    _name = "ib4tech.minbar.page"
    _description = "Minbar Information Page"
    _order = "sequence, id"

    name = fields.Char(string="Title", required=True)
    slug = fields.Char(
        string="Page Address", required=True, index=True,
        help="Last part of the page address: /app/page/<address>. Latin letters, digits and dashes.")
    body = fields.Html(string="Text", sanitize=True)
    show_in_menu = fields.Boolean(
        string="Listed in the App", default=True, help="Adds a link to this page in the More tab.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _slug_uniq = models.Constraint("UNIQUE (slug)", "Another page already uses this address.")
    _slug_format = models.Constraint(
        "CHECK (slug ~ '^[a-z0-9-]+$')",
        "The address may only contain lowercase Latin letters, digits and dashes.",
    )
