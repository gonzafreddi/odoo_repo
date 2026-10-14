from datetime import timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.shop_coupon import PARAM_PREFIX, store_today


@tagged("post_install", "-at_install", "shop_coupons")
class TestShopCoupon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Comprador cupón"})
        cls.product = cls.env["product.product"].create({
            "name": "Proteína test cupón",
            "list_price": 1000.0,
            "taxes_id": [(6, 0, [])],
        })
        cls.Coupon = cls.env["shop.coupon"]

    def _order(self, email="buyer@example.com", code=None, qty=10, price=1000.0):
        vals = {
            "partner_id": self.partner.id,
            "x_web_customer_email": email,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "price_unit": price,
                "tax_ids": [(6, 0, [])],
            })],
        }
        if code:
            vals["x_web_coupon_code"] = code
        return self.env["sale.order"].create(vals)

    def _set_post_purchase(self, **values):
        params = self.env["ir.config_parameter"].sudo()
        defaults = {"enabled": "True", "discount_type": "percent",
                    "discount_value": "10", "validity_days": "30"}
        for key, value in {**defaults, **values}.items():
            params.set_param(PARAM_PREFIX + key, value)

    def test_percent_coupon_discounts_product_lines(self):
        self.Coupon.create({"name": "Día de la Madre", "code": "diamadre",
                            "discount_value": 15})
        order = self._order(code=" DiaMadre ")
        self.assertEqual(order.amount_total, 8500.0)
        self.assertEqual(order.x_web_coupon_id.code, "DIAMADRE")
        self.assertEqual(order.x_web_coupon_discount, 1500.0)

    def test_fixed_coupon_with_cap_to_order_amount(self):
        self.Coupon.create({"name": "Fijo", "code": "FIJO2000",
                            "discount_type": "fixed", "discount_value": 2000})
        order = self._order(code="FIJO2000")
        self.assertAlmostEqual(order.amount_total, 8000.0, delta=1)

    def test_percent_cap(self):
        self.Coupon.create({"name": "Tope", "code": "TOPE", "discount_value": 50,
                            "max_discount_amount": 1000})
        order = self._order(code="TOPE")
        self.assertAlmostEqual(order.amount_total, 9000.0, delta=1)

    def test_one_use_per_customer_but_open_to_everyone(self):
        self.Coupon.create({"name": "Día de la Madre", "code": "DIAMADRE",
                            "discount_value": 10, "usage_per_customer": 1})
        self._order(email="a@example.com", code="DIAMADRE")
        self._order(email="b@example.com", code="DIAMADRE")
        with self.assertRaisesRegex(ValidationError, "Ya usaste"):
            self._order(email="A@example.com", code="DIAMADRE")
        check = self.Coupon.shop_check_coupon("diamadre", "a@example.com", 5000)
        self.assertFalse(check["valid"])
        check = self.Coupon.shop_check_coupon("diamadre", "c@example.com", 5000)
        self.assertTrue(check["valid"])
        self.assertEqual(check["discount_amount"], 500.0)

    def test_invalid_coupons_are_rejected(self):
        today = store_today()
        self.Coupon.create({"name": "Vencido", "code": "VENCIDO", "discount_value": 10,
                            "date_to": today - timedelta(days=1)})
        self.Coupon.create({"name": "Mínimo", "code": "MINIMO", "discount_value": 10,
                            "min_amount": 50000})
        self.Coupon.create({"name": "Personal", "code": "PERSONAL", "discount_value": 10,
                            "restricted_email": "Otro@Example.com"})
        with self.assertRaisesRegex(ValidationError, "no existe"):
            self._order(code="NOEXISTE")
        with self.assertRaisesRegex(ValidationError, "vencido"):
            self._order(code="VENCIDO")
        with self.assertRaisesRegex(ValidationError, "mínima"):
            self._order(code="MINIMO")
        with self.assertRaisesRegex(ValidationError, "personal"):
            self._order(code="PERSONAL")
        self.assertTrue(self._order(email="otro@example.com", code="PERSONAL"))

    def test_post_purchase_coupon_issued_on_confirm_and_single_use(self):
        self._set_post_purchase(min_amount="0", code_prefix="GRACIAS")
        order = self._order()
        order.action_confirm()
        coupon = order.x_generated_coupon_ids
        self.assertEqual(len(coupon), 1)
        self.assertTrue(coupon.code.startswith("GRACIAS"))
        self.assertEqual(coupon.restricted_email, "buyer@example.com")
        self.assertEqual(coupon.date_to, store_today() + timedelta(days=29))
        self.Coupon._issue_post_purchase(order)
        self.assertEqual(len(order.x_generated_coupon_ids), 1)

        payload = self.Coupon.shop_order_coupon_email(order.id)
        self.assertEqual(payload["code"], coupon.code)
        self.Coupon.shop_mark_coupon_emailed(coupon.id)
        self.assertFalse(self.Coupon.shop_order_coupon_email(order.id))

        # La compra con cupón también genera un cupón nuevo.
        second = self._order(code=coupon.code)
        second.action_confirm()
        self.assertEqual(second.amount_total, 9000.0)
        self.assertEqual(len(second.x_generated_coupon_ids), 1)
        self.assertNotEqual(second.x_generated_coupon_ids, coupon)
        with self.assertRaisesRegex(ValidationError, "ya fue utilizado"):
            self._order(code=coupon.code)

    def test_post_purchase_disabled_by_default(self):
        order = self._order()
        order.action_confirm()
        self.assertFalse(order.x_generated_coupon_ids)

    def test_cancel_releases_coupon_and_archives_generated_one(self):
        self._set_post_purchase()
        self.Coupon.create({"name": "Único", "code": "UNICO", "discount_value": 10,
                            "usage_limit": 1})
        order = self._order(code="UNICO")
        order.action_confirm()
        generated = order.x_generated_coupon_ids
        order._action_cancel()
        self.assertFalse(generated.active)
        self.assertTrue(self._order(email="other@example.com", code="UNICO"))
