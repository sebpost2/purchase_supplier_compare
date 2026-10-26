# purchase_supplier_compare

[![tests](https://github.com/sebpost2/purchase_supplier_compare/actions/workflows/tests.yml/badge.svg)](https://github.com/sebpost2/purchase_supplier_compare/actions/workflows/tests.yml)

**19 passing tests.** An Odoo 19 addon that answers the buyer's real question
on a request for quotation: which supplier is cheapest for *this* order, once
volume prices, freight and other extra costs are counted. The lowest unit
price often isn't the cheapest order.

> **En español:** compara proveedores en la solicitud de presupuesto por el
> costo total: el precio de cada proveedor según la cantidad (por tramos),
> más su flete, seguro u otros costos por compra. Si otro proveedor sale más
> barato, la solicitud lo avisa con el ahorro exacto, y con un clic pasa a ese
> proveedor con sus precios.

## What it does

- **Volume-tiered prices, Odoo's own way**: a supplier's price tiers are the
  standard vendor price list (several rows per product with a minimum
  quantity). Each line is priced with the tier its quantity reaches, with
  validity dates, the vendor's currency and unit of measure converted to the
  order's.
- **Extra costs per vendor** (`purchase.extra.cost`), on the vendor's Sales &
  Purchase tab: a fixed amount per order (freight, unloading) or a percentage
  of the goods (cargo insurance), optionally waived above an order amount
  (free freight).
- **Banner on the RFQ** when another vendor quotes every line for less, with
  the saving, extra costs included.
- **Total cost under the totals**: the vendor's extra costs and the untaxed
  total plus those costs, so choosing the cheaper vendor visibly lowers the
  cost even when the order total rises (the saving was in the freight).
- **Compare Suppliers**: every vendor ranked by total. Vendors missing a
  price for some product are listed last, saying which product. **Choose**
  moves the RFQ to that vendor and reprices every line with its prices,
  including lines whose price had been typed by hand.
- **In Spanish too**: `i18n/es.po` uses the Latin American wording of
  Odoo's own purchase app ("solicitud de cotización"), so a Peruvian
  (`es_PE`) user sees the whole module in Spanish.

![RFQ banner: another vendor is cheaper, with the saving](docs/screenshots/rfq-banner.png)
![Compare Suppliers: goods, extra costs and total per vendor](docs/screenshots/compare-wizard.png)
![Extra costs on the vendor](docs/screenshots/vendor-extra-costs.png)

*Screenshots in Spanish (Peru), with fictitious companies and prices.* In them, Distribuidora
Andina has the cheaper goods (S/ 11,105 vs S/ 11,360), but its freight and
insurance make Aceros Chachani S/ 586.05 cheaper for the whole order.

## Design decisions

- **No new price model.** Tiers live in `product.supplierinfo`, and each line
  is priced with Odoo's own `_select_seller`, so the comparison picks exactly
  the price Odoo would put on the line. One rule, not two that drift apart.
- **Extra costs belong to the vendor, not the product.** Freight is charged
  per shipment, so spreading it per unit would hide it on small orders and
  overstate it on big ones.
- **Advise, don't switch.** The RFQ only shows a banner; the buyer chooses.
  Lead time, quality or an open credit line can matter more than S/ 500.

## Running it

```bash
docker compose up -d
docker compose exec odoo odoo -d supplier_compare -i purchase_supplier_compare --with-demo --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Open `http://localhost:8069` (user `admin`, password `admin`), then Purchase,
Requests for Quotation. `--with-demo` loads the screenshots' example: an RFQ
to Distribuidora Andina whose banner points to Aceros Chachani, 586.05
cheaper with extra costs. Drop the flag for an empty database and add your
own vendor prices (product, Purchase tab) and extra costs (vendor, Sales &
Purchase tab).

## Running the tests

```bash
docker compose exec odoo odoo -d supplier_compare_test -i purchase_supplier_compare --test-enable --test-tags /purchase_supplier_compare --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

CI runs them on every push against the stock `odoo:19` image, once without
and once with demo data.

## Scope

Deliberately out of scope: taxes (the comparison is untaxed, as vendor prices
are), splitting one order across several vendors, landed-cost accounting on
receipts (`stock_landed_costs` does that after the purchase; this helps
choose before it), and extra costs that depend on weight or distance.
