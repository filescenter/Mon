from odoo import fields, models, _


class MinbarMajlisRepeat(models.TransientModel):
    _name = "ib4tech.minbar.majlis.repeat"
    _description = "Repeat a Majlis Daily"

    majlis_id = fields.Many2one(
        "ib4tech.minbar.majlis", required=True, ondelete="cascade",
        default=lambda self: self.env.context.get("active_id"))
    days = fields.Integer(
        string="Extra Days", required=True, default=9,
        help="Number of following days on which the majlis is repeated.")

    def action_repeat(self):
        self.ensure_one()
        copies = self.majlis_id.action_repeat_daily(self.days)
        return {
            "type": "ir.actions.act_window",
            "name": _("Repeated Majalis"),
            "res_model": "ib4tech.minbar.majlis",
            "view_mode": "list,form",
            "domain": [("id", "in", (self.majlis_id + copies).ids)],
        }
