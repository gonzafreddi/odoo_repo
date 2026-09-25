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
                "tax_ids": [Command.set([])],
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
                "mercadopago_fees": 0.0,
                "net": 30.0,
            },
            {
                "date": fields.Date.to_string(previous_day),
                "payment_amounts": {
                    "Efectivo resumen web": 40.0,
                },
                "total": 40.0,
                "mercadopago_fees": 0.0,
                "net": 40.0,
            },
        ])


@tagged("post_install", "-at_install", "shop_sale_payment_dashboard")
class TestExecutiveDashboardMercadoPago(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Producto MP", "type": "service", "list_price": 100.0,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Cliente MP"})
        cls.day = fields.Date.to_date("2099-03-10")

    def _paid_order(self, reference, amount, details):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": 1,
                "price_unit": amount, "tax_ids": [Command.set([])],
            })],
        })
        order.action_confirm()
        self.env["sale.order"].shop_register_online_payment(
            order.id, "mercadopago", reference, amount,
            order.currency_id.name, details,
        )
        # La fecha del cobro se fija por SQL: el cobro no admite escrituras.
        self.env.cr.execute(
            "UPDATE shop_sale_payment SET date = %s WHERE order_id = %s",
            (self.day, order.id),
        )
        order.web_payment_ids.invalidate_recordset(["date"])
        return order

    def test_mercadopago_metrics_group_fees_types_and_installments(self):
        self._paid_order("mp-a", 1000.0, {
            "payment_type_id": "credit_card", "payment_method_id": "visa",
            "installments": 3, "fee_amount": 80.0,
        })
        self._paid_order("mp-b", 500.0, {
            "payment_type_id": "credit_card", "payment_method_id": "master",
            "installments": 3, "fee_amount": 40.0,
        })
        self._paid_order("mp-c", 200.0, {
            "payment_type_id": "account_money",
            "payment_method_id": "account_money",
            "installments": 1, "fee_amount": 10.0,
        })
        data = self.env["shop.executive.dashboard"]._mercadopago_data(
            self.day, self.day
        )
        self.assertEqual(data["count"], 3)
        self.assertAlmostEqual(data["amount"], 1700.0)
        self.assertAlmostEqual(data["fees"], 130.0)
        self.assertAlmostEqual(data["net"], 1570.0)
        self.assertEqual(data["most_used_installments"], 3)
        self.assertAlmostEqual(data["average_installments"], 7 / 3)
        by_type = {row["name"]: row for row in data["by_type"]}
        self.assertEqual(by_type["Tarjeta de crédito"]["count"], 2)
        self.assertAlmostEqual(by_type["Dinero en cuenta"]["fees"], 10.0)
        by_installments = {row["installments"]: row for row in data["by_installments"]}
        self.assertEqual(by_installments[3]["count"], 2)
        self.assertAlmostEqual(by_installments[3]["amount"], 1500.0)
        self.assertEqual([row["name"] for row in data["by_method"]][:1], ["Visa"])

    def test_mercadopago_fees_reduce_operating_results(self):
        self._paid_order("mp-fee", 1000.0, {
            "payment_type_id": "debit_card", "installments": 1,
            "fee_amount": 50.0,
        })
        data = self.env["shop.executive.dashboard"].get_dashboard_data(
            "2099-03-10", "2099-03-10"
        )
        metrics = data["metrics"]
        self.assertAlmostEqual(metrics["mercadopago_fees"], 50.0)
        self.assertAlmostEqual(
            metrics["operating_result"],
            metrics["sales"] - metrics["purchases"] - metrics["expenses"] - 50.0,
        )
        self.assertAlmostEqual(
            metrics["profitability_operating_result"],
            metrics["gross_margin"] - metrics["expenses"] - 50.0,
        )
        self.assertEqual(data["mercadopago"]["count"], 1)
        self.assertNotIn("payment_ids", data["mercadopago"])
        self.assertEqual(len(data["record_ids"]["mercadopago_payments"]), 1)

    def test_payments_without_detail_are_grouped_apart(self):
        self._paid_order("mp-no-detail", 100.0, {"fee_amount": 5.0})
        data = self.env["shop.executive.dashboard"]._mercadopago_data(
            self.day, self.day
        )
        self.assertEqual(data["by_type"][0]["name"], "Sin detalle")
        self.assertEqual(data["by_installments"], [])
        self.assertEqual(data["most_used_installments"], 0)
