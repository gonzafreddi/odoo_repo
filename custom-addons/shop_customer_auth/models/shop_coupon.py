import secrets
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round

STORE_TZ = "America/Argentina/Buenos_Aires"
# Sin 0/O ni 1/I/L para que el código se pueda dictar y copiar sin errores.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
PARAM_PREFIX = "shop_customer_auth.post_purchase_coupon_"


def store_today():
    return datetime.now(pytz.timezone(STORE_TZ)).date()


def normalize_code(code):
    return (code or "").strip().upper()


def normalize_email(email):
    return (email or "").strip().lower()


class ShopCoupon(models.Model):
    _name = "shop.coupon"
    _description = "Cupón de descuento web"
    _order = "create_date desc, id desc"
    _rec_name = "code"

    _code_unique = models.Constraint(
        "UNIQUE(code)", "Ya existe un cupón con ese código.",
    )

    name = fields.Char(
        string="Descripción", required=True,
        help="Uso interno, por ejemplo «Día de la Madre».",
    )
    code = fields.Char(
        string="Código", required=True, copy=False, index=True,
        help="Lo que el cliente escribe en el checkout. No distingue mayúsculas.",
    )
    active = fields.Boolean(default=True)
    origin = fields.Selection(
        [("manual", "Manual"), ("post_purchase", "Post-compra")],
        string="Origen", required=True, default="manual", readonly=True,
    )
    discount_type = fields.Selection(
        [("percent", "Porcentaje"), ("fixed", "Monto fijo")],
        string="Tipo de descuento", required=True, default="percent",
    )
    discount_value = fields.Float(
        string="Descuento", required=True,
        help="Porcentaje (ej. 10) o monto en pesos según el tipo.",
    )
    max_discount_amount = fields.Float(
        string="Tope de descuento",
        help="Sólo para porcentaje: máximo en pesos que descuenta. 0 = sin tope.",
    )
    min_amount = fields.Float(
        string="Compra mínima",
        help="Subtotal mínimo de productos (sin envío) para usarlo. 0 = sin mínimo.",
    )
    date_from = fields.Date(string="Válido desde")
    date_to = fields.Date(string="Válido hasta", help="Incluido.")
    usage_limit = fields.Integer(
        string="Usos totales", default=0,
        help="Cuántas compras en total pueden usarlo. 0 = sin límite.",
    )
    usage_per_customer = fields.Integer(
        string="Usos por cliente", default=1,
        help="Cuántas veces puede usarlo cada cliente (por email). 0 = sin límite.",
    )
    restricted_email = fields.Char(
        string="Sólo para el email",
        help="Si se completa, sólo lo puede usar una compra hecha con este email.",
    )
    source_order_id = fields.Many2one(
        "sale.order", string="Generado por el pedido", readonly=True,
        copy=False, index=True, ondelete="set null",
    )
    email_sent_at = fields.Datetime(
        string="Email enviado", readonly=True, copy=False,
    )
    redemption_ids = fields.One2many(
        "shop.coupon.redemption", "coupon_id", string="Usos",
    )
    used_count = fields.Integer(string="Usado", compute="_compute_used_count")
    status = fields.Selection(
        [
            ("active", "Vigente"),
            ("scheduled", "Programado"),
            ("expired", "Vencido"),
            ("exhausted", "Agotado"),
            ("archived", "Archivado"),
        ],
        string="Estado", compute="_compute_status",
    )

    @api.depends("redemption_ids.state")
    def _compute_used_count(self):
        for coupon in self:
            coupon.used_count = len(
                coupon.redemption_ids.filtered(lambda r: r.state == "active")
            )

    @api.depends("active", "date_from", "date_to", "usage_limit", "used_count")
    def _compute_status(self):
        today = store_today()
        for coupon in self:
            if not coupon.active:
                coupon.status = "archived"
            elif coupon.date_to and coupon.date_to < today:
                coupon.status = "expired"
            elif coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
                coupon.status = "exhausted"
            elif coupon.date_from and coupon.date_from > today:
                coupon.status = "scheduled"
            else:
                coupon.status = "active"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = normalize_code(vals["code"])
            else:
                vals["code"] = self._generate_code()
            if vals.get("restricted_email"):
                vals["restricted_email"] = normalize_email(vals["restricted_email"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = normalize_code(vals["code"])
        if "restricted_email" in vals:
            vals["restricted_email"] = normalize_email(vals["restricted_email"]) or False
        return super().write(vals)

    @api.constrains("discount_type", "discount_value", "max_discount_amount",
                    "min_amount", "usage_limit", "usage_per_customer",
                    "date_from", "date_to", "code")
    def _check_values(self):
        for coupon in self:
            if not coupon.code or " " in coupon.code:
                raise ValidationError(_("El código no puede estar vacío ni tener espacios."))
            if coupon.discount_value <= 0:
                raise ValidationError(_("El descuento debe ser mayor que cero."))
            if coupon.discount_type == "percent" and coupon.discount_value > 100:
                raise ValidationError(_("El porcentaje no puede superar el 100 %."))
            if min(coupon.max_discount_amount, coupon.min_amount,
                   coupon.usage_limit, coupon.usage_per_customer) < 0:
                raise ValidationError(_("Los topes, mínimos y límites no pueden ser negativos."))
            if coupon.date_from and coupon.date_to and coupon.date_from > coupon.date_to:
                raise ValidationError(_("La fecha «desde» no puede ser posterior a «hasta»."))

    @api.model
    def _generate_code(self, prefix=""):
        prefix = normalize_code(prefix)
        for _attempt in range(20):
            code = prefix + "".join(secrets.choice(CODE_ALPHABET) for _i in range(8))
            if not self.with_context(active_test=False).search_count([("code", "=", code)]):
                return code
        raise ValidationError(_("No se pudo generar un código de cupón único."))

    # ------------------------------------------------------------------
    # Validación y cálculo
    # ------------------------------------------------------------------

    def _find_by_code(self, code):
        code = normalize_code(code)
        if not code:
            return self.browse()
        return self.search([("code", "=", code)], limit=1)

    def _check_usable(self, email, amount, exclude_order=None):
        """Devuelve un mensaje de error para el cliente, o False si se puede usar."""
        self.ensure_one()
        email = normalize_email(email)
        today = store_today()
        if not self.active:
            return _("El cupón no es válido.")
        if self.date_from and self.date_from > today:
            return _("El cupón todavía no está vigente.")
        if self.date_to and self.date_to < today:
            return _("El cupón está vencido.")
        if self.restricted_email and self.restricted_email != email:
            return _("Este cupón es personal y sólo vale con el email al que fue enviado.")
        active = self.redemption_ids.filtered(
            lambda r: r.state == "active" and (not exclude_order or r.order_id != exclude_order)
        )
        if self.usage_limit and len(active) >= self.usage_limit:
            return _("Este cupón ya fue utilizado.")
        if self.usage_per_customer and email and len(
            active.filtered(lambda r: r.email == email)
        ) >= self.usage_per_customer:
            return _("Ya usaste este cupón.")
        if self.min_amount and float_compare(amount, self.min_amount, precision_digits=2) < 0:
            return _("Este cupón requiere una compra mínima de $%s en productos.") % (
                "{:,.0f}".format(self.min_amount).replace(",", ".")
            )
        return False

    def _discount_for(self, amount):
        self.ensure_one()
        if amount <= 0:
            return 0.0
        if self.discount_type == "percent":
            discount = amount * self.discount_value / 100.0
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = self.discount_value
        return float_round(min(discount, amount), precision_digits=2)

    def _public_data(self):
        self.ensure_one()
        return {
            "code": self.code,
            "name": self.name,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "max_discount_amount": self.max_discount_amount or 0.0,
            "min_amount": self.min_amount or 0.0,
            "date_to": fields.Date.to_string(self.date_to) if self.date_to else False,
        }

    @api.model
    def shop_check_coupon(self, code, email, amount):
        """Vista previa para el checkout web. No reserva el cupón."""
        coupon = self._find_by_code(code)
        if not coupon:
            return {"valid": False, "message": _("El cupón no existe.")}
        amount = float(amount or 0.0)
        error = coupon._check_usable(email, amount)
        if error:
            return {"valid": False, "message": error}
        return {
            "valid": True,
            **coupon._public_data(),
            "discount_amount": coupon._discount_for(amount),
        }

    # ------------------------------------------------------------------
    # Cupón post-compra
    # ------------------------------------------------------------------

    @api.model
    def _post_purchase_settings(self):
        params = self.env["ir.config_parameter"].sudo()

        def number(key, default):
            try:
                return float(params.get_param(PARAM_PREFIX + key, default) or 0)
            except ValueError:
                return float(default)

        return {
            "enabled": params.get_param(PARAM_PREFIX + "enabled") in ("True", "1", "true"),
            "discount_type": params.get_param(PARAM_PREFIX + "discount_type") or "percent",
            "discount_value": number("discount_value", 10),
            "max_discount_amount": number("max_discount_amount", 0),
            "min_amount": number("min_amount", 0),
            "validity_days": int(number("validity_days", 30)),
            "code_prefix": params.get_param(PARAM_PREFIX + "code_prefix") or "",
        }

    @api.model
    def _issue_post_purchase(self, order):
        settings = self._post_purchase_settings()
        email = normalize_email(order.x_web_customer_email)
        if not settings["enabled"] or not email or settings["discount_value"] <= 0:
            return self.browse()
        existing = self.with_context(active_test=False).search(
            [("source_order_id", "=", order.id), ("origin", "=", "post_purchase")],
            limit=1,
        )
        if existing:
            return existing
        validity_days = max(settings["validity_days"], 1)
        return self.sudo().create({
            "name": _("Post-compra %s") % order.name,
            "code": self._generate_code(settings["code_prefix"]),
            "origin": "post_purchase",
            "discount_type": settings["discount_type"],
            "discount_value": settings["discount_value"],
            "max_discount_amount": settings["max_discount_amount"],
            "min_amount": settings["min_amount"],
            "date_from": store_today(),
            "date_to": store_today() + timedelta(days=validity_days - 1),
            "usage_limit": 1,
            "usage_per_customer": 1,
            "restricted_email": email,
            "source_order_id": order.id,
        })

    @api.model
    def shop_pending_coupon_emails(self, limit=20):
        """Cupones post-compra vigentes cuyo email todavía no salió."""
        since = fields.Datetime.now() - timedelta(days=3)
        coupons = self.search([
            ("origin", "=", "post_purchase"),
            ("email_sent_at", "=", False),
            ("create_date", ">=", since),
            ("source_order_id.state", "=", "sale"),
        ], limit=limit, order="id")
        return [coupon._email_payload() for coupon in coupons]

    def _email_payload(self):
        self.ensure_one()
        order = self.source_order_id
        return {
            "coupon_id": self.id,
            "order_id": order.id,
            "order_name": order.name,
            "email": self.restricted_email,
            "customer_name": order.x_web_customer_name or order.partner_id.name or "",
            **self._public_data(),
        }

    @api.model
    def shop_order_coupon_email(self, order_id):
        coupon = self.search([
            ("source_order_id", "=", order_id),
            ("origin", "=", "post_purchase"),
        ], limit=1)
        if not coupon or coupon.email_sent_at:
            return False
        return coupon._email_payload()

    @api.model
    def shop_mark_coupon_emailed(self, coupon_id):
        coupon = self.browse(coupon_id).exists()
        if coupon and not coupon.email_sent_at:
            coupon.email_sent_at = fields.Datetime.now()
        return bool(coupon)


class ShopCouponRedemption(models.Model):
    _name = "shop.coupon.redemption"
    _description = "Uso de cupón web"
    _order = "create_date desc, id desc"

    _coupon_order_unique = models.Constraint(
        "UNIQUE(coupon_id, order_id)", "El cupón ya está aplicado en este pedido.",
    )

    coupon_id = fields.Many2one(
        "shop.coupon", required=True, index=True, ondelete="cascade",
        string="Cupón",
    )
    order_id = fields.Many2one(
        "sale.order", required=True, index=True, ondelete="cascade",
        string="Pedido",
    )
    email = fields.Char(required=True, index=True)
    partner_id = fields.Many2one(related="order_id.partner_id", string="Cliente")
    discount_amount = fields.Monetary(
        string="Descuento", currency_field="currency_id",
    )
    currency_id = fields.Many2one(related="order_id.currency_id")
    state = fields.Selection(
        [("active", "Usado"), ("cancelled", "Liberado")],
        default="active", required=True, string="Estado",
    )
    date = fields.Datetime(related="create_date", string="Fecha")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_web_coupon_id = fields.Many2one(
        "shop.coupon", string="Cupón aplicado", copy=False, readonly=True,
        index=True, ondelete="restrict",
    )
    x_web_coupon_discount = fields.Monetary(
        string="Descuento por cupón", currency_field="currency_id",
        copy=False, readonly=True,
    )
    x_generated_coupon_ids = fields.One2many(
        "shop.coupon", "source_order_id", string="Cupón generado",
        context={"active_test": False},
    )

    @api.model_create_multi
    def create(self, vals_list):
        codes = [vals.pop("x_web_coupon_code", False) for vals in vals_list]
        orders = super().create(vals_list)
        for order, code in zip(orders, codes):
            if code:
                order._shop_apply_coupon(code)
        return orders

    def _shop_coupon_lines(self):
        return self.order_line.filtered(
            lambda line: not line.display_type and line.product_id
            and not line.is_delivery and line.price_unit > 0
        )

    def _shop_apply_coupon(self, code):
        """Aplica el cupón como descuento % en las líneas de productos.

        Corre dentro del create del pedido: si el cupón no es válido se
        revierte todo y la web recibe el mensaje.
        """
        self.ensure_one()
        coupon_model = self.env["shop.coupon"].sudo()
        coupon = coupon_model._find_by_code(code)
        if not coupon:
            raise ValidationError(_("El cupón no existe."))
        # Serializa los usos del mismo cupón para respetar los límites.
        self.env.cr.execute(
            "SELECT id FROM shop_coupon WHERE id = %s FOR UPDATE", [coupon.id]
        )
        coupon.invalidate_recordset(["redemption_ids"])
        lines = self._shop_coupon_lines()
        base = sum(lines.mapped("price_total"))
        email = normalize_email(self.x_web_customer_email)
        error = coupon._check_usable(email, base, exclude_order=self)
        if error:
            raise ValidationError(error)
        discount = coupon._discount_for(base)
        if discount <= 0:
            raise ValidationError(_("El cupón no aplica a este pedido."))
        percent = float_round(discount / base * 100.0, precision_digits=4)
        for line in lines:
            previous = line.discount or 0.0
            line.discount = 100.0 - (100.0 - previous) * (100.0 - percent) / 100.0
        applied = float_round(base - sum(lines.mapped("price_total")), precision_digits=2)
        self.write({
            "x_web_coupon_id": coupon.id,
            "x_web_coupon_discount": applied,
        })
        self.env["shop.coupon.redemption"].sudo().create({
            "coupon_id": coupon.id,
            "order_id": self.id,
            "email": email or "-",
            "discount_amount": applied,
        })

    def action_confirm(self):
        result = super().action_confirm()
        coupon_model = self.env["shop.coupon"].sudo()
        for order in self.filtered("x_web_customer_email"):
            coupon_model._issue_post_purchase(order)
        return result

    def _action_cancel(self):
        result = super()._action_cancel()
        redemptions = self.env["shop.coupon.redemption"].sudo().search([
            ("order_id", "in", self.ids), ("state", "=", "active"),
        ])
        redemptions.write({"state": "cancelled"})
        generated = self.env["shop.coupon"].sudo().search([
            ("source_order_id", "in", self.ids), ("origin", "=", "post_purchase"),
        ])
        generated.filtered(lambda c: not c.used_count).write({"active": False})
        return result
