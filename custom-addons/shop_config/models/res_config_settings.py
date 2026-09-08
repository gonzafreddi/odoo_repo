from odoo import fields, models


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
