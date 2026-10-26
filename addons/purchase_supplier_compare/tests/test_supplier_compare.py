from datetime import date, timedelta

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestSupplierCompare(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.dozen = cls.env.ref("uom.product_uom_dozen")
        Partner = cls.env["res.partner"]
        cls.lima = Partner.create({"name": "Lima Steel"})
        cls.andes = Partner.create({"name": "Andes Supply"})
        cls.sur = Partner.create({"name": "Sur Import"})
        Product = cls.env["product.product"]
        cls.cement = Product.create({"name": "Cement bag", "type": "consu", "uom_id": cls.unit.id})
        cls.rebar = Product.create({"name": "Rebar 1/2in", "type": "consu", "uom_id": cls.unit.id})

        # Lima: two quantity tiers on cement, no extra costs.
        cls._price(cls.lima, cls.cement, 30.0)
        cls._price(cls.lima, cls.cement, 25.0, min_qty=100)
        cls._price(cls.lima, cls.rebar, 10.0)
        # Andes: cheaper cement, but charges freight unless the goods reach 3000.
        cls._price(cls.andes, cls.cement, 28.0)
        cls._price(cls.andes, cls.rebar, 11.0)
        cls.env["purchase.extra.cost"].create({
            "partner_id": cls.andes.id, "name": "Freight", "cost_type": "fixed", "amount": 200.0, "waived_above": 3000.0,
        })
        # Sur: only quotes cement.
        cls._price(cls.sur, cls.cement, 20.0)

    @classmethod
    def _price(cls, vendor, product, price, min_qty=0.0, **vals):
        return cls.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": product.product_tmpl_id.id,
            "price": price, "min_qty": min_qty, **vals,
        })

    def _rfq(self, vendor, *lines):
        """lines: (product, qty) or (product, qty, uom)."""
        order_lines = []
        for product, qty, *uom in lines:
            vals = {"product_id": product.id, "product_qty": qty}
            if uom:
                vals["product_uom_id"] = uom[0].id
            order_lines.append(Command.create(vals))
        return self.env["purchase.order"].create({"partner_id": vendor.id, "order_line": order_lines})

    def _rows(self, order):
        return {row["partner"]: row for row in order._supplier_comparison()}

    # --- pricing each vendor

    def test_quantity_tier_applies_once_the_line_reaches_it(self):
        self.assertEqual(self._rows(self._rfq(self.lima, (self.cement, 50)))[self.lima]["goods"], 1500.0)
        self.assertEqual(self._rows(self._rfq(self.lima, (self.cement, 100)))[self.lima]["goods"], 2500.0)

    def test_freight_can_make_the_lower_unit_price_the_dearer_order(self):
        # Goods: Lima 50*30 + 20*10 = 1700, Andes 50*28 + 20*11 = 1620, but Andes adds 200 freight.
        rows = self._rfq(self.andes, (self.cement, 50), (self.rebar, 20))._supplier_comparison()
        self.assertEqual([row["partner"] for row in rows], [self.lima, self.andes, self.sur])
        self.assertEqual((rows[1]["goods"], rows[1]["extra"], rows[1]["total"]), (1620.0, 200.0, 1820.0))

    def test_fixed_cost_is_waived_once_the_goods_reach_the_threshold(self):
        andes = self._rows(self._rfq(self.andes, (self.cement, 110)))[self.andes]
        self.assertEqual((andes["goods"], andes["extra"]), (3080.0, 0.0))

    def test_percentage_cost_is_charged_on_the_goods(self):
        self.env["purchase.extra.cost"].create({
            "partner_id": self.lima.id, "name": "Insurance", "cost_type": "percent", "amount": 2.0,
        })
        lima = self._rows(self._rfq(self.lima, (self.cement, 50)))[self.lima]
        self.assertAlmostEqual(lima["extra"], 30.0)

    def test_vendor_missing_a_product_is_ranked_last_and_says_which(self):
        rows = self._rfq(self.lima, (self.cement, 50), (self.rebar, 20))._supplier_comparison()
        self.assertEqual(rows[-1]["partner"], self.sur)
        self.assertEqual(rows[-1]["missing"], self.rebar)

    def test_price_in_a_foreign_currency_is_converted_to_the_order_currency(self):
        eur = self.env.ref("base.EUR")
        eur.active = True
        self.env["res.currency.rate"].create({"currency_id": eur.id, "rate": 0.5, "name": "2000-01-01", "company_id": self.company.id})
        self._price(self.lima, self.rebar, 4.0, min_qty=20, currency_id=eur.id)  # 4 EUR = 8 in company currency
        order = self._rfq(self.lima, (self.rebar, 20))
        self.assertEqual(order.currency_id, self.company.currency_id)
        self.assertAlmostEqual(self._rows(order)[self.lima]["goods"], 160.0)

    def test_line_in_another_unit_is_priced_in_that_unit(self):
        # 2 dozen = 24 units, under the 100 tier: 30 per unit, 360 per dozen.
        order = self._rfq(self.lima, (self.cement, 2, self.dozen))
        self.assertAlmostEqual(self._rows(order)[self.lima]["goods"], 720.0)

    def test_expired_vendor_price_is_ignored(self):
        self._price(self.lima, self.rebar, 1.0, date_end=date.today() - timedelta(days=1))
        self.assertEqual(self._rows(self._rfq(self.lima, (self.rebar, 20)))[self.lima]["goods"], 200.0)

    def test_negative_extra_cost_is_rejected(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["purchase.extra.cost"].create({"partner_id": self.lima.id, "name": "Bad", "amount": -1.0})
            self.env.flush_all()

    # --- the RFQ banner

    def test_rfq_points_to_a_cheaper_vendor_and_the_saving(self):
        order = self._rfq(self.andes, (self.cement, 50), (self.rebar, 20))
        self.assertEqual(order.cheapest_partner_id, self.lima)
        self.assertAlmostEqual(order.cheapest_savings, 120.0)

    def test_no_banner_when_the_rfq_vendor_is_already_the_cheapest(self):
        self.assertFalse(self._rfq(self.lima, (self.cement, 50), (self.rebar, 20)).cheapest_partner_id)

    def test_no_banner_when_no_vendor_prices_the_products(self):
        product = self.env["product.product"].create({"name": "Unlisted", "type": "consu"})
        self.assertFalse(self._rfq(self.lima, (product, 1)).cheapest_partner_id)

    def test_no_banner_on_a_confirmed_order(self):
        order = self._rfq(self.andes, (self.cement, 50), (self.rebar, 20))
        order.button_confirm()
        self.assertFalse(order.cheapest_partner_id)

    # --- comparing and choosing

    def test_comparison_lists_every_vendor_and_flags_cheapest_and_current(self):
        order = self._rfq(self.andes, (self.cement, 50), (self.rebar, 20))
        wizard = self.env["purchase.supplier.compare"].browse(order.action_compare_suppliers()["res_id"])
        self.assertEqual(wizard.line_ids.partner_id, self.lima | self.andes | self.sur)
        self.assertEqual(wizard.line_ids.filtered("is_cheapest").partner_id, self.lima)
        self.assertEqual(wizard.line_ids.filtered("is_current").partner_id, self.andes)
        self.assertEqual(wizard.line_ids.filtered(lambda line: line.partner_id == self.sur).missing_products, "Rebar 1/2in")

    def test_choosing_a_vendor_moves_the_rfq_and_reprices_typed_prices(self):
        order = self._rfq(self.andes, (self.cement, 50), (self.rebar, 20))
        order.order_line[0].price_unit = 99.0  # typed by hand: Odoo alone would keep it
        wizard = self.env["purchase.supplier.compare"].browse(order.action_compare_suppliers()["res_id"])
        wizard.line_ids.filtered(lambda line: line.partner_id == self.lima).action_choose()
        self.assertEqual(order.partner_id, self.lima)
        self.assertEqual(order.order_line.mapped("price_unit"), [30.0, 10.0])
        self.assertEqual(order.amount_untaxed, 1700.0)
        self.assertFalse(order.cheapest_partner_id)

    def test_vendor_without_every_price_cannot_be_applied(self):
        order = self._rfq(self.lima, (self.cement, 50), (self.rebar, 20))
        with self.assertRaisesRegex(UserError, "no price for"):
            order._apply_supplier(self.sur)

    def test_confirmed_order_cannot_change_supplier(self):
        order = self._rfq(self.andes, (self.cement, 50))
        order.button_confirm()
        with self.assertRaisesRegex(UserError, "request for quotation"):
            order._apply_supplier(self.lima)
