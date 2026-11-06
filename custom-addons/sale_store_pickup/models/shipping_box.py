from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleStoreShippingBox(models.Model):
    _name = "sale.store.shipping.box"
    _description = "Caja para envíos de Correo Argentino"
    _order = "sequence, volume, id"

    name = fields.Char(string="Nombre", required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    inner_length_cm = fields.Integer(string="Largo interno (cm)", required=True)
    inner_width_cm = fields.Integer(string="Ancho interno (cm)", required=True)
    inner_height_cm = fields.Integer(string="Alto interno (cm)", required=True)
    outer_length_cm = fields.Integer(string="Largo externo (cm)", required=True)
    outer_width_cm = fields.Integer(string="Ancho externo (cm)", required=True)
    outer_height_cm = fields.Integer(string="Alto externo (cm)", required=True)
    tare_weight_g = fields.Integer(
        string="Peso caja y embalaje (g)",
        help="Peso de la caja vacía más el material de embalaje habitual.",
    )
    max_weight_g = fields.Integer(string="Peso máximo bruto (g)", required=True)
    volume = fields.Integer(compute="_compute_volume", store=True)

    @api.depends("inner_length_cm", "inner_width_cm", "inner_height_cm")
    def _compute_volume(self):
        for box in self:
            box.volume = (
                box.inner_length_cm * box.inner_width_cm * box.inner_height_cm
            )

    @api.constrains(
        "inner_length_cm",
        "inner_width_cm",
        "inner_height_cm",
        "outer_length_cm",
        "outer_width_cm",
        "outer_height_cm",
        "tare_weight_g",
        "max_weight_g",
    )
    def _check_shipping_box_dimensions(self):
        for box in self:
            inner = (
                box.inner_length_cm,
                box.inner_width_cm,
                box.inner_height_cm,
            )
            outer = (
                box.outer_length_cm,
                box.outer_width_cm,
                box.outer_height_cm,
            )
            if any(value <= 0 for value in inner + outer):
                raise ValidationError("Las medidas de la caja deben ser mayores a cero.")
            if any(inside > outside for inside, outside in zip(inner, outer)):
                raise ValidationError(
                    "Las medidas externas no pueden ser menores que las internas."
                )
            if box.tare_weight_g <= 0 or box.max_weight_g <= box.tare_weight_g:
                raise ValidationError(
                    "Ingresá una tara positiva y un peso máximo superior a ella."
                )
            if max(outer) > 150 or box.max_weight_g > 25000:
                raise ValidationError(
                    "Correo Argentino admite hasta 150 cm por lado y 25.000 g por bulto en la cotización."
                )
