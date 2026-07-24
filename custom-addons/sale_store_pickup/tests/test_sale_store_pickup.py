from odoo.exceptions import ValidationError
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
        self.assertEqual(order.x_logistics_status, "pending")

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

    def test_shipping_data_is_stored_on_sale_order(self):
        state = self.env["res.country.state"].search([], limit=1)
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "x_shipping_phone": "3515551234",
            "x_shipping_street": "San Martín",
            "x_shipping_street_number": "123",
            "x_shipping_floor_apartment": "2 B",
            "x_shipping_city": "Córdoba",
            "x_shipping_state_id": state.id,
            "x_shipping_zip": "5000",
            "x_shipping_notes": "Portón negro",
            "x_shipping_real_cost": 8500.0,
        })

        self.assertEqual(order.x_shipping_city, "Córdoba")
        self.assertEqual(order.x_shipping_state_id, state)
        self.assertEqual(order.x_shipping_real_cost, 8500.0)
        self.assertTrue(self.env["sale.order"]._fields["x_shipping_city"].index)
        self.assertTrue(
            self.env["sale.order"]._fields["x_shipping_state_id"].index
        )

        order.x_logistics_status = "preparing"
        self.assertEqual(order.x_logistics_status, "preparing")

        with self.assertRaises(ValidationError):
            order.x_logistics_status = "ready_pickup"

    def test_pickup_rejects_shipped_status(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "x_is_store_pickup": True,
        })

        order.x_logistics_status = "ready_pickup"
        self.assertEqual(order.x_logistics_status, "ready_pickup")
        with self.assertRaises(ValidationError):
            order.x_logistics_status = "shipped"
