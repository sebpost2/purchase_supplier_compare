from odoo import fields, models


class PurchaseExtraCost(models.Model):
    _name = "purchase.extra.cost"
    _description = "Vendor extra cost per purchase"
    _order = "partner_id, sequence, id"

    partner_id = fields.Many2one("res.partner", string="Vendor", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Cost", required=True, help="e.g. Freight to Arequipa, insurance, customs broker.")
    cost_type = fields.Selection(
        [("fixed", "Fixed per order"), ("percent", "% of the goods")],
        string="Type", required=True, default="fixed",
    )
    amount = fields.Float(required=True, help="Fixed amount in the company currency, or a percentage of the goods.")
    waived_above = fields.Monetary(
        string="Waived Above", currency_field="company_currency_id",
        help="The vendor drops this cost when the goods reach this amount (free freight). Leave empty if never.",
    )
    company_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, readonly=True)

    _amount_positive = models.Constraint("CHECK(amount >= 0)", "An extra cost cannot be negative.")

    def _amount_for(self, order, goods):
        """This cost on `order`, in the order's currency, for `goods` worth of products."""
        self.ensure_one()
        date = fields.Date.context_today(order, timestamp=order.date_order)

        def to_order(amount):
            return self.company_currency_id._convert(amount, order.currency_id, order.company_id, date, round=False)

        if self.waived_above and goods >= to_order(self.waived_above):
            return 0.0
        if self.cost_type == "percent":
            return goods * self.amount / 100
        return to_order(self.amount)
