from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_guest_checkout")
class TestGuestCheckout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente guest"})

    def _order(self, **values):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            **values,
        })

    def _auth(self, email, verified=True, active=True):
        partner = self.env["res.partner"].create({"name": email})
        return self.env["shop.customer.auth"].create({
            "partner_id": partner.id,
            "email": email,
            "password_hash": "x",
            "email_verified": verified,
            "active": active,
        })

    def test_checkout_key_is_unique_but_empty_keys_are_allowed(self):
        self._order(x_web_checkout_key="checkout-1")
        with self.assertRaises(Exception), self.cr.savepoint():
            self._order(x_web_checkout_key="checkout-1")
        self._order()
        self._order()

    def test_unverified_account_does_not_claim_orders(self):
        auth = self._auth("buyer@example.com", verified=False)
        order = self._order(
            x_web_guest=True,
            x_web_customer_email="buyer@example.com",
        )

        result = self.env["sale.order"].shop_claim_guest_orders(auth.id)

        self.assertEqual(result, {
            "status": "not_verified", "claimed": 0, "order_ids": [],
        })
        self.assertFalse(order.x_shop_auth_id)

    def test_verified_account_claims_only_matching_unclaimed_guest_orders_once(self):
        auth = self._auth("buyer@example.com")
        other_auth = self._auth("other@example.com")
        guest = self._order(
            x_web_guest=True,
            x_web_customer_email="buyer@example.com",
        )
        wrong_email = self._order(
            x_web_guest=True,
            x_web_customer_email="other@example.com",
        )
        not_guest = self._order(
            x_web_guest=False,
            x_web_customer_email="buyer@example.com",
        )
        already_claimed = self._order(
            x_web_guest=True,
            x_web_customer_email="buyer@example.com",
            x_shop_auth_id=other_auth.id,
        )

        model = self.env["sale.order"]
        result = model.shop_claim_guest_orders(auth.id)
        repeated = model.shop_claim_guest_orders(auth.id)

        self.assertEqual(result, {
            "status": "ok", "claimed": 1, "order_ids": [guest.id],
        })
        self.assertEqual(repeated, {"status": "ok", "claimed": 0, "order_ids": []})
        self.assertEqual(guest.x_shop_auth_id, auth)
        self.assertFalse(wrong_email.x_shop_auth_id)
        self.assertFalse(not_guest.x_shop_auth_id)
        self.assertEqual(already_claimed.x_shop_auth_id, other_auth)

    def test_inactive_account_cannot_claim_orders(self):
        auth = self._auth("inactive@example.com", active=False)
        order = self._order(
            x_web_guest=True,
            x_web_customer_email="inactive@example.com",
        )

        result = self.env["sale.order"].shop_claim_guest_orders(auth.id)

        self.assertEqual(result["status"], "not_verified")
        self.assertEqual(result["claimed"], 0)
        self.assertFalse(order.x_shop_auth_id)
