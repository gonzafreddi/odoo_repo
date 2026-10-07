from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_product_margins")
class TestProductMargins(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.template"]
        cls.normal = cls.Product.create({"name": "Margen normal", "sale_ok": True, "standard_price": 60, "list_price": 100})
        cls.offer = cls.Product.create({"name": "Margen con oferta", "sale_ok": True, "standard_price": 60, "list_price": 100, "offer_active": True, "offer_price": 80})
        cls.no_cost = cls.Product.create({"name": "Sin costo margen", "sale_ok": True, "standard_price": 0, "list_price": 100})
        cls.negative = cls.Product.create({"name": "Margen negativo", "sale_ok": True, "standard_price": 120, "list_price": 100})
        cls.not_sellable = cls.Product.create({"name": "No vendible margen", "sale_ok": False, "standard_price": 1, "list_price": 10})
        cls.component = cls.env["product.product"].create({"name": "Componente combo margen", "standard_price": 35})
        line = cls.env["product.combo"].create({
            "name": "Opción margen", "qty_max": 1,
            "combo_item_ids": [Command.create({"product_id": cls.component.id})],
        })
        cls.combo = cls.Product.create({"name": "Combo margen", "type": "combo", "list_price": 100, "combo_ids": [Command.set([line.id])]})

    def test_returns_effective_prices_costs_and_summary(self):
        result = self.env["shop.product.margin"].get_margin_data()
        rows = {row["id"]: row for row in result["rows"]}
        self.assertNotIn(self.not_sellable.id, rows)
        self.assertEqual(rows[self.normal.id]["price"], 100)
        self.assertAlmostEqual(rows[self.normal.id]["profit"], 40)
        self.assertAlmostEqual(rows[self.normal.id]["margin"], 0.4)
        self.assertEqual(rows[self.offer.id]["list_price"], 100)
        self.assertEqual(rows[self.offer.id]["price"], 80)
        self.assertAlmostEqual(rows[self.offer.id]["margin"], 0.25)
        self.assertFalse(rows[self.no_cost.id]["has_cost"])
        self.assertEqual(rows[self.combo.id]["cost"], 35)
        self.assertTrue(rows[self.combo.id]["is_combo"])
        self.assertGreaterEqual(result["summary"]["no_cost_count"], 1)
        self.assertGreaterEqual(result["summary"]["negative_count"], 1)

    def test_denies_users_without_allowed_groups(self):
        user = self.env["res.users"].create({
            "name": "Usuario sin permisos de margen", "login": "margin_no_access",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self.env["shop.product.margin"].with_user(user).get_margin_data()
