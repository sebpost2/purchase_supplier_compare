{
    "name": "Purchase Supplier Price Comparison",
    "version": "19.0.1.0.0",
    "summary": "Compare suppliers on an RFQ by total cost: volume-tiered prices plus each vendor's freight and other extra costs.",
    "description": """
Prices every line of an RFQ with each vendor's own price list (Odoo's vendor
prices, including quantity tiers), adds that vendor's freight and other extra
costs, and ranks the vendors by total. The RFQ shows a banner when another
vendor would be cheaper, and the comparison applies the chosen vendor and its
prices in one click.
""",
    "author": "Sebastian Postigo",
    "license": "LGPL-3",
    "category": "Inventory/Purchase",
    "depends": ["purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/purchase_order_views.xml",
        "wizard/purchase_supplier_compare_views.xml",
    ],
    "demo": ["data/demo.xml"],
    "installable": True,
    "application": False,
}
