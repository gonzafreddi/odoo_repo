from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestSaleStorePickup(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Store pickup customer"})
        cls.sales_user = new_test_user(
            cls.env,
            login="store_pickup_sales_user",
            groups="sales_team.group_sale_salesman",
        )

    def test_field_contract_and_default(self):
        field_info = self.env["sale.order"].fields_get(
            ["x_is_store_pickup"],
            ["type", "string", "required", "readonly"],
        )["x_is_store_pickup"]

        self.assertEqual(field_info["type"], "boolean")
        self.assertEqual(field_info["string"], "Retiro en local")
        self.assertFalse(field_info["required"])
        self.assertFalse(field_info["readonly"])
        self.assertTrue(self.env["sale.order"]._fields["x_is_store_pickup"].store)
        self.assertTrue(self.env["sale.order"]._fields["x_is_store_pickup"].index)

        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertFalse(order.x_is_store_pickup)

    def test_create_and_search_as_xmlrpc_sales_user(self):
        SaleOrder = self.env["sale.order"].with_user(self.sales_user)
        pickup_order = SaleOrder.create({
            "partner_id": self.partner.id,
            "x_is_store_pickup": True,
        })
        delivery_order = SaleOrder.create({
            "partner_id": self.partner.id,
            "x_is_store_pickup": False,
        })

        self.assertTrue(pickup_order.x_is_store_pickup)
        self.assertFalse(delivery_order.x_is_store_pickup)
        delivery_order.write({"x_is_store_pickup": True})
        self.assertTrue(delivery_order.x_is_store_pickup)
        delivery_order.write({"x_is_store_pickup": False})
        self.assertIn(
            "x_is_store_pickup",
            SaleOrder.fields_get(["x_is_store_pickup"]),
        )

        pickups = SaleOrder.search([
            ("id", "in", (pickup_order.id, delivery_order.id)),
            ("x_is_store_pickup", "=", True),
        ])
        self.assertEqual(pickups, pickup_order)
