from odoo import fields, models


class MinbarService(models.Model):
    _name = "ib4tech.minbar.service"
    _description = "Minbar Service Offered"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint("UNIQUE (name)", "This service already exists.")
