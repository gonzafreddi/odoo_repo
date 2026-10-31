from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


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

    def test_settings_persist_interest_free_installments(self):
        self.env["res.config.settings"].create({
            "x_interest_free_installments": 3,
        }).execute()

        self.assertEqual(
            self.env["ir.config_parameter"].sudo().get_param(
                "shop_config.interest_free_installments"
            ),
            "3",
        )

    def test_seeded_shipping_parameters_are_available(self):
        params = self.env["ir.config_parameter"].sudo()
        for key in (
            "shop_config.free_shipping_threshold",
            "shop_config.default_shipping_cost",
            "shop_config.free_shipping_enabled",
        ):
            self.assertTrue(params.get_param(key), f"Missing parameter: {key}")

    def test_cyber_dates_are_saved_as_utc_and_restored_as_argentina_local_time(self):
        self.env["res.config.settings"].create({
            "x_cyber_campaign_enabled": True,
            "x_cyber_campaign_start_local": "2026-11-02 00:00",
            "x_cyber_campaign_end_exclusive_local": "2026-11-05 00:00",
            "x_cyber_campaign_destination_url": "/productos?ofertas=cyber",
            "x_cyber_campaign_id": "cyber-suplex-2026",
        }).execute()

        params = self.env["ir.config_parameter"].sudo()
        self.assertEqual(
            params.get_param("shop_config.cyber_campaign_start_utc"),
            "2026-11-02T03:00:00Z",
        )
        self.assertEqual(
            params.get_param("shop_config.cyber_campaign_end_exclusive_utc"),
            "2026-11-05T03:00:00Z",
        )
        settings = self.env["res.config.settings"].create({})
        values = settings.get_values()
        self.assertEqual(values["x_cyber_campaign_start_local"], "2026-11-02 00:00")
        self.assertEqual(
            values["x_cyber_campaign_end_exclusive_local"], "2026-11-05 00:00"
        )
        self.assertEqual(params.get_param("shop_config.cyber_campaign_enabled"), "True")

    def test_cyber_end_must_be_after_start(self):
        settings = self.env["res.config.settings"].create({
            "x_cyber_campaign_start_local": "2026-11-05 00:00",
            "x_cyber_campaign_end_exclusive_local": "2026-11-05 00:00",
            "x_cyber_campaign_destination_url": "/productos",
            "x_cyber_campaign_id": "cyber-suplex-2026",
        })
        with self.assertRaises(ValidationError):
            settings.execute()

    def test_cyber_campaign_is_seeded_disabled_with_requested_window(self):
        params = self.env["ir.config_parameter"].sudo()
        self.assertIn(
            params.get_param("shop_config.cyber_campaign_enabled"),
            ("False", "0", ""),
        )
        self.assertEqual(
            params.get_param("shop_config.cyber_campaign_start_utc"),
            "2026-11-02T03:00:00Z",
        )
        self.assertEqual(
            params.get_param("shop_config.cyber_campaign_end_exclusive_utc"),
            "2026-11-05T03:00:00Z",
        )
