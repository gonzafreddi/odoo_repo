from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .shop_coupon import PARAM_PREFIX


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Sin tildar = apagado: Odoo borra el parámetro de los booleanos al
    # destildarlos, y la ausencia del parámetro significa «no generar».
    x_post_purchase_coupon_enabled = fields.Boolean(
        string="Enviar cupón después de cada compra",
        config_parameter=PARAM_PREFIX + "enabled",
    )
    x_post_purchase_coupon_discount_type = fields.Selection(
        [("percent", "Porcentaje"), ("fixed", "Monto fijo")],
        string="Tipo de descuento",
        config_parameter=PARAM_PREFIX + "discount_type",
        default="percent",
    )
    x_post_purchase_coupon_discount_value = fields.Float(
        string="Descuento",
        config_parameter=PARAM_PREFIX + "discount_value",
        default=10.0,
        help="Porcentaje (ej. 10) o monto en pesos según el tipo.",
    )
    x_post_purchase_coupon_max_discount = fields.Float(
        string="Tope de descuento ($)",
        config_parameter=PARAM_PREFIX + "max_discount_amount",
        help="Sólo para porcentaje. 0 = sin tope.",
    )
    x_post_purchase_coupon_min_amount = fields.Float(
        string="Compra mínima para usarlo ($)",
        config_parameter=PARAM_PREFIX + "min_amount",
        help="Subtotal mínimo de productos (sin envío). 0 = sin mínimo.",
    )
    x_post_purchase_coupon_validity_days = fields.Integer(
        string="Válido por (días)",
        config_parameter=PARAM_PREFIX + "validity_days",
        default=30,
    )
    x_post_purchase_coupon_code_prefix = fields.Char(
        string="Prefijo del código",
        config_parameter=PARAM_PREFIX + "code_prefix",
        help="Opcional, por ejemplo GRACIAS → GRACIAS7KX2M9QP.",
    )

    @api.constrains(
        "x_post_purchase_coupon_discount_type",
        "x_post_purchase_coupon_discount_value",
        "x_post_purchase_coupon_max_discount",
        "x_post_purchase_coupon_min_amount",
        "x_post_purchase_coupon_validity_days",
        "x_post_purchase_coupon_code_prefix",
    )
    def _check_post_purchase_coupon(self):
        for settings in self:
            if not settings.x_post_purchase_coupon_enabled:
                continue
            value = settings.x_post_purchase_coupon_discount_value
            if value <= 0:
                raise ValidationError(_("El descuento del cupón post-compra debe ser mayor que cero."))
            if settings.x_post_purchase_coupon_discount_type == "percent" and value > 100:
                raise ValidationError(_("El porcentaje del cupón post-compra no puede superar el 100 %."))
            if settings.x_post_purchase_coupon_validity_days < 1:
                raise ValidationError(_("El cupón post-compra debe valer al menos 1 día."))
            if min(settings.x_post_purchase_coupon_max_discount,
                   settings.x_post_purchase_coupon_min_amount) < 0:
                raise ValidationError(_("El tope y la compra mínima no pueden ser negativos."))
            prefix = settings.x_post_purchase_coupon_code_prefix or ""
            if prefix and not prefix.strip().isalnum():
                raise ValidationError(_("El prefijo del código sólo puede tener letras y números."))
