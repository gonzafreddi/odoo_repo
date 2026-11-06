from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_shipping_weight_g = fields.Integer(
        string="Peso para envío (g)",
        help="Peso real del producto preparado para despacho. No incluye el peso de la caja exterior.",
    )
    x_shipping_length_cm = fields.Integer(string="Largo para envío (cm)")
    x_shipping_width_cm = fields.Integer(string="Ancho para envío (cm)")
    x_shipping_height_cm = fields.Integer(string="Alto para envío (cm)")

    @api.constrains(
        "x_shipping_weight_g",
        "x_shipping_length_cm",
        "x_shipping_width_cm",
        "x_shipping_height_cm",
    )
    def _check_shipping_measurements(self):
        for product in self:
            values = (
                product.x_shipping_weight_g,
                product.x_shipping_length_cm,
                product.x_shipping_width_cm,
                product.x_shipping_height_cm,
            )
            if any(values) and not all(value > 0 for value in values):
                raise ValidationError(
                    "Completá peso, largo, ancho y alto para usar el producto en una cotización postal."
                )
