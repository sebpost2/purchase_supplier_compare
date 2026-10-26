from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    purchase_extra_cost_ids = fields.One2many("purchase.extra.cost", "partner_id", string="Extra Purchase Costs")
