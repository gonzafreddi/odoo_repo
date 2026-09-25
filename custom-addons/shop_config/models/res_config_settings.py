from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x_free_shipping_enabled = fields.Boolean(
        string="Envío gratis activo",
        config_parameter="shop_config.free_shipping_enabled",
        default=True,
        help="Si está desactivado, la tienda online no muestra mensajes de envío gratis.",
    )
    x_free_shipping_threshold = fields.Float(
        string="Umbral de envío gratis",
        config_parameter="shop_config.free_shipping_threshold",
        default=130000.0,
        help="Subtotal a partir del cual el envío es gratis en la tienda online.",
    )
    x_default_shipping_cost = fields.Float(
        string="Costo de envío por defecto",
        config_parameter="shop_config.default_shipping_cost",
        default=3500.0,
        help="Costo de envío que muestra la tienda online cuando el subtotal no alcanza el umbral.",
    )
    x_card_surcharge_percent = fields.Float(
        string="Recargo tarjeta / Mercado Pago (%)",
        config_parameter="shop_config.card_surcharge_percent",
        default=0.0,
        help="Recargo sobre el precio de lista (o de oferta) para pagos con tarjeta "
             "o Mercado Pago. Efectivo y transferencia pagan el precio de lista. "
             "Se aplica en la tienda online y en el POS.",
    )

    @api.constrains("x_card_surcharge_percent")
    def _check_card_surcharge_percent(self):
        for settings in self:
            if not 0 <= settings.x_card_surcharge_percent <= 100:
                raise ValidationError(
                    _("El recargo de tarjeta debe estar entre 0 y 100 %.")
                )
