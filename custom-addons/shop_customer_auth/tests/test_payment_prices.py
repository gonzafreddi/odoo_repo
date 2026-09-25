from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_payment_prices")
class TestPaymentPrices(TransactionCase):
    def _set_surcharge(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            "shop_config.card_surcharge_percent", value
        )

    def _product(self, **values):
        return self.env["product.template"].create({
            "name": "Producto precios", "list_price": 100000.0, **values,
        })

    def test_card_price_adds_global_surcharge_to_list_price(self):
        self._set_surcharge("10")
        product = self._product()
        self.assertEqual(product.cash_price, 100000.0)
        self.assertAlmostEqual(product.card_price, 110000.0)

    def test_card_surcharge_stacks_on_active_offer(self):
        self._set_surcharge("10")
        product = self._product(offer_active=True, offer_price=80000.0)
        self.assertEqual(product.cash_price, 80000.0)
        self.assertAlmostEqual(product.card_price, 88000.0)

    def test_inactive_offer_is_ignored(self):
        self._set_surcharge("10")
        product = self._product(offer_active=False, offer_price=80000.0)
        self.assertEqual(product.cash_price, 100000.0)

    def test_without_surcharge_card_equals_cash(self):
        self._set_surcharge("0")
        product = self._product()
        self.assertEqual(product.card_price, product.cash_price)

    def test_invalid_parameter_means_no_surcharge(self):
        self._set_surcharge("abc")
        self.assertEqual(self._product().card_price, 100000.0)

    def test_pos_config_exposes_surcharge(self):
        self._set_surcharge("12.5")
        config = self.env["pos.config"].search([], limit=1)
        if config:
            self.assertEqual(config.shop_card_surcharge_percent, 12.5)

    def test_pos_line_surcharge_base_is_loaded_in_pos(self):
        fields = self.env["pos.order.line"]._load_pos_data_fields(self.env["pos.config"])
        self.assertIn("shop_card_surcharge_base", fields)
