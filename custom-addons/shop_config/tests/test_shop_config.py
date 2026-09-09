from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestShopConfig(TransactionCase):
    def test_settings_persist_shipping_parameters(self):
        self.env["res.config.settings"].create({
            "x_free_shipping_enabled": True,
            "x_free_shipping_threshold": 150000.0,
            "x_default_shipping_cost": 4000.0,
        }).execute()

        params = self.env["ir.config_parameter"].sudo()
        self.assertEqual(
            float(params.get_param("shop_config.free_shipping_threshold")),
            150000.0,
        )
        self.assertEqual(
            float(params.get_param("shop_config.default_shipping_cost")),
            4000.0,
        )
        self.assertEqual(
            params.get_param("shop_config.free_shipping_enabled"),
            "True",
        )

    def test_seeded_shipping_parameters_are_available(self):
        params = self.env["ir.config_parameter"].sudo()
        for key in (
            "shop_config.free_shipping_threshold",
            "shop_config.default_shipping_cost",
            "shop_config.free_shipping_enabled",
        ):
            self.assertTrue(params.get_param(key), f"Missing parameter: {key}")
