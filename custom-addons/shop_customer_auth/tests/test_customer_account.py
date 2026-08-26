from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_customer_account")
class TestCustomerAccount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente CC"})
        cls.env.user.group_ids |= cls.env.ref(
            "shop_customer_auth.group_customer_account_manager"
        )
        cls.Move = cls.env["shop.customer.account.move"]
        cls.base_vals = {
            "partner_id": cls.partner.id,
            "company_id": cls.env.company.id,
            "currency_id": cls.env.company.currency_id.id,
            "user_id": cls.env.user.id,
        }

    def _move(self, move_type, amount, **extra):
        return self.Move.with_context(customer_account_pos_sync=True).create({
            **self.base_vals,
            "move_type": move_type,
            "amount": amount,
            **extra,
        })

    def test_balance_payments_and_overpayment(self):
        self._move("sale", 50000)
        self._move("sale", 20000)
        self._move("payment", 30000)
        self.assertEqual(self.partner.current_account_balance, 40000)
        self._move("payment", 60000)
        self.assertEqual(self.partner.current_account_balance, -20000)

    def test_cancelled_move_does_not_affect_balance(self):
        move = self._move("sale", 50000)
        self.assertEqual(self.partner.current_account_balance, 50000)
        move.action_cancel()
        self.assertEqual(self.partner.current_account_balance, 0)

    def test_running_balance_uses_date_then_id(self):
        first = self._move("sale", 50, date="2026-08-01")
        second = self._move("payment", 20, date="2026-08-01")
        third = self._move("sale", 15, date="2026-08-02")
        self.assertEqual(first.running_balance, 50)
        self.assertEqual(second.running_balance, 30)
        self.assertEqual(third.running_balance, 45)

    def test_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._move("sale", 0)

    def test_manual_sale_is_rejected(self):
        with self.assertRaises(AccessError):
            self.Move.create({**self.base_vals, "move_type": "sale", "amount": 10})

    def test_company_balances_are_isolated(self):
        company_2 = self.env["res.company"].create({"name": "Otra compañía"})
        self._move("sale", 100)
        self.Move.with_company(company_2).with_context(
            customer_account_pos_sync=True
        ).create({
            **self.base_vals,
            "company_id": company_2.id,
            "currency_id": company_2.currency_id.id,
            "move_type": "sale",
            "amount": 40,
        })
        self.assertEqual(self.partner.with_company(self.env.company).current_account_balance, 100)
        self.assertEqual(self.partner.with_company(company_2).current_account_balance, 40)

    def test_pos_asset_bundle_compiles(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle(
            "point_of_sale._assets_pos", css=True, js=True
        )
        self.assertTrue(bundle.js())
        self.assertTrue(bundle.css())
