from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ShopExecutiveDashboard(models.AbstractModel):
    _name = "shop.executive.dashboard"
    _description = "Shop Executive Dashboard"

    _ALLOWED_GROUPS = (
        "sales_team.group_sale_manager",
        "purchase.group_purchase_manager",
        "account.group_account_manager",
        "base.group_system",
    )
    @api.model
    def _check_dashboard_access(self):
        if not any(self.env.user.has_group(group) for group in self._ALLOWED_GROUPS):
            raise AccessError(_("You do not have access to the executive dashboard."))

    @api.model
    def _parse_period(self, date_from, date_to):
        try:
            start = fields.Date.to_date(date_from)
            end = fields.Date.to_date(date_to)
        except (TypeError, ValueError):
            raise ValidationError(_("Enter a valid date range.")) from None
        if not start or not end or start > end:
            raise ValidationError(_("The start date must be before or equal to the end date."))
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - (end - start)
        return start, end, previous_start, previous_end

    @api.model
    def _sales_data(self, start, end):
        company = self.env.company
        pos_orders = self.env["pos.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ("paid", "done")),
            ("date_order", ">=", datetime.combine(start, time.min)),
            ("date_order", "<=", datetime.combine(end, time.max)),
        ])
        store_orders = self.env["sale.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "sale"),
            ("date_order", ">=", datetime.combine(start, time.min)),
            ("date_order", "<=", datetime.combine(end, time.max)),
        ])
        pos_invoice_ids = pos_orders.account_move.ids
        moves = self.env["account.move"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
            ("id", "not in", pos_invoice_ids),
        ])
        # Web orders are recognized on their confirmation date; their invoices
        # must never re-enter the dashboard later as "other" sales.
        moves = moves.filtered(lambda move: not move.invoice_line_ids.sale_line_ids)
        lines = moves.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.product_id
        )
        by_category = defaultdict(lambda: {"amount": 0.0, "units": 0.0})
        by_product = defaultdict(lambda: {"amount": 0.0, "units": 0.0})
        channels = {
            "pos": {"amount": 0.0, "units": 0.0, "document_ids": pos_orders.ids},
            "store": {"amount": 0.0, "units": 0.0, "document_ids": store_orders.ids},
            "other": {"amount": 0.0, "units": 0.0, "document_ids": []},
        }
        other_moves = moves.browse()
        for line in lines:
            # Product line balances are credit-negative on customer invoices.
            amount = -line.balance
            quantity = line.product_uom_id._compute_quantity(
                line.quantity, line.product_id.uom_id
            ) * line.move_id.direction_sign
            category = line.product_id.categ_id
            other_moves |= line.move_id
            channels["other"]["amount"] += amount
            channels["other"]["units"] += quantity
            by_category[(category.id, category.display_name)]["amount"] += amount
            by_category[(category.id, category.display_name)]["units"] += quantity
            by_product[(line.product_id.id, line.product_id.display_name)]["amount"] += amount
            by_product[(line.product_id.id, line.product_id.display_name)]["units"] += quantity
        for order in store_orders:
            conversion_date = fields.Date.to_date(order.date_order)
            for line in order.order_line.filtered(
                lambda item: not item.display_type and item.product_id
            ):
                amount = order.currency_id._convert(
                    line.price_subtotal,
                    company.currency_id,
                    company,
                    conversion_date,
                )
                quantity = line.product_uom_id._compute_quantity(
                    line.product_uom_qty, line.product_id.uom_id
                )
                category = line.product_id.categ_id
                channels["store"]["amount"] += amount
                channels["store"]["units"] += quantity
                by_category[(category.id, category.display_name)]["amount"] += amount
                by_category[(category.id, category.display_name)]["units"] += quantity
                by_product[(line.product_id.id, line.product_id.display_name)]["amount"] += amount
                by_product[(line.product_id.id, line.product_id.display_name)]["units"] += quantity
        for order in pos_orders:
            conversion_date = fields.Date.to_date(order.date_order)
            for line in order.lines:
                amount = order.currency_id._convert(
                    line.price_subtotal,
                    company.currency_id,
                    company,
                    conversion_date,
                )
                quantity = line.product_uom_id._compute_quantity(
                    line.qty, line.product_id.uom_id
                )
                category = line.product_id.categ_id
                channels["pos"]["amount"] += amount
                channels["pos"]["units"] += quantity
                by_category[(category.id, category.display_name)]["amount"] += amount
                by_category[(category.id, category.display_name)]["units"] += quantity
                by_product[(line.product_id.id, line.product_id.display_name)]["amount"] += amount
                by_product[(line.product_id.id, line.product_id.display_name)]["units"] += quantity
        channels["other"]["document_ids"] = other_moves.ids
        total = sum(channel["amount"] for channel in channels.values())
        units = sum(channel["units"] for channel in channels.values())
        return {
            "total": total,
            "units": units,
            "document_count": len(moves) + len(pos_orders) + len(store_orders),
            "move_ids": moves.ids,
            "channels": channels,
            "by_category": by_category,
            "by_product": by_product,
        }

    @api.model
    def _payment_method_data(self, sales):
        company = self.env.company
        grouped = defaultdict(lambda: {
            "amount": 0.0,
            "pos": 0.0,
            "store": 0.0,
            "other": 0.0,
        })

        def add(label, amount, channel):
            if not company.currency_id.is_zero(amount):
                grouped[label]["amount"] += amount
                grouped[label][channel] += amount

        pending_label = _("Pendiente / sin cobro registrado")
        pos_orders = self.env["pos.order"].sudo().browse(
            sales["channels"]["pos"]["document_ids"]
        ).exists()
        for order in pos_orders:
            date = fields.Date.to_date(order.date_order)
            sale_amount = sum(
                order.currency_id._convert(
                    line.price_subtotal, company.currency_id, company, date
                )
                for line in order.lines
            )
            payments = order.payment_ids.filtered(lambda payment: payment.amount)
            weights = [abs(payment.amount) for payment in payments]
            weight_total = sum(weights)
            if not weight_total:
                add(pending_label, sale_amount, "pos")
                continue
            for payment, weight in zip(payments, weights):
                add(
                    payment.payment_method_id.display_name,
                    sale_amount * weight / weight_total,
                    "pos",
                )

        store_orders = self.env["sale.order"].sudo().browse(
            sales["channels"]["store"]["document_ids"]
        ).exists()
        for order in store_orders:
            date = fields.Date.to_date(order.date_order)
            sale_amount = order.currency_id._convert(
                order.amount_untaxed, company.currency_id, company, date
            )
            total_with_tax = abs(order.currency_id._convert(
                order.amount_total, company.currency_id, company, date
            ))
            payments = order.invoice_ids.filtered(
                lambda move: move.state == "posted"
            )._get_reconciled_payments()
            allocated = 0.0
            for payment in payments:
                ratio = min(abs(payment.amount_company_currency_signed) / total_with_tax, 1.0) if total_with_tax else 0.0
                amount = sale_amount * ratio
                label = " · ".join(filter(None, (
                    payment.journal_id.display_name,
                    payment.payment_method_line_id.name,
                )))
                add(label or _("Cobro contable"), amount, "store")
                allocated += amount
            add(pending_label, sale_amount - min(allocated, sale_amount), "store")

        other_moves = self.env["account.move"].sudo().browse(
            sales["channels"]["other"]["document_ids"]
        ).exists()
        for move in other_moves:
            sale_amount = sum(-line.balance for line in move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product" and line.product_id
            ))
            total_with_tax = abs(move.amount_total_signed)
            allocated = 0.0
            for payment in move._get_reconciled_payments():
                ratio = min(abs(payment.amount_company_currency_signed) / total_with_tax, 1.0) if total_with_tax else 0.0
                amount = sale_amount * ratio
                label = " · ".join(filter(None, (
                    payment.journal_id.display_name,
                    payment.payment_method_line_id.name,
                )))
                add(label or _("Cobro contable"), amount, "other")
                allocated += amount
            add(pending_label, sale_amount - min(allocated, sale_amount), "other")

        result = [
            {"name": name, "pending": name == pending_label, **values}
            for name, values in grouped.items()
        ]
        result.sort(key=lambda item: abs(item["amount"]), reverse=True)
        return result

    @api.model
    def _purchase_data(self, start, end):
        company = self.env.company
        orders = self.env["purchase.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "purchase"),
            ("date_approve", ">=", datetime.combine(start, time.min)),
            ("date_approve", "<=", datetime.combine(end, time.max)),
        ])
        by_category = defaultdict(float)
        total = 0.0
        for order in orders:
            conversion_date = fields.Date.to_date(order.date_approve or order.date_order)
            for line in order.order_line.filtered(
                lambda item: not item.display_type and item.product_id
            ):
                amount = order.currency_id._convert(
                    line.price_subtotal,
                    company.currency_id,
                    company,
                    conversion_date,
                )
                total += amount
                category = line.product_id.categ_id
                by_category[(category.id, category.display_name)] += amount
        return {"total": total, "order_ids": orders.ids, "by_category": by_category}

    @api.model
    def _expense_data(self, start, end):
        company = self.env.company
        expenses = self.env["hr.expense"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ("posted", "in_payment", "paid")),
            ("date", ">=", start),
            ("date", "<=", end),
        ])
        by_account = defaultdict(float)
        total = 0.0
        for expense in expenses:
            total += expense.total_amount
            account = expense.account_id
            account_key = (
                account.id or 0,
                account.display_name or _("Sin cuenta contable"),
            )
            by_account[account_key] += expense.total_amount
        return {
            "total": total,
            "expense_ids": expenses.ids,
            "by_account": by_account,
        }

    @api.model
    def _stock_data(self):
        company = self.env.company
        products = (
            self.env["product.product"].sudo()
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
            .search([("active", "=", True), ("is_storable", "=", True)])
        )
        by_category = defaultdict(lambda: {"value": 0.0, "available": 0.0})
        low_stock = []
        total = 0.0
        for product in products:
            available = product.qty_available
            value = available * product.lst_price
            category = product.categ_id
            total += value
            by_category[(category.id, category.display_name)]["value"] += value
            by_category[(category.id, category.display_name)]["available"] += available
            if available <= 5:
                low_stock.append({
                    "id": product.id,
                    "name": product.display_name,
                    "category": category.display_name,
                    "available": available,
                })
        low_stock.sort(key=lambda item: (item["available"], item["name"]))
        return {
            "total": total,
            "product_ids": products.ids,
            "by_category": by_category,
            "low_stock": low_stock,
        }

    @staticmethod
    def _comparison(current, previous):
        if previous:
            return (current - previous) / abs(previous) * 100
        return None if not current else 100.0

    @api.model
    def get_dashboard_data(self, date_from, date_to):
        self._check_dashboard_access()
        company = self.env.company
        start, end, previous_start, previous_end = self._parse_period(date_from, date_to)
        sales = self._sales_data(start, end)
        purchases = self._purchase_data(start, end)
        expenses = self._expense_data(start, end)
        previous_sales = self._sales_data(previous_start, previous_end)
        previous_purchases = self._purchase_data(previous_start, previous_end)
        previous_expenses = self._expense_data(previous_start, previous_end)
        stock = self._stock_data()
        payment_methods = self._payment_method_data(sales)

        category_keys = (
            set(sales["by_category"])
            | set(purchases["by_category"])
            | set(stock["by_category"])
        )
        categories = []
        for category_id, name in category_keys:
            sales_values = sales["by_category"].get((category_id, name), {})
            stock_values = stock["by_category"].get((category_id, name), {})
            categories.append({
                "id": category_id,
                "name": name,
                "sales": sales_values.get("amount", 0.0),
                "purchases": purchases["by_category"].get((category_id, name), 0.0),
                "stock_value": stock_values.get("value", 0.0),
                "units_sold": sales_values.get("units", 0.0),
                "units_available": stock_values.get("available", 0.0),
            })
        categories.sort(key=lambda item: item["sales"], reverse=True)
        expense_accounts = [
            {"id": key[0], "name": key[1], "amount": amount}
            for key, amount in expenses["by_account"].items()
        ]
        expense_accounts.sort(key=lambda item: item["amount"], reverse=True)
        product_ranking = [
            {"id": key[0], "name": key[1], **values}
            for key, values in sales["by_product"].items()
        ]
        product_ranking.sort(key=lambda item: item["amount"], reverse=True)

        operating_result = sales["total"] - purchases["total"] - expenses["total"]
        previous_result = (
            previous_sales["total"] - previous_purchases["total"] - previous_expenses["total"]
        )
        ticket = sales["total"] / sales["document_count"] if sales["document_count"] else 0.0
        previous_ticket = (
            previous_sales["total"] / previous_sales["document_count"]
            if previous_sales["document_count"] else 0.0
        )
        metrics = {
            "sales": sales["total"],
            "expenses": expenses["total"],
            "purchases": purchases["total"],
            "stock_value": stock["total"],
            "operating_result": operating_result,
            "average_ticket": ticket,
            "document_count": sales["document_count"],
            "units_sold": sales["units"],
            "low_stock_count": len(stock["low_stock"]),
        }
        comparisons = {
            "sales": self._comparison(sales["total"], previous_sales["total"]),
            "expenses": self._comparison(expenses["total"], previous_expenses["total"]),
            "purchases": self._comparison(purchases["total"], previous_purchases["total"]),
            "operating_result": self._comparison(operating_result, previous_result),
            "average_ticket": self._comparison(ticket, previous_ticket),
            "document_count": self._comparison(
                sales["document_count"], previous_sales["document_count"]
            ),
            "units_sold": self._comparison(sales["units"], previous_sales["units"]),
        }
        sales_channels = []
        channel_labels = {
            "pos": _("POS"),
            "store": _("Tienda"),
            "other": _("Otras ventas facturadas"),
        }
        for key in ("pos", "store", "other"):
            channel = sales["channels"][key]
            previous_channel = previous_sales["channels"][key]
            sales_channels.append({
                "key": key,
                "label": channel_labels[key],
                "amount": channel["amount"],
                "units": channel["units"],
                "document_count": len(channel["document_ids"]),
                "comparison": self._comparison(
                    channel["amount"], previous_channel["amount"]
                ),
            })
        return {
            "company": {"id": company.id, "name": company.display_name},
            "currency": {
                "id": company.currency_id.id,
                "name": company.currency_id.name,
                "symbol": company.currency_id.symbol,
                "position": company.currency_id.position,
                "decimal_places": company.currency_id.decimal_places,
            },
            "period": {
                "date_from": fields.Date.to_string(start),
                "date_to": fields.Date.to_string(end),
                "previous_from": fields.Date.to_string(previous_start),
                "previous_to": fields.Date.to_string(previous_end),
            },
            "metrics": metrics,
            "comparisons": comparisons,
            "sales_channels": sales_channels,
            "payment_methods": payment_methods,
            "categories": categories,
            "expense_accounts": expense_accounts,
            "product_ranking": product_ranking[:10],
            "low_stock": stock["low_stock"],
            "record_ids": {
                "sales": sales["move_ids"],
                "pos_sales": sales["channels"]["pos"]["document_ids"],
                "store_sales": sales["channels"]["store"]["document_ids"],
                "other_sales": sales["channels"]["other"]["document_ids"],
                "expenses": expenses["expense_ids"],
                "purchases": purchases["order_ids"],
                "stock": stock["product_ids"],
                "low_stock": [item["id"] for item in stock["low_stock"]],
            },
        }

    @api.model
    def get_daily_sales_summary(self, date_from, date_to, page=1, page_size=15):
        self._check_dashboard_access()
        start, end, _previous_start, _previous_end = self._parse_period(
            date_from, date_to
        )
        company = self.env.company
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 15), 5), 50)
        datetime_from = datetime.combine(start, time.min)
        datetime_to = datetime.combine(end, time.max)

        pos_orders = self.env["pos.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "in", ("paid", "done")),
            ("date_order", ">=", datetime_from),
            ("date_order", "<=", datetime_to),
        ])
        store_orders = self.env["sale.order"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "sale"),
            ("date_order", ">=", datetime_from),
            ("date_order", "<=", datetime_to),
        ])
        invoice_moves = self.env["account.move"].sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
            ("id", "not in", pos_orders.account_move.ids),
        ]).filtered(lambda move: not move.invoice_line_ids.sale_line_ids)

        active_dates = {
            fields.Date.to_date(order.date_order) for order in pos_orders
        }
        active_dates.update(
            fields.Date.to_date(order.date_order) for order in store_orders
        )
        active_dates.update(move.invoice_date for move in invoice_moves if move.invoice_date)
        ordered_dates = sorted(active_dates, reverse=True)
        total_rows = len(ordered_dates)
        page_count = max((total_rows + page_size - 1) // page_size, 1)
        page = min(page, page_count)
        offset = (page - 1) * page_size
        rows = []
        for day in ordered_dates[offset:offset + page_size]:
            sales = self._sales_data(day, day)
            methods = self._payment_method_data(sales)
            rows.append({
                "date": fields.Date.to_string(day),
                "payment_methods": [
                    {"name": method["name"], "amount": method["amount"]}
                    for method in methods
                ],
                "total": sales["total"],
            })
        return {
            "rows": rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "page_count": page_count,
                "total_rows": total_rows,
            },
            "currency": {
                "name": company.currency_id.name,
                "decimal_places": company.currency_id.decimal_places,
            },
        }
