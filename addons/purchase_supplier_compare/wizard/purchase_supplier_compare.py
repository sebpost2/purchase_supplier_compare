from odoo import fields, models


class PurchaseSupplierCompare(models.TransientModel):
    _name = "purchase.supplier.compare"
    _description = "Supplier price comparison for an RFQ"

    order_id = fields.Many2one("purchase.order", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="order_id.currency_id")
    line_ids = fields.One2many("purchase.supplier.compare.line", "wizard_id", string="Suppliers")


class PurchaseSupplierCompareLine(models.TransientModel):
    _name = "purchase.supplier.compare.line"
    _description = "One supplier's offer for an RFQ"
    _order = "id"

    wizard_id = fields.Many2one("purchase.supplier.compare", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    partner_id = fields.Many2one("res.partner", string="Vendor", readonly=True)
    goods_amount = fields.Monetary(string="Products", readonly=True)
    extra_amount = fields.Monetary(string="Extra Costs", readonly=True)
    total_amount = fields.Monetary(string="Total", readonly=True)
    missing_products = fields.Char(string="No Price For", readonly=True)
    is_current = fields.Boolean(readonly=True)
    is_cheapest = fields.Boolean(readonly=True)

    def action_choose(self):
        self.ensure_one()
        self.wizard_id.order_id._apply_supplier(self.partner_id)
        return {"type": "ir.actions.act_window_close"}
