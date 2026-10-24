from datetime import timedelta

from odoo import Command
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
        combo_line = cls.env["product.combo"].create({
            "name": "Elegí proteína",
            "combo_item_ids": [Command.create({"product_id": cls.product.id})],
        })
        cls.combo = cls.env["product.product"].create({
            "name": "Combo test cupón",
            "type": "combo",
            "list_price": 5000.0,
            "taxes_id": [(6, 0, [])],
            "combo_ids": [Command.set([combo_line.id])],
        })

    def _order(self, email="buyer@example.com", code=None, qty=10, price=1000.0,
               combos=0):
        lines = [(0, 0, {
            "product_id": self.product.id,
            "product_uom_qty": qty,
            "price_unit": price,
            "tax_ids": [(6, 0, [])],
        })] if qty else []
        if combos:
            # Como lo arma la web: el combo con su precio y los componentes en $0.
            lines += [(0, 0, {
                "product_id": self.combo.id,
                "product_uom_qty": combos,
                "price_unit": 5000.0,
                "tax_ids": [(6, 0, [])],
            }), (0, 0, {
                "product_id": self.product.id,
                "name": "Combo test cupón - Elegí proteína",
                "product_uom_qty": combos,
                "price_unit": 0.0,
                "tax_ids": [(6, 0, [])],
            })]
        vals = {
            "partner_id": self.partner.id,
            "x_web_customer_email": email,
            "order_line": lines,
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

    def _backdate(self, records, days):
        self.env.cr.execute(
            f"UPDATE {records._table} SET create_date = create_date - interval '%s days' "
            "WHERE id IN %s", [days, tuple(records.ids)],
        )
        records.invalidate_recordset(["create_date"])

    def test_usage_resets_every_n_days_and_keeps_history(self):
        coupon = self.Coupon.create({"name": "Mensual", "code": "MENSUAL",
                                     "discount_value": 10, "usage_per_customer": 1,
                                     "usage_limit": 1, "usage_reset_days": 30})
        first = self._order(email="a@example.com", code="MENSUAL")
        with self.assertRaisesRegex(ValidationError, "ya fue utilizado"):
            self._order(email="b@example.com", code="MENSUAL")
        # 31 días después arranca otro ciclo.
        self._backdate(coupon, 31)
        self._backdate(coupon.redemption_ids, 31)
        coupon.invalidate_recordset()
        self.assertEqual(coupon.used_count, 0)
        self.assertEqual(coupon.status, "active")
        second = self._order(email="a@example.com", code="MENSUAL")
        coupon.invalidate_recordset()
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(coupon.total_used_count, 2)
        self.assertEqual(coupon.redemption_ids.order_id, first | second)
        old = coupon.redemption_ids.filtered(lambda r: r.order_id == first)
        self.assertFalse(old.in_current_period)
        self.assertTrue(coupon.next_reset_at > coupon.period_start)

    def test_manual_reset_reenables_customers(self):
        coupon = self.Coupon.create({"name": "DIAMADRE", "code": "DIAMADRE",
                                     "discount_value": 10, "usage_per_customer": 1})
        self._order(email="a@example.com", code="DIAMADRE")
        with self.assertRaisesRegex(ValidationError, "Ya usaste"):
            self._order(email="a@example.com", code="DIAMADRE")
        self._backdate(coupon.redemption_ids, 1)
        coupon.action_reset_usage()
        self.assertTrue(self.Coupon.shop_check_coupon("DIAMADRE", "a@example.com", 5000)["valid"])
        self._order(email="a@example.com", code="DIAMADRE")
        coupon.invalidate_recordset()
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(coupon.total_used_count, 2)

    def test_coupon_excludes_combos_by_default(self):
        self.Coupon.create({"name": "Sin combos", "code": "SINCOMBOS",
                            "discount_value": 10, "usage_per_customer": 0})
        # 10 × 1000 sueltos + 1 combo de 5000: descuenta 10 % sólo de los 10000.
        order = self._order(code="SINCOMBOS", combos=1)
        self.assertEqual(order.x_web_coupon_discount, 1000.0)
        self.assertEqual(order.amount_total, 14000.0)
        combo_line = order.order_line.filtered(lambda l: l.product_id == self.combo)
        self.assertFalse(combo_line.discount)
        check = self.Coupon.shop_check_coupon("SINCOMBOS", "x@example.com", 15000, 5000)
        self.assertEqual(check["discount_amount"], 1000.0)
        self.assertFalse(check["apply_to_combos"])
        # Sólo combos en el carrito: no aplica.
        check = self.Coupon.shop_check_coupon("SINCOMBOS", "x@example.com", 5000, 5000)
        self.assertFalse(check["valid"])
        self.assertIn("combos", check["message"])
        with self.assertRaisesRegex(ValidationError, "no aplica a combos"):
            self._order(code="SINCOMBOS", qty=0, combos=1)

    def test_coupon_minimum_ignores_combos(self):
        self.Coupon.create({"name": "Mínimo", "code": "MINIMO", "discount_value": 10,
                            "min_amount": 8000, "usage_per_customer": 0})
        check = self.Coupon.shop_check_coupon("MINIMO", "x@example.com", 12000, 5000)
        self.assertFalse(check["valid"])
        with self.assertRaisesRegex(ValidationError, "compra mínima"):
            self._order(code="MINIMO", qty=7, combos=1)

    def test_coupon_can_include_combos(self):
        self.Coupon.create({"name": "Con combos", "code": "CONCOMBOS",
                            "discount_value": 10, "apply_to_combos": True})
        order = self._order(code="CONCOMBOS", combos=1)
        self.assertEqual(order.x_web_coupon_discount, 1500.0)
        check = self.Coupon.shop_check_coupon("CONCOMBOS", "x@example.com", 15000, 5000)
        self.assertEqual(check["discount_amount"], 1500.0)

    def test_post_purchase_coupon_follows_combo_setting(self):
        self._set_post_purchase()
        order = self._order()
        order.action_confirm()
        self.assertFalse(order.x_generated_coupon_ids.apply_to_combos)
        self._set_post_purchase(apply_to_combos="True")
        order = self._order(email="other@example.com")
        order.action_confirm()
        self.assertTrue(order.x_generated_coupon_ids.apply_to_combos)

    def test_executive_dashboard_counts_coupon_usage(self):
        self.Coupon.create({"name": "Día de la Madre", "code": "TABLERO15",
                            "discount_value": 15})
        self._set_post_purchase()
        first = self._order(email="a@example.com", code="TABLERO15")
        second = self._order(email="b@example.com", code="TABLERO15", qty=2)
        plain = self._order(email="c@example.com")
        (first | second | plain).action_confirm()
        generated = first.x_generated_coupon_ids
        with_generated = self._order(email="a@example.com", code=generated.code, qty=5)
        with_generated.action_confirm()
        draft = self._order(email="d@example.com", code="TABLERO15")
        orders = first | second | plain | with_generated | draft
        # Período aislado de los datos que ya tenga la base.
        orders.write({"date_order": "2099-05-10 12:00:00"})

        data = self.env["shop.executive.dashboard"].get_dashboard_data(
            "2099-05-10", "2099-05-10"
        )
        coupons = data["coupons"]
        # El borrador no cuenta: el tablero solo mira ventas confirmadas.
        self.assertEqual(coupons["count"], 3)
        self.assertAlmostEqual(coupons["discount"], 1500.0 + 300.0 + 500.0)
        self.assertAlmostEqual(coupons["sales"], 8500.0 + 1700.0 + 4500.0)
        self.assertAlmostEqual(coupons["order_share"], 75.0)
        by_code = {row["code"]: row for row in coupons["by_coupon"]}
        self.assertEqual(by_code["TABLERO15"]["count"], 2)
        self.assertAlmostEqual(by_code["TABLERO15"]["discount"], 1800.0)
        self.assertEqual(by_code["Post-compra"]["count"], 1)
        self.assertAlmostEqual(by_code["Post-compra"]["discount"], 500.0)
        self.assertEqual(
            set(data["record_ids"]["coupon_orders"]),
            set((first | second | with_generated).ids),
        )
        self.assertNotIn("order_ids", coupons)
