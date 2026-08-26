from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, format_amount


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _process_order(self, order, existing_order):
        order_id = super()._process_order(order, existing_order)
        self.browse(order_id)._sync_customer_account_moves()
        return order_id

    def _sync_customer_account_moves(self):
        Move = self.env["shop.customer.account.move"].sudo()
        for order in self:
            payments = order.payment_ids.filtered(
                lambda payment: payment.payment_method_id.is_customer_account
                and not payment.is_change
                and not order.currency_id.is_zero(payment.amount)
            )
            if not payments:
                continue
            if not order.partner_id:
                raise ValidationError(
                    _("Debés seleccionar un cliente para utilizar Cuenta Corriente.")
                )

            # Serialize debt changes for the same customer. The lock lives until
            # the POS sync transaction commits or rolls back.
            self.env.cr.execute(
                "SELECT id FROM res_partner WHERE id = %s FOR UPDATE",
                [order.partner_id.id],
            )
            existing_payment_ids = set(Move.search([
                ("pos_payment_id", "in", payments.ids),
            ]).mapped("pos_payment_id").ids)
            new_payments = payments.filtered(
                lambda payment: payment.id not in existing_payment_ids
            )
            new_debt = sum(payment.amount for payment in new_payments if payment.amount > 0)

            partner = order.partner_id.with_company(order.company_id)
            limit = partner.credit_limit
            if new_debt and limit > 0:
                grouped = Move._read_group(
                    [
                        ("partner_id", "=", partner.id),
                        ("company_id", "=", order.company_id.id),
                    ],
                    [],
                    ["signed_amount:sum"],
                )
                balance = grouped[0][0] if grouped else 0.0
                if float_compare(
                    balance + new_debt, limit,
                    precision_rounding=order.company_id.currency_id.rounding,
                ) > 0:
                    available = limit - balance
                    currency = order.company_id.currency_id
                    raise ValidationError(_(
                        "Límite de crédito excedido\n\n"
                        "Saldo actual: %(balance)s\nNueva deuda: %(debt)s\n"
                        "Límite: %(limit)s\nDisponible: %(available)s",
                        balance=format_amount(self.env, balance, currency),
                        debt=format_amount(self.env, new_debt, currency),
                        limit=format_amount(self.env, limit, currency),
                        available=format_amount(self.env, available, currency),
                    ))

            vals_list = []
            for payment in new_payments:
                is_refund = payment.amount < 0
                vals_list.append({
                    "partner_id": partner.id,
                    "date": fields.Date.to_date(payment.payment_date),
                    "move_type": "credit_adjustment" if is_refund else "sale",
                    "amount": abs(payment.amount),
                    "currency_id": order.company_id.currency_id.id,
                    "company_id": order.company_id.id,
                    "pos_order_id": order.id,
                    "pos_payment_id": payment.id,
                    "reference": order.pos_reference or order.name,
                    "note": (
                        _("Devolución POS a Cuenta Corriente")
                        if is_refund else _("Venta POS a Cuenta Corriente")
                    ),
                    "user_id": order.user_id.id or self.env.user.id,
                })
            if vals_list:
                Move.with_context(customer_account_pos_sync=True).create(vals_list)
