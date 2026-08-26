from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_sale_payment")
class TestSaleOrderPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente web"})
        cls.product = cls.env["product.product"].create({
            "name": "Producto web", "type": "service", "list_price": 100.0,
        })
        cls.cash = cls.env["shop.sale.payment.method"].create({
            "name": "Efectivo web", "company_id": cls.env.company.id,
        })
        cls.transfer = cls.env["shop.sale.payment.method"].create({
            "name": "Transferencia web", "company_id": cls.env.company.id,
            "reference_required": True,
        })

    def _order(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": 1,
                "price_unit": 100.0,
            })],
        })
        order.action_confirm()
        return order

    def _register(self, order, amount, method=None, reference=None):
        action = order.action_validate_payment()
        self.assertEqual(action["res_model"], "shop.sale.payment.register.wizard")
        wizard = self.env[action["res_model"]].with_context(action["context"]).create({
            "payment_method_id": (method or self.cash).id,
            "amount": amount, "reference": reference,
        })
        return wizard.action_confirm()

    def test_full_payment_marks_order_paid(self):
        order = self._order()
        self._register(order, 100.0)
        self.assertEqual(order.web_payment_state, "paid")
        self.assertEqual(order.web_amount_paid, 100.0)
        self.assertEqual(order.web_amount_due, 0.0)

    def test_partial_payment_keeps_remaining_balance(self):
        order = self._order()
        self._register(order, 40.0)
        self.assertEqual(order.web_payment_state, "partial")
        self.assertEqual(order.web_amount_paid, 40.0)
        self.assertEqual(order.web_amount_due, 60.0)

    def test_split_payment_accepts_multiple_methods(self):
        order = self._order()
        self._register(order, 25.0)
        self._register(order, 75.0, self.transfer, "TRX-001")
        self.assertEqual(order.web_payment_state, "paid")
        self.assertEqual(
            order.web_payment_ids.mapped("payment_method_id"),
            self.cash | self.transfer,
        )

    def test_payment_cannot_exceed_remaining_balance(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            self._register(order, 100.01)

    def test_payment_amount_must_be_positive(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            self._register(order, 0.0)

    def test_required_reference_is_enforced(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            self._register(order, 100.0, self.transfer)

    def test_cancelling_payment_reopens_balance_and_keeps_audit_record(self):
        order = self._order()
        self._register(order, 100.0)
        payment = order.web_payment_ids
        payment.action_cancel()
        self.assertEqual(payment.state, "cancelled")
        self.assertEqual(order.web_payment_state, "not_paid")
        self.assertEqual(order.web_amount_due, 100.0)
        with self.assertRaises(UserError):
            payment.unlink()

    def test_confirmed_payment_cannot_be_modified(self):
        order = self._order()
        self._register(order, 100.0)
        with self.assertRaises(UserError):
            order.web_payment_ids.write({"amount": 50.0})

    def test_historical_confirmed_order_without_custom_payments_is_pending(self):
        order = self._order()
        self.assertEqual(order.web_payment_state, "not_paid")
        self.assertEqual(order.web_amount_paid, 0.0)
        self.assertEqual(order.web_amount_due, 100.0)

    def test_payment_action_is_only_available_for_confirmed_orders(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        with self.assertRaises(UserError):
            order.action_validate_payment()

    def test_wizard_defaults_to_remaining_balance(self):
        order = self._order()
        self._register(order, 35.0)
        action = order.action_validate_payment()
        wizard = self.env[action["res_model"]].with_context(action["context"]).create({
            "payment_method_id": self.cash.id,
        })
        self.assertEqual(wizard.amount, 65.0)

    def test_sale_order_lists_expose_payment_state_filters(self):
        list_view = self.env.ref(
            "shop_customer_auth.sale_order_list_web_payment",
            raise_if_not_found=False,
        )
        search_view = self.env.ref(
            "shop_customer_auth.sale_order_search_web_payment",
            raise_if_not_found=False,
        )
        self.assertTrue(list_view, "Falta la columna Estado de cobro")
        self.assertTrue(search_view, "Faltan los filtros de estado de cobro")

        list_arch = list_view._get_combined_arch()
        self.assertTrue(list_arch.xpath(
            "//field[@name='web_payment_state' and @widget='badge']"
        ))

        search_arch = search_view._get_combined_arch()
        for filter_name in (
            "web_payment_not_paid",
            "web_payment_partial",
            "web_payment_paid",
            "group_by_web_payment_state",
        ):
            self.assertTrue(search_arch.xpath(
                f"//filter[@name='{filter_name}']"
            ), f"Falta el filtro {filter_name}")
