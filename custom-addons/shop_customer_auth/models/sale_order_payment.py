from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class ShopSalePaymentMethod(models.Model):
    _name = "shop.sale.payment.method"
    _description = "Medio de cobro web"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    reference_required = fields.Boolean(string="Exige referencia")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True,
    )

    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "Ya existe un medio de cobro web con ese nombre en la compañía.",
    )


class ShopSalePayment(models.Model):
    _name = "shop.sale.payment"
    _description = "Cobro de venta web"
    _order = "date desc, id desc"
    _check_company_auto = True

    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="restrict", index=True,
        check_company=True,
    )
    payment_method_id = fields.Many2one(
        "shop.sale.payment.method", string="Medio de cobro", required=True,
        ondelete="restrict", check_company=True,
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    reference = fields.Char()
    user_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company", required=True, related="order_id.company_id",
        store=True, index=True,
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, related="order_id.currency_id",
        store=True,
    )
    state = fields.Selection(
        [("confirmed", "Confirmado"), ("cancelled", "Anulado")],
        required=True, default="confirmed", index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["sale.order"].browse([
            vals.get("order_id") for vals in vals_list if vals.get("order_id")
        ]).exists()
        order_by_id = {order.id: order for order in orders}
        for vals in vals_list:
            order = order_by_id.get(vals.get("order_id"))
            if order:
                vals.setdefault("company_id", order.company_id.id)
                vals.setdefault("currency_id", order.currency_id.id)
        return super().create(vals_list)

    @api.constrains(
        "amount", "state", "order_id", "payment_method_id", "reference"
    )
    def _check_payment(self):
        for payment in self:
            currency = payment.currency_id
            if float_compare(
                payment.amount, 0.0, precision_rounding=currency.rounding
            ) <= 0:
                raise ValidationError(_("El importe debe ser mayor que cero."))
            if payment.order_id.state != "sale":
                raise ValidationError(
                    _("Sólo se pueden registrar cobros en pedidos confirmados.")
                )
            if (
                payment.payment_method_id.reference_required
                and not (payment.reference or "").strip()
            ):
                raise ValidationError(
                    _("El medio de cobro seleccionado exige una referencia.")
                )
            confirmed_total = sum(
                payment.order_id.web_payment_ids.filtered(
                    lambda item: item.state == "confirmed"
                ).mapped("amount")
            )
            if float_compare(
                confirmed_total,
                payment.order_id.amount_total,
                precision_rounding=currency.rounding,
            ) > 0:
                raise ValidationError(
                    _("El cobro supera el saldo pendiente del pedido.")
                )

    def write(self, values):
        if self and not self.env.context.get("shop_cancel_payment"):
            raise UserError(
                _("Los cobros registrados no se modifican; deben anularse.")
            )
        return super().write(values)

    def unlink(self):
        if self:
            raise UserError(
                _("Los cobros se conservan por auditoría y no pueden eliminarse.")
            )
        return super().unlink()

    def action_cancel(self):
        for payment in self:
            if payment.state == "confirmed":
                payment.with_context(shop_cancel_payment=True).write({
                    "state": "cancelled",
                })
        return True


class SaleOrder(models.Model):
    _inherit = "sale.order"

    web_payment_ids = fields.One2many(
        "shop.sale.payment", "order_id", string="Cobros web",
    )
    web_amount_paid = fields.Monetary(
        string="Cobrado", compute="_compute_web_payment_totals",
        currency_field="currency_id", store=True,
    )
    web_amount_due = fields.Monetary(
        string="Pendiente", compute="_compute_web_payment_totals",
        currency_field="currency_id", store=True,
    )
    web_payment_state = fields.Selection(
        [
            ("not_paid", "No pagado"),
            ("partial", "Pago parcial"),
            ("paid", "Pagado"),
        ],
        string="Estado de cobro", compute="_compute_web_payment_totals",
        store=True,
    )

    @api.depends(
        "amount_total", "web_payment_ids.amount", "web_payment_ids.state"
    )
    def _compute_web_payment_totals(self):
        for order in self:
            paid = sum(
                order.web_payment_ids.filtered(
                    lambda payment: payment.state == "confirmed"
                ).mapped("amount")
            )
            due = max(order.amount_total - paid, 0.0)
            order.web_amount_paid = paid
            order.web_amount_due = due
            if order.currency_id.compare_amounts(due, 0.0) == 0:
                order.web_payment_state = "paid"
            elif order.currency_id.compare_amounts(paid, 0.0) > 0:
                order.web_payment_state = "partial"
            else:
                order.web_payment_state = "not_paid"

    def action_validate_payment(self):
        self.ensure_one()
        if self.state != "sale":
            raise UserError(
                _("Sólo se pueden registrar cobros en pedidos confirmados.")
            )
        if self.currency_id.compare_amounts(self.web_amount_due, 0.0) <= 0:
            raise UserError(_("El pedido no tiene saldo pendiente."))
        return {
            "name": _("Registrar cobro web"),
            "type": "ir.actions.act_window",
            "res_model": "shop.sale.payment.register.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_order_id": self.id,
                "default_amount": self.web_amount_due,
                "default_company_id": self.company_id.id,
            },
        }


class ShopSalePaymentRegisterWizard(models.TransientModel):
    _name = "shop.sale.payment.register.wizard"
    _description = "Registrar cobro web"

    order_id = fields.Many2one(
        "sale.order", required=True, readonly=True,
    )
    payment_method_id = fields.Many2one(
        "shop.sale.payment.method", string="Medio de cobro", required=True,
        domain="[('company_id', '=', company_id)]",
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    date = fields.Date(required=True, default=fields.Date.context_today)
    reference = fields.Char()
    company_id = fields.Many2one(
        "res.company", required=True, related="order_id.company_id",
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, related="order_id.currency_id",
    )

    def action_confirm(self):
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM sale_order WHERE id = %s FOR UPDATE",
            [self.order_id.id],
        )
        self.order_id.invalidate_recordset([
            "web_amount_paid", "web_amount_due", "web_payment_state",
        ])
        if self.order_id.state != "sale":
            raise ValidationError(
                _("Sólo se pueden registrar cobros en pedidos confirmados.")
            )
        if float_compare(
            self.amount, 0.0, precision_rounding=self.currency_id.rounding
        ) <= 0:
            raise ValidationError(_("El importe debe ser mayor que cero."))
        if float_compare(
            self.amount,
            self.order_id.web_amount_due,
            precision_rounding=self.currency_id.rounding,
        ) > 0:
            raise ValidationError(_("El cobro supera el saldo pendiente del pedido."))
        payment = self.env["shop.sale.payment"].create({
            "order_id": self.order_id.id,
            "payment_method_id": self.payment_method_id.id,
            "amount": self.amount,
            "date": self.date,
            "reference": self.reference,
            "user_id": self.env.user.id,
            "currency_id": self.currency_id.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "shop.sale.payment",
            "res_id": payment.id,
            "view_mode": "form",
            "target": "current",
        }
