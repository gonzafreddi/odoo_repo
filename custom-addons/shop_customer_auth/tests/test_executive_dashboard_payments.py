from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "shop_sale_payment_dashboard")
class TestExecutiveDashboardWebPayments(TransactionCase):
    def test_web_payments_are_grouped_by_custom_method_with_pending_balance(self):
        product = self.env["product.product"].create({
            "name": "Producto tablero",
            "type": "service",
            "list_price": 100.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.env["res.partner"].create({
                "name": "Cliente tablero",
            }).id,
            "order_line": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
                "price_unit": 100.0,
            })],
        })
        order.action_confirm()
        method = self.env["shop.sale.payment.method"].create({
            "name": "Tarjeta web",
            "company_id": self.env.company.id,
        })
        self.env["shop.sale.payment"].create({
            "order_id": order.id,
            "payment_method_id": method.id,
            "amount": 40.0,
            "date": fields.Date.today(),
            "currency_id": order.currency_id.id,
        })
        empty_pos = self.env["pos.order"].browse()
        empty_moves = self.env["account.move"].browse()
        methods = self.env["shop.executive.dashboard"]._payment_method_data({
            "channels": {
                "pos": {"document_ids": empty_pos.ids},
                "store": {"document_ids": order.ids},
                "other": {"document_ids": empty_moves.ids},
            },
        })

        by_name = {row["name"]: row for row in methods}
        self.assertEqual(by_name["Tarjeta web"]["store"], 40.0)
        pending = next(row for row in methods if row["pending"])
        self.assertEqual(pending["store"], 60.0)

    def test_daily_web_summary_groups_confirmed_payments_by_payment_date(self):
        today = fields.Date.to_date("2099-01-02")
        previous_day = today - timedelta(days=1)
        product = self.env["product.product"].create({
            "name": "Producto resumen web",
            "type": "service",
            "list_price": 200.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.env["res.partner"].create({
                "name": "Cliente resumen web",
            }).id,
            "order_line": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
                "price_unit": 200.0,
            })],
        })
        order.action_confirm()
        cash = self.env["shop.sale.payment.method"].create({
            "name": "Efectivo resumen web",
            "company_id": self.env.company.id,
        })
        transfer = self.env["shop.sale.payment.method"].create({
            "name": "Transferencia resumen web",
            "company_id": self.env.company.id,
        })
        payment_model = self.env["shop.sale.payment"]
        payment_model.create({
            "order_id": order.id,
            "payment_method_id": cash.id,
            "amount": 40.0,
            "date": previous_day,
        })
        payment_model.create({
            "order_id": order.id,
            "payment_method_id": transfer.id,
            "amount": 30.0,
            "date": today,
        })
        cancelled = payment_model.create({
            "order_id": order.id,
            "payment_method_id": cash.id,
            "amount": 20.0,
            "date": today,
        })
        cancelled.action_cancel()

        dashboard = self.env["shop.executive.dashboard"]
        self.assertTrue(
            hasattr(dashboard, "get_daily_web_payment_summary"),
            "Falta el resumen diario web por fecha de cobro",
        )
        summary = dashboard.get_daily_web_payment_summary(previous_day, today)

        self.assertEqual(summary["payment_method_names"], [
            "Efectivo resumen web",
            "Transferencia resumen web",
        ])
        self.assertEqual(summary["rows"], [
            {
                "date": fields.Date.to_string(today),
                "payment_amounts": {
                    "Transferencia resumen web": 30.0,
                },
                "total": 30.0,
            },
            {
                "date": fields.Date.to_string(previous_day),
                "payment_amounts": {
                    "Efectivo resumen web": 40.0,
                },
                "total": 40.0,
            },
        ])
