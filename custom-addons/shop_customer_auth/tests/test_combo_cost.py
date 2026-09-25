from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_combo_cost")
class TestComboCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        cls.protein_vanilla = Product.create({
            "name": "Proteína vainilla", "type": "consu", "standard_price": 30.0,
        })
        cls.protein_cookies = Product.create({
            "name": "Proteína cookies", "type": "consu", "standard_price": 35.0,
        })
        cls.creatine = Product.create({
            "name": "Creatina", "type": "consu", "standard_price": 10.0,
        })
        cls.protein_line = cls.env["product.combo"].create({
            "name": "Elegí proteína",
            "qty_max": 1,
            "combo_item_ids": [
                Command.create({"product_id": cls.protein_vanilla.id}),
                Command.create({"product_id": cls.protein_cookies.id}),
            ],
        })
        cls.creatine_line = cls.env["product.combo"].create({
            "name": "Elegí 2 creatinas",
            "qty_max": 2,
            "combo_item_ids": [Command.create({"product_id": cls.creatine.id})],
        })
        cls.combo = cls.env["product.template"].create({
            "name": "Combo test",
            "type": "combo",
            "list_price": 100.0,
            "combo_ids": [Command.set([cls.protein_line.id, cls.creatine_line.id])],
        })

    def test_combo_cost_sums_most_expensive_option_times_quantity(self):
        # 35 (opción más cara) + 2 × 10
        self.assertAlmostEqual(self.combo.combo_cost, 55.0)
        self.assertAlmostEqual(self.combo.margin_percentage, 0.45)
        self.assertEqual(self.combo.standard_price, 0.0)

    def test_combo_cost_follows_component_cost_changes(self):
        self.creatine.standard_price = 15.0
        self.combo.invalidate_recordset(["combo_cost"])
        self.assertAlmostEqual(self.combo.combo_cost, 65.0)

    def test_regular_products_have_no_combo_cost(self):
        self.assertEqual(self.creatine.product_tmpl_id.combo_cost, 0.0)

    def test_dashboard_assigns_web_component_costs_to_the_combo(self):
        combo_variant = self.combo.product_variant_id
        order = self.env["sale.order"].create({
            "partner_id": self.env["res.partner"].create({"name": "Cliente combo"}).id,
            "date_order": fields.Datetime.to_datetime("2099-05-10 12:00:00"),
            "order_line": [
                Command.create({
                    "product_id": combo_variant.id,
                    "name": "Combo test (Elegí proteína: Proteína cookies)",
                    "product_uom_qty": 1, "price_unit": 100.0,
                }),
                Command.create({
                    "product_id": self.protein_cookies.id,
                    "name": "Combo test - Elegí proteína: Proteína cookies",
                    "product_uom_qty": 1, "price_unit": 0.0,
                    "tax_ids": [Command.set([])],
                }),
                Command.create({
                    "product_id": self.creatine.id,
                    "name": "Combo test - Elegí 2 creatinas: Creatina",
                    "product_uom_qty": 2, "price_unit": 0.0,
                    "tax_ids": [Command.set([])],
                }),
                Command.create({
                    "product_id": self.creatine.id,
                    "name": "Creatina",
                    "product_uom_qty": 1, "price_unit": 20.0,
                    "tax_ids": [Command.set([])],
                }),
            ],
        })
        order.action_confirm()
        order.date_order = fields.Datetime.to_datetime("2099-05-10 12:00:00")
        sales = self.env["shop.executive.dashboard"]._sales_data(
            fields.Date.to_date("2099-05-10"), fields.Date.to_date("2099-05-10")
        )
        by_id = {key[0]: values for key, values in sales["by_product"].items()}
        self.assertAlmostEqual(by_id[combo_variant.id]["cost"], 55.0)
        self.assertAlmostEqual(by_id[self.protein_cookies.id]["cost"], 0.0)
        # La creatina suelta conserva su costo; la del combo pasa al combo.
        self.assertAlmostEqual(by_id[self.creatine.id]["cost"], 10.0)
        self.assertAlmostEqual(sales["cost"], 65.0)
