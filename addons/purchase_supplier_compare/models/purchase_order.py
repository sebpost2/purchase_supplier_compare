from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cheapest_partner_id = fields.Many2one(
        "res.partner", compute="_compute_cheapest_partner",
        help="Another vendor that quotes every line of this RFQ for less, extra costs included.",
    )
    cheapest_savings = fields.Monetary(compute="_compute_cheapest_partner")

    @api.depends(
        "state", "partner_id", "currency_id", "date_order",
        "order_line.product_id", "order_line.product_qty", "order_line.product_uom_id",
    )
    def _compute_cheapest_partner(self):
        for order in self:
            order.cheapest_partner_id = False
            order.cheapest_savings = 0.0
            if order.state not in ("draft", "sent") or not order.currency_id:
                continue
            complete = [row for row in order._supplier_comparison() if not row["missing"]]
            if not complete:
                continue
            best = complete[0]
            current = next((row for row in complete if row["partner"] == order.partner_id), None)
            if current is None:
                order.cheapest_partner_id = best["partner"]
            elif order.currency_id.compare_amounts(best["total"], current["total"]) < 0:
                order.cheapest_partner_id = best["partner"]
                order.cheapest_savings = current["total"] - best["total"]

    def _product_lines(self):
        return self.order_line.filtered(lambda line: line.product_id and not line.display_type)

    def _vendor_price(self, line, vendor):
        """(vendor price row, undiscounted unit price in the line's unit and the order's currency) for `vendor`
        on `line`, picked by Odoo's own rule: the vendor's best price whose minimum quantity the line reaches."""
        date = fields.Date.context_today(self, timestamp=self.date_order)
        seller = line.product_id._select_seller(
            partner_id=vendor,
            quantity=abs(line.product_qty),
            date=date,
            uom_id=line.product_uom_id,
            params=line._get_select_sellers_params(),
        )
        if not seller:
            return seller, 0.0
        price = seller.currency_id._convert(seller.price, self.currency_id, self.company_id, date, round=False)
        return seller, seller.product_uom_id._compute_price(price, line.product_uom_id)

    def _supplier_comparison(self):
        """One row per vendor with a price for at least one product of this RFQ: goods, extra costs and total
        in the order's currency. Vendors that quote every line come first, cheapest first."""
        self.ensure_one()
        self = self.with_company(self.company_id)
        lines = self._product_lines()
        rows = []
        for vendor in lines.product_id.seller_ids.partner_id:
            goods, missing = 0.0, self.env["product.product"]
            for line in lines:
                seller, price_unit = self._vendor_price(line, vendor)
                if not seller:
                    missing |= line.product_id
                    continue
                goods += price_unit * (1 - seller.discount / 100) * line.product_qty
            extra = sum(cost._amount_for(self, goods) for cost in vendor.purchase_extra_cost_ids)
            rows.append({"partner": vendor, "goods": goods, "extra": extra, "total": goods + extra, "missing": missing})
        return sorted(rows, key=lambda row: (bool(row["missing"]), row["total"]))

    def _apply_supplier(self, vendor):
        """Move this RFQ to `vendor` and reprice every line with that vendor's prices, as compared."""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_("Only a request for quotation can change supplier."))
        self.partner_id = vendor
        self.onchange_partner_id()
        for line in self._product_lines():
            seller, price_unit = self._vendor_price(line, vendor)
            if not seller:
                raise UserError(_(
                    "%(vendor)s has no price for %(product)s.",
                    vendor=vendor.display_name, product=line.product_id.display_name,
                ))
            # Set explicitly: Odoo keeps a price the user typed by hand, but the comparison assumed the vendor's.
            line._reset_price_unit(price_unit)
            line.discount = seller.discount

    def action_compare_suppliers(self):
        self.ensure_one()
        wizard = self.env["purchase.supplier.compare"].create({
            "order_id": self.id,
            "line_ids": [
                fields.Command.create({
                    "partner_id": row["partner"].id,
                    "goods_amount": row["goods"],
                    "extra_amount": row["extra"],
                    "total_amount": row["total"],
                    "missing_products": ", ".join(row["missing"].mapped("display_name")),
                    "is_current": row["partner"] == self.partner_id,
                    "is_cheapest": index == 0 and not row["missing"],
                })
                for index, row in enumerate(self._supplier_comparison())
            ],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Compare suppliers"),
            "res_model": "purchase.supplier.compare",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
