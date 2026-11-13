from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

HIJRI_MONTHS = [
    ("1", "Muharram"),
    ("2", "Safar"),
    ("3", "Rabi al-Awwal"),
    ("4", "Rabi al-Thani"),
    ("5", "Jumada al-Ula"),
    ("6", "Jumada al-Akhirah"),
    ("7", "Rajab"),
    ("8", "Shaban"),
    ("9", "Ramadan"),
    ("10", "Shawwal"),
    ("11", "Dhu al-Qadah"),
    ("12", "Dhu al-Hijjah"),
]


class MinbarOccasion(models.Model):
    _name = "ib4tech.minbar.occasion"
    _description = "Minbar Hijri Occasion"
    _order = "hijri_month_number, hijri_day, id"

    name = fields.Char(required=True)
    hijri_month = fields.Selection(HIJRI_MONTHS, required=True)
    hijri_month_number = fields.Integer(
        compute="_compute_hijri_month_number", store=True, string="Hijri Month Number")
    hijri_day = fields.Integer(required=True, default=1)
    occasion_type = fields.Selection(
        [
            ("wiladah", "Birth"),
            ("shahadah", "Martyrdom"),
            ("eid", "Eid"),
            ("other", "Other"),
        ],
        string="Type", required=True, default="other",
    )
    note = fields.Text()
    active = fields.Boolean(default=True)

    @api.depends("hijri_month")
    def _compute_hijri_month_number(self):
        for occasion in self:
            occasion.hijri_month_number = int(occasion.hijri_month or 0)

    @api.constrains("hijri_day")
    def _check_hijri_day(self):
        for occasion in self:
            if not 1 <= occasion.hijri_day <= 30:
                raise ValidationError(_("The hijri day must be between 1 and 30."))
