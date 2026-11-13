from odoo import fields, models
from odoo.addons.base.models.res_partner import _tz_get


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    minbar_app_name = fields.Char(
        string="App Name", config_parameter="ib4tech_minbar.app_name")
    minbar_tz = fields.Selection(
        _tz_get, string="App Timezone", config_parameter="ib4tech_minbar.tz")
    minbar_hijri_offset = fields.Integer(
        string="Hijri Date Adjustment (days)",
        config_parameter="ib4tech_minbar.hijri_offset",
        help="Days added to the computed hijri date so that it matches the local moon sighting (-2 to +2).",
    )
    minbar_default_city_id = fields.Many2one(
        "ib4tech.minbar.city", string="Default City",
        config_parameter="ib4tech_minbar.default_city_id")
    minbar_auto_publish_verified = fields.Boolean(
        string="Auto-publish majalis of verified pages",
        config_parameter="ib4tech_minbar.auto_publish_verified",
        help="Majalis added by the owner of a verified page are published without waiting for a review.",
    )
