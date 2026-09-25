from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_payment_prices")
class TestPaymentPrices(TransactionCase):
    def _set_discount(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "shop_config.cash_discount_percent", value
        )

    def _product(self, **values):
        return self.env["product.template"].create({
            "name": "Producto precios", "list_price": 100000.0, **values,
        })

    def test_cash_price_applies_global_discount_to_list_price(self):
        self._set_discount("10")
        product = self._product()
        self.assertEqual(product.card_price, 100000.0)
        self.assertEqual(product.cash_price, 90000.0)

    def test_cash_discount_stacks_on_active_offer(self):
        self._set_discount("10")
        product = self._product(offer_active=True, offer_price=80000.0)
        self.assertEqual(product.card_price, 80000.0)
        self.assertEqual(product.cash_price, 72000.0)

    def test_inactive_offer_is_ignored(self):
        self._set_discount("10")
        product = self._product(offer_active=False, offer_price=80000.0)
        self.assertEqual(product.card_price, 100000.0)

    def test_without_discount_cash_equals_card(self):
        self._set_discount("0")
        product = self._product()
        self.assertEqual(product.cash_price, product.card_price)

    def test_invalid_parameter_means_no_discount(self):
        self._set_discount("abc")
        self.assertEqual(self._product().cash_price, 100000.0)

    def test_pos_config_exposes_discount(self):
        self._set_discount("12.5")
        config = self.env["pos.config"].search([], limit=1)
        if config:
            self.assertEqual(config.shop_cash_discount_percent, 12.5)
