from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "shop_customer_account")
class TestCustomerAccountPos(TestPoSCommon):
    def setUp(self):
        super().setUp()
        self.env.user.group_ids |= self.env.ref(
            "shop_customer_auth.group_customer_account_manager"
        )
        self.config = self.basic_config
        self.cc_payment_method = self.bank_pm1
        self.cc_payment_method.is_customer_account = True
        self.customer = self.env["res.partner"].create({"name": "Cliente POS CC"})
        self.product = self.create_product(
            "Producto CC", self.categ_basic, 100.0, 50.0
        )
        self.open_new_session()

    def _sync(self, cc_amount, cash_amount=0, customer=None, uuid=None, quantity=1):
        payments = []
        if cash_amount:
            payments.append((self.cash_pm1, cash_amount))
        if cc_amount:
            payments.append((self.cc_payment_method, cc_amount))
        data = self.create_ui_order_data(
            [(self.product, quantity)],
            payments=payments,
            customer=customer,
            uuid=uuid,
        )
        return data, self.env["pos.order"].sync_from_ui([data])

    def test_mixed_payment_creates_only_cc_amount(self):
        self._sync(60, cash_amount=40, customer=self.customer)
        move = self.env["shop.customer.account.move"].search([
            ("partner_id", "=", self.customer.id),
        ])
        self.assertEqual(len(move), 1)
        self.assertEqual(move.move_type, "sale")
        self.assertEqual(move.amount, 60)

    def test_customer_is_required_on_backend(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self._sync(100)

    def test_same_order_retry_is_idempotent(self):
        uuid = self.create_random_uid()
        data, _result = self._sync(100, customer=self.customer, uuid=uuid)
        self.env["pos.order"].sync_from_ui([data])
        moves = self.env["shop.customer.account.move"].search([
            ("partner_id", "=", self.customer.id),
            ("move_type", "=", "sale"),
        ])
        self.assertEqual(len(moves), 1)

    def test_credit_limit_is_enforced(self):
        self.customer.credit_limit = 500
        self.env["shop.customer.account.move"].with_context(
            customer_account_pos_sync=True
        ).create({
            "partner_id": self.customer.id,
            "move_type": "sale",
            "amount": 450,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
        })
        with self.assertRaisesRegex(ValidationError, "Límite de crédito excedido"), self.env.cr.savepoint():
            self._sync(60, cash_amount=40, customer=self.customer)
        self._sync(40, cash_amount=60, customer=self.customer)
        self.assertEqual(self.customer.current_account_balance, 490)

    def test_refund_cc_reduces_debt(self):
        self._sync(100, customer=self.customer)
        self._sync(-30, customer=self.customer, quantity=-0.3)
        moves = self.env["shop.customer.account.move"].search([
            ("partner_id", "=", self.customer.id),
        ], order="id")
        self.assertEqual(moves.mapped("move_type"), ["sale", "credit_adjustment"])
        self.assertEqual(self.customer.current_account_balance, 70)
