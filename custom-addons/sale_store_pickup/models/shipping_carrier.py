from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    x_is_correo_argentino = fields.Boolean(
        string="Cotizar con Correo Argentino MiCorreo",
        help="Nest calcula los bultos y consulta los servicios de MiCorreo. El precio fijo del transportista es el importe que paga el cliente en la tienda.",
    )
