import logging
from datetime import datetime, timezone

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


_logger = logging.getLogger(__name__)


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

    def _fixed_mercadopago_method(self):
        return self.env.ref(
            "shop_customer_auth.payment_method_mercadopago",
            raise_if_not_found=False,
        )

    def write(self, values):
        fixed = self._fixed_mercadopago_method()
        if fixed and fixed in self:
            locked = {
                "name": fixed.name,
                "active": True,
                "company_id": fixed.company_id.id,
            }
            if any(
                key in values and values[key] != current
                for key, current in locked.items()
            ):
                raise UserError(_(
                    "Mercado Pago es un medio de cobro fijo: no se puede "
                    "renombrar, archivar ni cambiar de compañía."
                ))
        return super().write(values)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_fixed_mercadopago(self):
        fixed = self._fixed_mercadopago_method()
        if fixed and fixed in self:
            raise UserError(_("Mercado Pago es un medio de cobro fijo y no se puede eliminar."))


class ShopSalePayment(models.Model):
    _name = "shop.sale.payment"
    _description = "Cobro de venta web"
    _order = "date desc, id desc"
    _check_company_auto = True

    _mercadopago_reference_unique = models.UniqueIndex(
        "(provider_payment_ref) "
        "WHERE provider_payment_ref IS NOT NULL AND state = 'confirmed'",
        "A confirmed payment already uses this provider reference.",
    )

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
    provider_payment_ref = fields.Char(
        string="Referencia del proveedor", readonly=True, copy=False, index=False,
    )
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
    # Detalle informado por Mercado Pago al registrar el cobro.
    mp_payment_type = fields.Char(string="Tipo de pago", readonly=True, copy=False)
    mp_payment_method = fields.Char(string="Medio de pago", readonly=True, copy=False)
    mp_card_last_four = fields.Char(string="Tarjeta (últimos 4)", readonly=True, copy=False)
    mp_installments = fields.Integer(string="Cuotas", readonly=True, copy=False)
    mp_payer_name = fields.Char(string="Pagador", readonly=True, copy=False)
    mp_payer_email = fields.Char(string="Email del pagador", readonly=True, copy=False)
    mp_date_approved = fields.Datetime(string="Aprobado el", readonly=True, copy=False)
    mp_fee_amount = fields.Monetary(
        string="Comisión Mercado Pago", currency_field="currency_id",
        readonly=True, copy=False,
    )
    mp_net_amount = fields.Monetary(
        string="Neto recibido", currency_field="currency_id",
        readonly=True, copy=False,
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
        if (
            self.env.context.get("shop_payment_details")
            and all(key.startswith("mp_") for key in values)
        ):
            return super().write(values)
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
    web_payment_preference = fields.Selection(
        [
            ("card", "Tarjeta / Mercado Pago"),
            ("cash", "Efectivo / Transferencia"),
        ],
        string="Medio elegido en la web", readonly=True, copy=False,
        help="Medio de pago que eligió el cliente al confirmar en la tienda online. "
             "Efectivo y transferencia llevan el descuento en cada línea.",
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

    @api.model
    def shop_register_online_payment(
        self, order_id, provider, provider_payment_id, amount, currency_code,
        details=None,
    ):
        order = self.browse(order_id).exists()
        if not order:
            return self._online_payment_result(
                "rejected", "order_not_found", False, order_id,
            )
        order.ensure_one()

        if provider == "mercadopago":
            method = self._get_online_payment_method(provider, order.company_id)
        else:
            return self._online_payment_result(
                "rejected", "unsupported_provider", False, order.id, order,
            )
        reference = str(provider_payment_id)
        provider_reference = "mercadopago:%s" % reference
        payment_model = self.env["shop.sale.payment"]
        detail_vals = self._prepare_mercadopago_details(details)
        existing = payment_model.search([
            ("provider_payment_ref", "=", provider_reference),
            ("state", "=", "confirmed"),
        ], limit=1)
        if existing:
            # Completa el detalle de cobros registrados antes de guardarlo.
            if detail_vals and not existing.mp_payment_type:
                existing.with_context(shop_payment_details=True).write(detail_vals)
            return self._online_payment_result(
                "already_registered", False, existing.id, order.id, order,
            )
        if order.state != "sale":
            return self._online_payment_result(
                "rejected", "order_not_confirmed", False, order.id, order,
            )
        if currency_code != order.currency_id.name:
            return self._online_payment_result(
                "rejected", "currency_mismatch", False, order.id, order,
            )
        if order.currency_id.compare_amounts(order.web_amount_due, 0.0) == 0:
            return self._online_payment_result(
                "rejected", "already_paid", False, order.id, order,
            )
        if float_compare(
            amount, order.web_amount_due,
            precision_rounding=order.currency_id.rounding,
        ) != 0:
            return self._online_payment_result(
                "rejected", "amount_mismatch", False, order.id, order,
            )

        try:
            with self.env.cr.savepoint():
                payment = payment_model.create({
                    "order_id": order.id,
                    "payment_method_id": method.id,
                    "amount": amount,
                    "reference": reference,
                    "provider_payment_ref": provider_reference,
                    **detail_vals,
                })
        except IntegrityError:
            existing = payment_model.search([
                ("provider_payment_ref", "=", provider_reference),
                ("state", "=", "confirmed"),
            ], limit=1)
            if existing:
                return self._online_payment_result(
                    "already_registered", False, existing.id, order.id, order,
                )
            raise
        order.message_post(body=_(
            "Cobro Mercado Pago registrado: pago #%(payment_id)s, $%(amount)s",
            payment_id=payment.id, amount=amount,
        ))
        return self._online_payment_result(
            "created", False, payment.id, order.id, order,
        )

    _MP_PAYMENT_TYPES = {
        "credit_card": "Tarjeta de crédito",
        "debit_card": "Tarjeta de débito",
        "prepaid_card": "Tarjeta prepaga",
        "account_money": "Dinero en cuenta",
        "ticket": "Efectivo",
        "bank_transfer": "Transferencia",
        "atm": "Cajero",
        "digital_currency": "Mercado Crédito",
        "consumer_credits": "Mercado Crédito",
    }
    _MP_PAYMENT_METHODS = {
        "visa": "Visa",
        "debvisa": "Visa Débito",
        "master": "Mastercard",
        "debmaster": "Mastercard Débito",
        "amex": "American Express",
        "naranja": "Naranja",
        "cabal": "Cabal",
        "debcabal": "Cabal Débito",
        "maestro": "Maestro",
        "account_money": "Dinero en cuenta",
        "consumer_credits": "Mercado Crédito",
        "pagofacil": "Pago Fácil",
        "rapipago": "Rapipago",
    }

    @api.model
    def _prepare_mercadopago_details(self, details):
        if not isinstance(details, dict):
            return {}

        def text(key):
            value = details.get(key)
            return str(value).strip()[:255] if value not in (None, False, "") else False

        def number(key):
            try:
                return float(details.get(key))
            except (TypeError, ValueError):
                return False

        payment_type = text("payment_type_id")
        payment_method = text("payment_method_id")
        vals = {
            "mp_payment_type": payment_type and self._MP_PAYMENT_TYPES.get(
                payment_type, payment_type
            ),
            "mp_payment_method": payment_method and self._MP_PAYMENT_METHODS.get(
                payment_method, payment_method.capitalize()
            ),
            "mp_card_last_four": text("card_last_four"),
            "mp_payer_name": text("payer_name"),
            "mp_payer_email": text("payer_email"),
            "mp_date_approved": self._parse_mercadopago_datetime(
                details.get("date_approved")
            ),
        }
        installments = number("installments")
        if installments:
            vals["mp_installments"] = int(installments)
        for key, field in (
            ("fee_amount", "mp_fee_amount"),
            ("net_received_amount", "mp_net_amount"),
        ):
            value = number(key)
            if value is not False:
                vals[field] = value
        return {key: value for key, value in vals.items() if value is not False}

    @api.model
    def _parse_mercadopago_datetime(self, value):
        if not isinstance(value, str) or not value:
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.replace(microsecond=0)

    @api.model
    def _get_online_payment_method(self, provider, company):
        if provider != "mercadopago":
            return self.env["shop.sale.payment.method"]
        method_model = self.env["shop.sale.payment.method"].sudo().with_context(
            active_test=False
        )
        fixed = method_model._fixed_mercadopago_method()
        if fixed and fixed.company_id == company:
            return fixed.sudo()
        # Otras compañías: se reutiliza o crea un medio con el mismo nombre.
        method = method_model.search([
            ("company_id", "=", company.id),
            ("name", "=ilike", "Mercado Pago"),
        ], limit=1)
        if method:
            if not method.active:
                method.write({"active": True})
            return method
        return method_model.create({
            "name": "Mercado Pago",
            "company_id": company.id,
            "reference_required": True,
            "sequence": 50,
        })

    @api.model
    def _online_payment_result(self, status, reason, payment_id, order_id, order=False):
        if status == "rejected":
            _logger.warning(
                "Mercado Pago payment rejected for order %s: %s", order_id, reason,
            )
        return {
            "status": status,
            "reason": reason or False,
            "payment_id": payment_id or False,
            "order_id": order_id,
            "order_name": order.name if order else False,
            "web_payment_state": order.web_payment_state if order else False,
            "web_amount_due": order.web_amount_due if order else 0.0,
        }

    @api.model
    def shop_get_payment_status(self, order_id):
        order = self.browse(order_id).exists()
        if not order:
            return {"order_id": order_id, "found": False}
        order.ensure_one()
        return {
            "order_id": order.id,
            "found": True,
            "order_name": order.name or False,
            "state": order.state or False,
            "amount_total": order.amount_total,
            "web_amount_due": order.web_amount_due,
            "web_payment_state": order.web_payment_state or False,
            "web_payment_preference": order.web_payment_preference or False,
            "currency_code": order.currency_id.name or False,
        }

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
