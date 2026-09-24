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
                "price_unit": 100.0, "tax_ids": [Command.set([])],
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

    def test_mercadopago_rpc_creates_payment(self):
        order = self._order()
        result = self.env["sale.order"].shop_register_online_payment(
            order.id, "mercadopago", 12345, 100.0, order.currency_id.name,
        )
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["payment_id"], order.web_payment_ids.id)
        self.assertEqual(order.web_payment_ids.reference, "12345")
        self.assertEqual(order.web_payment_ids.provider_payment_ref, "mercadopago:12345")
        self.assertEqual(order.web_payment_state, "paid")

    def test_mercadopago_rpc_is_idempotent(self):
        order = self._order()
        model = self.env["sale.order"]
        result1 = model.shop_register_online_payment(
            order.id, "mercadopago", "mp-duplicate", 100.0, order.currency_id.name,
        )
        result2 = model.shop_register_online_payment(
            order.id, "mercadopago", "mp-duplicate", 100.0, order.currency_id.name,
        )
        self.assertEqual(result1["status"], "created")
        self.assertEqual(result2["status"], "already_registered")
        self.assertEqual(result1["payment_id"], result2["payment_id"])
        self.assertEqual(len(order.web_payment_ids), 1)

    def test_manual_payments_can_reuse_reference_across_orders(self):
        order1 = self._order()
        order2 = self._order()
        self._register(order1, 100.0, self.transfer, "transf")
        self._register(order2, 100.0, self.transfer, "transf")
        self.assertEqual(len(order1.web_payment_ids | order2.web_payment_ids), 2)

    def test_mercadopago_reuses_existing_method_and_reactivates_it(self):
        method = self.env["shop.sale.payment.method"].create({
            "name": "Mercado Pago", "company_id": self.env.company.id,
            "active": False,
        })
        order = self._order()
        result = self.env["sale.order"].shop_register_online_payment(
            order.id, "mercadopago", "existing-method", 100.0,
            order.currency_id.name,
        )
        self.assertEqual(result["status"], "created")
        self.assertEqual(order.web_payment_ids.payment_method_id, method)
        self.assertTrue(method.active)

    def test_mercadopago_creates_method_when_missing(self):
        order = self._order()
        result = self.env["sale.order"].shop_register_online_payment(
            order.id, "mercadopago", "new-method", 100.0,
            order.currency_id.name,
        )
        self.assertEqual(result["status"], "created")
        method = order.web_payment_ids.payment_method_id
        self.assertEqual(method.name, "Mercado Pago")
        self.assertTrue(method.reference_required)
        self.assertEqual(method.sequence, 50)

    def test_mercadopago_rpc_rejects_amount_and_currency_mismatches(self):
        order = self._order()
        model = self.env["sale.order"]
        self.assertEqual(model.shop_register_online_payment(
            order.id, "mercadopago", "mp-amount", 99.0, order.currency_id.name,
        )["reason"], "amount_mismatch")
        other_currency = self.env["res.currency"].search([
            ("id", "!=", order.currency_id.id), ("active", "=", True),
        ], limit=1)
        if other_currency:
            self.assertEqual(model.shop_register_online_payment(
                order.id, "mercadopago", "mp-currency", 100.0, other_currency.name,
            )["reason"], "currency_mismatch")

    def test_mercadopago_rpc_rejects_unconfirmed_paid_and_missing_orders(self):
        model = self.env["sale.order"]
        draft = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(model.shop_register_online_payment(
            draft.id, "mercadopago", "mp-draft", 100.0, draft.currency_id.name,
        )["reason"], "order_not_confirmed")
        order = self._order()
        self._register(order, 100.0)
        self.assertEqual(model.shop_register_online_payment(
            order.id, "mercadopago", "mp-paid", 100.0, order.currency_id.name,
        )["reason"], "already_paid")
        self.assertEqual(model.shop_register_online_payment(
            999999999, "mercadopago", "mp-missing", 1.0, order.currency_id.name,
        )["reason"], "order_not_found")

    def test_payment_status_rpc_returns_snapshot(self):
        order = self._order()
        status = self.env["sale.order"].shop_get_payment_status(order.id)
        self.assertTrue(status["found"])
        self.assertEqual(status["order_id"], order.id)
        self.assertEqual(status["state"], "sale")
        self.assertEqual(status["web_payment_state"], "not_paid")
        self.assertEqual(status["currency_code"], order.currency_id.name)
        self.assertFalse(self.env["sale.order"].shop_get_payment_status(999999999)["found"])

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
