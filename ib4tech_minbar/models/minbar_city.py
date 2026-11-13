from odoo import fields, models
from odoo.addons.base.models.res_partner import _tz_get


class MinbarCity(models.Model):
    _name = "ib4tech.minbar.city"
    _description = "Minbar City"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    governorate = fields.Char()
    latitude = fields.Float(digits=(10, 6))
    longitude = fields.Float(digits=(10, 6))
    tz = fields.Selection(_tz_get, string="Timezone", default="Asia/Baghdad", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "UNIQUE (name, governorate)",
        "This city already exists in the same governorate.",
    )
